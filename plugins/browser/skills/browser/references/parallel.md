# Several browsers, several agents

Two separate problems hide behind "run agents in parallel". Isolation solves the
first and does nothing about the second:

```
  BROWSER STATE                      APPLICATION STATE
  one window per agent               one server, shared by everyone
  cookies, profile, page             settings, flags, records
  ── solved by sessions ──           ── solved by agreement ──
```

## Sessions

Every browser gets a name, and every action is addressed to that name. Without
it, agents attach to the same default session: one agent's navigation resets
another's page, one agent's close kills another's browser, and snapshots land on
the wrong screen.

```bash
bash scripts/launch.sh --count 3 --session review --allow-install
# → review-1, review-2, review-3, each with its own profile
```

Hand each agent its session name in the prompt that starts it. Subagents share
the parent's MCP servers but not its shell, so a subagent addressing
`-s=<its own session>` gets its own browser — this is the whole reason the CLI
is the default.

Under the hood every call carries `-s=<session>`:

```bash
bash "${CLAUDE_SKILL_DIR}/scripts/pw.sh" -s=review-1 snapshot
bash "${CLAUDE_SKILL_DIR}/scripts/pw.sh" -s=review-1 click e3
bash "${CLAUDE_SKILL_DIR}/scripts/pw.sh" -s=review-1 fill e4 "text"
bash "${CLAUDE_SKILL_DIR}/scripts/pw.sh" list                     # who else is running
bash "${CLAUDE_SKILL_DIR}/scripts/pw.sh" -s=review-1 close        # only yours
```

The failure this prevents is silent, which is what makes it worth the
discipline. A launch against a blocked browser fails loudly and you go and fix
it. A missing `-s=` looks like it worked — right up to the point where you
report that a page renders correctly and it was somebody else's page.

**Never** run `close-all` or `kill-all`. They end other agents' work with no
warning and no way to tell what was lost. `scripts/launch.sh --stop <name>`
closes exactly one session and refuses anything broader.

## How much parallelism, and of what kind

| Shape | What it costs | When it fits |
| ----- | ------------- | ------------ |
| **CLI sessions** — N browsers, one Claude session | ~400 MB RAM each | The default. Subagents can each hold one. |
| **Separate Claude sessions** — one browser each | A worktree or clone per agent | Long independent workstreams, such as a test-automation repo with one clone per agent. |
| **One browser, page-ID routing** | Shared cookies, shared login, shared everything | Read-only fan-out on a memory-starved machine. |

Above four browsers the machine becomes the limit before the tooling does; the
launcher asks for confirmation rather than deciding for the user.

**Fan-out shares one IP.** Several sessions hitting the same public site in the
same minute looks like automation to that site, because it is. Against anything
public, expect a rate limit or bot check to catch some fraction of the fan-out —
an HTTP 429 or a `/sorry/` interstitial rather than the page. Have each agent
report that as what it is instead of retrying into the block. Internal staging
or review environments do not care.

Each session has its own cookie jar, so a consent or cookie wall has to be
dismissed once **per session**, not once for the fan-out.

Know which profile convention is in play; mixing them up costs an afternoon:

- This skill: `~/.cache/claude-browser/<session>/` (or under
  `BROWSER_PROFILE_ROOT`) — survives a reboot.
- A test-automation repo may keep its own Playwright profiles elsewhere, for
  example `/tmp/pw-$PLAYWRIGHT_SESSION` with one `PLAYWRIGHT_SESSION` per repo
  clone set in that clone's `.env`. Disposable by design, because the clones
  are.

## Working alongside other agents

Assume you are not alone unless you have been told otherwise. `--list` shows
who else is running.

### What is yours

Your session, your profile, your pages, and the records you created. Do what you
like with them.

### What belongs to everyone

Changing any of these breaks whatever another agent is midway through, usually
in a way that looks like a bug in their feature rather than interference:

- Global and organisation-level settings
- Feature flags
- Shared configuration, such as teams, departments or workspaces
- Preferences and saved state of a login you share with another session
- Anything described in the UI as applying "to all users" or "to the whole
  organisation"

If your task needs one of these changed, **stop and report the blocker**. Do not
change it and undo it afterwards either — another agent will read it in the
window where it was wrong.

The exception is being told you are the only one running. Then change what you
need, and say what you changed.

### Keeping your data apart

Each session gets a marker (its name, uppercased, recorded in
`<profile>/session.json`). Prefix records you create with it — `REVIEW-1 Test
Customer` rather than `Test Customer`. Two agents both editing "Test Customer"
produce a bug report that reproduces for nobody.

Prefer creating a record to editing a shared one, even when editing is fewer
clicks. Creating is invisible to everyone else; editing is not.

## Coordinating a fan-out

If you are the one splitting the work, allocate before anyone starts:

| Give each worker | So that |
| ---------------- | ------- |
| Session name | Its actions cannot land in another's browser |
| Login | Two agents are not fighting over one user's state |
| Data marker | Its records are identifiable |
| Its slice of the app | Different areas or sections where possible |
| A report path | Its findings survive whatever happens to the agent |

**Have each worker write its report to a file, as its last action.** A returned
message is not a reliable channel for a fan-out: it can arrive minutes after the
agent goes quiet, arrive twice, or not arrive at all, and an agent that has gone
idle is not there to ask again. A file is there either way.

Give the fan-out a run id and put the reports under it, rather than in the
session directories. Profiles are reused between runs, so a session-scoped path
means last run's report is already sitting there — and an existence check would
count it as this run's worker finishing.

```bash
# coordinator, once
RUN_DIR="$HOME/.cache/claude-browser/runs/$(date -u +%Y%m%dT%H%M%SZ)-$$"
mkdir -p "$RUN_DIR"

# handed to each worker, exact path, no globbing on their side
REPORT="$RUN_DIR/<session>.md"
```

Workers write to a temporary file and move it into place, so the coordinator
never reads a half-written report:

```bash
printf '%s\n' "$body" > "$REPORT.part" && mv "$REPORT.part" "$REPORT"
```

The coordinator then reads only its own run, and a missing file means that
worker did not finish:

```bash
for r in "$RUN_DIR"/*.md; do
  [ -e "$r" ] || continue
  printf '\n=== %s ===\n' "$(basename "$r" .md)"
  cat "$r"
done
```

**Do not sleep or poll while waiting.** Background work re-invokes you when it
completes, so a `sleep` in the coordinator buys nothing and holds the turn open
while the notifications queue behind it. Yield instead, and read the reports
when you are called back.

Ask for a message too, by all means. Just do not let the run depend on it, and
do not read silence as failure — check the files before concluding an agent came
back with nothing.

Then read the plan back for collisions. Two tasks that both need the same flag
or setting changed do not run at the same time — they run one after the other,
however tempting the parallelism looks. If the work cannot be split without
agents interfering, say so and run it in sequence. A sequential result that is
true beats a parallel one that has to be redone.

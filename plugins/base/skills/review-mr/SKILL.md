---
name: review-mr
description: "Review a GitLab merge request or a GitHub pull request in an isolated worktree and post the findings in the user's name as one review (drafts, then one submit with a verdict), with range anchors, suggestion fences and every low in one thread. Asks upfront whether to review with Claude, Codex, or both, and at what effort, checks the branch out at head_sha against the MR's own target branch, loads the repo's review rules from ~/.claude/review-rules/, finds the MR for the same change in the paired repo when the rules name one and reviews the boundary between the two, or both in full, reads the existing threads first so a re-review validates our earlier findings instead of repeating them, cuts the changed files into contract-sized slices with one Haiku owner each (Opus with --fast) that also checks the repo's own instruction files, runs the repo's lint, type and test commands with no LLM (skip with --no-checks), runs changed scripts and hooks in a throwaway sandbox, runs the review in two waves so the second one hunts the ground the first left unopened, at most --max-parallel agents at once, then sends an Opus refutation agent with a browser and the code that owns the product rules to break the survivors before anything is drafted, then shows the draft comments and the proposed thread actions, each summarised in plain English, for acceptance before anything reaches the MR. On a re-review where only a couple of mediums and some lows remain, it offers to close the MR instead: every remaining finding in one non-blocking comment plus an approval. Records each agent's role, model and the findings it produced in run.json for the usage report, then sweeps its temp folders and removes the review worktrees it created (keep them with --keep-worktrees). Use when the user asks to review an MR or PR, or runs /base:review-mr. Nothing is posted, resolved or approved without the user's acceptance."
argument-hint: "<mr-or-pr-url | !iid> [<second url>] [--both] [--finish | --no-finish] [--fast] [--no-checks] [--keep-worktrees] [--max-parallel N]"
effort: high
dependencies:
  - browser
  - writing-style-guide
  - humanizer
  - usage
---

# Review an MR and post the comments

For reviewing someone else's merge request or pull request and leaving inline
feedback on it. "MR" below means either. Use the user's writing-style skill for
the comment prose when one is installed: **writing-style-guide** (which pulls
in **humanizer**) ships in this same plugin. Both are
optional; without them, follow the comment rules in step 6 alone. They matter
when present: the findings are only useful if a colleague can act on them, and
unreadable walls of text get skipped.

Input is an MR URL or `!iid`, optionally followed by `--finish` (force finish
mode, step 6a) or `--no-finish` (never offer it). A second MR URL from the
paired repo, or `--both`, asks for a full review of both halves of the change
(step 1a). The other flags:

- `--fast` - wave 1 and wave 2 on Opus at the base effort instead of Haiku at
  max (step 4). Faster, not better.
- `--no-checks` - skip the deterministic checks (step 4a) and the run-it
  agent (step 4b), for an author whose code you do not want to run.
- `--keep-worktrees` - keep the review worktrees this run created (step 8).
- `--max-parallel N` - at most N wave-1 and wave-2 agents at once, default 12
  (step 4).

Nothing is posted, resolved, reopened or approved until the user accepts.

Two things shape the whole run. A single review pass misses things that a second
pass finds, so step 4 runs two waves and the second one is aimed at what the
first left unopened. And an MR that already carries our comments is a
re-review, not a first look, so step 3 happens before any reviewing at all.

## How this skill is built

- **Core** - this file: the review procedure, from engine and effort through
  worktree, sizing, waves, refutation, grading and acceptance to posting.
- **Agent brief** - `references/agent-brief.md`: what every review agent is
  told, including the coverage ledger it reports.
- **Run-it brief** - `references/run-it-brief.md`: the throwaway sandbox and
  the "promises versus behaviour" table for the run-it agent (step 4b).
- **Platforms** - `platforms/gitlab.md` and `platforms/github.md`: how each
  platform fetches an MR, anchors comments, holds drafts, submits a verdict,
  and resolves or reopens threads.
- **Scripts** - `scripts/gitlab_comments.py` and `scripts/github_comments.py`,
  the platform clients with the same subcommands; `scripts/find_rules.py`,
  the rules lookup; `scripts/find_conventions.py`, the lookup of the repo's
  own instruction files (step 4); `scripts/run_checks.py`, the deterministic
  checks (step 4a).
  All stdlib Python, with tests in `tests/`.
- **Project rules** - `~/.claude/review-rules/<repo>.md`: everything specific
  to one repo or product (step 0a).
- **Browser** - the browser skill the rules name, or any installed skill
  named `browser` or `<plugin>:browser`, for the refuters' in-browser checks.
  Optional (step 5).

`$SKILL_DIR` below is the directory this SKILL.md was loaded from,
`$SCRIPT` is `$SKILL_DIR/scripts/gitlab_comments.py` or
`$SKILL_DIR/scripts/github_comments.py` for the MR's platform (step 0a), and
`$SCRATCH` is this session's scratchpad directory. Both scripts take
`--project` (GitLab: numeric id or URL-encoded path; GitHub: `owner/repo`) and
`--iid` (the MR iid or PR number), and offer the same subcommands, so every
command below reads the same on both platforms.

These names, and `$RUN_TMP` (step 1), are placeholders, not shell variables:
the Bash tool keeps no variables between calls, so write the literal absolute
path into every command.

## 0. Choose the review engine, the counterpart scope and the effort

These questions are the run's **first tool call** - before reading the rules,
running `refs`, fetching, or anything else. They need nothing from the MR, and
the user should not wait through setup to answer them. Use **AskUserQuestion**
once, with three questions.

The engine:

- `Claude (Recommended)` - Haiku slice owners at max effort, with Opus
  refuters (step 4 and 5).
- `Codex` - the same slices and waves, run as Codex tasks instead.
- `Both` - run both and compare, weighting every finding the same regardless of
  which engine produced it.

The counterpart, asked before anyone knows whether one exists, since the two
halves of a change in paired repos (a frontend and its backend, say) usually
ship as two MRs:

- `This MR + contract check (Recommended)` - review this MR in full and read
  the other repo's MR only for the boundary between the two.
- `Full review of both` - review both MRs in full, as one change.

Skip the second question when the user passed `--both` or two MR URLs: that is
`Full review of both` already.

The effort of the Opus roles (refuters, thread validation, and wave 1 and 2
under `--fast`) and the `--effort` of every Codex task:

- `Medium (Recommended)` - the default.
- `Low` - cheaper, for a small or familiar MR.
- `High` - for a risky change.

Haiku agents from the role table always run at max, whatever the answer. Do
not ask about the model: the `## Models` lines, the role table in step 4 and
`--fast` carry it.

Carry the answers through as `<engine>`, `<scope>` and `<effort>`. `<engine>`
changes only which pass(es) run in step 4 and the merge behaviour in step 5 when
it is `Both`; `<scope>` only matters once step 1a finds a counterpart;
`<effort>` is the base effort in the role table (step 4) and the `--effort` of
every Codex task.

With `--fast` and `<engine>` `Codex` alone, say in one line that `--fast` does
not apply to Codex, then run the Codex review as usual.

## 0a. Platform and project rules

**Platform.** Read it off the MR URL's host, or, for a bare `!iid`, off
`git remote get-url origin` of the checkout: `github.com` is GitHub, `gitlab`
in the host is GitLab. A rules file may set `Platform:` for a self-hosted host
that names neither. Read `$SKILL_DIR/platforms/<platform>.md` now and follow it
wherever a step says "the platform file". Set `$SCRIPT` to that platform's
script.

**Project rules.** Find the rules file for the MR's repo:

```bash
python3 $SKILL_DIR/scripts/find_rules.py --repo-name <last segment of the MR's project path>
```

Run from inside a checkout of the repo, it can read the name off
`git remote get-url origin` instead (omit `--repo-name`); the remote, not the
directory name, so a worktree resolves the same as its main checkout. It
prints one JSON object: `path` (the rules file, or `null`), `expected` (the
exact path it looked for), `repo`, and `skipped` (rules files whose frontmatter
could not be read, with the reason). Mention any `skipped` entry to the user in
one line: a typo there reads like "no rules".

Read the rules file whole when there is one. It may hold: the repo's checkout,
worktree base and project id; a counterpart repo and its pairing rule; size
excludes; details for the core lenses and extra lenses with the paths that
trigger them; the checkout refuters read product rules from; the browser skill
to use; the repo's own review material, including the comments file the
Comments lens needs; product-consequence examples for grading; and machine
notes for
running git or the platform CLI. Where a step below says "the rules", it means
this file.

When `path` is `null`, show this notice, framed, then **continue without
rules**: no counterpart lookup, no extra lenses or excludes, no refuter
checkout beyond the MR's own worktree.

```text
────────────────────────────────────────────────────────────────────
 No review rules for <repo>
 Looked for: <expected>
 A rules file there (or any *.md in ~/.claude/review-rules/ whose
 frontmatter lists <repo> under applies-to:) adds the paired repo,
 size excludes, extra lenses and the browser skill. Continuing
 without rules.
────────────────────────────────────────────────────────────────────
```

### Project rules: the format

Rules live in `~/.claude/review-rules/`. A file named `<repo>.md`, where
`<repo>` is the last segment of the repo's remote URL without `.git`, applies
to that repo. One file can serve several repos through its frontmatter:

```yaml
---
applies-to: [backend-repo, frontend-repo]
---
```

Only the frontmatter is parsed; the body is prose for the review to read, and
any section may be left out. A minimal example:

```markdown
---
applies-to: [shop-api, shop-web]
---

# Review rules: shop

## Repos

| repo       | label | checkout            | worktree base                 | `--project`       |
| ---------- | ----- | ------------------- | ----------------------------- | ----------------- |
| `shop-api` | BE    | `~/code/shop-api`   | `~/code/shop-api.worktrees/`  | `acme/shop-api`   |
| `shop-web` | FE    | `~/code/shop-web`   | `~/code/shop-web.worktrees/`  | `acme/shop-web`   |

## Counterpart

The sibling of `shop-api` is `shop-web` and the other way round; pass the other
row's project as `--sibling`. Pairing rule: both halves share a branch name.

## Size excludes

':(exclude)**/locales/**' ':(exclude)**/migrations/**'

## Lens details

- **i18n** - the locale files are `web/locales/**`.
- **Payments** (extra lens) - wherever `api/billing/**` changes: amounts,
  currencies, refunds.

## Refuters

- Checkout for product rules: `~/code/shop-api`.
- Browser skill: `browser`.

## Repo review material

- `docs/review/CORRECTNESS.md`
- Comments file: `docs/review/comments.md`

## Product consequences

High: an order charged twice, one shop seeing another shop's orders.
```

## 1. Locate the repo and its review worktree

Take the repo's local checkout, worktree base and `--project` from the rules.
Without rules, a session already inside a checkout whose `origin` is the MR's
project uses that checkout, with `<repo>.worktrees/` as the worktree base and
the project path from the MR URL as `--project`. A repo found neither way is
the only reason to ask the user anything in this step: ask once for its local
clone, then carry on as below.

Work in `<base>/reviews`. Whether it exists is settled by
`git -C <repo> worktree list`, not by guessing from the session's working
directory or asking - an existing `reviews` worktree is reused, since step 2
checks out the MR head in it anyway. Before reusing it, run
`git -C <base>/reviews status --porcelain`; when it lists anything, stop and
ask the user, since edits and untracked files there would be reviewed and
tested as part of the MR. Create it only if that list lacks it:

```bash
git -C <repo> fetch origin <default branch>
git -C <repo> worktree add <base>/reviews origin/<default branch>
```

If the rules carry machine notes for git (a sandbox that blocks one of these,
say), run each command the way they say. Never work in the primary checkout - it
usually holds uncommitted work on an unrelated branch, and a review must not
disturb it.

Note whether this run created the worktree. A created one goes into
`worktrees_created` in `run.json` (step 2a) and is removed in step 8; a reused
one is never removed. The same goes for the counterpart's worktree in full
scope.

### The run's temp dir and the status snapshots

Every agent of this run works under one temp dir in the session scratchpad,
so the sweep in step 8 is a single delete. Snapshot the git status of the
primary checkout and the review worktree now, so step 8 can tell which
untracked files the run left behind:

```bash
RUN_TMP=$(mktemp -d -p "$SCRATCH" review.XXXXXX) && echo "$RUN_TMP"
git -C <repo> status --porcelain=v1 -z -uall > "$RUN_TMP/status-primary.before"
git -C <base>/reviews status --porcelain=v1 -z -uall > "$RUN_TMP/status-review.before"
```

Note the printed path: it is `run_tmp` in `run.json` and the literal value
of `$RUN_TMP` in every later command. Give that absolute path in every agent
brief. A stopped run leaves a
`review.XXXXXX` dir in the scratchpad, which `/base:cleanup` lists.

## 1a. Find the counterpart MR

Only when the rules name a counterpart repo; otherwise skip this step. The rules
give the pairing rule - usually that the two halves of a change share a branch
name - and the description sometimes links the other one:

```bash
python3 $SCRIPT --project <id> --iid <iid> counterpart --sibling <sibling project>
```

It prints every open sibling MR on the same source branch or linked from the
description, with its url, refs and draft state, or `none`. A second MR URL the
user passed is the counterpart, whatever the lookup says.

- **None found** - carry on as a single-MR review and say so in step 7.
- **More than one** - ask which, once, in the step 7 summary if not sooner.
  Never pick by guessing.
- **A Draft** - read it for context, never post on it: its author has not
  asked for review yet. A draft counterpart forces contract scope.

From here on, "the counterpart" is that MR, `<cp_iid>` its iid and
`<cp_project>` the sibling project. What it adds to each step depends on
`<scope>`:

| step | contract check (default)                                              | full review of both                                     |
| ---- | --------------------------------------------------------------------- | ------------------------------------------------------- |
| 2    | save its diff only                                                    | its own reviews worktree at its `head_sha`, as step 1-2 |
| 3    | its threads, only to drop duplicates                                  | its threads, re-review validation included              |
| 4    | one **contract agent** in wave 1                                      | its files sliced by the same rule, plus one contract agent |
| 5-7  | contract findings only; those whose proof sits in its code post on it | every finding posts on the MR whose code it is about    |

Save its diff either way:

```bash
python3 $SCRIPT --project <cp_project> --iid <cp_iid> diff --out $SCRATCH/counterpart.diff
```

In contract scope, read the counterpart's files at its head through the
platform API (the platform file has the command), not from the primary checkout
of that repo, which sits on an unrelated branch.

## 2. Check out the MR at head, against its own base

```bash
python3 $SCRIPT --project <id> --iid <iid> --repo-dir <repo> refs \
  --description-out $SCRATCH/description.md
```

`refs` also prints the MR title and writes its description to that file; both
go into every agent's brief.

Then in the reviews worktree: fetch the source branch (the platform file says
how; a fork's branch needs its own ref) and check out the MR's `head_sha`.
Confirm `git rev-parse HEAD` equals `head_sha` - if it doesn't, your line
numbers won't match the diff the platform renders and every anchor will be off.

**Diff against the MR's own base, which is often not main.** Stacked MRs target
another feature branch, and local `main` is usually days stale, so diffing
against either invents changes that aren't in the MR and you end up reviewing
somebody else's merged work. Use the `base_sha` that `refs` printed - that is
the merge-base the platform itself used - and tell every agent what the target
branch is, so nobody assumes main.

Save the diff now, so the agents read MR-head state rather than whatever the
worktree happens to contain:

```bash
python3 $SCRIPT --project <id> --iid <iid> diff --out $SCRATCH/mr.diff
```

### 2a. Plan the slices

Measure the reading load before planning any agents, because it decides how
many slice owners step 4 spawns. Reading load is the line count of the whole
changed files at head, not the changed lines: a 5-line change in a 900-line
file still needs the whole file read (brief step 1), so it counts 900. Leave
out lockfiles, locale files and generated files, which nobody reviews line by
line. The default pathspecs below cover lockfiles, minified files,
`*.generated.*`, `dist/` and `build/` output, `locales/`, JSON under `i18n/`
and `*.po` files at any depth, even when there are no rules; add the rules'
size excludes after them:

```bash
EXCL=(':(exclude)*.lock' ':(exclude)*-lock.*' ':(exclude)pnpm-lock.yaml'
  ':(exclude)go.sum' ':(exclude)*.lockb' ':(exclude)npm-shrinkwrap.json'
  ':(exclude)packages.lock.json'
  ':(exclude)*.min.js' ':(exclude)*.min.css' ':(exclude)*.generated.*'
  ':(exclude)*.po' ':(exclude,glob)**/dist/**' ':(exclude,glob)**/build/**'
  ':(exclude,glob)**/locales/**' ':(exclude,glob)**/i18n/**/*.json'
  <the rules' size excludes>)
GD=(git -C <worktree> -c core.quotePath=false diff --name-only --no-renames <base_sha> <head_sha>)
"${GD[@]}" > "$RUN_TMP/changed.txt"
"${GD[@]}" -- . "${EXCL[@]}" > "$RUN_TMP/counted.txt"
grep -vxFf "$RUN_TMP/counted.txt" "$RUN_TMP/changed.txt" > "$RUN_TMP/excluded.txt"
while IFS= read -r f; do
  printf '%s\t%s\n' "$(git -C <worktree> show "<head_sha>:$f" 2>/dev/null | wc -l)" "$f"
done < "$RUN_TMP/counted.txt" > "$RUN_TMP/load.tsv"
awk -F'\t' '{ n += $1 } END { print n+0, NR }' "$RUN_TMP/load.tsv"
```

The excludes apply to the line count only. `changed.txt` keeps every changed
file, and no file in `excluded.txt` is silently dropped: give each one to the
owner of the slice that changed its source (a lockfile to the slice with its
manifest, a locale file to the slice with the component that uses the key),
as a lightweight file that adds 0 lines of load and gets a "check it matches
its source" read, not a line-by-line one. List any excluded file that no slice
fits under "Not reviewed" in the step-7 summary.

A deleted file counts 0 (`git show` finds nothing at head). Also keep the old
changed-line count as `reviewed_lines`, so this run compares with earlier
ones:

```bash
git -C <worktree> diff --numstat <base_sha> <head_sha> -- . "${EXCL[@]}" \
  | awk '$1 != "-" { n += $1 + $2 } END { print n+0 }'
```

**Cut the slices.** Group the files by tool contract or component: a script
with its tests and the doc section that describes it, a hook with its
`hooks.json` entry, a component with its composable and spec. Then cut to a
target of **about 400 lines of whole files per slice, hard limit about 700**.
A file above the limit is its own slice; above about 1,500 lines it splits
into ranges of about 700 lines, one slice each, and the slice block names
the range. Write the plan to
`$RUN_TMP/slices.json` as `[{slice, files: [{path, lines}], load}]`.

There are no size tiers and no whole-MR lens agents: a small MR is one slice
with one owner. In the counterpart's full scope, its changed files get slices
of their own by the same rule.

Why this size: benchmark run E (three component-sized Haiku slices of about
1,000 lines, `~/.claude/model-bench/review-hooks-browser/RESULTS.md`) caught 9
of 14 known bugs with 87% of requests over 100k tokens, while run D's seven
small slices caught 13 of 14 for $0.39 per caught bug against $0.47. Wider
slices grow each agent's context and miss more. On PR #238 one agent on a
small scope found what eleven lens and slice agents missed.

Start `$SCRATCH/run.json` now and keep it current for the whole run. It is how
a later run can tell whether these settings found more, and the `usage`
report reads it to price the run by role and slice, so it is not optional:

```json
{
  "mr": "<url>", "round": 1, "head_sha": "<sha>", "base_sha": "<sha>",
  "reviewed_lines": 812, "reading_load": 2905, "files": 23, "effort": "medium",
  "fast": false, "engine": "claude",
  "session_id": "<session id>",
  "transcript_dir": "~/.claude/projects/<project dir>/<session id>/subagents",
  "run_tmp": "<RUN_TMP>",
  "worktrees_created": ["<base>/reviews"],
  "agents": [
    {"agent_id": "<id the Agent call returned>", "role": "slice-owner",
     "slice": "slice-2", "model": "haiku", "effort": "max",
     "model_name": "Haiku 5.5", "model_source": "user",
     "files": ["hooks/guard.sh", "hooks/hooks.json"],
     "report": "$SCRATCH/wave1-slice-2.txt"}
  ],
  "findings": [
    {"id": "slice-2-1", "draft_id": "H1", "source": "slice-2",
     "duplicates": ["runit"], "survived": true}
  ],
  "checks": {"findings": [], "pre_existing": [], "not_run": [], "untrusted": []}
}
```

`$SCRATCH` is `.../<project dir>/<session id>/scratchpad`, so the session id
is the name of its parent dir and the project dir the one above that.
`agent_id` is the id the Agent call returns (`agent-<agent_id>.jsonl` is its
transcript). `role` is one of `slice-owner`, `contract`, `runit`, `gap`,
`e2e`, `refuter` and `thread-validation`; a Codex task gets `"model": "codex"`.
`model_name` and `model_source` come from "Agents, models and effort";
`model_name` is left out when the table was used.
For each finding that survives refutation, `source` is the agent that first
reported it and `duplicates` every agent that repeated it. `run.json` holds no
cost and no resolved model id: the `usage` skill reads both from each agent's
transcript and is the only place that prices a review run.

## 3. Read the thread state before reviewing

```bash
python3 $SCRIPT --project <id> --iid <iid> threads --out $SCRATCH/threads.json
```

Read every thread, ours and everyone else's. Do the same for the counterpart
(`$SCRATCH/counterpart-threads.json`): in contract scope only to drop findings
it already carries, in full scope with the validation below too. Two things come
out of this.

**Is this a re-review?** Any thread opened by us means yes. Colleagues resolve
our comments as they push fixes, sometimes with a reply, sometimes without, and
sometimes the fix does not actually close the finding. Validating that is the
first job of a re-review, before any new reviewing - and it is the part that is
easy to skip, because a resolved thread looks finished.

**What is already covered?** Bots (CodeRabbit and the like) and human reviewers
may have said it already. A finding that repeats an open thread does not get
posted again, it gets dropped. Note what is covered and carry it into step 4.

**What did our last round weigh?** Each of our threads carries a `severity`
parsed from its opening line, and a `head_sha`. Our previous round is our
threads with the most recent `head_sha`; count them by severity and carry the
count into step 6a.

### Validating our own threads

Our old comment is anchored at the `head_sha` it was written against, so its
line number usually points somewhere else now. **Find the code by content, not
by line** - read the file at the current head and locate what the comment was
about. A comment that still points at the same line by coincidence is the trap
here.

Then judge what actually landed, and pick the action:

| what you find                                                               | action                                           |
| --------------------------------------------------------------------------- | ------------------------------------------------ |
| fix is real, thread already resolved, and our last note isn't a closing one | reply `✅ Verified` with `--resolve`             |
| fix is real, thread already resolved, we already closed it                  | nothing                                          |
| fix is real, thread still open                                              | reply `✅ Verified` with `--resolve`             |
| the finding still stands, thread resolved                                   | reply with what still stands, `--reopen`         |
| the finding still stands, thread still open                                 | nothing, unless the reply asked us something     |
| the code is gone or reverted, so the finding no longer applies              | reply `Does not apply anymore.` with `--resolve` |

Every closing reply carries `--resolve`, resolved thread or not. The platform
file says why on that platform (on GitLab, publishing a draft reply without it
reopens the thread).

`✅ Verified` means exactly that string and nothing else. When a colleague did
what we asked, there is nothing to add, and a paragraph of appreciation is
noise in a thread they have already finished with. Same for
`Does not apply anymore.` - it is a full answer.

The one case that earns prose is a fix that does not close the finding. Say
what still stands in two or three sentences, name the `file:line` at the
current head, and stop. That thread is being reopened over someone's
"Resolving, reopen if...", so it has to carry its reason.

**Never resolve a thread we did not open.** Not a bot's, not a
colleague's - resolving somebody's thread claims their finding is dealt with,
which is theirs to say. `resolve`/`unresolve` refuse it outright, but the
refusal is a backstop, not the rule. Replying on their thread is fine when we
have something to say.

## 4. Review in two waves

Run whichever engine(s) `<engine>` selected, from inside the reviews worktree
checked out at `head_sha`.

- **Codex** - the same two waves as below, slice owners, contract agent, brief
  and gap hunt included, with each agent run as a Codex task instead of an
  Agent call: one Codex task per slice, no lens tasks. It needs the
  `openai-codex` Claude Code plugin; when its companion script is missing, say
  so and offer the Claude engine instead:

  ```bash
  CODEX=$(command ls -d ~/.claude/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs \
    | sort -V | tail -1)
  node "$CODEX" task --background --fresh --effort <effort> "<brief + slice>"
  ```

  What differs from the Claude agents:
  - A task runs read-only without network: no platform CLI, `curl` or file
    writes. Its report comes back as its reply; collect it with
    `node "$CODEX" result <job>` and save it to `$SCRATCH/wave<n>-<slice>.txt`
    yourself. Tell it so in the brief, and that claims it cannot measure are
    derived.
  - The harness does not track the jobs. Watch them from the main session with a
    background loop over `node "$CODEX" status --json` that exits when none is
    running, and check its first poll returned a real count. Never from a
    subagent, which is not woken when its loop ends.
  - Not the native `review` / `adversarial-review`: they take no effort and no
    brief, so they cannot be pointed away from what is already found.
  - Haiku and `--fast` do not apply, and the run-it agent (step 4b) is skipped.
    The checks (step 4a) and the conventions lookup still run.

- **Both** - launch the Claude wave 1 and the Codex wave 1 at the same time, both
  in the background, so neither blocks the other; wave 2 then works the ground
  both left dark.
  Pool every finding from every pass before verification. Don't label findings by
  source, and don't let either engine win a disagreement by default - resolve it
  like any two agents disagreeing, against the code. When both flag the same
  issue, merge it into one comment.

### Agents, models and effort

Every Agent call in this skill passes `model` and `effort` explicitly and
records both in `run.json`.

Before spawning, read the `## Models` section of `~/.claude/CLAUDE.md`, then of
the repo's `CLAUDE.md`; when both have a line, the repo's wins. These lines set
a role's model and effort:

- `- Review slices:` every role below except refuters and thread validation.
- `- Review refuters:` refuters and thread validation.
- `- Review with --fast:` the slice roles when `--fast` is given.

Map the model name to the Agent alias (Haiku `haiku`, Sonnet `sonnet`, Opus
`opus`, Fable `fable`) and keep the full name (`Haiku 5.5`) in `run.json` as
`model_name`. A role with no line uses this table and `<effort>` (step 0);
"base" is `<effort>`. Record `model_source` per agent: `user`, `repo` or
`table`.

| role                                   | model, effort | with `--fast`  |
| -------------------------------------- | ------------- | -------------- |
| wave 1 slice owners                    | haiku, max    | opus, base     |
| wave 1 contract agent (counterpart)    | haiku, max    | opus, base     |
| wave 1 run-it agent (step 4b)          | haiku, max    | opus, base     |
| wave 2 gap agents                      | haiku, max    | opus, base     |
| end-to-end simulation (optional)       | haiku, max    | opus, base     |
| refuters (step 5)                      | opus, base    | opus, base     |
| thread validation (step 3)             | opus, base    | opus, base     |

Why: on the hooks and browser benchmark, Haiku at max with the brief's "does
NOT set" lens caught 13 of 14 known bugs for $5.08, where Opus at medium on
component slices caught 6 for $6.38, and one Haiku agent found the push-gate
bypass on PR #238 that eleven Opus agents missed. Refutation stays on Opus
because its errors are the expensive kind: a wrong finding that survives lands
on a colleague's MR. Refuters run at the base effort, not one above: high gave
the same verdicts as medium for 59% more. `--fast` exists because Haiku runs
are about 2.5x slower; it is faster, not better.

### Who runs in wave 1

- **Slice owners.** One agent per slice from step 2a, named `slice-<n>`. Each
  reads its files whole, applies every lens below to them, and greps every
  consumer of each changed export. There are no whole-MR lens agents at any
  size: a small MR is one slice with one owner.
- **Contract agent.** Only when step 1a found a counterpart: exactly one
  agent, named `contract`, with both diffs and the Contract lens below. There
  is no other cross-file agent: in benchmark runs B, D and E it added no bug
  the slices missed, and in run B it was the most expensive agent. Seams
  between slices are covered by each owner grepping every consumer.
- **Run-it agent.** Step 4b says when.
- **End-to-end simulation (optional).** Use it when the MR changes a
  multi-step flow that can be driven against a stub, whatever the size: a
  script or skill that calls an API across rounds, a state machine. It is the
  most expensive agent in the logs and found one survivor on !121,
  independently of a slice owner.

**Batching.** Run at most `--max-parallel N` wave-1 and wave-2 agents at once,
default 12, and start the next queued agent as one finishes. Do not ask about
the count, and never merge slices to need fewer agents: a big MR takes longer
instead. 12 is this skill's own limit, not a known Claude Code one; lower it
on machines or plans that limit concurrent agents.

Finding ids carry their source agent's prefix (`slice-2-1`, `contract-1`,
`runit-1`, `e2e-1`, `check-1`) from the report through refutation into the
draft files, so `run.json` can say which agent produced each survivor.

### Why two waves

One pass finds a subset, and which subset varies between runs. Running the same
pass twice mostly re-finds the same things, because the two runs read the same
diff the same way. So wave 2 is not a repeat: it is handed wave 1's findings and
wave 1's coverage ledgers, and sent at the ground nobody opened. That is the
same thing that makes a manual re-review productive - you already know what was
caught, so you look elsewhere.

### Wave 1: breadth

Every slice owner applies these lenses to its files, the first three always,
the rest where the slice touches what they are about:

- **Correctness** - the mechanism that misbehaves, with its trigger.
- **Product behaviour** - what a user sees, and whether it matches what the MR
  description claims. Description-versus-code is a finding nobody gets from
  reading the diff.
- **Error paths and silent failures** - swallowed errors, fallbacks that hide a
  broken call, an empty state that means "failed" and reads as "none".
- **What the code does NOT set** and **repo conventions** - standing sections
  of the brief, applied to every slice.
- **Tests** - only where the MR changes behaviour that could be covered.
- **Accessibility and design system** - on frontend files touching markup,
  design-system components or CSS.
- **i18n** - wherever locale files or user-visible strings change.
- **Types and API contracts** - where signatures, schemas or generated types move.
  When none moved, skip it and say why.
- **Comments** - only when the rules name a comments file and that file exists
  at the reviewed head: `git -C <worktree> cat-file -e <head_sha>:<path>`. When
  the rules name none, or the file is missing at head, skip this lens and say
  which of the two it was; the repo's instruction files (conventions entries
  below) still apply.
- **Extra lenses the rules list** under a name not above, in the brief of each
  slice whose files match their trigger paths. Where the rules describe a lens
  above (which design system, which locale paths), that wording goes into the
  brief of each matching slice. Neither starts an agent.
- **Contract** - the contract agent's lens, whenever step 1a found a
  counterpart. It gets both diffs and reads where the two halves meet, shape
  and logic both:
  - **Shape** - every field, type, nullability and enum value one side reads
    against what the other side serves; URLs and route names; feature-flag
    keys and their defaults; permissions; message and broadcast channel names.
  - **Meaning** - whether one side interprets each value the way the other
    computes it, not just whether the type matches: what a `null`, an empty
    list or a flag-off answer means on the side that serves it, and on the
    side that reads it.
  - **Duplicated rules** - a rule both sides implement, such as a permission
    check, a rounding rule or a state transition, has to agree on every input.
  - **End to end** - trace each user action the MRs change through both of
    them: click, request, backend logic, response, frontend state. Error
    responses, flag-off paths and cache invalidation after a write included.
  - **Deploy order** - each half merged and released alone, with the flag on
    and off, still has to work, since the two MRs rarely ship in the same
    release.

  In full scope the counterpart's files have slice owners of their own, but
  the contract agent still runs once, across both MRs.

**Repo conventions.** Before writing the briefs, look up the repo's own
instruction files (`CLAUDE.md`, `AGENTS.md`, Copilot and Cursor rules,
`CONTRIBUTING.md`, `.editorconfig`) once, for all changed paths, as they are
at `base_sha`:

```bash
python3 $SKILL_DIR/scripts/find_conventions.py --repo <worktree> \
  --ref <base_sha> --paths-file "$RUN_TMP/changed.txt" > "$RUN_TMP/conventions.json"
```

Put the entries for a slice's files into that slice's brief, under "Your
slice". The owner checks the diff against them and cites `path:line` of the
rule; no separate agent. An entry marked `changed` is an instruction file the
MR itself edits: the owner reads its rules at `base_sha` and reviews its diff
as code. `~/.claude/review-rules/<repo>.md` is read as before; the
conventions come in addition to it.

Give every agent the brief in `references/agent-brief.md` with the paths filled
in, `RUN_TMP` and the slice block included, the counterpart section included
whenever step 1a found one, then its lenses. The brief is what makes wave 2
possible: it obliges each agent to open every changed file whole, grep every
consumer of each changed export, and report a coverage ledger saying what it
did not examine and why.

If the repo ships its own review material - the rules name where it lives -
hand the relevant file to the slice owners whose files it covers. It is how
that repo wants its MRs read, and it is more specific than anything an agent
brings from general knowledge.

Each agent writes its report to `$SCRATCH/wave1-<slice>.txt` (`wave1-contract.txt`,
`wave1-runit.txt`) and replies with the path. A long reply truncates in transit
and the tail is lost silently. Some subagents are refused the report write by
their Write tool and reply with the report text instead: when a reply is not a
path, save it to that agent's report path yourself and go on, without asking
the agent again.

### Wave 2: the gap hunt

Merge the wave 1 ledgers into one list and work out what is still dark:

- changed files nobody examined
- every file on a report's `Unfinished:` line: that agent could not finish
  reading it, so wave 2 starts a fresh agent on exactly those files
- changed exports whose consumers nobody grepped
- the seams: where a changed file meets an unchanged one that assumes the old
  behaviour
- anything an agent declared out of scope

Skip wave 2 when there is one slice and its ledger leaves no dark ground: every
file examined and no `Unfinished:` line. Otherwise spawn fresh agents for wave
2, one per area of dark ground, each with the brief, the merged findings list
from wave 1 ("already found, don't repeat these") and its assigned ground.

Fresh rather than the wave 1 agents, which was tested head to head on one MR
with both variants working the same five areas. Reusing the wave 1 agents is
faster and they write better "I tried to break this and could not" sections,
but they carry their own conclusions with them: the reused agent that had
already cleared the department-switch path in wave 1 filed the same missing
option as a latent hazard and never tried the error path, while a fresh agent
on the same ground found it as a live defect. The fresh agents also caught that
their headline finding was pre-existing, which the reused ones asserted the
opposite of. That error is the expensive one, so fresh wins.

Reports go to `$SCRATCH/wave2-<area>.txt`, same rule about replying with the path.

### When an agent goes quiet

A subagent's plain text isn't visible to you. If an idle notification arrives
with no report path, `SendMessage` them: their output isn't visible, reply to
`main` with the path. Don't wait silently or assume they found nothing.

## 4a. Deterministic checks (no LLM)

Skip this step when the user passed `--no-checks`. Otherwise start it in the
background from the main session at the same time as wave 1, so it costs no
agent tokens. It runs the repo's own lint, typecheck, format-check and test
commands on the changed files in the review worktree:

```bash
python3 $SKILL_DIR/scripts/run_checks.py detect --repo <worktree> \
  --base <base_sha> --head <head_sha> --paths-file "$RUN_TMP/changed.txt" \
  > "$RUN_TMP/checks-plan.json"
python3 $SKILL_DIR/scripts/run_checks.py run --plan "$RUN_TMP/checks-plan.json" \
  --repo <worktree> --tmp "$RUN_TMP/checks" > "$RUN_TMP/checks.json"
```

- `detect` reads manifests and config as they are at `base_sha`, so the MR
  cannot change which commands are chosen. The chosen commands still run head
  code with the head's config, so pass or fail follows the head's lint, type
  and test config. It covers `package.json` scripts (`lint`,
  `typecheck`, `type-check`, `check`, `format:check`, `test`, `test:unit`) run
  with the package manager the lockfile names (pnpm when there is none),
  `eslint`, `prettier --check`, `ruff`, `mypy`, `pytest`, `go vet`, `go test`,
  `cargo check`, `cargo test` and `shellcheck`. `pytest` is planned only when
  a pytest config exists (`[tool.pytest` in `pyproject.toml`, `pytest.ini`
  or `[tool:pytest` in `setup.cfg`), and a project `.venv` tool is used
  before one on `PATH`. A manifest that is new in the
  MR is listed under `untrusted` and never run. A script runs by name, so the
  package manager reads its body at head: when its body, or the body of a
  script it runs by name, differs between base and head, it is listed under
  `untrusted` with "script body changed in this MR" and never run. A script
  with a fix flag runs in a check-only form or is skipped with the reason.
- `run` stops a command at 120 s and the step at 300 s, never passes a fix
  flag and never installs anything. A command whose dependencies are missing
  is skipped with "dependencies not installed", and a timeout is "not run",
  never a failure.
- The rules' machine notes apply as they do for git and the platform CLI:
  `--wrap "<prefix>"` runs every command through the prefix they name, and
  `--skip-deps-check` runs a command whose dependencies live somewhere the
  notes describe.
- A failing command is re-run at `base_sha` in a throwaway worktree under
  `$RUN_TMP/checks` (removed afterwards), on the same files. Only messages
  that are not also there become findings. A failing test is re-run once at
  head first, to rule out a flaky one. Head runs leave a quarter of the 300 s
  for base re-runs. When a base re-run times out or errors, or the base
  worktree cannot be made (`error` in the output), the command goes under
  `not_run` as "base run failed" with the reason and makes no finding. The
  base re-run uses the head's `node_modules` and `.venv`; the result's
  `base.deps` says `"head"` when it did, so a failure caused by a dependency
  bump in the MR can show as pre-existing. A head command that cannot start
  is "not run: could not start".
- `checks.json` holds `results`, `findings`, `pre_existing`, `not_run`,
  `base_worktree`, `base_worktree_removed` and `network`.

When nothing is detected, say so in one line and go on. Each entry of
`findings` is a finding with its `check-<n>` id and the command that produced
it. Its default severity is medium for a failing test or type error and low for
a lint or format failure (the lows thread); regrade by consequence in step 6, so
a failing test that shows a user-visible break may go higher. Check findings
were measured by a tool, so they skip refutation. Record `pre_existing`,
`not_run` and `untrusted` under `checks` in `run.json`; they are not posted.

## 4b. Run it

One run-it agent, in wave 1, on the wave-1 model (step 4), runs the
changed code in a throwaway sandbox and compares what it does with what the
docs promise. Reading did not find what running found on PR #238; one agent
doing it once is cheaper than every slice setting up a sandbox.

**Trigger.** Spawn it when the diff adds or changes runnable code beyond
comments and whitespace. Runnable code means:

- executable or shebang files
- scripts under `scripts/`, `bin/` or `hooks/`
- entries in `hooks.json` or a `package.json` `bin` or `scripts`
- skills that ship scripts

**Skip it** for documentation-only and frontend-only MRs (refuters cover the
browser), when fewer than about 30 runnable lines changed and no runnable file
was added (slice owners read that), under the Codex engine alone, and when
the user passed `--no-checks`, saying why in one line.

Give it the "Where you are" part of `references/agent-brief.md` with
`RUN_TMP`, then `references/run-it-brief.md` with the list of runnable things
filled in. Its report is `$SCRATCH/wave1-runit.txt`, with a "promises versus
behaviour" table. Each mismatch is a measured finding (`runit-<n>`), and it
still goes through refutation, since a stub can mislead.

## 5. Refute, then verify

This step changes the output more than wave 2 does, so do not economise on it.

Everything goes through this step, whichever engine produced it, except the
check findings from step 4a. A Codex finding
is no less likely than a Claude one to be a mechanism reasoned out of source
without ever being measured, and the engine someone picked should not decide
whether a claim is checked before it lands on a colleague's MR.

Take the findings you would actually post, hand them to **a fresh agent whose
job is to break them**, and give it the two things the review agents lacked:
permission to drive a browser (the browser skill chosen below) and the checkout
the rules name for product rules, or the counterpart's own head when the half
that owns those rules is the counterpart: its reviews worktree in full scope,
the files API in contract scope.
For each claim it states what would have to be true for the claim to be wrong,
then goes and checks that. A claim it cannot break comes back with the evidence
that survived. Refuters run on the refuter model and effort from step 4.

Refuters get three more things:

- **A sample of what was cleared.** Up to 3 entries from each slice report's
  "checked and found sound" list, picked by you, claims that something is
  refused, blocked or safe first. In benchmark run F two agents listed a real
  bug there, and refuters that only get findings never see it. A sound claim
  the refuter breaks becomes a finding and goes through grading.
- **Derived claims to run.** A finding marked "settle by running X" is run by
  the refuter in the same kind of throwaway sandbox as the run-it agent
  (`references/run-it-brief.md`: `env -i`, a temp `HOME` under `RUN_TMP`,
  stubs first on `PATH`, fake credentials).
- **The `RUN_TMP` path**, with the same temp-folder and `Leftovers:` rules as
  every other agent.

Check findings from step 4a skip this step: a tool measured them.

**Choosing the browser skill.** Use the skill the rules name. Without one,
look in your list of available skills for one named `browser`, either bare or
namespaced by the plugin that ships it as `<plugin>:browser`: this
marketplace's `extras` plugin lists it as `extras:browser`, and other plugins
ship their own, such as `global-resources:browser`. Compare only the part after
the last colon, and compare it exactly: `chrome-browser` or `built-in-browser`
is not a match. A name in the rules is matched the same way, so `browser` there
also finds `extras:browser`. When several match, use the first one listed and
name it in the refuter brief. The browser is optional: when none is available,
show this notice, framed, and tell the refuter to work from code alone and to
mark every claim only a browser could settle as derived.

```text
────────────────────────────────────────────────────────────────────
 In-browser checks are off for this review
 No browser skill found (looked for: <rules' skill or none>,
 browser, <plugin>:browser).
 To enable them, install a browser skill (this marketplace's
 `extras` plugin has one) or name one under "Browser skill:" in
 <rules path or expected rules path>. Refuters continue with
 code-only checks.
────────────────────────────────────────────────────────────────────
```

This is not ceremony. On the MR this was built against, three of the four
strongest findings were refuted: a stacking-context claim reasoned correctly
from the CSS spec that no browser engine actually implements that way, a WCAG
failure that the criterion's own spacing exception excuses, and a "the help
copy points at the wrong screen" that dissolved once somebody opened the
backend and found two similarly named settings. All three were derived from
source and spec, and all three read as certain. Posting them would have sent a
colleague to revert a fix that works and to "correct" copy that was right.

Then do your own pass on what's left. The agents contradict each other, and
when they do, work out which mechanism is real rather than posting both. Check
every survivor against the code at head yourself, including whether the MR
introduced it - `git diff <base_sha>..<head_sha>` on the file settles that, and
a finding mislabelled as introduced costs more credit than it wins.

Finally, drop anything that repeats an open thread from step 3, ours or theirs.
On a live MR this removed two of the strongest i18n findings, both already
raised by another reviewer.

## 6. Draft the comments

Post everything that genuinely lands as **critical, blocker, high or medium**.
**Low** findings post too, never one by one: all of them go into one shared
thread (below), which step 7 offers as a single entry. The user is not asked
about each low - they take the thread or drop it. Noise never posts - nit-picks, style preferences and
"consider maybe" observations go in your reply, not on the MR.

**The lows go out together as one resolvable thread**, never one
thread each. A string of small threads reads as a pile-on and costs the author a
resolve click apiece; one thread says "small things, take them or leave them"
and closes in one go. Open it with `🔵 **Low** - <n> small points, in one
thread`, then one bullet per low: a bold one-line title, the `file:line`, one or
two sentences and the ask. Anchor it on the line of the most relevant low when
that line is in the diff, otherwise draft it as a general thread.

The filter is severity, not count: if five things are really high, post five. A
review that flags everything buries the real problem, but one that downgrades a
genuine finding to keep the list short is worse. Grade by the consequence in the
product, and grade after refutation rather than before - a finding often moves a
step once somebody has measured it. The rules' product-consequence examples
show what that means for this product.

**Flag every finding a refuter lowered from high.** Both refuters in the
benchmark's refuter test lowered a real high to medium. Re-check each flagged
finding yourself against the code at head before you set its final grade, and
list the flagged ones in the step 7 summary with the grade the refuter gave and
the one you set.

Keep every comment to roughly **two short paragraphs, ~600 characters**. A
reviewer scans comments between other work; an essay gets skipped, so the long
version helps nobody. Your supporting evidence stays available for when they
push back - it doesn't need to ship up front.

```
🔴 **Critical** / 🔴 **Blocker** / 🟠 **High** / 🟡 **Medium** / 🔵 **Low** - <one line: what breaks>

<2-4 sentences: the mechanism, with ONE file:line as proof. Name the consequence
in the product - money mis-booked, request crashes, alerts flood - not the shape
of the code.>

<The ask, phrased as a question. Hand the decision back.>
```

What to leave out: numbered repro walkthroughs, bulleted evidence dumps, full
patch blocks, and inventories of everything you checked. One inline snippet is
fine when the fix isn't obvious from words.

**A `suggestion` fence is the exception to "no patch blocks"**, when the fix
fits the commented lines and you would bet a second reviewer writes essentially
the same change. The platform renders it as a diff with an apply button, so the
author takes it in one click. It closes the comment, after the
question, and does not count toward the ~600 characters. A fence replaces whole
lines: anchor the thread on the span (`--line` / `--end-line`) and write the
fence the way the platform file says (GitLab counts offsets from the anchor
line and caps them; GitHub replaces the anchored span as is). A span longer
than the platform takes gets prose instead. Where the
fix is one option among several, say so in words and leave the fence out - an
apply button reads as settled.

**Anchor the whole span.** A finding about lines 40-47 anchors on 40-47, so the
thread highlights every line involved; the script clamps a span that runs past
the diff and says so. It refuses a clamped span whose body holds a suggestion
fence, since the fence was written for lines the anchor no longer covers:
rewrite the fence for the clamped span, or drop it. It also refuses a span that
crosses from one hunk into another; anchor on one hunk or split the finding. A
file whose diff the platform withheld (too large) takes no inline anchor at
all; findings on it go through `--outside`. **A finding on lines no hunk touched** - a caller the
change breaks, a test that should have moved with it - still goes in the same
review, through `draft --outside path:40-47`, which opens it with the location
and turns any suggestion fence into a plain code sample (the platform file says
where it lands).

Keep the coloured-dot severity prefix - it makes a thread's weight readable at a
glance in the discussion list. "Critical" as a severity label is fine and clearer
than a euphemism; a style guide's ban on it applies to inflated prose ("a
critical improvement to the flow"), not to grading a finding. No em-dashes
(spaced hyphen instead), no Oxford comma. Say plainly when something is
**pre-existing rather than introduced by this MR**, and when you're unsure (say,
a behaviour that depends on a prod setting you can't see) - a reviewer who spots
you overclaiming stops trusting the rest.

## 6a. Finish mode

A re-review that turns up only a little is better closed than dragged through
another round. Finish mode is on when either:

- the user passed `--finish`, or
- without `--no-finish`, both rounds are light: our previous round (step 3) had
  no critical, blocker or high and at most two mediums, **and** this round,
  counting our findings that still stand, has the same - no high or worse, at
  most two mediums, any number of lows.

A first review never qualifies on its own, since there is no previous round.

In finish mode nothing is posted inline and nothing is reopened. Every finding
of this round, lows included, and every one of ours that still stands goes
into **one general comment**, `$SCRATCH/finish.md`, followed by `approve`. When
the run also drafted thread replies (`✅ Verified`), `finish.md` is the summary
note of that review's `submit --state reviewed`; with no drafts at all it goes
out through `note`:

```
✅ Approving - the points below are non-blocking, take them or leave them.

- 🟡 **Medium** - `path/file.ts:54` <what breaks, one or two sentences>
- 🔵 **Low** - `path/file.ts:63` <one sentence>
```

Each entry keeps the severity dot and one `file:line` at head; the step 6
length budget applies per entry, not to the whole comment. Our open threads
whose fix landed still get `✅ Verified` and resolved as usual; a still-standing
one is left as it is and listed in the comment rather than reopened.

## 7. Get acceptance, then write

Show the drafts **and** the thread actions from step 3 - reopen, resolve,
verified - as one list, then use **AskUserQuestion** to confirm scope and tone
in one call.

**Print and ask, in the same turn.** The user wants to read what goes out and
answer a dialog, and either half alone has failed: a question with no visible
drafts asks them to accept blind, and drafts closed by a plain "approve?" line
leave them typing an answer the skill then has to parse. So print every draft
comment in full as reply text (a markdown quote each), then call
AskUserQuestion in that same turn. The dialog can cover what sits above it, so
the recommended option's `preview` carries the drafts too; when they do not
fit, it carries the one-line list and the question text gives the summary
file's full absolute path to open in a markdown viewer (the rules or the
user's own instructions may name one).

Ask at most two questions in that one call: what to post (all as drafted,
recommended; or drop entries by id) and the verdict. An answer that does not
name a verdict is asked again - never filled in from your own recommendation.

Reopening a thread the author closed is the one that needs an
explicit yes; so does anything pre-existing or arguably out of scope. Posting
those on a colleague's MR is the user's call, not yours.

Give every finding a stable id as you draft it - `C1`, `H1`, `M1`, `L1` by
severity, the id its draft file already carries as `$SCRATCH/c1.md` - and use
that id everywhere the finding appears in the run. When findings go to the
counterpart too, prefix every id with its repo label from the rules (`FE-H1`
and `BE-M2`), and group
the summary block under one heading per MR with its link. A thread action is keyed by
its thread id the same way.

The acceptance step then has two halves, and neither replaces the other. Above
the question, a summary block: **every finding and every thread action written
out in plain language under its id**, or the user is accepting findings they
cannot see. The question itself stays **one line per entry, each line opening
with its id**, so it is scannable and the answer is a handful of ids rather
than a restatement. Someone who already knows what `H1` is picks it off the
short list; someone who does not scrolls up to `H1` and reads the three
sentences there.

Writing the summaries:

- **One to three sentences of ordinary English under each entry.** What is
  wrong, and what happens if it ships. Someone who has not read the diff and
  does not work in this file should reach the end of the entry knowing what
  they just agreed to.
- **Length follows the finding, never the layout.** A subtle finding earns its
  third sentence. Compressing every entry to six words so the list looks tidy
  is the failure this rule exists to prevent.
- **No jargon, and every acronym spelled out where it first appears** -
  _cross-site scripting (XSS)_, _one database query per row (N+1)_,
  _server-side rendering (SSR)_ - and dropped altogether where the short form
  earns nothing. The lenses reason in shorthand; a label the reader has to go
  and look up is worth the same as no summary at all.
- **Describe the problem, not the review.** "Whatever someone types into the
  note is put into the page as markup, so they can run code in another user's
  browser" - not "the Correctness lens flagged a `v-html` binding".
- **Every severity, same rule.** Medium and low entries are exactly where the
  reader has least idea what they are approving, so they get the same plain
  English as a critical one.

Write each summary from the mechanism and its consequence in the product,
rephrased for a reader outside the code - not pasted out of the draft comment,
which is written for a colleague with the diff already open.

Below the entries, before the question, add a **Lowered by refutation** line
when step 6 flagged any: each id with the refuter's grade and your final grade
(`M3: high, lowered to medium by the refuter, medium after re-check`). Leave it out when
none was flagged.

```markdown
**4 findings and 1 thread action on !512**

🔴 **Critical - C1. Unsanitised client note rendered through `v-html`**
`app/components/invoice/LineNote.vue:40-47`

Whatever a user types into a client note is put into the page as markup
instead of as text. A note carrying a script therefore runs in the browser of
everyone who opens that invoice afterwards, admins included, and acts with
their permissions. This is the attack known as stored cross-site scripting
(XSS).

🟠 **High - H1. Invoice lookup rescans every invoice for every line**
`app/composables/useInvoiceLines.ts:88-101`

For each invoice line the code searches the whole invoice list from the
beginning, and it redoes all of that work every time a line is edited. At
sizes large customers already reach - hundreds of lines against hundreds of open
invoices - that is hundreds of thousands of comparisons per keystroke, which
is where the multi-second freeze on the invoice tab comes from.

🟡 **Medium - M1. Hand-rolled rounding duplicates `roundCurrency`**
`app/composables/useInvoiceLines.ts:54-58`

This writes its own money-rounding code beside the shared one the export
already uses. Both round the same way today, but nothing keeps them in step,
and the day they drift apart a customer sees two different totals for one
invoice.

🔵 **Low - L1. Comment restates the line below it**
`app/composables/useInvoiceLines.ts:63`

A comment reading "loop over the lines" sits above a loop over the lines. It
tells the next reader nothing the code does not, and it is one more line that
has to be kept true as the code changes.

**Reopen T2** - our thread on `useInvoiceLines.ts`, resolved by the author

We said the discount was applied after tax rather than before it. The author
replied "fixed" and closed the thread, but at head the order is unchanged and
discounted invoices still come out wrong. Reopening contradicts them on their
own closed thread, which is why it needs your yes.

**Which should I post?**

- **C1** - client note rendered as markup, so a script in it runs for the next
  person who opens the invoice
- **H1** - invoice lookup rescans every invoice for every line, freezing the
  invoice tab
- **M1** - hand-rolled rounding beside the shared `roundCurrency`
- **L** - the lows thread: L1, comment restates the line below it
- **T2** - reopen: the discount-before-tax fix did not land

Post all, some (by id), or none?
```

In finish mode the summary block is the same, but the question gets one more
entry, first: **F** - post the findings above as one non-blocking comment and
approve. Show `finish.md` in full above the question, since it is what goes
out. Picking F posts the comment and approves; picking ids instead falls back
to the normal inline flow with no approval.

Outside finish mode, a light round still earns the offer. When this round has
no critical, blocker or high and at most two mediums - a first review included -
the question gets one more entry, last: **A** - approve after posting. Without
it, a clean first review can only ever go out as a Comment, which leaves the
author waiting on an approval nobody meant to withhold.

Approve first, then post: `finish.md` says the MR is approved, so it goes out
only once the approval has landed. A refused approval then stops the run with
nothing posted.

```bash
L=$SCRATCH/drafts-<iid>.json
# GitHub with drafted replies: one review that approves and carries finish.md
python3 $SCRIPT --project <id> --iid <iid> submit --ledger $L \
  --state approved --sha <head_sha> --file $SCRATCH/finish.md
# otherwise: approve, then the review (with drafts) or a plain note (without)
python3 $SCRIPT --project <id> --iid <iid> approve --sha <head_sha>
python3 $SCRIPT --project <id> --iid <iid> submit --ledger $L \
  --state reviewed --file $SCRATCH/finish.md
python3 $SCRIPT --project <id> --iid <iid> note    --file $SCRATCH/finish.md
```

`approve` and `submit --state approved` send the `head_sha` you reviewed, so the
approval is refused if the author pushed since; re-check the new head before
approving it.

**Re-run `refs` immediately before posting.** A review takes long enough that
the author often pushes in the middle of it, and a rebase changes every sha on
the branch. On the MR this was built against, the head moved twice during the
run: anchors computed against the old head landed on the wrong lines, and one
finding had already been fixed. If `head_sha` moved, check the branch out again,
re-run `added-lines`, and re-check each finding and each of our threads against
the new head before anything is written.

### Writing it as one review

Everything accepted goes out as **one review**, the way the MR page's
**Submit review** does: each comment and each reply becomes a draft only we can
see, then one submit publishes them together with a verdict. The author gets one
notification and one review instead of a comment every few minutes. The
platform file says what a draft is on that platform and where its behaviour
differs.

1. **Check for drafts the user already holds.** `drafts` lists them. Submitting
   publishes _every_ pending draft the user's account holds on the MR,
   including ones they wrote by hand, so a non-empty list stops the run here: show it and let the
   user submit or discard them first. `submit` refuses too, as a backstop.
2. **Draft each accepted entry.** Every draft is recorded in
   `$SCRATCH/drafts-<iid>.json`, the ledger that lets a failed run delete its
   own drafts. One ledger per MR: a ledger shared between MRs would carry one
   MR's entries into the other's submit. A successful `submit` or
   `discard-drafts` empties it.

   ```bash
   L=$SCRATCH/drafts-<iid>.json
   python3 $SCRIPT --project <id> --iid <iid> draft --label H1 --ledger $L \
     --file $SCRATCH/h1.md --path app/foo.ts --line 40 --end-line 47
   python3 $SCRIPT --project <id> --iid <iid> draft --label M2 --ledger $L \
     --file $SCRATCH/m2.md --outside app/bar.ts:12-15
   python3 $SCRIPT --project <id> --iid <iid> draft --label L --ledger $L \
     --file $SCRATCH/lows.md --path app/foo.ts --line 63
   python3 $SCRIPT --project <id> --iid <iid> draft --label T1 --ledger $L \
     --file $SCRATCH/t1.md --reply <discussion> --resolve
   ```

   `--resolve` resolves the thread on submit and is refused on a thread we did
   not open. Where the platform will not take it on the draft, `draft` records
   it in the ledger instead and `submit` resolves the thread directly
   afterwards. `--reopen` on a reply reopens the thread when the review is
   submitted, and is refused on a thread we did not open too. On GitLab a reply
   that would reopen a resolved thread on submit is refused unless `--reopen`
   says that is the point. A draft that
   fails to create stops the run before submitting: the verdict below was
   chosen with that finding in it.

3. **Submit with the verdict.** Any critical, blocker or high in the review →
   `requested_changes`, also when the finding predates the MR; otherwise
   `reviewed` (the platform's **Comment**). On GitLab `requested_changes` holds
   the merge until we re-review; on GitHub it does only where branch protection
   requires approvals. On a GitHub PR the user opened themselves, GitHub refuses
   `requested_changes` and `approved`, and `submit` refuses them before
   publishing: submit as `reviewed` and keep the drafts. Only the user's
   explicit pick in step 7 overrides this. The summary note is
   optional - one line on what blocks, or nothing (the platform file says when
   it is required):

   ```bash
   python3 $SCRIPT --project <id> --iid <iid> submit --ledger $L \
     --state requested_changes --file $SCRATCH/summary.md
   ```

   `submit` reads the result back rather than trusting the platform's answer:
   how many drafts published and what reviewer state stuck. A state that did
   not stick is worth one line to the user, not a second submit.

   If the user picked **A**, approve once the submit has landed:
   `approve --sha <head_sha>` (the platform file may offer a one-call form).

4. **Reopens ride on the reply.** A reopen always comes with a reply saying
   why, so draft it as `--reply <discussion> --reopen`; the thread reopens
   when the review is submitted. `unresolve` reopens a thread right away and is
   only for a reopen with nothing to say, which this skill does not make.

**When something fails**, the drafts are the part that outlives the run. A
draft left pending is invisible to the author, but the user's next manual
**Submit review** publishes it, and the next run of this skill stops on it as
the user's own. So on any failure after the first draft - including stopping on
the user's say-so - run `threads` first, since a failed submit can arrive after
some drafts already became threads, then delete ours that are still pending:

```bash
python3 $SCRIPT --project <id> --iid <iid> discard-drafts --ledger $L
```

Report which entries landed as threads and which did not; never re-draft one
that `threads` shows as posted.

The script refuses to resolve or reopen a thread we didn't open, deletes and
reports a draft the platform returned unanchored, and fails loudly when a write
does not apply, because a silent downgrade otherwise looks like success. `post`,
`reply` and `resolve` still exist for a single out-of-band comment; a review
goes through drafts.

**The platform can throw 5xx errors mid-run** (GitLab often answers 502). The
write often lands anyway, so on any non-JSON response run `drafts` or `threads`
and check what's actually there before retrying. Blind retries double-post on a
colleague's MR.

To revise a posted comment, `edit` it rather than delete-and-repost - the thread
keeps its anchor and any replies:

```bash
python3 $SCRIPT --project <id> --iid <iid> edit --file $SCRATCH/c1-short.md \
  --discussion <id> --note <id>
```

**Two MRs, two reviews.** Findings for the counterpart go out as a second,
separate review on it: its own `drafts` check, its own ledger
(`$SCRATCH/drafts-<cp_iid>.json`), its own verdict from its own findings, and
its own `refs` re-check before posting. Finish mode (step 6a) is judged per MR.
A finding about the seam itself goes on the MR whose code has to change, and
where either side could, on the one this run was started for, naming the other
MR's line in the body.

Then run step 8. Finish by confirming what landed: one line per thread -
posted, reopened, resolved, verified - and name anything you deliberately left
unposted. The final line says which worktrees were removed and which stayed.

## 8. Clean up

Run this once the drafts are submitted, and also when the user stopped the
run or it failed after step 1.

**Sweep.** Touch only the run's own paths. Every command below uses the
literal paths from `run.json` (`run_tmp`) and the scratchpad, never a shell
variable set in an earlier call, which is empty by now. Each command starts
with a guard that refuses to run when its path is empty, so an empty value
can never widen what it matches or deletes:

1. Read the `Leftovers:` line of every report. Note each path it names.
2. Stop any process still running with the run temp dir in its command line,
   such as a browser an agent started. Never run `pgrep` or `pkill` with an
   empty pattern: it matches every process.

   ```bash
   RT='<run_tmp from run.json>'
   [ -n "$RT" ] && [ -d "$RT" ] || exit 1
   for pid in $(pgrep -f -- "$RT"); do
     [ "$pid" = "$$" ] || [ "$pid" = "$PPID" ] || kill "$pid"
   done
   ```

3. Compare the status snapshots from step 1, for the primary checkout and the
   review worktree, and list the untracked entries that are new. The list is
   NUL-separated, so a name with a colour code or a newline in it is safe:

   ```bash
   RT='<run_tmp from run.json>'
   [ -n "$RT" ] && [ -d "$RT" ] || exit 1
   git -C <repo> status --porcelain=v1 -z -uall > "$RT/status-primary.after"
   python3 - "$RT/status-primary.before" "$RT/status-primary.after" \
     > '<scratchpad>/new-primary.json' <<'EOF'
   import json, sys
   def untracked(path):
       raw = open(path, "rb").read().decode("utf-8", "surrogateescape")
       return {e[3:] for e in raw.split("\0") if e.startswith("?? ")}
   new = sorted(untracked(sys.argv[2]) - untracked(sys.argv[1]))
   print(json.dumps(new))
   EOF
   ```

   Do the same for the review worktree (`status-review.*`, `new-review.json`)
   when it stays. When either list is not empty, ask once with
   **AskUserQuestion** which entries to delete, every entry unticked by
   default (nothing is deleted unless the user picks it), shown with `repr()`
   so odd characters are visible, and primary-checkout entries labelled "may
   be yours", since the user may have made a file there during the review.
   Delete only the picked ones, by their index in the list, and report the
   rest:

   ```bash
   python3 - '<scratchpad>/new-primary.json' <repo> <picked indexes> <<'EOF'
   import json, os, shutil, sys
   entries, root = json.load(open(sys.argv[1])), sys.argv[2]
   for i in sys.argv[3:]:
       path = os.path.join(root, entries[int(i)])
       if os.path.isdir(path) and not os.path.islink(path):
           shutil.rmtree(path)
       else:
           os.remove(path)
       print("deleted", repr(entries[int(i)]))
   EOF
   ```

   Never delete anything else outside `RUN_TMP` and the review worktree.
4. Remove the throwaway base worktree of step 4a if it is still listed
   (`git -C <repo> worktree list`). Take its path only from `base_worktree` in
   `checks.json`, never by eye from the list, and only when its real path is
   under `<run_tmp>/checks/`: `git -C <repo> worktree remove --force <path>`,
   then `git -C <repo> worktree prune`.
5. Delete `RUN_TMP` after checking that its real path is inside `$SCRATCH`:

   ```bash
   RT='<run_tmp from run.json>'; SP='<scratchpad>'
   [ -n "$RT" ] && [ -n "$SP" ] && [ -d "$RT" ] || exit 1
   real=$(realpath -- "$RT"); scratch=$(realpath -- "$SP")
   if [[ "$real" == "$scratch"/review.* ]]; then rm -r -- "$real"
   else echo "not deleting $real: it is not inside $scratch"; fi
   ```

   It parses under both bash and zsh, the Bash tool's shell on some hosts.

   A leftover path an agent named outside `RUN_TMP` is reported to the user,
   not deleted.
6. Remove each review worktree in `worktrees_created` (the counterpart's
   included) through its own path, `git -C <path> worktree remove <path>`, so
   the counterpart's worktree is removed from its own repo, unless the user
   passed `--keep-worktrees`. Never remove a worktree that existed before the
   run. When `remove` refuses because the worktree has changes, leave it and
   say so.

The final line names what was removed and what stayed: "Removed
`<base>/reviews` and the run temp dir; kept `<cp base>/reviews` (existed
before the run)."

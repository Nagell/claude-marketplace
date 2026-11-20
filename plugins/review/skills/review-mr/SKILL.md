---
name: review-mr
description: Review a GitLab merge request or a GitHub pull request in an isolated worktree and post the findings in the user's name as one review (drafts, then one submit with a verdict), with range anchors, suggestion fences and every low in one thread. Asks upfront whether to review with Claude, Codex, or both, and at what effort, checks the branch out at head_sha against the MR's own target branch, loads the repo's review rules from ~/.claude/review-rules/, finds the MR for the same change in the paired repo when the rules name one and reviews the boundary between the two, or both in full, reads the existing threads first so a re-review validates our earlier findings instead of repeating them, runs the review in two waves so the second one hunts the ground the first left unopened, then sends a refutation agent with a browser and the code that owns the product rules to break the survivors before anything is drafted, then shows the draft comments and the proposed thread actions, each summarised in plain English, for acceptance before anything reaches the MR. On a re-review where only a couple of mediums and some lows remain, it offers to close the MR instead: every remaining finding in one non-blocking comment plus an approval. Invoke only via /review-mr.
argument-hint: "<mr-or-pr-url | !iid> [<second url>] [--both] [--finish | --no-finish]"
disable-model-invocation: true
effort: high
dependencies:
  - browser
  - writing-style-guide
  - humanizer
---

# Review an MR and post the comments

For reviewing someone else's merge request or pull request and leaving inline
feedback on it. "MR" below means either. Use the user's writing-style skill for
the comment prose when one is installed: **writing-style-guide** (which pulls
in **humanizer**) ships in this marketplace's `base-setup` plugin. Both are
optional; without them, follow the comment rules in step 6 alone. They matter
when present: the findings are only useful if a colleague can act on them, and
unreadable walls of text get skipped.

Input is an MR URL or `!iid`, optionally followed by `--finish` (force finish
mode, step 6a) or `--no-finish` (never offer it). A second MR URL from the
paired repo, or `--both`, asks for a full review of both halves of the change
(step 1a). Nothing is posted, resolved,
reopened or approved until the user accepts.

Two things shape the whole run. A single review pass misses things that a second
pass finds, so step 4 runs two waves and the second one is aimed at what the
first left unopened. And an MR that already carries our comments is a
re-review, not a first look, so step 3 happens before any reviewing at all.

## How this skill is built

- **Core** - this file: the review procedure, from engine and effort through
  worktree, sizing, waves, refutation, grading and acceptance to posting.
- **Agent brief** - `references/agent-brief.md`: what every review agent is
  told, including the coverage ledger it reports.
- **Platforms** - `platforms/gitlab.md` and `platforms/github.md`: how each
  platform fetches an MR, anchors comments, holds drafts, submits a verdict,
  and resolves or reopens threads.
- **Scripts** - `scripts/gitlab_comments.py` and `scripts/github_comments.py`,
  the platform clients with the same subcommands, and `scripts/find_rules.py`,
  the rules lookup.
- **Project rules** - `~/.claude/review-rules/<repo>.md`: everything specific
  to one repo or product (step 0a).
- **Browser** - the browser skill the rules name, or a known one, for the
  refuters' in-browser checks. Optional (step 5).

`$SKILL_DIR` below is the directory this SKILL.md was loaded from,
`$SCRIPT` is `$SKILL_DIR/scripts/gitlab_comments.py` or
`$SKILL_DIR/scripts/github_comments.py` for the MR's platform (step 0a), and
`$SCRATCH` is this session's scratchpad directory. Both scripts take
`--project` (GitLab: numeric id or URL-encoded path; GitHub: `owner/repo`) and
`--iid` (the MR iid or PR number), and offer the same subcommands, so every
command below reads the same on both platforms.

## 0. Choose the review engine, the counterpart scope and the effort

These questions are the run's **first tool call** - before reading the rules,
running `refs`, fetching, or anything else. They need nothing from the MR, and
the user should not wait through setup to answer them. Use **AskUserQuestion**
once, with three questions.

The engine:

- `Claude (Recommended)` - the multi-lens agent pass in step 4.
- `Codex` - the same lenses and waves, run as Codex tasks instead.
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

The effort, which sets the base for every agent the run spawns:

- `Medium (Recommended)` - the default.
- `Low` - cheaper, for a small or familiar MR.
- `High` - for a risky change or one past a reliable size.

File-slice owners and refuters run one level above the base: `low` → `medium`,
`medium` → `high`, `high` → `xhigh`. Slice owners are the role the run data
supports, and refutation is the step that changes the output most. Every other
agent runs at the base.

Carry the answers through as `<engine>`, `<scope>` and `<effort>`. `<engine>`
changes only which pass(es) run in step 4 and the merge behaviour in step 5 when
it is `Both`; `<scope>` only matters once step 1a finds a counterpart;
`<effort>` sets every Agent call in steps 3-5 and the `--effort` of every Codex
task, by the same table.

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
directory or asking - an existing `reviews` worktree is reused as is, since
step 2 checks out the MR head in it anyway. Create it only if that list lacks it:

```bash
git -C <repo> fetch origin <default branch>
git -C <repo> worktree add <base>/reviews origin/<default branch>
```

If the rules carry machine notes for git (a sandbox that blocks one of these,
say), run each command the way they say. Never work in the primary checkout - it
usually holds uncommitted work on an unrelated branch, and a review must not
disturb it.

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
| 4    | one extra **Contract** lens in wave 1                                 | every lens and wave 2 cover both MRs                    |
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
python3 $SCRIPT --project <id> --iid <iid> --repo-dir <repo> refs
```

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

### 2a. Size the review

Measure the diff before planning any agents, because the size decides how many
agents step 4 spawns. Count changed lines (added plus
removed) from the reviews worktree, leaving out lockfiles, locale files and
generated files, which nobody reviews line by line. Add the rules' size
excludes to the pathspecs:

```bash
git -C <worktree> diff --numstat <base_sha> <head_sha> -- . \
  ':(exclude)*.lock' ':(exclude)*-lock.*' ':(exclude)pnpm-lock.yaml' \
  <the rules' size excludes> \
  | awk '$1 != "-" { n += $1 + $2; f++ } END { print n+0, f+0 }'
```

| tier | reviewed lines | what changes in step 4                                  |
| ---- | -------------- | ------------------------------------------------------- |
| S    | under 300      | lenses only                                             |
| M    | 300-999        | lenses, plus file-slice owners in wave 1                |
| L    | 1000-2499      | as M                                                    |
| XL   | 2500 and over  | as L; say in step 7 that the MR is past a reliable size |

In the counterpart's full scope, size the two diffs together.

Start `$SCRATCH/run.json` now and keep it current for the whole run:
`{mr, round, head_sha, base_sha, reviewed_lines, files, tier, effort, agents: []}`, one
`agents` entry per spawn with `role`, `effort`, `files` and its report path. It
is how a later run can tell whether these settings found more, so it is not
optional.

Why this exists: across 182 earlier runs, a later round found 10% more on MRs
under 300 lines and 22% more at 1000-2499, and the share of agents that left
files unexamined went from 19% to 65%. Agents did about the same amount of work
whatever the size, so on a big MR each one simply read less. Effort was never
set, so nothing yet shows how much effort alone helps; the file-slice owners
are the part the data supports.

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
| the finding still stands, thread resolved                                   | unresolve, reply with what still stands          |
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

- **Codex** - the same two waves as below, lenses, slice owners, brief and gap
  hunt included, with each agent run as a Codex task instead of an Agent call.
  It needs the `openai-codex` Claude Code plugin; when its companion script is
  missing, say so and offer the Claude engine instead:

  ```bash
  CODEX=$(ls -d ~/.claude/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs \
    | sort -V | tail -1)
  node "$CODEX" task --background --fresh --effort <role effort> "<brief + lens>"
  ```

  What differs from the Claude agents:
  - A task runs read-only without network: no platform CLI, `curl` or file
    writes. Its report comes back as its reply; collect it with
    `node "$CODEX" result <job>` and save it to `$SCRATCH/wave<n>-<lens>.md`
    yourself. Tell it so in the brief, and that claims it cannot measure are
    derived.
  - The harness does not track the jobs. Watch them from the main session with a
    background loop over `node "$CODEX" status --json` that exits when none is
    running, and check its first poll returned a real count. Never from a
    subagent, which is not woken when its loop ends.
  - Not the native `review` / `adversarial-review`: they take no effort and no
    brief, so they cannot be pointed away from what is already found.

- **Both** - launch the Claude wave 1 and the Codex wave 1 at the same time, both
  in the background, so neither blocks the other; wave 2 then works the ground
  both left dark.
  Pool every finding from every pass before verification. Don't label findings by
  source, and don't let either engine win a disagreement by default - resolve it
  like any two agents disagreeing, against the code. When both flag the same
  issue, merge it into one comment.

### Agents and effort

Every Agent call in this skill passes `effort` explicitly, from `<effort>`
(step 0) and this table, and records it in `run.json`:

| role                                        | effort         |
| ------------------------------------------- | -------------- |
| thread validation (step 3)                  | base           |
| wave 1 lens agents                          | base           |
| wave 1 file-slice owners (M and up)         | one above base |
| wave 2 gap agents                           | base           |
| refuters (step 5)                           | one above base |
| end-to-end simulation (optional, L / XL)    | base           |

- **Lenses stay one agent each**, reading the whole MR, at every size.
- **File-slice owners (M and up).** Next to the lenses, spawn one agent per
  slice of about 300-400 reviewed lines, grouping the changed files by directory
  or feature. Each one reads its files whole, applies every lens to them, and
  follows each change into the unchanged code that calls it. Name them
  `slice-<n>`. This adds one agent per slice, not one per lens per slice: every
  agent costs about 110k tokens of context before it reads anything.
  On !121 the slice owners found what two rounds of lens agents had missed
  across the whole MR, in the logic of the multi-step flows.
- **End-to-end simulation (optional, L / XL).** Use it only when the MR changes
  a multi-step flow that can be driven against a stub: a script or skill that
  calls an API across rounds, a state machine. It is the most expensive agent
  in the logs and found one survivor on !121, independently of a slice owner.
- **Cap.** When the tier asks for more than about 12 agents in wave 1, say so
  before spawning, with the count, and let the user pick: all of them, or fewer
  and larger slices.

Finding ids carry their source agent's prefix (`correctness-3`, `slice-2-1`, `e2e-1`)
from the report through refutation into the draft files, so `run.json` can say
which role produced each survivor.

### Why two waves

One pass finds a subset, and which subset varies between runs. Running the same
pass twice mostly re-finds the same things, because the two runs read the same
diff the same way. So wave 2 is not a repeat: it is handed wave 1's findings and
wave 1's coverage ledgers, and sent at the ground nobody opened. That is the
same thing that makes a manual re-review productive - you already know what was
caught, so you look elsewhere.

### Wave 1: breadth

Pick the lenses from what the MR actually touches, not from a fixed list. Always
include the first three:

- **Correctness** - the mechanism that misbehaves, with its trigger.
- **Product behaviour** - what a user sees, and whether it matches what the MR
  description claims. Description-versus-code is a finding nobody gets from
  reading the diff.
- **Error paths and silent failures** - swallowed errors, fallbacks that hide a
  broken call, an empty state that means "failed" and reads as "none".
- **Tests** - only where the MR changes behaviour that could be covered.
- **Accessibility and design system** - on frontend MRs touching markup,
  design-system components or CSS.
- **i18n** - wherever locale files or user-visible strings change.
- **Types and API contracts** - where signatures, schemas or generated types move.
  When none moved, skip it and say why.
- **Comments** - only when the rules name a comments file and that file exists
  at the reviewed head: `git -C <worktree> cat-file -e <head_sha>:<path>`. When
  the rules name none, or the file is missing at head, skip the lens and say
  which of the two it was. Do not fall back to other repo conventions.
- **Extra lenses the rules list** under a name not above, whenever the MR
  touches their trigger paths. Where the rules describe a lens above (which
  design system, which locale paths), that wording goes into that lens's
  prompt; it neither widens the lens's trigger nor starts a second agent.
- **Contract** - whenever step 1a found a counterpart. It gets both diffs and
  reads where the two halves meet, shape and logic both:
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

  In full scope the other lenses cover both MRs, but this one still runs.

Give every agent the brief in `references/agent-brief.md` with the paths filled
in, the counterpart section included whenever step 1a found one, then its own
lens. The brief is what makes wave 2 possible: it obliges each
agent to open every changed file whole, follow one edge out of each, and report
a coverage ledger saying what it did not examine and why.

If the repo ships its own review material - the rules name where it lives -
hand the relevant file to the matching lens. It is how that repo wants its MRs
read, and it is more specific than anything an agent brings from general
knowledge.

Each agent writes its report to `$SCRATCH/wave1-<lens>.md` and replies with the
path. A long reply truncates in transit and the tail is lost silently.

### Wave 2: the gap hunt

Merge the wave 1 ledgers into one list and work out what is still dark:

- changed files nobody examined, or that only one lens touched
- changed exports whose consumers nobody traced
- the seams: where a changed file meets an unchanged one that assumes the old
  behaviour
- anything a lens declared out of scope

Spawn fresh agents for wave 2, one per area of dark ground, each with the brief,
the merged findings list from wave 1 ("already found, don't repeat these") and
its assigned ground.

Fresh rather than the wave 1 agents, which was tested head to head on one MR
with both variants working the same five areas. Reusing the wave 1 agents is
faster and they write better "I tried to break this and could not" sections,
but they carry their own conclusions with them: the reused agent that had
already cleared the department-switch path in wave 1 filed the same missing
option as a latent hazard and never tried the error path, while a fresh agent
on the same ground found it as a live defect. The fresh agents also caught that
their headline finding was pre-existing, which the reused ones asserted the
opposite of. That error is the expensive one, so fresh wins.

Reports go to `$SCRATCH/wave2-<area>.md`, same rule about replying with the path.

### When an agent goes quiet

A subagent's plain text isn't visible to you. If an idle notification arrives
with no report path, `SendMessage` them: their output isn't visible, reply to
`main` with the path. Don't wait silently or assume they found nothing.

## 5. Refute, then verify

This step changes the output more than wave 2 does, so do not economise on it.

Everything goes through this step, whichever engine produced it. A Codex finding
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
that survived.

**Choosing the browser skill.** Use the skill the rules name. Without one, use
the first known browser skill that is installed: `browser`, then
`start-chrome-debug` (with the chrome-devtools tools). The browser is optional:
when none is available, show this notice, framed, and tell the refuter to work
from code alone and to mark every claim only a browser could settle as derived.

```text
────────────────────────────────────────────────────────────────────
 In-browser checks are off for this review
 No browser skill found (looked for: <rules' skill or none>,
 browser, start-chrome-debug).
 To enable them, install a browser skill (the `browser` plugin in
 this marketplace) or name one under "Browser skill:" in
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
the diff and says so. **A finding on lines no hunk touched** - a caller the
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

```bash
# with drafted replies: the review carries finish.md as its summary
python3 $SCRIPT --project <id> --iid <iid> submit --ledger $SCRATCH/drafts.json \
  --state reviewed --file $SCRATCH/finish.md
# no drafts: a plain note
python3 $SCRIPT --project <id> --iid <iid> note    --file $SCRATCH/finish.md
python3 $SCRIPT --project <id> --iid <iid> approve --sha <head_sha>
```

`approve` sends the `head_sha` you reviewed, so the approval is refused if the
author pushed since; re-check the new head before approving it.

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
   `$SCRATCH/drafts.json`, the ledger that lets a failed run delete its own
   drafts:

   ```bash
   L=$SCRATCH/drafts.json
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
   afterwards. A reply that would reopen a resolved thread on submit is refused
   unless `--reopen` says that is the point. A draft that
   fails to create stops the run before submitting: the verdict below was
   chosen with that finding in it.

3. **Submit with the verdict.** Any critical, blocker or high in the review →
   `requested_changes`, which holds the merge until we re-review, also when the
   finding predates the MR; otherwise `reviewed` (the platform's **Comment**).
   Only the user's explicit pick in step 7 overrides this. The summary note is
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

4. **Reopens go separately**, before the submit: drafts cannot unresolve.

   ```bash
   python3 $SCRIPT --project <id> --iid <iid> unresolve --discussion <id>
   ```

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

Finish by confirming what landed: one line per thread - posted, reopened,
resolved, verified - and name anything you deliberately left unposted.

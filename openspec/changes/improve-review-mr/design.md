# Design

## Context

`review-mr` today: step 0 asks engine, counterpart scope and effort. Step 2a sizes the diff in changed lines (S under 300, M 300-999, L 1000-2499, XL above). Step 4 runs wave 1 (three always-on lens agents plus optional lenses, plus one file-slice owner per 300-400 changed lines from tier M), then wave 2 on the ground the ledgers left dark. Step 5 refutes the survivors. All agents inherit the session model; effort is "base" or "one above" per role.

Evidence, all from `~/.claude/model-bench/` (one run per arm, no repeats; treat differences as signals, not proof):

| Run | Setup | Key bugs caught (of 14) | Real cost | Requests over 100k |
|---|---|---|---|---|
| B | Opus 5.5 medium, 3 component slices + 1 cross-file | 6 strict, 7 with partials | $6.38 | not applicable |
| C | Haiku 5.5 max, same slices | 7 / 8.5 | $3.34 | 69% |
| D | Haiku 5.5 max, 7 small slices + narrow cross-file + "does NOT set" lens | 13 / 13.5 | $5.08 | 71% |
| E | Haiku 5.5 max, 3 component slices + lens, no cross-file | 9 / 9.5 | $4.25 | 87% |
| F | Opus 5.5 medium, same slices and prompts as E | 9 / 9.5 | $6.99 | not applicable |
| #238 | one Haiku max agent | found the push-gate bypass | about $0.50 | not measured |
| #238 | full review-mr, 11 Opus agents | missed it | $21.68 | not applicable |

The #238 single-agent runs (Haiku max, Opus medium, Sonnet high) all ran the hook with test input. Only the Haiku run reported the multi-line and heredoc bypass of the push gate.

Refuter test on run F's 35 findings (same brief, no answer key): Opus high kept 34, refuted 1, $2.76; Opus medium kept 33, refuted the same 1, left 1 unsettled, $1.74. Both kept every key bug and both lowered the sandbox-off finding (a key high) to medium. Neither saw the `--stop '*'` bug that two run-F agents had listed as sound, because refuters only get findings.

Cost per agent in run D: $0.30 to $1.12 for the slices and $0.82 for the cross-file agent. The price table, tier rule (Haiku 5.5 charges 5x per request whose prompt is over 100k tokens, cache reads included) and the transcript scanner come from `add-usage-skill`; its later `models` mode (`add-usage-models-mode`) reuses the same scanner. This design refers to them and defines no table of its own.

## Goals / Non-Goals

**Goals:**

- Find more high-severity bugs per dollar than the 11-agent Opus setup, with the run-D result (13 of 14) as the bar.
- Keep review quality on Opus-only judgment steps (refutation, thread validation).
- Make the run measurable (real cost per agent) and clean (no stray folders or worktrees).

**Non-Goals:**

- No change to posting: drafts, one review, verdict rules, finish mode, thread validation and platform files stay as they are.
- No new model-selection logic beyond one default and one flag. Choosing models per task type is the `usage` skill's models mode (`add-usage-models-mode`).
- No Codex-specific tuning. The Codex engine keeps its current behaviour.
- No new per-repo configuration file. Repo conventions are read from files the repo already has.

## Decisions

### 1. Wave-1 model: Haiku 5.5 at max, Opus for refutation and validation

Agents are spawned with `model: haiku` and `effort: max`; the resolved model id is read back from the transcript into `run.json`, so alias drift shows up. Roles on Haiku: slice owners, the contract agent, the run-it agent, wave-2 gap agents, the optional end-to-end simulation. Roles on Opus: refuters and thread validation, both at the base effort (`medium` by default). Refuters were one level above until the refuter test: high gave the same verdicts as medium for 59% more.

Why: run D beat run B by 7 key bugs at 80% of its cost, and the one Haiku agent on #238 found what 11 Opus agents did not. Refutation stays strong because it changes the output most: on the MR the current step 5 was built against, three of the four strongest findings fell to it. A finding that survives a weak refuter lands on a colleague's MR, while wave 1 is cheap to widen with more agents.

Engine question: **kept, not replaced, and its default stays `Claude (Recommended)`**. It chooses a vendor (Claude, Codex or both), which the model default does not touch. What changes is the label: "Claude" now means Haiku slice owners at max with Opus refuters. A per-run model question was rejected: the user decided the default, reviews rarely need speed, and a fourth question delays the first tool call. The model is carried by the role table and the `--fast` flag.

Effort question: kept, but it now sets the Opus roles only (thread validation and refuters at base, and wave 1 under `--fast`). Haiku agents always run at max, whatever was answered. Codex tasks take the effort answer as their `--effort`, follow the slice model (one Codex task per slice, reports named `wave<n>-<slice>.md`) and have no lens tasks.

Rejected: all Opus (run B: fewer catches at higher cost); Sonnet for wave 1 (not benchmarked on the hooks case; one Sonnet-high run on #238 did not report the bypass; revisit through the models mode, `add-usage-models-mode`); Haiku for refuters (refutation errors are the expensive kind).

### 2. `--fast`

`--fast` puts every wave-1 and wave-2 agent on Opus at the base effort (`medium` by default) instead of Haiku max. Slice sizes and the brief do not change. It is for the cases where the user waits on the review: measured from transcript timestamps, the slowest agent (the run's wall time) took 8.9 min in run B (Opus medium, 4 agents), 23.1 min in run C (Haiku max, 4 agents) and 23.7 min in run D (Haiku max, 8 agents), so Haiku runs are about 2.5x slower and smaller slices do not shorten them. The rerun records durations too. Refuters and validation are unaffected. With the Codex engine the flag has no effect and the skill says so in one line.

Run F measured Opus medium with the lens on 3 component slices: 9 of 14 key bugs (same count as Haiku run E, different misses), $6.99, slowest agent 9.2 min against 32.9 for E, $0.78 per caught bug against run D's $0.39. So `--fast` is faster, not better. Not measured yet: Opus on run D's 7 small slices; the rerun's `--fast` arm uses them.

### 3. Slicing: small contract-sized slices (decided by run E)

Option A wins: about 400 lines of whole files per slice, hard limit about 700, one tool contract or component per slice. Run E tested the other end (three component-sized Haiku max agents, no cross-file agent, same "does NOT set" lens as run D) and scored 9 / 9.5 of 14 at $4.25, with 87% of requests over 100k, a slowest agent of 32.9 min and a miss on S1. Run D scored 13 / 13.5 at $5.08, with 71% over 100k and a slowest agent of 23.7 min. Cost per caught key bug is $0.39 for D and $0.47 for E, and fewer, wider Haiku agents grow their own context further.

What the options share:

- Slices are sized by reading load, the line count of the whole changed files (lockfiles, generated files and the rules' size excludes left out), not by changed lines. A 5-line change in a 3,000-line file still needs the whole file read (brief step 1). `reviewed_lines` stays in `run.json` for comparison with earlier runs.
- Files group by tool contract or component: a script with its tests and the doc section that describes it, a hook with its `hooks.json` entry, a component with its composable and spec.
- Reading load is measured on the head tree: list the changed files with `git diff --name-only <base_sha> <head_sha> -- <size-exclude pathspecs>`, then count each with `git show <head_sha>:<path> | wc -l` (a deleted file counts 0).
- The tier table (S/M/L/XL by diff lines) is removed, with every place that reads the tier: the `tier` field in `run.json`, the XL note "past a reliable size" and the effort option text that names it.
- The optional end-to-end simulation no longer depends on a tier. It runs when the MR changes a multi-step flow that can be driven against a stub, whatever the size.
- Whole-MR lens agents (Correctness, Product behaviour, Error paths and the optional ones) are dropped at every size: a slice owner applies every lens, and a small MR is one slice with one owner. This follows #238 (one agent beat eleven) and keeps one code path in the skill. Alternative: keep three lens agents on a one-slice MR; rejected for the same cost reason (Open questions).
- Extra lenses and details from the rules go into the brief of each slice whose files match their trigger paths, with no extra agent.
- Batching replaces the old 12-agent question: at most `--max-parallel N` wave-1 and wave-2 agents run at once (default 12), and the next queued slice starts as one finishes. Slice size does not grow with the MR; a big MR takes longer instead. 12 is this skill's own limit, not a known Claude Code limit.

The two options:

| | A: many small slices | B: few component-sized slices |
|---|---|---|
| Size | about 400 lines of whole files per slice, hard limit about 700; a file above the limit is its own slice and splits into ranges of about 700 lines above about 1,500 | one slice per component or tool contract, whatever its size (runs B and C: hooks, browser scripts, browser docs; 3 slices for 2,905 lines, about 1,000 lines each) |
| Evidence | Run D: 7 small slices + cross-file, 13 / 13.5 of 14, $5.08, 71% of requests over 100k. One slice (hooks) found all five hook bugs alone; run C's coarse hooks slice found 3 and missed H1 | Run C: 7 / 8.5, $3.34, 69% over 100k, but without the lens. Run E: same slices with the lens, 9 / 9.5, $4.25, 87% over 100k, missed S1 |
| Cost shape | More agents, each with its own base context. Run D agent cost $0.30 to $1.12 | Fewer agents, longer contexts: the longest run C agent made 83 requests, with 53 over 100k |
| Result | A: chosen | B: rejected by run E |
| Risk | Cost grows with slice count, and a big MR needs more batches under `--max-parallel` | A big slice means more files per agent: run C's docs slice spent the most requests (83) for no clean key catch, and in runs B and C nobody owned the launch options (S6, S7) |

Run E decided it, by the user's rule "if E is better go with it, otherwise D". The rerun of this change's own benchmark (task group 11) uses option A, so it is also a second data point.

### 4. The cross-file agent is dropped by default

Evidence on the cross-file agent (narrow scope in run D, broader in B and C):

- Run B: most expensive agent ($2.21), no unique key bug, contradicted the slices on `--stop '*'`.
- Run C: the only agent that caught H1; the hooks slice was coarse, so the seam was real.
- Run D: $0.82 (16% of the run), no unique key bug, three duplicates (S2, S4, S5); its one unique extra was a medium non-key finding (DX4, a doc tells Claude to re-register a server and drops `--secrets`).
- Run E: no cross-file agent by design.

Decision: the skill spawns no cross-file agent by default. It added no unique key bug in runs B, D or E, and the one catch in run C came from a coarse slice that option A no longer produces. The only exception is the contract owner: when a counterpart MR exists, one agent checks the Contract lens against the other repo. With full counterpart scope, the counterpart's changed files are cut into slices of their own by the same rule, and the contract agent still runs once.

Seams between slices: the owner of a slice that changes an export greps every consumer of it, not only one. Today's brief asks for one traced consumer per export; the new brief widens that.

Drop test for the remaining agents: `run.json` records which agent produced each surviving finding (ids already carry the prefix). If an agent adds no survivor that only it found in the benchmark rerun and the next five real reviews, it becomes opt-in.

### 5. The "does NOT set" lens becomes standing brief text

`references/agent-brief.md` gets the run-D addendum as a standing section, applied to every file in the slice:

- For every external tool the code runs or configures, list the options it passes, then ask which important ones it does not pass and what the tool's default is: security (sandboxing, permissions), output locations (logs, caches, snapshots written into the caller's repo), network and proxy, auto-install and download, behaviour on error, what is persisted where.
- Verify a claim about what a tool can or cannot do against the tool's own source or docs (its `--help`, local `node_modules`, web docs), never against this repo's docs. Never install the tool to check.
- Look for swallowed errors (`|| true`, `2>/dev/null`, empty fallbacks) that turn a failure into "nothing there", and for checks that wrongly block legitimate input, not only for what slips through.
- Report an unsafe or surprising inherited default as a finding with the default cited.

Run D evidence: this lens found the Chromium sandbox off (S6) and the `.playwright-cli` output dir (S7), which B and C missed, and sent s7 to the CLI source where it found the secrets-file route (S1). It is general on purpose: the addendum named Playwright, git and npm; the brief names classes of settings and gives those as examples.

### 6. Context and cost measures in the brief

Cost is requests times context, and each Haiku request over 100k pays 5x on every token class. Every Haiku agent in run C and D crossed the line. Slice size alone did not prevent it (max prompt 161k to 309k in D), so the brief adds tool-output rules:

- Counts before content: `wc -l`, `grep -c`, `ls | wc -l` first; open a file whole only when the slice's own files need it (the brief already requires that for changed files), and read anything else by `grep -n` and `sed -n 'a,bp'`.
- Every command pipes through `head` or `tail` (about 40 lines). Never `cat` a file over about 200 lines that is not in the slice.
- A command whose output may be long writes to a file in the agent's temp folder; the agent then `grep`s or `head`s that file. Test and stub runs follow this: `cmd > out.txt 2>&1; tail -20 out.txt`.
- Several independent commands go in one Bash call. Fewer round trips means fewer requests, each paying for the full context.
- Never re-read a file already read; note line numbers in the report as you go.
- Append each finding to the report file when found, not at the end, so an early stop loses nothing.
- Soft budget: after about 40 tool calls, or about 150 KB of tool output read, stop opening new ground, finish the ledger with every unopened file marked `not examined`, put an `Unfinished:` line at the top of the report and reply with the path.

The main session treats `Unfinished:` like any dark ground: wave 2 starts a fresh agent on exactly those files. That is the "split a slice that nears the limit" mechanism, and it reuses wave 2. The numbers (40, 150 KB) are first guesses: an agent cannot read its own token count, and in run D slice s1 crossed 100k at about its sixth request, so the base prompt may be large. The rerun records the first-request prompt size and the request index at which each agent crosses 100k; the budget is recalibrated from that. Target for the rerun: under 50% of requests over 100k, down from 71%.

Rejected: forbidding stub runs in slices (they measure real behaviour; they move to the run-it agent instead, see 8); a hard token cap (cannot be enforced from outside a running agent).

### 7. Deterministic checks (no LLM)

New `scripts/run_checks.py` with two subcommands, `detect` and `run`, stdlib only. `detect` reads the changed files and finds commands from manifests and config at the nearest project root for each changed file:

- Node: `package.json` scripts named `lint`, `typecheck`, `type-check`, `check`, `format:check`, `test` (plus `test:unit`), run with the package manager picked by lockfile (`pnpm-lock.yaml`, `yarn.lock`, `bun.lock`/`bun.lockb`, `package-lock.json`); with no lockfile, pnpm. Direct tools when configured: `eslint <files>`, `prettier --check <files>`.
- Python: `ruff check <files>`, `ruff format --check <files>`, `mypy <files>`, `pytest` when `pyproject.toml`, `ruff.toml`, `mypy.ini` or `pytest.ini` configure them.
- Go: `go vet` and `go test` on the changed packages. Rust: `cargo check` and `cargo test`. Shell: `shellcheck <files>` when installed.

`detect` reads manifests and config as they are at `base_sha`, so an MR cannot change which commands run; a manifest that is new in the MR is listed but not trusted. `run` executes each command in the review worktree with a time limit (120 s per command, 300 s total; a timeout is reported as "not run", never as a failure), with no auto-fix flags and no installs: when dependencies are missing the command is skipped with "dependencies not installed" unless the rules' machine notes say how to run it. Machine notes apply as for git and the platform CLI. Commands run in the background during wave 1, in the main session, so they cost no agent tokens.

A failure becomes a finding only if it is new at head. The failing command is re-run at `base_sha` in a throwaway worktree under the run's temp dir (removed afterwards), on the same files; failures whose normalised messages also appear at base are pre-existing and listed in the run log, not posted. Default severity: failing test or type error medium, lint or format low (the lows thread); the main session regrades by consequence. These findings are measured, so they skip refutation; a failing test is re-run once to rule out flakiness.

Why a script: detection and base comparison are mechanical, they must behave the same each run and they can be unit tested. Rejected: asking an agent to find and run the commands (tokens spent on what a manifest says, and the agent may run `--fix`); running whole-repo commands (noise from code the MR did not touch).

### 8. "Run it": a separate agent, only when worth it

Decision: one separate run-it agent, not a duty in every slice brief.

- Run D found the launcher bugs by reading the installed tool's source, with no browser run. The stub-heavy slices s2 and s4 had 82% and 80% of requests over 100k (read-heavy s7 had 77%, so running is one driver among several). Per-slice running multiplies sandbox setup (temp HOME, stub CLIs on PATH, fake credentials) and tool output across agents.
- On #238 all three single agents ran the hook with test input inline and that is where the measured findings came from, so running is valuable; one agent doing it once is cheaper than seven setting it up.

Trigger: the diff adds or changes runnable code beyond comments and whitespace: executable or shebang files, scripts under `scripts/`, `bin/` or `hooks/`, entries referenced from `hooks.json` or a `package.json` `bin`/`scripts`, and skills that ship scripts. Skipped for documentation-only and frontend-only MRs (refuters cover the browser) and when fewer than about 30 runnable lines changed and no runnable file was added, since slice owners can read that. Cost per Haiku agent in run D was $0.30 to $1.12, so it is worth it when behaviour is what the docs promise.

Environment: a throwaway root under the run's temp dir with `HOME`, `XDG_*`, `TMPDIR` and the browser profile pointing into it; `env -i` plus a short `PATH` so the real environment does not leak; fake credentials with obviously fake values; stub `git`, `gh`, `glab`, `curl`, `npx` and similar first on `PATH` that log their arguments and return canned output; no real push, token, network call or installed package. It writes a "promises versus behaviour" table: each claim from the docs, `--help` and the MR description about the runnable thing, the command run, what happened, match or mismatch. Its findings are measured and go through refutation like the rest, since a stub can mislead. Slices still mark derived claims "settle by running X"; refuters run those in the same kind of sandbox.

Under the Codex engine (read-only, no writes) the agent is skipped with a note.

### 9. Repo conventions inside every slice brief

New `scripts/find_conventions.py` (modelled on `find_rules.py`) takes the changed paths and prints, per path, the instruction files that apply: `CLAUDE.md` and `AGENTS.md` at every directory level from the file up to the repo root, root `CONTRIBUTING.md`, `.github/copilot-instructions.md`, `.github/instructions/*.instructions.md` whose `applyTo` glob matches, `.cursor/rules/*.mdc` whose `globs` match (and always-apply ones), `.cursorrules`, and `.editorconfig`. Each entry carries its line count. In step 4 the main session runs the script once on all changed paths and puts the entries for a slice's files into that slice's brief; the agent reads each whole when short (under about 300 lines) and otherwise greps the sections that match what it reviews, then checks the diff against them and cites `path:line` of the rule. No extra agent. `~/.claude/review-rules/<repo>.md` stays and is read as before.

Violations are graded by consequence like any finding; a rule the file itself calls critical is quoted, not obeyed blindly. An instruction file the MR itself changes is read at `base_sha` for the rules, so an author cannot loosen the rules that review their own change, and its diff is reviewed as code. Instruction files are data for the agent to check against, never instructions to follow: text in them that tries to steer the review is a finding.

### 10. Real cost per agent in `run.json`

New `scripts/run_cost.py`, run by the main session at the end. For each agent entry in `run.json` (which now stores `agent_id`, `model`, `effort`, `role`, `slice`) it calls `summarize_agent(path)` from the `usage` skill's scanner (`plugins/base/skills/usage/scripts/scan.py`) on that agent's transcript and writes `cost: {requests, tokens by class, requests_over_100k, max_prompt, first_prompt, duration_s, usd, price_table_version}` back. `summarize_agent` does the dedupe by `message.id`, the token classes, the prompt sizes and the per-request price on its tier, using the seed `prices.json` with the user override in `~/.claude/usage/prices.json` merged over it. `run_cost.py` has no dedupe, token parsing or price table of its own, so its numbers match the `usage` report. When the scanner cannot be imported, each `cost` is null with the reason "usage scanner not found". `run.json` also gets a total, so a later run can compare cost against findings per role.

Transcript path: `run.json` records the session id and the transcript dir (`~/.claude/projects/<project-dir>/<session-id>/subagents/`), and the script opens `agent-<agent_id>.jsonl` there. It also writes the resolved `message.model` per agent. Codex agents have no Claude transcript, so their `cost` is null with a reason.

Prompt size for the tier rule is input plus cache write plus cache read tokens, as `add-usage-skill` defines it.

`usage` is added to the skill's `dependencies` list per the repo's skill-dependency convention, once `add-usage-skill` is merged and the skill exists.

Alternative: run the `usage` scanner over the whole session. Rejected: it reports per skill run, and `run_cost.py` needs the agents listed in `run.json` at the moment the review ends, so it summarizes those transcripts one by one with the shared summary function.

### 11. Cleanup

- At the start the main session creates the run's temp dir, `RUN_TMP`, with `RUN_TMP=$(mktemp -d -p "$SCRATCH" review.XXXXXX)`, and records the `git status --porcelain=v1 -z` of the primary checkout and the review worktree.
- Every agent brief carries `RUN_TMP`. The agent makes its folder with `mktemp -d -p "$RUN_TMP" <agent>.XXXXXX`, sets `TMPDIR` and `HOME` for anything it runs to point inside it, uses absolute paths only (never a path typed from `ls` output, which can carry colour codes; use `command ls`), deletes the folder before replying and ends its report with `Leftovers: none` or each leftover path and why.
- At the end the main session: checks each report's `Leftovers` line; stops any process whose command line contains `RUN_TMP`; deletes `RUN_TMP` after confirming its real path is inside `$SCRATCH`; compares the two `git status` snapshots and lists untracked entries that are new (using the NUL-separated list, so odd names are safe), asks once with AskUserQuestion which to delete (all ticked by default, so a file the user made during the review can be kept), deletes only the ticked ones and reports the rest; removes the throwaway base worktree from the checks step.
- Review worktrees the run created (recorded in `run.json` as `worktrees_created`, the counterpart's included) are removed with `git worktree remove` once drafts are submitted or the user stopped, unless `--keep-worktrees` was passed. A worktree that already existed (an earlier reviews worktree) is never removed. The final line names what was removed and what stayed.

Why `RUN_TMP` under the scratchpad: run D's agents wrote to `/tmp` and the repo; one root the main session owns makes the sweep a single delete. `add-cleanup` switches agents to `mktemp -d -p <session scratchpad>`; this change uses the same form one level down, so a run dir left by a stopped run has the `mktemp` shape that `add-cleanup`'s own-session scan lists. Tools that write to `/tmp` on their own (Playwright artifact dirs) follow `TMPDIR`.

`add-cleanup` (separate change) adds a `/base:cleanup` skill that scans known locations for old worktrees, merged branches and stale scratchpads, as a safety net for agents that stop early. This change makes the review run clean up after itself, so the net has less to catch. The sweep here touches only the run's own paths and does not call that skill. The brief bullet added in `c507be4` is superseded by this wording; keep one copy. The same commit added a temp-folder line to the `plugins/base/CLAUDE.md` template. That line is owned by `add-cleanup`, and this change does not touch it.

### 12. Waves

Wave 2 stays, aimed at dark ground, with fresh agents. It now also takes every slice's `Unfinished:` list and runs only when the merged ledgers leave dark ground, so a one-slice MR with a complete ledger finishes in one wave. Thread validation, finish mode and posting are unchanged. Refutation gains two checks. Refuters also get up to 3 entries from each slice report's "checked and found sound" list, picked by the main session with claims that something is refused, blocked or safe first: in run F two agents listed a real bug there. Grading (prose in SKILL.md step 6, there is no grading table) flags every finding a refuter lowered from high, the main session re-checks it before the final grade, and the step 7 summary lists the flagged ones (both refuters in the test lowered a key high).

## Risks / Trade-offs

- One run per arm: the 13-of-14 result may be partly luck. The rerun repeats the Haiku arm twice and adds a `--fast` arm; the claim in the specs is the process, not a recall number.
- Haiku's lower recall on subtle logic is unmeasured: the hooks and browser case is shell and config heavy, which suits the "does NOT set" lens. A frontend or business-logic MR may need Opus. The `--fast` flag is not the answer to that; the models mode (`add-usage-models-mode`) is.
- Option A puts more agents on a small MR than one owner would need: bounded by one slice per contract; `--max-parallel` limits how many run at once, not how many exist. Option B risks long contexts that pay the 5x tier.
- Seams between slices have no owner now that the cross-file agent is dropped; the benchmark rerun checks whether anything is lost.
- Deterministic checks can be slow or need installed dependencies; time limits and "not run" results keep that from blocking a review. Checks run repo-defined commands, which execute the MR's own code (a test, a lint plugin). The commands come from base manifests, run in the review worktree and never with fix flags, but the code under test is the author's. `--no-checks` skips the step for an author the reviewer does not trust (added flag; see Open questions).
- Run-it executes MR code. The throwaway environment limits damage but is not a security boundary; the brief forbids real network, push and credentials, and the agent is read-only on the repo.
- The user's `rm` guard hook can block an agent's own cleanup (it did in run D). The agent then reports the leftover instead of working around the guard, and the main session removes it.
- Reading instruction files adds context to every slice; the 300-line rule and grep-first reading cap it.

## Open questions

Slicing and the cross-file agent are decided (run E, design 3 and 4). Everything below is an assumption made because the user could not be asked; each is cheap to reverse.

1. One-slice MRs get a single slice owner and no lens agents (design 3, settled part). Alternative: keep the three lens agents below the size where slicing starts. Chosen for simplicity and because of #238.
2. `--fast` uses base effort (`medium` by default) rather than a fixed `medium`; with a `High` answer it is Opus high. The user said "Opus (medium)".
3. Run-it threshold (about 30 runnable changed lines or a new runnable file) and the soft budget numbers (40 tool calls, 150 KB) are guesses to calibrate from the rerun.
4. `--no-checks` and `--keep-worktrees` are new flags. `--keep-worktrees` follows from "unless the user keeps them". `--no-checks` is an addition for untrusted authors; drop it if unwanted.
5. The exact import path of the `usage` scanner. `add-usage-skill` requires `summarize_agent` and the pricing functions to be importable; `run_cost.py` adds `../../usage/scripts` relative to its own file to the import path.
6. Wave 2 skipping on a one-slice MR with a complete ledger is new; the old text ran it regardless of tier.
7. Codex engine: Haiku and `--fast` do not apply, run-it is skipped, checks and conventions still run, Codex `--effort` takes the effort answer. Not benchmarked.
8. Decided by the user: new untracked entries in the primary checkout are listed and the user picks what to delete in one question; nothing there is deleted without that answer.
9. Overlap with `add-cleanup`: it is the general safety net (a skill the user runs); this change is the review run's own cleanup. Neither calls the other. Both use `mktemp -d -p` under the session scratchpad. The `plugins/base/CLAUDE.md` template line belongs to `add-cleanup`.
10. The `haiku` alias resolves to Haiku 5.5 today; if it moves, `run.json` shows it but the skill does not pin a version.
11. Refuters sample up to 3 "sound" entries per slice report. Chosen to cap refuter cost; raise it if the rerun shows sound-list misses.
12. `--max-parallel` defaults to 12, the old cap. Lower it on machines or plans that limit concurrent agents.

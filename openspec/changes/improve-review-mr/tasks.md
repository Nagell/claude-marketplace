# Tasks

Paths are under `plugins/base/skills/review-mr/` unless noted. Python tests run with `python3 -m pytest plugins/base/skills/review-mr/tests`. The slicing rule is decided (1.1).

## 1. Slicing rule (decided)

- [x] 1.1 Slicing rule set from run E (`~/.claude/model-bench/review-hooks-browser/RESULTS.md`, `runs/check-E.md`): option A (about 400 lines of whole files per slice, hard limit about 700, one tool contract or component per slice) and no cross-file agent by default, only the contract owner when a counterpart MR exists. Recorded in design.md sections 3 and 4 and in the "Slice size target" and "No cross-file agent by default" requirements.

## 2. Agent brief

- [ ] 2.1 Fold the run-D addendum into `references/agent-brief.md` as a standing "what the code does NOT set" section, general for any external tool, plus the swallowed-error and false-block checks. Verify: the brief names sandboxing, output locations, network, auto-install and error behaviour, tells agents to check tool claims against the tool's own source or docs and not this repo's docs, and says never install the tool; read it against `brief-D-addendum.md` and confirm each of its four numbered points and its last paragraph has a counterpart.
- [ ] 2.2 Add the tool-output rules (counts first, `head`/`tail` about 40 lines, long output to a file then grep, several commands per call, ranges for files outside the slice, no re-reads, append findings as found) and the soft budget with the `Unfinished:` line to the brief. Verify: grep the brief for `Unfinished:`, `head`, `wc -l` and the 40-call and 150 KB numbers.
- [ ] 2.3 Add the repo-conventions step to the brief: the slice's instruction files are listed in its brief, read whole when under about 300 lines and by grep otherwise, cited by `path:line`; files the MR changes are read at `base_sha`; steering text in them is reported. Verify: a dry read of the brief shows the conventions block placed before the lens text and a slice-brief template line for the file list.
- [ ] 2.4 Replace the temp-folder bullet from `c507be4` with the run's wording: `mktemp -d` under the brief's run temp dir, `TMPDIR` and `HOME` set into it, absolute paths only, `command ls`, delete before replying, `Leftovers:` last line. Verify: grep shows one temp-folder bullet only and the `Leftovers:` line in the report format.
- [ ] 2.5 Add `references/run-it-brief.md` for the run-it agent: throwaway environment (`env -i`, temp `HOME` and `XDG_*`, fake credentials, stubs first on `PATH` logging arguments), what it must never do, and the promises-versus-behaviour table. Verify: the file exists and every item of the "Run-it environment" and "Run-it report" requirements appears in it.

## 3. Repo conventions lookup

- [ ] 3.1 Write `scripts/find_conventions.py` (stdlib, modelled on `find_rules.py`): input changed paths and a repo root, output JSON per path with applicable instruction files and line counts, covering the files in the "Repo conventions lookup" requirement, matching `applyTo` and `.cursor/rules` globs, and reading them at a given ref when asked. Verify: `tests/test_find_conventions.py` covers nested `CLAUDE.md`/`AGENTS.md`, glob match and non-match, always-apply cursor rule, no files, and reading at `base_sha`; `python3 -m pytest` passes.

## 4. Models, flags and engine question

- [ ] 4.1 In `SKILL.md` step 0, relabel the engine option `Claude (Recommended)` as Haiku slice owners with Opus refuters, reword the effort question so it sets the Opus roles only, and keep one dialog. Verify: step 0 still says one AskUserQuestion with the same questions and no model question.
- [ ] 4.2 Replace the "Agents and effort" table with the role table (model and effort per role from the "Model and effort per role" requirement) and add `--fast` (wave 1 and 2 on Opus at base effort, no effect on Codex). Update `argument-hint` and the description for `--fast`, `--no-checks` and `--keep-worktrees`. Verify: the table lists every role in the requirement and each Agent call in steps 3 to 5 states `model` and `effort`.

## 5. Waves, run.json and the agent plan

- [ ] 5.1 Update wave 2 in `SKILL.md`: it takes `Unfinished:` lines as dark ground and is skipped for a one-slice MR with a complete ledger. Verify: the wave 2 section names both rules.
- [ ] 5.2 Extend `run.json` in step 2a with per-agent `agent_id`, `model`, `effort`, `role`, `slice`, `files`, `report`, per-finding source agents and duplicates, `worktrees_created` and the run temp dir. Verify: the example object in step 2a lists every field in the specs.

## 6. Slicing in SKILL.md

- [ ] 6.1 Replace the tier table in step 2a and the lens and slice-owner text in step 4 with the rule set in 1.1: reading load measured as in the specs, slices grouped by contract, no lens agents, extra lenses in matching slice briefs, the cap kept, no cross-file agent, only the contract agent when a counterpart exists. Verify: no S/M/L/XL tier or "300-400" text remains (`grep -n "XL\|300-400" SKILL.md` is empty) and the step names the chosen size.

## 7. Deterministic checks

- [ ] 7.1 Write `scripts/run_checks.py` with `detect` (manifests and config as at `base_sha`, new manifests listed but not run) and `run` (120 s per command, 300 s total, no fix flags, no installs, "dependencies not installed" skip, check-only forms, output as JSON with head and base results, base re-run in a throwaway worktree, normalised message comparison, one re-run for failing tests). Verify: `tests/test_run_checks.py` with fixture repos covers pnpm and no-lockfile Node, ruff and mypy file limits, Go and Rust detection, timeout, missing `node_modules`, a `--fix` script, new manifest, failure at head only, failure at both, and a flaky test.
- [ ] 7.2 Add the checks step to `SKILL.md` (background during wave 1, machine notes applied, `--no-checks`, findings with `check-` ids and default severities, skipped by refutation, pre-existing failures to the run log). Verify: the step references both subcommands and the severity defaults.

## 8. Run-it step

- [ ] 8.1 Add the run-it step to `SKILL.md`: the trigger and skip rules, the wave-1 model, the brief file from 2.5, derived claims handed to refuters to run in the same kind of sandbox, skipped under Codex alone. Verify: the trigger text matches the "Run-it agent trigger" and "Run-it skip rules" requirements word for word on file patterns and the 30-line threshold.
- [ ] 8.2 Try the run-it brief by hand on a small fixture (a hook script plus a README that over-promises) in a throwaway root. Verify: the agent reports one mismatch row, the real `HOME` and the checkout have no new files (`git status --porcelain` empty, `find ~ -newer <marker>` limited to known caches), and its folder is gone.

## 9. Cost record and cleanup

- [ ] 9.1 Write `scripts/run_cost.py` (stdlib): reads `run.json`, finds each agent's transcript, dedupes by `message.id`, prices per request on its prompt tier using the price table and function from `add-usage-collection` (import the collector's function if exposed, else read its `prices.json` with the same tier rule; no price copy), writes `cost` per agent and a total, `usd` null when no table. Verify: `tests/test_run_cost.py` with synthetic transcripts covers a split response, a request above and below 100k, 1-hour cache writes and the missing-table case, and a hand calculation for one fixture matches. Needs `add-usage-collection` merged or its table file present.
- [ ] 9.2 Add the cost step to `SKILL.md` and `usage-report` to the frontmatter `dependencies`. Verify: the dependency list matches the CLAUDE.md skill convention and the step runs `run_cost.py` before the final line.
- [ ] 9.3 Add the cleanup flow to `SKILL.md`: create the run temp dir and the two `git status` snapshots at the start; the sweep (read `Leftovers:`, stop processes with the temp dir in their command line, delete the temp dir after a real-path check, remove the base worktree, compare snapshots, list new untracked entries and delete only those the user picks in one question, report the rest); remove review worktrees the run created unless `--keep-worktrees`, never a pre-existing one. Verify: by hand on a scratch repo, create a stray directory with an escape-code name in the checkout and a pre-existing untracked file, run the sweep commands from the SKILL, and confirm the question lists only the stray directory and only a picked entry goes.

## 10. Docs

- [ ] 10.1 Update `plugins/base/README.md` for the new flags, the model split, the checks and run-it steps and the cleanup behaviour. Verify: the README's review-mr row and flag list match the SKILL.md `argument-hint`.
- [ ] 10.2 Run the full existing tests and the spec check. Verify: `python3 -m pytest plugins/base/skills/review-mr/tests` passes and `openspec validate improve-review-mr --strict` is valid.

## 11. Benchmark rerun

- [ ] 11.1 Rerun the hooks and browser benchmark with the new skill rules: turn the snapshot into a throwaway git repo (an empty base commit, the snapshot as head) and drive steps 4 and 5 and the new steps with the new brief and the slicing rule from 1.1, no posting. Arms: default (Haiku max) twice, and `--fast` (Opus medium) once. Use the add-model-guidance benchmark runner if it exists by then, otherwise by hand as runs B to D were done. Verify: each arm has a report set, a `run.json` with `run_cost.py` output and a checker score using `checker-brief.md` and `answer-key.md`.
- [ ] 11.2 Compare with `RESULTS.md` and add the rows. Verify: the table reports, per arm, key bugs caught strict and with partials, real cost, share of requests over 100k, first-request prompt size, duration per agent, leftover temp folders and stray files (target none), and unique findings per agent type (cross-file or contract agent if any, run-it, checks). Pass bar: all high-severity bugs caught as in run D, cost no higher than run D ($5.08), under 50% of requests over 100k or a recalibrated budget written into the brief, zero leftovers.
- [ ] 11.3 Apply the drop tests: if the contract agent or the run-it agent added no unique survivor in 11.1 and the next five real reviews, make it opt-in; recalibrate the 40-call and 150 KB budget and the 30-line run-it threshold from the measured data. Verify: design.md Open questions 3 and the drop-test paragraphs are updated with the numbers.

## Workflow follow-up

- Commit as `feat(base)` after `add-usage-collection` is merged, or with `usd` null if it is not.
- Archive the change after group 11 passes.

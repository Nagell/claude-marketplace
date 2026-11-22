# Tasks

Prerequisite: `add-usage-collection` is implemented and its dataset, `prices.json` format and `usage-report` skill exist.

## 1. Skill scaffold and prices

- [ ] 1.1 Create `plugins/base/skills/model-guidance/SKILL.md` (`disable-model-invocation: true`, `dependencies: [usage-report]`) with the run order: preflight, prices, external evidence, usage, benchmark, proposal; verify with `grep -n dependencies` and by reading the skill end to end for the spec's approval gates
- [ ] 1.2 Add the preflight (dataset present, last status `ok`, at least 14 active days) as a helper script; verify with fixture data directories for no data, thin data and good data
- [ ] 1.3 Add a script that fetches the pricing page in markdown form, parses the model table and diffs it against the active `prices.json`; verify with a saved copy of the page as fixture (added, changed, retired models) and by one live fetch whose model count matches the page
- [ ] 1.4 Write the price-refresh steps in the skill: footnotes to tiers, `claude-api` cross-check with disagreement shown, approval before writing the user override, then the reprice hint and the list of unpriced dataset models; verify by a dry run that declines the diff and leaves `~/.claude/usage/prices.json` unchanged

## 2. External evidence

- [ ] 2.1 Create `skills/model-guidance/sources.json` from the source table in design.md (URL, contribution, read method, stability, verified date); verify every URL answers and update the verified dates
- [ ] 2.2 Add fetch helpers for Artificial Analysis (Data API with `AA_API_KEY`, page fallback, MCP fallback) and the Terminal-Bench leaderboard table, saving raw fetches under `~/.claude/model-bench/external/<date>/`; verify that output rows carry model, effort, metric, URL and date, and confirm from the API whether Claude 5.5 models appear at efforts below max
- [ ] 2.3 Add per-source failure handling (named, skipped, listed as a registry problem) and the "new source proposed, added on approval" step; verify by pointing one registry entry at a dead URL and checking the run continues and reports it

## 3. Benchmark

- [ ] 3.1 Write `references/benchmark-format.md` (directory layout, `case.json`, `key.json`, `run.json`, score and cost files) and run a one-arm dry run with `claude -p` to settle the read-only tool flags and the `--output-format json` fields used for cost; verify the reference matches the dry run's files
- [ ] 3.2 Add a case-creation and checksum script (manifest, key items referencing snapshot files); verify it refuses a run when one snapshot byte changes
- [ ] 3.3 Move the 2026-11 experiment snapshot and answer key to durable storage first, then import them as case `hooks-browser-review`; verify the manifest checks out and `key.json` has 14 items (5 hooks, 7 browser scripts, 2 docs)
- [ ] 3.4 Add the run step: arms list with older models, repeats, fresh temp snapshot per run, no key in the working directory, estimate and cost cap with approval; verify with two cheap arms that the key path is not reachable from the run directory and that the cap stops a batch
- [ ] 3.5 Add the fixed-checker scoring step and a scoring script (recall, severity-weighted recall, false findings, extra real, cost per caught bug); verify against the earlier experiment's hand-scored reports (agreement within one item)
- [ ] 3.6 Add cost lookup from the dataset by session id or agent description, with a collector refresh first and `claude -p` reported cost as a cross-check; verify one run's cost against its transcript totals
- [ ] 3.7 Add stored-run comparison (new arm beside old, invalid when checker, brief or snapshot differ); verify with a fabricated stored run that has another checker

## 4. Usage by task type and the proposal

- [ ] 4.1 Add task-type classification (heuristics, cache, one approved batched call for unlabelled titles) and a usage summary per task type with the thin-data label; verify on the real dataset that no unlabelled batch call happens without approval
- [ ] 4.2 Add the guidance table builder (tiers, split by task type, evidence month and review-by month, 30% rule, outlier-only for cost) and the guidance log writer; verify with fixtures for a mixed outcome (review changes, commit-chore stays) and for cost-only evidence (no rule)
- [ ] 4.3 Add the diff and approval step for `~/.claude/CLAUDE.md` and `plugins/base/CLAUDE.md`, one diff and one `AskUserQuestion` each, ten-line cap; verify that declining one leaves that file byte-identical and approving the other changes only the model section
- [ ] 4.4 Document the skill in `plugins/base/README.md` (when to run, cost of benchmark runs, where data lives); verify every command in the section runs as written
- [ ] 4.5 Integration run after a real model release or with the current models: all phases on this machine, with one cheap benchmark pass; verify a guidance log entry exists, no CLAUDE.md changed without approval and the plan-window warning appeared

## Workflow follow-up

- Commit with `feat(base): ...` through the commit agent. Do not push without the user's yes.
- Archive the change after review.

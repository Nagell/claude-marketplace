# Tasks

## 1. Prices

- [ ] 1.1 Create `plugins/base/skills/usage/prices.json` from the 2026-11-21 official table (Opus 5.5, Sonnet 5.5, Haiku 5.5 with its 100k long-prompt tier, Fable 5.2 and the older models) with a `version` field. Verify: `python3 -m json.tool` parses it and every model has the five base prices.
- [ ] 1.2 Write `scripts/prices.py` (stdlib), starting from `~/.claude/model-bench/review-hooks-browser/cost.py`: load the seed, merge a valid `~/.claude/usage/prices.json` over it per model id and return both table versions, report an invalid override and use the seed alone, match model ids exactly then without a date suffix, compute prompt size and per-request cost on the right tier, count `cache_creation_input_tokens` as 5-minute writes when the `cache_creation` dict is missing, return null for an unpriced model. Verify: `tests/test_prices.py` covers Haiku at 80k and 120k, a 1-hour cache write, a missing `cache_creation` dict, the dated id `claude-haiku-4-5-20251001`, an invalid override and an unpriced model, and one hand-computed cost matches.
- [ ] 1.3 Add an override merge fixture. Verify: an override that lists only Haiku 5.5 changes Haiku's cost, Opus 5.5 keeps its seed price, and the output names the seed and override versions.
- [ ] 1.4 Add a regression fixture with `cost.py`'s run D token counts. Verify: `prices.py` gives the same USD as `cost.py` for each run D agent.

## 2. Scanner

- [ ] 2.1 Write `scripts/scan.py`: find session and agent transcripts with activity in a window, parse tolerantly with a skipped-line count, dedupe by `message.id` with one set per scan (files read in order of first timestamp, largest value per usage field), skip `<synthetic>` lines and report their count as API errors, keep the five token classes apart, and link agents through the meta file. Verify: `tests/test_scan.py` with fixtures in `tests/fixtures/` covers a split response, a truncated last line, an agent with and without meta, and a file older than the window that is not opened.
- [ ] 2.2 Add dedupe fixtures. Verify: two session files that share ids count each shared id once, in the earlier file; a response whose first line has `output_tokens` 1 and last line 335 counts 335 once; a `<synthetic>` line is counted as an API error and is not listed as unpriced.
- [ ] 2.3 Add run detection per design decision 4: typed prompt by `origin.kind` `human` with the content fallback when `origin` is missing, runs by `attributionSkill` with unattributed lines kept in the open run, else a skill `<command-name>` or `Skill` tool_use, and agent-to-run linking by `toolUseId` and, for nested agents, `parentAgentId`. Verify: tests for a run with nine agents, the same skill twice in one session, a session without `attributionSkill` and requests outside any skill.
- [ ] 2.4 Add run boundary fixtures. Verify: a `<task-notification>` user line in the middle of a run does not end it; assistant lines without `attributionSkill` inside an open run stay in it; `/clear` in a session without `attributionSkill` starts no run; a nested agent at `spawnDepth` 2 with `parentAgentId` lands in its parent agent's run.
- [ ] 2.5 Add per-agent details (role, actual model, effort, requests, token classes, largest prompt, over-100k count, duration, cost, `Unfinished:` count or n/a, meta `finished` when present), export `summarize_agent(path)` for one agent file, and add a JSON CLI. Verify: a test on a fixture agent with an `Unfinished:` line and a 140k prompt, a test that a skill whose agents never use `Unfinished:` shows n/a, a test that `summarize_agent` on a fixture agent equals that agent's entry in the scan output, and `python3 scripts/scan.py --days 30` on the fixtures prints valid JSON.

## 3. Report script

- [ ] 3.1 Write `scripts/report.py` with `--days`, `--top`, `--runs`: rank skills by spend, aggregate trends per skill (cost per run, per role, per model and effort, over-100k share, per month) and pick the last N runs plus outliers (most expensive, most `Unfinished:` lines, largest prompt), marking a run that is both and skipping the most-`Unfinished:` outlier when the count is n/a. Verify: `tests/test_report.py` covers default top 5, fewer skills than the limit, a custom run count and an outlier that is also recent, and a skill with the `Unfinished:` count n/a.
- [ ] 3.2 Add `--retention`: read `cleanupPeriodDays` (unset means 30, 0 means no sweep and no offer), measure average transcript bytes per active day and print the 180-day estimate; add a `--set-retention 180` write that keeps every other key and replaces the file atomically. Verify: tests on a temp home for unset, 0, under 180 and 180 or more, and a write that keeps a sample of other keys.

- [ ] 3.3 Read `review-mr`'s `run.json` per design decision 5a: add `--scratch-root` (default `/tmp/claude-<uid>`), find `<scratch root>/<project dir>/<session id>/scratchpad/run.json` for each scanned session, match agents by `agent_id`, label by role and slice, price them with `summarize_agent`, and count unique and repeated surviving findings per role from `source` and `duplicates`. Verify: `tests/test_report.py` covers a fixture run with `run.json` (labels, cost per role, unique findings per role), a repeated finding, a run without `run.json`, a Codex agent with no cost and a `--scratch-root` on a temp dir.

## 4. Skill and docs

- [ ] 4.1 Write `plugins/base/skills/usage/SKILL.md` (`disable-model-invocation: true`): retention check first, then AskUserQuestion with `report (Recommended)` and `models (not available yet)`, the report flow (run `report.py`, read the selected agents' final replies, write drop and strengthen candidates citing run ids), the "output only, apply through an OpenSpec change and a benchmark" rule, and no file writes into the working tree. Verify: read the skill end to end against each `usage-report` requirement.
- [ ] 4.2 Add a `usage` section to `plugins/base/README.md`: what it reads, where the price override lives and that it merges per model id, retention, the estimate caveat and how to run the tests. Also add a `/base:usage` row to the "You invoke these" table, add `usage` to the Python 3 requirement line, and add usage to the base row in the root `README.md`. The `/base:cleanup` row from `add-cleanup` is already in the table; keep it. Verify: every command in the section runs as written on the fixtures, and `grep -n usage README.md plugins/base/README.md` shows the row, the requirement and the root entry.
- [ ] 4.3 Run the skill once on this machine's real transcripts. Verify: one session's total is within the documented 12% estimate gap of its last `cost-state` line's `totalCostUSD` (the gap is side calls such as the dated Haiku 4.5 id), the top skills look right against a hand count, `git status` in the working tree is clean, and no prompt text appears in the script output (grep for a known prompt).

## 5. Portability

- [ ] 5.1 Run `uv run --python 3.9 python -m unittest discover -s tests` from the skill folder, and grep the scripts for GNU-only calls and non-stdlib imports. Verify: all tests pass and the grep finds none; note that macOS was not run unless a Mac is available.

## Workflow follow-up

- `move-review-cost-to-usage` removed `review-mr`'s own pricing; this change is now the only place that prices review runs.
- `add-usage-models-mode` adds the `models` mode and modifies this change's `usage-report` spec after archive.
- Commit as `feat(base): ...` through the commit agent. Do not push without the user's yes.
- Archive after review.

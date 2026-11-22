# Tasks

## 1. Collector core

- [ ] 1.1 Create `plugins/base/skills/usage-report/scripts/collect.py` (stdlib only) with transcript discovery, ledger and incremental reads; verify with `python3 -m unittest` cases for unchanged, grown and partial-last-line files on synthetic fixtures in `skills/usage-report/tests/fixtures/`
- [ ] 1.2 Add message parsing, dedupe by message id (including a response split across two runs) and local-day attribution; verify with tests for split response, run boundary, multi-day session and a 23:30 UTC message in a UTC+1 zone
- [ ] 1.3 Add subagent discovery and meta-file linking, compaction events and `derived-from` chain; verify with tests for an agent with and without a meta file and for a compacted multi-day session
- [ ] 1.4 Add session rebuild for rewritten files (size below offset, head hash change); verify with a test that truncates and regrows a fixture and ends with unchanged totals

## 2. Dataset and prices

- [ ] 2.1 Write monthly JSONL rows with the six token classes, keyed by day, session, agent, model, effort, speed and tier, using temp file plus `os.replace`; verify with a test that kills the writer mid-way and still reads the old file
- [ ] 2.2 Add seed `skills/usage-report/prices.json` from the 2026-11-21 official table (Opus 5.5, Sonnet 5.5, Haiku 5.5 with long-prompt tier, Fable 5.2 and the older models) and the user override; verify per-request pricing against hand-computed values, including a Haiku request over 100k and an unpriced model
- [ ] 2.3 Add the `--reprice` option; verify that changing a price in the override file changes every affected row and its table version

## 3. Daily files and the skill

- [ ] 3.1 Render `daily/YYYY-MM-DD.md` (title, count-built summary, fixed table, flags) for touched days only; verify with a golden-file test and a test that an idle day writes no file
- [ ] 3.2 Add `skills/usage-report/SKILL.md` (re-collect a day, show the file, document the format and the estimate caveat) with a `--day` option in the collector; verify by running the skill against fixtures for a normal day, a swept day and an empty day
- [ ] 3.3 Run the collector once on this machine's real transcripts with a throwaway `CLAUDE_CONFIG_DIR` copy of the data root; verify that totals for one known day match a hand count from the transcripts within the documented 12% estimate gap and that no prompt text appears in the output (grep)

## 4. Health and escalation

- [ ] 4.1 Add validation (parse failures, missing fields, zero usage on an active day, unknown types), `status.json` (running then final) and `diagnostics.jsonl` with key names only; verify with tests for each threshold, including the five-line floor, and for crash detection
- [ ] 4.2 Create `hooks/usage-session-start.sh` and the python hook script: python3 check, throttle, detached spawn, status read, once-per-day `additionalContext` JSON via `notified.json`, opt-out; verify by piping a SessionStart payload in with `ok`, `error`, already-announced, stale and `CLAUDE_USAGE_COLLECT=0` states and checking the printed JSON and exit code
- [ ] 4.3 Register the hook in `plugins/base/hooks/hooks.json` under `SessionStart`; verify the JSON parses and a fresh session on this machine starts a collector (status file updates) without delaying startup (time the hook, under 200 ms)
- [ ] 4.4 Add `skills/usage-investigate/SKILL.md` (`disable-model-invocation: true`, background agent, writes only to `investigations/`); verify by breaking a fixture on purpose, running the command and checking the findings file names the changed field

## 5. Platforms and docs

- [ ] 5.1 Check portability: run the unit tests under the lowest python3 available, run `shellcheck` on the hook script, grep for `setsid`, `date -d`, `stat -c` and other GNU-only calls; verify none remain, and note that macOS was not run unless a Mac is available
- [ ] 5.2 Document in `plugins/base/README.md`: what is stored and where, the off switch, `cleanupPeriodDays`, the estimate caveat; verify every command in the section runs as written
- [ ] 5.3 Confirm `usage-investigate` declares `dependencies: [usage-report]` in its frontmatter (repo skill convention) and that `hooks.json` and `plugin.json` are valid JSON; verify with `grep -n dependencies` and `python3 -m json.tool`

## Workflow follow-up

- Commit with `feat(base): ...` through the commit agent. Do not push without the user's yes.
- Archive the change after review.

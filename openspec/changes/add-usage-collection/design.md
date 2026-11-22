# Design

## Context

Facts checked against real local transcripts (Claude Code 2.1.247 to 2.1.330):

- Transcripts live in `~/.claude/projects/<slug>/<session>.jsonl`. Subagents live in `<session>/subagents/agent-<id>.jsonl` with an `agent-<id>.meta.json` (agentType, description, model alias, effort, toolUseId, spawnDepth).
- Each assistant line has `message.id`, `message.model`, `timestamp` (UTC) and `message.usage`. One response is written as one line per content block with identical usage: 1,404 lines held 626 unique ids in one session, so naive sums are about 2.2x too high.
- Cache reads dominate raw token sums, so token classes must stay separate.
- Resume and compaction keep the same session file. `/clear` starts a new session id with a `derived-from` line. Compaction is a `compact_boundary` system line. 12 of 31 local session files span more than one active day.
- `effort` is per assistant line and can change inside a session.
- Hooks: `SessionStart` can return `additionalContext`. Plain stdout from other hook types is silently dropped, so output is always JSON. A hook's output reaches the agent that ran it.
- Transcript format is undocumented. Fields such as `ai-title`, `cost-state` and `attributionAgent` exist only in some versions.
- The repo is public. Existing hooks are shell scripts called as `${CLAUDE_PLUGIN_ROOT}/hooks/<name>`.

## Goals / Non-Goals

**Goals:**

- A correct per-day record of sessions, agents, tokens and estimated cost that survives transcript sweeps.
- Cheap on a machine with thousands of session files.
- A break in the collector is noticed in the next session.

**Non-Goals:**

- Any LLM call in the daily run. Task-type categories (review, implement) belong to `add-model-guidance`.
- Plan-window consumption. It is not available locally, so USD is an API-equivalent proxy, not a measure of the subscription window.
- A scheduler, cloud routine or Windows-native support.
- Changing `cleanupPeriodDays`. The README only recommends raising it.
- Pricing refresh from the web. The seed table ships here; `add-model-guidance` refreshes it.

## Decisions

### 1. Home: plugin `base`, one collector script shared by hook and skill

The user chose `base` over a new `usage` plugin. The collector lives in `plugins/base/skills/usage-report/scripts/collect.py` and the hook calls it through `${CLAUDE_PLUGIN_ROOT}/skills/usage-report/scripts/`. One copy serves the hook, the skill and later the benchmark. The hook entry point is `hooks/usage-session-start.sh` (POSIX `sh`), which checks python3 and runs a small python hook script with `python3 -I`.

Rejected: new plugin `usage` (more to maintain; user decided otherwise), keeping the collector in `hooks/` (the skill would need a second path).

### 2. Trigger: SessionStart, detached by python, no scheduler

The hook is synchronous because it must return `additionalContext`. It reads `status.json` (small), prints context if needed, then spawns the collector with `subprocess.Popen(..., start_new_session=True)` and exits. Python replaces `setsid`, which macOS lacks. A throttle (no spawn when the last run ended under five minutes ago) keeps resume and compact restarts cheap. The collector holds `fcntl.flock` on a lock file: the lock disappears when the process dies, so there are no stale locks.

Rejected: SessionEnd (1.5 s budget, never fires for multi-day sessions), systemd or cron (not running on this WSL), desktop scheduled task (starts a full session just to run a script), cloud routine (cannot see `~/.claude`). `async: true` alone was rejected because the hook needs to inject context.

Because the source is the transcripts, not the hook payload, nothing is lost when no session starts for a day; the next start catches up.

### 3. Ledger and incremental reads

`~/.claude/usage/ledger.json` maps file path to `{size, mtime_ns, offset, head_hash, session, agent, tail_message_id, title, pr, branch}`. Per run: `stat` every file, skip if size and mtime match, otherwise open, seek to `offset`, parse whole lines only, advance `offset` to the end of the last complete line. `head_hash` is a hash of the first 4 KiB: it detects a rewritten file (the other trigger is `size < offset`). A rewritten file marks its session dirty: all rows of that session are dropped and rebuilt from its files at offset 0. A session is therefore the unit of replacement.

Messages split across runs: block lines of one response are adjacent, so the ledger keeps `tail_message_id` and the next run skips leading lines with that id. Rejected: keeping every seen id in the ledger (grows without bound), re-reading the whole file (defeats the ledger).

Vanished files stay in the ledger flagged `gone` so their rows are never deleted.

### 4. Dataset: aggregated rows, monthly JSONL, reprice-able

Row key: day, session, agent, model, effort, speed, prompt tier. Values: requests, six token classes, web searches, est_usd, price table version, plus title, skill, branch, PR, compactions, first and last timestamp, project, entrypoint, agent type and description, chain (`derived-from` id). Rows are additive, so incremental lines add to an existing row. Files are `data/YYYY-MM.jsonl`, rewritten via temp file and `os.replace`, only for touched months. Prompt tier is a key dimension because Haiku 5.5 prices a request over 100k prompt tokens (cache reads included) at 5x: a per-day total could not be repriced correctly, a per-tier total can.

Rejected: one row per request (about 70 MB a year, no analysis need yet), one `usage.jsonl` (rewritten in full on every run), CSV (export on demand).

### 5. Attribution rule

Per message, local day of its own timestamp, using the system zone (so DST is handled by the stdlib). Rows exist only for active days. Compaction is an event on its boundary day. Task label is the latest `ai-title` at or before the row's last line, then skill, PR, branch, agent description. Rejected: whole session on start day or end day (hides cost, and the number moves later), per compaction segment (segments are context units, not time or cost units).

Known blind spot: the compaction summary call and some side calls (web-search Haiku, title generation) are not assistant lines, so estimates can be 7 to 12% low compared with `cost-state` on some sessions. The daily file says "estimate".

### 6. Cost

`prices.json` holds absolute per-model prices (input, output, 5m and 1h cache write, cache read, optional long-prompt tier with threshold, web-search price). Absolute prices, not multipliers: cache-read ratios differ per model. The seed is the 2026-11-21 table from the official page. A user file at `~/.claude/usage/prices.json` overrides it. A `--reprice` run recomputes estimates from stored tokens.

### 7. Validation, status, escalation

The collector records parse-failure and missing-field ratios, unknown entry types and zero-usage active days (see spec). Thresholds are 1% with a floor of 5 lines, so one truncated line never alerts. Status is written at start (`running`) and at the end, which makes a crash visible. The hook injects at most one note per distinct problem set per local day, tracked in `notified.json` (separate from `status.json` so the hook and the collector never write the same file). The note carries an instruction for the model, not just a message, because the hook cannot print to the user directly. The background job itself never needs an agent.

`usage-investigate` is a user-only skill (`disable-model-invocation: true`, as `review-mr` does) that spawns one background agent with read access and write access only to `~/.claude/usage/investigations/`. Diagnostics hold key names, not values, so the agent can look at shapes without prompts leaking into a file.

### 8. Privacy and opt-out

No prompt text, file contents or tool arguments are stored. Titles, project names, branches and agent descriptions are, so the data directory is outside every repo. Since `base` is installed by everyone, `CLAUDE_USAGE_COLLECT=0` turns the hook off.

### 9. Tests

Stdlib `unittest` with synthetic transcripts committed under `skills/usage-report/tests/fixtures/` (no real data). Cases: split-response dedupe, run boundary, multi-day and UTC edge, compaction, agent link, rewrite, price tiers, validation thresholds, crash recovery.

## Risks / Trade-offs

- Transcript format drift: mitigated by validation and escalation, but a silent semantic change (a field that stays valid but means something else) is not detectable. The calibration check against `cost-state` (where present) is a manual sanity test in the skill docs.
- Retention: if transcripts are swept before the first run, history is gone. README recommends `cleanupPeriodDays` of 90 or more.
- Hook cost: python startup is paid at every session start (tens of ms). Accepted.
- Forced on every `base` user: mitigated by the off switch and by storing nothing outside `~/.claude`. A background process writing files is still a behavior change, so release notes say so.
- Adjacent-block assumption for run-boundary dedupe. If blocks of one response are ever interleaved with other ids, a boundary could double count once. The session rebuild option corrects it.
- Local zone changes (travel) are not applied to old rows.
- Subagent token numbers in task notifications were never reconciled with transcript sums. Transcripts are the source.

## Open questions

Assumptions made because nobody could be asked:

- The off switch is an environment variable, not a settings entry. Cheap and visible; revisit if users want a config file.
- Announce at most once per local day per problem set. Could be per session instead.
- Collector needs python 3.8 or newer. The oldest macOS system python3 (3.9) fits; not tested on 3.8.
- Skill and hook sit in `base`, as decided, but a later split into an opt-in plugin stays possible because everything lives in two skill directories and one hook.
- `fcntl` is POSIX only, so native Windows is out. WSL is in.
- The 1% threshold and five-minute throttle are first guesses; tune after a week of real runs.

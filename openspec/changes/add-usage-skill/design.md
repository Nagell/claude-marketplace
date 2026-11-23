# Design

## Context

See proposal.md for why. Facts checked against local transcripts (Claude Code 2.1.247 to 2.1.330, research carried over from `add-usage-collection` and rechecked on 2026-11-22):

- Session transcripts live in `~/.claude/projects/<slug>/<session>.jsonl`. Agents live in `<session>/subagents/agent-<id>.jsonl` with `agent-<id>.meta.json` (`agentType`, `description`, `toolUseId`, `spawnDepth`, `pickedEffortModel`, and for nested agents `parentAgentId`). Meta `model` is an alias, a full id or `inherit`, and is often missing; meta `effort` is often missing too. The scanner relies on line-level `message.model` and `effort` instead. 128 of 129 sampled meta files have `toolUseId`.
- Each assistant line has `message.id`, `message.model`, `timestamp` (UTC) and `message.usage`. One response is written as one line per content block, usually with the same usage. One session had 1,404 lines for 626 ids, so raw sums are about 2.2x too high. In versions 2.1.247 and 2.1.271 the first line of some responses has a lower `output_tokens` than the last line.
- A resumed or derived session copies its parent's history, so 384 ids appeared in two session files (about 5% of session tokens). Agent and session files never share ids.
- User lines carry `origin.kind`: `human` for a typed prompt, `task-notification` when a background agent finishes, `peer` for peer messages. Older lines lack `origin`.
- Built-in commands (`/plugin`, `/clear`, `/compact` and others) also appear as `<command-name>` user lines.
- 22 assistant lines have `message.model` `<synthetic>`: API error placeholders with zero tokens.
- Session files have `cost-state` lines with Claude Code's own `totalCostUSD` and `modelUsage`. They include side calls on dated ids such as `claude-haiku-4-5-20251001` that are not on assistant lines.
- Assistant lines carry `attributionSkill` (for example `base:review-mr`) in both session and agent transcripts in recent versions. Older lines lack it. Slash commands appear as a user line with `<command-name>`. Model-invoked skills appear as a `Skill` tool_use.
- `effort` is per assistant line and can change inside a session.
- After a typed reply, Claude Code usually drops `attributionSkill` on the turns that answer it (50 of 54 first turns after a reply in a 30-day sample). Compaction summaries are user lines with `isCompactSummary`.
- Claude Code resolves its config folder as `CLAUDE_CONFIG_DIR`, else `~/.claude`; transcripts and `settings.json` live there.
- Cache reads dominate raw token sums.
- `cleanupPeriodDays` is unset on this machine. Claude Code documents a default of 30 and a minimum of 1; setting 0 fails validation (rechecked 2026-11-23). The sweep did not delete files older than 30 days here: the oldest transcript was 85 days old.
- The transcript format is undocumented and fields come and go between versions.
- Skill scripts live in `scripts/*.py` with tests in `tests/test_*.py`. This change follows the `setup-zsh` and `add-cleanup` layout with stdlib `unittest`; `review-mr` uses pytest.
- Prior art: `~/.claude/model-bench/review-hooks-browser/cost.py` already prices requests per model, with 5-minute and 1-hour writes, the Haiku tier above 100k and a fallback to `cache_creation_input_tokens` when the `cache_creation` dict is missing. `improve-review-mr` quotes its run D costs.

## Goals / Non-Goals

**Goals:**

- One scanner and one price module that every mode shares. No other skill prices requests.
- A report that runs in seconds on a few thousand transcript files.

**Non-Goals:**

- Keeping history past the retention sweep. Longer retention is the answer, offered by the retention check.
- Plan-window consumption. It is not available locally. USD is an API-equivalent estimate.
- Price refresh from the web. Prices come with plugin releases or the user's override file.
- Native Windows.
- The `models` mode. It belongs to `add-usage-models-mode`.

## Decisions

### 1. Layout in plugin `base`

```
plugins/base/skills/usage/
  SKILL.md              user-invoked, asks the mode
  prices.json           seed price table
  scripts/scan.py       transcript reading, dedupe, runs, agents (CLI + importable)
  scripts/prices.py     table loading, prompt tier, per-request cost (importable)
  scripts/report.py     top skills, trends, outliers, retention numbers (CLI)
  tests/                unittest + synthetic fixtures
```

`prices.py` is the single copy of the price logic. `scan.py` imports it and exports `summarize_agent(path)`: dedupe, token classes, prompt sizes and cost for one agent file, which the scan calls for every agent. `report.py` labels the agents of a `review-mr` `run.json` (decision 5a) on top of the scan's numbers, so the two always match. The later `models` mode reuses `scan.py` and `prices.py` and adds its own script.

Rejected: one big script (the models mode would import the report code too), pricing inside `review-mr` (two places to keep in step; `move-review-cost-to-usage` removed it), a separate plugin (the user chose `base`).

### 2. On-demand scan, no stored state

`scan.py` walks the project folders, skips files whose modification time is older than the window start, and parses the rest line by line. It prints JSON to stdout. Nothing is cached. A full read is acceptable because the report runs rarely and only on files in the window.

Rejected: the ledger and daily dataset from `add-usage-collection` (hook, background job, rewrite detection and health checks, for a question that is asked a few times a month).

### 3. Dedupe

Keep one set of `message.id` per scan, across all files. Files are read in order of their first timestamp, then by line count, so a resumed session's copied history counts in the parent file even when both start at the same time. For each id, take the largest value of each usage field over its lines, because an old first line can hold partial usage. Lines without an id are counted as their own request, under an id that includes the file path. Lines whose model is `<synthetic>` are not priced and not listed as unpriced; their count is reported as API errors. When a line has no `cache_creation` dict, `cache_creation_input_tokens` counts as 5-minute writes, as in `cost.py`.

### 4. Run detection

A run is keyed by session and skill. Rule, in order:

A typed prompt is a user line with `origin.kind` `human`. When `origin` is missing, a typed prompt is a user line with string content that is not `isMeta`, not a tool result and does not start with `<task-notification>`, `<local-command` or `<bash-`. Task notifications and peer messages never end a run.

1. If assistant lines carry `attributionSkill`, a run starts at the first line with a value and ends at the next typed prompt. An assistant line without `attributionSkill` inside an open run stays in that run. A different skill inside an open run (one skill loading another) stays in the open run and is listed as nested. After a typed prompt, the last run reopens unless the skill was invoked again (a skill `<command-name>`, a skill-load meta line or a `Skill` tool_use): when the next line carries the same skill, or when the run's last turn asked the user something (it ends with a question or an `AskUserQuestion` call) and the next line carries no skill. Compaction summaries are not typed prompts. A plugin command (name with `:`) starts a run at once; another unknown command only when a skill-load line follows.
2. Otherwise the run starts at a `Skill` tool_use, or at a `<command-name>` user line for a skill command, and ends at the next typed prompt. A `<command-name>` is a skill command when the name contains `:`, is not a built-in command, or the following lines carry `attributionSkill` or the skill-load meta line. `/clear`, `/compact`, `/plugin` and other built-ins never start a run.

An agent belongs to the run that holds the `Agent` tool_use whose id matches the meta file's `toolUseId`; the first file to hold that id wins, so a resumed session's agents join the parent's run. A nested agent (`spawnDepth` 2) matches a tool_use in its parent agent's file; it belongs to the parent agent's run through `parentAgentId`. When `toolUseId` is missing, the agent's own `attributionSkill` or its start time inside a run decides. Skill names are normalized by dropping the plugin prefix for display (`base:review-mr` shows as `review-mr`) and kept in full in the JSON.

Rejected: whole session as one run (a session often runs several skills).

### 5. Per-agent details

Role is `agentType` plus `description` from the meta file. Model is the most frequent `message.model` in the agent file (the actual model, not the alias). Effort is the most frequent `effort` value. Largest prompt and requests over 100k use the prompt rule below. `Unfinished:` lines are counted in the agent's last assistant text and in its last Write to a `.txt` or `.md` file, because `review-mr` agents write the line into their report and reply with the path. The convention comes from `review-mr`'s agent brief, so it applies to `review-mr` only; other skills report n/a. The meta field `finished` is reported as a second signal when present. Duration is last minus first timestamp. Files left unread are not counted by the script: the model finds them in the deep read from the agent's ledger or reply.

### 5a. Review runs from run.json

`review-mr` writes `$SCRATCH/run.json`, where `$SCRATCH` is `<scratch root>/<project dir>/<session id>/scratchpad`. The scratch root is not under `~/.claude`: it is `/tmp/claude-<uid>` on Linux and WSL. `report.py` takes `--scratch-root`; the skill passes the parent three levels above its own scratchpad, as `cleanup.py`'s `default_scratch_root` does, and the script falls back to `/tmp/claude-<uid>`. `<project dir>` and `<session id>` are the same names as the transcript's folder and file. For each scanned session `report.py` reads that file when present; a broken file is listed under `errors`. Each entry is checked (string role, slice and source, a list of strings for duplicates, a boolean survived), and bad entries are skipped and counted rather than stopping the report. It matches each entry of `agents` to a scanned agent by `agent_id` (`agent-<agent_id>.jsonl`) and uses its `role` and `slice` as the agent's label, keeping the requested `model` and `effort` next to the actual model from the transcript. A finding with `survived: true` counts as unique for the agent its `source` names (a slice name or a role) and as repeated for each entry in `duplicates`. Per role the report shows cost and unique surviving findings. A Codex agent (`"model": "codex"`) has no transcript and shows no cost. Without a `run.json`, or for agents it does not list, labels fall back to the meta file (decision 5).

A session holds one `run.json`, the latest review run's. It goes to the review run whose agents it lists, else to the latest one; agents from other runs keep meta-file labels. The scratchpad lives in `/tmp`, which a reboot or a tmp cleaner clears, and `/base:cleanup` removes stale ones, so most older runs have no `run.json`; the report says how many review runs had one.

Rejected: `review-mr` pricing its own agents (two places that price), `review-mr` writing cost into `run.json` (stale once prices change).

### 6. Prices and tier

`prices.json` holds absolute per-model prices: input, output, 5-minute and 1-hour cache write, cache read, and an optional `long_prompt` entry with a threshold and its own prices. Absolute prices, not multipliers, because cache-read ratios differ per model. The seed is the 2026-11-21 official table (Opus 5.5, Sonnet 5.5, Haiku 5.5 with its 100k tier, Fable 5.2 and older models). `~/.claude/usage/prices.json` merges over the seed per model id: a model in the override uses the override's prices, every other model keeps the seed's. The output names both table versions. An override entry that leaves out a seed `long_prompt` tier keeps the seed's tier, and a model id not in the seed is noted. Prices must be finite and not negative. An invalid override is reported and the seed alone is used. The models mode (`add-usage-models-mode`) writes this file, so the merge keeps a partial file safe. Prompt = input + cache write + cache read. Model ids are matched exactly, then without a date suffix (`claude-haiku-4-5-20251001` matches `claude-haiku-4-5`). `prices.py` starts from `cost.py`'s logic.

### 7. Report flow

`report.py` takes `--days 30 --top 5 --runs 5` and prints JSON: per top skill, the trend aggregates, the last N runs and the outliers (most expensive, most `Unfinished:` lines, largest prompt), each with per-agent details. The skill then reads that JSON plus, for the selected runs only, the agents' final replies, and writes the drop and strengthen candidates. The numbers in the report come from the script; the model only writes the judgment and cites run ids.

### 8. Retention check

`report.py --retention` reads `cleanupPeriodDays` (unset means the Claude Code default of 30; an invalid value, 0 included, is one Claude Code reports as a settings error, counted as 30 here). A whole-number float such as 180.0 is valid. An unreadable settings file is reported and no offer is made. When the effective value is from 1 to 179 it sums transcript bytes per day over the files present, takes the average per active day and prints the estimate at 180 days. The skill shows it and asks with AskUserQuestion. On yes it writes the setting with a JSON load, update, fsync and atomic replace that keeps every other key, through a symlinked settings file to its target. It refuses a value below 1 and a settings file that is not a JSON object. The check runs on every invocation, before the mode question's result is used, and costs one stat pass.

### 9. Tests

Stdlib `unittest`, run with `python3 -m unittest discover -s tests` from the skill folder. Python 3.9 is the floor, the macOS system version; tests also run under uv's 3.9. Synthetic fixtures under `tests/fixtures/` only, never real transcripts. Cases: split response, growing first-line usage, ids shared by two session files, `<synthetic>` lines, agent with and without meta, nested agent via `parentAgentId`, attribution by field and by fallback, unattributed lines inside a run, a task notification inside a run, `/clear` in the fallback, two runs in one session, Haiku above and below 100k, a dated model id, override merge and unpriced model, missing `cache_creation` dict, truncated line, trends and outliers, `Unfinished:` n/a, retention estimate, `cleanupPeriodDays` 0 and settings write on a temp home. A regression fixture reproduces `cost.py`'s run D numbers.

## Risks / Trade-offs

- [Transcript format drift] → tolerant parsing reports skipped lines; the fallback run rule covers versions without `attributionSkill`. A silent change in meaning is not detectable.
- [Short history] → the report only sees transcripts still on disk. The retention check makes this visible and offers 180 days.
- [Estimate gap] → compaction summaries and some side calls are not assistant lines, so estimates can be 7 to 12% low. The report says "estimate".
- [Run boundary heuristic] → a user prompt typed in the middle of a skill run (for example an answer typed as a prompt) splits it. Accepted; the deep read shows such splits. Background agent notifications do not split a run.
- [Unknown built-in commands] → a new built-in command without `:` and without skill lines could be read as a skill in the fallback. The fallback only matters for old transcripts.
- [Settings write] → the skill edits a user file. Mitigated by asking first and preserving all other keys.
- [Drop candidates are judgment] → each candidate cites its runs, and applying one needs an OpenSpec change and a benchmark.

## Migration Plan

None. `add-usage-collection` was never built, so nothing is installed to migrate. Its folder is deleted in the same commit as this change.

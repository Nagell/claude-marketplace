# Proposal

## Why

Model and effort choices for agents are made on anecdotes. Claude Code writes every request's token usage into local transcripts, but nothing turns that into a per-day record of what ran and what it cost. Transcripts are swept after a retention period, so the history is lost unless something copies it. Summing the raw lines is also wrong: one API response is written as several lines, and cache reads dwarf every other token class.

## What Changes

- A collector in plugin `base` reads session transcripts incrementally and writes a durable dataset plus one fixed-format Markdown file per day, both under `~/.claude/usage/` (never in a repo).
- A `SessionStart` hook returns at once and starts the collector as a detached background job. No scheduler, no LLM in the daily run.
- Multi-day, resumed and compacted sessions are attributed per message to the local calendar day. Subagent transcripts are tracked and linked to their parent.
- The collector validates the transcript shape it relies on and writes a status file. A problem is surfaced in the next session through `SessionStart` `additionalContext`.
- An optional command (`/usage-investigate`) starts a background agent that investigates a reported problem and writes a findings file.
- An on-demand skill (`usage-report`) re-collects a day and shows its file.
- A seed price table ships with the plugin so estimated USD can be shown. Tokens stay the source of truth.

## Capabilities

### New Capabilities

- `usage-collection`: incremental transcript scanning, ledger, attribution rule, dedupe, dataset, price table, SessionStart trigger, platform support.
- `usage-report`: fixed-format daily Markdown file and the on-demand skill that re-collects and shows a day.
- `usage-health`: schema validation, status file, escalation into the next session, optional investigation command.

### Modified Capabilities

None.

## Impact

- `plugins/base/hooks/hooks.json`: new `SessionStart` entry. New hook script beside the existing ones.
- `plugins/base/skills/usage-report/` (collector script, seed prices, tests, skill) and `plugins/base/skills/usage-investigate/`.
- `plugins/base/README.md` and a note on transcript retention. Release: `feat(base)`, minor bump.
- Runtime: python3 (stdlib only) must exist. Writes only under `~/.claude/usage/`.
- Because `base` is installed by everyone, the hook has an off switch (`CLAUDE_USAGE_COLLECT=0`).
- Change `add-model-guidance` depends on this change (dataset, price table, per-agent rows).

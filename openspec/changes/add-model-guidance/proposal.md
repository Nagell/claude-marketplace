# Proposal

## Why

Which model and effort to use for which task is decided today from price lists and single experiments. New models ship in groups every few months, and the right answer is rarely "switch everything": an older or cheaper model is often good enough for one task type and not for another. One recent case: nine Opus review agents missed a high-severity bug that a single Haiku max-effort agent found at about a fifth of the cost. That is one run, not evidence. The user needs current prices, independent benchmark data, their own real usage and a repeatable local test in one place, ending in a small rule change they approve.

## What Changes

- One skill, `model-guidance`, run by the user when new models ship (every few months). It is the only new skill; there is no separate pricing skill.
- It fetches current prices from Anthropic's official pricing page and cross-checks them with the `claude-api` skill.
- It fetches intelligence and coding-agent benchmark data per model and effort from Artificial Analysis and other independent sources, kept in a small source registry.
- It reads the usage dataset from `add-usage-collection` for real usage and cost by task type.
- It runs a small repeatable benchmark: cases stored under `~/.claude/model-bench/`, run per model and effort, scored against an answer key, priced from real transcripts. First case: a code review of a hooks and browser-skill snapshot with 14 known bugs.
- It proposes a split guidance table (task type to model@effort) as a diff to `~/.claude/CLAUDE.md` and `plugins/base/CLAUDE.md`, applied only after the user approves.

## Capabilities

### New Capabilities

- `model-guidance`: the skill's workflow: price refresh, external evidence, usage by task type, the split table, evidence rules, approval and the diff to CLAUDE.md files.
- `model-benchmark`: benchmark case storage, running a case per model and effort, scoring against a key, real cost per run, comparing runs.

### Modified Capabilities

None.

## Impact

- New skill directory `plugins/base/skills/model-guidance/` (skill, source registry, helper scripts, format reference). Frontmatter `dependencies: [usage-report]`.
- Reads and writes `~/.claude/usage/prices.json` (the user price override introduced by `add-usage-collection`). Writes `~/.claude/model-bench/` and `~/.claude/usage/guidance-log.md`.
- Edits `~/.claude/CLAUDE.md` and `plugins/base/CLAUDE.md`, only after approval of a shown diff.
- Network: the official pricing page and the benchmark sources. Benchmark runs cost real tokens and plan-window time, so each run needs approval.
- **Depends on `add-usage-collection`**: it needs the dataset, the price table format, per-agent rows and the `usage-report` skill. Implement and merge that change first.

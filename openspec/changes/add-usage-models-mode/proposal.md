# Proposal

## Why

Model and effort choices per task are made from price lists and single runs. New models ship every few months, and the right answer is rarely "switch everything". The local review benchmark already shows the gap: Haiku 5.5 max with small slices caught 13 of 14 key bugs at $0.39 per caught bug, and Opus 5.5 medium caught 9 at $0.78. That evidence lives in a folder, not in the rules the user follows. This change replaces the planned `model-guidance` skill (`add-model-guidance`) with a `models` mode in the `usage` skill, so it reads usage through the same scanner and prices.

## What Changes

- The `usage` skill's mode question offers `models` as a working mode.
- Prices: the mode checks the seed and override prices against Anthropic's pricing page and the `claude-api` skill. Changes go to `~/.claude/usage/prices.json` after the user's yes.
- External data: Artificial Analysis gives score, cost to run the index and time per task per model and effort, for Claude models and as reference points for other vendors (Kimi, GPT, Gemini). A free key (`AA_API_KEY`) covers score and cost; time per task and coding-agent rows come from the page data. Without a key the skill asks for one, then falls back to the page. Other vendors are never run.
- Ranking is by real cost per caught key bug and wall time per task from the local benchmark. Artificial Analysis cost is shown as "cost per index point". Token price is only a column.
- Local benchmark: cases under `~/.claude/model-bench/<case>/`, with brief templates and one `slices.json` per setup. Every result records a setup id, and results are compared only within one setup. Only new models run; stored results of older models are reused. At most 2 efforts per new model, 1 run each, a repeat only when the result is within 1 to 2 key bugs of the current model. A cost estimate and a user-approved cap come before any run, and each agent call gets the remaining cap as a hard budget. The checker is Opus 5.5 at medium, fixed per case.
- New cases: report mode's top skills become case suggestions. A case is added only with the user's yes and an answer key built from a merged fix.
- Output: a short `## Models` list by task, proposed as one diff to `~/.claude/CLAUDE.md` and `plugins/base/CLAUDE.md` (kept identical), applied only on the user's yes. No table and no report file.

## Capabilities

### New Capabilities

- `usage-models`: the `models` mode: price check, external data, benchmark policy and runs, case suggestions, ranking and the CLAUDE.md proposal.

### Modified Capabilities

- `usage-report`: the "Models mode not available yet" requirement from `add-usage-skill` becomes "Models mode available".

## Impact

- `plugins/base/skills/usage/`: SKILL.md gains the models flow; new `scripts/models.py`, `scripts/bench.py`, `sources.json` and tests. Reuses `scan.py`, `summarize_agent` and `prices.py`. No dataset.
- Writes `~/.claude/usage/prices.json`, `~/.claude/model-bench/` and, after approval, `~/.claude/CLAUDE.md` and `plugins/base/CLAUDE.md`.
- Network: the pricing page and Artificial Analysis (a free `AA_API_KEY` for the API, plus the web page). Benchmark runs spend real tokens and plan window.
- Depends on `add-usage-skill`: implement and merge it first, and archive it (or sync its specs) before this change is archived. `add-model-guidance` is deleted.
- `improve-review-mr` task 11.1 records a setup id for its rerun, so its rows join the same case as a new setup.
- Release: `feat(base)`, minor bump.

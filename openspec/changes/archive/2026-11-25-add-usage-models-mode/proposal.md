# Proposal

## Why

Model and effort choices per task are made from price lists and single runs. New models ship every few months, and the right answer is rarely "switch everything". The local review benchmark already shows the gap: with an older review-mr brief (commit `c3f54be`) and 7 hand-cut slices, Haiku 5.5 max caught 12 of 14 key bugs strict and 2 partly (13 with partials at half), all 4 highs, for $11.59 with an Opus 5.5 medium refuter (run I). That evidence lives in a folder outside the repo, not in the rules the user follows. This change replaces the planned `model-guidance` skill (`add-model-guidance`) with a `models` mode in the `usage` skill, so it reads usage through the same scanner and prices.

## What Changes

- The `usage` skill's mode question offers `models` as a working mode.
- Prices: the mode checks the seed and override prices against Anthropic's pricing page and the `claude-api` skill. Changes go to `~/.claude/usage/prices.json` after the user's yes.
- External data: Artificial Analysis gives score, cost to run the index and time per task per model and effort, for Claude models and as reference points for other vendors (Kimi, GPT, Gemini). A free key (`AA_API_KEY`) covers score and cost; time per task and coding-agent rows come from the page data. Without a key the skill asks for one, then falls back to the page. Other vendors are never run.
- Ranking is by real cost per caught key bug and wall time per task from the local benchmark. Artificial Analysis cost is shown as "cost per index point". Token price is only a column.
- Local benchmark: cases live in the repo under `plugins/base/skills/usage/references/bench/<case>/`, each with a snapshot, a provenance file, a self-contained answer key, brief templates, setup files, `results.json` and `RESULTS.md`. A setup is review-mr's brief version plus its size-based slicing rule (about 400 lines per slice, hard limit about 700). Every result records a setup id, and results are compared only within one setup. The first case starts with one setup, `review-mr-v1`: review-mr's current slice brief and size rule. Runs B to I stay in RESULTS.md as history and are not ranked; run I is the reference point for v1's first baseline run, which runs on the PR branch before merge. Only new models run; stored results of older models are reused. At most 2 efforts per new model, 1 run each, a repeat only when the result is within 1 to 2 key bugs of the current model. A cost estimate and a user-approved cap come before any run, and each agent call gets the remaining cap as a hard budget. The checker is Opus 5.5 at medium, pinned in the case's checker brief. Run outputs and raw external fetches go to `~/.claude/model-bench/`.
- The scanner leaves out benchmark sessions (custom title starting with `bench-`), so report mode and the models mode's usage never count them.
- New cases: report mode's top skills become case suggestions. A case is added only with the user's yes and an answer key built from a merged fix.
- Output: a short `## Models` list by task, proposed as one diff to two places: `~/.claude/CLAUDE.md` and `plugins/base/CLAUDE.md` (kept identical), and review-mr's fallback role table in `plugins/base/skills/review-mr/SKILL.md`. Applied only on the user's yes. review-mr reads the `- Review` lines when present; the table covers a machine without them. No output table and no report file.

## Capabilities

### New Capabilities

- `usage-models`: the `models` mode: price check, external data, benchmark cases, policy and runs, case suggestions, ranking and the CLAUDE.md and role table proposal.

### Modified Capabilities

- `usage-report`: the "Models mode not available yet" requirement becomes "Models mode available".
- `usage-scanner`: sessions with a `bench-` custom title are left out of every aggregate.

## Impact

- `plugins/base/skills/usage/`: SKILL.md gains the models flow; new `scripts/models.py`, `scripts/bench.py`, `sources.json`, the first case under `references/bench/review-hooks-browser/` and tests. `scan.py` gains the `bench-` filter. Reuses `summarize_agent`, `prices.py` and `report.py`'s `report()` and `trends()`. No dataset.
- The repo is public, so the answer key and snapshot become public. The key comes from public fix commits, so nothing new is exposed.
- Writes `~/.claude/usage/prices.json`, `~/.claude/model-bench/` (run outputs, raw fetches), the case's `results.json` and `RESULTS.md` in the repo and, after approval, `~/.claude/CLAUDE.md`, `plugins/base/CLAUDE.md` and the role table in `plugins/base/skills/review-mr/SKILL.md`.
- Network: the pricing page and Artificial Analysis (a free `AA_API_KEY` for the API, plus the web page). Benchmark runs spend real tokens and plan window.
- Met prerequisites: `add-usage-skill` was merged and archived (`2026-11-24-add-usage-skill`), and `improve-review-mr` task 11.1 was done (runs G, H and I exist).
- Release: `feat(base)`, minor bump.

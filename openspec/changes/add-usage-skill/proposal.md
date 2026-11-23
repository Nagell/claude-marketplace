# Proposal

## Why

Model and effort choices for skills and their agents are made on anecdotes. Claude Code already writes every request's token usage into local transcripts, but nothing reads them per skill run. Summing raw lines is also wrong: one response is written as several lines, and Haiku 5.5 charges a request over 100k prompt tokens at a higher tier. This change replaces `add-usage-collection`. A daily collector was more machinery than the question needs, so this change reads transcripts on demand instead.

## What Changes

- New user-invoked skill `usage` in plugin `base` (`plugins/base/skills/usage/`). It asks which mode to run: `report` (recommended) or `models`. `models` is shown as not available yet. A later change, `add-usage-models-mode`, adds it.
- A stdlib Python scanner reads transcripts on demand, finds skill runs and their agents, dedupes by `message.id` across all files and prices each request. It is the single copy of the price and dedupe logic. No other skill prices requests.
- A seed price table ships with the plugin. A user file at `~/.claude/usage/prices.json` merges over it per model id. No network.
- `report` picks the top skills by spend in a window (default 5) and shows script-built trends for them. The model then reads the per-agent details of recent runs and outliers and names agents to drop or to strengthen. Recommendations are output only.
- `report` is the only place that prices `review-mr` runs. When a session's scratchpad (under `/tmp/claude-<uid>`, not `~/.claude`) still holds `review-mr`'s `run.json`, the report labels that run's agents by role and slice and shows cost and unique surviving findings per role.
- Every run checks transcript retention (`cleanupPeriodDays`) and offers to set 180 days when it is from 1 to 179 or unset. 0 means no sweep, so no offer. Nothing changes without the user's yes.
- Removed from the earlier plan: hooks, background job, ledger, daily Markdown files, session error notes, re-runs and parse-failure thresholds.

## Capabilities

### New Capabilities

- `usage-scanner`: reading transcripts, finding skill runs and agents, dedupe, prompt tier, price table and per-request cost. Shared by every mode and by other skills.
- `usage-report`: the `usage` skill entry, mode choice, top skills, trends, deep read, recommendations and the retention check.

### Modified Capabilities

None.

## Impact

- New `plugins/base/skills/usage/` (SKILL.md, `scripts/`, seed `prices.json`, `tests/`). `plugins/base/README.md` gains a section, a skill table row and the Python 3 requirement; the root `README.md` base row names it. Release: `feat(base)`, minor bump.
- Runtime: python3 3.9 or newer, stdlib only. Linux, macOS and WSL. Reads `~/.claude/projects/`, `~/.claude/settings.json` and `run.json` files in the session scratchpads. Writes only `~/.claude/settings.json`, and only after the user agrees. Reports are printed, never written into a repo.
- `review-mr`: reads nothing from this skill. `move-review-cost-to-usage` removed its own pricing; its `run.json` (agent ids, roles, slices, model, effort, finding sources) is input to the report.
- `add-usage-collection` is deleted. `add-usage-models-mode` builds the `models` mode on this change and replaces `add-model-guidance`.

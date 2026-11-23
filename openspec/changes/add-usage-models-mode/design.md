# Design

## Context

See proposal.md for why. This change builds on `add-usage-skill` and reuses the still-valid research of the deleted `add-model-guidance`.

- `add-usage-skill` ships `plugins/base/skills/usage/` with SKILL.md (mode question: `report (Recommended)`, then `models` marked not available), `scripts/scan.py` (transcripts, dedupe, runs, agents, `summarize_agent(path)`), `scripts/prices.py` (seed table, per-model override `~/.claude/usage/prices.json`, Haiku 100k tier) and `scripts/report.py` (top skills by spend, model and effort per skill, trends, outliers). Stdlib Python 3.9, `unittest`.
- Effort does not change per-token price. It changes token counts and tool calls, so effort effects come from measurement.
- The first case exists at `~/.claude/model-bench/review-hooks-browser/`: `snap/` (2,905 lines), `answer-key.md` (14 bugs from later fix commits), `brief.md`, `brief-D-addendum.md` (run D's lens), `checker-brief.md`, `refuter-brief.md`, `cost.py`, `runs/` (with `walltime.py`) and `RESULTS.md` with runs B to F. The case belongs to the `review-mr` skill.
- The stored briefs only work in the old session. `brief.md`, `checker-brief.md` and `refuter-brief.md` hardcode that session's scratchpad (`exp2/snap/`, `exp2-key/`) and transcript folder. `checker-brief.md` hardcodes "4 reports". `walltime.py` hardcodes one subagent folder. No slicing file exists: run D's 7 slices exist only as report names. A reboot can clear the scratchpad.
- RESULTS.md has no checker model or effort, no date for runs B to D and no hashes. B's over-100k share is "n/a" (Opus has a flat price). Wall time for B to E is active time with gaps over 5 minutes left out (`walltime.py`). F's 9.2 min is in the notes.
- Baseline from RESULTS.md (key caught strict, real cost, cost per caught key bug, slowest agent):

| Run | Setup | Caught | Cost | Per bug | Slowest |
|---|---|---|---|---|---|
| B | Opus 5.5 medium, 3 slices + cross-file | 6 | $6.38 | $1.06 | 8.9 min |
| C | Haiku 5.5 max, same slices | 7 | $3.34 | $0.48 | 23.1 min |
| D | Haiku 5.5 max, 7 small slices + lens | 13 | $5.08 | $0.39 | 23.7 min |
| E | Haiku 5.5 max, 3 slices + lens | 9 | $4.25 | $0.47 | 32.9 min |
| F | Opus 5.5 medium, 3 slices + lens | 9 | $6.99 | $0.78 | 9.2 min |

- Refuter test on run F: Opus medium gave the same verdicts as Opus high on 34 of 35 findings for 37% less ($1.74 vs $2.76). That is the reason for an Opus medium checker. Single sample.
- `improve-review-mr` task 11.1 reruns this case with a new brief and slicing rule. Its rows go to the same case under a new setup.
- The repo is public. Cases and keys stay under `~/.claude/model-bench/`.
- The user is on a subscription with a 5-hour window. Benchmark runs use it.
- Both `~/.claude/CLAUDE.md` and `plugins/base/CLAUDE.md` have a `## Models` section. review-mr reads its `- Review slices:`, `- Review refuters:` and `- Review with --fast:` lines when present, and falls back to the role table in its SKILL.md step 4.

## Goals / Non-Goals

**Goals:**

- Run every few months, when new models ship, and end in a short approved rule list.
- Spend benchmark money only on new models, with a cap the user sets.
- Rank by what a finished task costs and how long it takes, not by token price.

**Non-Goals:**

- Running other vendors' models. They are reference points only.
- A report file, a table output or a guidance log.
- Task type classification of all sessions. Tasks come from top skills and the existing cases.
- Re-running stored results, variance studies or three repeats per finalist.
- Plan-window measurement.
- A paid Artificial Analysis tier. The free key is enough.

## Decisions

### 1. Layout

```
plugins/base/skills/usage/
  SKILL.md              models flow added after the mode question
  sources.json          external source registry
  scripts/models.py     usage per skill, price check diff, AA fetch, ranking inputs (CLI, JSON out)
  scripts/bench.py      plan runs, cost estimate, cap check, run, store result (CLI)
  tests/                unittest + fixtures (saved pricing page, AA responses, AA page data, case folder)
```

Both scripts import `scan.py`, `prices.py` and `report.py` by path, as improve-review-mr's planned `run_cost.py` will. The model does judgment: reading footnotes, choosing tasks, writing the rule list. Scripts do the numbers. Rejected: a separate `model-guidance` skill (a second copy of usage reading and prices).

### 2. Usage

`models.py --usage` calls `report.py`'s per-skill aggregate and prints, per top skill, the model and effort used most and the cost per run. Each case names its skill in `results.json` (`"skill": "review-mr"` for the first case), so the benchmark plan can find that skill's most used effort. Sessions tagged as benchmark runs (decision 7) are left out.

### 3. Prices

Verified on 2026-11-22: `https://platform.claude.com/docs/en/about-claude/pricing.md` returns a 40 KB markdown table (the HTML is 800 KB). The URL is stored in `sources.json`. One row per model: input, 5-minute and 1-hour cache write, cache read, output, with footnote markers for tiers. Rows use display names such as "Claude Opus 5.5" or "Claude Opus 4.1 ([retired, ...])". `prices.json` is keyed by model id.

`models.py --prices` fetches and parses the page. It maps each display name to a model id (lowercase, spaces to dashes, `claude-` prefix) and keeps a retired marker as a flag. It then diffs the result against the active table (seed plus override). The model reads the footnotes (long-prompt tier, retired models) and invokes the `claude-api` skill once to cross-check the mapped ids and prices. The page wins; any difference is shown. On the user's yes, changed models are written to `~/.claude/usage/prices.json` with a JSON load, update and atomic replace. The plugin seed is never edited, because a plugin update would replace it.

### 4. External data and registry

`sources.json` stores URL, contribution, read method, stability and verified date per source. Checked on 2026-11-22:

| Source | Contributes | Read | Stability |
|---|---|---|---|
| Anthropic pricing, https://platform.claude.com/docs/en/about-claude/pricing.md | Token prices per model | Markdown fetch | Stable |
| Artificial Analysis models, https://artificialanalysis.ai/models | Intelligence Index and cost to run the index per model and effort, all vendors; time per task | Free key: `GET /api/v2/language/models/free` with `x-api-key` (attribution required, 100 requests per window). Time per task from the page's embedded data. `GET /api/v2/language/models` is Pro+ only | API versioned. Static HTML lists Sonnet 5.5 at low to max, Opus 5.5 and Haiku 5.5 only at max |
| Artificial Analysis Coding Agent Index, https://artificialanalysis.ai/agents/coding | One row per agent, model and effort, with score, cost and time per task | Page embedded data. API `/api/v2/language/agents/coding` is Pro+ only | New; verify per run |
| Artificial Analysis Terminal-Bench 4.0 | 66 terminal tasks, pass@1 over three repeats | Page embedded data | As above |
| Terminal-Bench leaderboard, https://www.tbench.ai/leaderboard | Model with effort, resolution rate, tokens and cost | Static HTML table | Stable, no key; mostly max effort |

Kept for method only, not fetched: GitHub ReviewBench, Martian Code Review Bench (JavaScript only), CR-Bench, MCR-Bench, SWR-Bench. Checked and not used: Aider, Scale SWE-Bench Pro, SWE-rebench, OpenRouter rankings, LMArena, LiveBench, swebench.com, Snorkel, Epoch AI (stale or no effort levels).

No live leaderboard covers code review at model and effort level for current Claude models. That gap is why the local benchmark exists.

Key: `models.py --external` reads `AA_API_KEY`, the name Artificial Analysis uses in its docs. When it is not set, the skill first asks the user for a key through AskUserQuestion. The question explains that Artificial Analysis gives a free API key after a free sign-up on artificialanalysis.ai, and that a pasted key is used for this run only and not stored. If the user has no key, the mode falls back to the page. API calls without a key return 401. The MCP server also needs sign-in and is not used.

With a free key, `/language/models/free` gives the index score and cost to run per model and effort. Time per task and the coding-agent rows come from the page's embedded data. The pages are JavaScript rendered, so the parser reads the embedded JSON, tested against a saved fixture. The mode calls the Pro+ endpoints once; a 403 is expected on a free key, is reported as "free tier" and is not an error. The mode prints which path it used.

Rows carry vendor, model, effort, metric, URL and date. Raw fetches go to `~/.claude/model-bench/external/<date>/` with a hash, so a layout change is noticed. A failing source is named and skipped. Rows for other vendors are tagged `reference` and never reach the run plan or the rule list.

### 5. Ranking

Per task, candidates are ranked by cost per finished task, then wall time per task. These come from the local benchmark: real cost per caught key bug and slowest-agent wall time, compared only within one setup (decision 9). For a pair without a local result, the external inputs are AA's cost to run divided by its score and AA's time per task. That ratio is labelled "cost per index point": AA's cost is for the whole index run, so it is not a cost per task. Local and external rows are shown in separate groups and never ranked against each other. Token prices from `prices.py` are shown as a column for context. Rejected: ranking by token price (run F: Opus had no tier and fewer requests, yet cost twice D per caught bug).

### 6. Benchmark policy

`bench.py plan <case> [--setup <id>]` reads the case's `results.json`. The default setup is the one of the current model's result. It lists models without a result in that setup. Per new model it picks at most 2 efforts:

1. The effort with the lowest cost per index point on Artificial Analysis.
2. The effort used most for the case's skill in report mode's data (most frequent `effort` of that skill's agents in the scan window).

Equal picks collapse to 1. Each pick runs once. After scoring, a repeat is proposed only when the result is within 2 key bugs of the current model for that task.

The current model for a task is the model and effort named in the `## Models` line for that task, once that section exists. Before that, it is the best-ranked stored result for the case in the chosen setup.

Cost estimate per run: the stored cost of the closest older run in the same setup, scaled by the new model's price relative to that run's model from `prices.py` (Haiku tier included at the stored over-100k share). The review case costs about $4 to $7 per run. `bench.py` prints the plan with estimates and total, and the skill asks for a cap through AskUserQuestion. `bench.py run --cap <usd>` stops before a run whose estimate would pass the remaining cap. Each `claude -p` call also gets `--max-budget-usd` set to the remaining cap, so a run that overspends is stopped by the CLI.

### 7. Runner

`claude -p --model <id> --effort <level> --output-format json` in a fresh `mktemp -d` folder per agent, because the Agent tool offers only aliases and older models need full ids. The snapshot is copied in without the key, and the folder is removed after the run.

The briefs need Bash: `brief.md` tells reviewers to run scripts against stubs in /tmp. So the tool flags are `--tools "Read,Grep,Glob,Bash" --permission-mode dontAsk`, plus `--disallowedTools` deny rules for the key paths: `~/.claude/model-bench/` and any other copy of the key, such as the old scratchpad `exp2-key/`. The temp folder only keeps the key out of the working folder; the deny rules stop reads by absolute path. Task 3.2's dry run confirms the exact flags and whether `--bare` (no plugin hooks such as safety-guards) is wanted.

Each call gets `-n bench-<case>-<run>`, so report mode can leave benchmark sessions out. `--no-session-persistence` is not used, because `summarize_agent` needs the transcript. `bench.py` finds the transcript at `~/.claude/projects/<slug of the temp folder path>/<session_id>.jsonl`, with `session_id` from the JSON output. Real cost comes from `summarize_agent` on that transcript; the JSON output's cost is a cross-check. Wall time per agent is active time with gaps over 5 minutes left out, as `walltime.py` measured runs B to E.

The brief and the slices come from the run's setup (decision 9), filled in with the temp folder paths.

### 8. Checker

Opus 5.5 at medium, fixed per case, with the case's checker brief template and `answer-key.md`. It writes caught, partial or missed per key item and real, false or unsettled per other finding. `results.json` records the checker model and effort and the checker brief and key hashes per run, so a change is visible.

### 9. Case storage and setups

The existing case folder keeps its files. A task turns `brief.md`, `brief-D-addendum.md`, `checker-brief.md` and `refuter-brief.md` into templates with path placeholders (`{snap}`, `{reports}`, `{key}` and a report count). Each setup gets `setups/<setup>/slices.json`: setup name, version, file list per slice, brief template and addendum. The first case starts with three setups, all at version 1:

- `3-slices-xfile` (runs B and C): 3 slices plus a cross-file agent, no lens.
- `7-slices-lens` (run D): run D's 7 slices and `brief-D-addendum.md`.
- `3-slices-lens` (runs E and F): 3 slices plus `brief-D-addendum.md` (both runs read it; their spawn prompts are in the session transcript).

A setup id is the setup name and version plus the hashes of its brief, addendum and `slices.json`. Results are compared only within one setup, so runs B to F stay valid next to later runs. A changed brief or slicing is a new setup or version, not an edit. If a hash no longer matches a stored setup id, or the checker, checker brief, key or snapshot changed, the affected results are marked not comparable and the user decides.

A new `results.json` per case holds the case's `skill` and one entry per run: id, model, effort, setup id, caught strict and with partials, real cost, slowest-agent minutes, wall-time method, over-100k share, checker, checker brief hash, key hash, date. It is seeded from every RESULTS.md row present at apply time, including rows that improve-review-mr 11.1 added. For seeded rows B to F, `checker` and missing dates are `null`, B's over-100k share is `null`, and the hashes are taken from the templates at seeding as the baseline. RESULTS.md stays as the human log and gets one line per new run.

New cases: the mode lists report mode's top skills without a case as suggestions. A case is added only on the user's yes and only from a merged fix: the snapshot is the fix's parent, the key is the bugs the fix closed. Without a merged fix, no case.

### 10. Output

The mode prints a `## Models` list, one line per task, for example:

```
## Models

- Coding: Opus 5.5 medium
- Review slices: Haiku 5.5 max (about 7 agents, ~400 lines each)
- Review refuters: Opus 5.5 medium (every severity)
- Review with --fast: Opus 5.5 medium slices (faster, finds less)
```

Only tasks with evidence get a line; others keep their current line. It shows one diff over two places and asks once. On yes it writes the same section into `~/.claude/CLAUDE.md` and `plugins/base/CLAUDE.md`, replacing an existing `## Models` section, else appending one, and updates the rows of review-mr's fallback role table (`plugins/base/skills/review-mr/SKILL.md`, step 4) that the `- Review` lines cover. review-mr reads those lines when present, so the table only matters for a machine without them; keeping it in line stops the two from drifting. Rejected: different content per file (the user keeps them identical), a report or table as output (the user wants usable data only), leaving the role table alone (it would go stale after the first model change).

## Risks / Trade-offs

- [One case, 14 bugs] → each bug moves recall by 7 points; differences under 2 bugs trigger a repeat, not a rule.
- [Single runs] → accepted to keep cost down; the repeat rule covers close calls.
- [AA effort coverage] → Opus 5.5 and Haiku 5.5 appear only at max. Then the AA pick is max and the real-use pick covers the other effort.
- [AA free tier] → no time per task through the free API; the page parse fills it and can break. The raw fetch hash and the saved fixture show a layout change.
- [Contamination] → the key comes from public fix commits; newer models may have seen them.
- [Checker mis-scores] → same checker for every run; the user can spot check against the key.
- [Agent with Bash] → it could read the key by absolute path; deny rules block the key paths, and the dry run checks it.
- [Scraping breaks] → registry with verified dates, raw fetches saved, failing sources skipped.
- [Estimate off] → `--max-budget-usd` stops an overspending run, and the cap stops further runs; actual cost is shown after each run.

## Migration Plan

None. `add-model-guidance` was never built. Its folder deletion is staged in the worktree and goes into the same commit as this change.

Archive order: `add-usage-skill` is archived (or its specs synced) before this change is archived, because the REMOVED delta for "Models mode not available yet" needs that requirement in `openspec/specs/`.

## Open Questions

- Answered on 2026-11-22: Artificial Analysis lists Sonnet 5.5 at low, medium, high, xhigh and max ("Default Fallback" variants). Opus 5.5 and Haiku 5.5 appear only at max. Task 2.2 checks this again against the free API and the page data.

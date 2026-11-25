# Design

## Context

See proposal.md for why. This change builds on `add-usage-skill` (merged and archived as `2026-11-24-add-usage-skill`) and reuses the still-valid research of the deleted `add-model-guidance`.

- `add-usage-skill` shipped `plugins/base/skills/usage/` with SKILL.md (mode question: `report (Recommended)`, then `models` marked not available), `scripts/scan.py` (transcripts, dedupe, runs, agents, `summarize_agent(path)`), `scripts/prices.py` (seed table, per-model override `~/.claude/usage/prices.json`, Haiku 100k tier) and `scripts/report.py` (top skills by spend, model and effort per skill, trends, outliers). Stdlib Python 3.9, `unittest`.
- Effort does not change per-token price. It changes token counts and tool calls, so effort effects come from measurement.
- The first case exists outside the repo at `~/.claude/model-bench/review-hooks-browser/`: `snap/` (20 files, 2,905 lines), `answer-key.md` (14 bugs from later fix commits), `brief.md`, `brief-D-addendum.md` (run D's lens), `checker-brief.md`, `refuter-brief.md`, `cost.py`, `runs/` (with `walltime.py` and `check-B.md` to `check-I.md`) and `RESULTS.md` with runs B to I. The case belongs to the `review-mr` skill.
- The stored briefs only work in the old session. `brief.md`, `checker-brief.md` and `refuter-brief.md` hardcode that session's scratchpad (`exp2/snap/`, `exp2-key/`) and transcript folder. `checker-brief.md` hardcodes "4 reports" and names no checker model. `answer-key.md` points into the source repo instead of quoting the fixes. `walltime.py` hardcodes one subagent folder. A reboot can clear the scratchpad.
- Snapshot sources: the browser files match commit `0dc4655`, the parent of fix `05e0493`. The source commit of the 5 hook files is not recorded yet.
- RESULTS.md has no checker model or effort, no date for runs B to D and no hashes. Runs B to H used different briefs and slicings (3 slices with or without a cross-file agent, D's 7 named slices, PR #251's first brief). They are history, not comparable setups.
- Reference point: run I. Haiku 5.5 max, the older slice brief from commit `c3f54be` (PR #251's brief with D's lens and context wording restored), run D's 7 hand-cut slices plus run-it, Opus 5.5 medium refuter. 12 key bugs caught strict, 2 partial, 0 missed of 14 (13 with partials at half), all 4 highs. $7.89, $11.59 with the refuter ($3.70). Slowest agent 26.9 min. Run I is not the baseline of `review-mr-v1`: v1 uses review-mr's current brief, which gained lines since `c3f54be` (commits `c7930ea`, `38eebcc`, `f8ce2b0`), and the size rule instead of hand-cut slices. Haiku 7-slice range of runs D, G and I: 10 to 13 strict of 14, all 4 highs.

- Refuter test on run F: Opus medium gave the same verdicts as Opus high on 34 of 35 findings for 37% less ($1.74 vs $2.76). That is the reason for an Opus medium checker. Single sample.
- `improve-review-mr` task 11.1 was done: it reran this case as runs G, H and I.
- The repo is public. The case moves into it so it survives reboots and new machines; the key comes from public fix commits, so moving it exposes nothing new. `~/.claude/model-bench/` keeps only run outputs and raw external fetches.
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
- `~/.claude/model-bench/pr-238/`. It is not a case and is left alone.
- Ranking runs B to H. They stay in RESULTS.md as history.

## Decisions

### 1. Layout

```
plugins/base/skills/usage/
  SKILL.md              models flow added after the mode question
  sources.json          external source registry
  scripts/models.py     usage per skill, price check diff, AA fetch, ranking inputs (CLI, JSON out)
  scripts/bench.py      plan runs, cost estimate, cap check, run, store result (CLI)
  references/bench/<case>/   snapshot, provenance, answer key, templates, setups, results (decision 9)
  tests/                unittest + fixtures (saved pricing page, AA responses, AA page data, case folder)
```

Both scripts import `scan.py`, `prices.py` and `report.py` by path. The model does judgment: reading footnotes, choosing tasks, writing the rule list. Scripts do the numbers. Rejected: a separate `model-guidance` skill (a second copy of usage reading and prices).

### 2. Usage

`models.py --usage` calls `report.py`'s `report()` for the top skills and their runs and `trends()` for the per-model and per-effort split, and prints, per top skill, the model and effort used most and the cost per run. Each case names its skill in `results.json` (`"skill": "review-mr"` for the first case), so the benchmark plan can find that skill's most used effort. Benchmark sessions (decision 7) are left out by the scanner, so both modes skip them.

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

Rows carry vendor, model, effort, metric, URL and date. Raw fetches go to `~/.claude/model-bench/external/<date>/` (outside the repo) with a hash, so a layout change is noticed. A failing source is named and skipped. Rows for other vendors are tagged `reference` and never reach the run plan or the rule list.

### 5. Ranking

Per task, candidates are ranked by cost per finished task, then wall time per task. These come from the local benchmark: real cost per caught key bug and slowest-agent wall time, compared only within one setup (decision 9). For a pair without a local result, the external inputs are AA's cost to run divided by its score and AA's time per task. That ratio is labelled "cost per index point": AA's cost is for the whole index run, so it is not a cost per task. Local and external rows are shown in separate groups and never ranked against each other. Token prices from `prices.py` are shown as a column for context. Rejected: ranking by token price (run F: Opus had no tier and fewer requests, yet cost twice D per caught bug).

### 6. Benchmark policy

`bench.py plan <case> [--setup <id>]` reads the case's `results.json`. The default setup is the one of the current model's result. It lists models without a result in that setup. Per new model it picks at most 2 efforts:

1. The effort with the lowest cost per index point among Artificial Analysis coding-agent rows. The models page is used only for max: a model listed there at max only prints "Effort not listed" for its lower efforts.
2. The effort used most for the case's skill in report mode's data (most frequent `effort` of that skill's agents in the scan window).

Equal picks collapse to 1. Each pick runs once. After scoring, a repeat is proposed only when the result is within 2 key bugs of the current model for that task.

The current model for a task is the model and effort named in the `## Models` line for that task, once that section exists. Before that, it is the best-ranked stored result for the case in the chosen setup.

Cost estimate per run: the stored cost of the closest older run in the same setup, scaled by the new model's price relative to that run's model from `prices.py` (Haiku tier included at the stored over-100k share). With no stored run in the setup, the estimate comes from the closest history run of the case (an entry with no setup id, else RESULTS.md's history rows, such as run I) and is marked `from_history`; with none at all, the run stops with "no estimate". The review case costs about $8 per run, $12 with the refuter (run I, older setup). `bench.py` prints the plan with estimates and total, and the skill asks for a cap through AskUserQuestion. `bench.py run --cap <usd>` stops before a run whose estimate would pass the remaining cap. Each `claude -p` call also gets `--max-budget-usd` set to the remaining cap, so a run that overspends is stopped by the CLI.

### 7. Runner

`claude -p --model <id> --effort <level> --output-format json` in a fresh `mktemp -d` folder per agent, because the Agent tool offers only aliases and older models need full ids. The snapshot is copied in without the key, and the folder is removed after the run.

The briefs need Bash: review-mr's brief tells reviewers to run scripts against stubs in /tmp. So the tool flags are `--tools "Read,Grep,Glob,Bash" --permission-mode dontAsk`, plus `--disallowedTools` deny rules for every copy of the key: the case folder in the repo checkout, the installed plugin copy under `~/.claude/plugins/`, `~/.claude/model-bench/` and the old scratchpad `exp2-key/`. The temp folder only keeps the key out of the working folder; the deny rules stop reads by absolute path. Each call also gets `--strict-mcp-config` (no MCP servers) and `--settings '{"enabledPlugins": {...}}'` that switches off every plugin enabled in `~/.claude/settings.json` except base, so the start context is close to a real review subagent's (dry run: about 10.5k input tokens on the first request, about 410k before the trim). `--bare` is not used: it needs `ANTHROPIC_API_KEY`, and runs use the subscription login.

Final flags, confirmed by task 3.3's dry run: `claude -p --model <id> --effort <level> --output-format json --tools "Read,Grep,Glob,Bash" --permission-mode dontAsk --strict-mcp-config --settings <plugins off> --disallowedTools <key deny rules> -n bench-<case>-<run>-<role> --max-budget-usd <remaining cap>`.

Each call gets `-n bench-<case>-<run>`, which writes a `{"type":"custom-title","customTitle":"bench-..."}` line, so the scanner can leave benchmark sessions out. `--no-session-persistence` is not used, because `summarize_agent` needs the transcript. `bench.py` finds the transcript at `~/.claude/projects/<slug of the temp folder path>/<session_id>.jsonl`, with `session_id` from the JSON output. Real cost comes from `summarize_agent` on that transcript; the JSON output's cost is a cross-check. Wall time per agent is active time with gaps over 5 minutes left out. `bench.py` reimplements that rule from `runs/walltime.py`, which hardcodes one subagent folder, and applies it to the run's own transcripts.

The brief and the slices come from the run's setup (decision 9): the brief template filled in with the temp folder paths, and slices cut from the snapshot by the setup's size rule.

### 8. Checker

Opus 5.5 at medium, pinned in the case's checker brief template and used with the case's `answer-key.md`. It writes caught, partial or missed per key item and real, false or unsettled per other finding. `results.json` records the checker model and effort and the checker brief and key hashes per run, so a change is visible.

### 9. Case storage and setups

Each case lives in the repo at `plugins/base/skills/usage/references/bench/<case>/`, so it does not depend on a session scratchpad or the source repo. The first case, `review-hooks-browser`, holds:

- `snap/`: the 20 snapshot files (2,905 lines), copied from the old folder.
- `provenance.md`: each snapshot file with its source commit. The browser files come from `0dc4655`, the parent of fix `05e0493`. The 5 hook files get their source commit at apply time, or "snapshot only" when none matches.
- `answer-key.md`: self-contained. Each of the 14 bugs has id, severity, mechanism, file and line in the snapshot, the fixing commit and the fix excerpt as a diff hunk.
- `checker-brief.md` and `refuter-brief.md`: templates with placeholders (`{snap}`, `{reports}`, `{key}`, `{report_count}`). The checker brief names Opus 5.5 medium as the checker.
- `setups/<setup>.json`: one file per setup.
- `results.json` and `RESULTS.md`: the result history, moved from the old folder.

A setup is review-mr's slice brief version plus its size-based slicing rule (review-mr SKILL.md step 2a: about 400 lines of whole files per slice, hard limit about 700), not a slice count. The setup file holds name, version, the brief template (review-mr's slice brief with placeholders), the size rule, the extra agents (run-it) and the refuter (Opus 5.5 medium). `bench.py` cuts the slices from the snapshot with the size rule at run time. The first case starts with one setup, `review-mr-v1`: review-mr's current slice brief (`plugins/base/skills/review-mr/references/agent-brief.md` at main) and its current size rule.

A setup id is the setup name and version plus the hashes of its brief template and setup file. Results are compared only within one setup. A later change to review-mr's brief or size rule is a new setup version, not an edit. If a hash no longer matches a stored setup id, or the checker, checker brief, key or snapshot changed, the affected results are marked not comparable and the user decides.

`results.json` holds the case's `skill` and one entry per run: id, model, effort, setup id, caught strict and with partials, real cost with and without the refuter, slowest-agent minutes, wall-time method, over-100k share, checker, checker brief hash, key hash, date. Each entry has a `status`: `complete`, or `incomplete` when the cap or an error cut the run, with the reason, the cost spent and which roles finished; an incomplete entry is never ranked and never the setup's baseline. It is seeded empty. The setup id's hashes are taken from the current templates at seeding, and missing values in later entries are `null`. Runs B to I stay in RESULTS.md as history and get no entry, so they are never ranked. The first complete `review-mr-v1` entry is the baseline run of task 7.1, compared against run I and the Haiku 7-slice range of runs D, G and I (10 to 13 strict of 14, all 4 highs). RESULTS.md gets one line per new run. `bench.py` writes results only to the case folder in a repo checkout, never to the installed plugin copy, which a plugin update replaces; the change reaches other machines through a commit.

The old briefs `brief.md` and `brief-D-addendum.md` belong to runs B to H. They are not carried into the case.

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

### 11. Apply-time choices

- Cost per caught bug uses the strict caught count, and the cost includes the refuter.
- Slices are packed in file path order.
- Each run's temp folder is a git repo: an empty base commit, then the snapshot as head.
- The checker's cost counts against the cap but not against the run's cost.
- Lines in a rule list that name no Claude model are dropped.

## Risks / Trade-offs

- [One case, 14 bugs] → each bug moves recall by 7 points; differences under 2 bugs trigger a repeat, not a rule.
- [Single runs] → accepted to keep cost down; the repeat rule covers close calls.
- [AA effort coverage] → Opus 5.5 and Haiku 5.5 appear only at max. Then the AA pick is max and the real-use pick covers the other effort.
- [AA free tier] → no time per task through the free API; the page parse fills it and can break. The raw fetch hash and the saved fixture show a layout change.
- [Contamination] → the key comes from public fix commits, and the case is now public in this repo; newer models may have seen both.
- [Checker mis-scores] → same checker for every run; the user can spot check against the key.
- [Agent with Bash] → it could read the key by absolute path, in the repo checkout or the installed plugin copy; deny rules block every key path, and the dry run checks it.
- [Scraping breaks] → registry with verified dates, raw fetches saved, failing sources skipped.
- [Estimate off] → `--max-budget-usd` stops an overspending run, and the cap stops further runs; actual cost is shown after each run.

## Migration Plan

The first case moves from `~/.claude/model-bench/review-hooks-browser/` into the repo (decision 9). The old folder keeps its `runs/` outputs; new run outputs go to `~/.claude/model-bench/<case>/runs/`.

`add-usage-skill` is already archived, so the REMOVED delta for "Models mode not available yet" finds that requirement in `openspec/specs/usage-report/`.

## Open Questions

None. The effort question is settled in decision 6: effort picks come from Artificial Analysis coding-agent rows (Sonnet 5.5 at low to max; Opus 5.5 and Haiku 5.5 only at max on the models page as of 2026-11-22).

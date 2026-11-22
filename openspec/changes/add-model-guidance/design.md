# Design

## Context

- Depends on `add-usage-collection`: dataset rows per day, session, agent, model, effort and prompt tier; the price table format (`prices.json`, seed in the plugin, user override in `~/.claude/usage/`); the `usage-report` skill and its collector.
- Effort does not change per-token price. It changes token counts and tool calls, so prices are stored per model and effort effects come from measurement. Haiku 5.5 prices a request over 100k prompt tokens at 5x, so "Haiku is a fifth of the cost" holds only while prompts stay short.
- Evidence so far is anecdotal: one nine-agent Opus review missed a high-severity bug that one Haiku max agent found. A larger Opus medium vs Haiku max experiment on a 2,900-line snapshot produced an answer key of 14 bugs (5 in hooks, 7 in browser scripts, 2 in browser docs, taken from later fix commits). The snapshot and key exist as plain files from that experiment; their current location is a session scratchpad and must be moved to durable storage before it is cleaned (see tasks).
- The repo is public. Cases and keys must not go in it.
- The user is on a subscription with a 5-hour window, sometimes with paid overage. Benchmark runs consume it.
- Existing CLAUDE.md files: `~/.claude/CLAUDE.md` (personal) and `plugins/base/CLAUDE.md` (template others copy). Neither has a model-and-effort section today.

## Goals / Non-Goals

**Goals:**

- One skill that, run every few months, ends in a small approved rule change.
- Quality evidence from independent sources and from a local repeatable test, not only price.
- Older models stay in the comparison.
- Easy to refresh: sources, prices and cases are data, not code paths.

**Non-Goals:**

- A separate pricing skill, a scheduler or an automatic CLAUDE.md edit.
- Other providers. The data schema keeps a provider field, but only Anthropic prices are fetched.
- A general benchmark framework. One case type (code review) is shipped; other task types add cases later by the same format.
- Measuring plan-window consumption.

## Decisions

### 1. One skill, user-invoked, in `base`

`plugins/base/skills/model-guidance/`, `disable-model-invocation: true`, `dependencies: [usage-report]`. Helper scripts under the skill's `scripts/` handle the deterministic parts (parse the price table, diff, cost per run, scoring arithmetic). The model does fetching judgment, classification review and the proposal. Rejected: separate `model-pricing` skill (user decided against), running on a timer (new models arrive irregularly; the user decides when).

### 2. Prices: the official page in markdown form, cross-check with `claude-api`

Verified on 2026-11-22: appending `.md` to the pricing URL returns a 40 KB markdown document with the full model table (the HTML form is 800 KB). The table has one row per model: input, 5m and 1h cache write, cache read, output, with footnote markers for tiers. A script parses it; the model reads the footnotes (long-prompt tier, retired models, limited availability) and fills `tiers`. The `claude-api` skill is invoked once per run and its model ids and prices compared; the page wins and any difference is shown. Retired models stay in the table only when they appear in the dataset. The write goes to the user override file, never into the plugin directory (a plugin update would replace it).

### 3. External evidence: a registry with honest stability notes

Sources were fetched on 2026-11-22. The registry (`sources.json`) stores URL, contribution, read method, stability and verified date.

Use:

| Source | Contributes | How read | Stability |
|---|---|---|---|
| Artificial Analysis models, https://artificialanalysis.ai/models | Intelligence Index, cost to run the index, time per task, per model and effort (for example Fable 5.2 at max, xhigh and high) | Free Data API (`GET /api/v2/language/models`, key in `x-api-key`, attribution required) or MCP server `https://mcp.artificialanalysis.ai/mcp`; the HTML is 1.2 MB of framework output | API documented and versioned (index versioning page); HTML layout can change. In the static HTML the 5.5 Claude models appear only as "(max)", so per-effort rows for them must be confirmed through the API |
| Artificial Analysis Terminal-Bench 4.0, https://artificialanalysis.ai/evaluations/terminalbench-4-0 | 66-task terminal benchmark, mini-swe-agent harness, pass@1 over three repeats, independent | Same API or the page | As above |
| Artificial Analysis Coding Agent Index, https://artificialanalysis.ai/agents/coding | Composite of FrontierCode-AA 2.0, Terminal-Bench 4.1 and SWE-Atlas-QnA-AA across agents and models; API has `/language/agents/coding` | API or page | New (static text names only older models); verify per run |
| Terminal-Bench leaderboard, https://www.tbench.ai/leaderboard | Terminal-Bench 4.1: model with effort, agent harness, resolution rate with confidence interval, tokens and cost. At fetch: Opus 5.5 (max) 65.8% at $4.7k, Sonnet 5.5 (max) 63.9% at $7.3k, Haiku 5.5 (max) 40.0% at $1.0k | Plain HTML table in the static page | Good: stable table, no key. Mostly max effort for Claude models |

Use for method or as secondary:

| Source | Contributes | How read | Stability |
|---|---|---|---|
| GitHub ReviewBench, https://github.blog/ai-and-ml/reviewbench-an-open-benchmark-for-ai-code-review/ | 219 real PRs with golden findings; precision, recall, F1 | Blog post (static) | Product-level (review tools), not raw model and effort; a template for our scoring |
| Martian Code Review Bench, https://codereview.withmartian.com | Online and offline code review leaderboards | Page is empty without JavaScript: needs a browser | Unstable to scrape; check by hand when needed |
| CR-Bench https://arxiv.org/abs/2603.11078, MCR-Bench https://arxiv.org/abs/2608.27442, SWR-Bench https://arxiv.org/abs/2509.01494 | Code review metrics (precision, recall, signal to noise) and how pressure for more findings adds noise | Papers | Fixed in time, older models; cite for method |
| Snorkel agentic coding, https://snorkel.ai/leaderboard/agentic-coding/ | SWE-bench CLI and other agent benchmarks, top three per board | Static HTML | No effort levels; coarse |
| Epoch AI benchmarks, https://epoch.ai/benchmarks | Capabilities index; showed Fable 5.2 | Static HTML | Not checked for 5.5 rows |

Checked and not used: Aider leaderboard (page dated November 2025), Scale SWE-Bench Pro (page lists Opus 4.1 and Sonnet 4), SWE-rebench (newest Claude entries Opus 5 and Sonnet 5, window ends 2026-07, 7.8 MB page), OpenRouter rankings (token share, not quality), LMArena (403 to scripts), LiveBench (JavaScript shell), swebench.com (no model names found in the static page).

No live leaderboard covers code review at model and effort level for the current Claude models. That gap is the reason for the local benchmark.

Rejected: one source only (single point of failure, vendor-specific harness), scoring from vendor announcements (not independent).

Each fetched datum is saved with URL, date and a hash of the raw fetch under `~/.claude/model-bench/external/<date>/`, so a decision can be traced and a layout change is noticed.

### 4. Task types and usage

Fixed list: review, implement, research, commit-chore, docs, other. Heuristics first (skill name, branch prefix `fix/feat/chore`, agent type, title words). Unlabelled titles go to one batched call at a cheap model after the user agrees, cached in `~/.claude/usage/task-types.json` so it never repeats. Rejected: classifying daily inside the collector (adds LLM cost to every day).

Useful before any quality label exists: agents per task, cache-read volume per agent and cost per task type, which shows fan-out cost.

### 5. Benchmark storage and runs

```
~/.claude/model-bench/
  cases/<case-id>/case.json      id, task type, description, checker arm, scoring notes
                  brief.md       what the model is told
                  snapshot/      plain files, no git history
                  MANIFEST       sha256 per snapshot file
                  key.json       items: id, severity, slice, location, mechanism
  runs/<run-id>/run.json         case, snapshot checksum, arms, repeats, checker, price table, date, session ids
                 <arm>-<n>/report.md  score.json  cost.json
  external/<date>/<source>.json  raw evidence per source
```

A run materialises the snapshot into a fresh temp directory per run, so the key is never in the model's working directory. Reports are scored by one checker arm held constant across all runs (recorded in the run). Scoring follows the experiment: key item caught (mechanism, not just file), partial or missed; other findings real, false or unsettled; recall, false findings, extra real findings, severity-weighted recall; plus cost per caught bug.

Snapshot as plain files, not a git revision: the experiment snapshot mixes files from several commits. A manifest guarantees that a rerun months later reviews the same bytes.

Rerun on release: a new model becomes a new arm. Stored arms are not rerun unless the checker, brief or snapshot changed, in which case the comparison is marked invalid and the old arms must be rerun.

Cost comes from the dataset after a collector refresh, matched by the session id or agent description in `run.json`, not from the single token number in task notifications (never reconciled with transcripts). For `claude -p` runs the JSON output's reported cost is a cross-check.

Variance: one run per arm is an anecdote. The default is three repeats for finalists and one for a first screening pass, reported as mean and range. The cost estimate and a cap are shown before any run.

Rejected: shipping the key in the repo (public, may leak into future training data and into agent reads), LLM judge without a fixed key (scores drift), scoring by the arm itself.

### 6. Guidance proposal

A table of task type to tier and model@effort, tiers mapped in one line (cheap, mid, top), each rule carrying `(evidence YYYY-MM, review by YYYY-MM)`. A new release only remaps the tier line or edits rows with evidence. Thresholds from the spec: a quality signal is required; a change needs at least 30% lower cost at equal or better measured quality (or a clear quality gain at similar cost); cost-only findings are outliers, not rules. The section stays at about ten lines. Evidence lives in `~/.claude/usage/guidance-log.md`.

Targets and approval: a diff per file through `AskUserQuestion`, recommended option first. Personal rules go to `~/.claude/CLAUDE.md`; only broadly backed rules go to `plugins/base/CLAUDE.md`, which other users copy. Rejected: writing without a diff, one combined diff (the user may want only one file), a monthly cadence (the trigger is a model release).

## Risks / Trade-offs

- Benchmark of one case (14 bugs, one repo, one task type) generalises poorly. Mitigation: repeats, mean and range, rules flagged with their evidence and further cases added by the same format.
- Benchmark runs spend plan window. Mitigation: estimate, cap and approval.
- The key is small: 14 items, so each item moves recall by 7 points. Compare differences below two items with caution.
- Scraping breaks: layouts change and the AA free API needs a key. Mitigation: registry with verified dates, per-source failure handling, raw fetch saved.
- Effort coverage in external sources may be only "max" for new models. Then those data cannot rank effort levels and the local benchmark decides.
- Models may have been trained on the public fixes. The bugs come from public fix commits, so contamination is possible and would favour newer models.
- The checker is itself a model and can mis-score. The user can spot check, and the same checker is used throughout.
- Subagent tool-loading cost may drop in coming weeks. Rerun after such a change; the dataset shows the new cost directly.

## Open questions

Assumptions made because nobody could be asked:

- Skill lives in `base` next to `usage-report`. The user named CLAUDE.md files in `base` as targets but did not name a plugin for the skill.
- Runner is `claude -p --model <id> --effort <level> --output-format json` in a throwaway directory, because the Agent tool offers only model aliases and older models need full ids. The exact read-only tool flags are settled by a dry run in task 3.1.
- Checker arm: the strongest available model at high effort, fixed per case. Which one is the user's call at first run.
- Default repeats: 1 for screening, 3 for finalists. Cost cap default is set per run after the estimate.
- Free Artificial Analysis API key is assumed available as `AA_API_KEY`. Without it the skill falls back to the page and then to the MCP server, and says which it used.
- Whether the sources list 5.5 models at efforts below max (for example `claude-sonnet-5-5-high`) was not confirmed from static HTML. Confirm through the API in task 2.2.
- Moving the experiment's snapshot and key out of the session scratchpad (`.../scratchpad/exp2/snap` and `.../exp2-key/answer-key.md`) is a prerequisite for task 3.3. If they are gone, the snapshot can be rebuilt from the parents of fix commits 0933c9f, fd405f0, 05e0493 and 992289b, but the original mix of file versions may differ.
- Task type list and tier names (cheap, mid, top) are proposals from the exploration and can be changed.

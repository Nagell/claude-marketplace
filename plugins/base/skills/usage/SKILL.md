---
name: usage
description: Show what your most used skills and their agents cost on this machine, from Claude Code's local transcripts, read on demand. Ranks skills by estimated spend in a window, shows script-built trends per skill (cost per run, per agent role, per model and effort, share of prompts over 100k, per month), reads the recent and outlier runs, and names agent roles to drop or to strengthen. Labels review-mr agents by role and slice from its run.json. Checks transcript retention and offers 180 days. A models mode checks prices, reads Artificial Analysis, benchmarks new models under a cost cap you set and proposes a `## Models` rule list. Changes nothing without your yes. Invoke only via /base:usage.
argument-hint: "[--days N] [--top N] [--runs N]"
disable-model-invocation: true
dependencies:
  - review-mr
  - claude-api
---

# Usage

Estimated API-equivalent cost of your skill runs, from the transcripts Claude Code already writes to `~/.claude/projects/`. One scan, no hook, no stored data. Numbers come from scripts; you write only the judgment.

`$SKILL_DIR` is the folder this SKILL.md was loaded from. `<scratchpad>` is the session scratchpad named in your system prompt. `<scratch root>` is the folder three levels above it (`<scratch root>/<project>/<session>/scratchpad`), usually `/tmp/claude-<uid>`.

## Rules

- Every number you show comes from the script output. Never compute, estimate or round a cost yourself beyond formatting, and never read transcripts to count tokens.
- Report mode writes nothing into the working tree or any repository. The report is printed in the session.
- Report mode may change only `~/.claude/settings.json`, through `report.py --set-retention`, and only after the user said yes in this run.
- Models mode may change only these, each after the user's yes in this run: `~/.claude/usage/prices.json` (through `models.py --prices --write`), the case's `results.json` and `RESULTS.md` in a repo checkout (through `bench.py run`), and the `## Models` sections and the review-mr role table (step M8). It never edits the plugin's `prices.json` seed. Its scripts also write their own outputs under `~/.claude/model-bench/`: raw external fetches (`external/<date>/`, step M3) and run reports (`<case>/runs/`, step M5).
- Recommendations are output only. Never edit a skill, an agent brief or a setting to apply one: applying it goes through an OpenSpec change and a benchmark check.
- Costs are estimates at API prices, not plan usage. Say "estimate" with the totals.

## Steps

### 1. Retention check

```bash
python3 $SKILL_DIR/scripts/report.py --retention
```

When `error` is set, show it in one line and skip the offer. `source` says where the value comes from (`managed`, `project local`, `project`, `user` or `unset`); when it is not `user` or `unset`, `offer` is false and `note` names the file. When `offer` is false, say nothing about it (180 or more is long enough). When `offer` is true, the history is cut at `effective_days`: show `cleanupPeriodDays` and the `note` (unset or invalid, such as 0, means the default of 30 applies), the average size per active day and `estimate_bytes_at_180_days`, in MB or GB. Ask in the same AskUserQuestion call as step 2:

- `Keep 180 days (Recommended)` - writes `cleanupPeriodDays: 180`, every other key kept.
- `Leave it` - nothing changes.

On yes, run `python3 $SKILL_DIR/scripts/report.py --set-retention 180` and confirm in one line. When it prints an `error` (exit 1), show it: the file was not changed.

### 2. Mode

One AskUserQuestion call, with the retention question when there is one:

- `report (Recommended)` - top skills, trends, drop and strengthen candidates.
- `models` - model and effort advice per task: prices, external data, a small local benchmark of new models, and a `## Models` rule list. Follow [Models mode](#models-mode).

When the user picks `models`, skip steps 3 to 5.

### 3. Report data

```bash
python3 $SKILL_DIR/scripts/report.py --days <N> --top <N> --runs <N> --scratch-root '<scratch root>'
```

Defaults: `--days 30 --top 5 --runs 5`; take the user's values from the arguments when given. The output is JSON with:

- `skills`: the top skills by spend, each with `trends` and `runs` (the last N runs plus outliers, each with `picked_because` and per-agent details, including `path`, the agent's transcript).
- `skills_in_window`: when it is below `--top`, say only that many skills ran.
- `review_run_json`: `review_runs` and `with_run_json`, how many `review-mr` runs had a `run.json` (labels by role and slice, `findings_by_role`). Each run keeps its own in a folder under `runs_root`, which nothing deletes; runs from before those folders fall back to the session scratchpad, which keeps only the latest review's file until a reboot, so older runs often have none. Say how many, and show any entry in `errors` (a broken file, a folder no run matched, or a second folder for one run).
- `prices` (with `override_notes` or `override_error`), `unpriced_models`, `warnings`, `api_errors`, `skipped_lines`, `spend_no_skill`: mention each one that is not empty or zero, in one line. A skill's `notes` say when unpriced requests make its cost too low.

### 4. Deep read

For each top skill, read the runs in `runs`. For each agent of those runs, read only the end of its transcript at `path` (its final reply: the last assistant text, with `tail` or `grep -n`, never the whole file; a `review-mr` agent replies with a report path, so read that report's ledger instead when it still exists) to see what it found, what it reported unfinished and which files it left unread. Do not read other agents or other runs.

A skill's `notes` say when its agents do not use the `Unfinished:` convention (a `review-mr` rule); then there is no most-unfinished outlier, and say why.

### 5. Write the report

Per top skill:

1. One line: runs, total and cost per run (mean and max), over-100k share.
2. A short table from `trends`: cost per role and per model and effort; one line per month when there is more than one.
3. **Strengthen candidates**: roles that look overwhelmed. Signs: prompts over 100k (`over_100k`, `largest_prompt`), `Unfinished:` lines, files left unread in the final reply. Cite the run ids each rests on (for example "4 of 5 recent runs: `<run_id>`...").
4. **Drop candidates**: roles that add nothing the others do not. For `review-mr` with `run.json`, a role with repeated but no unique surviving findings in `findings_by_role`; otherwise what the final replies show. Cite the runs.

Say plainly when there is nothing to recommend. End with one line: applying a candidate goes through an OpenSpec change and a benchmark check; nothing was changed.

## Models mode

Scripts print JSON; you read footnotes, pick tasks and write the rule list. Every number still comes from a script. `<case>` is a folder under `$SKILL_DIR/references/bench/` (the first is `review-hooks-browser`, which belongs to `review-mr`).

### M1. Usage

```bash
python3 $SKILL_DIR/scripts/models.py --usage --days <N> --top <N>
```

Show one line per top skill: runs, the model and effort used most, cost per run (mean). Benchmark sessions (custom title `bench-...`) are already left out.

### M2. Prices

```bash
python3 $SKILL_DIR/scripts/models.py --prices
```

It fetches Anthropic's pricing page (URL in `sources.json`), maps display names to model ids and diffs them against the active table (seed plus override). An `error` (exit 1) means the page could not be read (no answer, no model rows, a long-prompt note it cannot parse) or the override file is invalid: show it and keep the current table. Read `footnotes` yourself: a tier such as "for prompts over 100,000 tokens" is already a `long_prompt` entry; say which models are `retired`. Then invoke the `claude-api` skill once and cross-check the mapped ids and the prices of `added` and `changed` against it. The page wins; show every difference between the page, the skill and the table as old and new price.

When `added` or `changed` is not empty, ask one AskUserQuestion: `Update ~/.claude/usage/prices.json (Recommended)` or `Keep the current table`. On yes run `python3 $SKILL_DIR/scripts/models.py --prices --write` (atomic; only those models change, other keys are kept) and confirm in one line. On no, nothing is written and the run uses the current table.

### M3. External data

Before any fetch, check whether a key is there: `AA_API_KEY` is set or `~/.claude/usage/aa-api-key` exists (`test -n "$AA_API_KEY" || test -s ~/.claude/usage/aa-api-key`; never print the key). When neither is, ask one AskUserQuestion first:

- `I'll add a key (Recommended)` - Artificial Analysis gives a free API key after a free sign-up; get it at https://artificialanalysis.ai/data-api. The free tier covers the models list (index score and cost to run per model and effort, 100 requests a day). The user writes the key, from their own terminal and not in this session, to `~/.claude/usage/aa-api-key` (`umask 077` first, so only they can read it), then says when it is there. Never ask them to paste the key into the session: a key on a command line lands in the transcript and the safety hook blocks it.
- `No key, read the page` - the scores come from the public page, which lists fewer efforts.

Then run:

```bash
python3 $SKILL_DIR/scripts/models.py --external
```

Say which `path` was used (`free API` or `page`). A Pro+ endpoint answering 403 is reported in `notes` as `free tier`; that is expected, not an error. Name every entry in `skipped` (a source that did not answer, or answered with nothing the script could read) and go on without it. Show `effort_coverage` notes ("Effort not listed: ...") for the models you discuss. Rows tagged `reference` (other vendors) are context only: never benchmark them and never put them in the rule list. Credit Artificial Analysis when you show its numbers (`attribution`). Raw fetches with their hashes are under `~/.claude/model-bench/external/<date>/`; when a hash differs from the last run and the rows look wrong, say the page layout may have changed.

### M4. Benchmark plan

Save the outputs of M1 and M3 to files in `<scratchpad>`, then per case:

```bash
python3 $SKILL_DIR/scripts/bench.py plan <case> --external '<scratchpad>/external.json' --usage '<scratchpad>/usage.json' \
  --claude-md ~/.claude/CLAUDE.md --claude-md <repo>/plugins/base/CLAUDE.md > '<scratchpad>/plan.json'
```

It plans only models with no stored result in the setup (`setup_id`; default: the setup of the current model's result), at most 2 efforts each (`why`: lowest Artificial Analysis cost per index point, most used effort of the case's skill), and estimates each run from the closest stored run in the same setup. Show every pick with its estimate and the total (say "from history" for an estimate with `from_history`: it scales a run from before the setup; every estimate scales by token price only, not effort), `current` (the `## Models` line, else the best stored result) and anything in `comparability` (a changed checker brief, key, snapshot or setup makes those results not comparable: say so and let the user decide). A pick in `unestimated` has no stored run to scale from; say that its cost is unknown. Name the models in `no_effort` (no Artificial Analysis effort and no usage effort, so not planned) and a `note` on `current` (a `## Models` line the script could not read). List `incomplete_in_setup` with its `reason`: such a run can resume instead of starting over. Nothing planned: say so and go to M6.

### M5. Approval, cap and runs

Ask one AskUserQuestion with the plan and its total: `Run with a cap of $<total, rounded up> (Recommended)`, `Run with another cap` (the user types it) or `Skip the benchmark`. When `incomplete_in_setup` holds a run of a planned pick, add `Resume run <id> (Recommended)` first: it reruns only the agents that did not finish. Run nothing without a yes. A cap is required. Results are written only to a repo checkout of this marketplace, never to the installed plugin copy, so pass the case folder of that checkout (`<repo>` is its root); the script refuses any other folder before it spends:

```bash
python3 $SKILL_DIR/scripts/bench.py run <repo>/plugins/base/skills/usage/references/bench/<case> --plan '<scratchpad>/plan.json' --cap <usd> \
  --claude-md ~/.claude/CLAUDE.md --claude-md <repo>/plugins/base/CLAUDE.md   # add --resume <id> to resume
```

Run it in the background; it takes as long as one review per pick. One fresh temp folder with the snapshot and no key serves each pick. Each reviewer and the refuter is a `claude -p` call in it, with `--tools "Read,Grep,Glob,Bash" --permission-mode dontAsk`, deny rules for every key copy and `-n bench-<case>-<run>` (so both modes leave it out). The checker runs in its own folder and reads the key. `--max-budget-usd`: each reviewer gets the remaining cap minus the refuter's and checker's estimates, the refuter and the checker get what remains. The cap is checked after each phase, so reviewers running at once can together pass it by the estimate's error; the run then stops before the refuter. A pick whose estimate is above the remaining cap is not started: show its `reason`. After the runs, show per run: key bugs caught (strict and with partials), real cost with and without the refuter, slowest agent, and `repeat_proposed`. A repeat (within 2 key bugs of the current model) needs the same approval and cap as a first run. Results go to the case's `results.json` and `RESULTS.md`; commit them on a branch when the user wants them kept.

### M6. Case suggestions

From report mode's top skills (`python3 $SKILL_DIR/scripts/report.py --days <N> --top <N>`), list the skills that have no case under `references/bench/` as suggestions, in one line each. Add a case only after the user's yes, and only from a merged fix: the snapshot is the fix commit's parent, the key is the bugs that fix closed (each with id, severity, mechanism, snapshot file and line, fixing commit and fix hunk, as in `review-hooks-browser/answer-key.md`). When the user says yes but no merged fix exists to build a key from, add nothing and say why.

### M7. Ranking

```bash
python3 $SKILL_DIR/scripts/models.py --rank <case> --external-json '<scratchpad>/external.json'
```

`local` ranks complete runs within one setup by cost per caught key bug, then slowest-agent time (incomplete runs are left out); never rank across setups. `external` holds pairs without a local result by Artificial Analysis cost per index point (the cost of the whole index run, not a cost per task) and time per task, as a separate group. Token price is only a column.

### M8. Rule list and diff

Write the proposal as a `## Models` list, one line per task in the form `- <task>: <model> <effort>`, a short note in brackets where the setup matters, for example `- Review slices: Haiku 5.5 max (about 7 agents, ~400 lines each)`. Give a line only to tasks with evidence (a local result or external data, named in one line under the list); the script keeps the current line of every task the proposal does not name. Never name another vendor's model. No report file, no table. Save it to `<scratchpad>/models.md` and run:

```bash
python3 $SKILL_DIR/scripts/models.py --rules '<scratchpad>/models.md' --claude-md ~/.claude/CLAUDE.md --claude-md <repo>/plugins/base/CLAUDE.md \
  --review-skill <repo>/plugins/base/skills/review-mr/SKILL.md
```

Name every line in `dropped` (no task, or a model and effort the script cannot read) and fix or leave it. An `error` (exit 1) means no line was left: nothing changes. Show `diff` (both `## Models` sections, kept identical, and the rows of review-mr's fallback role table in `plugins/base/skills/review-mr/SKILL.md` step 4 that the `- Review` lines cover) and ask one AskUserQuestion: `Apply (Recommended)` or `Leave the files`. On yes rerun with `--write`; it writes the merged lines (`section`) into an existing `## Models` section or appends one, and changes nothing else. On no, none of the three files changes.

## Tests

```bash
cd $SKILL_DIR && python3 -m unittest discover -s tests
```

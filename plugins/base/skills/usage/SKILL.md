---
name: usage
description: Show what your most used skills and their agents cost on this machine, from Claude Code's local transcripts, read on demand. Ranks skills by estimated spend in a window, shows script-built trends per skill (cost per run, per agent role, per model and effort, share of prompts over 100k, per month), reads the recent and outlier runs, and names agent roles to drop or to strengthen. Labels review-mr agents by role and slice from its run.json. Checks transcript retention and offers 180 days. Prints only; changes nothing without your yes. Invoke only via /base:usage.
argument-hint: "[--days N] [--top N] [--runs N]"
disable-model-invocation: true
---

# Usage

Estimated API-equivalent cost of your skill runs, from the transcripts Claude Code already writes to `~/.claude/projects/`. One scan, no hook, no stored data. Numbers come from scripts; you write only the judgment.

`$SKILL_DIR` is the folder this SKILL.md was loaded from. `<scratchpad>` is the session scratchpad named in your system prompt. `<scratch root>` is the folder three levels above it (`<scratch root>/<project>/<session>/scratchpad`), usually `/tmp/claude-<uid>`.

## Rules

- Every number you show comes from the script output. Never compute, estimate or round a cost yourself beyond formatting, and never read transcripts to count tokens.
- Write nothing into the working tree or any repository. The report is printed in the session.
- The only file this skill may change is `~/.claude/settings.json`, through `report.py --set-retention`, and only after the user said yes in this run.
- Recommendations are output only. Never edit a skill, an agent brief or a setting to apply one: applying it goes through an OpenSpec change and a benchmark check.
- Costs are estimates at API prices, not plan usage. Say "estimate" with the totals.

## Steps

### 1. Retention check

```bash
python3 $SKILL_DIR/scripts/report.py --retention
```

When `error` is set, show it in one line and skip the offer. When `offer` is false, say nothing about it (180 or more is long enough). When `offer` is true, the history is cut at `effective_days`: show `cleanupPeriodDays` and the `note` (unset or invalid, such as 0, means the default of 30 applies), the average size per active day and `estimate_bytes_at_180_days`, in MB or GB. Ask in the same AskUserQuestion call as step 2:

- `Keep 180 days (Recommended)` - writes `cleanupPeriodDays: 180`, every other key kept.
- `Leave it` - nothing changes.

On yes, run `python3 $SKILL_DIR/scripts/report.py --set-retention 180` and confirm in one line.

### 2. Mode

One AskUserQuestion call, with the retention question when there is one:

- `report (Recommended)` - top skills, trends, drop and strengthen candidates.
- `models (not available yet)` - model and effort advice per task; a later change adds it.

When the user picks `models`, say it is not available yet and offer to run `report` instead.

### 3. Report data

```bash
python3 $SKILL_DIR/scripts/report.py --days <N> --top <N> --runs <N> --scratch-root '<scratch root>'
```

Defaults: `--days 30 --top 5 --runs 5`; take the user's values from the arguments when given. The output is JSON with:

- `skills`: the top skills by spend, each with `trends` and `runs` (the last N runs plus outliers, each with `picked_because` and per-agent details, including `path`, the agent's transcript).
- `skills_in_window`: when it is below `--top`, say only that many skills ran.
- `review_run_json`: how many `review-mr` runs still had their `run.json` (labels by role and slice, `findings_by_role`). The scratchpad lives in `/tmp`, so older runs often have none; say how many.
- `prices`, `unpriced_models`, `api_errors`, `skipped_lines`, `spend_no_skill`: mention each one that is not empty or zero, in one line.

### 4. Deep read

For each top skill, read the runs in `runs`. For each agent of those runs, read only the end of its transcript at `path` (its final reply: the last assistant text, with `tail` or `grep -n`, never the whole file) to see what it found, what it reported unfinished and which files it left unread. Do not read other agents or other runs.

A skill's `notes` say when its agents do not use the `Unfinished:` convention (a `review-mr` rule); then there is no most-unfinished outlier, and say why.

### 5. Write the report

Per top skill:

1. One line: runs, total and cost per run (mean and max), over-100k share.
2. A short table from `trends`: cost per role and per model and effort; one line per month when there is more than one.
3. **Strengthen candidates**: roles that look overwhelmed. Signs: prompts over 100k (`over_100k`, `largest_prompt`), `Unfinished:` lines, files left unread in the final reply. Cite the run ids each rests on (for example "4 of 5 recent runs: `<run_id>`...").
4. **Drop candidates**: roles that add nothing the others do not. For `review-mr` with `run.json`, a role with repeated but no unique surviving findings in `findings_by_role`; otherwise what the final replies show. Cite the runs.

Say plainly when there is nothing to recommend. End with one line: applying a candidate goes through an OpenSpec change and a benchmark check; nothing was changed.

## Tests

```bash
cd $SKILL_DIR && python3 -m unittest discover -s tests
```

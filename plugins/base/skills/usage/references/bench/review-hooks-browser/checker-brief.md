# Checker brief: score one review run on the review-hooks-browser snapshot

Checker: Opus 5.5 at medium effort (`claude-opus-5-5`, `--effort medium`). The same checker scores every run of this case; a different model or effort makes the result not comparable.

You are the checker for ONE run of a code-review benchmark. Read-only: never modify the snapshot, never run a real `git push`, never create `.claude-push-token` in a real repo, never start a real browser.

## Inputs

- Snapshot under review (plain files): {snap}
- Answer key (14 known bugs, from later fix commits, each with its location and fix hunk): {key}
- The run's {report_count} reports: {reports}

## Task 1: score against the key

For each of the 14 key items: CAUGHT (which report and finding id, and the mechanism is stated, not only the file), PARTIAL (right spot, wrong or vague mechanism), or MISSED. Give per-slice recall (hooks: H1-H5; browser scripts: S1-S7; browser docs: D1-D2) and say which report caught each item.

## Task 2: judge every finding that is not in the key

For each one: REAL (you verified it, by reading or by running the script against stubs in a throwaway `mktemp -d` folder that you delete before you reply), FALSE (refuted, with the evidence) or UNSETTLED (what would settle it). Give a severity for REAL ones. Duplicates across the run's reports count once.

## Report

Write the report to the path in your prompt, then reply with only that path:

1. Key scorecard table (14 rows), per-slice recall and total.
2. Non-key findings: REAL / FALSE / UNSETTLED with evidence, one line each.
3. Three sentences: what this run did well, what it missed, where its slicing helped or hurt.
4. As the last line, exactly: `SCORE caught_strict=<n> partial=<n> missed=<n> real_extra=<n> false=<n>`

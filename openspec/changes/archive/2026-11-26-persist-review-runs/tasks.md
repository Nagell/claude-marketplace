# Tasks

## 1. Check the Write tool in default permission mode

- [x] 1.1 Check whether the Write tool prompts when creating a file under the run root in default permission mode (verify: design.md decisions 1 and 4 state the result; the test folders are deleted afterwards)

## 2. review-mr writes to the run folder

- [x] 2.1 In `plugins/base/skills/review-mr/SKILL.md`, create the run folder by writing `run.json` with the Write tool where `run.json` starts (step 2a), with the run id from design decision 3, add `run_dir` to the `run.json` example, say that no Bash command writes into the run folder, and stop the run with the path when the Write fails (verify: the step names the literal path form and the stop message; no `$SCRATCH/run.json` remains)
- [x] 2.2 Move every `$SCRATCH/wave…` report path, the Codex result path (saved with the Write tool, never a shell redirect) and the `report` field in the `run.json` example to the run folder, and give the folder's absolute path in every agent brief (verify: a structural search of `SKILL.md` and its briefs finds no `$SCRATCH/wave` and no `$SCRATCH/run.json`)
- [x] 2.3 Add to the sweep in step 8 that the run folder is never stopped, moved or deleted, and keep the temp-dir sweep as it is (verify: the sweep text names the run folder as kept; the existing review-mr tests pass)
- [x] 2.4 Document in the base plugin README's review section where run folders live, that they hold quoted code and are never deleted automatically, and the allow rule `Edit(//<home>/.local/share/review-runs/**)` for non-bypass permission modes (verify: the README section states the path, the allow rule and the manual deletion)

## 3. usage reads run folders

- [x] 3.1 In `usage/scripts/report.py`, read `run.json` from `<runs root>/<project>/<session>/*/` with a `--runs-root` option defaulting to `$XDG_DATA_HOME/review-runs` or `~/.local/share/review-runs`, match each review run to a folder by agent ids, else give the folder to the latest run that started at or before the folder's time, and read the scratchpad `run.json` only for runs no folder matched (verify: `python3 -m unittest discover -s tests` in `usage` passes)
- [x] 3.2 Add tests for the usage-report scenarios: two runs in one session with two folders, a run with no agents matched by time, an older run labelled from the scratchpad, and a run with neither (verify: each new test fails when the folder lookup is removed, then passes)
- [x] 3.3 Update `usage/SKILL.md` where it describes `review_run_json`, the "one run.json per session" note in `report.py`'s output, and the "Review runs" line in the base plugin README's usage section, so they name the run folders and the scratchpad fallback (verify: no text says a reboot or `/base:cleanup` removes run data for runs with a run folder)

## 4. End-to-end check

- [x] 4.1 Run the branch's `report.py` on the real transcripts with this session's two real `review-mr` `run.json` files placed as run folders under a temporary `--runs-root` and no scratchpad: both runs get their slice-owner labels from the folders (verify: `with_run_json` counts both runs and `errors` is empty)

## Workflow follow-up

- After the release that ships this change: run `/base:review-mr` twice in one session, then `/base:usage`, and check that both runs are labelled from their own folders under `~/.local/share/review-runs/` and that the folders outlive the session. `review-mr` loads from the installed plugin, so this cannot run from the branch.
- Sync specs and archive the change.

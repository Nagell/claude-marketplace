## Why

`review-mr` reads per-repo rules from `~/.claude/review-rules/<repo>.md`, but nothing helps anyone write one. The format lives only in `SKILL.md`, the no-rules notice names a path and nothing else, and this machine has no rules files at all. So the paired-repo question, extra lenses, size excludes and the server-rendering override never get used.

## What Changes

- A template rules file ships with the skill: every section with a short comment on what it does and that it is optional. The `## Counterpart` section is inside an HTML comment, so an untouched copy does not switch the paired-repo question on.
- When a review finds no rules file for the repo and the repo is not on the declined list, the step 0 dialog adds one question: create rules from the template at the expected path.
- Yes: the run copies the template, fills the Repos row (repo, checkout, project id; the worktree base is left to its `<checkout>.worktrees/` default), shows the path and the content, asks whether the repo has a paired repo (writing a live `## Counterpart` section when it does), then asks whether to add anything else, writes it in the right section and shows the change. It reruns the rules lookup and continues the review with the new file.
- No: the repo name goes into `~/.claude/review-rules/.declined`, and the offer is not shown again for that repo.
- `find_rules.py` reports `declined`.
- `SKILL.md`'s format section and the base README's "Project rules" section point to the template.

Non-goals: no change to how rules are found or matched (one file per repo name from `origin`, so it covers every worktree of the repo); no rules editor beyond the creation step.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `review-mr-agents`: the step 0 dialog offers to create a rules file when none exists; new requirements for the template, the creation step and the declined list.

## Impact

- New `plugins/base/skills/review-mr/references/rules-template.md`.
- `plugins/base/skills/review-mr/SKILL.md`: step 0, step 0a and the format section.
- `plugins/base/skills/review-mr/scripts/find_rules.py` and its tests: the `declined` field.
- `plugins/base/README.md`: "Project rules".
- Writes under `~/.claude/review-rules/` only after the user's yes (the rules file) or no (the declined list).

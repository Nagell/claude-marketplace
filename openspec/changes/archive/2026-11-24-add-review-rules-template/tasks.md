## 1. Template

- [x] 1.1 Add `references/rules-template.md`: frontmatter, every section of the format with an HTML comment (what it does, optional), worktree base marked optional with its default, `## Counterpart` inside a comment. Verify: `find_rules.py` on an unedited copy reports `counterpart: false`.
- [x] 1.2 Shorten the `SKILL.md` format example to the description plus a pointer to the template, and say that the worktree base is optional. Verify by reading.

## 2. Declined list

- [x] 2.1 `find_rules.py` reads `~/.claude/review-rules/.declined` (or under `REVIEW_RULES_DIR`) and prints `declined`. Verify: tests for listed, not listed, missing file, blank lines and a name with surrounding spaces.

## 3. Step 0 and 0a

- [x] 3.1 Step 0: with `path: null` and `declined: false`, add the create question to the dialog; with `declined: true`, no question, and the no-rules notice says how to be asked again. Verify by reading.
- [x] 3.2 Creation: copy without overwriting, prefill the Repos row, show path and content, ask about a paired repo, then an open "anything to add", write and show the change, rerun the rules lookup and continue. A no appends the repo to `.declined`. Verify by reading.

## 4. Docs

- [x] 4.1 Base README "Project rules": point to the template and describe the offer. Verify: `grep -n rules-template plugins/base/README.md`.

## 5. Verification

- [x] 5.1 Dry run in a throwaway rules dir (`REVIEW_RULES_DIR`): copy the template, prefill, add a live Counterpart, and check `find_rules.py` before and after; append to `.declined` and check `declined: true`.

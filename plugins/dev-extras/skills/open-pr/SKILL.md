---
name: open-pr
description: Open a merge request or pull request with a house-style description the push hook keeps current. Use every time an MR or PR is about to be created or opened — "open an MR", "create a merge request", "raise a PR", "open a pull request", "make a PR for this branch", "submit this for review", "glab mr create", "gh pr create" — including when opening the MR is the last step of a larger task.
dependencies:
  - pr-descriptions
---

# Open an MR / PR

Every new MR or PR gets its description from the `pr-descriptions` skill, with the
generated part inside the auto-refresh markers from the start.

1. **Push the branch first** and read the diff against the target branch
   (`git merge-base`, then `git diff <base> HEAD`), plus the commits.
2. **Ask for the author's note once**, with AskUserQuestion: "Want to add a line in your
   own words about what this MR is for?", with a skip option. Use the answer verbatim;
   a skip means no note.
3. **Write the generated part** to `block.md` following `pr-descriptions`: everything
   below the title and the note. No leading or trailing blank lines or spaces.
4. **Assemble `body.md`:**

   ```markdown
   ## <Title>

   > <author's note, verbatim>
   >
   > — <git config user.name>

   <!-- mr-desc:start sha=<git rev-parse HEAD> hash=<hash of block.md> -->
   <block.md>
   <!-- mr-desc:end -->
   ```

   Drop the quote when the author skipped. Compute the hash exactly this way, or the
   refresh reads the block as hand-edited and never touches it:

   ```bash
   printf '%s' "$(cat block.md)" | git hash-object --stdin
   ```

5. **Create it from the file,** never with the body inline — `!`, backticks and `$`
   are mangled by the shell:

   ```bash
   glab mr create --title "<title>" --description "$(cat body.md)"   # GitLab
   gh pr create --title "<title>" --body-file body.md                 # GitHub
   ```

6. **Re-read the live description** and confirm the markers and the note arrived
   unchanged.

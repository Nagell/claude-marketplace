---
name: open-pr
description: Use every time a merge request or pull request is being created or opened, on GitLab or GitHub. Triggers on "open an MR", "create a merge request", "raise a PR", "open a pull request", "submit a PR", "make an MR for this branch", "put this up for review", and before any `glab mr create` or `gh pr create`. Writes the description in the pr-descriptions house style, asks the author once for a note in their own words, and wraps the generated part in the auto-refresh markers.
dependencies:
  - pr-descriptions
---

# Open an MR/PR

Every MR/PR is opened with a description in the `pr-descriptions` house style, with the
generated part inside the auto-refresh markers from the start. Read the `pr-descriptions`
skill before writing.

## 1. Gather the change

- The branch, its target (the default branch unless the user names one), and the diff and
  commits against the merge base: `git diff "$(git merge-base <target> HEAD)"`.
- The branch must be on the remote before the MR/PR is created. Push it if it isn't.

## 2. Ask for the author's note, once

Ask with AskUserQuestion, e.g. "Want to add a line in your own words about what this MR is
for?", with a skip option. A skip means no note; don't ask again. Use the answer verbatim:
no rewording, shortening or fixing.

## 3. Write the block

Write everything below the title and note to `block.md`, following `pr-descriptions`. It
starts with text (no leading blank line), has no trailing spaces, and ends with one
newline: the hash below must match what the refresh script computes from the live
description.

## 4. Assemble the body

```bash
title='<Title naming the change>'
head=$(git rev-parse HEAD)   # full 40 characters
hash=$(printf '%s' "$(cat block.md)" | git hash-object --stdin)
{
  printf '## %s\n\n' "$title"
  # Only when the author gave a note (note.txt holds it verbatim):
  sed 's/^/> /; s/^> $/>/' note.txt
  printf '>\n> — %s\n\n' "$(git config user.name)"
  printf '<!-- mr-desc:start sha=%s hash=%s -->\n' "$head" "$hash"
  cat block.md
  printf '<!-- mr-desc:end -->\n'
} >body.md
```

Leave out the `note.txt` line and the signature `printf` when the author skipped. Anything
kept by hand (test notes, links) goes after the end marker.

## 5. Create it from the file

Never pass the body inline: the shell mangles `!`, backticks and `$`.

```bash
glab mr create --title "$title" --description "$(cat body.md)"   # GitLab
gh pr create --title "$title" --body-file body.md                # GitHub
```

## 6. Re-read the live description

The create command's output is not proof of what was stored.

```bash
diff -u body.md <(glab mr view -F json | jq -r .description)   # GitLab
diff -u body.md <(gh pr view --json body -q .body)             # GitHub
```

Any difference beyond a trailing newline means the markers or the note did not survive:
fix the description from `body.md` and re-read again.

## Context

`find_rules.py` runs before the step 0 dialog and prints `path`, `expected` and `counterpart`. The format is documented in `SKILL.md` ("Project rules: the format") with an inline example. `has_counterpart` already ignores a heading inside an HTML comment or a code fence.

## Goals / Non-Goals

**Goals:** a first review in a repo without rules ends with a usable rules file after one yes, without leaving the run; a "no" is asked once.

**Non-Goals:** changing how rules are matched; a separate setup command; editing existing rules files.

## Decisions

- **Template file, not the inline example.** `references/rules-template.md` holds the frontmatter and every section with an HTML comment per section. The `SKILL.md` format section keeps a short description and points to the file, so the example and the template cannot drift.
- **Counterpart commented out.** A live heading in the template would turn the paired-repo question on for every new file. The creation step asks about a paired repo explicitly instead, because that section is the only one a script reads.
- **Worktree base optional.** The column is documented with its default, `<checkout>.worktrees/`, and the prefill leaves it out.
- **Creation in the procedure, declined list in the script.** The copy, prefill and edits are done by the main session as `SKILL.md` describes (it needs the user's answers anyway). `find_rules.py` only reads `.declined` and reports `declined`, so the offer decision is testable.
- **Where the prefill comes from.** Repo name from the rules lookup, checkout from the session's checkout whose `origin` is the MR's project (step 1's rule), project id from the MR URL. A value that is not known yet is left as a placeholder.

Rejected: an empty rules file as the "declined" marker (it would read as "rules exist" and hide the notice); stopping the run after creation (the user chose to continue).

## Risks / Trade-offs

- The dialog grows by one question on first reviews → only when no rules file exists and the repo is not declined.
- Free-text additions can land in the wrong section → the run shows the change before continuing.

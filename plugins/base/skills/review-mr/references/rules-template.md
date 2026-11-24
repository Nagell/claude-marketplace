---
# Optional: the repos this file applies to besides the one in its file name.
# Needed only when one file serves several repos; delete it otherwise.
applies-to: [<repo>]
---

# Review rules: <repo>

<!--
How review-mr uses this file: it reads it whole as instructions for the
review. Every section is optional, and an empty one is fine: start with only
the Repos row. Fill a section when a review gets something wrong for this
repo - it read generated files line by line (Size excludes), missed what
matters here (Lens details), graded a finding too high or too low (Product
consequences) - and write the rule that would have avoided it, in plain
words. Comments like this one are notes for you; replace a section's comment
with your text. The one heading a script reads is "## Counterpart" (see
below), so keep that spelling.
-->

<!--
Platform: only for a self-hosted host whose name says neither github nor
gitlab. Write it as a line "Platform: gitlab" (or github) right here.
-->

## Repos

<!--
Optional. One row per repo this file covers. checkout: the local clone. --project: the
GitLab id or path, or the GitHub owner/repo. worktree base: only when review
worktrees should go somewhere other than <checkout>.worktrees/ (add the
column then); review-mr creates its "reviews" worktree there.
-->

| repo     | label | checkout     | `--project`    |
| -------- | ----- | ------------ | -------------- |
| `<repo>` | <tag> | `<checkout>` | `<project id>` |

<!--
## Counterpart

Uncomment this section only when the changes of this repo ship together with
MRs in another repo (a frontend and its backend). With it, a review asks
whether to check the boundary or review both MRs; without it, it does not ask.
Add the other repo as a row in "Repos" above.

The sibling of `<repo>` is `<other repo>`; pass its project as `--sibling`.
Pairing rule: both halves share a branch name.
-->

## Size excludes

<!--
Optional. Pathspecs left out of the reading-load count, on top of lockfiles, locales
and build output, which are always left out. Example:
':(exclude)**/migrations/**' ':(exclude)**/fixtures/**'
-->

## Lens details

<!--
Optional. What a lens means in this repo, or an extra lens with the paths that trigger
it. Examples:
- **i18n** - the locale files are `web/locales/**`.
- **Payments** (extra lens) - wherever `api/billing/**` changes: amounts,
  currencies, refunds.
-->

## Server rendering

<!--
Optional. Force the server-rendering lens on or off when detection from the framework
config guesses wrong (layers, env vars, per-route settings). One line per
repo: - `<repo>`: on   or   - `<repo>`: off
-->

## Refuters

<!--
Optional. - Checkout for product rules: the clone whose code owns the product rules,
  when that is another repo.
- Browser skill: the skill refuters drive a browser with, e.g. `browser`.
-->

## Repo review material

<!--
Optional. Review guides the repo keeps, handed to the slices they cover, and the
comments file the Comments lens checks. Example:
- `docs/review/CORRECTNESS.md`
- Comments file: `docs/review/comments.md`
-->

## Product consequences

<!--
Optional. What high and medium mean for this product, used to grade findings. Example:
High: an order charged twice, one shop seeing another shop's orders.
-->

## Machine notes

<!--
Optional. How to run git or the platform CLI on this machine when the default does not
work (a sandbox, a wrapper, a token in another place).
-->

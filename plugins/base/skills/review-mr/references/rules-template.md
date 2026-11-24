---
# Optional: the repos this file applies to besides the one in its file name.
# Needed only when one file serves several repos; delete it otherwise.
applies-to: [<repo>]
---

# Review rules: <repo>

<!--
How review-mr uses this file: it reads it whole as instructions for the
review. Every section is optional - delete what you do not need. The one
heading a script reads is "## Counterpart" (see below), so keep that spelling.
-->

## Repos

<!--
One row per repo this file covers. checkout: the local clone. --project: the
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
Pathspecs left out of the reading-load count, on top of lockfiles, locales
and build output, which are always left out. Example:
':(exclude)**/migrations/**' ':(exclude)**/fixtures/**'
-->

## Lens details

<!--
What a lens means in this repo, or an extra lens with the paths that trigger
it. Examples:
- **i18n** - the locale files are `web/locales/**`.
- **Payments** (extra lens) - wherever `api/billing/**` changes: amounts,
  currencies, refunds.
-->

## Server rendering

<!--
Force the server-rendering lens on or off when detection from the framework
config guesses wrong (layers, env vars, per-route settings). One line per
repo: - `<repo>`: on   or   - `<repo>`: off
-->

## Refuters

<!--
- Checkout for product rules: the clone whose code owns the product rules,
  when that is another repo.
- Browser skill: the skill refuters drive a browser with, e.g. `browser`.
-->

## Repo review material

<!--
Review guides the repo keeps, handed to the slices they cover, and the
comments file the Comments lens checks. Example:
- `docs/review/CORRECTNESS.md`
- Comments file: `docs/review/comments.md`
-->

## Product consequences

<!--
What high and medium mean for this product, used to grade findings. Example:
High: an order charged twice, one shop seeing another shop's orders.
-->

## Machine notes

<!--
How to run git or the platform CLI on this machine when the default does not
work (a sandbox, a wrapper, a token in another place).
-->

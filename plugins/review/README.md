# review

Review someone else's GitLab merge request or GitHub pull request from an isolated worktree. You accept the drafts before anything is posted, and then they go out as one review with one verdict.

## Installation

```bash
/plugin install review@dawidnitka
```

## Skills

| Skill        | Description                                                                 |
| ------------ | --------------------------------------------------------------------------- |
| `/review-mr` | Review an MR or PR and post the accepted findings as one review with a verdict |

`/review-mr` runs only when you type it. Pass an MR or PR URL (or `!iid` inside the repo). Optional flags: `--both` or a second URL to review a paired change in full, `--finish` / `--no-finish` for finish mode.

What a run does:

- Asks which engine (Claude, Codex or both) and what effort to use, and whether to review a paired MR in full or only the boundary between the two.
- Checks the MR out at its head in a `reviews` worktree, and diffs against the MR's own merge base rather than `main`.
- Reads the existing threads first, so a re-review checks earlier findings instead of repeating them.
- Reviews in two waves. Every agent writes a coverage ledger, and the second wave works the ground the first one left unexamined.
- Sends a refutation agent to break each finding, with a browser if one is available, before anything is drafted.
- Shows every draft and thread action in plain English for acceptance, then posts them as one review: drafts first, then one submit with a verdict.

## Project rules

Anything specific to one repo or product lives outside the skill, in `~/.claude/review-rules/`:

- `~/.claude/review-rules/<repo>.md` applies to the repo whose `origin` URL ends in `<repo>`. The name comes from the remote, so worktrees resolve the same as the main checkout.
- If there is no file with that name, the first `*.md` whose frontmatter lists the repo under `applies-to:` is used:

  ```yaml
  ---
  applies-to: [shop-api, shop-web]
  ---
  ```

A rules file can name the checkout and project id, a paired repo and its pairing rule, size excludes, extra lenses with trigger paths, the checkout refuters read product rules from, the browser skill, the repo's own review material, examples of product consequences, and machine notes. `skills/review-mr/SKILL.md` (step 0a) documents the format with a full example.

When no rules file matches, the review shows a framed notice with the exact path it looked for, then continues without rules.

## Platforms

| Platform | Client                       | CLI    | Notes                                                                                   |
| -------- | ---------------------------- | ------ | --------------------------------------------------------------------------------------- |
| GitLab   | `scripts/gitlab_comments.py` | `glab` | Draft notes, `bulk_publish` with a reviewer state, resolve on publish                   |
| GitHub   | `scripts/github_comments.py` | `gh`   | Pending review plus a submit event; threads are resolved or reopened after publishing via GraphQL |

The platform is detected from the MR URL, or from the remote URL when you pass `!iid`. Both clients have the same subcommands. `skills/review-mr/platforms/` describes where the two platforms differ.

## Dependencies

| Skill                                | Required | Used for                                                                |
| ------------------------------------ | -------- | ----------------------------------------------------------------------- |
| `browser` (or `start-chrome-debug`)  | No       | In-browser checks by the refuters; without one, refuters check code only and say so |
| `writing-style-guide`, `humanizer`   | No       | Comment prose, from `base-setup`                                        |
| Codex plugin (`openai-codex`)        | No       | The Codex engine                                                        |

## Requirements

- Claude Code
- Git and Python 3
- An authenticated `glab` (GitLab) or `gh` (GitHub)

## Tests

```bash
cd plugins/review && python3 -m pytest tests
```

# dev-extras

Optional developer tooling split out of `base-setup`, so work setups that already ship their own versions can skip it.

## Installation

```bash
/plugin install dev-extras@dawidnitka
```

## Skills

| Skill             | Description                                                 |
| ----------------- | ----------------------------------------------------------- |
| `skill-creator`   | Create, edit, eval, and benchmark skills                    |
| `pr-descriptions` | Write PR/MR descriptions in a consistent house style        |
| `open-pr`         | Open a PR/MR with a description the push hook keeps current |

Call any of them by name, or let Claude reach for them when the task fits. For browser work, install the
`browser` plugin from this marketplace.

## Hooks

| Event                    | Script                      | Purpose                                                      |
| ------------------------ | --------------------------- | ------------------------------------------------------------ |
| PostToolUse (`git push`) | `refresh-mr-description.sh` | Rewrites the marked block of the branch's open PR/MR description |

After each push Claude makes, the hook refreshes the open GitHub PR (via `gh`) or GitLab MR (via `glab`) for the pushed branch. The platform comes from the remote URL; set `MR_DESC_FORGE=github` or `gitlab` to override it, e.g. for GitHub Enterprise.

- Only the text between `<!-- mr-desc:start … -->` and `<!-- mr-desc:end -->` is rewritten. Descriptions without the markers are left alone.
- A block edited by hand is skipped until you run the script with `run --force`.
- Each run calls `claude -p` on Haiku, capped at $0.50, and saves the previous description to `~/.local/state/mr-desc-refresh/backups/`.
- Log: `~/.local/state/mr-desc-refresh/refresh.log`.

## Requirements

- Claude Code
- Python 3 (for `skill-creator` eval scripts)
- `jq`, `claude`, and an authenticated `gh` or `glab` (for the PR/MR refresh hook)

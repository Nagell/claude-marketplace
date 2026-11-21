# base

Foundational Claude Code configuration with safety guardrails, auto-formatting, and pre-configured MCP servers.

## Installation

```bash
# Add marketplace
/plugin marketplace add Nagell/claude-marketplace

# Install plugin
/plugin install base@dawidnitka
```

### Quick Setup (All Plugins)

After installing, run:

```bash
/base:plugin-setup
```

This installs all recommended official plugins in one command. Restart Claude Code after installation.

## Skills

Some skills you invoke by name; others Claude reaches for on its own.

### You invoke these (`/base:<name>`)

| Skill                             | Description                                                              |
| --------------------------------- | ------------------------------------------------------------------------ |
| `/base:plugin-setup`              | Install recommended plugins and marketplaces                             |
| `/base:setup-token-savings`       | Set up tools for CC to save tokens                                       |
| `/base:setup-macos`               | macOS only: Finder defaults, screenshots to the clipboard, Spaces hotkeys off Ctrl+arrows, Karabiner-Elements Windows-style shortcuts and Ctrl+click, fast key repeat, numbered workspaces per screen (FlashSpace on Caps Lock, SketchyBar top bar, Rectangle snapping with gaps), AltTab window switcher on Cmd+Tab |
| `/base:setup-zsh`                 | Configure Zsh with zinit, Powerlevel10k, syntax highlighting, Nerd Fonts, Windows-style keybindings; optional Ghostty (macOS), herdr, mdv and LazyVim editor |
| `/base:review-mr`                 | Review an MR or PR and post the accepted findings as one review with a verdict ([details](#reviewing-mrs-and-prs)) |

These set `disable-model-invocation: true`, so they run only when you call them, never on Claude's initiative.

On a Mac, run `/base:setup-macos` first, then `/base:setup-zsh`: the zsh keybindings need the Spaces hotkeys moved off Ctrl+arrows. On Linux and WSL, `setup-zsh` is all you need.

### Claude uses these automatically

| Skill                 | Description                                              |
| --------------------- | -------------------------------------------------------- |
| `writing-style-guide` | Dawid Nitka's personal writing style guide               |
| `html-doc`            | Convert markdown into styled HTML reports or slide decks |
| `humanizer`           | Strip AI-writing tells from prose (vendored upstream)    |
| `openspec-grill`      | Grill an idea or a change against the project's specs, then hand it to propose or update ([OpenSpec steps](#openspec-steps)) |
| `openspec-plan-check` | Check a change's plan against today's code before apply  |
| `grilling`            | Vendored from [mattpocock/skills](https://github.com/mattpocock/skills) (MIT); `openspec-grill` runs it |

## Reviewing MRs and PRs

`/base:review-mr` reviews someone else's GitLab merge request or GitHub pull request from an isolated worktree. You accept the drafts before anything is posted, and then they go out as one review with one verdict.

Pass an MR or PR URL (or `!iid` inside the repo). Optional flags: `--both` or a second URL to review a paired change in full, `--finish` / `--no-finish` for finish mode.

What a run does:

- Asks which engine (Claude, Codex or both) and what effort to use, and whether to review a paired MR in full or only the boundary between the two.
- Checks the MR out at its head in a `reviews` worktree, and diffs against the MR's own merge base rather than `main`.
- Reads the existing threads first, so a re-review checks earlier findings instead of repeating them.
- Reviews in two waves. Every agent writes a coverage ledger, and the second wave works the ground the first one left unexamined.
- Sends a refutation agent to break each finding, with a browser if one is available, before anything is drafted.
- Shows every draft and thread action in plain English for acceptance, then posts them as one review: drafts first, then one submit with a verdict.

### Project rules

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

### Platforms

| Platform | Client                       | CLI    | Notes                                                                                   |
| -------- | ---------------------------- | ------ | --------------------------------------------------------------------------------------- |
| GitLab   | `scripts/gitlab_comments.py` | `glab` | Draft notes, `bulk_publish` with a reviewer state, resolve on publish                   |
| GitHub   | `scripts/github_comments.py` | `gh`   | Pending review plus a submit event; threads are resolved or reopened after publishing via GraphQL |

The platform is detected from the MR URL, or from the remote URL when you pass `!iid`. Both clients have the same subcommands. `skills/review-mr/platforms/` describes where the two platforms differ.

### Optional companions

| Skill or plugin                    | Used for                                                                            |
| ---------------------------------- | ----------------------------------------------------------------------------------- |
| `browser`                          | In-browser checks by the refuters; without one, refuters check code only and say so |
| `writing-style-guide`, `humanizer` | Comment prose; both ship in this plugin                                             |
| Codex plugin (`openai-codex`)      | The Codex engine                                                                    |

### Tests

```bash
cd plugins/base/skills/review-mr && python3 -m pytest tests
```

## OpenSpec steps

Two steps the [OpenSpec](https://github.com/Fission-AI/OpenSpec) workflow doesn't ship: a grilling session
grounded in the project's specs before a change is proposed (`openspec-grill`), and a check of the plan
against the code before it is applied (`openspec-plan-check`).

### Requires OpenSpec

These two skills build on OpenSpec and are useless without it. They need the `openspec` CLI **2.1 or
newer** (written against 2.1.1) and OpenSpec's own skills, with `verify` added to the default profile:

```bash
npm install -g @fission-ai/openspec@latest   # or: curl -fsSL https://openspec.dev/cli/install.sh | sh
openspec config profile                      # pick the core workflows plus verify
openspec init --scope global --tools claude  # skills once, in ~/.agents/skills, for every project
```

Then `openspec init --scope global --tools claude` inside each project creates its `openspec/` folder.
OpenSpec changes its skills between releases; when a skill here stops matching what OpenSpec does, check
the OpenSpec changelog before anything else.

### Where they fit

| Step | Skill |
| --- | --- |
| Explore the idea | `openspec-explore` |
| Stress-test the decisions | `openspec-grill` |
| Write the change | `openspec-propose` |
| Check the plan against the code | `openspec-plan-check` |
| Revise the plan | `openspec-update-change` |
| Build it | `openspec-apply-change` |
| Check the code against the plan | `openspec-verify-change` |
| Review the MR | `review-mr`, from this plugin, once the MR is open; it posts the review in your name |
| Close it | `openspec-archive-change` |

## Safety Features

This plugin includes comprehensive safety guardrails:

### Blocked Operations

- `rm -rf` targeting home (`~`) or root (`/`) directories
- Hardcoded secrets (API_KEY, TOKEN, PASSWORD patterns 16+ chars)
- Modifications to `.env` files via shell
- `git push --force` without `--force-with-lease`

### Warnings

- Commands containing production keywords
- `git reset --hard` (destructive)
- `git clean` (deletes untracked files)
- Destructive database operations

## Hooks

| Hook                  | Trigger                  | Action                                |
| --------------------- | ------------------------ | ------------------------------------- |
| `safety-guards.sh`    | PreToolUse (Bash)        | Block dangerous commands              |
| `post-edit-format.sh` | PostToolUse (Edit/Write) | Auto-format with prettier/eslint/ruff |

## MCP Servers

This plugin includes pre-configured MCP servers:

| Server          | Type  | Purpose                          |
| --------------- | ----- | -------------------------------- |
| context7        | HTTP  | Up-to-date library documentation |
| nuxt-remote     | HTTP  | Nuxt.js documentation            |
| playwright      | stdio | Browser automation and testing   |

## CLAUDE.md

The included [CLAUDE.md](CLAUDE.md) establishes opinionated defaults for package managers, commit messages, code style, and TypeScript conventions.

## Requirements

- Claude Code
- Git
- Node.js (for npx-based MCP servers and formatters)
- Python 3 and an authenticated `glab` (GitLab) or `gh` (GitHub), for `/base:review-mr`

## Directory Structure

```
base/
├── .claude-plugin/
│   └── plugin.json
├── .mcp.json
├── CLAUDE.md
├── hooks/
│   ├── hooks.json
│   ├── safety-guards.sh
│   └── post-edit-format.sh
├── agents/
├── skills/
└── README.md
```

## License

MIT

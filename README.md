# claude-marketplace

Personal Claude Code marketplace with safety guardrails, auto-formatting, and pre-configured development tools.

## Installation

### From GitHub Repository

```bash
# Add marketplace
/plugin marketplace add Nagell/claude-marketplace

# Install core plugin
/plugin install base-setup@dawidnitka
```

### Quick Setup (All Plugins)

After installing the core plugin, run:

```
/base-setup:plugin-setup
```

This installs all recommended official plugins in one command. Restart Claude Code after installation.

## Plugins

| Plugin                            | Description                                                    |
| --------------------------------- | -------------------------------------------------------------- |
| [base-setup](plugins/base-setup/) | Safety guardrails, auto-formatting, MCP servers, and CLAUDE.md |

## Safety Features

This marketplace includes comprehensive safety guardrails:

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

| Server          | Type  | Purpose                          |
| --------------- | ----- | -------------------------------- |
| context7        | HTTP  | Up-to-date library documentation |
| nuxt-remote     | HTTP  | Nuxt.js documentation            |
| playwright      | stdio | Browser automation and testing   |
| chrome-devtools | stdio | Chrome DevTools automation       |

## Requirements

- Claude Code
- Git
- Node.js (for npx-based MCP servers)

## Versioning & Releases

This repository uses [Release Please](https://github.com/googleapis/release-please) for automated versioning based on [Conventional Commits](https://www.conventionalcommits.org/).

### How it works

1. When you merge a PR to `main`, Release Please analyzes commit messages
2. It creates a Release PR with version bumps and changelog updates
3. Merging the Release PR publishes the new version

### Commit message format

| Prefix | Version Bump | Example |
| ------ | ------------ | ------- |
| `feat:` | Minor (0.1.0 → 0.2.0) | `feat: add new safety hook` |
| `fix:` | Patch (0.1.0 → 0.1.1) | `fix: correct regex in guard` |
| `feat!:` or `BREAKING CHANGE:` | Major (0.1.0 → 1.0.0) | `feat!: redesign hook API` |

### Files updated automatically

- `plugins/<name>/.claude-plugin/plugin.json` - plugin version
- `.claude-plugin/marketplace.json` - marketplace plugin entry version
- `plugins/<name>/CHANGELOG.md` - changelog

## Directory Structure

```
claude-marketplace/
├── .claude-plugin/
│   └── marketplace.json
├── plugins/
│   └── base-setup/
│       ├── .claude-plugin/
│       │   └── plugin.json
│       ├── .mcp.json
│       ├── CLAUDE.md
│       ├── commands/
│       ├── hooks/
│       ├── agents/
│       ├── skills/
│       └── README.md
└── README.md
```

## License

Private - personal use only.

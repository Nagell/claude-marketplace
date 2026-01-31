# base-setup

Foundational Claude Code configuration with safety guardrails, auto-formatting, and pre-configured MCP servers.

## Installation

```bash
# Add marketplace
/plugin marketplace add Nagell/claude-marketplace

# Install plugin
/plugin install base-setup@dawidnitka
```

### Quick Setup (All Plugins)

After installing, run:

```
/base-setup:plugin-setup
```

This installs all recommended official plugins in one command. Restart Claude Code after installation.

## Commands

| Command                    | Description                                                                   |
| -------------------------- | ----------------------------------------------------------------------------- |
| `/base-setup:plugin-setup` | Install recommended official plugins (feature-dev, serena, superpowers, etc.) |

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
| chrome-devtools | stdio | Chrome DevTools automation       |

## CLAUDE.md

The included [CLAUDE.md](CLAUDE.md) establishes opinionated defaults for package managers, commit messages, code style, and TypeScript conventions.

## Requirements

- Claude Code
- Git
- Node.js (for npx-based MCP servers and formatters)

## Directory Structure

```
base-setup/
├── .claude-plugin/
│   └── plugin.json
├── .mcp.json
├── CLAUDE.md
├── commands/
│   └── plugin-setup.md
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

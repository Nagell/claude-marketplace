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

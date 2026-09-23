# dev-extras

Optional developer tooling split out of `base-setup`, so work setups that already ship their own versions can skip it.

## Installation

```bash
/plugin install dev-extras@dawidnitka
```

## Skills

| Skill                             | Description                                                  |
| --------------------------------- | ------------------------------------------------------------ |
| `/dev-extras:start-chrome-debug`  | Start Chrome with remote debugging (WSL/Linux/macOS/Windows) |
| `skill-creator`                   | Create, edit, eval, and benchmark skills                     |

Call either by name, or let Claude reach for them when the task fits.

## MCP Servers

| Server          | Type  | Purpose                                                  |
| --------------- | ----- | -------------------------------------------------------- |
| chrome-devtools | stdio | Chrome DevTools automation, attaches to Chrome on `9222` |

## Requirements

- Claude Code
- Node.js (for the npx-based MCP server)
- Python 3 (for `skill-creator` eval scripts)
- Google Chrome or Chromium (for `start-chrome-debug`)

---
description: Install RTK (token-saving CLI proxy) and context-mode (context window compression plugin) by fetching the latest instructions from GitHub
---

# Setup Token Tools

Install two complementary token-saving tools:

- **RTK** — shell-level CLI proxy that compresses command output before it enters context
- **context-mode** — Claude Code plugin (MCP + hooks) that sandboxes heavy tool calls and compresses context

They operate at different hook layers and do not conflict.

## Instructions

### Step 1 — Fetch latest install instructions

Use WebFetch to retrieve the current README for each tool:

- RTK: `https://github.com/rtk-ai/rtk`
- context-mode: `https://github.com/mksglu/context-mode`

Read the **Installation** sections from both. Do not rely on any hardcoded steps below — follow whatever the READMEs say at the time of running this command.

### Step 2 — Install RTK

Follow the install instructions from the RTK README for the current platform (detect with `uname -r` / `uname -s`).

After installing the binary, run the Claude Code init command (exact flag may differ — check the README):

```bash
rtk init -g
```

Verify:

```bash
rtk --version
rtk gain
```

### Step 3 — Install context-mode and verify

Follow the install instructions from the context-mode README. The commands are typically:

```
/plugin marketplace add mksglu/context-mode
/plugin install context-mode@context-mode
```

Run these as `claude plugin` CLI commands (not inside a session):

```bash
claude plugin marketplace add mksglu/context-mode
claude plugin install context-mode@context-mode
```

Tell the user to **restart Claude Code** to activate context-mode hooks and MCP server, then run the doctor skill to confirm everything is active:

```
/context-mode:ctx-doctor
```

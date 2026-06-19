---
name: plugin-setup
description: Install all recommended plugins and marketplaces
disable-model-invocation: true
---

# Setup Plugins

Install recommended Claude Code plugins and marketplaces with interactive selection.

## Instructions

1. When running as an agent, prefix all `claude` CLI commands with `unset CLAUDECODE &&` to avoid the nested session error.

2. **Step 0 — Windows prerequisite**: Check the platform. If on Windows:
   - Read `~/.claude/settings.json`
   - Check if the `env` object contains `CLAUDE_CODE_GIT_BASH_PATH`
   - If missing, add it:

     ```json
     "env": {
       "CLAUDE_CODE_GIT_BASH_PATH": "C:\\Program Files\\Git\\bin\\bash.exe"
     }
     ```

   - Inform the user the path was set (default: `C:\Program Files\Git\bin\bash.exe`) and ask them to confirm it matches their Git installation before continuing.

3. **Step 1 — Ask install mode**: Use `AskUserQuestion` to ask the user:
   - "Install all (Recommended)" — skip to installing everything from the plugin list below
   - "Let me choose" — proceed to Step 2

4. **Step 2 — Interactive selection** (only if "Let me choose"):
   - Do NOT use `AskUserQuestion` for this step. Instead, for each marketplace group (each `####` heading), print a numbered list of all plugins with their descriptions (the comment above each command).
   - Then ask the user as a plain text message to reply with the numbers or names of plugins they want installed, or "all" / "none" for the group.
   - Wait for the user's reply before moving to the next marketplace group.

   **Derive marketplaces**: Only add marketplaces that have at least one selected plugin.

   **Install order**: Run marketplace commands first, then plugin commands.

   After installation, tell the user to restart Claude Code to activate the plugins.

5. **Step 3 — Global CLAUDE.md instructions**: After installation, offer to save this plugin's `CLAUDE.md` as the user's global Claude instructions (`~/.claude/CLAUDE.md`).
   - Check if `~/.claude/CLAUDE.md` already exists.
   - **If it does NOT exist**: Use `AskUserQuestion` to ask:
     - "Yes, create it (Recommended)" — copy `plugins/base-setup/CLAUDE.md` to `~/.claude/CLAUDE.md`
     - "No, skip" — do nothing
   - **If it DOES exist**: Read both `~/.claude/CLAUDE.md` and `plugins/base-setup/CLAUDE.md`, show their contents to the user for comparison, then use `AskUserQuestion` to ask:
     - "Append to existing (Recommended)" — append the proposed content at the end of the existing file
     - "Replace existing" — overwrite with the proposed content
     - "Skip" — do nothing

6. **Step 4 — Statusline**: Offer to install the bundled statusline (lean single-line: model, folder, branch, context bar, cost).
   - Use `AskUserQuestion` to ask:
     - "Yes, install (Recommended)" — proceed
     - "No, skip" — do nothing
   - If yes:
     - Copy this skill's `scripts/statusline.sh` to `~/.claude/statusline.sh` and make it executable (`chmod +x ~/.claude/statusline.sh`). The script requires `jq`.
     - Read `~/.claude/settings.json` and add the `statusLine` setting (merge into the existing JSON, don't clobber other keys):

       ```json
       "statusLine": {
         "type": "command",
         "command": "~/.claude/statusline.sh"
       }
       ```

     - If `statusLine` already exists, show the current value and ask before overwriting.
     - Tell the user to restart Claude Code to see the statusline.

## Plugin List

### Marketplaces

```bash
/plugin marketplace add claude-plugins-official
/plugin marketplace add onmax/nuxt-skills
```

### Plugins

#### claude-plugins-official

```bash
# Feature development workflow with exploration, architecture, and review agents
/plugin install feature-dev@claude-plugins-official
# Create hooks to prevent unwanted behaviors by analyzing patterns
/plugin install hookify@claude-plugins-official
# PR review agents for comments, tests, error handling, and code quality
/plugin install pr-review-toolkit@claude-plugins-official
# Complete software development workflow with composable skills
/plugin install superpowers@claude-plugins-official
# Iterative development loops with self-referential AI
/plugin install ralph-loop@claude-plugins-official
```

#### nuxt-skills

```bash
# Vue, Nuxt, and NuxtHub skills (vue, vueuse, nuxt, nuxt-modules, nuxt-content,
# nuxt-ui, nuxt-seo, nuxt-studio, nuxt-better-auth, nuxthub, reka-ui, vite,
# vitest, pnpm, tsdown, ts-library, motion, tresjs, and more) as one plugin
/plugin install nuxt-skills@nuxt-skills
```

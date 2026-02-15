---
description: Install all recommended plugins and marketplaces
---

# Setup Plugins

Install recommended Claude Code plugins and marketplaces with interactive selection.

## Instructions

1. When running as an agent, prefix all `claude` CLI commands with `unset CLAUDECODE &&` to avoid the nested session error.

2. **Step 1 — Ask install mode**: Use `AskUserQuestion` to ask the user:
   - "Install all (Recommended)" — skip to installing everything from the plugin list below
   - "Let me choose" — proceed to Step 2

3. **Step 2 — Interactive selection** (only if "Let me choose"):
   - Do NOT use `AskUserQuestion` for this step. Instead, for each marketplace group (each `####` heading), print a numbered list of all plugins with their descriptions (the comment above each command).
   - Then ask the user as a plain text message to reply with the numbers or names of plugins they want installed, or "all" / "none" for the group.
   - Wait for the user's reply before moving to the next marketplace group.

4. **Derive marketplaces**: Only add marketplaces that have at least one selected plugin.

5. **Install order**: Run marketplace commands first, then plugin commands.

6. After installation, tell the user to restart Claude Code to activate the plugins.

7. **Step 6 — Global CLAUDE.md instructions**: After installation, offer to save this plugin's `CLAUDE.md` as the user's global Claude instructions (`~/.claude/CLAUDE.md`).
   - Check if `~/.claude/CLAUDE.md` already exists.
   - **If it does NOT exist**: Use `AskUserQuestion` to ask:
     - "Yes, create it (Recommended)" — copy `plugins/base-setup/CLAUDE.md` to `~/.claude/CLAUDE.md`
     - "No, skip" — do nothing
   - **If it DOES exist**: Read both `~/.claude/CLAUDE.md` and `plugins/base-setup/CLAUDE.md`, show their contents to the user for comparison, then use `AskUserQuestion` to ask:
     - "Append to existing (Recommended)" — append the proposed content at the end of the existing file
     - "Replace existing" — overwrite with the proposed content
     - "Skip" — do nothing

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
# Vue 3 components, composables, and testing patterns
/plugin install vue@nuxt-skills
# Nuxt 4+ server routes, routing, middleware, and configuration
/plugin install nuxt@nuxt-skills
# Nuxt module creation with defineNuxtModule and Kit utilities
/plugin install nuxt-modules@nuxt-skills
# Nuxt Content v3 typed collections, queryCollection API, and MDC
/plugin install nuxt-content@nuxt-skills
# Headless Vue components with accessibility and styling patterns
/plugin install reka-ui@nuxt-skills
# TypeScript library authoring, exports, build tooling, and releases
/plugin install ts-library@nuxt-skills
# Reactive utilities for state, browser APIs, sensors, and animations
/plugin install vueuse@nuxt-skills
# Unit/integration testing with Vitest configuration and mocking
/plugin install vitest@nuxt-skills
# Vite build config, plugin API, SSR, and Rolldown migration
/plugin install vite@nuxt-skills
# pnpm workspace setup, catalogs, CLI commands, and CI config
/plugin install pnpm@nuxt-skills
```

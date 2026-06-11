---
name: coach-setup
description: Install coding-tutor + register the post-commit learning coach hook.
disable-model-invocation: true
---

# Coach Setup

Install the `coding-tutor` plugin and its marketplace, then point the user at coding-tutor's own onboarding.

## Instructions

1. When running as an agent, prefix `claude` CLI calls with `unset CLAUDECODE &&` to avoid the nested-session error.

2. **Step 1 — Confirm.** Use `AskUserQuestion` with two options:
   - "Install (Recommended)" — proceed
   - "Cancel" — exit

3. **Step 2 — Install.** Run the marketplace command first, then the plugin command:

   ```bash
   # Marketplace (add only if not already added — /plugin is idempotent enough)
   /plugin marketplace add EveryInc/compound-engineering-plugin

   # Plugin
   /plugin install coding-tutor@compound-engineering-plugin
   ```

4. **Step 3 — Activate.** Tell the user to run `/reload-plugins` (a Claude Code CLI built-in that activates pending plugin changes in the current session without a full restart). Note that this command is CLI-only — it may not be exposed in the VS Code or Cursor extension command palette. If the user is in those editors and the command isn't recognised, instruct them to fully close and reopen Claude Code as the fallback.

5. **Step 4 — Next steps.** After plugins reload (or after the restart fallback), instruct the user to run a `/teach-me` call to trigger coding-tutor's first-run onboarding (it asks 3 questions and writes `~/coding-tutor-tutorials/learner_profile.md`):

   > Run `/teach-me <something you want to learn>` once. Coding-tutor will introduce itself, ask 3 short questions, and create your learner profile. After that, every git commit fires this plugin's hook and Claude will consider offering more `/teach-me` calls based on what's in that profile.

6. **Step 5 — Optional calibration snippet.** Offer to print the calibration snippet (see this plugin's README) so they can paste it into their profile after coding-tutor created it. Use `AskUserQuestion`:
   - "Yes, show me the snippet" — print it
   - "No, I'll edit the profile myself later" — exit

Do not write to `~/coding-tutor-tutorials/learner_profile.md` directly. That file belongs to `coding-tutor`. We only provide guidance.

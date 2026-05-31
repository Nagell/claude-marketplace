# coding-tutor-coach

A thin coach layer around [`coding-tutor`](https://github.com/EveryInc/compound-engineering-plugin). Two surfaces:

- **`/coach-setup`** — installs the `compound-engineering-plugin` marketplace and the `coding-tutor` plugin, then points you at coding-tutor's own onboarding.
- **A post-commit hook** — fires after every real `git commit`, reads your `~/coding-tutor-tutorials/learner_profile.md`, and nudges Claude to consider offering `/teach-me`. Claude decides whether to offer.

## Requires coding-tutor

This plugin only nudges — the actual teaching comes from the `coding-tutor` plugin. Without it installed, the `/teach-me` command Claude offers won't exist. Run `/coach-setup` to install `coding-tutor` and its marketplace.

## Your learning profile stays yours

When you run `/teach-me` for the first time, `coding-tutor` asks you 3 questions and saves your answers to `~/coding-tutor-tutorials/learner_profile.md`. That file belongs to `coding-tutor`.

This plugin **only reads** that file — to remind Claude how you like to learn — and **never changes it**. Uninstalling this plugin leaves `~/coding-tutor-tutorials/` exactly as it was.

## Install + use

```bash
# One-time setup
/plugin install coding-tutor-coach@dawidnitka    # this plugin
/coach-setup                                     # installs coding-tutor + reloads
# (run /reload-plugins, or restart Claude Code)
/teach-me <something>                            # triggers coding-tutor's onboarding
# (coding-tutor asks 3 questions, writes ~/coding-tutor-tutorials/learner_profile.md)
# (optional) paste the calibration snippet below into the profile

# Daily use — nothing to invoke
git commit -m "feat: ..."                        # hook fires; Claude considers /teach-me

# Manual learning
/teach-me <topic>
/quiz-me
```

## Optional calibration snippet

Want explicit per-domain bars? Paste this anywhere into your `~/coding-tutor-tutorials/learner_profile.md` after coding-tutor creates it (coding-tutor reads the whole file). Optional — the hook works without it; Claude falls back to general judgement.

```markdown
## Calibration rules

- **Frontend (Vue / TS / Nuxt):** high bar. Offer only when the change
  introduces a new pattern, library, or architectural idea. Skip routine
  refactors, bugfixes, copy / locale tweaks, tests, dependency bumps.
  Target: ~1 offer per 10 FE commits.
- **Backend (Python / Django / DRF):** low bar. Offer after most commits
  that touch backend code. Stack is new; frequent exposure is the goal.
  Target: ~1 offer per 2–3 BE commits.
- **Mixed commits:** weight by lines changed; ties → backend rules.
- **Config / CI / docs-only:** never offer.
- **Max 1 offer per session**, regardless of commit count.
```

## How the hook decides what to fire on

The hook runs on every Claude Code `Bash` tool call but returns in ~1–2ms unless the command contains the literal string `git commit`. It skips `--dry-run` and `--amend`. It stays silent when the profile is missing (printing a one-liner pointing you at `/teach-me`).

**Assumption pinned here:** the hook inspects the committed command via the PostToolUse JSON payload on stdin (`tool_input.command`), falling back to `$CLAUDE_TOOL_INPUT`. Only substring matching is used, so no JSON parser is required. If Claude Code changes this contract upstream, the matching in `hooks/post-commit-nudge.sh` is where to look.

# coding-tutor

Your personal AI tutor that creates tutorials tailored to you — using real code from your projects, building on what you already know, and tracking your progress over time. Plus a commit-triggered nudge that reminds Claude to offer a lesson when you ship something worth learning from.

## Vendored from upstream

The teaching half of this plugin is vendored from [`coding-tutor`](https://github.com/EveryInc/compound-engineering-plugin) (MIT, © 2025 Every; original author Nityesh Agarwal) at version `1.3.0`. Upstream **removed the plugin** on 2026-06-12, so this is now a maintained fork rather than a tracked mirror — there is no newer upstream release to refresh from. The original MIT `LICENSE` is kept in this directory. The post-commit hook and calibration guidance below are local additions, not part of upstream.

## Install

```bash
/plugin install coding-tutor@dawidnitka
# then run /reload-plugins, or restart Claude Code
/teach-me <something you want to learn>
```

The first `/teach-me` runs coding-tutor's onboarding: it asks 3 short questions and writes your learner profile to `~/coding-tutor-tutorials/learner_profile.md`.

## Commands

- `/teach-me` — learn something new, anchored in your actual codebase
- `/quiz-me` — test retention with spaced repetition
- `/sync-tutorials` — back your tutorials up to a private GitHub repo

## Commit-triggered coaching (the hook)

A `PostToolUse` hook fires after every real `git commit` (it skips `--dry-run` and `--amend`, and returns in a few milliseconds on non-commits). It reads `~/coding-tutor-tutorials/learner_profile.md` and nudges Claude to **consider** offering `/teach-me` based on what changed. Claude decides whether to actually offer — nothing is forced, and it stays silent if it decides not to.

If the profile doesn't exist yet, the hook simply points you at `/teach-me` to create one.

## Optional calibration snippet

Want explicit per-domain bars for how often the hook should prompt? Paste this anywhere into your `~/coding-tutor-tutorials/learner_profile.md` after it's created (coding-tutor reads the whole file). Optional — without it, Claude falls back to general judgement.

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

## Tell it your level

The onboarding interview captures your background as free prose — there's no built-in per-language skill field. But the tutor reads the whole profile and calibrates teaching depth from it, so you can declare your proficiency explicitly. Paste a block like this anywhere in your `~/coding-tutor-tutorials/learner_profile.md`:

```markdown
## My proficiency
- TypeScript / Vue / Nuxt: advanced — go deep, skip the basics
- Python / Django: beginner — explain fundamentals, more scaffolding
- Rust: none yet — start from zero
```

This steers *how* a tutorial is pitched (depth, assumed knowledge), which is separate from the calibration rules above that steer *how often* the hook offers one.

## Storage

Tutorials and your learner profile live at `~/coding-tutor-tutorials/`, auto-created on first use and shared across all your projects. The hook only **reads** that directory; it never writes to it. Uninstalling this plugin leaves `~/coding-tutor-tutorials/` untouched.

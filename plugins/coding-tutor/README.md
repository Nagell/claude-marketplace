<a id="readme-top"></a>

# coding-tutor

A personal tutor that builds tutorials and drills from real code in your projects, starts from what you already know and tracks your progress over time. A commit hook offers a drill or a lesson when you ship something worth learning from.

<details>
  <summary>Table of Contents</summary>
  <ol>
    <li><a href="#installation">Installation</a></li>
    <li><a href="#commands">Commands</a></li>
    <li><a href="#commit-triggered-coaching">Commit-triggered coaching</a></li>
    <li>
      <a href="#tuning-the-tutor">Tuning the tutor</a>
      <ul>
        <li><a href="#how-often-it-offers">How often it offers</a></li>
        <li><a href="#how-deep-it-goes">How deep it goes</a></li>
      </ul>
    </li>
    <li><a href="#storage">Storage</a></li>
    <li><a href="#vendored-from-upstream">Vendored from upstream</a></li>
  </ol>
</details>

<!-- INSTALLATION -->

## Installation

```bash
/plugin install coding-tutor@dawidnitka
# then run /reload-plugins, or restart Claude Code
/teach-me <something you want to learn>
```

The first `/teach-me` runs the onboarding: three short questions, and the answers become your learner profile at `~/coding-tutor-tutorials/learner_profile.md`.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- COMMANDS -->

## Commands

| Command           | What it does                                                                        |
| ----------------- | ----------------------------------------------------------------------------------- |
| `/teach-me`       | A tutorial anchored in your own codebase, ending with an optional drill             |
| `/train-me`       | A hands-on drill: rewrite a blanked slice of real code, judged against what shipped |
| `/quiz-me`        | A spaced-repetition quiz on what you learned before                                 |
| `/sync-tutorials` | Back your tutorials up to a private GitHub repo                                     |

Quizzes check what you can explain, drills check what you can write. Both use spaced repetition, and drills keep their own log in `training_log.md`.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- COMMIT-TRIGGERED COACHING -->

## Commit-triggered coaching

A `PostToolUse` hook runs after every real `git commit` Claude makes. It returns in milliseconds on anything else, and skips `--dry-run`, `--amend`, commits in the tutorials repo itself and commits that did not move `HEAD`, so a failed commit never reports the previous one's files.

On a real commit it passes Claude the subject, the diffstat and any newly added import lines. Claude then:

1. **Skips the trivial** without a word: formatting or lint only, lockfile and dependency bumps, generated files, pure renames and reverts.
2. **Asks right away** with a popup named after the topic: **Train** (write a slice yourself, the default), **Teach** (a tutorial on it) or **Skip**.
3. **Runs what you picked.** Train may resurface an overdue past drill instead of a fresh one. Skip, or closing the popup, ends it for that commit.

There is no per-session limit, but a concept already drilled or skipped in the session is not offered again. Without a learner profile, the hook only points you at `/teach-me`.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- TUNING THE TUTOR -->

## Tuning the tutor

Both snippets below are optional and go anywhere in `~/coding-tutor-tutorials/learner_profile.md` once it exists. The tutor reads the whole file.

### How often it offers

Per-domain bars for the commit hook. Without them, Claude falls back to general judgement.

```markdown
## Calibration rules

- **Frontend (Vue / TS / Nuxt):** high bar. Offer only when the change
  introduces a new pattern, library or architectural idea. Skip routine
  refactors, bugfixes, copy / locale tweaks, tests and dependency bumps.
  Target: ~1 offer per 10 FE commits.
- **Backend (Python / Django / DRF):** low bar. Offer after most commits
  that touch backend code. The stack is new, and frequent exposure is the goal.
  Target: ~1 offer per 2-3 BE commits.
- **Mixed commits:** weight by lines changed; ties go to the backend rules.
- **Config / CI / docs only:** never offer.
- **Max 1 offer per session**, regardless of commit count.
```

### How deep it goes

The onboarding stores your background as free prose, with no per-language level field. Declare your levels yourself, and the tutor pitches each tutorial to match:

```markdown
## My proficiency

- TypeScript / Vue / Nuxt: advanced - go deep, skip the basics
- Python / Django: beginner - explain fundamentals, more scaffolding
- Rust: none yet - start from zero
```

Calibration steers how often the hook offers something, and proficiency steers how a tutorial is pitched.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- STORAGE -->

## Storage

Tutorials, the training log and your learner profile live in `~/coding-tutor-tutorials/`. The folder is created on first use and shared across all your projects. The hook only reads it, and uninstalling the plugin leaves it untouched.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- VENDORED FROM UPSTREAM -->

## Vendored from upstream

The teaching half is vendored from [`coding-tutor`](https://github.com/EveryInc/compound-engineering-plugin) (MIT, © 2025 Every; original author Nityesh Agarwal) at version `1.3.0`. Upstream removed the plugin on 2026-06-12, so this is now a maintained fork with no newer release to refresh from. The original MIT `LICENSE` stays in this directory.

Local additions, not part of upstream: the commit hook, training mode (`/train-me` and the drill log) and the tuning guidance above.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

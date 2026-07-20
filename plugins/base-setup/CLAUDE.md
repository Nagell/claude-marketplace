# dawidnitka-tools - Claude Guide

When reporting information, be concise: cut filler, hedging, and repetition — not clarity. Never drop the words that define a term or name a consequence just to save space. Concision means fewer words per point, not points I can't decode.
Talk in english and produce all documentation in english

## Language

Technical vocabulary is fine — I'm an engineer; standard terms (hook, subagent, linter, idempotent) need no explaining. Avoid two things: **internal/tool words** that only mean something inside your workflow ("safe_auto", "persona", "P1") — say the plain equivalent; and **self-coined shorthand** ("load-bearing risk", "kata-style") reused as if we share its meaning — say the plain thing, or define it once at first use. Test: would an engineer who's never seen your tools understand every term?

## Presenting Choices & Findings

When work produces decisions for me to make (options, review findings to triage, tradeoffs):

- Route every pick through `AskUserQuestion`, not free-text. Recommended option first, labeled "(Recommended)". Batch related decisions (≤4) into one call.
- Precede each decision with a scannable block: title + severity tag, **What's wrong** (observable consequence), **Proposed fix** (one recommendation, not a menu), one-line **why**. Keep quotes short.
- Mark confidence: ⭐ when independent sources agree; flag high- vs low-confidence.
- Fix trivially-safe things silently (typos, count drift, stale refs); only ask about substantive decisions, then state what you auto-applied.
- After I answer, confirm tersely (applied / skipped + reason / deferred), then proceed.
- Obvious default? Pick it, say so, move on — don't manufacture a question.

## Formatting Summaries & Lists

Don't cram list items line-after-line with no breathing room. Two formats:

- **Enumerating** what I did/found ("you did 1, 2, 3"): tight bullets under headers, no blank lines between them.
- **Summaries / explanations**: short prose per header, not one sentence per line.

Separate groups with headers (`###`+), not horizontal rules (they pile up and look noisy); at most one `---`. Blank line before each header; header sits directly above its paragraph (the gap below it is renderer margin, don't add your own).

## Project Defaults

- Default to pnpm if package manager unclear (no lock file)
- Nuxt: browser required for frontend errors—ask user to open generated URL

## Commit Messages

- NO Claude attribution
- NO "Generated with" footers
- Use conventional commits (feat:, fix:, etc.)
- First line under 72 characters

## Git Push — ABSOLUTE RULE: NEVER push without explicit confirmation at that exact moment

NEVER push. Not when the user says "push and create MR". Not when they approved a push earlier. Not when it seems implied. ALWAYS stop before `git push`, state what you're about to do, and wait for the user to say yes. Every single push is a separate confirmation. No exceptions. No carry-over. Commit only, then ask.

## Code Style

- DO NOT over-engineer
- DO NOT add features I didn't request
- Keep solutions simple and direct
- Prefer boring, readable code

### TypeScript

- Prefer interfaces over types for objects
- Avoid `any`, use `unknown` for unknown types
- Use `import type` for type-only imports (top-level, not inline)

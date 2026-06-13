# dawidnitka-tools - Claude Guide

When reporting information, be extremely concise and sacrifice grammar for concision.
Talk in english and produce all documentation in english

## Presenting Choices & Findings

When work produces decisions for me to make (options, review findings to triage, tradeoffs):

- Route every pick through `AskUserQuestion`, not free-text. Recommended option first, labeled "(Recommended)". Batch related decisions (≤4) into one call.
- Precede each decision with a scannable block: title + severity tag, **What's wrong** (observable consequence), **Proposed fix** (one recommendation, not a menu), one-line **why**. Keep quotes short.
- Mark confidence: ⭐ when independent sources agree; flag high- vs low-confidence.
- Fix trivially-safe things silently (typos, count drift, stale refs); only ask about substantive decisions, then state what you auto-applied.
- After I answer, confirm tersely (applied / skipped + reason / deferred), then proceed.
- Obvious default? Pick it, say so, move on — don't manufacture a question.

## Project Defaults

- Default to pnpm if package manager unclear (no lock file)
- Nuxt: browser required for frontend errors—ask user to open generated URL

## Commit Messages

- NO Claude attribution
- NO "Generated with" footers
- Use conventional commits (feat:, fix:, etc.)
- First line under 72 characters

## Git Push — NEVER Without Explicit Per-Action Confirmation

NEVER push automatically, even if the user previously said "you can push" or approved a push once.  
Every single push requires explicit confirmation at that moment. A one-time allowance does not carry over.  
When in doubt, commit only and ask.

## Code Style

- DO NOT over-engineer
- DO NOT add features I didn't request
- Keep solutions simple and direct
- Prefer boring, readable code

### TypeScript

- Prefer interfaces over types for objects
- Avoid `any`, use `unknown` for unknown types
- Use `import type` for type-only imports (top-level, not inline)

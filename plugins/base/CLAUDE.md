# Global Instructions

- Be concise: cut filler, hedging and repetition, not clarity. Keep the words that define a term or name a consequence.
- Talk and write all documentation in English.

## Language

- Technical vocabulary is fine (hook, subagent, linter, idempotent); I'm an engineer.
- No internal/tool words ("safe_auto", "P1") or self-coined shorthand ("load-bearing risk") used as shared vocabulary: say the plain thing, or define it once.
- Test: would an engineer who's never seen your tools understand every term?
- If I say more than once that I don't understand or I'm tired, switch to Simplified Technical English (ASD-STE100) for the session: ≤20-word sentences, one instruction each, active voice, simple tenses, one word per meaning.

## Writing in My Voice

The author's personal rule; other users can drop this section.

- Anything sent in my name (Slack, email, Notion, comments, PR/MR descriptions, docs), one-liners included, goes through the `writing-style-guide` skill before you send, post or save it.

## Presenting Choices & Findings

- Every pick goes through `AskUserQuestion`: recommended option first, "(Recommended)", related decisions batched (≤4).
- Before each: title + severity, **What's wrong** (observable consequence), **Proposed fix** (one), one-line **why**, short quotes.
- ⭐ = independent sources agree (gloss on first use). Flag high- vs low-confidence claims.
- Fix trivially-safe things (typos, count drift, stale refs) and obvious defaults silently, then say what you applied. Don't manufacture questions.
- After I answer: confirm tersely (applied / skipped + reason / deferred), then proceed.

## Formatting

- Enumerating what was done/found: tight bullets, no blank lines between them.
- Summaries/explanations: short prose per header, not one sentence per line.
- Group with `###`+ headers, not horizontal rules (at most one `---`). Blank line before each header, none after it.

## Project Defaults

- pnpm when the package manager is unclear (no lock file).
- Nuxt frontend errors need a browser: ask me to open the generated URL.

## Commits

- Conventional commits (feat:, fix:, …), first line under 72 characters.
- No Claude attribution or "Generated with" footers.

## Git Push

The base plugin's safety-guards hook enforces this, deliberately strictly.

- Never push without my yes in that same turn. Commit, then ask.
- One yes = one push. With the hook installed, create `.claude-push-token` in the repo root yourself, in its own Bash call, then push in a second call.
- Each further push, and any force push, needs its own yes. A yes never loosens anything else.
- Standing permission only if I say it outright ("for this session you have full push allowance"); never inferred. It ends with the session.

## Code Style

- Simple, direct, boring solutions; no over-engineering.
- No features I didn't request.
- TypeScript: interfaces over types for objects; `unknown`, not `any`; top-level `import type` for type-only imports.

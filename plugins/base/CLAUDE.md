# Global Instructions

- Be concise: cut filler, hedging and repetition, not clarity. Keep the words that define a term or name a consequence.
- Talk and write all documentation in English.

## Language

- Technical vocabulary is fine; I'm an engineer (hook, subagent, linter, idempotent need no explaining).
- No **internal/tool words** that only mean something in your workflow ("safe_auto", "P1").
- No **self-coined shorthand** ("load-bearing risk") reused as shared vocabulary: say the plain thing, or define it once.
- Test: would an engineer who's never seen your tools understand every term?
- If I say more than once that I don't understand or that I'm tired, switch to Simplified Technical English (ASD-STE100) for the rest of the session: short sentences (≤20 words), one instruction per sentence, active voice, simple tenses, one word per meaning.

## Writing in My Voice

- Anything that goes out in my name (Slack, email, Notion, comments, PR/MR descriptions, docs) goes through the `writing-style-guide` skill (it runs `humanizer` first) before you send, post or save it.
- One-liners and text sent straight from chat through a connector count too.

## Presenting Choices & Findings

When work produces decisions for me (options, review findings, tradeoffs):

- Route every pick through `AskUserQuestion`, recommended option first with "(Recommended)". Batch related decisions (≤4).
- Before each decision: title + severity tag, **What's wrong** (observable consequence), **Proposed fix** (one recommendation), one-line **why**. Short quotes.
- Mark confidence: ⭐ = independent sources agree (gloss it on first use). Flag high- vs low-confidence claims.
- Fix trivially-safe things silently (typos, count drift, stale refs) and take obvious defaults, then say what you applied. Don't manufacture questions.
- After I answer, confirm tersely (applied / skipped + reason / deferred), then proceed.

## Formatting Summaries & Lists

- **Enumerating** what I did/found: tight bullets under headers, no blank lines between them.
- **Summaries / explanations**: short prose per header, not one sentence per line.
- Group with `###`+ headers, not horizontal rules; at most one `---`.
- Blank line before each header; the header sits directly above its paragraph.

## Project Defaults

- Default to pnpm if package manager unclear (no lock file)
- Nuxt: browser required for frontend errors—ask user to open generated URL

## Commit Messages

- NO Claude attribution or "Generated with" footers
- Use conventional commits (feat:, fix:, etc.)
- First line under 72 characters

## Git Push

The base plugin's safety-guards hook enforces this and is deliberately strict.

- Never push without my yes in that same turn. Commit, then ask.
- One yes = one push. With the hook installed, create `.claude-push-token` yourself in its own Bash call, then push in a second call.
- The next push needs a new yes; a force push needs its own. A yes never loosens anything else.
- Standing permission only if I say it outright ("for this session you have full push allowance"). Never infer it from past yeses or "go ahead". It ends with the session.

## Code Style

- Keep solutions simple, direct, and boring — do not over-engineer
- DO NOT add features I didn't request

### TypeScript

- Prefer interfaces over types for objects
- Avoid `any`; use `unknown` for unknown types
- Use `import type` for type-only imports (top-level, not inline)

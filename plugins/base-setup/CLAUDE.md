# dawidnitka-tools - Claude Guide

When reporting information, be extremely concise and sacrifice grammar for concision.
Talk in english and produce all documentation in english

## Project Defaults

- Default to pnpm if package manager unclear (no lock file)
- Nuxt: browser required for frontend errors—ask user to open generated URL

## Commit Messages

- NO Claude attribution
- NO "Generated with" footers
- Use conventional commits (feat:, fix:, etc.)
- First line under 72 characters

## Code Style

- DO NOT over-engineer
- DO NOT add features I didn't request
- Keep solutions simple and direct
- Prefer boring, readable code

### TypeScript

- Prefer interfaces over types for objects
- Avoid `any`, use `unknown` for unknown types
- Use `import type` for type-only imports (top-level, not inline)

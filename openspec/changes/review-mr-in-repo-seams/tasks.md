# Tasks

## 1. Route, event and message seams

- [x] 1.1 Widen step 2 of `references/agent-brief.md` and "What finishes the job" to routes (URL derived from the route file's path), event names and message types, comparing what each side sends and reads; verify by reading the brief.
- [x] 1.2 Update "Cut the slices" and "Who runs in wave 1" in `SKILL.md`: a changed route stays with its changed callers within the hard limit; seams cover routes, events and messages; verify by reading SKILL.md.

## 2. Server-rendering lens

- [x] 2.1 Add `scripts/find_server_rendering.py` (framework table: Nuxt `ssr: false`, Next.js `output: 'export'`) with `tests/test_find_server_rendering.py`; verify with `pytest`.
- [x] 2.2 Add the server-rendering lens to "Wave 1: breadth" in `SKILL.md` and to the agent brief, run the script once before the briefs, and document the `## Server rendering` override in "Project rules: the format"; verify by reading SKILL.md.

## 3. Verification

- [ ] 3.1 Add a route-and-caller drift fixture under `tests/fixtures/route-drift/` (server requires a field the page doesn't send) and run a slice owner with the new brief on it; done when the owner reports the drift.

## Workflow follow-up

- Plan check, review and archive after the PR is reviewed.

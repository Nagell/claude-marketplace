# Proposal

## Why

`review-mr` checks the boundary between two halves of a change only when they ship as two MRs in two repos. When both halves live in one repo, as with a Nuxt or Next.js server route and the page that calls it, nobody compares them: each slice owner greps the users of changed exports, but a route is reached by a URL string, not an import, so the grep finds nothing. A server that starts requiring a field the page never sends passes review. Separately, no lens covers the bugs that only exist when an app renders on the server, such as a hydration mismatch or state shared between requests.

## What Changes

- The seam rule widens from changed exports to changed exports, routes, event names and message types. A slice owner finds every user of a changed route by its URL (derived from the route file's path for file-based routing), and of an event or message by its name, in any slice, and compares what each side sends and reads.
- Slicing keeps a changed route together with the changed files that call it, within the existing size limit.
- A new built-in server-rendering lens: hydration mismatches, browser-only globals used during server render, module-level state shared between requests, secrets in public runtime config, and clashing or doubled data-fetch keys. It applies only when a framework config shows the app renders on the server. Repos that don't get no extra brief text.
- A rules file can force the lens on or off per repo, for setups where detection guesses wrong.
- Still no cross-file agent besides the counterpart contract agent.
- The step 0 counterpart question (contract check or full review of both) is asked only when the repo's rules have a `## Counterpart` section. `find_rules.py` reports it as `counterpart`. Without one, the dialog has two questions and step 1a is skipped, unless the user passed `--both` or a second MR URL.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `review-mr-agents`: the seam requirement covers routes, events and message names; slicing keeps a route with its callers; new requirements for the server-rendering lens and its rules override; the step 0 dialog asks the counterpart question only when the rules name a counterpart.

## Impact

- `plugins/base/skills/review-mr/SKILL.md`: step 0, slicing, wave 1 lenses, the rules format section.
- `plugins/base/skills/review-mr/scripts/find_rules.py`: the `counterpart` field.
- `plugins/base/skills/review-mr/references/agent-brief.md`: the seam step and the server-rendering lens text.
- New `plugins/base/skills/review-mr/scripts/find_server_rendering.py` with tests, which reads framework configs at the reviewed head.
- A fixture under `plugins/base/skills/review-mr/tests/fixtures/` for a route and caller that drift apart.
- Repos with no server-rendering app see no extra brief text and no change in agent count; the seam step in the brief is longer for every repo.

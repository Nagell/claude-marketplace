# Proposal

## Why

The model and effort for each review role live only in the role table in `review-mr`'s `SKILL.md`. The `## Models` section in `CLAUDE.md` now states the same picks as plain lines, and the planned models mode updates those lines. Without this change a new pick in `CLAUDE.md` has no effect on reviews.

## What Changes

- Before spawning agents, `review-mr` reads the `## Models` section from `~/.claude/CLAUDE.md`, then from the repo's `CLAUDE.md`. When both have the same line, the repo's line wins.
- A `- Review slices:`, `- Review refuters:` or `- Review with --fast:` line sets the model and effort for that role. Haiku, Sonnet, Opus and Fable map to the Agent model alias; `run.json` keeps the full name from the line.
- When no such line exists, the role table in `SKILL.md` stays the fallback.
- `run.json` records `model_source` per agent: `user`, `repo` or `table`.

## Capabilities

### New Capabilities

### Modified Capabilities
- `review-mr-agents`: the "Model and effort per role" requirement reads `## Models` lines first and keeps the table as the fallback.

## Impact

`plugins/base/skills/review-mr/SKILL.md` ("Agents, models and effort" and the `run.json` example). No script or test changes.

# Tasks

## 1. Read models from CLAUDE.md

- [x] 1.1 In `plugins/base/skills/review-mr/SKILL.md`, "Agents, models and effort": add the `## Models` lookup (user file, then repo file, repo wins), the three review lines and their roles, the alias mapping, and the role table as fallback; verify with `grep -n "## Models" SKILL.md`
- [x] 1.2 Add `model_name` and `model_source` to the `run.json` agent example and its notes; verify with `grep -n model_source SKILL.md`

## 2. Integration

- [x] 2.1 Run `uvx pytest plugins/base/skills/review-mr/tests` and `openspec validate --all --strict`; verify both pass

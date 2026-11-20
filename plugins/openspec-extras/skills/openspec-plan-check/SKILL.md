---
name: openspec-plan-check
description: Check an OpenSpec change's plan against the code it will touch, after propose or update and before apply. Finds plans that rest on files, functions, APIs or behaviour that don't exist or work differently, tasks that miss part of the work, work that is already done, and clashes with existing specs. Use when the user says "openspec plan check", "check the plan against the code", "is this change still valid" or before running openspec-apply-change. Read-only; fixes go through openspec-update-change.
compatibility: Requires the openspec CLI >= 2.1 and its skills (openspec-update-change, openspec-apply-change), see the plugin README.
dependencies:
  - openspec-update-change
---

# OpenSpec plan check

`openspec-verify-change` checks code against the plan after apply. This is the other direction, before apply:
does the plan match the code as it is today? A plan written from memory or from an old branch fails here
cheaply, instead of halfway through `tasks.md`.

Read-only: never edit artifacts or code in this skill.

## 1. Pick the change

Run `openspec context --json` (add `--store <id>` when the user names a store) and use `root.path`. Then
`openspec list --json`: take the change the user named, or the only active one; with several and none named,
ask which one. Read every artifact `openspec status --change <name> --json` reports, plus
`openspec/config.yaml` for project context and rules.

Run `openspec validate <name> --strict --json` first. A change that fails validation gets those errors
reported before anything else.

## 2. No code yet?

When the repo has no code the change touches (a new project, a plan written before the code), say so and
check only what can be checked: the artifacts agree with each other, every requirement has a task that
delivers it and a scenario that tests it, and nothing contradicts the existing specs
(`openspec list --specs --json`, `openspec show <spec> --json`). Then stop.

## 3. Extract the claims

List every concrete thing the plan takes for granted about the code, each with the artifact and line it comes
from:

- **Exists:** a file, module, function, type, endpoint, config key, table or dependency the plan names.
- **Behaves:** "X currently does Y", "Z is called from A", "the API returns B".
- **Covers:** each requirement and scenario in the delta specs, and which task delivers it.
- **Order:** a task that needs another task's output, or a migration before a deploy.

## 4. Check them against the code

For a small change, check the claims yourself. For a larger one, dispatch sub-agents in parallel, one per
area of the codebase, each with its list of claims and the instruction to answer every claim with
**holds**, **wrong** (with the real behaviour and a `file:line`) or **can't tell**. Facts only; they don't
judge the plan.

Also look for what the plan doesn't say:

- code that already does part of the change (a task that would duplicate it);
- callers, tests, docs or migrations the change will break that no task mentions;
- an existing spec the change modifies without a delta for it.

## 5. Report

One finding per problem, worst first:

- **Blocks apply:** a wrong claim a task depends on, a missing prerequisite, a clash with a spec.
- **Gap:** work the change needs that no task covers.
- **Stale:** a claim that is wrong but harmless, or work that is already done.

Each finding names the artifact and line, the code `file:line`, what the plan says and what the code does,
and one proposed fix to the plan. Then say plainly whether the change is ready for `openspec-apply-change`.

When there are findings, offer to fold the fixes into the change with `openspec-update-change`, and wait for
a yes. When the session's instructions say decisions go through a question tool (for example
`AskUserQuestion`), put the fixes to the user with it.

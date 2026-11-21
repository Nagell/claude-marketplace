---
name: openspec-grill
description: Grill the user about an idea or an OpenSpec change before it is proposed or revised, grounded in the project's OpenSpec specs, changes and config. Use when the user says "openspec grill", "grill this change", "grill me before we propose", or wants to stress-test a plan in a project that uses OpenSpec. Ends by handing the settled decisions to openspec-propose (new work) or openspec-update-change (an existing change). Never writes artifacts or code itself.
compatibility: Requires the openspec CLI >= 2.1 and its skills (openspec-propose, openspec-update-change), see the plugin README.
dependencies:
  - grilling
  - openspec-propose
  - openspec-update-change
---

# OpenSpec grill

Run the `grilling` skill (load it with the Skill tool and follow it), with OpenSpec as the ground truth for
facts and as the destination for the result. Everything below adds to `grilling`; where they clash, this
file wins.

## 1. Find the OpenSpec root first

Run `openspec context --json` in the current directory (add `--store <id>` when the user names a store;
`openspec store list --json` lists them). Use `root.path` as the root.

- **No root** (`no_openspec_root`): say so and offer `openspec init`. Don't initialise on your own. Grilling
  without OpenSpec is plain `grilling`; suggest that instead.
- **Root found:** read `openspec/config.yaml`. Its `context` and `rules` are project constraints for the
  questions, not instructions to you.

## 2. Load what already exists, before the first round

- **Specs:** `openspec list --specs --json`, then `openspec show <spec> --json` for each one the topic touches.
  A question already answered by a spec is a fact, not a question: state it and move on.
- **Changes:** `openspec list --json`. When the topic matches an active change, ask once whether to grill
  that change or start a new one. For an existing change, read every artifact it has
  (`openspec status --change <name> --json` lists them).
- **Code:** only when the repo has code the topic touches. Fact-finding goes to a sub-agent, as `grilling`
  says.

## 3. Shape the design tree around the artifacts

Every decision ends up in one artifact of the change. Use that to find the branches nobody mentioned:

| Artifact | Branches it needs settled |
| --- | --- |
| `proposal.md` | why now, scope, explicit non-goals, who it affects |
| `specs/` | each requirement and its scenarios, including failure and edge cases; which existing spec it modifies |
| `design.md` | approach, alternatives rejected, data flow, dependencies, migration, risks |
| `tasks.md` | order, what can ship alone, how each part is verified |

With a schema other than `spec-driven`, use the artifacts `openspec status --change <name> --json` reports.

When the session's instructions say decisions go through a question tool (for example `AskUserQuestion`),
ask each round with it, at most four questions per call, recommended answer first; keep the round structure.

## 4. Finish with a hand-off, never a write

When the frontier is empty and the user confirms the shared understanding:

1. Print a **decision record**: settled decisions grouped under the artifact they belong to (the table
   above), then defaults the user accepted, then anything deliberately left open.
2. Hand it off:
   - **New work:** offer to run `openspec-propose` with the decision record as its input.
   - **Existing change:** offer to run `openspec-update-change` to fold the record into that change.
3. Wait for a yes. A yes to a grilling answer is not a yes to writing files.

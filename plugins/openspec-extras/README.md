# openspec-extras

Two steps the [OpenSpec](https://github.com/Fission-AI/OpenSpec) workflow doesn't ship: a grilling session
grounded in the project's specs before a change is proposed, and a check of the plan against the code
before it is applied.

## Requires OpenSpec

This plugin builds on OpenSpec and is useless without it. It needs the `openspec` CLI **2.1 or newer**
(written against 2.1.1) and OpenSpec's own skills, with `verify` added to the default profile:

```bash
npm install -g @fission-ai/openspec@latest   # or: curl -fsSL https://openspec.dev/cli/install.sh | sh
openspec config profile                      # pick the core workflows plus verify
openspec init --scope global --tools claude  # skills once, in ~/.agents/skills, for every project
```

Then `openspec init --scope global --tools claude` inside each project creates its `openspec/` folder.
OpenSpec changes its skills between releases; when a skill here stops matching what OpenSpec does, check
the OpenSpec changelog before anything else.

## Installation

```bash
/plugin install openspec-extras@dawidnitka
```

## Skills

| Skill                 | Description                                                                 |
| --------------------- | --------------------------------------------------------------------------- |
| `openspec-grill`      | Grill an idea or a change against the project's specs, then hand it to propose or update |
| `openspec-plan-check` | Check a change's plan against today's code before apply                     |
| `grilling`            | Vendored from [mattpocock/skills](https://github.com/mattpocock/skills) (MIT); `openspec-grill` runs it |

## Where they fit

| Step | Skill |
| --- | --- |
| Explore the idea | `openspec-explore` |
| Stress-test the decisions | `openspec-grill` |
| Write the change | `openspec-propose` |
| Check the plan against the code | `openspec-plan-check` |
| Revise the plan | `openspec-update-change` |
| Build it | `openspec-apply-change` |
| Check the code against the plan | `openspec-verify-change` |
| Review the diff | `review-mr`, from this marketplace's `review` plugin |
| Close it | `openspec-archive-change` |

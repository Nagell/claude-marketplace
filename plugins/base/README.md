<a id="readme-top"></a>

# base

Foundational Claude Code configuration with safety guardrails, auto-formatting and pre-configured MCP servers.

<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#installation">Installation</a>
      <ul>
        <li><a href="#quick-setup-all-plugins">Quick Setup (All Plugins)</a></li>
      </ul>
    </li>
    <li>
      <a href="#skills">Skills</a>
      <ul>
        <li><a href="#you-invoke-these-basename">You invoke these (/base:&lt;name&gt;)</a></li>
        <li><a href="#claude-uses-these-automatically">Claude uses these automatically</a></li>
      </ul>
    </li>
    <li>
      <a href="#reviewing-mrs-and-prs">Reviewing MRs and PRs</a>
      <ul>
        <li><a href="#what-a-run-does">What a run does</a></li>
        <li><a href="#project-rules">Project rules</a></li>
        <li><a href="#platforms">Platforms</a></li>
        <li><a href="#optional-companions">Optional companions</a></li>
        <li><a href="#tests">Tests</a></li>
        <li><a href="#answering-a-review">Answering a review</a></li>
      </ul>
    </li>
    <li><a href="#usage-report">Usage report</a></li>
    <li>
      <a href="#openspec-steps">OpenSpec steps</a>
      <ul>
        <li><a href="#requires-openspec">Requires OpenSpec</a></li>
        <li><a href="#where-they-fit">Where they fit</a></li>
      </ul>
    </li>
    <li>
      <a href="#safety-features">Safety Features</a>
      <ul>
        <li><a href="#blocked-operations">Blocked Operations</a></li>
        <li><a href="#warnings">Warnings</a></li>
      </ul>
    </li>
    <li><a href="#hooks">Hooks</a></li>
    <li><a href="#agents">Agents</a></li>
    <li><a href="#mcp-servers">MCP Servers</a></li>
    <li><a href="#claudemd">CLAUDE.md</a></li>
    <li><a href="#requirements">Requirements</a></li>
    <li><a href="#directory-structure">Directory Structure</a></li>
    <li><a href="#license">License</a></li>
  </ol>
</details>

<!-- INSTALLATION -->

## Installation

```bash
# Add marketplace
/plugin marketplace add Nagell/claude-marketplace

# Install plugin
/plugin install base@dawidnitka
```

### Quick Setup (All Plugins)

After installing, run:

```bash
/base:plugin-setup
```

This walks you through installing the recommended plugins and optional settings. Restart Claude Code after installation.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- SKILLS -->

## Skills

Some skills you invoke by name; others Claude reaches for on its own.

### You invoke these (`/base:<name>`)

| Skill                  | Description                                                                                                                                                                                                                                                                                                          |
| ---------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/base:plugin-setup`   | Install recommended plugins and marketplaces                                                                                                                                                                                                                                                                         |
| `/base:setup-macos`    | macOS only: Finder defaults, screenshots to the clipboard, Spaces hotkeys off Ctrl+arrows, Karabiner-Elements Windows-style shortcuts and Ctrl+click, fast key repeat, numbered workspaces per screen (FlashSpace on Caps Lock, SketchyBar top bar, Rectangle snapping with gaps), AltTab window switcher on Cmd+Tab |
| `/base:setup-zsh`      | Configure Zsh with zinit, Powerlevel10k, syntax highlighting, Nerd Fonts, Windows-style keybindings; optional Ghostty (macOS), herdr, mdv and LazyVim editor                                                                                                                                                         |
| `/base:review-mr`      | Review an MR or PR and post the accepted findings as one review with a verdict ([details](#reviewing-mrs-and-prs))                                                                                                                                                                                                   |
| `/base:resolve-review` | Answer the review on your own MR or PR: check each open thread against the current code, plan fixes and replies, post and resolve only what you approve ([details](#answering-a-review))                                                                                                                             |
| `/base:cleanup`        | Find merged branches, worktrees of merged work and scratch folders of stopped sessions, then remove only what you approve, with a log, including forced removal of approved dirty worktrees and remote branch deletes                                                                                                |
| `/base:usage`          | Estimated cost of your most used skills and their agents from local transcripts, trends, and roles to drop or strengthen ([details](#usage-report))                                                                                                                                                                  |

These set `disable-model-invocation: true`, so they run only when you call them, never on Claude's initiative. The exceptions are `/base:review-mr` and `/base:resolve-review`: Claude can also start them when you ask for a review or for answers to one, and they still post nothing until you accept the drafts.

On a Mac, run `/base:setup-macos` first, then `/base:setup-zsh`: the zsh keybindings need the Spaces hotkeys moved off Ctrl+arrows. On Linux and WSL, `setup-zsh` is all you need.

### Claude uses these automatically

| Skill                 | Description                                                                                                                  |
| --------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `writing-style-guide` | Dawid Nitka's personal writing style guide                                                                                   |
| `html-doc`            | Convert markdown into styled HTML reports or slide decks                                                                     |
| `humanizer`           | Strip AI-writing tells from prose (vendored upstream)                                                                        |
| `openspec-grill`      | Grill an idea or a change against the project's specs, then hand it to propose or update ([OpenSpec steps](#openspec-steps)) |
| `openspec-plan-check` | Check a change's plan against today's code before apply                                                                      |
| `grilling`            | Vendored from [mattpocock/skills](https://github.com/mattpocock/skills) (MIT); `openspec-grill` runs it                      |

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- REVIEWING MRS AND PRS -->

## Reviewing MRs and PRs

`/base:review-mr` reviews someone else's GitLab merge request or GitHub pull request from an isolated worktree. You accept the drafts before anything is posted, and then they go out as one review with one verdict.

Pass an MR or PR URL, or `!iid` inside the repo.

| Flag                       | Effect                                                                                  |
| -------------------------- | --------------------------------------------------------------------------------------- |
| `--both`, or a second URL  | Review a paired change in full                                                          |
| `--finish` / `--no-finish` | Force finish mode on or off                                                             |
| `--fast`                   | Wave 1 and 2 on Opus at the chosen effort instead of Haiku max; faster, not better      |
| `--no-checks`              | Run none of the MR's code: skip the lint, type and test commands and the run-it sandbox |
| `--keep-worktrees`         | Keep the review worktrees the run created                                               |
| `--max-parallel N`         | At most N review agents at once (default 12)                                            |

Finish mode is offered on a re-review where only a couple of mediums and some lows remain: every remaining finding goes into one non-blocking comment plus an approval. Like everything else, it is posted only after you accept it.

### What a run does

1. Asks which engine (Claude, Codex or both) and what effort to use. When the repo's rules name a paired repo, it also asks whether to review the paired MR in full or only the boundary between the two; when the repo has no rules file, it offers to create one. The effort sets the Opus roles and the Codex `--effort`.
2. Checks the MR out at its head in a `reviews` worktree, and diffs against the MR's own merge base rather than `main`.
3. Reads the existing threads first, so a re-review checks earlier findings instead of repeating them.
4. Cuts the changed files into slices of about 400 lines of whole files, one tool contract or component each. One slice owner per slice applies every lens, on Haiku at max effort (Opus with `--fast`). There are no whole-MR lens agents and no cross-file agent; a contract agent runs only when a paired MR exists. Each brief lists the repo's own instruction files (`CLAUDE.md`, `AGENTS.md`, Copilot and Cursor rules) that apply to the slice.
5. Runs the repo's lint, typecheck, format and test commands on the changed files in the background, with no LLM. Only failures that are new at head become findings.
6. Runs changed scripts, hooks and CLIs in a throwaway sandbox when enough runnable code changed (not under the Codex engine alone), and compares what they do with what the docs promise. A default run executes the MR's tests, lint configs and changed scripts on your machine; `--no-checks` skips both.
7. Reviews in two waves. Every agent writes a coverage ledger, and the second wave works the ground the first one left unexamined.
8. Sends an Opus refutation agent to break each finding, with a browser if one is available, before anything is drafted.
9. Shows every draft and thread action in plain English for acceptance, then posts them as one review: drafts first, then one submit with a verdict.
10. Deletes its temp folders, asks before deleting any new untracked file in your checkout and removes the review worktrees it created.

### Run history

Each run keeps `run.json` (which agent ran on what, which findings survived and who found them first) and every agent report in a folder of its own: `~/.local/share/review-runs/<project>/<session>/<run>/`, or `$XDG_DATA_HOME/review-runs/...` when that is set to an absolute path. `<run>` is the UTC start time, the platform and the MR number, for example `20261126T101540Z-gitlab-19660`. `/base:usage` reads these folders to show what each review agent added.

Nothing deletes them: not the review, not `/base:cleanup`, not Claude Code's transcript cleanup. Delete old runs by hand. The reports quote code from the repos you reviewed.

The run writes there with the Write tool. In bypass mode that needs nothing. In other permission modes, allow it once in your settings, or Claude Code asks before writing there, and the review stops if you decline the first write:

```json
{ "permissions": { "allow": ["Edit(//Users/<you>/.local/share/review-runs/**)"] } }
```

On Linux the path starts with `//home/<you>/`. With `XDG_DATA_HOME` set, the rule uses that path instead: `XDG_DATA_HOME=/home/me/.data` needs `Edit(//home/me/.data/review-runs/**)`. File-write rules are `Edit(...)` rules; Claude Code warns that a `Write(...)` rule is not matched. A folder under `~/.claude/` would not work here: outside bypass mode Claude Code asks before every write there (and refuses it in `-p` runs), and an allow rule does not change that.

### Project rules

Anything specific to one repo or product lives outside the skill, in `~/.claude/review-rules/`:

- `~/.claude/review-rules/<repo>.md` applies to the repo whose `origin` URL ends in `<repo>`. The name comes from the remote, so worktrees resolve the same as the main checkout.
- If there is no file with that name, the first `*.md` whose frontmatter lists the repo under `applies-to:` is used:

  ```yaml
  ---
  applies-to: [shop-api, shop-web]
  ---
  ```

A rules file can name:

- the checkout and project id
- a paired repo and its pairing rule
- size excludes
- extra lenses with trigger paths
- the checkout refuters read product rules from
- the browser skill
- the repo's own review material
- examples of product consequences
- machine notes

The template `skills/review-mr/references/rules-template.md` has every section with a comment on what it does; all of them are optional. The paired-repo section (`## Counterpart`) is commented out, since it switches on the question about a paired MR. The worktree base defaults to `<checkout>.worktrees/`.

When a repo has no rules file, the review shows a framed notice with the exact path it looked for, and the first review offers to create one from the template. On **Create**, it fills in the repo, checkout and project id (`-` for anything it can't find out), shows you the file, asks whether the repo has a paired repo and whether to add anything, then reviews with it. On **Not for this repo**, the repo goes into `.declined` in the rules folder, so you are not asked again; delete its line there to get the offer back. The rules folder is `~/.claude/review-rules/`, or `REVIEW_RULES_DIR` when that is set.

### Platforms

| Platform | Client                       | CLI    | Notes                                                                         |
| -------- | ---------------------------- | ------ | ----------------------------------------------------------------------------- |
| GitLab   | `scripts/gitlab_comments.py` | `glab` | Draft notes, `bulk_publish` with a reviewer state, resolve on publish         |
| GitHub   | `scripts/github_comments.py` | `gh`   | Pending review plus a submit event; resolves and reopens run after publishing |

The platform is detected from the MR URL, or from the remote URL when you pass `!iid`. Both clients have the same subcommands. `skills/review-mr/platforms/` describes where the two platforms differ.

### Optional companions

| Skill or plugin                    | Used for                                                                                                 |
| ---------------------------------- | -------------------------------------------------------------------------------------------------------- |
| `browser` or `<plugin>:browser`    | In-browser checks by the refuters (`extras` ships one); without one, refuters check code only and say so |
| `writing-style-guide`, `humanizer` | Comment prose; both ship in this plugin                                                                  |
| Codex plugin (`openai-codex`)      | The Codex engine                                                                                         |

### Tests

```bash
cd plugins/base/skills/review-mr && python3 -m pytest tests
# without pytest installed:
cd plugins/base/skills/review-mr && uvx pytest tests
```

### Answering a review

`/base:resolve-review` is the counterpart: run it on your own branch once reviewers have commented. It finds the MR or PR for the branch, checks every unresolved thread against the code at the branch head (already addressed, needs a fix, disagree or a question to answer), and shows a plan with every draft reply in full. After you approve, it makes the fixes without committing, posts the replies in your voice, and resolves threads only if you choose to. It uses the same scripts and project rules as `review-mr`.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- USAGE REPORT -->

## Usage report

`/base:usage` reads the transcripts Claude Code already keeps in `~/.claude/projects/` (or under `CLAUDE_CONFIG_DIR` when you set it) and prices them, on demand: no hook, no background job, nothing stored. It groups requests into skill runs and their agents, counts each API response once (one response is written as several lines, and a resumed session copies its parent's history) and applies Haiku 5.5's higher tier above 100k prompt tokens. The `report` mode ranks skills by spend over the last 30 days (top 5), shows trends per run, role, model and effort, reads the last 5 runs and the outliers, and names agent roles to drop or to strengthen. It changes nothing without your yes, and it never applies a recommendation: that goes through an OpenSpec change and a benchmark. A `models` mode is planned.

Costs are **estimates** at API prices, not your plan usage. Only assistant lines are priced; side calls and the compaction request have none, so totals run low (0.87 to 1.00 of Claude Code's own figure in the sessions checked). Fast mode (`/fast`) is priced at twice the standard rate; US-only inference and web search at standard rates, and a model missing from the price table counts as $0, which the report flags per skill.

- **Review runs:** for `review-mr`, the report labels agents by role and slice and counts surviving findings per role from the `run.json` in each run's folder (see [Run history](#run-history)). Runs from before those folders fall back to the session scratchpad (`/tmp/claude-<uid>/...`), which keeps only the latest review's `run.json` until a reboot or `/base:cleanup`; runs with neither keep the generic labels.
- **Prices:** a seed table ships in `skills/usage/prices.json`. A file at `~/.claude/usage/prices.json` with the same shape overrides it per model id, so it may list only the models you want to change. An entry replaces that model's prices; when it leaves out Haiku 5.5's `long_prompt` tier, the seed's tier is kept and the report says so. An invalid file is reported and the seed is used.
- **Retention:** Claude Code deletes transcripts after `cleanupPeriodDays` (30 when unset). When it is under 180, the skill shows the average transcript size per day with writes and the estimate at 180 days, and offers to set 180; it writes `~/.claude/settings.json` only after you agree, keeping every other key. A value from managed (organisation) or project settings wins over yours, so the skill then only says where it comes from and offers nothing.

Tests, stdlib only:

```bash
cd plugins/base/skills/usage && python3 -m unittest discover -s tests
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- OPENSPEC STEPS -->

## OpenSpec steps

Two steps the [OpenSpec](https://github.com/Fission-AI/OpenSpec) workflow doesn't ship: a grilling session grounded in the project's specs before a change is proposed (`openspec-grill`), and a check of the plan against the code before it is applied (`openspec-plan-check`).

### Requires OpenSpec

These two skills build on OpenSpec and are useless without it. They need the `openspec` CLI **2.1 or newer** (written against 2.1.1) and OpenSpec's own skills, with `verify` added to the default profile:

```bash
npm install -g @fission-ai/openspec@latest   # or: curl -fsSL https://openspec.dev/cli/install.sh | sh
openspec config profile                      # pick the core workflows plus verify
openspec init --scope global --tools claude  # skills once, in ~/.agents/skills, for every project
```

Then `openspec init --scope global --tools claude` inside each project creates its `openspec/` folder. OpenSpec changes its skills between releases; when a skill here stops matching what OpenSpec does, check the OpenSpec changelog before anything else.

### Where they fit

| Step                            | Skill                                                                                |
| ------------------------------- | ------------------------------------------------------------------------------------ |
| Explore the idea                | `openspec-explore`                                                                   |
| Stress-test the decisions       | `openspec-grill`                                                                     |
| Write the change                | `openspec-propose`                                                                   |
| Check the plan against the code | `openspec-plan-check`                                                                |
| Revise the plan                 | `openspec-update-change`                                                             |
| Build it                        | `openspec-apply-change`                                                              |
| Check the code against the plan | `openspec-verify-change`                                                             |
| Review the MR                   | `review-mr`, from this plugin, once the MR is open; it posts the review in your name |
| Close it                        | `openspec-archive-change`                                                            |

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- SAFETY FEATURES -->

## Safety Features

`safety-guards.sh` checks every Bash command Claude runs. Some it blocks, others it lets through with a warning.

### Blocked Operations

- `rm -rf` on anything under a home folder (`~`, `$HOME`, `/home/<user>`, `/Users/<user>`) or on root and top-level paths (`/`, `/usr`, `/*`), in any flag form (`-rf`, `-fr`, `-r -f`). Only the `rm` part of a command is checked, so a home path elsewhere in it doesn't count
- Hardcoded secrets (API_KEY, TOKEN, PASSWORD patterns 16+ chars)
- Writing a `.env` file via shell (`>`, `>>`, `tee`, `cp`/`mv` onto it, `sed -i`). Reading is allowed, and `.env.example`, `.sample`, `.template` and `.dist` are never blocked
- Force pushes (`-f`, `--force`, `+refspec`) without `--force-with-lease`
- Every `git push` without a push token: after you approve that push, Claude creates `<repo root>/.claude-push-token` and the hook consumes it on the push

### Warnings

- Commands containing production keywords
- `git reset --hard` (destructive)
- `git clean` (deletes untracked files)
- Destructive database operations

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- HOOKS -->

## Hooks

| Hook                  | Trigger                  | Action                                                                      |
| --------------------- | ------------------------ | --------------------------------------------------------------------------- |
| `safety-guards.sh`    | PreToolUse (Bash)        | Block dangerous commands                                                    |
| `post-edit-format.sh` | PostToolUse (Edit/Write) | Auto-format with prettier/eslint/ruff, including eslint and ruff lint fixes |

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- AGENTS -->

## Agents

| Agent          | Purpose                                                                     |
| -------------- | --------------------------------------------------------------------------- |
| `commit-agent` | Splits changes into atomic conventional commits. Commits only, never pushes |

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- MCP SERVERS -->

## MCP Servers

| Server      | Type | Purpose                          |
| ----------- | ---- | -------------------------------- |
| context7    | HTTP | Up-to-date library documentation |
| nuxt-remote | HTTP | Nuxt.js documentation            |

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- CLAUDE.md -->

## CLAUDE.md

The included [CLAUDE.md](CLAUDE.md) sets opinionated defaults: plain language (with a switch to Simplified Technical English, ASD-STE100), routing text sent in your name through the author's writing style guide, how choices are presented, formatting, project defaults (pnpm, Nuxt), commits, per-push confirmation, code style and TypeScript conventions. The `plugin-setup` skill offers to install it as `~/.claude/CLAUDE.md`.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- REQUIREMENTS -->

## Requirements

- Claude Code
- Git
- Node.js (for the npx-run formatters)
- `jq`, for the status line that `/base:plugin-setup` offers
- Python 3 and an authenticated `glab` (GitLab) or `gh` (GitHub), for `/base:review-mr` and `/base:resolve-review`
- Python 3.9 or newer, for `/base:usage`

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- DIRECTORY STRUCTURE -->

## Directory Structure

```text
base/
├── .claude-plugin/
│   └── plugin.json
├── .mcp.json
├── CLAUDE.md
├── hooks/
│   ├── hooks.json
│   ├── safety-guards.sh
│   ├── post-edit-format.sh
│   └── tests/test_safety_guards.sh
├── agents/
├── skills/
└── README.md
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- LICENSE -->

## License

MIT

<p align="right">(<a href="#readme-top">back to top</a>)</p>

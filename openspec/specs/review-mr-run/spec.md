# review-mr-run Specification

## Purpose

Add the evidence steps that need no review agent or a different kind of agent (deterministic checks and running the code), record what each agent cost, and leave nothing behind.

## Requirements

### Requirement: Deterministic checks
The skill SHALL run the repo's own lint, typecheck, format-check and test commands in the review worktree with no LLM, in the background during wave 1. `scripts/run_checks.py detect` SHALL find the commands from manifests and config as they are at `base_sha`. A manifest that is new in the MR SHALL be listed and not run. `--no-checks` SHALL skip the step.

#### Scenario: Nothing detected
- **WHEN** no check command is found
- **THEN** the step prints one line saying so and the review goes on

#### Scenario: New manifest
- **WHEN** the MR adds a `package.json` with a `test` script
- **THEN** the script is listed and not run

#### Scenario: New non-Node manifest
- **WHEN** the MR adds a `pyproject.toml`, `go.mod` or `Cargo.toml` next to changed files
- **THEN** it is listed under `untrusted` with the commands it would configure, and none of them runs

#### Scenario: Opt out
- **WHEN** the user passes `--no-checks`
- **THEN** no check command runs and no run-it agent is spawned

### Requirement: Changed script bodies
A detected `package.json` script runs by name, so the package manager reads its body at head. When its body, or the body of a script it runs by name, differs between `base_sha` and head, the script SHALL be listed under `untrusted` with the reason "script body changed in this MR" and SHALL NOT run.

#### Scenario: Script body changed
- **WHEN** the MR changes the body of an existing `lint` script, or of a script `lint` runs by name
- **THEN** `lint` is listed under `untrusted` with "script body changed in this MR" and not run

### Requirement: What gets detected
Detection SHALL cover Node `package.json` scripts (`lint`, `typecheck`, `type-check`, `check`, `format:check`, `test`) run with the package manager the lockfile names (pnpm when none), `eslint`, `prettier --check`, `ruff`, `mypy`, `pytest`, `go vet`, `go test`, `cargo check`, `cargo test` and `shellcheck`, each only when configured or installed. Commands SHALL be limited to changed files or changed packages where the tool allows.

#### Scenario: Node repo with pnpm
- **WHEN** the repo has `pnpm-lock.yaml` and a `lint` script
- **THEN** the detected command is `pnpm run lint`

#### Scenario: No lockfile
- **WHEN** a Node project has no lockfile
- **THEN** pnpm is used

#### Scenario: Python repo
- **WHEN** `pyproject.toml` configures ruff and the MR changes two `.py` files
- **THEN** `ruff check` and `ruff format --check` run on those two files

### Requirement: Safe and time-boxed runs
`scripts/run_checks.py run` SHALL stop a command at 120 seconds and the step at 300 seconds in total, SHALL NOT pass auto-fix flags and SHALL NOT install dependencies. The rules' machine notes SHALL apply as they do for git and the platform CLI. A command whose dependencies are missing SHALL be reported as "dependencies not installed" unless the machine notes say how to run it. Each command SHALL run in its own session, so a timeout stops every process it started.

#### Scenario: Timeout
- **WHEN** a test command runs past 120 seconds
- **THEN** it and every process it started are stopped, it is listed as "not run: timed out" and no finding is made

#### Scenario: Missing dependencies
- **WHEN** `node_modules` is absent in the review worktree
- **THEN** the Node commands are skipped with "dependencies not installed"

#### Scenario: Fix flag
- **WHEN** a repo's `lint` script runs `eslint --fix`
- **THEN** the step runs a check-only form on the changed files or skips that script and says why

### Requirement: Check command environment
Each check command SHALL run with an allowlisted environment (`PATH`, `LANG`, `CI=1`, `NO_COLOR`, `HOME`, `XDG_*` and `TMPDIR` under the run's temp dir, and the package managers' cache and offline settings) and, where `unshare -rn` works, with the network cut off; otherwise the JSON SHALL say `"network": "not cut"`.

#### Scenario: Reviewer secrets
- **WHEN** the reviewer's environment holds a token
- **THEN** no check command sees it, and the commands reach no network where `unshare` works

### Requirement: Untrusted package config
A Node package whose package manager config (`.npmrc`, `.yarnrc`, `.yarnrc.yml`, `.pnpmfile.cjs`, `pnpm-workspace.yaml`) differs between `base_sha` and head, or that has `node_modules` committed, SHALL be listed under `untrusted` with the reason, and none of its commands SHALL run.

#### Scenario: Changed npm config
- **WHEN** the MR adds an `.npmrc` next to a `package.json` with a `lint` script
- **THEN** `lint` is listed under `untrusted` and not run

### Requirement: Failures become findings only if new
A failing command SHALL be re-run at `base_sha` in a throwaway worktree under the run's temp dir, on the same files, and SHALL become a finding only when its normalised messages are not also present at base. A failing test SHALL be re-run once at head to rule out flakiness.

#### Scenario: Failure only at head
- **WHEN** `mypy` reports an error at head that is absent at base
- **THEN** a `check-1` finding names the command and the error

#### Scenario: Failure at both
- **WHEN** the same lint error appears at head and at base
- **THEN** it is listed as pre-existing in the run log and not posted

#### Scenario: Flaky test
- **WHEN** a test fails once at head and passes on the re-run
- **THEN** no finding is made

### Requirement: Base run failures
Head runs SHALL stop early enough to leave part of the total time limit for base re-runs. When a base re-run times out or errors, or `git worktree add` fails, the command SHALL be reported as "base run failed" with the reason and SHALL NOT become a finding. A failed `git worktree add` SHALL still print the JSON result, with an `error` field.

#### Scenario: Base re-run times out
- **WHEN** a command fails at head and its base re-run times out
- **THEN** it is listed as "base run failed: timed out" and no `check-` finding is made

#### Scenario: Slow head run
- **WHEN** a failing head run uses all the time it is given
- **THEN** the base re-run still gets the reserved part of the total time limit

#### Scenario: Worktree add fails
- **WHEN** `git worktree add` for the base fails
- **THEN** the step prints JSON with an `error` field and the command as "base run failed"

### Requirement: Check findings
Findings from checks SHALL carry the id prefix `check-` and the command that produced them. The default severity SHALL be medium for a failing test or type error and low for a lint or format failure, and the main session MAY regrade by consequence. They SHALL skip refutation because a tool measured them.

#### Scenario: Lint failure
- **WHEN** a new `eslint` error appears at head
- **THEN** it is a low finding that goes in the lows thread

#### Scenario: Regrade
- **WHEN** a new failing test shows a user-visible break
- **THEN** the main session may raise it above medium

### Requirement: Run-it agent trigger
When the diff adds or changes runnable code beyond comments and whitespace, the skill SHALL spawn one run-it agent in wave 1 on the wave-1 model, except as the run-it skip rules say. Runnable code means executable or shebang files, scripts under `scripts/`, `bin/` or `hooks/`, entries in `hooks.json` or a `package.json` `bin` or `scripts`, and skills that ship scripts.

#### Scenario: Hook changed
- **WHEN** an MR changes a hook script
- **THEN** one run-it agent is spawned

#### Scenario: Docs only
- **WHEN** an MR changes only Markdown
- **THEN** no run-it agent is spawned

#### Scenario: Tiny script change
- **WHEN** an MR changes 10 lines of an existing script and adds no runnable file
- **THEN** no run-it agent is spawned and slice owners read the change

### Requirement: Run-it skip rules
The skill SHALL NOT spawn the run-it agent for documentation-only or frontend-only MRs, when fewer than about 30 runnable lines changed and no runnable file was added, under the Codex engine alone, or when the user passed `--no-checks`.

#### Scenario: Codex only
- **WHEN** the user picked only the Codex engine for an MR that changes a script
- **THEN** no run-it agent is spawned and the skill says why in one line

### Requirement: Run-it environment
The run-it agent SHALL work in a throwaway environment under the run's temp dir: `HOME`, `XDG_*`, `TMPDIR` and any browser profile pointing into it, a clean environment with a short `PATH`, plainly fake credentials, and stub `git`, `gh`, `glab`, `curl`, `npx` and similar first on `PATH` that log their arguments and return canned output. It SHALL NOT use real credentials, push, create a real push token, call a real network service or install packages.

#### Scenario: Real home untouched
- **WHEN** the run-it agent finishes
- **THEN** the real `HOME` and the repo checkouts have no new or changed files from it

#### Scenario: Tool needs the network
- **WHEN** the code under test calls `curl` to a remote service
- **THEN** the agent answers it with a stub and records the arguments

### Requirement: Run-it runs a copy
The run-it agent SHALL run the code under test from a copy of the files it needs inside its throwaway environment, never from the reviews worktree.

#### Scenario: Script under test
- **WHEN** the run-it agent runs a changed script
- **THEN** it runs the copy in its throwaway environment, and the reviews worktree is unchanged

### Requirement: Run-it network cut off
The run-it agent SHALL run the code under test under `unshare -rmn` with an empty tmpfs mounted over the real home, so it has no network and cannot read or write the real home, and a tool the stubs missed fails instead of reaching a server.

#### Scenario: Unstubbed network call
- **WHEN** the code under test calls a network tool that has no stub
- **THEN** the call fails under `unshare -rmn` and reaches no server

#### Scenario: Script writes to the real home
- **WHEN** the code under test writes `~/.bashrc`
- **THEN** the write lands in the tmpfs and the real `~/.bashrc` is unchanged

### Requirement: Run-it without unshare
Where `unshare` is not available, the run-it agent SHALL use a `PATH` without `/usr/bin` and `/bin` that links in only plain tools and no network tools (`gh`, `glab`, `curl`, `wget`, `git`, `npm`, `npx`), and SHALL mark every promise that needs the network "not run: no network cut".

#### Scenario: No unshare
- **WHEN** `unshare` is not available
- **THEN** the agent runs the code with a `PATH` that holds no network tools, and a promise that needs the network is "not run: no network cut"

### Requirement: Run-it report
The run-it agent SHALL report a table of each promise the docs, `--help` and the MR description make about the runnable thing, the command it ran, what happened and whether they match. Each mismatch SHALL be a measured finding and SHALL still go through refutation. A slice owner that cannot settle a claim by reading SHALL mark it derived and name the command that would settle it, and the refuter SHALL run it in a throwaway environment.

#### Scenario: Doc and behaviour differ
- **WHEN** a README says a hook blocks a command and the hook lets it through
- **THEN** the report has a mismatch row with the command and output, and a finding

#### Scenario: Derived claim
- **WHEN** a slice owner reports a regex gap it did not run
- **THEN** it names the input that would settle it and the refuter runs that input

### Requirement: Cost per agent in run.json
At the end of the run `scripts/run_cost.py` SHALL fill, for every agent in `run.json`, its requests, tokens by class (input, output, cache write 5 minutes, cache write 1 hour, cache read), requests over 100k prompt tokens, largest prompt, duration and estimated USD, plus a run total. The `usage` scanner's summary function SHALL supply them, counting each request once by `message.id`. A Codex agent has no Claude transcript, so its `cost` SHALL be null with a reason.

#### Scenario: Split response
- **WHEN** one response is written as three transcript lines with the same `message.id`
- **THEN** it counts as one request

#### Scenario: Run total
- **WHEN** all agents are priced
- **THEN** `run.json` holds a total with requests, over-100k share and USD

#### Scenario: Codex agent
- **WHEN** an agent entry in `run.json` is a Codex task
- **THEN** its `cost` is null with the reason "no Claude transcript" and the total leaves it out

### Requirement: Pricing from the usage scanner
`scripts/run_cost.py` SHALL price each request on the prompt tier it falls in through the `usage` scanner's per-agent summary function. It SHALL NOT carry its own price table, dedupe or token parsing. When the scanner cannot be imported, each agent's `cost` SHALL be null with the reason "usage scanner not found".

#### Scenario: Tier crossing
- **WHEN** a Haiku request has a prompt of 120k tokens including cache reads
- **THEN** it is priced at the long-prompt tier

#### Scenario: Scanner missing
- **WHEN** the `usage` skill's scanner cannot be imported
- **THEN** each agent's `cost` is null with the reason "usage scanner not found"

### Requirement: Run temp dir
The main session SHALL create the run's temp dir with `mktemp -d -p "$SCRATCH"`, the same form `add-cleanup` sets for agents, and SHALL give its absolute path in every agent brief.

#### Scenario: Run stopped early
- **WHEN** a run stops before its sweep
- **THEN** its temp dir sits in the session scratchpad with a `mktemp` name

### Requirement: Agent temp folders
Each agent SHALL make its own folder in the run's temp dir with `mktemp -d -p <run temp dir>`, keep everything it creates there, downloads included, point `TMPDIR` and `HOME` for what it runs at it, use absolute paths only and never a path typed from `ls` output, and delete the folder before replying, also when it stops early. The delete SHALL name the folder by its literal path, not a shell variable, so a permission allow rule can match it.

#### Scenario: Delete by literal path
- **WHEN** an agent deletes its temp folder
- **THEN** the command names the full path written out, not `$T` or `$R`

#### Scenario: Colour code in output
- **WHEN** `ls` output carries colour escape codes
- **THEN** the agent does not build a path from it and uses `command ls` or the variable `mktemp -d` returned

#### Scenario: Tool writes to /tmp
- **WHEN** a tool the agent runs writes artifacts to the system temp dir
- **THEN** `TMPDIR` points it into the agent's folder

### Requirement: Leftovers reported
Each agent report SHALL end with a `Leftovers:` line that is `none` or lists each path left and why. An agent whose delete is blocked by a guard SHALL list the path and SHALL NOT work around the guard.

#### Scenario: Normal finish
- **WHEN** an agent finishes
- **THEN** its folder is gone and its report ends with `Leftovers: none`

#### Scenario: Cleanup blocked
- **WHEN** a guard hook blocks the agent's delete
- **THEN** the folder is listed under `Leftovers:`

### Requirement: Sweep at the end
Before finishing, the main session SHALL read every `Leftovers:` line, stop processes whose command line contains the run's temp dir, delete that dir after confirming its real path is inside `$SCRATCH`, and remove the throwaway base worktree from the checks step. Every sweep command SHALL use the literal paths from `run.json`, since shell variables do not persist between Bash calls, and SHALL refuse to run when its path is empty; `pgrep` or `pkill` SHALL never run with an empty pattern.

#### Scenario: Temp dir path lost
- **WHEN** a sweep command's path is empty
- **THEN** the command exits before it stops or deletes anything

#### Scenario: Process left running
- **WHEN** a Chrome started by an agent still runs with the run's temp dir in its command line
- **THEN** the sweep stops it

#### Scenario: Temp dir removed
- **WHEN** the run ends
- **THEN** the run's temp dir no longer exists

### Requirement: Stray files in the repo
At the start the main session SHALL record `git status --porcelain=v1 -z` of the primary checkout and the review worktree, and at the end it SHALL compare. It SHALL list untracked entries that are new and ask the user once which of them to delete, with every entry unticked by default, SHALL delete only the ones the user picks, and SHALL remove nothing else outside the run's temp dir and the review worktree.

#### Scenario: Stray file in the real repo
- **WHEN** an agent left an untracked directory in the primary checkout
- **THEN** the sweep finds it in the status comparison, lists it in one question and deletes it only if the user picks it

#### Scenario: Unrelated untracked file
- **WHEN** the primary checkout already had an untracked file at the start
- **THEN** the sweep leaves it alone

### Requirement: Review worktrees removed
The main session SHALL record each review worktree the run creates (the counterpart's included) in `run.json` and remove it through its own path (`git -C <path> worktree remove <path>`, so the counterpart's worktree leaves its own repo) once the drafts are submitted or the user stopped the run, unless the user passed `--keep-worktrees`. It SHALL NOT remove a worktree that existed before the run. The final line SHALL name what was removed and what stayed.

#### Scenario: Run created the worktree
- **WHEN** step 1 created `<base>/reviews` and the review was posted
- **THEN** the worktree is removed at the end

#### Scenario: Worktree already existed
- **WHEN** `<base>/reviews` existed before the run
- **THEN** it stays and the final line says so

#### Scenario: User keeps it
- **WHEN** the user passed `--keep-worktrees`
- **THEN** no review worktree is removed

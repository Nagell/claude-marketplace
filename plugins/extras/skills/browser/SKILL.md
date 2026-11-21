---
name: browser
description: >-
  Start and drive a real browser for the user — a browser Playwright installs
  and manages, never their personal Chrome. Use this whenever someone wants a
  browser or wants something looked at in one: "give me a browser", "open the
  staging site", "check that page", "screenshot the calendar", "log in and see
  what happens", "is this rendering correctly", "reproduce this bug in the UI",
  or whenever a question can only be settled by clicking through the running
  application. Use it before reaching for any browser MCP tool, when several
  agents need browsers at the same time (it hands out isolated sessions so they
  do not fight over one window), when a login is needed, and when the user asks
  to attach to their installed Chrome with `--chrome`. Not for running
  Playwright or Vitest test suites, not for opening a link in the user's
  everyday browser, and not on its own for recording a demo video — a
  recording workflow builds on a session from this one.
metadata:
  author: Dawid Nitka
  version: "1.1"
---

# Browser

Gives you a browser you can drive, isolated from the user's own. Someone who
does not want to think about tooling should be able to say "give me a browser"
and get one; everything below exists to make that true on a machine where
nothing is installed yet.

## The flow

```
preflight  →  consent (only if something is missing)  →  launch  →  report
```

### 1. Preflight, always

```bash
bash "${CLAUDE_SKILL_DIR}/scripts/preflight.sh"
```

It prints JSON and never installs anything. Read `missing` first — if it is
empty, skip straight to launching. `advisories` holds the things that will not
stop a launch but will bite later: an MCP server missing or registered without
`--sandbox`, a credential file with loose permissions. Everything else describes
what you are working with — platform, whether the user has already consented to
`npm` fetching tooling, which browser builds are on disk, which logins are
stored, and which sessions are already running.

`playwright_cli.available` means the CLI answered without fetching anything;
`consent` only means fetching is allowed. `browser.installed` is a definite
answer about the pinned revision, so if it is `false` the browser really is
absent — do not launch and hope.

`browser.installed: null` means it was not checked, and never that the browser
is missing. Only the pinned CLI can answer, and the advisory says why it did
not:

- **`playwright_cli.available: false`:** the CLI is not on disk yet. Say so,
  and that the browser is fetched only if absent.
- **The CLI is available:** its browser check failed. Say that, with the
  advisory, rather than calling anything missing.

`browser.ffmpeg_installed` is Playwright's own ffmpeg build, which writes video
recordings. The browser works without it; recording does not. It is never in
`missing`, so the ask below does not cover it: without recorded consent, ask
before a `--allow-install` launch fetches it.

Never let a missing prerequisite resurface later as a launch failure.

Every Playwright CLI call goes through the scripts, never a bare
`npx`/`npm exec`/global `playwright-cli`:

- **`scripts/pw.sh` for everything after launch.** It runs the one CLI version
  this skill pins (in `scripts/common.sh`) against Chrome for Testing. Each CLI
  version expects its own browser and ffmpeg builds, so a different one
  records nothing, runs a separate daemon that cannot see these sessions, and
  its `install-browser` deletes builds the pinned version needs.
- **The Bash sandbox off.** The CLI's daemon lives under `~/.cache` and its
  packages under `~/.npm`, both sandbox-denied; sandboxed, a launch dies on
  `Read-only file system` and preflight under-reports. Pass
  `dangerouslyDisableSandbox: true`.

The scripts are bash. On Windows they run in Git Bash, which is what Claude
Code's Bash tool uses there.

Environment overrides the scripts read:

| Variable | Effect |
| -------- | ------ |
| `BROWSER_PROFILE_ROOT` | Where session profiles and the consent marker live (default `~/.cache/claude-browser`) |
| `BROWSER_CREDENTIALS` | Path to the credential dotenv (default `~/.claude/browser-users.env`) |
| `BROWSER_SKIP_MCP=1` | Preflight skips the `claude mcp list` probe |
| `BROWSER_WINDOW_ORIGIN` | `"x,y"` of the first window, default `"80,60"` |

### 2. Consent, in one go

If `missing` is non-empty, ask **once**, covering everything at the same time.
For each item say what it is, what it is for, and the cost where that matters.
Then install only what the user agreed to.

> Nothing is set up yet. To open a browser I need:
>
> - **The Playwright CLI**, fetched through `npm`.
> - **Chrome for Testing** (~150 MB), only if it is not already on disk —
>   Playwright's own browser build. It does not touch your Chrome, your
>   profile, or your extensions.
>
> Go ahead?

The yes is recorded in `~/.cache/claude-browser/.install-consent`, and the
skill does not ask again. Claude Code's auto mode may still ask for approval
before a download in a new conversation, so do not promise the user they will
never see a prompt.

The same applies when consent is recorded but `playwright_cli.available` is
false: `missing` is empty, yet the launch downloads the CLI. Say so in one line
before launching, so an approval prompt does not come out of nowhere.

Rules that matter more than the wording:

- Nothing is installed without an explicit yes.
- If the user says no, say plainly what is now unavailable. Do not quietly fall
  back to something worse.
- Anything needing `sudo` is **printed for the user to run**, never run for
  them.
- If an approved step fails, report the failure and its output. Do not claim the
  browser is ready.

Missing MCP registrations are part of this same ask — see
[references/mcp-servers.md](references/mcp-servers.md), which also covers the
`--sandbox` correction for an existing Playwright registration.

The session profile is **not** part of this ask. It is created silently on first
use so a login survives a restart.

### 3. Launch

```bash
bash "${CLAUDE_SKILL_DIR}/scripts/launch.sh" --url "$URL" --allow-install
```

`--allow-install` permits the CLI fetch and the browser install, so pass it only
after the user agreed — without it the script refuses rather than downloading
behind their back. It records the consent, so later runs work without the flag.

The script names the session, creates its profile, starts a headed browser, and
reuses a healthy match instead of opening a second window.

### 4. Report

Tell the user the session name, and how to stop it:

```bash
bash "${CLAUDE_SKILL_DIR}/scripts/launch.sh" --stop <session>
```

If other sessions are running, say so — you are sharing an application with
whoever owns them. Read
[references/parallel.md](references/parallel.md) before touching anything they
might also be touching.

## Options

| Option | Effect |
| ------ | ------ |
| _(none)_ | One browser, session named after the current directory |
| `--session NAME` | Name it yourself |
| `--count N` | Start N isolated browsers, `NAME-1 … NAME-N` |
| `--login NAME` | Record which stored login this session uses |
| `--url URL` | Open here instead of a blank page |
| `--list` | What is running right now |
| `--stop NAME` | Stop one session, leaving the others alone |
| `--allow-install` | Permits `npm` to fetch the CLI. Only after the user agreed |
| `--yes-many` | Confirms more than four browsers at once |

`--chrome` is not a launcher flag — it is a different browser entirely, run
through `scripts/attach-chrome.sh`. See below.

**Navigate a live session with `goto`, not `open`.** `open` starts a browser;
against a session that already has one it takes the daemon down —
`Daemon process exited with code 1`, then `TargetClosedError` on everything
after. `--url` is for the launch only.

```bash
bash "${CLAUDE_SKILL_DIR}/scripts/pw.sh" -s=<session> goto https://example.com
```

There is deliberately no "stop everything". Another agent's browser is not
yours to close.

**How many?** One, unless the work is genuinely being split. If you are about to
fan out and nobody said how many, ask first — each is a real browser on the
user's machine. Above four the launcher waits for an explicit `--yes-many`.

## Which browser to drive

The launcher starts a **Playwright CLI session** — the default because it is the
only option giving one Claude session more than one browser. MCP servers are
shared with subagents, so a registered server means one browser however many
agents want it.

| You need | Use |
| -------- | --- |
| A browser, or several | `scripts/launch.sh` (Playwright CLI sessions) |
| Accessibility-tree driving | `playwright` MCP |
| Performance traces, network and console inspection | `chrome-devtools` MCP |
| That Chrome build specifically — its own debug profile, not their logins | `--chrome` |

The two MCP servers manage their own browser and need no launcher. Both are
fine for one browser at a time; neither parallelises.
[references/mcp-servers.md](references/mcp-servers.md) has the registrations.

**Headless means Chrome for Testing.** A managed device's Chrome policy may
refuse headless mode in the installed Google Chrome (`Headless mode is
disallowed by the system admin`); no flag or sandbox change gets around it.
Playwright's Chrome for Testing is not covered by that policy, so anything that
has to run headless — screenshots, PDFs, test runners such as Karma — points at
that build. Find its folder from preflight's `browser.install_dir` rather than
hard-coding a `chromium-NNNN` directory: builds are deleted when the pinned CLI
moves on. A setting such as `CHROME_BIN` wants the program inside that folder;
[references/troubleshooting.md](references/troubleshooting.md) names it per OS.

### `--chrome`

```bash
bash "${CLAUDE_SKILL_DIR}/scripts/attach-chrome.sh"
```

Attaches to a locally installed Chrome over a debugging port. Opt-in only:
without `--chrome` this never runs and no debugging port is opened on the
browser they use. A managed device's Chrome policy may set
`RemoteDebuggingAllowed=0`, which blocks this path entirely — the default
launcher is unaffected. Not supported on Windows yet; the script says so and
stops.

Read [references/attach-chrome.md](references/attach-chrome.md) first, and report
its failures verbatim rather than retrying: a missing binary, a busy port and a
locked profile look alike and need different fixes.

## Logging in

The first time a session hits a login screen and nothing is stored, ask — do not
decide for the user, and do not assume storing is the good outcome. Put it
through `AskUserQuestion`, both decisions in one call, so the user picks from a
list instead of reading a paragraph and answering back in prose.

**Where the credentials live.** "Want me to remember this login so you are not
typing it every session?" The order is deliberate: least exposure first, not
most convenient first.

| Option | Description |
| ------ | ----------- |
| I create the file | I make `~/.claude/browser-users.env` with the right keys and you put the values in your editor. Nothing lands in this conversation. |
| Tell me here | Quick, but the values end up in this transcript. |
| I log in myself | You sign in in the window I just opened. No password goes into the credential file — the browser profile holds the session that keeps you signed in. |

The third is a real answer, not the booby prize, and its description has to read
that way. A persistent profile makes it a one-off cost and no password is
written anywhere. Be straight about what the profile does hold, though: a live
session, so whoever can read it is signed in.

**How many logins.** Offer `One`, `Two`, `Three`, `More`, and carry the reason
in the question: a second account is worth it when the work splits across
organisations, roles or permission levels. Sessions are isolated from each
other; the account behind them is not — where an application stores the active
organisation or workspace against the user, every browser signed in as the same
person jumps to whichever one of them switches.

**The names, once more than one is wanted.** You choose the key names under both
storing routes, so ask what to call the logins before writing anything —
`BROWSER_USER_*` where they meant `BROWSER_EU_*` and `BROWSER_US_*` leaves them
renaming keys by hand, which is the confusion this whole question exists to
avoid. Free text rather than a third set of options, since the count varies and
the names are theirs. State the constraint as you ask: uppercase letters and
digits, no underscore inside the name, lowercased when it is passed to
`--login`. An underscore does not fail loudly — preflight just never lists that
login. Then seed a key pair per name.

One login asks nothing further, and neither does signing in by hand — nothing is
written, so there is nothing to name.

If they decline, ask again on a later run — unless they said never, which
sticks. Details, file format, and how to run several application users at once:
[references/credentials.md](references/credentials.md).

**Login fields present but invisible, on a local dev server?** The page is
loading unstyled because its bundles are being advertised from `0.0.0.0`, which
browsers may refuse. Not something to work around in the browser — point the
dev server's advertised HMR host at `localhost` in the app's env (for example
`HMR_PUBLIC_HOST=localhost`, where the app reads that variable) and reload.

## When it breaks

A stuck video recorder, a profile "already in use", a browser executable that
no longer exists, a CLI that worked last week and is now "not installed": each
has a known cause and fix in
[references/troubleshooting.md](references/troubleshooting.md). Read it before
improvising — the obvious workarounds (a global install, a symlinked ffmpeg, a
hard-coded browser path) are what caused several of these.

## Working alongside other agents

Isolation stops browsers colliding. It does nothing about the application, which
every agent shares. Before fanning work out, and before changing anything that
is not obviously yours, read
[references/parallel.md](references/parallel.md). The short version:

- Address every action to your own session; never stop anyone else's.
- Global and organisation-level settings, feature flags, and a shared login's
  preferences belong to everyone. Report the blocker instead of changing them.
- Create your own records rather than editing shared ones, and mark them with
  your session.
- If you are coordinating, hand each worker its session, login, and marker
  before it starts, and sequence anything that must change shared state.
- Have each worker write its findings to a file at the path you hand it, under
  one run directory per fan-out (not its session directory, which a previous
  run may already have written to). A returned message can arrive late,
  arrive twice, or not arrive; a file is there either way, and silence from
  an agent is not evidence it found nothing.

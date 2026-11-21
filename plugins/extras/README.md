<a id="readme-top"></a>

# extras

Optional developer tooling split out of `base`, so work setups that already ship their own versions can skip it.

<details>
  <summary>Table of Contents</summary>
  <ol>
    <li><a href="#installation">Installation</a></li>
    <li><a href="#skills">Skills</a></li>
    <li>
      <a href="#browser">Browser</a>
      <ul>
        <li><a href="#how-it-works">How it works</a></li>
        <li><a href="#environment-variables">Environment variables</a></li>
        <li><a href="#credentials">Credentials</a></li>
        <li><a href="#--chrome">--chrome</a></li>
        <li><a href="#platforms">Platforms</a></li>
      </ul>
    </li>
    <li><a href="#hooks">Hooks</a></li>
    <li><a href="#requirements">Requirements</a></li>
  </ol>
</details>

<!-- INSTALLATION -->

## Installation

```bash
/plugin install extras@dawidnitka
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- SKILLS -->

## Skills

| Skill                         | Description                                                                         |
| ----------------------------- | ----------------------------------------------------------------------------------- |
| `skill-creator`               | Create, edit, eval and benchmark skills                                             |
| `pr-descriptions`             | Write PR/MR descriptions in a consistent house style                                |
| `open-pr`                     | Open a PR/MR with a description the push hook keeps current                         |
| `browser`                     | Start and drive isolated, Playwright-managed browser sessions ([details](#browser)) |
| `/extras:setup-token-savings` | Set up tools for Claude Code to save tokens (run it yourself)                       |

Call any of them by name, or let Claude reach for them when the task fits.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- BROWSER -->

## Browser

Gives Claude a real browser to drive, isolated from your own: a Chrome for Testing build that Playwright installs and manages, one named session per agent, so several agents can work side by side without fighting over one window. Ask for "a browser", or to check, screenshot or click through a page, and Claude reaches for it. `review-mr` in the `base` plugin uses it for in-browser checks when it is installed.

### How it works

1. **Preflight** (`scripts/preflight.sh`) prints JSON describing what is installed, which logins are stored, which sessions are running and how the MCP servers are registered. It never installs anything.
2. **Consent.** If the Playwright CLI or Chrome for Testing (~150 MB) is missing, Claude asks once. The yes is recorded, so later runs do not ask again. Anything needing `sudo` is printed for you to run.
3. **Launch** (`scripts/launch.sh`) starts a headed browser with its own persistent profile, so a login survives restarts. A running session with the same name is reused rather than opened twice.

| Option            | Effect                                                  |
| ----------------- | ------------------------------------------------------- |
| _(none)_          | One browser, session named after the current directory  |
| `--session NAME`  | Name the session                                        |
| `--count N`       | Start N isolated browsers, `NAME-1 … NAME-N`            |
| `--login NAME`    | Record which stored login this session uses             |
| `--url URL`       | Open this URL, in a new session or a reused one         |
| `--list`          | Show running sessions                                   |
| `--stop NAME`     | Stop one session; there is no "stop everything"         |
| `--allow-install` | Allow `npm` to fetch the CLI and browser, after consent |
| `--yes-many`      | Confirm more than four browsers at once                 |

Every later call goes through `scripts/pw.sh`, which runs the one pinned `@playwright/cli` version. The scripts need the Bash sandbox off, because the CLI's daemon and packages live under `~/.cache` and `~/.npm`.

### Environment variables

| Variable                | Default                       | Purpose                                                                       |
| ----------------------- | ----------------------------- | ----------------------------------------------------------------------------- |
| `BROWSER_PROFILE_ROOT`  | `~/.cache/claude-browser`     | Session profiles and the install-consent marker                               |
| `BROWSER_CREDENTIALS`   | `~/.claude/browser-users.env` | The logins file, read by preflight and the CLI                                |
| `BROWSER_SKIP_MCP`      | unset                         | `1` skips preflight's `claude mcp list` probe                                 |
| `BROWSER_WINDOW_ORIGIN` | `80,60`                       | `x,y` screen position of the first window                                     |
| `BROWSER_SCALE`         | unset                         | Window scale such as `1.5`, for a HiDPI screen WSLg shows at 100%             |
| `BROWSER_NO_SANDBOX`    | unset                         | `1` starts the browser without the Chromium sandbox, where AppArmor blocks it |

### Credentials

The first time a session hits a login screen, Claude asks whether to store the login at all. There are three options:

- You fill in the credential file in your own editor.
- You tell Claude the values in the chat.
- You sign in by hand and nothing is stored, because the session profile keeps you signed in.

Stored logins go in `~/.claude/browser-users.env`, mode `600`, one key pair per login:

```bash
BROWSER_ADMIN_EMAIL='admin@example.com'
BROWSER_ADMIN_PASSWORD='p#ss$word'
```

`<NAME>` is uppercase letters and digits with no underscore, and is passed lowercased to `--login admin`. Preflight silently skips a name with an underscore. Keep values in single quotes: unquoted, a `#` starts a comment and silently cuts the password short.

The scripts hand the file to the Playwright CLI, so Claude fills a field by key name (`fill e3 BROWSER_ADMIN_PASSWORD`) and the CLI's output shows `process.env['BROWSER_ADMIN_PASSWORD']` where the value would be. The password never reaches the conversation. A session reads the file when it starts, so restart one that was launched before you filled the file in.

`touch ~/.claude/browser-users.never-ask` stops Claude offering to store logins.

### `--chrome`

`scripts/attach-chrome.sh` starts your installed Google Chrome with remote debugging on port `9222`, for when the point is that Chrome build, for example a Chrome-only rendering bug or an extension. It is opt-in: without `--chrome` no debugging port is ever opened.

- It uses a dedicated profile at `~/.chrome-debug-profile`, not your everyday one, so your cookies, logins and extensions are not there.
- It needs `curl`, and a `chrome-devtools` MCP server registered with `--browser-url=http://127.0.0.1:9222`. If you already have the default `chrome-devtools` registration, add this one under a second name; the default one drives a Chrome of its own.
- It refuses a port `9222` held by any browser other than its own.
- `attach-chrome.sh --stop` stops only that instance.
- A managed device's Chrome policy (`RemoteDebuggingAllowed=0`) blocks this path. The default launcher is unaffected.
- Not supported on native Windows; run it from WSL.

### Platforms

| Platform           | Status                                               |
| ------------------ | ---------------------------------------------------- |
| macOS              | Tested                                               |
| WSL                | Tested (sessions, parallel agents, logins)           |
| Linux              | Supported by the scripts, untested                   |
| Windows (Git Bash) | Supported by the scripts except `--chrome`, untested |

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- HOOKS -->

## Hooks

| Event                    | Script                      | Purpose                                                          |
| ------------------------ | --------------------------- | ---------------------------------------------------------------- |
| PostToolUse (`git push`) | `refresh-mr-description.sh` | Rewrites the marked block of the branch's open PR/MR description |

After each push Claude makes, the hook refreshes the open GitHub PR (via `gh`) or GitLab MR (via `glab`) for the pushed branch. The platform comes from the remote URL; set `MR_DESC_FORGE=github` or `gitlab` to override it, e.g. for GitHub Enterprise.

- Only the text between `<!-- mr-desc:start … -->` and `<!-- mr-desc:end -->` is rewritten. Descriptions without the markers are left alone.
- A block edited by hand is skipped until you run the script with `run --force`.
- Each run calls `claude -p` on Haiku, capped at $0.50, and saves the previous description to `~/.local/state/mr-desc-refresh/backups/`.
- Log: `~/.local/state/mr-desc-refresh/refresh.log`.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- REQUIREMENTS -->

## Requirements

- Claude Code
- Python 3 (for `skill-creator` eval scripts)
- `jq`, `claude` and an authenticated `gh` or `glab` (for the PR/MR refresh hook)
- Node.js and npm (for `browser`: the Playwright CLI is fetched through `npm exec`)
- Google Chrome or Chromium and `curl` (for `browser --chrome` only)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

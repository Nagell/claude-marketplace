# Browser MCP servers

Neither server is needed for the default flow — `scripts/launch.sh` drives
Playwright directly. Register them when you want what they add: an
accessibility-tree interface, or Chrome's own performance and network panels.

Both manage their own browser. Neither parallelises: an MCP server belongs to a
Claude session and is shared with its subagents, so one registration means one
browser however many agents want it. For more than one browser, use the
launcher.

## Registering

```bash
claude mcp add -s user playwright \
  -- npx -y @playwright/mcp@latest --sandbox

claude mcp add -s user chrome-devtools \
  -- npx -y chrome-devtools-mcp@latest
```

Both need Node and npm on `PATH`, and **the session must be restarted** before
the new tools appear. Say so when you offer the registration — otherwise the
user restarts for no reason, or waits for tools that were never going to show
up.

Note what is *not* in the `chrome-devtools` registration: `--browser-url`. With
it, the server attaches to a Chrome someone else had to start on port 9222 and
does nothing until they do. Without it, it launches and manages its own Chrome.
Add `--browser-url=http://127.0.0.1:9222` only for the `--chrome` path in
[attach-chrome.md](attach-chrome.md).

## `--sandbox`, and the warning bar

Playwright launches Chromium with the renderer sandbox **disabled** by default.
That is why `@playwright/mcp` offers a `--sandbox` flag to turn it back on, and
it is where the yellow bar comes from:

> You are using an unsupported command-line flag: `--no-sandbox`. Stability and
> security will suffer.

It is cosmetic in the sense that the browser still works, and not cosmetic in
the sense that a security boundary really is switched off. Register with
`--sandbox`.

If preflight reports a registration without it, offer the fix:

```bash
claude mcp remove -s user playwright
claude mcp add -s user playwright -- npx -y @playwright/mcp@latest --sandbox
```

This replaces the registration rather than amending it, so read the existing one
first and carry its options across. One that had `--user-data-dir`,
`--storage-state` or `--secrets` loses them here, and the loss is silent.

To confirm what a running browser was actually launched with, open
`chrome://version` in it and read the **Command Line** row. That is the only
check that settles the question — the flag can come from the MCP registration,
from a wrapper, or from the user's own shell alias.

## Options worth knowing

### `@playwright/mcp`

| Option | Why you would use it |
| ------ | -------------------- |
| `--sandbox` | Re-enables the Chromium sandbox. Register with it. |
| `--isolated` | Profile in memory, discarded on close. Needed if two clients share a workspace. |
| `--user-data-dir <path>` | Persistent profile of your choosing — the way to give two clients separate logins. |
| `--storage-state <path>` | Seeds cookies and localStorage into an isolated session. |
| `--secrets <dotenv>` | Fills credential fields without the values entering context. See [credentials.md](credentials.md). |
| `--device`, `--viewport-size` | Emulation, when the bug is layout-dependent. |

Its default profile lives under `~/.cache/ms-playwright/mcp-{channel}-{hash}`
(macOS: `~/Library/Caches/...`, Windows: `%LOCALAPPDATA%\ms-playwright\...`),
where the hash comes from the workspace root.
Different projects are therefore already separate; two clients in the *same*
project are not.

### `chrome-devtools-mcp`

| Option | Why you would use it |
| ------ | -------------------- |
| _(none)_ | Launches its own Chrome with a persistent profile — a login survives restarts. |
| `--isolated` | Temporary profile, cleaned up on close. Loses the login. |
| `--userDataDir <path>` | Persistent profile elsewhere; how to give two servers separate logins. |
| `--no-page-id-routing` | Opts out of page-ID routing, which is on by default. |
| `--channel`, `--executablePath` | Pick a different Chrome build. |
| `--browser-url <url>` | Attach instead of launch — the `--chrome` path only. |

Its default profile is `~/.cache/chrome-devtools-mcp/chrome-profile`, and **only
one browser may use it at a time**. Two servers pointed at the default directory
will fight; give the second one `--userDataDir` or `--isolated`.

Page-ID routing is on by default, so page-scoped calls already carry a page ID
and concurrent agents can in principle share one browser. That is the one route
out of a single MCP server, and it costs more than it looks: one browser means
one cookie jar, so every agent is the same logged-in user and every settings
change is shared. It is the low-memory option, not the safe one —
[parallel.md](parallel.md) says when it is worth it.

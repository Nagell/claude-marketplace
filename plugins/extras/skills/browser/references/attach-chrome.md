# `--chrome`: attaching to an installed Chrome

Drives a locally installed Chrome over a debugging port instead of launching
Playwright's own browser. Use it when the point *is* that Chrome build — a
Chrome-only rendering question, or an extension that only exists there.

It does **not** give you the user's everyday browsing state. The script runs
Chrome against a dedicated `~/.chrome-debug-profile`, so their extensions,
cookies and logins are absent: anything needed has to be installed and signed
into inside that profile once, and it persists there afterwards.

Opt-in only. Without `--chrome`, nothing here runs and no debugging port is
opened on anything the user browses with.

```bash
bash "${CLAUDE_SKILL_DIR}/scripts/attach-chrome.sh"          # start or reuse
bash "${CLAUDE_SKILL_DIR}/scripts/attach-chrome.sh" --stop   # stop only this instance
```

## Before running it

**A browser.** `chrome-devtools-mcp` supports Google Chrome and Chrome for
Testing; Chromium builds may work but are not guaranteed, so the script prefers
Chrome and treats `chromium` / `chromium-browser` as best effort. When it finds
nothing it prints the install command for the platform. Ask before any `sudo`
install — print the command for the user rather than running it.

**`curl`.** Used to check the DevTools endpoint. The script fails fast without
it rather than reporting a misleading startup failure.

**A server pointed at the port.** The attached browser does nothing until
something drives it:

```bash
claude mcp add -s user chrome-devtools \
  -- npx -y chrome-devtools-mcp@latest --browser-url=http://127.0.0.1:9222
```

That registration is *specific to this path* — it makes the server useless until
someone starts Chrome on 9222. The default registration in
[mcp-servers.md](mcp-servers.md) launches its own browser and needs none of it.
The session must be restarted before the tools appear.

Check `claude mcp list` first. A `chrome-devtools` server registered the default
way, without `--browser-url`, drives a Chrome of its own, not the one this
script starts. Its tools then work on the wrong browser. Register the attaching
server under a second name (`chrome-devtools-attach`, say) instead of replacing
the default one, and use that server's tools for this path.

## Reading the result

On success the script prints the `Browser` value. Relay it.

A port held by anything else is a failure, not a warning: the script exits
non-zero and starts nothing, whether the endpoint answered without being
DevTools or answered as DevTools from a profile that is not the dedicated one.
Do not work around it — tell the user to free port 9222, or drop `--chrome` and
take the default launcher.

On failure, report the script's stderr — including the captured Chrome stderr —
**verbatim**, and do not retry blindly. A missing binary, a busy port and a
locked profile look alike from the outside and need different fixes; guessing
between them burns the user's time. Then offer the default Playwright browser,
which for most tasks is the better answer anyway.

A failed launch can leave Chrome running. When the IPv4 port is already taken
Chrome falls back to `ws://[::1]:9222`, which neither the script's check nor a
server pointed at `127.0.0.1` can reach. Free the port, `--stop`, then retry.

## How it behaves

- **Reuses** a debug Chrome that is already listening instead of launching a
  second one — a second launch silently fails to bind the port and leaves a
  browser with no endpoint at all.
- **Probes the DevTools endpoint**, not the port, and requires a
  `webSocketDebuggerUrl` in the response, so neither a listener without remote
  debugging nor an unrelated HTTP service is mistaken for success. It retries
  briefly, because an idle Chrome can take seconds to answer its first request.
- **Separate profile** at `~/.chrome-debug-profile`. Logins and cookies persist
  across restarts and the user's main profile is never touched or unlocked.
  Same path on Linux and macOS.
- **Headed.** The window must stay open; the tools drive that window.
- **Stops precisely.** `--stop` matches the profile path exactly, so the user's
  normal Chrome and any similarly named profile survive.

## Platform notes

| Platform | Binary used | Notes |
| -------- | ----------- | ----- |
| Linux | `google-chrome`, `google-chrome-stable`, then `chromium`, `chromium-browser` from `PATH` | First match wins; the chromium builds are best effort |
| macOS | `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome` (also `~/Applications`, then Chromium) | Invoked directly, not via `open`, so the flags actually apply |
| WSL | The Linux binary installed inside the distro | Windows-side `chrome.exe` binds the port on the Windows loopback, which WSL2 cannot reach at `127.0.0.1` unless mirrored networking is on |
| Windows | — | Run it from WSL |

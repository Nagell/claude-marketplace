# When the browser skill breaks

Each entry is a failure seen in real use, what actually caused it, and the fix.
Report the error text to the user as it appeared; several of these look alike.

## The CLI "is not installed", but it worked last week

**Seen as:** preflight shows `playwright_cli.available: false`, or `pw.sh` fails
with npm refusing to fetch.

**Cause:** the pinned CLI is not on disk. Usually npm's cache was cleared, or the
pin in `scripts/common.sh` was bumped. Other `@playwright/cli` versions on disk
do not count. Each version expects its own browser and ffmpeg builds.

**Fix:** `launch.sh --allow-install` fetches the pinned version. A recorded
consent covers the skill's own question, but auto mode may still ask for
approval, so tell the user a download is coming. Do not substitute a global
install or `npm exec -y` of another version.

## `video-stop` fails with `ENOENT … copyfile …/playwright-artifacts-…/….webm`

**Cause:** Playwright's ffmpeg build for this CLI version is missing, so the
recorder never wrote its temp file. Preflight reports it as
`browser.ffmpeg_installed: false`.

**Fix:** `launch.sh --allow-install`. `install-browser chromium` fetches the
matching ffmpeg build along with the browser. Do not symlink another ffmpeg
build in its place: an older build does not work with a newer CLI, and the
symlink then blocks the real install.

## `Video recording has already been started`

**Cause:** an earlier `video-start` never finished: `video-stop` failed or the
script died mid-take. The session keeps that state.

**Fix:** stop and relaunch the session (`launch.sh --stop <session>`, then
launch again), then record again. Its profile survives, so the login does too.

## `Browser is already in use for <profile>` / `Daemon process exited with code 1`

**Cause:** a browser still holds that session's profile, usually one started by
a different CLI runner (a global `playwright-cli`, or another version through
`npm exec`). Each runner has its own daemon and cannot see the other's sessions,
so neither `--stop` nor `list` finds it.

**Fix:** first try `pw.sh -s=<session> close`. If nothing lists the session,
the leftover processes are the ones started with that session's exact profile
path as `--user-data-dir`. Stop only those, and only if the session is yours.
Match the whole argument: parallel sessions are named `qa`, `qa-2`, `qa-10`, so
a bare substring match on `…/qa` also kills the others.

- macOS / Linux: `pkill -f -- "--user-data-dir=<profile path>( |$)"`
- Windows: `Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match
  ('--user-data-dir="?' + [regex]::Escape('<profile path>') + '"?( |$)') }`,
  then `Stop-Process -Id` on each `ProcessId` it lists

Then stay on `pw.sh` so the leftovers do not come back.

`Daemon process exited with code 1` also happens when `open` is run against a
session that already has a browser. Use `goto` to navigate a live session.

## `Executable doesn't exist at …/chromium-NNNN/…`

**Cause:** something points at a browser build that was deleted. When a CLI
version runs `install-browser`, it removes builds no installed Playwright still
uses. A hard-coded `chromium-NNNN` path in a config, `CHROME_BIN`, or a note then
breaks without warning.

**Fix:** take the current build folder from preflight's `browser.install_dir`,
and never write a build number into a config. That is a folder, so a setting
that wants the browser program itself, such as `CHROME_BIN`, needs the
executable inside it:

| OS | Executable inside `browser.install_dir` |
| --- | --- |
| macOS | `chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing` (`chrome-mac-x64/…` on Intel) |
| Linux | `chrome-linux64/chrome` |
| Windows | `chrome-win64\chrome.exe` |

If two tools pin different CLI versions, running `install-browser` from one can
delete the other's builds.

## Headless Google Chrome refuses to start

**Seen as:** `Headless mode is disallowed by the system admin`.

**Cause:** a managed device's Chrome policy on the installed Google Chrome. No
flag gets around it.

**Fix:** use Chrome for Testing (`browser.install_dir`), which the policy does
not cover.

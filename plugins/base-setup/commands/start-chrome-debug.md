---
description: Start Chrome with remote debugging enabled (port 9222), works on WSL/Linux/macOS/Windows
---

# Start Chrome Debug

Launch Chrome with `--remote-debugging-port=9222` so MCP tools (chrome-devtools, playwright) can connect to it.

## Instructions

### Step 1 — Detect OS and find Chrome

Run the following to detect the environment:

```bash
uname -r 2>/dev/null; uname -s 2>/dev/null
```

Use the output to determine the platform:

- **WSL**: `uname -r` contains `microsoft` or `WSL`
- **macOS**: `uname -s` returns `Darwin`
- **Linux**: `uname -s` returns `Linux` (non-WSL)
- **Windows native** (PowerShell/CMD): neither command available, or environment variable `OS=Windows_NT`

### Step 2 — Locate Chrome executable

Search common paths for the platform. Use the first one that exists:

**WSL** (Windows Chrome via `/mnt/c`):
```bash
ls "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe" 2>/dev/null \
  || ls "/mnt/c/Program Files (x86)/Google/Chrome/Application/chrome.exe" 2>/dev/null \
  || ls "$HOME/.local/share/google-chrome/chrome" 2>/dev/null
```

**Linux**:
```bash
which google-chrome || which google-chrome-stable || which chromium || which chromium-browser
```

**macOS**:
```bash
ls "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" 2>/dev/null \
  || ls "$HOME/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" 2>/dev/null
```

If Chrome is not found, tell the user and stop. Do not guess paths.

### Step 3 — Set temp user-data-dir for the platform

Using a separate `--user-data-dir` ensures the debug instance is isolated from any running Chrome (avoids single-instance handoff that strips the debug flag).

- **WSL / Linux**: `$TMPDIR/chrome-debug` or `/tmp/chrome-debug`
- **macOS**: `$TMPDIR/chrome-debug`

### Step 4 — Launch Chrome

**WSL** (run Windows Chrome from WSL):
```bash
"<chrome_path>" \
  --remote-debugging-port=9222 \
  --user-data-dir="C:\\Temp\\chrome-debug" \
  --no-first-run \
  --no-default-browser-check \
  > /dev/null 2>&1 &
```

Note: `--user-data-dir` must use a **Windows path** (e.g. `C:\Temp\chrome-debug`), not a WSL path, because the process runs on Windows.

**Linux / macOS**:
```bash
"<chrome_path>" \
  --remote-debugging-port=9222 \
  --user-data-dir="/tmp/chrome-debug" \
  --no-first-run \
  --no-default-browser-check \
  > /dev/null 2>&1 &
```

### Step 5 — Verify connection

Wait ~2 seconds, then check if Chrome is reachable:

```bash
curl -s http://127.0.0.1:9222/json/version | head -c 200
```

- **Success**: Report that Chrome is running and the MCP can connect on port 9222.
- **Failure on WSL**: Remind the user that WSL2 may block localhost forwarding to the Windows host. Suggest adding `localhostForwarding=true` under `[wsl2]` in `%USERPROFILE%\.wslconfig` and restarting WSL (`wsl --shutdown`).
- **Failure on Linux/macOS**: Report the error output and stop.

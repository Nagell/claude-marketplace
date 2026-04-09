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

**WSL** — prefer native Linux Chrome installed inside WSL:
```bash
which google-chrome || which google-chrome-stable || which chromium || which chromium-browser
```

If none found, do **not** fall back to Windows Chrome. Instead, tell the user:

> Chrome was not found inside WSL. Install it with:
>
> ```bash
> wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg
> echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list
> sudo apt-get update && sudo apt-get install -y google-chrome-stable
> ```
>
> Then re-run `/start-chrome-debug`.

Stop here until Chrome is installed. Do not guess paths or use Windows Chrome.

**Linux**:
```bash
which google-chrome || which google-chrome-stable || which chromium || which chromium-browser
```

**macOS**:
```bash
ls "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" 2>/dev/null \
  || ls "$HOME/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" 2>/dev/null
```

If Chrome is not found on Linux or macOS, tell the user and stop. Do not guess paths.

### Step 3 — Set temp user-data-dir for the platform

Using a separate `--user-data-dir` ensures the debug instance is isolated from any running Chrome (avoids single-instance handoff that strips the debug flag).

- **WSL / Linux / macOS**: `$TMPDIR/chrome-debug` or `/tmp/chrome-debug`

### Step 4 — Launch Chrome

**WSL / Linux / macOS** (native Chrome process):
```bash
"<chrome_path>" \
  --remote-debugging-port=9222 \
  --user-data-dir="/tmp/chrome-debug" \
  --no-first-run \
  --no-default-browser-check \
  > /dev/null 2>&1 &
```

On WSL, since Chrome runs as a native Linux process, it binds directly to `127.0.0.1:9222` inside the WSL network namespace — no Windows port forwarding needed.

### Step 5 — Verify connection

Wait ~2 seconds, then check if Chrome is reachable:

```bash
curl -s http://127.0.0.1:9222/json/version | head -c 200
```

- **Success**: Report that Chrome is running and the MCP can connect on port 9222.
- **Failure on WSL**: Make sure the native Linux Chrome was used (not Windows Chrome). If Chrome launched but curl fails, check that no firewall rule is blocking `127.0.0.1:9222` inside WSL. Retry `curl` a couple of times — the browser may still be starting.
- **Failure on Linux/macOS**: Report the error output and stop.

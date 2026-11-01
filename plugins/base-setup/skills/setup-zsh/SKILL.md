---
name: setup-zsh
description: Install and configure Zsh with zinit, Powerlevel10k, autosuggestions, syntax highlighting, and Nerd Fonts, plus optional terminal tools (glow, mdv, btop, the herdr TUI and Herdr app), a LazyVim Neovim editor (TypeScript, Vue, Python) and Python tooling (uv, IPython)
disable-model-invocation: true
---

# Setup Zsh Environment

Install and configure a complete Zsh environment with zinit plugin manager, Powerlevel10k theme, zsh-autosuggestions, zsh-syntax-highlighting, and MesloLGS NF Nerd Font. No Oh My Zsh — zinit self-bootstraps and manages everything. Optionally sets up Neovim as a VS Code-like editor with LazyVim, and Python with uv and IPython. Handles WSL, native Linux, and macOS environments.

## How this skill is organised

This file is the run order: do Steps 1-21 in sequence. Long procedures live next to it, in this skill's directory (`<this-skill-dir>`, the directory holding this file):

- `scripts/install-font.sh` — Nerd Font install (Step 4)
- `assets/zshrc/*.zsh` — the blocks Steps 6, 7, 8 and 14 put into `~/.zshrc`. To add one, Read the asset with the Read tool, then insert its exact content with the Edit tool (Write for a fresh `~/.zshrc`) at the place the step names.
- `references/*.md` — step details: `glow.md`, `mdv.md`, `lazyvim.md`, `terminal.md`, `herdr-tui.md`, `herdr-app.md`, `herdr-spin.md`, `wsl-audio.md`

Each step below says what it checks, when to skip, which question to ask, and where the details are.

## Implementation Steps

When this command is invoked:

### 1. Detect Environment

Run this check using Bash tool:

```bash
if [[ "$(uname)" == "Darwin" ]]; then echo "MACOS"; elif grep -qi microsoft /proc/version 2>/dev/null; then echo "WSL"; else echo "LINUX"; fi
```

Store the result - it determines how Zsh is installed (Step 3) and how fonts are installed (Step 4).

Possible results:

- **WSL** - Windows Subsystem for Linux. Zsh via apt, fonts to Windows host.
- **LINUX** - Native Linux. Zsh via apt, fonts to `~/.local/share/fonts`.
- **MACOS** - macOS. Zsh is pre-installed (default shell since Catalina). Fonts to `~/Library/Fonts`. Best run after `/base-setup:setup-macos` (Finder, Spaces hotkeys, Karabiner).

### 2. Check Prerequisites

Check what is already installed. Run each line below as its own Bash tool call, all in parallel, so every result is labelled by its command:

```bash
which zsh 2>/dev/null && echo "INSTALLED" || echo "MISSING"
which git 2>/dev/null && echo "INSTALLED" || echo "MISSING"
which curl 2>/dev/null && echo "INSTALLED" || echo "MISSING"
which unzip 2>/dev/null && echo "INSTALLED" || echo "MISSING"
which fzf 2>/dev/null && echo "INSTALLED" || echo "MISSING"
which glow 2>/dev/null && echo "INSTALLED" || echo "MISSING"
which btop 2>/dev/null && echo "INSTALLED" || echo "MISSING"
test -x ~/.local/bin/mdv && echo "mdv: INSTALLED" || echo "mdv: MISSING"
test -d ~/.config/nvim && echo "nvim config: EXISTS" || echo "nvim config: MISSING"
test -d "$HOME/.local/share/zinit/zinit.git" && echo "INSTALLED" || echo "MISSING"
```

Report which components are already installed. Zinit manages all plugins and Powerlevel10k — they are downloaded automatically on the first shell launch after `.zshrc` is configured.

### 3. Install Zsh (requires user action on Linux/WSL)

Later steps need a few base tools that a fresh Debian/Ubuntu (WSL in particular) leaves out: `git` (zinit, LazyVim), `curl` (fonts, installers), `unzip` (Fira Code, Mason), `jq` (glow style, the Herdr app block), `fc-cache` from fontconfig (fonts on Linux) and `gpg` (glow's apt repo). Check them alongside zsh:

```bash
for c in zsh git curl unzip jq fc-cache gpg; do printf "%s: " $c; command -v $c >/dev/null && echo OK || echo MISSING; done
```

On LINUX or WSL, if anything is MISSING, hand over one command that installs them together, even when zsh itself is already there, instead of letting a later step fail halfway. Package names: `fontconfig` for `fc-cache`, `gnupg` for `gpg`:

```
Please run this command manually, then confirm when done:

sudo apt update && sudo apt install -y zsh git curl unzip jq fontconfig gnupg
```

Add `chsh -s $(which zsh)` below it only when zsh was MISSING. On MACOS the system has git, curl and unzip; install a missing `jq` with `brew install jq`.

If Zsh is not installed:

**If MACOS:** Zsh is the default shell since macOS Catalina. It should already be installed. If somehow missing, instruct the user:

```
Please run this command manually, then confirm when done:

brew install zsh
chsh -s $(which zsh)
```

**If LINUX or WSL:** **IMPORTANT: Claude cannot run sudo commands.** The combined command above already installs zsh; output it with `chsh -s $(which zsh)` added and wait for confirmation before proceeding. Explain that `chsh` changes the default shell and takes effect on next login/terminal session.

**DO NOT proceed to Step 4 until the user confirms Zsh is installed.** Use AskUserQuestion to ask "Have you finished installing Zsh and setting it as default shell?" with options "Yes, done" and "Skip, it was already installed".

### 4. Install Nerd Font

**Ask the user which font to install** using AskUserQuestion: "Which Nerd Font would you like to install?" with options:

- `MesloLGS NF` (recommended — specially designed for Powerlevel10k)
- `Fira Code Nerd Font` (popular programming font with ligatures)

Store the choice as `FONT_CHOICE = "meslo"` or `"fira"`. Use it in Step 11 to set the correct VS Code font family name.

Then run the install script with Bash:

```bash
bash <this-skill-dir>/scripts/install-font.sh <FONT_CHOICE>
```

The script detects the environment like Step 1 and picks the font directory: on WSL the Windows host (`/mnt/c/Users/<user>/AppData/Local/Microsoft/Windows/Fonts`, because VS Code and Windows Terminal run on Windows), on Linux `~/.local/share/fonts`, on macOS `~/Library/Fonts`. It skips files already present with a valid size, downloads the rest (MesloLGS NF: the four Regular/Bold/Italic/Bold Italic files from `romkatv/powerlevel10k-media`; Fira Code: the `FiraCodeNerdFont-*.ttf` standard variants from the nerd-fonts v3.4.0 `FiraCode.zip`, not the Mono/Propo ones), and verifies each file (MesloLGS >1MB each, `FiraCodeNerdFont-Regular.ttf` >100KB). On Linux it runs `fc-cache -fv`; macOS picks up `~/Library/Fonts` by itself. On WSL it registers the fonts under `HKCU` with `reg.exe` so Windows discovers them — no admin/sudo required.

Report what it printed (`Already installed`, `OK`, `INVALID`, `MISSING`). If it exits non-zero, some fonts are missing or invalid: report the specific failures to the user and do NOT proceed — ask them to retry or download manually.

### 5. Install fzf

fzf is required for fzf-tab completion and shell key bindings. It must be installed before the first `exec zsh`, otherwise fzf-tab silently does nothing.

If already installed (`which fzf` returned INSTALLED), skip this step.

**If MACOS or WSL (linuxbrew available):**

```bash
brew install fzf
```

**If LINUX (no brew):** **IMPORTANT: Claude cannot run sudo commands.** Output the following and wait for confirmation:

```bash
# Please run this command manually, then confirm when done:
sudo apt install fzf -y
```

Use AskUserQuestion to ask "Have you finished installing fzf?" with options "Yes, done" and "Skip".

After installing, verify:

```bash
which fzf && fzf --version
```

**Check the version, also when fzf was already installed.** Step 6 sets up fzf's key bindings with `eval "$(fzf --zsh)"`, which fzf only supports from 0.48 on. Debian 12 ships 0.38 (Ubuntu 22.04 0.29), so with the apt package every new shell prints an error and the bindings are missing. If the version is below 0.48, install the current release binary into `~/.local/bin`, no sudo:

```bash
case "$(uname -m)" in x86_64) A=linux_amd64 ;; aarch64) A=linux_arm64 ;; esac
URL=$(curl -fsSL https://api.github.com/repos/junegunn/fzf/releases/latest \
  | jq -r --arg a "$A" '.assets[] | select(.name | endswith("-" + $a + ".tar.gz")) | .browser_download_url')
mkdir -p ~/.local/bin && curl -fsSL "$URL" | tar -xz -C ~/.local/bin fzf
~/.local/bin/fzf --version
```

The new binary only wins if `~/.local/bin` comes before `/usr/bin` in PATH when `.zshrc` runs that `eval`, so in this case Step 6 adds `export PATH="$HOME/.local/bin:$PATH"` right after the P10K instant prompt block (or at the top of a new file), unless `~/.zshrc` already exports it that early.

### 6. Configure ~/.zshrc

Read the existing `~/.zshrc` file using the Read tool. If it already contains `zdharma-continuum/zinit`, zinit is already configured: only make sure `bindkey -e` (with its comment, as in `assets/zshrc/zinit.zsh`) sits right after the `source "${ZINIT_HOME}/zinit.zsh"` line, adding it with the Edit tool if missing, then skip to Step 7.

Otherwise, read the existing `~/.zshrc` with the Read tool to identify any PATH exports, NVM setup, custom functions, or keybindings to preserve. Then use the Write tool to create `~/.zshrc` with this structure, incorporating any preserved content after the aliases block:

1. The P10K instant prompt block (keep it first if the file has one). If Step 5 put fzf into `~/.local/bin`, follow it with `export PATH="$HOME/.local/bin:$PATH"`.
2. The core zinit block: the content of `assets/zshrc/zinit.zsh`, before any other config.
3. History, completion styling and aliases after the zinit block: the content of `assets/zshrc/history.zsh`.
4. Preserved content.
5. A shell integrations block before the p10k sourcing line:

```zsh
# Shell integrations
eval "$(fzf --zsh)"
```

Do NOT include `export ZSH`, `ZSH_THEME`, `plugins=(...)`, or `source $ZSH/oh-my-zsh.sh` — there is no Oh My Zsh. Zinit handles everything.

`bindkey -e` is required on every platform: when `$EDITOR` or `$VISUAL` contains "vi" (e.g. `nvim`), zsh starts in vi mode, and every Esc-prefixed key sequence breaks — Ctrl+Shift+→ ends in `C`, which vi mode reads as "change to end of line" and deletes text.

### 7. Configure Keybindings

**If MACOS** — first check that macOS itself leaves Ctrl+arrows alone. By default "Move left/right a space" sits on Ctrl+←/→ (plus hidden Ctrl+Shift+←/→ variants), so those keys never reach the terminal:

```bash
defaults export com.apple.symbolichotkeys - | python3 -c '
import plistlib, sys
hk = plistlib.loads(sys.stdin.buffer.read()).get("AppleSymbolicHotKeys", {})
FN, CTRL = 0x800000, 0x40000
problems = []
for i in ("79", "81"):  # Move left/right a space: must not sit on plain Ctrl+arrow
    e = hk.get(i)
    if e is None or (e.get("enabled") and e["value"]["parameters"][2] & ~FN == CTRL):
        problems.append(i)
for i in ("80", "82"):  # hidden Ctrl+Shift+arrow variants: must be disabled
    if hk.get(i, {}).get("enabled", True):
        problems.append(i)
print("hotkeys: OK" if not problems else "hotkeys: NOT SET (" + ", ".join(problems) + ")")
'
```

If it prints `NOT SET`, tell the user that Ctrl+←/→ and Ctrl+Shift+←/→ will switch Spaces instead of moving or selecting by word in the terminal until they run `/base-setup:setup-macos` (its Spaces hotkeys step moves them to Ctrl+Option+←/→). Continue with the rest of this step either way.

Then read `~/.zshrc` using Read tool and check these:

- **`_select_all` with `zle -K shift-select`** — the current select-all. If `_select_all` exists but uses `set-mark-command` instead, it is the earlier version that leaves arrows unable to deselect: replace just that function with the one in `assets/zshrc/keys-base.zsh` and keep the rest of the block.
- **`# >>> setup-zsh keys >>>`** — the navigation keys block. If present but without the `'^U' backward-kill-line` line, add that line before `unset _seq`; otherwise leave it.
- **`# >>> setup-zsh select-replace >>>`** — typing or pasting over a selection replaces it. If present, leave it.
- **WSL only: `_to_win_clipboard`** — the UTF-8-safe clipboard helper. If the clipboard functions exist but pipe straight into `clip.exe` or run a bare `powershell.exe Get-Clipboard`, they are the earlier version that mangles non-ASCII text: replace `_cut_to_clipboard` and `_paste_from_clipboard` with the WSL versions in `assets/zshrc/clipboard-wsl.zsh`, add `_to_win_clipboard`, and switch the `clip.exe` calls in `_backspace_or_delete_region` / `_delete_or_delete_region` to `| _to_win_clipboard`.

If all are current, skip this step. Otherwise use the Edit tool to append whatever is missing **before** the p10k sourcing line (`[[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh`) if it exists, or at the end of the file otherwise. All these blocks must come after the zinit plugins load, because they use the `shift-select` keymap that zsh-shift-select creates. Append in this order:

1. **All environments** — `assets/zshrc/keys-base.zsh`. Ctrl+A selects the whole buffer and switches to zsh-shift-select's keymap, so the selection behaves like one made with Shift+arrows: a plain arrow deselects, Backspace/Delete remove it. Ctrl+Z / Ctrl+Y are undo / redo.
2. **All environments** — `assets/zshrc/keys-nav.zsh` (the navigation keys block): Ctrl+Shift+arrows select by word / to the buffer ends on every platform (where zsh-shift-select already binds Ctrl+Shift — Linux, WSL — the loop rebinds the same widgets and changes nothing), plus Home/End, Ctrl+←/→, Ctrl+Delete, Alt/Option+Delete and `^U` (Cmd+Backspace in Ghostty) that zsh's emacs keymap leaves unbound.
3. **All environments** — `assets/zshrc/select-replace.zsh`. zsh-shift-select on its own deselects and inserts when you type over a selection, and drops non-ASCII characters (ä, ż) because its fallback covers only ASCII. This block makes typed text and bracketed pastes replace the selection; plain arrows still deselect.
4. **Clipboard bindings**, by the environment from Step 1:
   - **If WSL** — `assets/zshrc/clipboard-wsl.zsh` (converts to UTF-16LE for `clip.exe` and reads via PowerShell as UTF-8, so non-ASCII text survives).
   - **If macOS** — `assets/zshrc/clipboard-macos.zsh` (`pbcopy` / `pbpaste`).
   - **If native Linux** — `assets/zshrc/clipboard-linux.zsh`: no clipboard bindings, only Backspace/Delete removing a selection.

### 8. Configure Prefix History Search

Bind Up/Down arrows to prefix history search so they cycle through history entries beginning with whatever has already been typed — the same set `zsh-autosuggestions` draws its single grey suggestion from (autosuggestions has no cycling feature of its own).

Read `~/.zshrc` using Read tool. If it already contains `# >>> setup-zsh prefix-history >>>`, the block is already configured — skip this step.

Otherwise, Read `assets/zshrc/prefix-history.zsh` and use Edit tool to append it **after** the keybindings block from Step 7 — before the p10k sourcing line (`[[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh`) if it exists, or at the end of the file otherwise. It must load after zinit and after any other arrow-key bindings so it wins.

The block uses `up-line-or-beginning-search`, not `up-line-or-search` — the latter matches only the first word (`docker`) instead of the full typed prefix (`docker compose`), surfacing unrelated history entries. It binds both `^[[A/B` and `^[OA/OB` — terminals switch between normal and application cursor-key modes, and binding only one leaves arrows broken in the other mode.

History dedup (`hist_ignore_all_dups`, `hist_find_no_dups`) is already set in Step 6's history block — no changes needed there.

Verify:

```bash
zsh -c 'source ~/.zshrc 2>/dev/null; bindkey "^[[A"'
```

Should print `"^[[A" up-line-or-beginning-search`.

### 9. Configure WSL Audio (WSL only)

Skip this step entirely if the environment is not WSL.

This enables microphone/audio input in WSL via WSLg's PulseAudio bridge — required for tools like Claude Code voice mode.

**Check what's already set up:**

```bash
which pactl 2>/dev/null && echo "pactl: OK" || echo "pactl: MISSING"
dpkg -l libasound2-plugins 2>/dev/null | grep -q '^ii' && echo "libasound2-plugins: OK" || echo "libasound2-plugins: MISSING"
test -f /mnt/wslg/runtime-dir/pulse/native && echo "WSLg PulseAudio: OK" || echo "WSLg PulseAudio: NOT RUNNING"
test -f "$HOME/.asoundrc" && echo ".asoundrc: EXISTS" || echo ".asoundrc: MISSING"
grep -q 'PULSE_SERVER' "$HOME/.zshrc" 2>/dev/null && echo "PULSE_SERVER in .zshrc: YES" || echo "PULSE_SERVER in .zshrc: NO"
```

**If packages are missing (`pactl: MISSING` or `libasound2-plugins: MISSING`):** **IMPORTANT: Claude cannot run sudo commands.** Output the following and wait for confirmation:

```
Please run this command manually, then confirm when done:

sudo apt-get install -y pulseaudio-utils libasound2-plugins
```

Use AskUserQuestion to ask "Have you finished installing the audio packages?" with options "Yes, done" and "Skip audio setup".

If user skips, skip the rest of this step.

**If WSLg PulseAudio is not running:** Inform the user: "WSLg PulseAudio is not running — audio may not work until you restart WSL. Continue anyway and audio will work after restart."

**Configure `~/.asoundrc`:** If `~/.asoundrc` does not exist, or does not contain `pcm.default pulse`, create/overwrite it using Write tool:

```
pcm.default pulse
ctl.default pulse
```

**Add `PULSE_SERVER` to `.zshrc`:** If `PULSE_SERVER` is not already in `~/.zshrc`, use Edit tool to add it right before the zinit block, which Step 6 always writes (a fresh `.zshrc` has no `export PATH=` line to attach it to):

- old_string: `# Zinit - auto-installs itself if missing`
- new_string: `export PULSE_SERVER=unix:/mnt/wslg/runtime-dir/pulse/native` + blank line + `# Zinit - auto-installs itself if missing`

Report what was configured. Inform the user that audio input (microphone) is now routed through WSLg — tools like Claude Code `/voice` should work after reopening the terminal.

**Microphone that survives WSLg hangs:** WSLg's microphone link can fail after a few dictations and hang its PulseAudio until `wsl --shutdown` (more often when a Windows dictation app shares the microphone). Unless `~/.zshrc` already contains `# >>> setup-zsh claude-pulse >>>`, use AskUserQuestion: "Record Claude Code voice through a PulseAudio server on Windows instead of WSLg? Needs a Windows install and mirrored networking" with options "Yes (Recommended)" and "No, keep WSLg". On yes, follow `references/wsl-audio.md` from top to bottom.

### 10. Port Bash Environment to Zsh

Step 6 writes a fresh `~/.zshrc`, and zsh does not read `~/.bashrc` or `~/.profile`, so environment setup that lives there is lost. Common breakage: NVM (node/npm/pnpm missing), custom PATH entries, SSH agent auto-start, other exports.

Scan the user's existing bash config files for portable environment setup:

```bash
# Extract export, source, PATH, and eval statements from bash configs
for file in "$HOME/.bashrc" "$HOME/.profile" "$HOME/.bash_profile"; do
  if [[ -f "$file" ]]; then
    echo "=== $file ==="
    grep -E '^\s*(export |source |\. |PATH=|eval )' "$file" | grep -v -E '(shopt|bash_completion|PS1=|PROMPT_|HISTCONTROL|HISTSIZE|HISTFILESIZE|__git_ps1|BASH_)'
  fi
done
```

Read the output and identify portable statements that should carry over to zsh. Common ones to include:

- **NVM**: the `export NVM_DIR` / `source nvm.sh` / `nvm bash_completion` block
- **Custom PATH entries**: `~/.local/bin`, tool-specific paths, cargo, go, etc.
- **SSH agent**: `eval "$(ssh-agent)"` or keychain setup
- **Custom env vars**: `export EDITOR`, `export GOPATH`, etc.
- **pyenv/rbenv/fnm init**: `eval "$(pyenv init -)"` etc.

Things to **exclude** (bash-specific, already handled by the zsh config from Step 6, or not portable):

- `shopt` commands
- bash-completion sourcing
- `PS1`/`PROMPT_COMMAND` (p10k handles this)
- `HISTCONTROL`/`HISTSIZE`/`HISTFILESIZE` (Step 6's history block sets `HISTSIZE`, `SAVEHIST` and the dedup options)
- Anything referencing `BASH_` variables

Read `~/.zshrc` using Read tool, then use Edit tool to append the portable statements **before** the p10k sourcing line (`[[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh`) if it exists, or at the end of the file otherwise. Wrap them in a clearly marked block:

```bash
# --- Ported from bash config ---
<portable statements here>
# --- End ported from bash config ---
```

After appending, verify key commands are resolvable:

```bash
zsh -c 'source ~/.zshrc 2>/dev/null; for cmd in node npm pnpm git; do which $cmd 2>/dev/null && echo "$cmd: OK" || echo "$cmd: NOT FOUND"; done'
```

Report results to the user. If commands like `node` are missing, suggest they check NVM was ported correctly or run `nvm install --lts` in a new zsh session.

If no portable statements are found in bash configs, skip this step and inform the user that no environment setup needed porting.

#### Default editor (optional)

If `EDITOR` and `VISUAL` are not already exported (in `~/.zshenv`, `~/.zshrc` or the ported block above), use AskUserQuestion: "Set a default editor for git, crontab and other tools that open one?" with options "nvim", "vim", "nano" and "Skip". If one is picked, append to `~/.zshenv` (create it if missing; `~/.zshenv` is read by every zsh, including non-interactive ones that tools spawn):

```zsh
export EDITOR=nvim
export VISUAL=nvim
```

With `nvim` or `vim` this relies on the `bindkey -e` line from Step 6 — without it zsh switches the prompt to vi mode.

### 11. VS Code Terminal Font Configuration

Use the `FONT_CHOICE` from Step 4 to determine the font family name:

- `FONT_CHOICE = "meslo"` → font family: `"MesloLGS NF"`
- `FONT_CHOICE = "fira"` → font family: `"FiraCode Nerd Font"`

Set `"terminal.integrated.fontFamily": "<font family>"` in all VS Code settings files — both the default and any profile-specific ones. VS Code profiles store their own `settings.json` that overrides the default.

First, locate the VS Code config directory and find all `settings.json` files. On WSL, VS Code runs on Windows and reads its user settings there (the terminal font is a window setting, even for a WSL window), so `~/.config/Code` inside Linux would have no effect:

```bash
if [[ "$(uname)" == "Darwin" ]]; then
  VSCODE_DIR="$HOME/Library/Application Support/Code"
elif grep -qi microsoft /proc/version 2>/dev/null; then
  VSCODE_DIR="/mnt/c/Users/$(cmd.exe /c 'echo %USERNAME%' 2>/dev/null | tr -d '\r')/AppData/Roaming/Code"
else
  VSCODE_DIR="$HOME/.config/Code"
fi
# Default settings
echo "${VSCODE_DIR}/User/settings.json"
# Profile-specific settings (override default)
find "${VSCODE_DIR}/User/profiles" -name "settings.json" 2>/dev/null
```

For **each** `settings.json` found, read it using the Read tool, then:

- If `"terminal.integrated.fontFamily"` already exists, use Edit tool to update its value to the chosen font family name
- If it does not exist, use Edit tool to add `"terminal.integrated.fontFamily": "<font family>"` inside the top-level JSON object (after the opening `{`)
- If the file does not exist, create it with Write tool containing: `{ "terminal.integrated.fontFamily": "<font family>" }`

Report which files were updated and which already had the correct value.

### 12. Configure Windows Terminal Shift+Enter (WSL only)

Skip this step entirely if the environment is not WSL.

Windows Terminal submits on plain Enter and does nothing on Shift+Enter by default, which makes multi-line input in CLIs like Claude Code awkward. Add a keybinding so Shift+Enter inserts a newline.

Locate the Windows Terminal `settings.json` (checks stable, preview, and unpackaged locations):

```bash
WINUSER=$(cmd.exe /c "echo %USERNAME%" 2>/dev/null | tr -d '\r')
for p in \
  "/mnt/c/Users/${WINUSER}/AppData/Local/Packages/Microsoft.WindowsTerminal_8wekyb3d8bbwe/LocalState/settings.json" \
  "/mnt/c/Users/${WINUSER}/AppData/Local/Packages/Microsoft.WindowsTerminalPreview_8wekyb3d8bbwe/LocalState/settings.json" \
  "/mnt/c/Users/${WINUSER}/AppData/Local/Microsoft/Windows Terminal/settings.json"; do
  [[ -f "$p" ]] && echo "FOUND: $p"
done
```

If nothing is found, report that Windows Terminal settings were not located and skip this step.

Read the found `settings.json` with the Read tool. Check whether a `shift+enter` binding already exists (search for `"shift+enter"`). If it does, report it as already configured and skip.

If not, use the Edit tool to add an entry as the **first** element of the top-level `keybindings` array (right after the opening `[`):

```json
{
    "command": { "action": "sendInput", "input": "\n" },
    "keys": "shift+enter"
},
```

Preserve the existing indentation and trailing commas. Windows Terminal auto-reloads settings on save — tell the user to open a new tab/window to pick up the change.

If `\n` still submits instead of inserting a newline on the user's terminal build, `\r` is the fallback value.

### 13. Fix Powerlevel10k Right Prompt Wrapping (optional)

On narrow terminals, right prompt segments on line 1 cause powerline cap symbols to wrap and create graphical artifacts when resizing the terminal window. This fix removes all line 1 right segments and clears the cap symbols that render as invisible artifacts even when no segments are shown.

**Trade-off:** All right-side prompt info (exit code, execution time, node/python/etc. versions, background jobs, etc.) will no longer be visible. Only the left prompt remains.

Use AskUserQuestion to ask: "Do you want to fix p10k right prompt wrapping artifacts on narrow terminals? (Trade-off: all right-side prompt info — exit code, execution time, version managers, etc. — will no longer be visible)" with options "Yes, apply fix" and "No, skip".

If the user skips, proceed to Step 14.

If the user accepts:

**Check if `~/.p10k.zsh` exists:**

```bash
test -f ~/.p10k.zsh && echo "EXISTS" || echo "MISSING"
```

If `MISSING`: inform the user — "The fix requires `~/.p10k.zsh`. It is generated when you run the p10k wizard, which launches automatically on the first `exec zsh`. Run the wizard first, then re-apply this fix manually or re-run the command." Skip the rest of this step.

If `EXISTS`, read `~/.p10k.zsh` using the Read tool, then apply these changes with the Edit tool:

**1. Clear line 1 right prompt segments** — replace the entire `POWERLEVEL9K_RIGHT_PROMPT_ELEMENTS=(...)` block with one that has no line 1 segments and only `newline` on line 2. The exact content of the block will vary, but use Edit tool to replace from the opening `typeset -g POWERLEVEL9K_RIGHT_PROMPT_ELEMENTS=(` line through the closing `)` with:

```zsh
  typeset -g POWERLEVEL9K_RIGHT_PROMPT_ELEMENTS=(
    # =========================[ Line #1 ]=========================
    # (all line 1 segments removed to prevent wrapping/artifacts on narrow terminals)
    # =========================[ Line #2 ]=========================
    newline
  )
```

**2. Clear right prompt powerline cap symbols** — these render invisible frame artifacts even when no segments are present. Find and replace:

- `POWERLEVEL9K_RIGHT_PROMPT_FIRST_SEGMENT_START_SYMBOL=''` → `POWERLEVEL9K_RIGHT_PROMPT_FIRST_SEGMENT_START_SYMBOL=''`
- `POWERLEVEL9K_RIGHT_PROMPT_LAST_SEGMENT_END_SYMBOL=''` → `POWERLEVEL9K_RIGHT_PROMPT_LAST_SEGMENT_END_SYMBOL=''`

Note: the exact unicode values may differ depending on the style chosen in the p10k wizard — search for `RIGHT_PROMPT_FIRST_SEGMENT_START_SYMBOL` and `RIGHT_PROMPT_LAST_SEGMENT_END_SYMBOL` by name, not by value.

Run to apply immediately:

```bash
source ~/.p10k.zsh
```

### 14. Install glow

glow renders markdown in the terminal, but glow 3.x word-wraps at a hard-coded 80 columns and never reads the real terminal size — wide tables get shredded to one character per column unless the width is passed explicitly on every call.

Skip this step if `which glow` returned INSTALLED in Step 2.

**If MACOS, or LINUX/WSL with linuxbrew available:**

```bash
brew install glow
```

**If LINUX or WSL without brew** - glow lives in Charm's own apt repo, not in the Ubuntu archive.

**IMPORTANT: Claude cannot run sudo commands.** Output the following and wait for confirmation:

```bash
# Please run these commands manually, then confirm when done:
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://repo.charm.sh/apt/gpg.key | sudo gpg --dearmor -o /etc/apt/keyrings/charm.gpg
echo "deb [signed-by=/etc/apt/keyrings/charm.gpg] https://repo.charm.sh/apt/ * *" | sudo tee /etc/apt/sources.list.d/charm.list
sudo apt update && sudo apt install glow -y
```

Use AskUserQuestion to ask "Have you finished installing glow?" with options "Yes, done" and "Skip".

Verify:

```bash
glow --version
```

Then follow `references/glow.md` in order: build the wide style `~/.config/glow/glow-wide.json` (needs `jq`), write `~/.config/glow/glow.yml`, add the `glow()` / `glowide()` functions from `assets/zshrc/glow.zsh` at the end of `~/.zshrc` (skip if it already contains `# >>> setup-zsh glow >>>`; function definitions need not go before the p10k sourcing line), and verify the rendered width.

### 15. Install mdv (Neovim Markdown viewer, optional)

`mdv FILE.md` views Markdown in a throwaway Neovim profile: `/` search, mouse, live reload that keeps the scroll position while a file is still being written, wide pipe tables reflowed into box tables that fit the window, and copy-on-select — a mouse selection lands on the system clipboard the moment the button is released, with a "copied N lines to clipboard" toast, the way Herdr does it. glow (Step 14) stays useful for one-shot renders; mdv is for watching a plan or report while an agent writes it.

Everything installs under `$HOME` — no sudo. Needs `git`, `curl`, `tar` and access to GitHub.

Use AskUserQuestion to ask "Install mdv, a Neovim-based Markdown viewer with live reload and copy-on-select?" with options "Yes" and "Skip". If skipped, continue with Step 16. On yes, follow the **Install** section of `references/mdv.md` (Neovim 0.10+, launcher and config, plugins, PATH, verify, what to tell the user).

If Step 2 reported `mdv: INSTALLED`, don't ask the question above. Instead, check whether the installed files match this skill's copies, since a skipped step never delivers launcher or config updates:

```bash
A=<this-skill-dir>/assets/mdv
for f in init.lua lazy-lock.json lua/mdreflow.lua lua/mdview.lua; do cmp -s "$A/$f" ~/.config/mdv/$f || echo "OUTDATED: ~/.config/mdv/$f"; done
cmp -s "$A/mdv" ~/.local/bin/mdv || echo "OUTDATED: ~/.local/bin/mdv"
```

If nothing prints, report mdv as already installed and up to date, and continue with Step 16. Otherwise list the outdated files and use AskUserQuestion: "Update mdv to this skill's version? Local changes to these files are overwritten" with options "Yes, update (Recommended)" and "Skip". On yes, run **Copy the launcher and config** from `references/mdv.md`. If `lazy-lock.json` was among them, also run **Install the plugins** there so the pinned plugin versions are checked out. Then continue with Step 16.

### 16. Set up Neovim as an editor with LazyVim (optional)

Turns `nvim` into a VS Code-like editor: [LazyVim](https://www.lazyvim.org) with a file tree, fuzzy file search, TypeScript (vtsls), Vue (vue_ls), Python (pyright, ruff), ESLint, Prettier, JSON/YAML/Markdown support, lazygit, Catppuccin Mocha with a transparent background (the same theme mdv uses), a few VS Code shortcuts, and Windows-style selection, copy/paste and undo/redo. It lives in `~/.config/nvim`; mdv keeps its own `~/.config/mdv` (`NVIM_APPNAME=mdv`), so neither affects the other.

Use AskUserQuestion to ask "Set up Neovim as a code editor (LazyVim with file tree, TypeScript, Vue, Python, ESLint/Prettier, VS Code-style shortcuts)?" with options "Yes" and "Skip". If skipped, continue with Step 17.

If Step 2 reported `nvim config: EXISTS`, do not overwrite it. Report that `~/.config/nvim` already exists and skip this step, unless the user explicitly asks to replace it — then move it aside first (`mv ~/.config/nvim ~/.config/nvim.bak-$(date +%Y%m%d)`, same for `~/.local/share/nvim`).

An existing config that is LazyVim (has `~/.config/nvim/lazyvim.json`) can still pick up language support it lacks. Compare its `extras` with `assets/lazyvim/lazyvim.json`. If any are missing (for example `lang.vue` or `lang.python`), use AskUserQuestion to offer adding them. On yes, insert the missing entries into the user's `extras` list with the Edit tool, then run only the two headless passes under **Install plugins, language servers and parsers** in `references/lazyvim.md`. Use `Lazy! install` instead of `Lazy! restore` there, so the user's own pinned plugin versions stay as they are.

Otherwise (fresh install, or replacing a moved-aside config) follow the **Install** section of `references/lazyvim.md`: Neovim 0.11+ (LazyVim needs newer than mdv's 0.10), the tools it expects (with a sudo hand-off on Linux/WSL without brew), the starter plus this skill's `assets/lazyvim/` files, the global markdownlint rules (ask before replacing an existing `~/.markdownlint-cli2.yaml`), the headless plugin/LSP/parser install, the verify checks, and the key summary to tell the user.

### 17. Set up Python: uv, a current Python and IPython (optional)

Distribution Pythons are often old (Debian 12 ships 3.11). Below 3.13 the built-in console has no colors, and its completion is basic in every version. This step installs [uv](https://docs.astral.sh/uv/), uses it to put a current Python on PATH ahead of the system one, and adds IPython as the everyday console. Everything goes under `$HOME`, so no sudo is needed.

Use AskUserQuestion to ask "Set up Python (uv, Python 3.14 as your default python/python3, IPython console)?" with options "Yes" and "Skip". If skipped, continue with Step 18.

```bash
command -v uv && uv --version || echo "uv: MISSING"
python3 --version; command -v python3
command -v ipython && ipython --version || echo "ipython: MISSING"
```

#### Install uv

Skip if uv is already installed.

**If MACOS, or LINUX/WSL with linuxbrew available:** `brew install uv`

**Otherwise** use the official installer, which writes to `~/.local/bin`:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### Python 3.14 as the user default

```bash
uv python install 3.14 --default
```

This creates `python`, `python3` and `python3.14` links in `~/.local/bin`. uv marks `--default` as experimental and prints a warning, but the install works. The system `/usr/bin/python3` is not touched, which matters because apt and other OS tools depend on it. The links only take effect if `~/.local/bin` comes before `/usr/bin` in PATH. Check with `zsh -i -c 'command -v python3'`. If that does not print `~/.local/bin/python3`, add the `setup-zsh local-bin` block from `references/mdv.md` (**Make sure ~/.local/bin is on PATH**).

uv's Python is marked as externally managed, so a global `pip install` is refused. Packages go into a project venv (`uv venv`, then `uv pip install <pkg>`), and command-line tools go in with `uv tool install`.

#### IPython

```bash
uv tool install ipython
```

This gives a global `ipython` with colors, completion and `%autoreload`. It runs in its own environment, so it can import files from the current folder but not packages installed into a project venv. For a project with dependencies, also run `uv pip install ipython` inside that project's activated venv.

#### Verify

```bash
zsh -i -c 'python3 --version; ipython --version' 2>/dev/null
```

Expect `Python 3.14.x` and an IPython version. Terminals that are already open still remember the old `python3` path until `hash -r` or a new tab.

Then tell the user:

```
Python is set up. python / python3 now run 3.14; /usr/bin/python3 stays for the OS.
  ipython                         console with colors and Tab completion
  %load_ext autoreload            then %autoreload 2: edited files reload before each command
  import mymodule; mymodule.f()   call functions directly (IPython lines are Python, not shell)
  %run script.py --flag           run a script with command-line flags from inside IPython
  ipython script.py -- --flag     same from the shell (the -- stops IPython reading --flag itself)
  uv venv && uv pip install X     per-project packages; activate with source .venv/bin/activate
Open nvim after activating a venv so pyright sees that venv's packages.
```

### 18. Install btop

btop is a resource monitor (CPU, memory, disks, network, process list) with a much nicer terminal UI than `top`/`htop`. Standalone tool, no `.zshrc` wiring needed.

Skip this step if `which btop` returned INSTALLED in Step 2.

**If MACOS, or LINUX/WSL with linuxbrew available:**

```bash
brew install btop
```

**If LINUX or WSL without brew:** **IMPORTANT: Claude cannot run sudo commands.** Output the following and wait for confirmation:

```bash
# Please run this command manually, then confirm when done:
sudo apt install btop -y
```

Use AskUserQuestion to ask "Have you finished installing btop?" with options "Yes, done" and "Skip".

Verify:

```bash
btop --version
```

### 19. Set up the terminal (macOS: Ghostty, WSL: Windows Terminal profile)

Skip this step on native Linux.

#### Work directory

Several settings below open a projects folder. Look for an existing one first:

```bash
for d in ~/Development ~/Projects ~/projects ~/Code ~/code ~/dev ~/src ~/repos ~/workspace; do [[ -d $d ]] && echo "$d"; done
```

**If MACOS**, `defaults read com.apple.finder NewWindowTargetPath 2>/dev/null` may already name one (Finder's new-window folder); offer it first.

Use AskUserQuestion: "Which folder holds your projects?" with the folders found as options (first one marked "(Recommended)"). If none were found, offer `~/Development` (Recommended) and let the user type another. Store it as `WORK_DIR` (a path relative to `$HOME`, e.g. `Development`); create it with `mkdir -p` if it does not exist yet.

#### If MACOS: Ghostty

Follow the **Ghostty (macOS)** section of `references/terminal.md`: check for Ghostty and offer to install it (asks "Install Ghostty as your terminal?"; it restores tabs, splits and folders after Cmd+Q and can hand Shift/Ctrl+arrows to zsh), merge the keybinds and settings into `config.ghostty` (back it up, add only missing keys, never overwrite), set Claude Code's Ctrl+V / Option+V paste keys if Claude Code is installed, and offer the optional work-directory and translucency settings (AskUserQuestion, multiSelect).

#### If WSL: Windows Terminal profile for herdr

There is no auto-start in `~/.zshrc` on WSL; a dedicated Windows Terminal profile starts the herdr TUI (installed in Step 20) instead. It is only for the TUI; the Herdr app is its own window. Use AskUserQuestion: "Add a Windows Terminal profile that opens straight into the herdr TUI?" — "Yes (Recommended)" / "No, I won't use the herdr TUI". If no, skip the rest of this step.

If yes, follow the **Windows Terminal profile for herdr (WSL)** section of `references/terminal.md`: add a `herdr` profile to `settings.json` (back it up first), then ask "Make herdr the default Windows Terminal profile?".

### 20. Install herdr: the TUI, the app, or both (optional)

[herdr](https://herdr.dev) runs AI coding agents (Claude Code, Codex, etc.) side by side, with a sidebar that tracks each agent's status. It comes in two independent products that can be installed side by side; nothing else in this skill depends on either:

- **Herdr TUI** (`herdr`): a terminal app that runs inside your terminal (Windows Terminal, Ghostty). Resumes Claude Code after a restart by itself. Extras: herdr-spin, notifications, reopen nvim, btop, lazygit and mdv after a restart (mdv-restore).
- **Herdr app** (`herdr-app` + herdr-core `hc`): a native window. On WSL it runs inside WSL and shows through WSLg. Claude Code, nvim, btop, lazygit and mdv come back after a reboot through herdr-agent-resume and two zsh blocks.

**1. Check what is installed.**

```bash
which herdr 2>/dev/null && herdr --version || echo "herdr TUI: NOT INSTALLED"
command -v herdr-app >/dev/null && echo "herdr app: INSTALLED" || echo "herdr app: NOT INSTALLED"
```

**2. Ask which one to set up.** Use AskUserQuestion: "Which herdr do you want to set up?" with options "Herdr TUI", "Herdr app", "Both" and "Neither". Mention what is already installed in the question; picking an installed one still runs its configuration.

- **Neither:** skip to Step 21.
- **Herdr app** or **Both:** follow this skill's `references/herdr-app.md` from top to bottom. With **Herdr app** alone, skip the rest of this step afterwards and go to Step 21.
- **Herdr TUI** or **Both:** then follow `references/herdr-tui.md` from top to bottom: install with herdr's official installer if `NOT INSTALLED` (no sudo; on failure report the exact error and skip the rest of this step, no automatic retry), the Ghostty auto-start block on macOS (asks "Start herdr automatically when Ghostty opens?"), the version check against herdr-spin's 0.8.2 minimum, 1-line wheel scrolling (asks "Scroll 1 line per mouse wheel notch in herdr?"), and a multiSelect "herdr is installed. Set up any of these?" offering only what is still missing: herdr-spin, agent notifications, reopen nvim, btop, lazygit and mdv after a restart (mdv-restore).

### 21. Apply Configuration

Run using Bash tool to verify the config is valid:

```bash
zsh -c 'source ~/.zshrc && echo "Config loaded successfully"' 2>&1 | head -20
```

If this produces errors, report them to the user. Minor warnings about "no tty" or p10k configuration are expected and can be ignored.

Inform the user:

```
Setup complete! To apply changes:
- Close and reopen your terminal, OR
- Run: exec zsh

On first launch, Powerlevel10k will start its configuration wizard (p10k configure).
You can re-run it anytime with: p10k configure
```

## Error Handling

If any step fails:

- Report the specific command that failed and the error message
- For network errors (git clone, curl): suggest checking internet connectivity and retrying
- For permission errors: output the exact command the user needs to run manually with sudo
- **DO NOT retry failed commands automatically** - ask the user how to proceed

## Important Notes

- **NEVER run sudo commands directly** - always instruct the user to run them manually
- **NEVER clone git repos into the current directory** - always specify the full target path
- **Skip components that are already installed** - report them as "already installed"
- **Detect WSL vs native Linux vs macOS first** - this affects Zsh installation and font paths
- **On macOS**, Zsh is pre-installed - skip Zsh installation, fonts go to `~/Library/Fonts`
- **On macOS**, `brew` is used instead of `apt` if any packages are needed
- **glow never auto-detects terminal width.** If tables render squeezed, the `glow()` function from Step 14 is not loaded - check `which glow` returns a function rather than `/usr/bin/glow`.
- **mdv copies over OSC 52.** If a selection shows the "copied" toast but the clipboard is unchanged, the terminal or multiplexer dropped the OSC 52 write — see `references/mdv.md`.

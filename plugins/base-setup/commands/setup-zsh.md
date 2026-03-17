---
description: Install and configure Zsh with Oh My Zsh, Powerlevel10k, autosuggestions, syntax highlighting, and Nerd Fonts
---

# Setup Zsh Environment

Install and configure a complete Zsh environment with Oh My Zsh, Powerlevel10k theme, zsh-autosuggestions, zsh-syntax-highlighting, and MesloLGS NF Nerd Font. Handles WSL, native Linux, and macOS environments.

## Implementation Steps

When this command is invoked:

### 1. Detect Environment

Run this check using Bash tool:

```bash
if [[ "$(uname)" == "Darwin" ]]; then echo "MACOS"; elif grep -qi microsoft /proc/version 2>/dev/null; then echo "WSL"; else echo "LINUX"; fi
```

Store the result - it determines how Zsh is installed (Step 3) and how fonts are installed (Step 7).

Possible results:

- **WSL** - Windows Subsystem for Linux. Zsh via apt, fonts to Windows host.
- **LINUX** - Native Linux. Zsh via apt, fonts to `~/.local/share/fonts`.
- **MACOS** - macOS. Zsh is pre-installed (default shell since Catalina). Fonts to `~/Library/Fonts`.

### 2. Check Prerequisites

Check what is already installed by running these checks in parallel using Bash tool:

```bash
which zsh 2>/dev/null && echo "INSTALLED" || echo "MISSING"
```

```bash
test -d "$HOME/.oh-my-zsh" && echo "INSTALLED" || echo "MISSING"
```

```bash
test -d "${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/themes/powerlevel10k" && echo "INSTALLED" || echo "MISSING"
```

```bash
test -d "${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins/zsh-autosuggestions" && echo "INSTALLED" || echo "MISSING"
```

```bash
test -d "${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins/zsh-syntax-highlighting" && echo "INSTALLED" || echo "MISSING"
```

```bash
test -d "${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins/zsh-shift-select" && echo "INSTALLED" || echo "MISSING"
```

Report which components are already installed and which need installation. Skip already-installed components in subsequent steps.

### 3. Install Zsh (requires user action on Linux/WSL)

If Zsh is not installed:

**If MACOS:** Zsh is the default shell since macOS Catalina. It should already be installed. If somehow missing, instruct the user:

```
Please run this command manually, then confirm when done:

brew install zsh
chsh -s $(which zsh)
```

**If LINUX or WSL:**

**IMPORTANT: Claude cannot run sudo commands.** Output the following message to the user and wait for confirmation before proceeding:

```
Please run these commands manually in your terminal, then confirm when done:

sudo apt update && sudo apt install zsh -y
chsh -s $(which zsh)
```

Explain that `chsh` changes the default shell and takes effect on next login/terminal session.

**DO NOT proceed to Step 4 until the user confirms Zsh is installed.** Use AskUserQuestion to ask "Have you finished installing Zsh and setting it as default shell?" with options "Yes, done" and "Skip, it was already installed".

### 4. Install Oh My Zsh

If Oh My Zsh is not already installed (`~/.oh-my-zsh` does not exist):

Run using Bash tool:

```bash
sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended
```

The `--unattended` flag prevents the installer from switching the shell or prompting. This should succeed without sudo.

If `~/.oh-my-zsh` already exists, skip this step and report it as already installed.

### 5. Install Powerlevel10k Theme

If not already installed:

Run using Bash tool:

```bash
git clone --depth=1 https://github.com/romkatv/powerlevel10k.git "${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/themes/powerlevel10k"
```

This clones into the Oh My Zsh custom themes directory - NOT into the current working directory.

### 6. Install Plugins

If not already installed, clone each plugin into the Oh My Zsh custom plugins directory. Run these in parallel using Bash tool:

**zsh-autosuggestions:**

```bash
git clone https://github.com/zsh-users/zsh-autosuggestions.git "${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins/zsh-autosuggestions"
```

**zsh-syntax-highlighting:**

```bash
git clone https://github.com/zsh-users/zsh-syntax-highlighting.git "${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins/zsh-syntax-highlighting"
```

**zsh-shift-select** (Shift+Arrow selection):

```bash
git clone https://github.com/jirutka/zsh-shift-select.git "${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins/zsh-shift-select"
```

### 7. Install MesloLGS NF Nerd Font

Download the four MesloLGS NF font files. The installation location depends on the environment detected in Step 1.

First, check if fonts are already installed by looking for them in the appropriate directory.

**If WSL:**

Fonts must be installed on the Windows host for VS Code to use them. Check if they already exist:

```bash
WINUSER=$(cmd.exe /c "echo %USERNAME%" 2>/dev/null | tr -d '\r')
FONTDIR="/mnt/c/Users/${WINUSER}/AppData/Local/Microsoft/Windows/Fonts"
ls "${FONTDIR}"/MesloLGS*.ttf 2>/dev/null | wc -l
```

If the count is 4, all fonts are already installed - skip downloading and report them as already installed.

If fewer than 4, download the missing fonts:

```bash
WINUSER=$(cmd.exe /c "echo %USERNAME%" 2>/dev/null | tr -d '\r')
FONTDIR="/mnt/c/Users/${WINUSER}/AppData/Local/Microsoft/Windows/Fonts"
mkdir -p "${FONTDIR}"
declare -A fontmap=( ["Regular"]="Regular" ["Bold"]="Bold" ["Italic"]="Italic" ["Bold Italic"]="Bold%20Italic" )
for font in "Regular" "Bold" "Italic" "Bold Italic"; do
  filepath="${FONTDIR}/MesloLGS NF ${font}.ttf"
  if [[ -f "$filepath" ]] && [[ $(stat -c%s "$filepath" 2>/dev/null || echo 0) -gt 1000000 ]]; then
    echo "Already installed: MesloLGS NF ${font}.ttf"
  else
    curl -fsSL -o "$filepath" "https://github.com/romkatv/powerlevel10k-media/raw/master/MesloLGS%20NF%20${fontmap[$font]}.ttf"
  fi
done
```

After downloading, **verify all 4 files exist and have valid size** (>1MB each):

```bash
WINUSER=$(cmd.exe /c "echo %USERNAME%" 2>/dev/null | tr -d '\r')
FONTDIR="/mnt/c/Users/${WINUSER}/AppData/Local/Microsoft/Windows/Fonts"
MISSING=0
for font in "Regular" "Bold" "Italic" "Bold Italic"; do
  filepath="${FONTDIR}/MesloLGS NF ${font}.ttf"
  if [[ -f "$filepath" ]]; then
    size=$(stat -c%s "$filepath" 2>/dev/null || echo 0)
    if [[ $size -gt 1000000 ]]; then
      echo "OK: MesloLGS NF ${font}.ttf (${size} bytes)"
    else
      echo "INVALID (too small): MesloLGS NF ${font}.ttf (${size} bytes)"
      MISSING=$((MISSING+1))
    fi
  else
    echo "MISSING: MesloLGS NF ${font}.ttf"
    MISSING=$((MISSING+1))
  fi
done
echo "Missing fonts: ${MISSING}"
```

If any fonts are missing or invalid, report the specific failures to the user and do NOT proceed — ask them to retry or download manually.

Then **register fonts in Windows registry** so Windows discovers them:

```bash
WINUSER=$(cmd.exe /c "echo %USERNAME%" 2>/dev/null | tr -d '\r')
WINFONTDIR="C:\\Users\\${WINUSER}\\AppData\\Local\\Microsoft\\Windows\\Fonts"
for font in "Regular" "Bold" "Italic" "Bold Italic"; do
  regname="MesloLGS NF ${font} (TrueType)"
  regpath="${WINFONTDIR}\\MesloLGS NF ${font}.ttf"
  reg.exe add "HKCU\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Fonts" /v "$regname" /t REG_SZ /d "$regpath" /f
done
```

This registers the fonts under the current user's registry hive — no admin/sudo required.

**If native Linux:**

Check if fonts already exist:

```bash
FONTDIR="$HOME/.local/share/fonts"
ls "${FONTDIR}"/MesloLGS*.ttf 2>/dev/null | wc -l
```

If the count is 4, skip downloading. Otherwise, download missing fonts:

```bash
FONTDIR="$HOME/.local/share/fonts"
mkdir -p "${FONTDIR}"
declare -A fontmap=( ["Regular"]="Regular" ["Bold"]="Bold" ["Italic"]="Italic" ["Bold Italic"]="Bold%20Italic" )
for font in "Regular" "Bold" "Italic" "Bold Italic"; do
  filepath="${FONTDIR}/MesloLGS NF ${font}.ttf"
  if [[ -f "$filepath" ]] && [[ $(stat -c%s "$filepath" 2>/dev/null || echo 0) -gt 1000000 ]]; then
    echo "Already installed: MesloLGS NF ${font}.ttf"
  else
    curl -fsSL -o "$filepath" "https://github.com/romkatv/powerlevel10k-media/raw/master/MesloLGS%20NF%20${fontmap[$font]}.ttf"
  fi
done
fc-cache -fv
```

After downloading, **verify all 4 files exist and have valid size** (>1MB each):

```bash
FONTDIR="$HOME/.local/share/fonts"
MISSING=0
for font in "Regular" "Bold" "Italic" "Bold Italic"; do
  filepath="${FONTDIR}/MesloLGS NF ${font}.ttf"
  if [[ -f "$filepath" ]]; then
    size=$(stat -c%s "$filepath" 2>/dev/null || echo 0)
    if [[ $size -gt 1000000 ]]; then
      echo "OK: MesloLGS NF ${font}.ttf (${size} bytes)"
    else
      echo "INVALID (too small): MesloLGS NF ${font}.ttf (${size} bytes)"
      MISSING=$((MISSING+1))
    fi
  else
    echo "MISSING: MesloLGS NF ${font}.ttf"
    MISSING=$((MISSING+1))
  fi
done
echo "Missing fonts: ${MISSING}"
```

If any fonts are missing or invalid, report the specific failures to the user and do NOT proceed — ask them to retry or download manually.

The `fc-cache` command refreshes the font cache so the fonts are immediately available.

**If macOS:**

Check if fonts already exist:

```bash
FONTDIR="$HOME/Library/Fonts"
ls "${FONTDIR}"/MesloLGS*.ttf 2>/dev/null | wc -l
```

If the count is 4, skip downloading. Otherwise, download missing fonts:

```bash
FONTDIR="$HOME/Library/Fonts"
mkdir -p "${FONTDIR}"
declare -A fontmap=( ["Regular"]="Regular" ["Bold"]="Bold" ["Italic"]="Italic" ["Bold Italic"]="Bold%20Italic" )
for font in "Regular" "Bold" "Italic" "Bold Italic"; do
  filepath="${FONTDIR}/MesloLGS NF ${font}.ttf"
  if [[ -f "$filepath" ]] && [[ $(stat -f%z "$filepath" 2>/dev/null || echo 0) -gt 1000000 ]]; then
    echo "Already installed: MesloLGS NF ${font}.ttf"
  else
    curl -fsSL -o "$filepath" "https://github.com/romkatv/powerlevel10k-media/raw/master/MesloLGS%20NF%20${fontmap[$font]}.ttf"
  fi
done
```

After downloading, **verify all 4 files exist and have valid size** (>1MB each):

```bash
FONTDIR="$HOME/Library/Fonts"
MISSING=0
for font in "Regular" "Bold" "Italic" "Bold Italic"; do
  filepath="${FONTDIR}/MesloLGS NF ${font}.ttf"
  if [[ -f "$filepath" ]]; then
    size=$(stat -f%z "$filepath" 2>/dev/null || echo 0)
    if [[ $size -gt 1000000 ]]; then
      echo "OK: MesloLGS NF ${font}.ttf (${size} bytes)"
    else
      echo "INVALID (too small): MesloLGS NF ${font}.ttf (${size} bytes)"
      MISSING=$((MISSING+1))
    fi
  else
    echo "MISSING: MesloLGS NF ${font}.ttf"
    MISSING=$((MISSING+1))
  fi
done
echo "Missing fonts: ${MISSING}"
```

If any fonts are missing or invalid, report the specific failures to the user and do NOT proceed — ask them to retry or download manually.

macOS picks up fonts from `~/Library/Fonts` automatically - no cache refresh needed.

### 8. Configure ~/.zshrc

Read the existing `~/.zshrc` file using the Read tool.

**Set the theme:** Use Edit tool to change the `ZSH_THEME` line:

- old_string: `ZSH_THEME="robbyrussell"` (or whatever the current theme is)
- new_string: `ZSH_THEME="powerlevel10k/powerlevel10k"`

**Set the plugins:** Use Edit tool to update the `plugins=(...)` line:

- old_string: `plugins=(git)` (or whatever the current plugins list is)
- new_string: `plugins=(git zsh-autosuggestions zsh-syntax-highlighting zsh-shift-select)`

If the plugins line already contains some of these plugins, merge them - do not duplicate entries.

### 9. Configure Keybindings

Read `~/.zshrc` using Read tool. Check if a keybindings block already exists by searching for `_select_all`. If found, skip this step.

If not found, use Edit tool to append the following block **before** the p10k sourcing line (`[[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh`) if it exists, or at the end of the file otherwise.

**All environments** — append this base block:

```zsh
# Windows-like keybindings
_select_all() {
  zle beginning-of-line
  zle set-mark-command
  zle end-of-line
}
zle -N _select_all
bindkey '^A' _select_all
bindkey '^Z' undo
bindkey '^Y' redo
```

Then append clipboard bindings depending on the environment detected in Step 1:

**If WSL** — append:

```zsh
_cut_to_clipboard() {
  zle kill-region
  echo -n "$CUTBUFFER" | clip.exe 2>/dev/null
}
zle -N _cut_to_clipboard

_paste_from_clipboard() {
  local paste
  paste=$(powershell.exe Get-Clipboard 2>/dev/null | tr -d '\r')
  LBUFFER+=$paste
}
zle -N _paste_from_clipboard

bindkey '^X' _cut_to_clipboard
bindkey '^V' _paste_from_clipboard

_backspace_or_delete_region() {
  if (( REGION_ACTIVE )); then
    zle kill-region
    echo -n "$CUTBUFFER" | clip.exe 2>/dev/null
  else
    zle backward-delete-char
  fi
}
zle -N _backspace_or_delete_region
bindkey '^?' _backspace_or_delete_region

_delete_or_delete_region() {
  if (( REGION_ACTIVE )); then
    zle kill-region
    echo -n "$CUTBUFFER" | clip.exe 2>/dev/null
  else
    zle delete-char
  fi
}
zle -N _delete_or_delete_region
bindkey '^[[3~' _delete_or_delete_region
```

**If macOS** — append:

```zsh
_cut_to_clipboard() {
  zle kill-region
  echo -n "$CUTBUFFER" | pbcopy 2>/dev/null
}
zle -N _cut_to_clipboard

_paste_from_clipboard() {
  local paste
  paste=$(pbpaste 2>/dev/null)
  LBUFFER+=$paste
}
zle -N _paste_from_clipboard

bindkey '^X' _cut_to_clipboard
bindkey '^V' _paste_from_clipboard

_backspace_or_delete_region() {
  if (( REGION_ACTIVE )); then
    zle kill-region
    echo -n "$CUTBUFFER" | pbcopy 2>/dev/null
  else
    zle backward-delete-char
  fi
}
zle -N _backspace_or_delete_region
bindkey '^?' _backspace_or_delete_region

_delete_or_delete_region() {
  if (( REGION_ACTIVE )); then
    zle kill-region
    echo -n "$CUTBUFFER" | pbcopy 2>/dev/null
  else
    zle delete-char
  fi
}
zle -N _delete_or_delete_region
bindkey '^[[3~' _delete_or_delete_region
```

**If native Linux** — skip clipboard bindings but still add backspace/delete region support:

```zsh
_backspace_or_delete_region() {
  if (( REGION_ACTIVE )); then
    zle kill-region
  else
    zle backward-delete-char
  fi
}
zle -N _backspace_or_delete_region
bindkey '^?' _backspace_or_delete_region

_delete_or_delete_region() {
  if (( REGION_ACTIVE )); then
    zle kill-region
  else
    zle delete-char
  fi
}
zle -N _delete_or_delete_region
bindkey '^[[3~' _delete_or_delete_region
```

### 10. Configure WSL Audio (WSL only)

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

**If packages are missing (`pactl: MISSING` or `libasound2-plugins: MISSING`):**

**IMPORTANT: Claude cannot run sudo commands.** Output the following and wait for confirmation:

```
Please run this command manually, then confirm when done:

sudo apt-get install -y pulseaudio-utils libasound2-plugins
```

Use AskUserQuestion to ask "Have you finished installing the audio packages?" with options "Yes, done" and "Skip audio setup".

If user skips, skip the rest of this step.

**If WSLg PulseAudio is not running:**

Inform the user: "WSLg PulseAudio is not running — audio may not work until you restart WSL. Continue anyway and audio will work after restart."

**Configure `~/.asoundrc`:**

If `~/.asoundrc` does not exist, or does not contain `pcm.default pulse`, create/overwrite it using Write tool:

```
pcm.default pulse
ctl.default pulse
```

**Add `PULSE_SERVER` to `.zshrc`:**

If `PULSE_SERVER` is not already in `~/.zshrc`, use Edit tool to add it after the `export PATH=` line:

- old_string: the existing `export PATH=...` line
- new_string: same line + newline + `export PULSE_SERVER=unix:/mnt/wslg/runtime-dir/pulse/native`

Report what was configured. Inform the user that audio input (microphone) is now routed through WSLg — tools like Claude Code `/voice` should work after reopening the terminal.

### 11. Port Bash Environment to Zsh

Oh My Zsh creates a fresh `~/.zshrc` from a template, which means environment setup from `~/.bashrc` and `~/.profile` is lost. Common breakage: NVM (node/npm/pnpm missing), custom PATH entries, SSH agent auto-start, other exports.

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

Things to **exclude** (bash-specific, already handled by Oh My Zsh, or not portable):

- `shopt` commands
- bash-completion sourcing
- `PS1`/`PROMPT_COMMAND` (p10k handles this)
- `HISTCONTROL`/`HISTSIZE`/`HISTFILESIZE` (Oh My Zsh sets these)
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

### 12. VS Code Terminal Font Configuration

Set `"terminal.integrated.fontFamily": "MesloLGS NF"` in all VS Code settings files — both the default and any profile-specific ones. VS Code profiles store their own `settings.json` that overrides the default.

First, locate the VS Code config directory and find all `settings.json` files:

```bash
if [[ "$(uname)" == "Darwin" ]]; then
  VSCODE_DIR="$HOME/Library/Application Support/Code"
else
  VSCODE_DIR="$HOME/.config/Code"
fi
# Default settings
echo "${VSCODE_DIR}/User/settings.json"
# Profile-specific settings (override default)
find "${VSCODE_DIR}/User/profiles" -name "settings.json" 2>/dev/null
```

For **each** `settings.json` found, read it using the Read tool, then:

- If `"terminal.integrated.fontFamily"` already exists, use Edit tool to update its value to `"MesloLGS NF"`
- If it does not exist, use Edit tool to add `"terminal.integrated.fontFamily": "MesloLGS NF"` inside the top-level JSON object (after the opening `{`)
- If the file does not exist, create it with Write tool containing: `{ "terminal.integrated.fontFamily": "MesloLGS NF" }`

Report which files were updated and which already had the correct value.

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

- `POWERLEVEL9K_RIGHT_PROMPT_FIRST_SEGMENT_START_SYMBOL='\uE0BA'` → `POWERLEVEL9K_RIGHT_PROMPT_FIRST_SEGMENT_START_SYMBOL=''`
- `POWERLEVEL9K_RIGHT_PROMPT_LAST_SEGMENT_END_SYMBOL='\uE0BC'` → `POWERLEVEL9K_RIGHT_PROMPT_LAST_SEGMENT_END_SYMBOL=''`

Note: the exact unicode values may differ depending on the style chosen in the p10k wizard — search for `RIGHT_PROMPT_FIRST_SEGMENT_START_SYMBOL` and `RIGHT_PROMPT_LAST_SEGMENT_END_SYMBOL` by name, not by value.

Run to apply immediately:

```bash
source ~/.p10k.zsh
```

### 14. Apply Configuration

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
- **Use `--unattended` flag** for Oh My Zsh installer to prevent interactive prompts
- **On macOS**, Zsh is pre-installed - skip Zsh installation, fonts go to `~/Library/Fonts`
- **On macOS**, `brew` is used instead of `apt` if any packages are needed

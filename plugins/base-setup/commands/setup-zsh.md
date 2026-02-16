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
- new_string: `plugins=(git zsh-autosuggestions zsh-syntax-highlighting)`

If the plugins line already contains some of these plugins, merge them - do not duplicate entries.

### 9. Port Bash Environment to Zsh

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

### 10. VS Code Terminal Font Configuration

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

### 11. Apply Configuration

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

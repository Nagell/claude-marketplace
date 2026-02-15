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
for font in "Regular" "Bold" "Italic" "Bold Italic"; do
  filepath="${FONTDIR}/MesloLGS NF ${font}.ttf"
  if [[ -f "$filepath" ]]; then
    echo "Already installed: MesloLGS NF ${font}.ttf"
  else
    curl -fsSL -o "$filepath" "https://github.com/romkatv/powerlevel10k-media/raw/master/MesloLGS%20NF%20${font// /%20}.ttf"
  fi
done
```

After downloading, inform the user:

```
Fonts downloaded to Windows Fonts directory. You may need to register them:
1. Open Windows Settings > Personalization > Fonts
2. Drag and drop the .ttf files from: C:\Users\<USERNAME>\AppData\Local\Microsoft\Windows\Fonts
   OR the fonts may already be available if Windows auto-registered them.
```

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
for font in "Regular" "Bold" "Italic" "Bold Italic"; do
  filepath="${FONTDIR}/MesloLGS NF ${font}.ttf"
  if [[ -f "$filepath" ]]; then
    echo "Already installed: MesloLGS NF ${font}.ttf"
  else
    curl -fsSL -o "$filepath" "https://github.com/romkatv/powerlevel10k-media/raw/master/MesloLGS%20NF%20${font// /%20}.ttf"
  fi
done
fc-cache -fv
```

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
for font in "Regular" "Bold" "Italic" "Bold Italic"; do
  filepath="${FONTDIR}/MesloLGS NF ${font}.ttf"
  if [[ -f "$filepath" ]]; then
    echo "Already installed: MesloLGS NF ${font}.ttf"
  else
    curl -fsSL -o "$filepath" "https://github.com/romkatv/powerlevel10k-media/raw/master/MesloLGS%20NF%20${font// /%20}.ttf"
  fi
done
```

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

### 9. VS Code Terminal Font Configuration

Inform the user they need to set the terminal font in VS Code settings. Output this message:

```
To display Powerlevel10k icons correctly in VS Code terminal, add this to your VS Code settings.json:

"terminal.integrated.fontFamily": "MesloLGS NF"

You can do this via:
1. Open VS Code Settings (Ctrl+, on Linux/Windows, Cmd+, on macOS)
2. Search for "terminal font"
3. Set "Terminal > Integrated: Font Family" to: MesloLGS NF
```

### 10. Apply Configuration

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

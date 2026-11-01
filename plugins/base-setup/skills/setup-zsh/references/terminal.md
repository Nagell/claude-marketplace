# Terminal reference

Step 19 sends you here once `WORK_DIR` is known: **Ghostty** on macOS, **Windows Terminal
profile for herdr** on WSL. Native Linux skips Step 19 entirely.

## Ghostty (macOS)

Ghostty is the recommended terminal on macOS: it restores tabs, splits and their folders after Cmd+Q, and its keybinds can hand Shift/Ctrl+arrows to zsh. Check and install:

```bash
test -d /Applications/Ghostty.app && echo "Ghostty: INSTALLED" || echo "Ghostty: MISSING"
```

If MISSING, use AskUserQuestion: "Install Ghostty as your terminal?" with options "Yes, install Ghostty (Recommended)" and "No, keep my terminal". If yes:

```bash
brew install --cask ghostty
```

### Config

The config lives at `~/Library/Application Support/com.mitchellh.ghostty/config.ghostty`. Read it with the Read tool if it exists and back it up first (`cp "$F" "$F.bak-$(date +%Y%m%d-%H%M%S)"`); add only the lines whose key/keybind is not already set, and never overwrite the file with a fresh one. Create the directory and file if missing.

```ghostty
window-save-state = always

# Leave Shift+arrows and Shift+Home/End to zsh (zsh-shift-select) instead of adjusting the terminal selection.
keybind = shift+arrow_left=unbind
keybind = shift+arrow_right=unbind
keybind = shift+home=unbind
keybind = shift+end=unbind

# Cmd+Left/Right send Home/End instead of Ctrl+A/Ctrl+E (Ctrl+A is select-all in zsh, Step 7);
# Shift+Cmd+Left/Right select to the line start/end.
keybind = super+arrow_left=csi:H
keybind = super+arrow_right=csi:F
keybind = super+shift+arrow_left=csi:1;2H
keybind = super+shift+arrow_right=csi:1;2F

# Ctrl+Left/Right jump by word in zsh and in Claude's prompt (both read Esc b / Esc f as word moves).
keybind = ctrl+arrow_left=esc:b
keybind = ctrl+arrow_right=esc:f

# Option+V reaches Claude as Alt+V (its image/text paste) instead of typing a character.
keybind = alt+v=esc:v

# A free-spinning mouse wheel (Logitech MX) sends bursts of notches; 3 lines each jumps whole pages.
mouse-scroll-multiplier = precision:1,discrete:1
```

The scroll setting only covers Ghostty's own scrollback: inside herdr, herdr scrolls (Step 20).

`window-save-state = always` restores windows, tabs, splits and their working directories after Cmd+Q; running programs are not restored (the herdr auto-start in Step 20 covers herdr).

Don't bind `ctrl+v` in Ghostty: zsh (`_paste_from_clipboard`, Step 7) and nvim (the LazyVim keymaps) handle Ctrl+V themselves, and Claude Code needs to receive it (below). Only `alt+v` is remapped; changing `macos-option-as-alt` instead would break the Option characters of non-US layouts.

### Claude Code paste keys

**If Claude Code is installed** (`command -v claude`): make Ctrl+V and Option+V paste in its prompt. Both keys run Claude's image paste, which attaches an image from the clipboard and falls back to pasting text when there is none. Read `~/.claude/keybindings.json` first and merge into it; only create it if it does not exist:

```json
{
  "$schema": "https://www.schemastore.org/claude-code-keybindings.json",
  "$docs": "https://code.claude.com/docs/en/keybindings",
  "bindings": [
    {
      "context": "Chat",
      "bindings": {
        "ctrl+v": "chat:imagePaste",
        "meta+v": "chat:imagePaste"
      }
    }
  ]
}
```

Claude Code reads the file at start, so restart it afterwards. A macOS screenshot only reaches the clipboard if screenshots are set to copy there (`/base-setup:setup-macos`) or taken with Cmd+Ctrl+Shift+4.

### Optional settings

Optional, ask before adding (AskUserQuestion, multiSelect) — these are taste, not needed for anything else:

```ghostty
# New windows start in the work directory instead of the home folder.
working-directory = ~/<WORK_DIR>
tab-inherit-working-directory = false

# Translucent, blurred background (the LazyVim theme from Step 16 shows it through).
background-opacity = 0.8
background-blur = true
```

Ghostty picks up config changes after Cmd+Shift+, (reload config) or a restart.

## Windows Terminal profile for herdr (WSL)

Only run this if the user said yes to the profile question in Step 19.

Locate `settings.json` with the same loop as Step 12, read it with the Read tool, back it up (`cp`, `.bak-<timestamp>` suffix), and if no profile named `herdr` exists, add one to `profiles.list` with the Edit tool. Generate the GUID with `cat /proc/sys/kernel/random/uuid`.

```json
{
    "guid": "{<new GUID>}",
    "name": "herdr",
    "commandline": "wsl.exe -d <distro> --cd <linux home>/<WORK_DIR> -- zsh -lic herdr"
},
```

`<distro>` is `$WSL_DISTRO_NAME` (e.g. `Ubuntu`) and `<linux home>` the absolute `$HOME` inside WSL (e.g. `/home/alice`). `zsh -lic` runs a login, interactive shell so herdr sees the same `PATH` as a normal tab. Copy `font`/`colorScheme` from the distro's existing profile if it sets them, so the herdr tab looks the same.

Then ask (AskUserQuestion): "Make herdr the default Windows Terminal profile?" — "Yes" / "No". If yes, set the top-level `"defaultProfile"` to the new GUID. Windows Terminal reloads `settings.json` on save.

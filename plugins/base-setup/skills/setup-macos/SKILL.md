---
name: setup-macos
description: Configure macOS for someone coming from Windows - Finder (hidden files, path bar, folders first, sort by kind), screenshots to the clipboard, Spaces hotkeys moved off Ctrl+arrows, and Karabiner-Elements rules for Windows-style Ctrl shortcuts outside terminals
disable-model-invocation: true
---

# Setup macOS

Operating-system settings for a Mac: Finder, screenshots, the Spaces hotkeys, and Karabiner-Elements. Run
this **before** `/base-setup:setup-zsh` — the terminal, shell and editor setup (Ghostty, zsh
keybindings, herdr, LazyVim) lives there and expects the Spaces hotkeys from Step 5 to be done.

Every step is idempotent and can be re-run. Each one backs up the preferences or file it changes
to `~/.local/share/setup-macos/backup-<timestamp>/` first; restore a domain with
`defaults import <domain> <backup>.plist`.

## Implementation Steps

### 1. Check the environment

```bash
[[ "$(uname)" == "Darwin" ]] && sw_vers -productVersion || echo "NOT MACOS"
```

If it prints `NOT MACOS`, stop: this skill is for macOS only.

Create the backup folder for this run:

```bash
BK="$HOME/.local/share/setup-macos/backup-$(date +%Y%m%d-%H%M%S)"; mkdir -p "$BK"; echo "$BK"
```

Shell variables do not survive between Bash tool calls: start each later command block with
`BK=<the printed path>` and `WORK_DIR=<the folder from Step 2>` where it uses them.

### 2. Work directory

Finder's new windows and Karabiner's Option+E open a projects folder. Look for an existing one:

```bash
for d in ~/Development ~/Projects ~/projects ~/Code ~/code ~/dev ~/src ~/repos ~/workspace; do [[ -d $d ]] && echo "$d"; done
```

Use AskUserQuestion: "Which folder holds your projects?" with the folders found as options (first
one marked "(Recommended)"). If none were found, offer `~/Development` (Recommended) and let the
user type another. Store it as `WORK_DIR`, relative to `$HOME` (e.g. `Development`), and create it
with `mkdir -p "$HOME/$WORK_DIR"` if needed.

### 3. Finder

Use AskUserQuestion (multiSelect): "Which Finder settings should I apply?" — all recommended:

- "Show hidden files" — `AppleShowAllFiles`
- "Path bar and full path in the title" — `ShowPathbar`, `_FXShowPosixPathInTitle`
- "New windows open the work directory" — `NewWindowTarget`, `NewWindowTargetPath`
- "Folders first, sorted by kind" — `_FXSortFoldersFirst`, `_FXSortFoldersFirstOnDesktop`, and
  `kind` as the sort column of every view in `StandardViewSettings`

Back up, then run only the lines for the picked options:

```bash
defaults export com.apple.finder - > "$BK/com.apple.finder.plist"

defaults write com.apple.finder AppleShowAllFiles -bool true
defaults write com.apple.finder ShowPathbar -bool true
defaults write com.apple.finder _FXShowPosixPathInTitle -bool true
defaults write com.apple.finder NewWindowTarget -string PfLo
defaults write com.apple.finder NewWindowTargetPath -string "file://$HOME/$WORK_DIR/"
defaults write com.apple.finder _FXSortFoldersFirst -bool true
defaults write com.apple.finder _FXSortFoldersFirstOnDesktop -bool true
```

The sort column lives in nested dictionaries that `defaults write` cannot reach. Edit an exported
copy with PlistBuddy and import it back — editing `~/Library/Preferences/com.apple.finder.plist`
directly does not stick, because `cfprefsd` holds its own copy and writes it back over the file:

```bash
P="$(mktemp -d)/finder.plist"
defaults export com.apple.finder - > "$P"
pb() { /usr/libexec/PlistBuddy -c "$1" "$P" >/dev/null 2>&1; }
setkind() {  # $1 = view settings dict, $2 = key
  pb "Add :StandardViewSettings dict" || true
  pb "Add :StandardViewSettings:$1 dict" || true
  pb "Set :StandardViewSettings:$1:$2 kind" || pb "Add :StandardViewSettings:$1:$2 string kind"
}
setkind ExtendedListViewSettingsV2 sortColumn
setkind ListViewSettings sortColumn
setkind IconViewSettings arrangeBy
setkind GalleryViewSettings arrangeBy
defaults import com.apple.finder "$P"
```

Then restart Finder (also when only the `defaults write` lines ran):

```bash
killall Finder
```

Export to stdout (`-`) and redirect, as above: inside Claude Code's sandbox,
`defaults export <domain> <file>` writes an incomplete file.

Verify:

```bash
defaults read com.apple.finder | grep -E 'AppleShowAllFiles|ShowPathbar|_FXShowPosixPathInTitle|NewWindowTarget|_FXSortFoldersFirst|sortColumn|arrangeBy'
```

Then tell the user:

```
Finder is set up.
  Folders that already have their own view settings (a .DS_Store) keep them: open the folder,
  Cmd+J, set "Sort By: Kind", then "Use as Defaults".
  Option+Cmd+C   copy the selected item's path
  Cmd+Shift+G    Go to Folder (type or paste a path)
  Cmd+Shift+.    toggle hidden files
```

### 4. Screenshots to the clipboard

macOS saves screenshots (Cmd+Shift+3/4/5) as files on the Desktop, so they never reach the
clipboard; pasting one into a chat or into Claude Code means opening the file and copying it first.
Use AskUserQuestion: "Copy screenshots straight to the clipboard, like Windows' Win+Shift+S?" —
"Yes (Recommended)" / "No, keep saving files". If no, skip this step.

```bash
BK=<backup folder>
defaults export com.apple.screencapture - > "$BK/com.apple.screencapture.plist" 2>/dev/null || true
defaults write com.apple.screencapture target clipboard
killall SystemUIServer
defaults read com.apple.screencapture target
```

Then tell the user:

```
Screenshots now go to the clipboard instead of the Desktop.
  Keep one as a file: in Preview, Cmd+N (new from clipboard), then save.
  Switch back: Cmd+Shift+5 -> Options -> Save to: Desktop.
```

### 5. Spaces hotkeys

macOS puts "Move left/right a space" on Ctrl+←/→, plus hidden Ctrl+Shift+←/→ variants, so those
keys never reach apps or the terminal — word jumps and word selection don't work. This step moves
the Space switch to Ctrl+Option+←/→ and disables the Ctrl+Shift variants.

Use AskUserQuestion: "Move 'switch Space' from Ctrl+←/→ to Ctrl+Option+←/→, so Ctrl+arrows jump by
word like on Windows?" — "Yes (Recommended)" / "No". If no, skip to Step 6.

The hotkeys live in `com.apple.symbolichotkeys`, keyed by number: 79/81 move left/right a space,
80/82 are the Ctrl+Shift variants. `parameters` is `[65535, key code, modifier flags]` with arrow
key codes 123 (←) and 124 (→); the flags are Ctrl 0x40000, Option 0x80000, Shift 0x20000, plus
0x800000 (fn), which macOS sets on every arrow key. Edit an exported copy with Python's `plistlib`
and import it back:

```bash
defaults export com.apple.symbolichotkeys - > "$BK/com.apple.symbolichotkeys.plist"
P="$(mktemp -d)/hotkeys.plist"
defaults export com.apple.symbolichotkeys - > "$P"
python3 - "$P" <<'EOF'
import plistlib, sys
path = sys.argv[1]
with open(path, "rb") as f:
    prefs = plistlib.load(f)
hotkeys = prefs.setdefault("AppleSymbolicHotKeys", {})
CTRL_OPTION_FN, CTRL_SHIFT_FN = 0x40000 | 0x80000 | 0x800000, 0x40000 | 0x20000 | 0x800000
for key, arrow, enabled, mods in (
    ("79", 123, True, CTRL_OPTION_FN),   # Move left a space
    ("81", 124, True, CTRL_OPTION_FN),   # Move right a space
    ("80", 123, False, CTRL_SHIFT_FN),   # hidden Ctrl+Shift+Left variant
    ("82", 124, False, CTRL_SHIFT_FN),   # hidden Ctrl+Shift+Right variant
):
    hotkeys[key] = {"enabled": enabled,
                    "value": {"type": "standard", "parameters": [65535, arrow, mods]}}
with open(path, "wb") as f:
    plistlib.dump(prefs, f)
EOF
defaults import com.apple.symbolichotkeys "$P"
/System/Library/PrivateFrameworks/SystemAdministration.framework/Resources/activateSettings -u
```

`activateSettings -u` applies the change without logging out.

Do not use `defaults write com.apple.symbolichotkeys AppleSymbolicHotKeys -dict-add 80 '{enabled = 0; …}'`:
it stores `enabled` as the string `"0"`, which macOS reads as still enabled. `plistlib` writes
real booleans and integers.

Verify:

```bash
defaults export com.apple.symbolichotkeys - | python3 -c '
import plistlib, sys
hk = plistlib.loads(sys.stdin.buffer.read())["AppleSymbolicHotKeys"]
for i in ("79", "80", "81", "82"): print(i, hk[i]["enabled"], hk[i]["value"]["parameters"])'
```

Expect `79 True [65535, 123, 9175040]`, `80 False [65535, 123, 8781824]`,
`81 True [65535, 124, 9175040]`, `82 False [65535, 124, 8781824]`. System Settings → Keyboard →
Keyboard Shortcuts → Mission Control shows the new keys.

### 6. Karabiner-Elements: Windows-style shortcuts

[Karabiner-Elements](https://karabiner-elements.pqrs.org) remaps keys system-wide. The rules from
this skill make Windows habits work in every app except terminals and VS Code, which keep Ctrl
for themselves (Ctrl+C interrupts a program; VS Code has its own Ctrl keymap).

Use AskUserQuestion: "Set up Karabiner-Elements for Windows-style shortcuts
(Ctrl+C/V/X/Z/Y/A/B/I/U, Ctrl+arrows, Option+F4, Option+E)?" — "Yes (Recommended)" / "No". If no,
skip to Step 7.

#### Install

```bash
test -d "/Applications/Karabiner-Elements.app" && echo "INSTALLED" || echo "MISSING"
```

If MISSING: **Claude cannot enter the sudo password the installer asks for.** Output this and wait:

```
Please run this in a terminal, then confirm when done:

brew install --cask karabiner-elements

Then open Karabiner-Elements and approve what it asks for:
  - System Settings → General → Login Items & Extensions → Driver Extensions: turn on
    Karabiner's driver extension
  - System Settings → Privacy & Security → Input Monitoring: allow the Karabiner entries
Karabiner does not need to be in "Open at Login" (its services are launchd agents),
but keep it on under "Allow in the Background".
```

Use AskUserQuestion: "Is Karabiner-Elements installed and approved?" — "Yes, done" / "Skip
Karabiner".

#### Keyboards that also report as a mouse

Karabiner leaves devices that report as both keyboard and pointing device unmodified by default
— for example a Logitech MX Keys over Bluetooth. List them:

```bash
python3 <this-skill-dir>/assets/karabiner/windows-shortcuts.py --list-devices
```

Each line is `VENDOR_ID:PRODUCT_ID`, name, transport. If any are listed, use AskUserQuestion
(multiSelect): "These keyboards also report as a pointing device, so Karabiner ignores them by
default. Apply the shortcuts to which of them?" with one option per device. Each one picked
becomes a `--device VENDOR_ID:PRODUCT_ID` argument below.

#### Merge the rules

`windows-shortcuts.py` (Python 3, standard library only) merges the rules into the selected
profile of `~/.config/karabiner/karabiner.json`. It backs the file up next to itself
(`karabiner.json.bak-<timestamp>`), creates a minimal file if there is none, keeps every other
rule and setting, and replaces its own rules (matched by description) instead of adding them a
second time. Preview, then write:

```bash
S=<this-skill-dir>/assets/karabiner/windows-shortcuts.py
python3 "$S" --work-dir "$WORK_DIR" [--device VID:PID ...] --dry-run
python3 "$S" --work-dir "$WORK_DIR" [--device VID:PID ...]
```

Replace `[--device VID:PID ...]` with one `--device` per keyboard picked above, or drop it.

The rules:

| Keys | Becomes | Where |
| --- | --- | --- |
| Option+F4 | Cmd+W (close window) | all apps |
| Option+E | `open "$HOME/<WORK_DIR>"` in Finder | all apps |
| Ctrl(+Shift)+←/→ | Option(+Shift)+←/→ (word jump / select) | not in terminals, VS Code |
| Ctrl+Backspace / Ctrl+Delete | Option+Backspace / Option+Delete (delete word) | not in terminals, VS Code |
| Ctrl+A | Cmd+A | not in terminals, VS Code |
| Ctrl+X / C / V | Cmd+X / C / V | not in terminals, VS Code |
| Ctrl+Z / Ctrl+Y | Cmd+Z undo / Cmd+Shift+Z redo | not in terminals, VS Code |
| Ctrl(+Shift)+R | Cmd(+Shift)+R (reload / hard reload) | not in terminals, VS Code |
| Ctrl+B / I / U | Cmd+B / I / U (bold, italic, underline) | not in terminals, VS Code |
| Ctrl+Shift+I | Cmd+Option+I (developer tools) | Chrome, Chrome for Testing, Firefox, Safari |
| Cmd+Q | `@` (Option+L on German, Shift+2 on other layouts) instead of quitting the app | all apps |

Cmd+Q is where Windows' AltGr+Q (`@` on German keyboards) lands on a Mac, so it quits apps by
accident; quit from the app menu or the Dock instead. Ask before applying it (AskUserQuestion:
"Make Cmd+Q type @ instead of quitting apps?" — "Yes (Recommended)" / "No") and drop the rule from
`build_rules()` if the user says no. Layouts whose `@` is elsewhere (e.g. Swiss German, Option+G)
go into `AT_SIGN_KEYS` at the top of the script.

The excluded apps are the `EXCLUDED_APPS` bundle IDs at the top of the script: Ghostty
(`com.mitchellh.ghostty`), Terminal (`com.apple.Terminal`) and VS Code (`com.microsoft.VSCode`).
Add others there and re-run; find an app's ID with
`mdls -name kMDItemCFBundleIdentifier -raw /Applications/<App>.app`.

> **Keyboard layouts.** Karabiner matches physical key positions in US terms, whatever layout is
> active. On QWERTZ layouts Z and Y swap places, so the Z/Y rules check the input source: they use
> `input_source_if` / `input_source_unless` on the layouts in `QWERTZ_LAYOUTS` at the top of the
> script (`^com\.apple\.keylayout\.German$` by default). Verified with German, U.S. and Polish Pro
> enabled. Any other QWERTZ layout the user has enabled (Swiss German, Austrian, Czech, …) must be
> added to `QWERTZ_LAYOUTS`, or Ctrl+Z and Ctrl+Y are swapped while it is active — check with
> `defaults read com.apple.HIToolbox AppleEnabledInputSources`. Removing a layout is safe: the
> QWERTY rules take over. X, C, V, A and E sit in the same place on all of these layouts.

#### Verify

Karabiner reloads `karabiner.json` on its own when the file changes. Check its log:

```bash
grep -E 'Load .*karabiner\.json|core_configuration is updated|monitor is started \(grabbed\)' /var/log/karabiner/core_service.log | tail -8
```

Expect a fresh `Load …/karabiner.json...` followed by `core_configuration is updated.`. For each
keyboard added with `--device`, expect `<name> (device_id:…) hid device events monitor is started
(grabbed).` — `(observed)` means Karabiner still leaves it alone.

Then ask the user to try Ctrl+C / Ctrl+V in a text field (Notes, Safari) and Ctrl+C in Ghostty or
Terminal, where it must still interrupt a running command.

### 7. Done

Report what was applied and where the backups are (`$BK`, plus `karabiner.json.bak-*`). Then tell
the user:

```
Next: run /base-setup:setup-zsh for the terminal (Ghostty), zsh keybindings, herdr and LazyVim.
```

## Important Notes

- **NEVER run sudo commands directly** — print them for the user to run.
- **Back up before every change** — `defaults export <domain> - > "$BK/<domain>.plist"`; the
  Karabiner script makes its own backup.
- **Edit nested preferences through `defaults export` → edit → `defaults import`.** Direct edits to
  the plist files are overwritten by `cfprefsd`.

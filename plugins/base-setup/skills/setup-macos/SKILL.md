---
name: setup-macos
description: Configure macOS for someone coming from Windows - Finder (hidden files, path bar, folders first, sort by kind), screenshots to the clipboard, Spaces hotkeys moved off Ctrl+arrows, Karabiner-Elements rules for Windows-style Ctrl shortcuts outside terminals, fast key repeat, and numbered workspaces per screen - FlashSpace workspaces on Caps Lock hotkeys, a SketchyBar top bar, Rectangle window snapping with gaps, the native menu bar auto-hidden
disable-model-invocation: true
---

# Setup macOS

Operating-system settings for a Mac: Finder, screenshots, the Spaces hotkeys, Karabiner-Elements,
key repeat, and a workspace setup (FlashSpace, SketchyBar, Rectangle). Run this **before** `/base-setup:setup-zsh` — the terminal, shell and editor setup (Ghostty, zsh
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
| Ctrl+T / Ctrl+Shift+T | Cmd+T new tab / Cmd+Shift+T reopen closed tab | Chrome, Chrome for Testing, Firefox, Safari |
| Ctrl+Shift+I | Cmd+Option+I (developer tools) | Chrome, Chrome for Testing, Firefox, Safari |
| Ctrl+Shift+C / Ctrl+K | Cmd+Shift+C code / Cmd+Shift+U link | Slack |
| Ctrl+Shift+Esc | Cmd+Option+Esc (Force Quit Applications) | all apps |
| Option+Shift+S | Cmd+Shift+4 (area screenshot) | all apps |
| Cmd+Q | `@` (Option+L on German, Option+Q on German – Standard, Shift+2 on other layouts) instead of quitting the app | all apps |

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
> script: German (`com.apple.keylayout.German`) and German – Standard
> (`com.apple.keylayout.German-DIN-2137`) by default. The two look alike in System Settings and
> are easy to swap by mistake; both are QWERTZ, but `@` is Option+L on German and Option+Q on
> German – Standard. Verified with German, U.S. and Polish Pro enabled. Any other QWERTZ layout
> the user has enabled (Swiss German, Austrian, Czech, …) must be added to `QWERTZ_LAYOUTS`, or
> Ctrl+Z and Ctrl+Y are swapped while it is active — check with
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

### 7. Key repeat

macOS's default key repeat is much slower than Windows', so holding Backspace or an arrow key
crawls. Use AskUserQuestion: "Make key repeat as fast as System Settings allows?" — "Yes
(Recommended)" / "No, keep the current speed". If no, skip this step.

```bash
BK=<backup folder>
defaults export NSGlobalDomain - > "$BK/NSGlobalDomain.plist"
defaults write -g KeyRepeat -int 2          # 30 ms between repeats: the fastest slider position
defaults write -g InitialKeyRepeat -int 15  # 225 ms before repeating starts: the shortest delay
defaults read -g KeyRepeat; defaults read -g InitialKeyRepeat
```

Both take effect after logging out and back in. Tell the user that, and that System Settings →
Keyboard → "Key repeat rate" / "Delay until repeat" moves them back.

### 8. Workspaces: what the next steps build

Steps 9–13 give the Mac numbered workspaces per screen, like virtual desktops on Windows, with a
bar on top. Four tools, each with one job:

| Tool | Job | Keys |
| --- | --- | --- |
| [FlashSpace](https://github.com/wojciech-kulik/FlashSpace) | Workspaces: which apps belong to which number, which screen each number lives on | Caps+1…9 switch, Caps+Shift+1…9 assign the focused app |
| [Rectangle](https://rectangleapp.com) | Window size and position inside a screen, with gaps | Option or Caps+←/→ halves, Option or Caps+↑ maximize, Option+↓ minimize, or drag to an edge |
| [SketchyBar](https://github.com/FelixKratz/SketchyBar) | The bar: workspace numbers with app icons, RAM, volume, battery, clock | Click a number to switch |
| Karabiner-Elements | Caps Lock sends Ctrl+Option+Cmd, the modifier for all of the above; Option+arrows (Win+arrows on a PC keyboard) forward to Rectangle | — |

Use AskUserQuestion: "Set up numbered workspaces per screen with a top bar (FlashSpace, SketchyBar,
Rectangle)?" — "Yes (Recommended)" / "No". If no, skip to Step 14.

Why not a tiling window manager: AeroSpace treats macOS native tabs (Finder, Ghostty) as separate
windows ([#68](https://github.com/nikitabobko/AeroSpace/issues/68), open since 2023), so switching
tabs breaks the layout. FlashSpace only shows and hides whole apps and never resizes windows, so
tabs cannot break it; Rectangle sizes windows only when asked.

Use `GAP=10` (px between the bar, the screen edges and the windows) in Steps 12 and 13.

### 9. Caps Lock as the workspace key

Caps Lock stops working as Caps Lock. Use AskUserQuestion: "Turn Caps Lock into the key for
workspaces and window snapping (it then sends Ctrl+Option+Cmd)?" — "Yes (Recommended)" / "No, I
need Caps Lock". If no, the hotkeys in Steps 11 and 13 need another modifier: ask which, and
replace `cmd+opt+ctrl` / `1835008` there.

Plain Option types characters on many layouts (Option+5…9 and Option+L are `[ ] | { } @` on
German), and Ctrl+Option is a common dictation push-to-talk key, so neither works as the modifier.

Run the Step 6 script again with `--caps-lock-hyper`, plus `--hide-menu-bar-icon` if the user
wants Karabiner's menu bar icon gone (AskUserQuestion: "Hide Karabiner's menu bar icon? Remapping
keeps working" — "Yes (Recommended)" / "No"). Repeat the `--work-dir` and `--device` arguments
from Step 6, or that step's rules change:

```bash
S=<this-skill-dir>/assets/karabiner/windows-shortcuts.py
python3 "$S" --work-dir "$WORK_DIR" [--device VID:PID ...] --caps-lock-hyper [--hide-menu-bar-icon]
```

The rule presses Cmd before Ctrl and Option, so the chord never passes through bare Ctrl+Option.
The flag also adds Option+←/→/↑ → Caps+←/→/↑ (Rectangle's halves and maximize, Step 13) and
Option+↓ → Cmd+M (minimize), like Win+arrows. Rectangle cannot bind Option+arrows itself: the
Ctrl+←/→ word-jump rule sends them, and Rectangle would take those too.

### 10. Menu bar auto-hide

SketchyBar draws its own bar where the menu bar is, so the native one has to auto-hide. App menus
come back when the pointer touches the top edge.

```bash
BK=<backup folder>
defaults export NSGlobalDomain - > "$BK/NSGlobalDomain-menubar.plist"
defaults write NSGlobalDomain _HIHideMenuBar -bool true
```

Only some screens pick this up. Tell the user to also set System Settings → Menu Bar →
"Automatically hide and show the menu bar" → **Always** (toggle it off and on if it already says
Always), which applies it to every screen.

A screen with a camera notch keeps its top strip reserved even with the menu bar hidden. Step 13
accounts for it.

### 11. FlashSpace

```bash
brew install --cask flashspace
```

FlashSpace reads its settings file at launch and writes it back on quit, so edit it while the app
is not running. Turn on the SketchyBar integration (its default script already sends the event
Step 12 listens for) and hide the menu bar title and icon:

```bash
pkill -x FlashSpace || true
F="$HOME/.config/flashspace/settings.json"
mkdir -p "$(dirname "$F")"
[ -f "$F" ] && cp -p "$F" "$F.bak-$(date +%Y%m%d-%H%M%S)"
python3 - "$F" <<'EOF'
import json, os, sys
path = sys.argv[1]
settings = json.load(open(path)) if os.path.exists(path) else {}
settings.update({"enableIntegrations": True, "showMenuBarIcon": False, "showMenuBarTitle": False})
json.dump(settings, open(path, "w"), indent=2)
EOF
```

FlashSpace always keeps a menu bar item: with both off it falls back to its ⚡ icon. With the menu
bar auto-hidden, it only shows when the menu bar slides in.

Claude's sandbox cannot launch apps. Output this and wait:

```
Please run:  open -a FlashSpace
Allow it under Accessibility when macOS asks, then in its settings (run `flashspace open`):
  General -> Launch at login: on
```

Workspaces need the screens in left-to-right order, with the names FlashSpace uses:

```bash
osascript -l JavaScript -e 'ObjC.import("AppKit"); var s=$.NSScreen.screens, o=[];
for (var i=0;i<s.count;i++){var c=s.objectAtIndex(i); o.push([c.frame.origin.x, ObjC.unwrap(c.localizedName)])}
o.sort(function(a,b){return a[0]-b[0]}); o.map(function(r){return r[1]}).join("\n")'
```

Workspace N lives on screen `(N-1) mod <screen count>`, counting from the left: with three screens,
1/4/7 on the left, 2/5/8 in the middle, 3/6/9 on the right. Numbers stay on their screen, so
switching never moves windows between screens. Tell the user this layout, then create the nine
workspaces with one `--display` per workspace from that list:

```bash
flashspace create-workspace 1 --display "<screen for 1>" --activate-key "cmd+opt+ctrl+1" --assign-key "cmd+opt+ctrl+shift+1"
# ... same for 2-9
flashspace list-workspaces
```

`--activate-key` switches to the workspace; `--assign-key` assigns the focused app to it for good.
Ask which apps go where: show `flashspace list-running-apps --with-bundle-id` and use
AskUserQuestion with a free-text answer such as "Chrome 1, Ghostty 2, Slack 3". Assign each by
bundle ID, so it also works for apps that are not running (Playwright's Chrome for Testing is
`com.google.chrome.for.testing`):

```bash
flashspace assign-app --name <bundle id> --workspace <number> --activate false
for n in 1 2 3 4 5 6 7 8 9; do printf '%s: ' "$n"; flashspace list-apps "$n" | paste -sd, -; done
```

### 12. SketchyBar

The look is [unsecretised/sketchybar-config](https://github.com/unsecretised/sketchybar-config).
It has no license, so this skill doesn't redistribute it: download the pinned commit and apply
this skill's changes on top. `assets/sketchybar/patch.py` switches its workspace buttons from
bobrwm to FlashSpace, adds a RAM item (macOS memory pressure) and sets the bar's offset and side
padding from `GAP`. It moves an existing `~/.config/sketchybar` to `sketchybar.bak-<timestamp>`.

```bash
brew tap FelixKratz/formulae
brew trust --formula felixkratz/formulae/sketchybar
brew install sketchybar
brew install --cask font-jetbrains-mono-nerd-font

SRC="$(mktemp -d)/sketchybar-config"
git clone -q https://github.com/unsecretised/sketchybar-config "$SRC"
git -C "$SRC" checkout -q 07cf294e0572421c4c29e142668c4a50528a342f
python3 <this-skill-dir>/assets/sketchybar/patch.py --source "$SRC" --gap "$GAP" --always-shown <screen count>
brew services start felixkratz/formulae/sketchybar
```

`brew services` also starts it at login. Verify:

```bash
sketchybar --query bar | python3 -c 'import json,sys; print(", ".join(json.load(sys.stdin)["items"]))'
```

Expect `workspace.1` … `workspace.9`, `front_app`, `ram`, `battery`, `volume`, `clock` and the
music items. Workspaces 1…(screen count) always show; the rest appear while they hold running
apps. The RAM figure is memory pressure, not Activity Monitor's "Memory Used", which counts
compressed memory as used and sits near 80% on a healthy Mac.

### 13. Rectangle

macOS's own edge snapping fills the whole screen and covers the bar. Rectangle snaps with gaps.
It reads its settings at launch, so write them before the first start. Its window gap
(`gapSize`) also applies at the screen edges, on top of the screen-edge gaps, so all spacing goes
into `gapSize` and the edges stay 0 — that gives `GAP` at the edges and between windows. The top
edge additionally clears the bar: `GAP` above it plus its 30 px groups (the window gap adds the
`GAP` below). On a notched screen macOS already reserves the notch strip, so subtract it (that
screen's `safeAreaInsets.top`):

```bash
brew install --cask rectangle
osascript -l JavaScript -e 'ObjC.import("AppKit"); var s=$.NSScreen.screens, o=[];
for (var i=0;i<s.count;i++){var c=s.objectAtIndex(i); o.push(ObjC.unwrap(c.localizedName)+"\t"+c.safeAreaInsets.top)}; o.join("\n")'
```

```bash
R=com.knollsoft.Rectangle
TOP=$((GAP + 30))
defaults write $R gapSize -float "$GAP"
defaults write $R screenEdgeGapTop -int "$TOP"
defaults write $R screenEdgeGapTopNotch -int $((TOP - <notch inset, e.g. 32>))  # only with a notched screen
defaults write $R screenEdgeGapBottom -int 0
defaults write $R screenEdgeGapLeft -int 0
defaults write $R screenEdgeGapRight -int 0
# Caps Lock (Ctrl+Option+Cmd = 262144 + 524288 + 1048576) with arrow keys 123, 124, 126.
# Down is Karabiner's minimize, so restore gets no hotkey.
M=1835008
defaults write $R leftHalf -dict-add keyCode -float 123 modifierFlags -float $M
defaults write $R rightHalf -dict-add keyCode -float 124 modifierFlags -float $M
defaults write $R maximize -dict-add keyCode -float 126 modifierFlags -float $M
```

Output this and wait:

```
Please run:  open -a Rectangle
  - Allow it under Accessibility.
  - First-launch dialog: pick "Recommended" shortcuts (the Caps Lock ones above stay).
    Those use Ctrl+Option+key, so they also trigger a dictation app that listens on Ctrl+Option.
  - Rectangle settings -> Launch on login: on
  - System Settings -> Desktop & Dock -> Windows -> "Drag windows to screen edges to tile": off,
    so macOS and Rectangle don't both snap the same drag.
```

After changing any Rectangle setting later, `pkill -x Rectangle` and open it again.

### 14. Done

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

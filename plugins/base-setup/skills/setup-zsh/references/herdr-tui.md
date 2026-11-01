# Herdr TUI setup

Step 20 sends you here when the user picks **Herdr TUI** or **Both**. Run the sections in
order; when this file says "skip to Step 21", return to the skill's Step 21. The Herdr app
has its own guide, `references/herdr-app.md`.

## 1. Install

If Step 20's check printed `herdr TUI: NOT INSTALLED`, install it with herdr's official
installer — this works the same on Linux, macOS, and WSL, and does not need sudo (it
installs to the user's own PATH, e.g. `~/.local/bin`):

```bash
curl -fsSL https://herdr.dev/install.sh | sh
```

Verify:

```bash
herdr --version
```

If the install or verification fails, report the exact error to the user and skip the
rest of this file — do not retry automatically (see the skill's Error Handling).

## 2. Start herdr with Ghostty (macOS only)

Only if MACOS and Ghostty is the terminal. Ghostty restores tabs after Cmd+Q but not the
programs in them; this block reopens herdr in the first Ghostty tab or window only — never
in a second tab, never inside herdr itself. Skip if `~/.zshrc` already contains
`_herdr_client_running`. Otherwise use AskUserQuestion: "Start herdr automatically when
Ghostty opens?" — "Yes (Recommended)" / "No".

If yes, back up `~/.zshrc` and use the Edit tool to put this block at the **very top of
`~/.zshrc`, above the p10k instant-prompt block** (`# Enable Powerlevel10k instant prompt`).
p10k's instant prompt takes over the terminal during startup, and a TUI started after it
freezes the tab. If `command -v herdr` is not `~/.local/bin/herdr`, use that path instead.

```zsh
# Ghostty doesn't restore running programs: reopen herdr in one tab only, across all windows.
# Above p10k's instant prompt, which takes over the terminal and freezes a TUI started later.
# Not in Herdr app terminals (HC_TERMINAL_ID): their terminal also reports TERM_PROGRAM=ghostty.
_herdr_client_running() {
  ps -axo tty=,command= | awk '$1 != "??" && $2 ~ /(^|\/)herdr$/ {found=1} END {exit !found}'
}
_herdr_unlock() { rm -f "$1/pid"; rmdir "$1" 2>/dev/null; }
if [[ -o interactive && "$TERM_PROGRAM" == ghostty && -z "$HERDR_ENV" && -z "$HC_TERMINAL_ID" ]] && ! _herdr_client_running; then
  _herdr_lock="${TMPDIR:-/tmp}/herdr-autostart.lock"
  # A lock left by a shell that died (crash, closed tab) is stale; clear it.
  [[ -d $_herdr_lock ]] && ! kill -0 "$(<$_herdr_lock/pid)" 2>/dev/null && _herdr_unlock "$_herdr_lock"
  # mkdir is atomic, so only one of several tabs restoring at once gets the lock.
  if mkdir "$_herdr_lock" 2>/dev/null; then
    print $$ > "$_herdr_lock/pid"
    "$HOME/.local/bin/herdr"
    _herdr_unlock "$_herdr_lock"
  fi
  unset _herdr_lock
fi
```

Quitting herdr drops back to the normal zsh prompt in that tab. On WSL, the Windows
Terminal profile from Step 19 does this job instead; nothing goes into `~/.zshrc`.

## 3. Check version and existing configuration

herdr is now installed (either just now, or already). Check its version against
herdr-spin's minimum (0.8.2), and check what's already configured:

```bash
herdr --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1
test -f "$HOME/.config/herdr-spin/spin.py" && echo "herdr-spin: INSTALLED" || echo "herdr-spin: MISSING"
grep -q '\[ui\.toast\]' "$HOME/.config/herdr/config.toml" 2>/dev/null && echo "notifications: CONFIGURED" || echo "notifications: MISSING"
test -x ~/.local/bin/mdv && { herdr plugin list 2>/dev/null | grep -q 'local.mdv-restore' && echo "mdv-restore: INSTALLED" || echo "mdv-restore: MISSING"; }
```

The last line prints nothing when mdv (Step 15) is not installed; then don't offer mdv-restore below.

Compare the version against `0.8.2` (e.g. `printf '%s\n0.8.2\n' "$VERSION" | sort -V | head -1` —
if that prints `0.8.2`, the installed version is new enough). If it's older, tell the
user herdr-spin needs 0.8.2+ and suggest `herdr update` (or their package manager, if
they installed via Homebrew/mise/Nix), then don't offer herdr-spin below — notifications
have no version requirement and can still be offered.

## 4. Wheel scrolling

herdr captures the mouse and scrolls its own scrollback, 3 lines per
wheel notch, whatever the terminal is set to; a free-spinning wheel (Logitech MX) jumps
pages at a time. Skip if `~/.config/herdr/config.toml` already sets `mouse_scroll_lines`.
Otherwise use AskUserQuestion: "Scroll 1 line per mouse wheel notch in herdr?" — "Yes
(Recommended)" / "No". If yes, read the file with the Read tool and add the key to its
existing `[ui]` table (add a `[ui]` table only if there is none; a second one is a TOML
error):

```toml
[ui]
mouse_scroll_lines = 1
```

Apply with `herdr server reload-config`; no restart needed.

## 5. Pick the extras

Only ask about things that are still `MISSING` (and, for herdr-spin, only if the version
check passed). If all are already configured, report that and skip to Step 21.

Use AskUserQuestion (multiSelect) with whichever of these still apply: "herdr is
installed. Set up any of these?" — "Animated agent spinner (herdr-spin)" (herdr dropped
its built-in spinner in 0.8.0 for performance reasons, with no setting to bring it back —
this plugin restores one glyph per agent state in the sidebar), "Agent notifications"
(a toast when a background agent finishes or needs input, so you don't have to keep
glancing at the sidebar) and "Reopen mdv after a restart (mdv-restore)" (mdv panes come
back on the same files after a herdr server restart, without showing up as agents in the
sidebar).

If the user picks none, skip to Step 21.

## 6. If "Animated agent spinner (herdr-spin)" was picked

a. Copy this skill's `assets/herdr-spin/spin.py` and `assets/herdr-spin/herdr-plugin.toml`
   into `~/.config/herdr-spin/`:

   ```bash
   mkdir -p ~/.config/herdr-spin
   cp <this-skill-dir>/assets/herdr-spin/spin.py <this-skill-dir>/assets/herdr-spin/herdr-plugin.toml ~/.config/herdr-spin/
   ```

b. Register the plugin with herdr:

   ```bash
   herdr plugin link ~/.config/herdr-spin
   herdr plugin list
   ```

   Confirm the output lists `local.spin ... enabled`. If it doesn't, report the output
   to the user and stop this sub-step.

c. Update herdr's sidebar config. Read `~/.config/herdr/config.toml` with the Read tool.
   This edit is additive — never overwrite an existing config file with a fresh one:

   - If the file has no `[ui.sidebar.agents]` table, use Edit to append one.
   - If it already has one, merge `rows` into it instead of adding a second table.

   Target shape:

   ```toml
   [ui.sidebar.agents]
   rows = [
     [
       { token = "$w", fg = "#fabd2f", bold = true, dim = false },
       { token = "$b", fg = "#fb4934", bold = true, dim = false },
       { token = "$d", fg = "#b8bb26", dim = false },
       { token = "$i", fg = "#b8bb26", dim = false },
       "workspace",
       "tab",
     ],
     ["agent"],
   ]
   ```

   This drops `state_icon` (herdr's default first column) in favor of four metadata
   tokens, one per agent state — a metadata token carries a single fixed colour, so the
   plugin needs one per state rather than one shared column. The hex values are herdr's
   gruvbox palette; on another theme, swap them for that theme's yellow/red/green.

d. Apply the config and start the animator:

   ```bash
   herdr server reload-config
   python3 ~/.config/herdr-spin/spin.py
   ```

   Herdr only fires the plugin's `[[startup]]` hook when its server starts, not when a
   plugin is linked, so this first run has to be by hand.

e. Verify:

   ```bash
   test -f "/tmp/herdr-spin-$UID/spin.lock" && echo "animator running" || echo "animator not running"
   ```

   If not running, check `/tmp/herdr-spin-$UID/spin.log` for errors.

   Tell the user: restart after editing the script with
   `python3 ~/.config/herdr-spin/spin.py --restart`, and see this skill's
   `references/herdr-spin.md` for tuning the frame rate, troubleshooting a blank icon
   column, and uninstalling.

## 7. If "Agent notifications" was picked

Read `~/.config/herdr/config.toml` with the Read tool — same additive-merge caution as
above. Use Edit to append (or Write to create the file if it doesn't exist):

```toml
[ui.toast]
delivery = "herdr"
delay_seconds = 1

[ui.toast.herdr]
position = "bottom-right"
```

`delivery = "herdr"` is an in-app toast. Mention the alternatives to the user: `"terminal"`
also works over SSH (an outer-terminal notification instead of an in-app one), and
`"system"` uses the OS notification service — on macOS this needs
`brew install terminal-notifier` for full functionality (click-to-focus); without it,
herdr falls back to `osascript`, which shows up as "Script Editor" in Notification Center
and can't focus the terminal.

Apply:

```bash
herdr server reload-config
```

## 8. If "Reopen mdv after a restart (mdv-restore)" was picked

The mdv launcher records each pane's open files under `~/.local/state/mdv-restore/` and
deletes the entry when mdv quits with `q`; this plugin's `[[startup]]` hook reopens the
recorded ones after the server restarts. It replaces the earlier launcher, which reported
mdv to herdr as an agent (`herdr pane report-agent`) and so listed every open file in the
agent sidebar. If Step 15 reported `~/.local/bin/mdv` as outdated and the update was
skipped, install the launcher now, since the old one never writes the state the plugin
reads:

```bash
install -m 755 <this-skill-dir>/assets/mdv/mdv ~/.local/bin/mdv
```

Copy and register the plugin:

```bash
mkdir -p ~/.config/herdr-mdv-restore
cp <this-skill-dir>/assets/mdv-restore/herdr-plugin.toml <this-skill-dir>/assets/mdv-restore/restore.sh ~/.config/herdr-mdv-restore/
herdr plugin link ~/.config/herdr-mdv-restore
herdr plugin list
```

Confirm the output lists `local.mdv-restore ... enabled`. Nothing else is needed: the hook
runs on the next server start. Tell the user what happens after `herdr server stop` and
`herdr`: mdv panes return on the same files, a pane quit with `q` returns as a plain
shell, and `herdr plugin log list --plugin local.mdv-restore` shows what the hook did.

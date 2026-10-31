# Herdr app setup

Step 20 sends you here when the user picks the Herdr app (alone or together with the TUI).
Follow the sections in order. `<this-skill-dir>` is the skill directory, `WORK_DIR` the
projects folder from Step 19 (relative to `$HOME`, e.g. `Development`).

The [Herdr app](https://herdr.dev) is a native window around **herdr-core** (`hc`), a small
server that keeps every terminal and agent running when the window closes. It shares
nothing with the Herdr TUI (`herdr`): different binary, config (`~/.config/herdr-app`) and
sessions, so both can be installed side by side. Its agent status comes from the agents
themselves (OSC 7501); Claude Code reports it out of the box.

## 1. Check what is there

```bash
command -v herdr-app && command -v hc && hc --version || echo "herdr-app: MISSING"
test -d ~/.config/herdr-app/mods/agent-resume && echo "agent-resume: INSTALLED" || echo "agent-resume: MISSING"
grep -q '# >>> setup-zsh herdr-app >>>' ~/.zshrc && echo "zsh block: OK" || echo "zsh block: MISSING"
```

Skip the sections whose part is already in place.

## 2. Install

The installer puts the app in `~/.local/share/herdr-app` (Linux) or `~/Applications`
(macOS), links `herdr-app` and `hc` into `~/.local/bin`, and needs no sudo. Running a piped
installer may be blocked for you; then give the user the command to run with `!`:

```bash
curl -fsSL https://releases.herdr.dev/app/install.sh | sh
```

**On WSL, install it inside WSL, never the Windows build.** The Windows app runs
herdr-core on Windows: "Start an agent" launches the Windows `claude`, folders are Windows
paths, and nothing from the WSL side (hooks, `hc` labels, resume) reaches it. Pointing its
shell at `wsl.exe` only fixes plain terminals. The Linux app shows on the Windows desktop
through WSLg. If a Windows build is installed (`%LOCALAPPDATA%\Programs\herdr-app`,
`herdr-core`), offer to remove it; give the user the PowerShell commands rather than
deleting it yourself.

## 3. WSL only: fonts, Start menu entry, icon

Skip this section outside WSL.

**UI font.** A minimal Debian/Ubuntu has none of the fonts the app falls back to for its
interface, and it crashes (`failed to resolve font '.SystemUIFont' or any of the
fallbacks`) as soon as a panel such as Files or Changes opens. Copy Segoe UI and Arial from
Windows into the user's fonts, no sudo:

```bash
mkdir -p ~/.local/share/fonts/windows
cp /mnt/c/Windows/Fonts/segoeui*.ttf /mnt/c/Windows/Fonts/arial.ttf /mnt/c/Windows/Fonts/arialbd.ttf \
   /mnt/c/Windows/Fonts/ariali.ttf /mnt/c/Windows/Fonts/arialbi.ttf ~/.local/share/fonts/windows/
fc-cache -f ~/.local/share/fonts >/dev/null
```

**Terminal font.** The Nerd Font from Step 4 lives on Windows; WSLg apps only see Linux
fonts, so p10k's icons are missing until it is copied over too. For MesloLGS NF:

```bash
WF="/mnt/c/Users/$(cmd.exe /c 'echo %USERNAME%' 2>/dev/null | tr -d '\r')/AppData/Local/Microsoft/Windows/Fonts"
mkdir -p ~/.local/share/fonts/nerd && cp "$WF"/MesloLGS*.ttf ~/.local/share/fonts/nerd/
fc-cache -f ~/.local/share/fonts >/dev/null
```

For Fira Code copy `FiraCodeNerdFont-*.ttf` instead. Section 4 sets it as the app's font.

**Start menu entry and taskbar icon.** WSLg only creates Windows Start menu entries (and
taskbar icons for running windows) for apps in `/usr/share/applications`; the installer's
entry in `~/.local/share/applications`, with an SVG icon, leaves the window as Tux, the
Linux penguin. Install the PNG icon shipped with this skill, then give the user the two
sudo commands:

```bash
mkdir -p ~/.local/share/icons/hicolor/256x256/apps
cp <this-skill-dir>/assets/herdr-app/herdr-app.png ~/.local/share/icons/hicolor/256x256/apps/
```

```bash
sudo install -m 644 ~/.local/share/applications/herdr-app.desktop /usr/share/applications/herdr-app.desktop
sudo sed -i "s|^Icon=.*|Icon=$HOME/.local/share/icons/hicolor/256x256/apps/herdr-app.png|" /usr/share/applications/herdr-app.desktop
```

WSLg picks it up after `wsl --shutdown` (which ends this session too, so say so). Then the
Start menu has **Herdr (<distro>)** in the distro's folder. Tell the user to pin it from
the Start menu (right-click > Pin to taskbar), not from the running window: pinning a
running WSLg window stores WSLg's remote-window host, and the pin breaks ("The item
'Program' ... was changed or moved").

## 4. App settings

Read `~/.config/herdr-app/settings.json` (it exists after the first start; create it with
`{}` if not) and add the terminal font from Step 4 unless `font` is already set:
`"MesloLGS NF"` or `"FiraCode Nerd Font"`. Leave `zoom` alone: WSLg does not pass Windows
display scaling through, so users set it to taste.

## 5. Resume Claude Code after a reboot (herdr-agent-resume)

The app keeps terminals across window restarts, but a reboot or `wsl --shutdown` brings
them back as bare shells, and the app does not resume agents by design (herdr-core#13).
[herdr-agent-resume](https://github.com/thuanlm215/herdr-agent-resume) closes that gap for
Claude Code and Codex: a `SessionStart` hook labels each app terminal with its session, and
a resume pass types `cd '<folder>' && claude --resume <id>` into terminals that lost it.
The hook returns at once outside an app terminal (no `HC_TERMINAL_ID`), so the Herdr TUI is
unaffected.

Use AskUserQuestion: "Bring Claude Code sessions back after a reboot in the Herdr app?" -
"Yes (Recommended)" / "No". If yes:

```bash
mkdir -p ~/.local/src
git -C ~/.local/src/herdr-agent-resume pull -q 2>/dev/null \
  || git clone -q --depth 1 https://github.com/thuanlm215/herdr-agent-resume ~/.local/src/herdr-agent-resume
python3 -I ~/.local/src/herdr-agent-resume/scripts/install.py --dry-run
```

The dry run lists the mod folder, the Ctrl+Shift+R shortcut and `~/.claude/settings.json`.
The real install edits Claude Code's settings (after backing them up), which you may not
be allowed to do; give the user the command to run with `!`:

```bash
python3 -I ~/.local/src/herdr-agent-resume/scripts/install.py
```

Section 6 makes the resume automatic; Ctrl+Shift+R stays as the manual way.

## 6. zsh block: automatic resume and start folder

Read `~/.zshrc`. Unless it already contains `# >>> setup-zsh herdr-app >>>`, append
`<this-skill-dir>/assets/herdr-app/zshrc-block.zsh` at the end, with both `<WORK_DIR>`
replaced by the Step 19 folder:

```bash
sed "s|<WORK_DIR>|$WORK_DIR|g" <this-skill-dir>/assets/herdr-app/zshrc-block.zsh >> ~/.zshrc
zsh -n ~/.zshrc && echo "syntax ok"
```

The block only acts in app terminals (`HC_TERMINAL_ID` set):

- **Claude Code / Codex:** when a restored shell finds an `agent-resume` label, it runs one
  resume pass in the background, so sessions come back without Ctrl+Shift+R. Skipped when
  section 5 was declined.
- **mdv:** the mdv launcher (Step 15) records its files in an `mdv-resume` label; a
  restored shell types the same `mdv` command again. `q` clears the label, so a viewer
  that was closed stays closed.
- **Start folder:** a new shell that starts in `~` moves to `~/<WORK_DIR>`.

It needs `jq` (Step 14) and the current mdv launcher; if Step 15 reported
`~/.local/bin/mdv` as outdated and the update was skipped, install it now with
`install -m 755 <this-skill-dir>/assets/mdv/mdv ~/.local/bin/mdv`.

## 7. Verify

Start the app (`herdr-app &`, or the Start menu entry on WSL). Then, from a terminal
outside it:

```bash
hc server status | jq -c '{version, live}'
```

Tell the user how to try the full cycle: open Claude Code and an mdv in app terminals, run
`wsl --shutdown` (WSL) or reboot, reopen Herdr. The mdv panes reopen by themselves and
Claude Code comes back on its conversation a few seconds later. `hc server restart` is no
test: herdr-core keeps programs running through a planned restart.

Defaults worth mentioning: Alt+Up / Alt+Down jump between agents (`agent.prev` /
`agent.next`), and the app takes Ctrl+Shift+T/N/O/R and Alt+arrows / Alt+H/J/K/L for itself.

## Uninstall

```bash
python3 -I ~/.local/src/herdr-agent-resume/scripts/install.py --uninstall
rm -rf ~/.local/share/herdr-app ~/.local/bin/herdr-app ~/.local/bin/hc ~/.local/bin/herdr-core \
  ~/.config/herdr-app ~/.local/src/herdr-agent-resume ~/.cache/herdr-agent-resume.lock
```

Then remove the `setup-zsh herdr-app` block from `~/.zshrc`, and on WSL
`sudo rm /usr/share/applications/herdr-app.desktop`.

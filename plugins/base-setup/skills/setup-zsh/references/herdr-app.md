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
test -d ~/.config/herdr-app/mods/reviewer && echo "reviewer: INSTALLED" || echo "reviewer: MISSING"
grep -q '# >>> setup-zsh herdr-app >>>' ~/.zshrc && echo "zsh block: OK" || echo "zsh block: MISSING"
grep -q '# >>> setup-zsh resume >>>' ~/.zshrc && echo "resume block: OK" || echo "resume block: MISSING"
```

Skip the sections whose part is already in place. Run section 7 anyway when `~/.zshrc`
contains `_hc_resumable` or `mdv-resume` (an earlier version of the zsh block).

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
   /mnt/c/Windows/Fonts/ariali.ttf /mnt/c/Windows/Fonts/arialbi.ttf \
   /mnt/c/Windows/Fonts/seguisym.ttf ~/.local/share/fonts/windows/
fc-cache -f ~/.local/share/fonts >/dev/null
```

Segoe UI Symbol (`seguisym.ttf`) is there for the Braille characters btop and other TUIs draw
graphs with: the Nerd Font has none, and without it Linux falls back to the blocky Unifont.
`fc-match ':charset=2800-28ff' family` should print `Segoe UI Symbol`.

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

**Links open in the Windows browser.** The app asks Linux (`xdg-open`) to open a clicked
link, which picks a browser installed inside WSL if there is one. Install a small handler
that passes links to `explorer.exe`, so they open in the default Windows browser, and make
it the Linux default for web links (back up `~/.config/mimeapps.list` first if it exists):

```bash
install -m 755 <this-skill-dir>/assets/herdr-app/open-in-windows ~/.local/bin/open-in-windows
mkdir -p ~/.local/share/applications
sed "s|<HOME>|$HOME|" <this-skill-dir>/assets/herdr-app/open-in-windows.desktop \
  > ~/.local/share/applications/open-in-windows.desktop
for m in x-scheme-handler/http x-scheme-handler/https x-scheme-handler/about x-scheme-handler/unknown text/html; do
  xdg-mime default open-in-windows.desktop "$m"
done
xdg-mime query default x-scheme-handler/https
```

Expect `open-in-windows.desktop`. This also covers terminal tools that open links through
`xdg-open` (`gh pr view --web`). Other URL schemes, such as `claude-cli`, keep their handlers.

## 4. App settings

Read `~/.config/herdr-app/settings.json` (it exists after the first start; create it with
`{}` if not) and add the terminal font from Step 4 unless `font` is already set:
`"MesloLGS NF"` or `"FiraCode Nerd Font"`. Leave `zoom` alone: WSLg does not pass Windows
display scaling through, so users set it to taste.

## 5. Changes panel with syntax highlighting (herdr-reviewer)

The shipped Changes panel shows diffs without syntax highlighting, and Herdr takes only
fixes for its shipped mods (features are meant to be built as your own mod).
[herdr-reviewer](https://github.com/vytasgavelis/herdr-reviewer) replaces it:
syntax-colored diffs, scopes (uncommitted, last commit, branch), and line comments it sends
to an agent ("Ask about diff"). It only runs `git diff`, `git rev-parse` and `hc send`.

Use AskUserQuestion: "Replace the Changes panel with herdr-reviewer (syntax-colored diffs,
line comments for the agent)?" - "Yes (Recommended)" / "No". If yes:

```bash
mkdir -p ~/.local/src
git -C ~/.local/src/herdr-reviewer pull -q 2>/dev/null \
  || git clone -q --depth 1 https://github.com/vytasgavelis/herdr-reviewer ~/.local/src/herdr-reviewer
cp -r ~/.local/src/herdr-reviewer/mods/reviewer ~/.config/herdr-app/mods/
herdr-app check ~/.config/herdr-app/mods/reviewer
```

Expect `check passed`. Shipped layouts are read-only (replaced on every start), so clone
`main` and point the clone's Changes block at the mod. This talks to the running app;
start it first (`herdr-app &`) if it is not. Skip the clone if
`~/.config/herdr-app/layouts/my-main.json` exists, since an existing name is refused:

```bash
herdr-app do layout.clone '{"name":"main","as":"my-main"}'
```

The clone also switches the window to `my-main`. Read
`~/.config/herdr-app/layouts/my-main.json` and use the Edit tool to change the block with
`"id": "changes"` from `"mod": "changes"` to `"mod": "reviewer"`, so it reads
`{"id": "changes", "type": "block", "content": {"mod": "reviewer"}}`. The app reloads
layouts live; `herdr-app status` should show `"layout": "my-main"` and `"errors": []`.

Tell the user it opens from the same Changes button (top right), with "Uncommitted ▾" and
"Ask about diff" in its header. Ctrl+Shift+L or
`herdr-app do layout.switch '{"name":"main"}'` goes back to the shipped panel. Herdr never
updates the mod or the cloned layout; to update the mod, run `git pull` in
`~/.local/src/herdr-reviewer` and the `cp` line again.

**Known issue:** at a Herdr zoom other than 1, diff rows overlap and changed lines show
darker stripes. It is a herdr-app list bug (rows spaced in unzoomed pixels), fixed by
[herdr-app#296](https://github.com/herdrdev/herdr-app/pull/296); the stripes are cosmetic
and go away with the herdr-app release that includes it. Don't patch the mod for it: once
the app is fixed, a patched mod would zoom its rows twice.

## 6. Resume Claude Code after a reboot (herdr-agent-resume)

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

Section 7 makes the resume automatic; Ctrl+Shift+R stays as the manual way.

## 7. zsh blocks: automatic resume and start folder

Two blocks, split by job: the `setup-zsh resume` block records what runs in a terminal, the
`setup-zsh herdr-app` block restores it in the shell that comes back. The herdr TUI's
mdv-restore plugin reads the same resume block's records, so it is shared between both.

Read `~/.zshrc`. If it contains `_hc_resumable` or `mdv-resume`, it has an earlier version:
see the end of this section instead. Unless it already contains `# >>> setup-zsh resume >>>`, read
`<this-skill-dir>/assets/zshrc/resume.zsh` and use the Edit tool to append it at the end.
Then, unless `~/.zshrc` contains `# >>> setup-zsh herdr-app >>>`, append
`<this-skill-dir>/assets/herdr-app/zshrc-block.zsh` after it, with both `<WORK_DIR>`
replaced by the Step 19 folder:

```bash
sed "s|<WORK_DIR>|$WORK_DIR|g" <this-skill-dir>/assets/herdr-app/zshrc-block.zsh >> ~/.zshrc
zsh -n ~/.zshrc && echo "syntax ok"
```

**macOS with the herdr TUI auto-start.** The app's terminals report
`TERM_PROGRAM=ghostty`, so the Ghostty auto-start block from `references/herdr-tui.md`
would launch the herdr TUI inside the first app terminal. If `~/.zshrc` contains
`_herdr_client_running` and its `if` line lacks `-z "$HC_TERMINAL_ID"`, add that condition
with the Edit tool, next to `-z "$HERDR_ENV"`.

In app terminals (`HC_TERMINAL_ID` set) they do this:

- **Claude Code / Codex:** when a restored shell finds an `agent-resume` label, it runs one
  resume pass in the background, so sessions come back without Ctrl+Shift+R. Skipped when
  section 6 was declined.
- **nvim, btop, lazygit, mdv:** the resume block wraps these in zsh functions that record
  the folder and the exact command in a `cmd-resume` label while the program runs, and
  clear it when the program ends with the shell still alive, however it was quit. After a
  reboot the shell is gone too, so the label stays, and the herdr-app block in the restored
  shell types `cd <folder> && <command>` again. With the LazyVim config from Step 16, nvim
  keeps the label in step with the files open inside it and reopens them, the current one
  first (its swap file offers any unsaved edits); splits and tabs inside nvim do not come
  back. `some-command | mdv` is not recorded. To add another program, add its name to the
  `for _resume_cmd in ...` list in the resume block.
- **Start folder:** a new shell that starts in `~` moves to `~/<WORK_DIR>`.

They need `jq` (Step 14).

An earlier version kept the wrapper inside the herdr-app block, and an even earlier one
only reopened mdv from an `mdv-resume` label the mdv launcher wrote. If `~/.zshrc` contains
`_hc_resumable` or `mdv-resume`, replace the whole block between the `setup-zsh herdr-app`
markers with the current resume asset followed by the current herdr-app asset, and update
`~/.local/bin/mdv` if Step 15 reported it as outdated: the launcher no longer records
anything.

## 8. Verify

Start the app (`herdr-app &`, or the Start menu entry on WSL). Then, from a terminal
outside it:

```bash
hc server status | jq -c '{version, live}'
```

Tell the user how to try the full cycle: open Claude Code and an mdv in app terminals, run
`wsl --shutdown` (WSL) or reboot, reopen Herdr. The mdv terminals reopen by themselves and
Claude Code comes back on its conversation a few seconds later. `hc server restart` is no
test: herdr-core keeps programs running through a planned restart.

Defaults worth mentioning: Alt+Up / Alt+Down jump between agents (`agent.prev` /
`agent.next`), and the app takes Ctrl+Shift+T/N/O/R and Alt+arrows / Alt+H/J/K/L for itself.

## Uninstall

```bash
python3 -I ~/.local/src/herdr-agent-resume/scripts/install.py --uninstall
rm -rf ~/.local/share/herdr-app ~/.local/bin/herdr-app ~/.local/bin/hc ~/.local/bin/herdr-core \
  ~/.config/herdr-app ~/.local/src/herdr-agent-resume ~/.cache/herdr-agent-resume.lock \
  ~/.local/src/herdr-reviewer
```

To remove only herdr-reviewer, switch back to the shipped layout first:

```bash
herdr-app do layout.switch '{"name":"main"}'
rm -rf ~/.config/herdr-app/mods/reviewer ~/.config/herdr-app/layouts/my-main.json ~/.local/src/herdr-reviewer
```

On WSL, also remove the link handler (`~/.local/bin/open-in-windows`,
`~/.local/share/applications/open-in-windows.desktop`) and point web links back at a Linux
browser with `xdg-mime default <browser>.desktop x-scheme-handler/https` (same for `http`
and `text/html`), if one is installed.

Then remove the `setup-zsh herdr-app` block from `~/.zshrc` (and the `setup-zsh resume`
block, unless the herdr TUI's mdv-restore plugin still uses it), and on WSL
`sudo rm /usr/share/applications/herdr-app.desktop`.

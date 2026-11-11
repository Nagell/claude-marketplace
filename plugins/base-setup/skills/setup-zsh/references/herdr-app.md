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
test -f ~/.config/herdr-app/layouts/my-nested-tabs.json && echo "my-nested-tabs: INSTALLED" || echo "my-nested-tabs: MISSING"
for m in over9k-switcher walkthrough linear; do test -d ~/.config/herdr-app/mods/$m && echo "$m: INSTALLED" || echo "$m: MISSING"; done
test -d ~/.config/herdr-app/mods/reviewer && echo "reviewer: INSTALLED (earlier version of this guide)"
grep -q '# >>> setup-zsh herdr-app >>>' ~/.zshrc && echo "zsh block: OK" || echo "zsh block: MISSING"
grep -q '# >>> setup-zsh resume >>>' ~/.zshrc && echo "resume block: OK" || echo "resume block: MISSING"
```

Skip the sections whose part is already in place. Run section 8 anyway when `~/.zshrc`
contains `_hc_resumable` or `mdv-resume` (an earlier version of the zsh block). When
`reviewer` is installed, section 5 replaces it.

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

**macOS only: Ctrl shortcuts.** On macOS the app ships a Cmd-only keymap in
`~/.config/herdr-app/keys.json` (it exists after the first start and reloads on save). Use
AskUserQuestion: "Add Windows-style Ctrl shortcuts to the Herdr app? App commands go on
Ctrl+Shift (Ctrl+Shift+P palette, Ctrl+Shift+T new tab, Ctrl+Shift+E/O split), so plain
Ctrl+letters stay with the terminal. The Cmd shortcuts keep working." with options "Yes, add
Ctrl shortcuts" and "No, keep Cmd only". If yes, merge this skill's
`assets/herdr-app/keys-ctrl-macos.json` into it. The merge is additive: a key the user
already bound to something else stays as it is and is printed.

```bash
python3 -I - <this-skill-dir>/assets/herdr-app/keys-ctrl-macos.json "$HOME/.config/herdr-app/keys.json" <<'EOF'
import json
import sys

additions = json.load(open(sys.argv[1]))
path = sys.argv[2]
keys = json.load(open(path))
for section, bindings in additions.items():
    target = keys.setdefault(section, {})
    for key, action in bindings.items():
        if target.get(key, action) != action:
            print(f"kept {section} {key} = {target[key]} (skill wanted {action})")
        else:
            target[key] = action
with open(path, "w") as f:
    json.dump(keys, f, indent=2, ensure_ascii=False)
    f.write("\n")
EOF
sleep 1; cat "$HOME/.config/herdr-app/keys.error" 2>/dev/null || echo "keys.json accepted"
```

If Herdr rejects the file, it keeps the last good keymap and writes the reason to
`keys.error`. Report that, and any `kept ...` lines, to the user.

## 5. Sidebar with tabs, side panels and agent details (herdr-nested-tabs)

The shipped window shows only the selected space's tabs, in the top bar; the Changes panel
has no syntax colours. This section sets up the personal layout `my-nested-tabs`:

- **Sidebar** ([herdr-nested-tabs](https://github.com/Nagell/herdr-nested-tabs)): each
  space lists its tabs under it, with a fold arrow, one status column (spinner working,
  red dot blocked, blue dot done), and for Claude Code and Codex agents model · effort ·
  context % · time since the last reply. Claude's sub-agents sit behind a count chip. The
  top bar keeps Files and Changes and drops its tab buttons.
- **Side panel:** [Better Files and Better Changes](https://github.com/munza/herdr-mods)
  with syntax colours, plus [Over9k](https://github.com/herunan/herdr-over9k)'s
  **Timeline** (the focused agent's conversation, prompt by prompt) as a third button.
- **Usage strip** (Over9k Usage) at the bottom of the sidebar: Claude's and Codex's 5-hour
  and weekly limits.

Use AskUserQuestion: "Set up the Herdr app sidebar that lists every space's tabs, with
agent details, syntax-coloured Files/Changes panels, Timeline and Usage?" - "Yes
(Recommended)" / "No". If yes, start the app if it is not running (`herdr-app &`), then
fetch and copy the mods. `Nagell/herdr-mods` carries the syntax colouring until
munza/herdr-mods merges it ([PR](https://github.com/munza/herdr-mods/pull/9)); clone munza's repo once it has.

```bash
mkdir -p ~/.local/src
git -C ~/.local/src/herdr-nested-tabs pull -q 2>/dev/null \
  || git clone -q --depth 1 https://github.com/Nagell/herdr-nested-tabs ~/.local/src/herdr-nested-tabs
git -C ~/.local/src/herdr-over9k pull -q 2>/dev/null \
  || git clone -q --depth 1 https://github.com/herunan/herdr-over9k ~/.local/src/herdr-over9k
git -C ~/.local/src/herdr-mods pull -q 2>/dev/null \
  || git clone -q --depth 1 -b feat/syntax-colouring https://github.com/Nagell/herdr-mods ~/.local/src/herdr-mods
M=~/.config/herdr-app/mods
S=~/.local/src
cp -r "$S"/herdr-nested-tabs/mods/nested-tabs "$S"/herdr-nested-tabs/mods/tabs-bar "$M"/
cp -r "$S"/herdr-mods/better-files/mods/better-files "$S"/herdr-mods/better-changes/mods/better-changes "$M"/
cp -r "$S"/herdr-over9k/over9k-timeline/mods/over9k-prompts "$S"/herdr-over9k/over9k-usage/mods/over9k-usage "$M"/
for m in nested-tabs tabs-bar better-files better-changes over9k-prompts over9k-usage; do herdr-app check "$M/$m"; done
```

Expect six `check passed`. Before copying on a fresh machine, tell the user what the mods
run and read (Herdr's rule for mods other people made; each repo's `RECIPE.md` lists it
under "Built from"): the sidebar runs `git`, `ps`, `lsof`, `hc` and `python3` scripts that
read Claude Code's and Codex's session files; Better Files/Changes run `git`; Timeline
reads the focused agent's conversation file.

Herdr adds a mod whose `mod.json` has a `place` (Better Changes, Timeline, Usage) to the
layout on screen as a new block. Run `herdr-app status`: if `layout` is a personal layout
(not `main`, `terminals` or `win98`), read it and remove any block for those three mods
that the layout didn't have before.

Copy this skill's layout, unless one with that name already exists (never overwrite the
user's), switch to it and merge the sidebar's keys with the section 4 merge snippet
(pass `~/.local/src/herdr-nested-tabs/keys.json` as its first argument):

```bash
test -e ~/.config/herdr-app/layouts/my-nested-tabs.json \
  || cp <this-skill-dir>/assets/herdr-app/my-nested-tabs.json ~/.config/herdr-app/layouts/
herdr-app do layout.switch '{"name":"my-nested-tabs"}'
herdr-app status | jq -c '{layout, errors}'
```

Expect `"layout":"my-nested-tabs"` and `"errors":[]`. Tell the user:

- **Tabs** are listed under each space. A tab with several terminals folds; a middle click
  closes a tab.
- **Cmd+Shift+I** switches agent details between one line (Compact) and two (Detailed);
  the button in the Spaces header does the same. **Cmd+Shift+T** brings the tab buttons
  back to the top bar, and hides them again.
- **Files, Changes and Timeline** open from the top-right buttons.
- **Usage's Claude row** fills in after Claude Code's next reply once the status line
  below is on. The Codex row works without it.
- **Ctrl+Shift+L** or `herdr-app do layout.switch '{"name":"main"}'` goes back to the
  shipped window.

**Claude's limits for Usage.** Claude Code gives the 5-hour and weekly limits only to a
status line, so Usage's Claude row needs one that runs Over9k's `claude-statusline.sh`.
The strip's own setup button replaces any status line the user has. Check what is set:

```bash
jq -c '.statusLine' ~/.claude/settings.json
```

- **Names `claude-statusline.sh` in an `over9k` folder:** already on, skip.
- **`null`:** use AskUserQuestion: "Show Over9k's Claude status line (model, context,
  cache, limits) under Claude Code's prompt, for Usage's Claude row?" - "Yes
  (Recommended)" / "No". If yes, run the strip's setup:
  `sh ~/.config/herdr-app/mods/over9k-usage/setup.sh status on ~/.config/herdr-app/mods/over9k-usage/claude-statusline.sh`.
- **Anything else (the user's own):** use AskUserQuestion: "Keep your Claude status line
  and run Over9k's in the background for Usage's Claude row?" - "Keep mine, add Over9k
  (Recommended)" / "Switch to Over9k's line" / "Skip". "Switch" runs the setup line above
  (it keeps theirs aside and puts it back when turned off). "Keep mine" installs this
  skill's wrapper: it runs Over9k's script with its output dropped and shows the saved
  status line, which Over9k's off switch restores from the same file.

```bash
S=~/.claude/settings.json
cp "$S" "$S.bak-statusline"
jq '.statusLine' "$S" > ~/.claude/.over9k-statusline-was.json
install -m 755 <this-skill-dir>/assets/herdr-app/statusline-over9k.sh ~/.claude/statusline-over9k.sh
jq --arg c "sh ~/.claude/statusline-over9k.sh $HOME/.config/herdr-app/mods/over9k-usage/claude-statusline.sh" \
  '.statusLine = {type: "command", command: $c}' "$S" > "$S.tmp" && [ -s "$S.tmp" ] && mv "$S.tmp" "$S"
```

These edit Claude Code's settings, which you may not be allowed to do; then give the user
the lines to run with `!`. After Claude Code's next reply, `~/.cache/over9k/usage/claude.json`
holds the limits and the strip shows them.

Herdr never updates copied mods. To update Over9k Usage and preserve the existing Claude
status line, run this skill's `assets/herdr-app/update-over9k-usage.sh`. It refreshes the
canonical source, copies the complete standalone mod (including `claude-statusline.sh`),
keeps the display status line and sends the same callback payload to Usage in the background.

```bash
<this-skill-dir>/assets/herdr-app/update-over9k-usage.sh
```

### Git Graph (optional)

Install Git Graph from the maintained `Nagell/herdr-git-graph` fork. Its `sync.sh`
copies the mod into Herdr's live folder and validates it. It is separate from Better
Changes, so it does not change the layout's existing Changes panel automatically.

```bash
<this-skill-dir>/assets/herdr-app/update-git-graph.sh
```

The installer keeps `origin` on the personal fork, records `werlang/herdr-git-graph` as
`upstream`, updates both local branches and removes the one-off
`backup/pre-rebase-stage-commit-discard` branch before syncing the live mod.

Open it beside the active terminal with:

```bash
herdr-app do pane.split --direction right --mod git-graph
```

**Earlier version of this guide (herdr-reviewer).** If `~/.config/herdr-app/mods/reviewer`
or `layouts/my-main.json` exists, offer to remove them once `my-nested-tabs` works
(Better Changes replaces the reviewer's Changes panel). base-setup's safety hook blocks
`rm -rf` under the home folder, so give the user the commands to run with `!`. The second
line also takes the window state Herdr keeps for the layout and any `.bak` copies:

```bash
rm -rf ~/.config/herdr-app/mods/reviewer ~/.local/src/herdr-reviewer
rm -f ~/.config/herdr-app/layouts/my-main.json ~/.config/herdr-app/layouts/.state/my-main.json ~/.config/herdr-app/layouts/my-main.json.bak*
```

## 6. Popups: agent switcher, Walkthrough, Linear (optional)

Use AskUserQuestion (multiSelect): "Add any of these Herdr app popups?" with:

- **Agent switcher (Ctrl+Tab):** [Over9k Switcher](https://github.com/herunan/herdr-over9k),
  the recently used agents, Ctrl+Tab again for the next one. It takes Ctrl+Tab from "next
  tab"; Ctrl+Shift+Tab stays "previous tab".
- **Walkthrough (Cmd+Shift+K, on Linux/WSL also Alt+Shift+W):** [dmazlum's Walkthrough](https://github.com/dmazlum/herdr-walkthrough)
  explains a change step by step in reading order (uncommitted, branch, a PR, the agent's
  last turn). Each Generate runs a small `claude` request (about $0.002 with Haiku).
- **Linear (Cmd+L, on Linux/WSL also Alt+Shift+N), optional:** [herdr-linear](https://github.com/mrolafsson/herdr-linear)
  lists your Linear issues and makes a worktree per issue. On first open it downloads its
  helper program (checksum-verified) and signs in to Linear with OAuth; some Linear
  workspaces need an admin to approve its OAuth app ("Herdr Plugin") first.

For each one picked, fetch it, copy its mod, check it and merge its keys with the section
4 snippet:

| Popup | Repo (into `~/.local/src`) | Mod folder | Keys file |
| --- | --- | --- | --- |
| Agent switcher | `herunan/herdr-over9k` (from section 5) | `over9k-switcher/mods/over9k-switcher` | `over9k-switcher/keys.json` |
| Walkthrough | `dmazlum/herdr-walkthrough` | `mods/walkthrough` | `keys.json` |
| Linear | `mrolafsson/herdr-linear` | `app/mods/linear` | `app/keys.json` |

```bash
R=dmazlum/herdr-walkthrough   # or mrolafsson/herdr-linear
git -C ~/.local/src/${R#*/} pull -q 2>/dev/null \
  || git clone -q --depth 1 https://github.com/$R ~/.local/src/${R#*/}
cp -r ~/.local/src/herdr-walkthrough/mods/walkthrough ~/.config/herdr-app/mods/
herdr-app check ~/.config/herdr-app/mods/walkthrough
```

Expect `check passed` for each. The keys merge keeps a key the user already bound to
something else and prints it; report those.

The agent switcher is the exception: Herdr's own keys bind `ctrl-tab` to `tab.next`, so the
merge keeps that and the switcher gets no key. The user picked it knowing it takes Ctrl+Tab,
so set it afterwards:

```bash
python3 -I - "$HOME/.config/herdr-app/keys.json" <<'EOF'
import json
import sys

path = sys.argv[1]
keys = json.load(open(path))
keys.setdefault("global", {})["ctrl-tab"] = "mod.open:over9k-switcher"
with open(path, "w") as f:
    json.dump(keys, f, indent=2, ensure_ascii=False)
    f.write("\n")
EOF
sleep 1; cat "$HOME/.config/herdr-app/keys.error" 2>/dev/null || echo "keys.json accepted"
```

On Linux and WSL, also merge `{"global": {"alt-shift-w": "mod.open:walkthrough"}}` for
Walkthrough and `{"global": {"alt-shift-n": "mod.open:linear"}}` for Linear with the same
snippet: `cmd` is the Super/Win key there, which the desktop or Windows often takes. Both are
free in Herdr's defaults; Alt+Shift+K and Alt+Shift+L are "swap pane up" and "swap pane right".

## 7. Resume Claude Code after a reboot (herdr-agent-resume)

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
python3 -I ~/.local/src/herdr-agent-resume/scripts/install.py --update --auto --dry-run
```

The dry run lists the mod folder, the Ctrl+Shift+R shortcut, `~/.claude/settings.json` and
`Startup lines: ~/.zshrc`. `--auto` adds an `agent-resume` block to `~/.zshrc` so each
restored shell starts its own agent; a single resume pass skips shells that are still busy
starting up when it reaches them, so with many terminals some agents stay as bare shells.
The real install edits Claude Code's settings and `~/.zshrc` (after backing them up), which
you may not be allowed to do; give the user the command to run with `!`:

```bash
python3 -I ~/.local/src/herdr-agent-resume/scripts/install.py --update --auto
```

Section 8 adds the zsh blocks that make this work with p10k; Ctrl+Shift+R stays as the
manual way.

## 8. zsh blocks: automatic resume and start folder

Two blocks, split by job: the `setup-zsh resume` block records what runs in a terminal, the
`setup-zsh herdr-app` block restores it in the shell that comes back. The herdr TUI's
mdv-restore plugin reads the same resume block's records, so it is shared between both.

Read `~/.zshrc`. If it contains `_hc_resumable` or `mdv-resume`, it has an earlier version:
see the end of this section instead. Unless it already contains `# >>> setup-zsh resume >>>`, read
`<this-skill-dir>/assets/zshrc/resume.zsh` and use the Edit tool to append it at the end. If
the block is there but lacks `zselect`, it is an earlier version that loses its record on a
macOS reboot: replace everything between the `setup-zsh resume` markers with the asset.
Then, unless `~/.zshrc` contains `# >>> setup-zsh herdr-app >>>`, append
`<this-skill-dir>/assets/herdr-app/zshrc-block.zsh` after it, with both `<WORK_DIR>`
replaced by the Step 19 folder:

```bash
sed "s|<WORK_DIR>|$WORK_DIR|g" <this-skill-dir>/assets/herdr-app/zshrc-block.zsh >> ~/.zshrc
zsh -n ~/.zshrc && echo "syntax ok"
```

**After section 7's `--auto` install.** The installer's `# >>> agent-resume >>>` block starts
the agent from the shell's first precmd, where p10k's instant prompt still redirects stdin
and stdout: Claude falls into `--print` mode and exits with "No deferred tool marker found",
Codex exits with code 1, and the mod then forgets those sessions as if they were quit. If
`~/.zshrc` contains `# >>> agent-resume >>>` but not
`# >>> setup-zsh agent-resume-line-init >>>`, append
`<this-skill-dir>/assets/herdr-app/agent-resume-line-init.zsh` at the end. It must come
after the installer's block, since it moves that block's hook to line-init (where the
herdr-app block already reopens mdv and btop); if the installer has not run yet, append it
once it has:

```bash
cat <this-skill-dir>/assets/herdr-app/agent-resume-line-init.zsh >> ~/.zshrc
zsh -n ~/.zshrc && echo "syntax ok"
```

**macOS with the herdr TUI auto-start.** The app's terminals report
`TERM_PROGRAM=ghostty`, so the Ghostty auto-start block from `references/herdr-tui.md`
would launch the herdr TUI inside the first app terminal. If `~/.zshrc` contains
`_herdr_client_running` and its `if` line lacks `-z "$HC_TERMINAL_ID"`, add that condition
with the Edit tool, next to `-z "$HERDR_ENV"`.

In app terminals (`HC_TERMINAL_ID` set) they do this:

- **Claude Code / Codex:** a restored shell with an `agent-resume` label starts its own
  agent once the line editor is up (the installer's block, moved by the line-init block).
  The herdr-app block's background resume pass still runs as a fallback and skips sessions
  a shell already brought back. Skipped when section 7 was declined.
- **nvim, btop, lazygit, mdv:** the resume block wraps these in zsh functions that record
  the folder and the exact command in a `cmd-resume` label while the program runs, and
  clear it when the program ends with the shell still alive, however it was quit. A macOS
  reboot sends SIGTERM to every process: the program quits, but the interactive shell
  ignores it, so the wrapper catches it and keeps the label. When the program quits before
  the shell's own SIGTERM arrives, a non-zero exit makes the wrapper wait half a second for
  it. The herdr-app block in the
  restored shell then types `cd <folder> && <command>` again. With the LazyVim config from Step 16, nvim
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

## 9. Verify

Start the app (`herdr-app &`, or the Start menu entry on WSL). Then, from a terminal
outside it:

```bash
hc server status | jq -c '{version, live}'
```

Tell the user how to try the full cycle: open Claude Code and an mdv in app terminals, run
`wsl --shutdown` (WSL) or reboot, reopen Herdr. The mdv terminals reopen by themselves and
Claude Code comes back on its conversation a few seconds later. `hc server restart` is no
test: herdr-core keeps programs running through a planned restart. Without a reboot,
`hc server stop && hc server start` from a terminal outside the app ends every program and
brings the terminals back as shells. It does not send the shells SIGTERM the way a macOS
reboot does; to check that part, find an mdv terminal's shell and nvim PIDs
(`hc get <t> --json | jq .pid`, then `pgrep -P <pid>`), `kill -TERM` nvim and then the shell, and
confirm the terminal's `cmd-resume` label is still set (`hc get <t> --json | jq .labels`).

Defaults worth mentioning: Alt+Up / Alt+Down jump between agents (`agent.prev` /
`agent.next`), and the app takes Ctrl+Shift+T/N/O/R and Alt+arrows / Alt+H/J/K/L for itself.

## Uninstall

base-setup's safety hook blocks `rm -rf` under the home folder: give the user the commands
in this section to run with `!`.

```bash
python3 -I ~/.local/src/herdr-agent-resume/scripts/install.py --uninstall
rm -rf ~/.local/share/herdr-app ~/.local/bin/herdr-app ~/.local/bin/hc ~/.local/bin/herdr-core \
  ~/.config/herdr-app ~/.local/src/herdr-agent-resume ~/.cache/herdr-agent-resume.lock \
  ~/.local/src/herdr-nested-tabs ~/.local/src/herdr-mods ~/.local/src/herdr-over9k \
  ~/.local/src/herdr-walkthrough ~/.local/src/herdr-linear ~/.local/share/herdr-linear ~/.cache/over9k
```

To remove only the sidebar layout and popups from sections 5 and 6, switch back to the
shipped layout first, then delete their keys from `~/.config/herdr-app/keys.json` (the
entries naming `nested-tabs.`, `tabs-bar.`, `over9k-switcher`, `walkthrough` or `linear`):

```bash
herdr-app do layout.switch '{"name":"main"}'
cd ~/.config/herdr-app/mods && rm -rf nested-tabs tabs-bar better-files better-changes \
  over9k-prompts over9k-usage over9k-switcher walkthrough linear
rm -f ~/.config/herdr-app/layouts/my-nested-tabs.json ~/.config/herdr-app/layouts/.state/my-nested-tabs.json
```

On WSL, also remove the link handler (`~/.local/bin/open-in-windows`,
`~/.local/share/applications/open-in-windows.desktop`) and point web links back at a Linux
browser with `xdg-mime default <browser>.desktop x-scheme-handler/https` (same for `http`
and `text/html`), if one is installed.

Then remove the `setup-zsh herdr-app` and `setup-zsh agent-resume-line-init` blocks from
`~/.zshrc` (and the `setup-zsh resume` block, unless the herdr TUI's mdv-restore plugin
still uses it), and on WSL `sudo rm /usr/share/applications/herdr-app.desktop`.

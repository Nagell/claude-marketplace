# mdv reference

Step 15 sends you here. **Install** below is the install procedure; the sections after it
are details that don't need to be in the main skill flow: what each file does, how the
clipboard path works, troubleshooting, updating the pinned versions, and how to remove it.

## Install

Everything installs under `$HOME` — no sudo. Needs `git`, `curl`, `tar` and access to GitHub.
Run the subsections in order (an update from Step 15 runs only the ones it names).

### Neovim 0.10 or newer

The launcher runs `~/.local/bin/nvim`. Check what is there:

```bash
test -x ~/.local/bin/nvim && ~/.local/bin/nvim --version | head -1 || echo "MISSING"
```

- **0.10 or newer** → keep it and continue with the next section.
- **MISSING, but `command -v nvim` finds a 0.10+ build elsewhere** (Homebrew, apt) → link it and continue:

  ```bash
  mkdir -p ~/.local/bin && ln -s "$(command -v nvim)" ~/.local/bin/nvim
  ```

- **Otherwise** → install the pinned release tarball into `~/.local/opt`. Distribution packages are often older than 0.10 (Ubuntu 24.04 ships 0.9.5), and the config needs `vim.base64`, `vim.ui.clipboard.osc52` and `nvim_ui_send`, all 0.10 APIs. A system Neovim is never touched.

```bash
NVIM_VERSION=v0.12.4
case "$(uname -s)-$(uname -m)" in
  Linux-x86_64)  ASSET=nvim-linux-x86_64 ;;
  Linux-aarch64) ASSET=nvim-linux-arm64 ;;
  Darwin-arm64)  ASSET=nvim-macos-arm64 ;;
  Darwin-x86_64) ASSET=nvim-macos-x86_64 ;;
  *) echo "unsupported platform: $(uname -s)-$(uname -m)"; exit 1 ;;
esac
mkdir -p ~/.local/opt ~/.local/bin
curl -fsSL -o "/tmp/$ASSET.tar.gz" "https://github.com/neovim/neovim/releases/download/$NVIM_VERSION/$ASSET.tar.gz"
[[ "$(uname -s)" == Darwin ]] && xattr -c "/tmp/$ASSET.tar.gz"
tar -xzf "/tmp/$ASSET.tar.gz" -C ~/.local/opt
ln -sfn "$HOME/.local/opt/$ASSET/bin/nvim" ~/.local/bin/nvim
~/.local/bin/nvim --version | head -1
```

The `xattr -c` on macOS drops the quarantine flag so Gatekeeper does not block the unsigned binary.

### Copy the launcher and config

The files live in this skill's `assets/mdv/`. `NVIM_APPNAME=mdv` keeps the config in `~/.config/mdv`, so an existing `~/.config/nvim` is never touched.

```bash
mkdir -p ~/.config/mdv/lua
cp <this-skill-dir>/assets/mdv/init.lua <this-skill-dir>/assets/mdv/lazy-lock.json ~/.config/mdv/
cp <this-skill-dir>/assets/mdv/lua/mdreflow.lua <this-skill-dir>/assets/mdv/lua/mdview.lua ~/.config/mdv/lua/
install -m 755 <this-skill-dir>/assets/mdv/mdv ~/.local/bin/mdv
```

### Install the plugins

lazy.nvim bootstraps itself on the first start, and `Lazy! restore` checks out the commits pinned in `lazy-lock.json`. Headless, about ten seconds:

```bash
NVIM_APPNAME=mdv ~/.local/bin/nvim --headless "+Lazy! restore" +qa 2>&1 | tail -3
ls ~/.local/share/mdv/lazy
```

Expect five directories: `catppuccin`, `lazy.nvim`, `render-markdown.nvim`, `rose-pine`, `tokyonight.nvim`.

### Make sure ~/.local/bin is on PATH

```bash
zsh -i -c 'command -v mdv' 2>/dev/null || echo "NOT ON PATH"
```

If it prints NOT ON PATH, read `~/.zshrc` with the Read tool and, unless a `.local/bin` PATH export is already there, use the Edit tool to append:

```zsh
# >>> setup-zsh local-bin >>>
export PATH="$HOME/.local/bin:$PATH"
# <<< setup-zsh local-bin <<<
```

### Verify

```bash
NVIM_APPNAME=mdv ~/.local/bin/nvim --headless "+lua print(vim.g.clipboard.name)" +qa 2>&1 | tail -1
```

Expect `osc52`. Then tell the user:

```
mdv is installed. Try it on any Markdown file: mdv README.md
  /  search      q  quit      g?  all keys
  Drag-select with the mouse: the text is on your clipboard the moment you release the button.
  Keyboard: v or V to select, y to copy.
  Several files: mdv docs/*.md (Tab / Shift-Tab switches). From a pipe: some-command | mdv
```

Copies travel as OSC 52 through the terminal, so they reach the Windows clipboard from WSL without `clip.exe` (which mangles non-ASCII text) and work inside Herdr panes.

## Files

| Installed path                              | Source                          | Purpose                                                                 |
| ------------------------------------------- | ------------------------------- | ----------------------------------------------------------------------- |
| `~/.local/bin/mdv`                          | `assets/mdv/mdv`                | Launcher: `NVIM_APPNAME=mdv nvim -R FILE…`, or `-` when reading a pipe   |
| `~/.config/mdv/init.lua`                    | `assets/mdv/init.lua`           | Options, live reload, clipboard, keys, plugin list, colour schemes       |
| `~/.config/mdv/lua/mdreflow.lua`            | `assets/mdv/lua/mdreflow.lua`   | Rewrites wide pipe tables into box tables with wrapped cells             |
| `~/.config/mdv/lua/mdview.lua`              | `assets/mdv/lua/mdview.lua`     | Scratch buffer showing the reflowed file; rebuilt on change and resize   |
| `~/.config/mdv/lazy-lock.json`              | `assets/mdv/lazy-lock.json`     | Plugin commits that `Lazy! restore` checks out                           |
| `~/.config/mdv/colorscheme.txt`             | written by `\c`                 | Remembered colour scheme (per machine, not shipped)                      |
| `~/.local/share/mdv/lazy/`                  | `Lazy! restore`                 | lazy.nvim, render-markdown.nvim, catppuccin, tokyonight, rose-pine       |
| `~/.local/opt/nvim-*/`, `~/.local/bin/nvim` | Neovim release tarball          | Neovim itself, only when the step had to install one                     |
| `~/.config/herdr-mdv-restore/`              | `assets/mdv-restore/`           | herdr plugin that reopens mdv after a restart (Step 20, optional)        |
| `~/.local/state/mdv-restore/`               | written by the launcher         | Open files per herdr pane, read by the plugin                            |
| `mdv-resume` label on an app terminal       | written by the launcher         | Open files per Herdr app terminal, read by the `~/.zshrc` block          |

`assets/mdv/` is the source of truth. A change made on a machine's `~/.config/mdv` goes
back into the assets, and the lock file travels with it.

## How it works

**Live reload.** `autoread` plus a one-second `checktime` poll. The viewport is saved on
every cursor move and scroll and restored after `FileChangedShellPost`, so a file growing
under you does not throw you back to the top. The poll only runs in Normal mode, so a
search prompt or an active selection pauses reloading until you leave it (Esc).

**Tables.** Neovim cannot wrap text inside a rendered table (neovim/neovim#14409), so
`mdreflow.lua` lays out every pipe table as a box table with wrapped cells and
`mdview.lua` shows the result in a scratch buffer. Cells are reduced to plain text and the
table is emitted inside a code fence; any markdown left in a cell would run across the
wrapped lines and shift the borders through conceal. Link labels and code spans keep their
colour through extmarks, and `gx` or a double-click still opens a cell's link because the
rendered line maps back to its source line. Column widths are sqrt-weighted with an
equal-share floor, so one huge column cannot starve the rest. The file on disk is never
written.

**Clipboard.** `vim.g.clipboard` is Neovim's built-in OSC 52 copy provider and
`clipboard=unnamedplus`, so `y` copies to the system clipboard. A Visual-mode
`<LeftRelease>` mapping yanks the mouse selection to `+` on button release and shows the
toast. The selection is dropped afterwards on purpose: keeping it would pause live reload.
Herdr captures OSC 52 written by a pane application and forwards it to the host clipboard,
and Windows Terminal handles OSC 52 itself, so the copy reaches the Windows clipboard from
WSL with UTF-8 intact. `clip.exe` was rejected because it decodes its input in the console
code page and turns `ż` into `┼╝`. Paste is a stub that returns the last copy: a viewer
never pastes, and Windows Terminal does not answer OSC 52 reads, so the built-in paste
would block for up to ten seconds.

**Reopened after a herdr restart.** Inside a herdr pane (`HERDR_PANE_ID` set), the wrapper
writes the launcher path and the absolute file paths to
`~/.local/state/mdv-restore/<server socket>/<pane id>`, and deletes that file only when nvim
exits cleanly (`q`). A stopped server or a closed terminal leaves it in place. The
`local.mdv-restore` herdr plugin (Step 20) runs once after each server start: for every
file whose pane still exists it types the mdv command into that pane's shell, with a
leading space so zsh's `hist_ignore_space` keeps it out of history; entries for panes
that are gone are deleted. Keying the folder by the server socket keeps named herdr
sessions from restoring into each other's panes. Not covered: `some-command | mdv` (no
file to reopen). Without the plugin, the state files are written but nothing reads them.

This replaces the first version, which reported `mdv <paths>` to herdr as the pane's
resume command through `herdr pane report-agent`. That reused herdr's own agent restore,
but herdr then listed every open mdv as an agent in the sidebar, and it rejected paths
containing an apostrophe. herdr has no way to keep a reported agent out of the sidebar.

**Reopened in the Herdr app.** Inside a Herdr app terminal (`HC_TERMINAL_ID` set), the
wrapper stores the same launcher path and files as a JSON array in the terminal's
`mdv-resume` label (`hc label`) and clears it on a clean quit. herdr-core keeps labels across
a reboot and gives a lost terminal a fresh shell with the same address; the `setup-zsh
herdr-app` block in `~/.zshrc` (`references/herdr-app.md`) finds the label there and types
the mdv command as the shell's first command. No plugin is involved.

## Keys

Also shown by `g?` inside mdv.

| Key                     | Action                                        |
| ----------------------- | --------------------------------------------- |
| `/`, `n`, `N`, Esc      | Search, next, previous, clear highlight       |
| mouse drag, then release | Copy the selection to the clipboard           |
| `v` / `V` then `y`      | Keyboard selection, copy                      |
| `q`                     | Quit                                          |
| `R`                     | Force reload from disk                        |
| `Ctrl-r`                | Toggle raw / rendered markdown                |
| `\t`                    | Toggle reflowed tables / raw source           |
| `\w`                    | Toggle line wrapping                          |
| `\c`                    | Next colour scheme (remembered)               |
| `gO`                    | Outline                                       |
| `gx`, double-click      | Open the link on this line                    |
| Tab / Shift-Tab         | Next / previous file when several were opened |

## Troubleshooting

- **Toast says copied, clipboard unchanged.** The terminal dropped the OSC 52 write.
  Windows Terminal and Herdr forward it. Inside tmux, `set -g set-clipboard on` is needed.
  iTerm2 needs "Applications in terminal may access clipboard" enabled in its preferences.
- **`mdv: neovim not found at ~/.local/bin/nvim`.** Redo the Neovim section of the step.
- **Live reload stopped.** You are in Visual mode or a search prompt; press Esc.
- **A table looks wrong.** `\t` shows the raw source; `R` forces a reload.
- **Errors about missing plugins at startup.** Re-run
  `NVIM_APPNAME=mdv ~/.local/bin/nvim --headless "+Lazy! restore" +qa`.
- **Colours unreadable on a light terminal.** `\c` cycles; `catppuccin-latte` is the light one.

## Updating

- **Neovim:** change `NVIM_VERSION` in the step. 0.10 is the floor (`vim.base64`,
  `vim.ui.clipboard.osc52`, `nvim_ui_send`).
- **Plugins:** `NVIM_APPNAME=mdv ~/.local/bin/nvim "+Lazy update"`, check the viewer still
  renders, then copy `~/.config/mdv/lazy-lock.json` back into `assets/mdv/`.

## Uninstall

```bash
rm -f ~/.local/bin/mdv
rm -rf ~/.config/mdv ~/.local/share/mdv ~/.local/state/mdv ~/.cache/mdv
```

If the mdv-restore plugin is linked, also:

```bash
herdr plugin unlink local.mdv-restore
rm -rf ~/.config/herdr-mdv-restore ~/.local/state/mdv-restore
```

If the step installed Neovim (a `~/.local/opt/nvim-*` directory exists), also:

```bash
rm -f ~/.local/bin/nvim
rm -rf ~/.local/opt/nvim-*
```

# mdv reference

Details for the mdv step that don't need to be in the main skill flow: what each file
does, how the clipboard path works, troubleshooting, updating the pinned versions, and
how to remove it.

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

If the step installed Neovim (a `~/.local/opt/nvim-*` directory exists), also:

```bash
rm -f ~/.local/bin/nvim
rm -rf ~/.local/opt/nvim-*
```

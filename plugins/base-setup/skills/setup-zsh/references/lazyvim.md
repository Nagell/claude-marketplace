# LazyVim reference

Details for the LazyVim step that don't need to be in the main skill flow: what each
file does, changing the theme, known quirks, and how to remove it.

## Files

| Installed path | Source | Purpose |
| --- | --- | --- |
| `~/.config/nvim/init.lua`, `lua/config/{lazy,options,autocmds}.lua` | LazyVim starter | Bootstraps lazy.nvim and LazyVim |
| `~/.config/nvim/lazyvim.json` | `assets/lazyvim/lazyvim.json` | Enabled extras (TypeScript, ESLint, Prettier, JSON, YAML, Markdown) |
| `~/.config/nvim/lazy-lock.json` | `assets/lazyvim/lazy-lock.json` | Plugin commits that `Lazy! restore` checks out |
| `~/.config/nvim/lua/config/keymaps.lua` | `assets/lazyvim/lua/config/keymaps.lua` | VS Code-style shortcuts |
| `~/.config/nvim/lua/plugins/colorscheme.lua` | `assets/lazyvim/lua/plugins/colorscheme.lua` | Catppuccin Mocha, transparent; One Dark themes for previewing |
| `~/.config/nvim/lua/plugins/explorer.lua` | `assets/lazyvim/lua/plugins/explorer.lua` | Tree shows all files; finder includes dotfiles |
| `~/.config/nvim/lua/plugins/markdownlint.lua` | `assets/lazyvim/lua/plugins/markdownlint.lua` | Passes `--config ~/.markdownlint-cli2.yaml` to lint and format |
| `~/.markdownlint-cli2.yaml` | `assets/lazyvim/markdownlint-cli2.yaml` | Line length 120, inline HTML allowed |
| `~/.local/share/nvim/lazy/` | `Lazy! restore` | Plugins |
| `~/.local/share/nvim/mason/` | Mason | Language servers, linters, formatters |
| `~/.local/share/nvim/site/parser/` | nvim-treesitter | Syntax parsers |

`install-wait.lua` is only a setup helper; it is not copied into the config.

## VS Code shortcuts

| Key | Action | Note |
| --- | --- | --- |
| `Ctrl+P` | Find file | Same picker as `<Space><Space>` |
| `Ctrl+B` | Toggle file tree | Mapped to `<Space>e`, so it follows whichever explorer LazyVim uses |
| `Ctrl+S` | Save | LazyVim default, not added by this skill |
| `Ctrl+/` | Toggle comment | Replaces LazyVim's `Ctrl+/` terminal toggle; use `<Space>ft`. Also bound to `Ctrl+_`, which many terminals send for `Ctrl+/` |

## Hidden files

Current LazyVim uses **neo-tree** for the file tree (`<Space>e`, `Ctrl+B`) and **fzf-lua**
for the file finder (`Ctrl+P`, `<Space><Space>`). Snacks has its own explorer and picker,
but LazyVim does not use them by default, so options set on `snacks.nvim` change nothing
here. `lua/plugins/explorer.lua` sets:

- neo-tree `hide_dotfiles = false` and `hide_gitignored = false` — the tree shows
  everything, like VS Code: dotfiles plus git-ignored files such as `.claude/`,
  `.mcp.json` or `node_modules` (dimmed by the git-status colours). With either left
  at its default, the tree ends in a `(N hidden items)` line instead.
- neo-tree `never_show = { ".git" }` — the repository internals stay out of the tree,
  as in VS Code, even when `H` turns filtering off.
- fzf-lua `files.hidden = true` — the finder searches dotfiles too, but still skips
  git-ignored files so `node_modules` doesn't flood the results.

Toggle for the session: `H` in the tree; `Alt+H` (dotfiles) and `Alt+I` (ignored) in
the finder.

## Colour scheme

`<Space>uC` previews every installed scheme live; the pick lasts for the session. To make
one permanent, change `colorscheme` in `lua/plugins/colorscheme.lua`:

- `catppuccin-mocha` (default), or another flavour: `macchiato`, `frappe`, `latte`
- `onedark` — navarasu/onedark.nvim, closest port of Atom One Dark; styles `dark`, `darker`, `cool`, `deep`, `warm`, `warmer`
- `onedark_vivid`, `onedark_dark` — olimorris/onedarkpro.nvim
- `tokyonight-*` — ships with LazyVim

Transparency is per theme. Catppuccin uses `transparent_background = true`; onedark.nvim
uses `transparent = true` and, because LazyVim applies the scheme before that plugin's
setup runs, also needs a `config` function that calls `require("onedark").setup(opts)`
and then `require("onedark").load()`.

The terminal decides how see-through the background is. On Windows Terminal that is
Settings → Defaults → Appearance → Background opacity (and acrylic), which applies to
every tab.

## Quirks

- **"Config Change Detected. Reloading…" but the colours don't change** — lazy.nvim
  reloads plugin specs, not the colour scheme. Run `:restart` (Neovim 0.12+) or reopen.
- **Language servers or parsers missing after setup** — a headless `+qa` exits while
  parsers compile and Mason downloads, aborting both; and LazyVim only starts Mason
  installs on the `VeryLazy` event, which never fires in `--headless` mode.
  `install-wait.lua` installs both explicitly and blocks until they finish. Interactively,
  `:Mason` shows package status and `:TSInstall <lang>` builds a parser.
- **A Mason package fails every time** — check `~/.local/state/nvim/mason.log`. The usual
  cause is a missing system tool: `stylua` ships as a zip and fails with
  `Could not find executable "unzip"` until `unzip` is installed.
- **Syntax highlighting missing, `tree-sitter` errors** — the parsers are compiled
  locally and need both a C compiler and the `tree-sitter` CLI.

## Updating

`:Lazy` → `U` updates plugins, then `:Lazy` → `L` shows the log. To refresh the pinned
versions shipped with the skill, copy `~/.config/nvim/lazy-lock.json` back into
`assets/lazyvim/lazy-lock.json` once the new versions have been tried.

## Uninstall

```bash
mv ~/.config/nvim ~/.config/nvim.removed
mv ~/.local/share/nvim ~/.local/share/nvim.removed
mv ~/.local/state/nvim ~/.local/state/nvim.removed
```

Delete the `.removed` directories once nothing is missed. mdv (`~/.config/mdv`,
`~/.local/share/mdv`) and `~/.local/bin/nvim` are separate and stay.

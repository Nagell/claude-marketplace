# LazyVim reference

Step 16 sends you here. **Install** below is the install procedure; the sections after it
are details that don't need to be in the main skill flow: what each file does, changing
the theme, known quirks, and how to remove it.

## Install

Run the subsections in order. An existing LazyVim config that only gains extras (Step 16)
runs just the two headless passes under **Install plugins, language servers and parsers**,
with `Lazy! install` instead of `Lazy! restore`, and can add `resume.lua` as described at the
end of **Install the config**.

### Neovim 0.11 or newer

Uses the same `~/.local/bin/nvim` as mdv. If Step 15 ran, it is already there. Otherwise follow the **Neovim 0.10 or newer** subsection of `references/mdv.md`, with one difference: LazyVim needs **0.11+**, so a system Neovim older than that is not good enough to link — install the pinned tarball instead.

```bash
~/.local/bin/nvim --version | head -1
```

### Tools LazyVim expects

`git`, a C compiler, `node` and `unzip` are required (Mason unpacks some tools, e.g. `stylua`, from zip files and fails without it); `rg` (ripgrep) powers text search, `fd` file search, `tree-sitter` builds syntax parsers, `lazygit` backs `<Space>gg`.

```bash
for c in git cc node unzip rg fd tree-sitter lazygit; do printf "%s: " $c; command -v $c >/dev/null && echo OK || echo MISSING; done
```

**If MACOS, or LINUX/WSL with linuxbrew available** — install whatever is missing:

```bash
brew install unzip ripgrep fd tree-sitter-cli lazygit
```

(`tree-sitter-cli` is the formula with the `tree-sitter` binary; plain `tree-sitter` is only the library.)

**If LINUX or WSL without brew:**

**IMPORTANT: Claude cannot run sudo commands.** Output the following and wait for confirmation:

```bash
# Please run these commands manually, then confirm when done:
sudo apt install -y build-essential unzip ripgrep fd-find
mkdir -p ~/.local/bin && ln -sf "$(command -v fdfind)" ~/.local/bin/fd
```

Then, without sudo: `npm install -g tree-sitter-cli`. lazygit is optional here; without it only `<Space>gg` does nothing.

If `node` is missing, point the user to Step 10 (NVM) or their Node install before continuing — the TypeScript, ESLint and Prettier tools are Node programs.

### Install the config

The LazyVim starter provides `init.lua` and the plugin bootstrap; this skill's `assets/lazyvim/` layers the choices on top (what each file does: **Files** below). Clone the starter into a temp directory so its `.git` never lands in `~/.config/nvim`:

```bash
TMP=$(mktemp -d)
git clone -q --depth 1 https://github.com/LazyVim/starter "$TMP/starter"
mkdir -p ~/.config/nvim
cp -r "$TMP/starter/init.lua" "$TMP/starter/lua" "$TMP/starter/stylua.toml" "$TMP/starter/.neoconf.json" ~/.config/nvim/

A=<this-skill-dir>/assets/lazyvim
cp "$A/lazyvim.json" "$A/lazy-lock.json" ~/.config/nvim/
cp "$A/lua/config/keymaps.lua" "$A/lua/config/options.lua" "$A/lua/config/resume.lua" ~/.config/nvim/lua/config/
cp "$A/lua/plugins/colorscheme.lua" "$A/lua/plugins/explorer.lua" "$A/lua/plugins/markdownlint.lua" "$A/lua/plugins/blink.lua" ~/.config/nvim/lua/plugins/
grep -q 'require("config.resume")' ~/.config/nvim/lua/config/autocmds.lua 2>/dev/null \
  || printf '\n-- Keep the herdr restart record in step with the open files (setup-zsh resume)\nrequire("config.resume")\n' >> ~/.config/nvim/lua/config/autocmds.lua
```

Leave `$TMP` for the OS to clean up.

`resume.lua` keeps the record of the `setup-zsh resume` zsh block (Step 20) in step with the files open in nvim, so a herdr server restart or Herdr app reboot reopens them, the current one first. It only acts when the zsh wrapper started nvim inside a herdr pane or Herdr app terminal; elsewhere, and for an nvim that git opens as an editor, it does nothing. An existing LazyVim config can get it the same way: copy `resume.lua` and append the `require` line.

`lazyvim.json` turns on the extras `lang.typescript`, `lang.vue`, `lang.python`, `linting.eslint`, `formatting.prettier`, `lang.json`, `lang.yaml` and `lang.markdown`; `lazy-lock.json` pins plugin commits known to work together.

### Markdown lint rules

markdownlint's defaults flag every line over 80 characters and every inline HTML tag, which is noisy for READMEs and PR descriptions that use `<details>`. Install the global rules (line length 120, inline HTML allowed). If `~/.markdownlint-cli2.yaml` already exists, show the user both files and ask before replacing it.

```bash
cp <this-skill-dir>/assets/lazyvim/markdownlint-cli2.yaml ~/.markdownlint-cli2.yaml
```

### Install plugins, language servers and parsers

Two headless passes. `Lazy! restore` checks out the pinned plugins. `install-wait.lua` then builds the syntax parsers and installs the language servers and formatters through Mason, blocking until both finish — a plain `+qa` quits mid-download and aborts them, and LazyVim only starts Mason installs on an event that never fires headless. A few minutes on first run.

```bash
cd ~ && ~/.local/bin/nvim --headless "+Lazy! restore" +qa 2>&1 | tail -1
~/.local/bin/nvim --headless -c "Lazy! load nvim-treesitter mason.nvim" -c "luafile <this-skill-dir>/assets/lazyvim/install-wait.lua" 2>&1 | tail -2
```

Expect `parsers: N installed` and `mason: all packages installed`. If it reports missing packages, show the user the matching `ERROR` lines from `~/.local/state/nvim/mason.log` (usually a missing tool such as `unzip`) rather than retrying blindly.

### Verify

Open a TypeScript file headless and check the theme, the language server and the shortcuts:

```bash
T=$(mktemp -d) && echo 'const x: number = 1' > "$T/t.ts" && cd "$T" && \
~/.local/bin/nvim --headless t.ts -c 'doautocmd User VeryLazy' -c 'sleep 15' \
  -c 'lua io.stdout:write("scheme=" .. vim.g.colors_name .. " bg=[" .. vim.fn.synIDattr(vim.fn.hlID("Normal"), "bg#") .. "] lsp=" .. table.concat(vim.tbl_map(function(c) return c.name end, vim.lsp.get_clients({ bufnr = 0 })), ",") .. " C-p=" .. vim.fn.maparg("<C-p>", "n", false, true).desc .. "\n")' \
  -c 'qa!' 2>&1 | tail -1
```

Expect `scheme=catppuccin-mocha bg=[] lsp=vtsls C-p=Find Files (VS Code)`. An empty `bg=[]` means the transparent background is active.

Check that the file tree really lists dotfiles — the option only helps if it lands on the explorer LazyVim actually uses (neo-tree in current LazyVim, not snacks):

```bash
cd <any git repo> && ~/.local/bin/nvim --headless -c 'doautocmd User VeryLazy' -c 'Neotree show' -c 'sleep 2' \
  -c 'lua for _, b in ipairs(vim.api.nvim_list_bufs()) do if vim.bo[b].filetype == "neo-tree" then for _, l in ipairs(vim.api.nvim_buf_get_lines(b, 0, -1, false)) do if l:match("%s%.%w") then io.stdout:write(vim.trim(l) .. "\n") end end end end' \
  -c 'qa!' 2>&1 | tail -5
```

Expect entries such as `.gitignore` or `.github`, and no `(N hidden items)` line.

Check that the Vue and Python language servers attach as well:

```bash
T=$(mktemp -d) && cd "$T" && echo '{}' > tsconfig.json && \
printf '<script setup lang="ts">\nconst x: number = 1\n</script>\n' > A.vue && printf 'import math\nmath.pi\n' > t.py && \
for f in A.vue t.py; do ~/.local/bin/nvim --headless "$f" -c 'doautocmd User VeryLazy' -c 'sleep 15' \
  -c 'lua io.stdout:write(vim.fn.expand("%") .. ": " .. table.concat(vim.tbl_map(function(c) return c.name end, vim.lsp.get_clients({ bufnr = 0 })), ",") .. "\n")' \
  -c 'qa!' 2>&1 | tail -1; done
```

Expect `A.vue: vue_ls,vtsls` and `t.py: pyright,ruff`. Completion items appear in the menu while typing (e.g. after `math.`). Enter accepts one. Tab does not, because LazyVim keeps Tab for jumping between snippet fields.

Then tell the user:

```
Neovim is set up (LazyVim). Run nvim in a project folder.
  Ctrl+P / Space Space   find file        Ctrl+B / Space e   file tree
  Ctrl+S                 save             Ctrl+/             comment line/selection
  Space /                search in files  gd / K             definition / type info
  Space ca               code actions     Space gg           lazygit
  Space ft               terminal         Space uC           preview colour schemes
  Shift+arrows           select           Ctrl+C / X / V     copy / cut / paste
  Ctrl+Z / Ctrl+Y        undo / redo      Ctrl+A             select all
  Ctrl+Q                 block selection (Ctrl+V pastes)
  Space (and wait)       menu of every key
After editing ~/.config/nvim, run :restart — lazy.nvim reloads plugin specs on change but not the colour scheme.
```

The transparent background only shows through if the terminal itself is translucent (Windows Terminal: Settings → Defaults → Appearance → Background opacity / acrylic).

## Files

| Installed path | Source | Purpose |
| --- | --- | --- |
| `~/.config/nvim/init.lua`, `lua/config/{lazy,autocmds}.lua` | LazyVim starter | Bootstraps lazy.nvim and LazyVim |
| `~/.config/nvim/lazyvim.json` | `assets/lazyvim/lazyvim.json` | Enabled extras (TypeScript, Vue, Python, ESLint, Prettier, JSON, YAML, Markdown) |
| `~/.config/nvim/lazy-lock.json` | `assets/lazyvim/lazy-lock.json` | Plugin commits that `Lazy! restore` checks out |
| `~/.config/nvim/lua/config/keymaps.lua` | `assets/lazyvim/lua/config/keymaps.lua` | VS Code- and Windows-style shortcuts |
| `~/.config/nvim/lua/config/options.lua` | `assets/lazyvim/lua/config/options.lua` | Windows-style selection (`keymodel`, `selectmode`); replaces the starter's copy |
| `~/.config/nvim/lua/config/resume.lua` | `assets/lazyvim/lua/config/resume.lua` | Keeps the herdr restart record in step with the open files; loaded by a `require` line appended to `autocmds.lua` |
| `~/.config/nvim/lua/plugins/colorscheme.lua` | `assets/lazyvim/lua/plugins/colorscheme.lua` | Catppuccin Mocha, transparent; One Dark themes for previewing |
| `~/.config/nvim/lua/plugins/explorer.lua` | `assets/lazyvim/lua/plugins/explorer.lua` | Tree shows all files; finder includes dotfiles |
| `~/.config/nvim/lua/plugins/markdownlint.lua` | `assets/lazyvim/lua/plugins/markdownlint.lua` | Passes `--config ~/.markdownlint-cli2.yaml` to lint and format |
| `~/.config/nvim/lua/plugins/blink.lua` | `assets/lazyvim/lua/plugins/blink.lua` | Drops blink.cmp's `Ctrl+Y` accept so `Ctrl+Y` redoes in Insert mode |
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

## Windows-style editing

`options.lua` sets `keymodel=startsel,stopsel` and `selectmode=key`: Shift (+Ctrl) +
arrows/Home/End start a selection in Select mode, a plain arrow ends it, and typing
replaces the selected text. `keymaps.lua` adds the clipboard and undo keys on top.

| Key | Action | Replaces Vim's |
| --- | --- | --- |
| `Shift`(+`Ctrl`)+arrows, `Shift+Home/End` | Select | Shift+arrow word/page motions |
| `Ctrl+Left/Right` (also `Alt+B/F`, which Ghostty sends for them) | Jump by word, ending any selection | — |
| `Ctrl+C` (selection) | Copy to the system clipboard; the selection and mode stay, so a selection made from Insert mode returns there | — |
| `Ctrl+X` (selection) | Cut to the system clipboard | `Ctrl+X` decrement number |
| `Ctrl+V` | Paste (Normal, Insert; over a selection). Typing over a selection leaves the clipboard alone, so it still pastes the last copy | `Ctrl+V` block selection — use `Ctrl+Q` |
| `Backspace` (selection) | Delete the selection without copying it | — |
| `Ctrl+A` | Select all in Select mode (typing replaces it); from Insert mode, ending the selection returns to Insert | `Ctrl+A` increment number |
| `Ctrl+Z` | Undo (Normal, Insert) | `Ctrl+Z` suspend |
| `Ctrl+Y` | Redo (Normal, Insert) | `Ctrl+Y` scroll one line; blink.cmp's `Ctrl+Y` accept (Enter still accepts) |

### Clipboard on WSL

WSL usually has no clipboard tool Neovim detects (win32yank, xclip, wl-paste), so Neovim
falls back to OSC 52. Windows Terminal honours OSC 52 writes but ignores reads, so `Ctrl+V`
would paste Neovim's own last yank instead of the Windows clipboard. `options.lua`
therefore sets `vim.g.clipboard` on WSL: copy stays on OSC 52 (Unicode-safe), paste runs
`powershell.exe Get-Clipboard` with UTF-8 output. Each paste costs about 0.35 s for
PowerShell to start. `Ctrl+Shift+V` (Windows Terminal's own paste) bypasses all of this.

Check it: `:lua print(vim.fn["provider#clipboard#Executable"]())` should print
`wsl-osc52-powershell`.

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

-- mdv: Neovim as a live Markdown viewer.
-- Isolated from any real Neovim config via NVIM_APPNAME=mdv.
-- Fixes glow's gaps: in-document search, reload that keeps your place, mouse.
--
-- Keys: /  search      \w  wrap on/off     \c  next colour scheme
--       q  quit        R   reload          <C-r>  raw <-> rendered
--       \t reflowed tables <-> raw source   g?  this list
--       gO outline     Tab / S-Tab  next / prev file
--       mouse-select or y  copy to the Windows clipboard

local o = vim.opt

-- Reading UX -----------------------------------------------------------------
o.mouse = 'a' -- wheel scroll, click to position, drag to select
o.mousescroll = 'ver:3,hor:4' -- shift+wheel scrolls tables sideways
o.wrap = true -- safe: tables are reflowed to fit the window, so they never wrap
o.linebreak = true -- break prose at word boundaries, not mid-word
o.breakindent = true
o.sidescroll = 4
o.sidescrolloff = 0
o.number = false
o.signcolumn = 'no'
o.cursorline = true
o.scrolloff = 3
o.showmode = false
o.swapfile = false
o.writebackup = false
o.termguicolors = true

-- Search ---------------------------------------------------------------------
o.ignorecase = true
o.smartcase = true
o.incsearch = true
o.hlsearch = true

-- Clipboard ------------------------------------------------------------------
-- Copies leave as OSC 52, which Herdr and Windows Terminal both forward to the
-- Windows clipboard; clip.exe mangles non-ASCII text. A viewer never pastes and
-- Windows Terminal does not answer OSC 52 reads, so paste hands back the last
-- copy instead of waiting ten seconds on the terminal.
local osc52 = require('vim.ui.clipboard.osc52')
local last_copy = { {}, 'v' }

local function clipboard_copy(reg)
  local send = osc52.copy(reg)
  return function(lines, regtype)
    last_copy = { lines, regtype }
    send(lines)
  end
end

local function clipboard_paste()
  return last_copy
end

vim.g.clipboard = {
  name = 'osc52',
  copy = { ['+'] = clipboard_copy('+'), ['*'] = clipboard_copy('*') },
  paste = { ['+'] = clipboard_paste, ['*'] = clipboard_paste },
}
o.clipboard = 'unnamedplus'

-- Live reload that preserves the viewport ------------------------------------
-- autoread + a 1s checktime poll; the saved view is restored after each reload,
-- so the file updating under you does not throw you back to the top.
o.autoread = true
o.updatetime = 250

local saved_view = nil

vim.api.nvim_create_autocmd({ 'CursorMoved', 'BufEnter', 'WinScrolled' }, {
  callback = function()
    if vim.bo.buftype == '' then
      saved_view = vim.fn.winsaveview()
    end
  end,
})

vim.api.nvim_create_autocmd('FileChangedShellPost', {
  callback = function()
    if saved_view then
      vim.schedule(function()
        pcall(vim.fn.winrestview, saved_view)
      end)
    end
  end,
})

--- Capture the viewport, then ask Neovim to notice changes on disk. Capturing
--- here (rather than only on cursor movement) means the restore after a reload
--- always uses the position the file actually changed at.
local function check_file()
  if vim.bo.buftype == '' then
    saved_view = vim.fn.winsaveview()
    vim.cmd('silent! checktime')
  end
end

vim.api.nvim_create_autocmd({ 'FocusGained', 'BufEnter', 'TermLeave' }, {
  callback = check_file,
})

local mdview = require('mdview')

local timer = vim.uv.new_timer()
timer:start(1000, 1000, vim.schedule_wrap(function()
  if vim.fn.mode() ~= 'n' then
    return
  end
  if vim.bo.buftype == '' then
    check_file()
  else
    mdview.refresh(false)
  end
end))

-- reflowed view of the file given on the command line
vim.api.nvim_create_autocmd('VimEnter', { callback = mdview.start })
-- column widths follow the window
vim.api.nvim_create_autocmd('VimResized', {
  callback = function()
    mdview.refresh(true)
  end,
})

-- Treesitter highlighting (markdown parsers ship with Neovim 0.10+) -----------
vim.api.nvim_create_autocmd('FileType', {
  pattern = 'markdown',
  callback = function(args)
    pcall(vim.treesitter.start, args.buf)
  end,
})

-- Keys -----------------------------------------------------------------------
vim.g.mapleader = '\\'

vim.keymap.set('n', 'q', '<cmd>quitall!<cr>', { desc = 'quit' })
vim.keymap.set('n', '<Esc>', '<cmd>nohlsearch<cr>', { desc = 'clear search highlight' })
vim.keymap.set('n', 'R', '<cmd>edit!<cr>', { desc = 'force reload from disk' })
vim.keymap.set('n', '<C-r>', '<cmd>RenderMarkdown toggle<cr>', { desc = 'toggle raw/rendered' })
-- cycle files when several were opened at once (e.g. `mdv dir/*.md`)
vim.keymap.set('n', '<Tab>', function()
  mdview.cycle(1)
end, { desc = 'next file' })
vim.keymap.set('n', '<S-Tab>', function()
  mdview.cycle(-1)
end, { desc = 'previous file' })

vim.keymap.set('n', '<leader>t', mdview.toggle, { desc = 'toggle reflowed tables / raw source' })
vim.keymap.set('n', 'gx', mdview.open, { desc = 'open link on this line' })
vim.keymap.set('n', '<2-LeftMouse>', mdview.open, { desc = 'open link under the pointer' })

-- Herdr copies a mouse selection the moment the button is released and says so;
-- match it. The selection is not kept: the reload timer only follows the file
-- from Normal mode, and a lingering highlight would silently freeze the view.
vim.keymap.set('x', '<LeftRelease>', function()
  vim.cmd('normal! "+y')
  local n = vim.fn.line("'>") - vim.fn.line("'<") + 1
  vim.notify(('copied %d line%s to clipboard'):format(n, n == 1 and '' or 's'))
end, { desc = 'copy the mouse selection to the clipboard' })

vim.keymap.set('n', '<leader>w', function()
  vim.wo.wrap = not vim.wo.wrap
  vim.notify('wrap ' .. (vim.wo.wrap and 'on' or 'off'))
end, { desc = 'toggle line wrapping' })

vim.keymap.set('n', 'g?', function()
  vim.notify(table.concat({
    '/ search   n/N next/prev   Esc clear highlight',
    'q quit     R reload        <C-r> raw/rendered',
    'gO outline Tab/S-Tab file  \\w wrap   \\c colours',
    '\\t reflowed tables <-> raw source',
    'gx or double-click  open the link on this line',
    'mouse selection or y  copy to the Windows clipboard',
  }, '\n'))
end, { desc = 'key help' })

-- Plugins --------------------------------------------------------------------
local lazypath = vim.fn.stdpath('data') .. '/lazy/lazy.nvim'
if not vim.uv.fs_stat(lazypath) then
  vim.fn.system({
    'git', 'clone', '--filter=blob:none', '--branch=stable',
    'https://github.com/folke/lazy.nvim.git', lazypath,
  })
end
o.rtp:prepend(lazypath)

require('lazy').setup({
  {
    'catppuccin/nvim',
    name = 'catppuccin',
    lazy = false,
    priority = 1000,
    opts = {
      flavour = 'mocha',
      integrations = { render_markdown = true, treesitter = true },
    },
  },
  { 'folke/tokyonight.nvim', lazy = false, priority = 900 },
  { 'rose-pine/neovim', name = 'rose-pine', lazy = false, priority = 900 },
  {
    'MeanderingProgrammer/render-markdown.nvim',
    ft = { 'markdown' },
    opts = {
      file_types = { 'markdown' },
      completions = { lsp = { enabled = false }, blink = { enabled = false } },
      sign = { enabled = false },
      heading = {
        sign = false,
        position = 'inline',
        width = { 'full', 'full', 'block', 'block', 'block', 'block' },
        min_width = 40,
        right_pad = 2,
        border = { true, true, false, false, false, false },
        border_virtual = true,
      },
      code = {
        width = 'block',
        min_width = 45,
        right_pad = 2,
        border = 'thin',
        inline_pad = 1,
      },
      -- tables: box-drawing borders, columns padded to equal width
      pipe_table = {
        preset = 'round',
        cell = 'padded',
        border_virtual = true,
      },
      dash = { width = 60 },
      bullet = { icons = { '●', '○', '◆', '◇' } },
      -- the reflowed view puts every table in a code fence; its background must
      -- stop exactly at the table edge, since padding past a full-width line
      -- would push it into a wrap
      overrides = {
        buftype = {
          nofile = {
            code = { width = 'block', left_pad = 0, right_pad = 0, min_width = 0 },
          },
        },
      },
    },
  },
}, {
  install = { colorscheme = { 'catppuccin-mocha' } },
  change_detection = { enabled = false },
  ui = { border = 'rounded' },
})

-- Colour scheme --------------------------------------------------------------
-- \c cycles; the choice is remembered in ~/.config/mdv/colorscheme.txt
local schemes = { 'catppuccin-mocha', 'tokyonight-night', 'rose-pine-moon', 'catppuccin-latte' }
local scheme_file = vim.fn.stdpath('config') .. '/colorscheme.txt'
local current = schemes[1]

if vim.uv.fs_stat(scheme_file) then
  local saved = (vim.fn.readfile(scheme_file)[1] or ''):gsub('%s', '')
  if vim.tbl_contains(schemes, saved) then
    current = saved
  end
end

local function apply(name)
  local ok = pcall(vim.cmd.colorscheme, name)
  if ok then
    current = name
  end
  return ok
end

--- Colours used for link labels and code spans inside reflowed table cells.
--- Re-derived on every colour scheme change so \c keeps them in step.
local function define_markup_highlights()
  local link = vim.api.nvim_get_hl(0, { name = '@markup.link.label.markdown', link = false })
  vim.api.nvim_set_hl(0, 'MdvLink', { fg = link.fg, underline = true })
  vim.api.nvim_set_hl(0, 'MdvCode', { link = 'RenderMarkdownCodeInline' })
end

vim.api.nvim_create_autocmd('ColorScheme', { callback = define_markup_highlights })

apply(current)
define_markup_highlights()

vim.keymap.set('n', '<leader>c', function()
  local index = 1
  for i, name in ipairs(schemes) do
    if name == current then
      index = i
    end
  end
  local next_scheme = schemes[(index % #schemes) + 1]
  if apply(next_scheme) then
    vim.fn.writefile({ next_scheme }, scheme_file)
    vim.notify('colour scheme: ' .. next_scheme)
  end
end, { desc = 'cycle colour scheme' })

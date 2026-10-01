-- Options are automatically loaded before lazy.nvim startup
-- Default options that are always set: https://github.com/LazyVim/LazyVim/blob/main/lua/lazyvim/config/options.lua
-- Add any additional options here

-- Windows-style selection: Shift (+Ctrl) + arrows/Home/End select, a plain arrow ends the
-- selection, and typing replaces it (Select mode instead of Visual mode).
vim.opt.keymodel = { "startsel", "stopsel" }
vim.opt.selectmode = { "key" }

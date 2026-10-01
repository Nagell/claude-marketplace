-- Options are automatically loaded before lazy.nvim startup
-- Default options that are always set: https://github.com/LazyVim/LazyVim/blob/main/lua/lazyvim/config/options.lua
-- Add any additional options here

-- Windows-style selection: Shift (+Ctrl) + arrows/Home/End select, a plain arrow ends the
-- selection, and typing replaces it (Select mode instead of Visual mode).
vim.opt.keymodel = { "startsel", "stopsel" }
vim.opt.selectmode = { "key" }

-- WSL: with no clipboard tool installed Neovim falls back to OSC 52, but Windows Terminal
-- ignores OSC 52 read requests, so paste returned Neovim's own last yank instead of the
-- Windows clipboard. Copy stays on OSC 52 (Unicode-safe); paste asks PowerShell, forcing
-- UTF-8 output so non-ASCII text survives.
if vim.fn.has("wsl") == 1 then
  local osc52 = require("vim.ui.clipboard.osc52")
  local paste = {
    "powershell.exe", "-NoLogo", "-NoProfile", "-Command",
    '[Console]::OutputEncoding = [Text.Encoding]::UTF8; [Console]::Out.Write(([string](Get-Clipboard -Raw)) -replace "`r", "")',
  }
  vim.g.clipboard = {
    name = "wsl-osc52-powershell",
    copy = { ["+"] = osc52.copy("+"), ["*"] = osc52.copy("*") },
    paste = { ["+"] = paste, ["*"] = paste },
    cache_enabled = 0,
  }
end

-- Keymaps are automatically loaded on the VeryLazy event
-- Default keymaps that are always set: https://github.com/LazyVim/LazyVim/blob/main/lua/lazyvim/config/keymaps.lua
-- Add any additional keymaps here

-- VS Code-style shortcuts (LazyVim already maps Ctrl+S to save)
local map = vim.keymap.set
map("n", "<C-p>", LazyVim.pick("files"), { desc = "Find Files (VS Code)" })
map("n", "<C-b>", "<leader>e", { remap = true, desc = "Toggle File Explorer (VS Code)" })
-- Ctrl+/ toggles a comment; many terminals send Ctrl+/ as Ctrl+_.
-- This replaces LazyVim's Ctrl+/ terminal toggle — use <leader>ft for the terminal.
for _, key in ipairs({ "<C-/>", "<C-_>" }) do
  map("n", key, "gcc", { remap = true, desc = "Toggle Comment (VS Code)" })
  map("x", key, "gc", { remap = true, desc = "Toggle Comment (VS Code)" })
end

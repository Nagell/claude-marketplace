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

-- Windows-style editing; selecting with Shift+arrows comes from keymodel/selectmode in options.lua.
-- These replace Vim's Ctrl+V block selection (use Ctrl+Q), Ctrl+A/X number increment/decrement,
-- Ctrl+Y scroll and Ctrl+Z suspend.
map("v", "<C-c>", '"+y', { desc = "Copy (Windows)" })
map("v", "<C-x>", '"+d', { desc = "Cut (Windows)" })
map("v", "<C-v>", '"+P', { desc = "Paste over selection (Windows)" })
map("v", "<BS>", '"_d', { desc = "Delete selection (Windows)" })
map("i", "<C-v>", "<C-r><C-o>+", { desc = "Paste (Windows)" })
map("n", "<C-v>", '"+P', { desc = "Paste (Windows)" })
map({ "n", "v" }, "<C-a>", "<Esc>ggVG", { desc = "Select All (Windows)" })
map("i", "<C-a>", "<Esc>ggVG", { desc = "Select All (Windows)" })
map("n", "<C-z>", "u", { desc = "Undo (Windows)" })
map("i", "<C-z>", "<C-o>u", { desc = "Undo (Windows)" })
map("n", "<C-y>", "<C-r>", { desc = "Redo (Windows)" })
map("i", "<C-y>", "<C-o><C-r>", { desc = "Redo (Windows)" })
-- Ctrl+Left/Right jump by word without selecting. Ghostty sends them as Esc b / Esc f
-- (Alt+B/F), other terminals as <C-Left>/<C-Right>; in a selection the jump ends it.
for _, keys in ipairs({ { "<C-Left>", "<M-b>", "b" }, { "<C-Right>", "<M-f>", "w" } }) do
  for _, key in ipairs({ keys[1], keys[2] }) do
    map("n", key, keys[3], { desc = "Word jump (Windows)" })
    map("i", key, "<C-o>" .. keys[3], { desc = "Word jump (Windows)" })
    map("v", key, "<Esc>" .. keys[3], { desc = "Word jump (Windows)" })
  end
end

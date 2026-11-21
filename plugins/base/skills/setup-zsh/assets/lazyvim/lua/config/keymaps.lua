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
-- Copy without leaving the selection or its mode, like VS Code: a selection made from Insert
-- mode stays "(insert) SELECT", so the next arrow or keystroke continues in Insert mode.
-- ("+y would end the selection and, after Ctrl+A, drop into Normal mode.)
local regtype = { v = "c", V = "l", ["\22"] = "b" }
map("v", "<C-c>", function()
  local mode = ({ s = "v", S = "V", ["\19"] = "\22" })[vim.fn.mode()] or vim.fn.mode()
  local lines = vim.fn.getregion(vim.fn.getpos("v"), vim.fn.getpos("."), { type = mode })
  vim.fn.setreg("+", lines, regtype[mode])
end, { desc = "Copy (Windows)" })
map("v", "<C-x>", '"+d', { desc = "Cut (Windows)" })
map("v", "<C-v>", '"+P', { desc = "Paste over selection (Windows)" })
map("v", "<BS>", '"_d', { desc = "Delete selection (Windows)" })
-- Typing over a Select-mode selection deletes it into the unnamed register, which
-- clipboard=unnamedplus mirrors to the system clipboard, so the next Ctrl+V pasted the replaced
-- text. Detach the clipboard while Select mode is active; the Ctrl+C/X/V maps name "+ directly.
vim.api.nvim_create_autocmd("ModeChanged", {
  pattern = "*:[sS\19]",
  callback = function()
    if vim.o.clipboard == "" then return end
    local saved = vim.o.clipboard
    vim.o.clipboard = ""
    vim.api.nvim_create_autocmd("ModeChanged", {
      pattern = "[sS\19]:*",
      once = true,
      -- Scheduled: the replace deletes after the mode switch, and must not reach the clipboard.
      callback = vim.schedule_wrap(function() vim.o.clipboard = saved end),
    })
  end,
})
map("i", "<C-v>", "<C-r><C-o>+", { desc = "Paste (Windows)" })
map("n", "<C-v>", '"+P', { desc = "Paste (Windows)" })
-- Select all in Select mode (typing replaces it). From Insert mode, <C-o> keeps the
-- "(insert)" flag, so ending the selection returns to Insert mode instead of Normal.
map("n", "<C-a>", "ggVG<C-g>", { desc = "Select All (Windows)" })
map("v", "<C-a>", "<C-\\><C-n>ggVG<C-g>", { desc = "Select All (Windows)" })
map("i", "<C-a>", "<C-o>gg<C-o>VG<C-g>", { desc = "Select All (Windows)" })
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

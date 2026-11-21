-- LazyVim maps Ctrl+Y in blink.cmp to "select and accept", a buffer-local Insert-mode map that
-- shadows the Windows-style Ctrl+Y redo from keymaps.lua. Enter still accepts a completion.
return {
  "saghen/blink.cmp",
  opts = {
    keymap = {
      ["<C-y>"] = false,
    },
  },
}

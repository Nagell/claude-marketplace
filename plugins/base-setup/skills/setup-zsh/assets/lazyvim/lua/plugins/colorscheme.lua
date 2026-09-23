-- Catppuccin Mocha (same as mdv), with a transparent background so
-- Windows Terminal's opacity/acrylic shows through.
-- Preview other themes live with <Space>uC.
return {
  {
    "catppuccin/nvim",
    name = "catppuccin",
    priority = 1000,
    opts = {
      flavour = "mocha", -- latte | frappe | macchiato | mocha
      transparent_background = true,
    },
  },
  -- Kept for previewing with <Space>uC
  { "navarasu/onedark.nvim", lazy = true },
  { "olimorris/onedarkpro.nvim", lazy = true },
  { "LazyVim/LazyVim", opts = { colorscheme = "catppuccin-mocha" } },
}

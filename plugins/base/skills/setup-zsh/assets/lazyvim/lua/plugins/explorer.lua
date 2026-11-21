-- File tree (neo-tree, <Space>e / Ctrl+B): show everything, like VS Code —
-- dotfiles and git-ignored files (.claude/, .mcp.json, node_modules), the
-- ignored ones dimmed by git status — except .git itself. H toggles filtering.
-- File finder (fzf-lua, Ctrl+P): include dotfiles, but still skip git-ignored
-- files so node_modules doesn't flood results. Alt+H / Alt+I toggle.
return {
  {
    "nvim-neo-tree/neo-tree.nvim",
    opts = {
      filesystem = {
        filtered_items = {
          hide_dotfiles = false,
          hide_gitignored = false,
          never_show = { ".git" }, -- hidden even when H toggles filtering off
        },
      },
    },
  },
  {
    "ibhagwan/fzf-lua",
    opts = { files = { hidden = true } },
  },
}

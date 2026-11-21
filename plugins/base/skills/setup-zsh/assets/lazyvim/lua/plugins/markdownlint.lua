-- Point markdownlint-cli2 at the global ~/.markdownlint-cli2.yaml
-- (line length 120, inline HTML allowed) for both linting and formatting.
local config = vim.fn.expand("~/.markdownlint-cli2.yaml")

return {
  {
    "mfussenegger/nvim-lint",
    opts = {
      linters = {
        ["markdownlint-cli2"] = { args = { "--config", config, "-" } },
      },
    },
  },
  {
    "stevearc/conform.nvim",
    opts = {
      formatters = {
        ["markdownlint-cli2"] = { prepend_args = { "--config", config } },
      },
    },
  },
}

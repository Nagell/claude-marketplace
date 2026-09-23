-- Headless helper for the setup-zsh LazyVim step. A plain `nvim --headless +qa`
-- exits while parsers compile and Mason downloads, aborting both, and LazyVim
-- only starts Mason installs on the VeryLazy event, which never fires headless.
-- This installs both explicitly and blocks until they finish.
-- Run: nvim --headless -c "Lazy! load nvim-treesitter mason.nvim" -c "luafile install-wait.lua"

local out = function(msg) io.stdout:write(msg .. "\n") end

-- 1. Syntax parsers LazyVim and its extras ask for
local parsers = LazyVim.opts("nvim-treesitter").ensure_installed or {}
local ok = pcall(function() require("nvim-treesitter").install(parsers):wait(600000) end)
out(ok and ("parsers: " .. #parsers .. " installed") or "parsers: timed out or failed")

-- 2. Mason packages the extras need; each attempted once, failures reported
local registry = require("mason-registry")
local packages = {
  "vtsls", "eslint-lsp", "json-lsp", "yaml-language-server", "marksman",
  "lua-language-server", "stylua", "prettier", "markdownlint-cli2", "markdown-toc", "shfmt",
}

registry.refresh(function()
  local pending, failed = 0, {}
  for _, name in ipairs(packages) do
    local pkg = registry.get_package(name)
    if not pkg:is_installed() and not pkg:is_installing() then
      pending = pending + 1
      pkg:install({}, function(success)
        pending = pending - 1
        if not success then table.insert(failed, name) end
      end)
    end
  end

  local function busy()
    if pending > 0 then return true end
    for _, name in ipairs(packages) do
      if registry.get_package(name):is_installing() then return true end
    end
    return false
  end

  vim.wait(600000, function() return not busy() end, 1000)
  local missing = vim.tbl_filter(function(n) return not registry.get_package(n):is_installed() end, packages)
  out(#missing == 0 and "mason: all packages installed"
    or ("mason: missing " .. table.concat(missing, ", ") .. " — see :MasonLog"))
  vim.cmd("qa!")
end)

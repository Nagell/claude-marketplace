-- Keep the restart record of the `setup-zsh resume` zsh block in step with the files open in
-- this nvim, so a herdr server restart or Herdr app reboot reopens them, not just whatever
-- was on the command line. The record is {cwd, argv}, argv = { "nvim", <current file>, <other
-- files> }: a Herdr app terminal label (HC_TERMINAL_ID) or a herdr pane file (HERDR_PANE_ID).
-- Only when the zsh wrapper started this nvim (SETUP_ZSH_RESUME, parent zsh) or herdr started
-- it straight as a terminal's own program (an agent's `pane.split --argv '["nvim", ...]'` in the
-- Herdr app, or `exec nvim ...` in a herdr pane): an nvim that git, crontab or lazygit opens as an
-- editor must not come back. The parent check runs even with SETUP_ZSH_RESUME set, because the
-- wrapped program's children inherit that variable.
if not (vim.env.HC_TERMINAL_ID or vim.env.HERDR_PANE_ID) then
  return
end
-- The editor runs as `nvim --embed` under nvim's own UI process; its parent is the real one.
local function parent_of(pid)
  local ps = vim.system({ "ps", "-o", "ppid=,comm=", "-p", tostring(pid) }):wait()
  local ppid = (ps.stdout or ""):match("%d+")
  if not ppid then
    return nil, nil
  end
  local name = vim.system({ "ps", "-o", "comm=", "-p", ppid }):wait()
  return tonumber(ppid), vim.trim(name.stdout or ""):match("[^/]+$") -- macOS prints the full path
end
-- pcall: vim.system throws when `ps` is missing, which means "don't record", never an error.
local ok, ppid, parent = pcall(parent_of, vim.uv.os_getpid())
if ok and parent == "nvim" then
  ok, ppid, parent = pcall(parent_of, ppid)
end
local wrapped = vim.env.SETUP_ZSH_RESUME == "1" and (parent == "zsh" or parent == "-zsh")
if not ok or not (wrapped or parent == "herdr-core" or parent == "herdr") then
  return
end

local last

local function record()
  local current = vim.api.nvim_get_current_buf()
  local files = {}
  for _, buf in ipairs(vim.api.nvim_list_bufs()) do
    local name = vim.api.nvim_buf_get_name(buf)
    if vim.bo[buf].buflisted and vim.bo[buf].buftype == "" and name ~= "" and vim.uv.fs_stat(name) then
      table.insert(files, buf == current and 1 or #files + 1, name)
    end
  end
  local json = vim.json.encode({ cwd = vim.fn.getcwd(), argv = vim.list_extend({ "nvim" }, files) })
  if json == last then
    return
  end
  last = json

  if vim.env.HC_TERMINAL_ID then
    vim.system({ "hc", "label", vim.env.HC_TERMINAL_ID, "cmd-resume=" .. json })
  else
    local state = vim.env.XDG_STATE_HOME or (vim.env.HOME .. "/.local/state")
    local dir = state .. "/mdv-restore/" .. (vim.env.HERDR_SOCKET_PATH or ""):gsub("[^%w._-]", "_")
    vim.fn.mkdir(dir, "p")
    vim.fn.writefile({ json }, dir .. "/" .. vim.env.HERDR_PANE_ID:gsub("/", "_"))
  end
end

vim.api.nvim_create_autocmd({ "BufEnter", "BufDelete", "DirChanged" }, {
  group = vim.api.nvim_create_augroup("setup_zsh_resume", { clear = true }),
  -- Scheduled: during BufDelete the buffer is still listed.
  callback = function()
    vim.schedule(function()
      pcall(record) -- best effort: a missing `hc` or an unwritable state dir records nothing
    end)
  end,
})
-- LazyVim loads autocmds.lua only after startup (VeryLazy), when the files given on the
-- command line or opened by -c are already in their buffers: record them once now.
vim.schedule(function()
  pcall(record)
end)

--- Scratch-buffer view of a markdown file with tables reflowed to the window.
---
--- The file itself is never modified: the reflowed text lives in a `nofile`
--- buffer that is rebuilt whenever the file changes on disk or the window is
--- resized, with the scroll position restored each time.

local reflow = require('mdreflow')

local M = { enabled = true }

local NS = vim.api.nvim_create_namespace('mdv_reflow')
local views = {} -- path -> buffer number
local sources = {} -- buffer number -> path
local stamps = {} -- path -> "mtime:size"
local origins = {} -- buffer number -> output line -> source line
local raw_lines = {} -- buffer number -> source file lines

---@param path string
---@return string|nil
local function stamp(path)
  local s = vim.uv.fs_stat(path)
  if not s then
    return nil
  end
  return ('%d.%d:%d'):format(s.mtime.sec, s.mtime.nsec, s.size)
end

---@param path string
---@return integer
local function scratch(path)
  local buf = vim.api.nvim_create_buf(false, true)
  vim.bo[buf].buftype = 'nofile'
  vim.bo[buf].bufhidden = 'hide'
  vim.bo[buf].swapfile = false
  pcall(vim.api.nvim_buf_set_name, buf, 'mdv://' .. vim.fn.fnamemodify(path, ':t'))
  return buf
end

--- Highlight every occurrence of `needle` in a rendered line.
---@return boolean found
local function paint(buf, lnum, text, needle, hl)
  local from, found = 1, false
  while true do
    local first, last = text:find(needle, from, true)
    if not first then
      return found
    end
    vim.api.nvim_buf_set_extmark(buf, NS, lnum - 1, first - 1, {
      end_col = last,
      hl_group = hl,
      priority = 120,
    })
    from, found = last + 1, true
  end
end

--- Colour the link labels and code spans inside reflowed table cells.
---
--- The markup characters are gone from the text, so the spans are located by
--- matching the label and code text of the source line. Highlighting is pure
--- colour -- no conceal, no virtual text -- so the borders stay put.
---@param buf integer
---@param rendered string[]
---@param origin integer[]
---@param lines string[] source file lines
local function colour_markup(buf, rendered, origin, lines)
  local cache = {}
  for lnum, text in ipairs(rendered) do
    -- a quoted table starts with its `> ` prefix, so look for the border anywhere
    if text:find('│', 1, true) then
      local index = origin[lnum]
      local spans = cache[index]
      if spans == nil then
        spans = reflow.markup(lines[index] or '')
        cache[index] = spans
      end
      for _, span in ipairs(spans) do
        if not paint(buf, lnum, text, span.text, span.hl) then
          -- the span was wrapped across lines, so colour its identifier-like
          -- words instead. Plain words are skipped: colouring every "settings"
          -- in a row because one cell mentioned `settings` is worse than
          -- colouring nothing.
          for word in span.text:gmatch('%S+') do
            if #word >= 5 and word:match('[%._/%(%)>#-]') then
              paint(buf, lnum, text, word, span.hl)
            end
          end
        end
      end
    end
  end
end

--- Rebuild the reflowed contents of `buf` from `path`.
---@param path string
---@param buf integer
local function fill(path, buf)
  local ok, lines = pcall(vim.fn.readfile, path)
  if not ok then
    return
  end
  local width = vim.api.nvim_win_get_width(0) - 1
  local rendered, headers, origin = reflow.transform(lines, width)
  origins[buf], raw_lines[buf] = origin, lines

  -- replace only the lines that actually changed: rewriting the whole buffer
  -- makes treesitter reparse the entire document on every keystroke upstream
  local old = vim.api.nvim_buf_get_lines(buf, 0, -1, false)
  local first = 1
  while first <= #old and first <= #rendered and old[first] == rendered[first] do
    first = first + 1
  end
  local last_old, last_new = #old, #rendered
  while last_old >= first and last_new >= first and old[last_old] == rendered[last_new] do
    last_old, last_new = last_old - 1, last_new - 1
  end

  vim.bo[buf].modifiable = true
  if first <= #old or first <= #rendered then
    vim.api.nvim_buf_set_lines(buf, first - 1, last_old, false, vim.list_slice(rendered, first, last_new))
  end
  vim.bo[buf].modifiable = false

  vim.api.nvim_buf_clear_namespace(buf, NS, 0, -1)
  for _, lnum in ipairs(headers) do
    vim.api.nvim_buf_set_extmark(buf, NS, lnum - 1, 0, {
      line_hl_group = 'RenderMarkdownTableHead',
    })
  end
  colour_markup(buf, rendered, origin, lines)
  stamps[path] = stamp(path)
end

--- Dim the box-drawing characters so the table structure recedes.
local function style_borders()
  if vim.w.mdv_matched then
    return
  end
  vim.w.mdv_matched = true
  pcall(vim.fn.matchadd, 'RenderMarkdownTableRow', '[│┌┬┐├┼┤└┴┘─]', 200)
end

--- Show the reflowed view of `path` in the current window.
---@param path string
function M.show(path)
  if vim.fn.filereadable(path) ~= 1 then
    return
  end
  local buf = views[path]
  if not buf or not vim.api.nvim_buf_is_valid(buf) then
    buf = scratch(path)
    views[path], sources[buf] = buf, path
  end
  fill(path, buf)
  vim.api.nvim_win_set_buf(0, buf)
  -- set the filetype only once the buffer is on screen: render-markdown attaches
  -- on the FileType event, and would miss a buffer typed while it was hidden
  if vim.bo[buf].filetype ~= 'markdown' then
    vim.bo[buf].filetype = 'markdown'
  end
  style_borders()
end

local next_rebuild = 0

--- Rebuild the current reflow buffer, keeping the viewport.
---
--- A large document costs a couple of hundred milliseconds to reflow, so while
--- one is being written continuously the rebuild backs off to a few times its
--- own cost instead of running flat out once a second.
---@param force boolean|nil rebuild even when the file is unchanged
function M.refresh(force)
  local path = sources[vim.api.nvim_get_current_buf()]
  if not path then
    return
  end
  if not force and (stamps[path] == stamp(path) or vim.uv.now() < next_rebuild) then
    return
  end
  local started = vim.uv.hrtime()
  local view = vim.fn.winsaveview()
  fill(path, vim.api.nvim_get_current_buf())
  pcall(vim.fn.winrestview, view)
  next_rebuild = vim.uv.now() + ((vim.uv.hrtime() - started) / 1e6) * 3
end

--- Swap between the reflowed view and the raw markdown source.
function M.toggle()
  local buf = vim.api.nvim_get_current_buf()
  local path = sources[buf]
  if path then
    M.enabled = false
    vim.cmd.edit(vim.fn.fnameescape(path))
    vim.notify('raw source')
    return
  end
  local name = vim.api.nvim_buf_get_name(buf)
  if name == '' or vim.fn.filereadable(name) ~= 1 then
    vim.notify('no file to reflow', vim.log.levels.WARN)
    return
  end
  M.enabled = true
  M.show(name)
  vim.notify('tables reflowed to window width')
end

--- Open the file at `index` in the argument list (1-indexed, wraps around).
---@param step integer
function M.cycle(step)
  local files = vim.fn.argv()
  if #files < 2 then
    return
  end
  local buf = vim.api.nvim_get_current_buf()
  local current = sources[buf] or vim.api.nvim_buf_get_name(buf)
  local index = 1
  for i, file in ipairs(files) do
    if vim.fn.fnamemodify(file, ':p') == vim.fn.fnamemodify(current, ':p') then
      index = i
    end
  end
  local next_file = files[((index - 1 + step) % #files) + 1]
  if M.enabled then
    M.show(vim.fn.fnamemodify(next_file, ':p'))
  else
    vim.cmd.edit(vim.fn.fnameescape(next_file))
  end
end

--- Links on the source line behind `lnum`, in order.
---
--- Reflowed cells hold only the link label, so the target is recovered from the
--- markdown line the rendered line came from. Relative targets (screenshots) are
--- resolved against the document's own directory.
---@param buf integer
---@param lnum integer
---@return { label: string, url: string }[]
function M.links_at(buf, lnum)
  local map, lines = origins[buf], raw_lines[buf]
  local text = map and lines and lines[map[lnum]] or vim.api.nvim_get_current_line()
  if not text then
    return {}
  end
  local dir = sources[buf] and vim.fn.fnamemodify(sources[buf], ':h') or vim.fn.getcwd()

  local function resolve(url)
    url = url:gsub('%s+".*$', '') -- drop a link title
    if url:match('^%a[%w+.-]*:') or url:match('^#') then
      return url
    end
    return vim.fs.normalize(dir .. '/' .. url)
  end

  local found = {}
  for label, url in text:gmatch('%[([^%]]*)%]%(([^)]+)%)') do
    found[#found + 1] = { label = label ~= '' and label or url, url = resolve(url) }
  end
  for url in text:gsub('%[[^%]]*%]%([^)]+%)', ' '):gmatch('https?://[^%s%)%]|`]+') do
    found[#found + 1] = { label = url, url = url }
  end
  return found
end

--- Open a link from the current line, asking which one when there are several.
function M.open()
  local buf = vim.api.nvim_get_current_buf()
  local links = M.links_at(buf, vim.api.nvim_win_get_cursor(0)[1])
  if #links == 0 then
    local cfile = vim.fn.expand('<cfile>')
    if cfile == '' then
      vim.notify('no link on this line', vim.log.levels.WARN)
    else
      vim.ui.open(cfile)
    end
    return
  end
  if #links == 1 then
    vim.ui.open(links[1].url)
    return
  end
  vim.ui.select(links, {
    prompt = 'open link',
    format_item = function(link)
      return ('%s  →  %s'):format(link.label, link.url)
    end,
  }, function(choice)
    if choice then
      vim.ui.open(choice.url)
    end
  end)
end

--- Enter the reflowed view for the file opened on the command line.
function M.start()
  if not M.enabled then
    return
  end
  local name = vim.api.nvim_buf_get_name(0)
  if name ~= '' and vim.fn.filereadable(name) == 1 then
    M.show(name)
  end
end

return M

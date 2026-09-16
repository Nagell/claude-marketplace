--- Reflow markdown pipe tables into fixed-width box tables with wrapped cells.
---
--- Neovim cannot wrap text inside a rendered table (see neovim/neovim#14409), so
--- the only way to read a table with 500-character cells is to rewrite the text
--- itself to fit the window, the way `glow` does. The output is plain text, so it
--- is only ever placed in a scratch buffer -- never written back to the file.

local M = {}

local strwidth = vim.fn.strdisplaywidth

local BORDER = {
  tl = '┌', t = '┬', tr = '┐',
  ml = '├', m = '┼', mr = '┤',
  bl = '└', b = '┴', br = '┘',
  v = '│', h = '─',
}

--- Split a table row into trimmed cells, honouring escaped pipes (`\|`).
---@param line string
---@return string[]
function M.cells(line)
  local body = line:gsub('^%s*|', ''):gsub('|%s*$', '')
  local out, buf, i = {}, {}, 1
  while i <= #body do
    local ch = body:sub(i, i)
    if ch == '\\' and body:sub(i + 1, i + 1) == '|' then
      buf[#buf + 1], i = '|', i + 2
    elseif ch == '|' then
      out[#out + 1], buf, i = table.concat(buf), {}, i + 1
    else
      buf[#buf + 1], i = ch, i + 1
    end
  end
  out[#out + 1] = table.concat(buf)
  for k, v in ipairs(out) do
    out[k] = vim.trim(v)
  end
  return out
end

--- True when the line is a pipe-table delimiter row (`|---|:--:|`).
---@param line string
---@return boolean
function M.is_delimiter(line)
  return line:match('^%s*|[%s:%-|]+|%s*$') ~= nil
end

--- Column alignments taken from the delimiter row.
---@param delimiter string[]
---@return string[]
function M.alignments(delimiter)
  local out = {}
  for i, cell in ipairs(delimiter) do
    local left, right = cell:sub(1, 1) == ':', cell:sub(-1) == ':'
    out[i] = (left and right and 'center') or (right and 'right') or 'left'
  end
  return out
end

--- Inline markup is concealed when rendered, which silently changes how wide a
--- line really is and pulls the table borders out of line. Cells are therefore
--- reduced to plain text before any width is measured.
local SUBSTITUTIONS = {
  { '<br%s*/?>', '\n' },
  { '!%[([^%]]*)%]%([^)]*%)', '%1' }, -- image -> alt text
  { '%[([^%]]*)%]%([^)]*%)', '%1' }, -- link -> label
  { '%[([^%]]*)%]%[[^%]]*%]', '%1' }, -- reference link -> label
  { '<(https?://[^>]*)>', '%1' }, -- autolink
  { '`([^`]*)`', '%1' }, -- code span
  { '%*%*([^%*]+)%*%*', '%1' }, -- bold
  { '%*([^%*]+)%*', '%1' }, -- italic
  { '~~([^~]+)~~', '%1' }, -- strikethrough
  { '</?%a[%w]*[^>]*>', '' }, -- leftover html tags
}

--- Strip markup that would be concealed, or is just noise, in a plain-text cell.
---@param text string
---@return string
function M.clean(text)
  local out = text
  for _, rule in ipairs(SUBSTITUTIONS) do
    out = out:gsub(rule[1], rule[2])
  end
  return out
end

--- Link labels and code spans of a markdown line, so the reflowed view can
--- colour them even though the markup itself has been stripped from the cells.
---@param text string
---@return { text: string, hl: string }[]
function M.markup(text)
  local out = {}
  for label in text:gmatch('%[([^%]]+)%]%([^)]+%)') do
    local plain = M.clean(label)
    if #plain >= 3 then
      out[#out + 1] = { text = plain, hl = 'MdvLink' }
    end
  end
  for code in text:gmatch('`([^`]+)`') do
    if #code >= 3 then
      out[#out + 1] = { text = code, hl = 'MdvCode' }
    end
  end
  return out
end

--- Display width of a cell, which may already contain hard line breaks.
---@param text string
---@return integer
local function cell_width(text)
  local widest = 0
  for _, line in ipairs(vim.split(text, '\n', { plain = true })) do
    widest = math.max(widest, strwidth(line))
  end
  return widest
end

--- Take the longest prefix of `word` that fits in `width` display cells.
---@param word string
---@param width integer
---@return string
local function take(word, width)
  local chars = math.min(width, vim.fn.strchars(word))
  while chars > 1 and strwidth(vim.fn.strcharpart(word, 0, chars)) > width do
    chars = chars - 1
  end
  return vim.fn.strcharpart(word, 0, chars)
end

-- identifiers and paths read far better broken after one of these than cut
-- mid-token: `format_factor_/display` rather than `format_factor_d/isplay`
local BREAK_AFTER = { ['/'] = true, ['_'] = true, ['-'] = true, ['.'] = true, [','] = true }

--- The part of an over-long word to put on this line, preferring a separator.
---@param word string
---@param width integer
---@return string
local function head_of(word, width)
  local head = take(word, width)
  local chars = vim.fn.strchars(head)
  for i = chars, math.max(1, math.floor(chars / 2)), -1 do
    if BREAK_AFTER[vim.fn.strcharpart(head, i - 1, 1)] then
      return vim.fn.strcharpart(head, 0, i)
    end
  end
  return head
end

--- Append `word` to `current`, spilling finished lines into `lines`.
---@return string current
local function place(lines, current, word, width)
  if current ~= '' then
    if strwidth(current) + 1 + strwidth(word) <= width then
      return current .. ' ' .. word
    end
    lines[#lines + 1] = current
  end
  while strwidth(word) > width do
    local head = head_of(word, width)
    lines[#lines + 1] = head
    word = word:sub(#head + 1)
  end
  return word
end

--- Greedy word wrap. Honours newlines already present in the text.
---@param text string
---@param width integer
---@return string[]
function M.wrap(text, width)
  local lines = {}
  for _, paragraph in ipairs(vim.split(text, '\n', { plain = true })) do
    local current = ''
    for word in paragraph:gmatch('%S+') do
      current = place(lines, current, word, width)
    end
    lines[#lines + 1] = current
  end
  return lines
end

--- Shrink columns that are wider than their fair share of `avail`.
---@param natural integer[]
---@param avail integer
---@param min_width integer
---@return integer[]
function M.shrink(natural, avail, min_width)
  local out, flexible, remaining = {}, {}, avail
  for i in ipairs(natural) do
    flexible[#flexible + 1] = i
  end

  -- water filling: a column narrower than its fair share keeps its natural
  -- width, which releases space for the genuinely wide columns
  local changed = true
  while changed and #flexible > 0 do
    changed = false
    local share = math.max(math.floor(remaining / #flexible), min_width)
    for k = #flexible, 1, -1 do
      local i = flexible[k]
      if natural[i] <= share then
        out[i], remaining = natural[i], remaining - natural[i]
        table.remove(flexible, k)
        changed = true
      end
    end
  end

  -- what is left goes to the wide columns by the square root of their content.
  -- Splitting it in direct proportion lets one 800-character column take almost
  -- everything and pins its neighbours to the floor, which is what makes the
  -- last column of a wide table unreadable.
  local flex_total = 0
  for _, i in ipairs(flexible) do
    flex_total = flex_total + math.sqrt(natural[i])
  end
  for _, i in ipairs(flexible) do
    out[i] = math.max(min_width, math.floor(remaining * math.sqrt(natural[i]) / flex_total))
  end
  return out
end

--- Trim the widest columns until the row fits; the `min_width` floor applied by
--- `shrink` can otherwise push the total back over the available width.
---@param widths integer[]
---@param avail integer
---@param min_width integer
---@return integer[]
function M.fit(widths, avail, min_width)
  local total = 0
  for _, w in ipairs(widths) do
    total = total + w
  end
  while total > avail do
    local widest, value = nil, min_width
    for i, w in ipairs(widths) do
      if w > value then
        widest, value = i, w
      end
    end
    if not widest then
      break -- every column is at the floor: the window is simply too narrow
    end
    widths[widest], total = widths[widest] - 1, total - 1
  end
  return widths
end

--- Column widths: natural width when the table fits, proportional otherwise.
---@param rows string[][]
---@param avail integer
---@param min_width integer
---@return integer[]
function M.widths(rows, avail, min_width)
  local natural, total = {}, 0
  for _, row in ipairs(rows) do
    for i, cell in ipairs(row) do
      natural[i] = math.max(natural[i] or 1, cell_width(cell))
    end
  end
  for _, n in ipairs(natural) do
    total = total + n
  end
  if total <= avail then
    return natural
  end

  local widths = M.fit(M.shrink(natural, avail, min_width), avail, min_width)

  -- rounding leaves a few cells unused; hand them to the column furthest below
  -- its natural width rather than leaving the table short of the window
  local used = 0
  for _, w in ipairs(widths) do
    used = used + w
  end
  local slack = avail - used
  if slack > 0 then
    local hungriest, gap = nil, 0
    for i, w in ipairs(widths) do
      if natural[i] - w > gap then
        hungriest, gap = i, natural[i] - w
      end
    end
    if hungriest then
      widths[hungriest] = widths[hungriest] + math.min(slack, gap)
    end
  end
  return widths
end

---@param widths integer[]
---@return string
local function rule(widths, left, middle, right)
  local parts = {}
  for _, w in ipairs(widths) do
    parts[#parts + 1] = string.rep(BORDER.h, w + 2)
  end
  return left .. table.concat(parts, middle) .. right
end

---@param text string
---@param width integer
---@param align string
---@return string
local function pad(text, width, align)
  local space = width - strwidth(text)
  if space < 0 then
    -- a double-width glyph can overshoot a narrow column; never break the border
    text = take(text, width)
    space = width - strwidth(text)
    if space < 0 then
      return string.rep(' ', width)
    end
  end
  if space == 0 then
    return text
  end
  if align == 'right' then
    return string.rep(' ', space) .. text
  end
  if align == 'center' then
    local left = math.floor(space / 2)
    return string.rep(' ', left) .. text .. string.rep(' ', space - left)
  end
  return text .. string.rep(' ', space)
end

--- Join cells into one line, shaving padding until it really fits `max_width`.
---
--- Some glyphs (emoji such as U+1F7E1) measure narrower on their own than they
--- occupy in a rendered line, so the composed line is measured rather than
--- trusted. Shaving costs at most a space of padding on the affected row.
---@param parts string[]
---@param max_width integer
---@return string
local function compose(parts, max_width)
  local text = BORDER.v .. table.concat(parts, BORDER.v) .. BORDER.v
  local guard = 0
  while strwidth(text) > max_width and guard < 8 do
    local widest = 1
    for i, part in ipairs(parts) do
      if strwidth(part) > strwidth(parts[widest]) then
        widest = i
      end
    end
    parts[widest] = take(parts[widest], strwidth(parts[widest]) - 1)
    text = BORDER.v .. table.concat(parts, BORDER.v) .. BORDER.v
    guard = guard + 1
  end
  return text
end

--- Render one table row, wrapping each cell over as many lines as it needs.
---@return string[] lines
local function row_lines(cells, widths, aligns, max_width)
  local wrapped, height = {}, 1
  for i, width in ipairs(widths) do
    wrapped[i] = M.wrap(cells[i] or '', width)
    height = math.max(height, #wrapped[i])
  end
  local out = {}
  for line = 1, height do
    local parts = {}
    for i, width in ipairs(widths) do
      parts[#parts + 1] = ' ' .. pad(wrapped[i][line] or '', width, aligns[i] or 'left') .. ' '
    end
    out[#out + 1] = compose(parts, max_width)
  end
  return out
end

--- Render a parsed table as box-drawing text.
---@param rows string[][] header row first
---@param aligns string[]
---@param total_width integer window width to fit into
---@return string[] lines
---@return integer header_height number of leading lines that are the header
function M.render(rows, aligns, total_width)
  -- the delimiter row decides how many columns the table has. A row with more
  -- cells has an unescaped `|` in its text, so the surplus is joined back into
  -- the last column rather than inventing a column no other row fills.
  local columns = #aligns
  for _, row in ipairs(rows) do
    columns = math.max(columns, columns > 0 and 0 or #row)
  end
  for _, row in ipairs(rows) do
    if #row > columns then
      local tail = {}
      for i = columns, #row do
        tail[#tail + 1] = row[i]
      end
      for i = #row, columns + 1, -1 do
        row[i] = nil
      end
      row[columns] = table.concat(tail, ' | ')
    end
    for i = 1, columns do
      row[i] = M.clean(row[i] or '')
    end
  end

  -- a stray `|` in one cell invents a column that is empty everywhere; keeping
  -- it would waste width the real columns need
  local keep = {}
  for i = 1, columns do
    for _, row in ipairs(rows) do
      if row[i] ~= '' then
        keep[#keep + 1] = i
        break
      end
    end
  end
  if #keep < columns then
    for r, row in ipairs(rows) do
      rows[r] = vim.tbl_map(function(i)
        return row[i]
      end, keep)
    end
    aligns = vim.tbl_map(function(i)
      return aligns[i] or 'left'
    end, keep)
    columns = #keep
  end

  local avail = total_width - (columns * 3) - 1
  -- every column gets an equal share as its floor, capped at 14 so a wide window
  -- does not hand a short column more than it can use, and reduced when the
  -- window is too narrow for the floors themselves to fit
  local min_width = math.max(3, math.min(14, math.floor(avail / columns)))
  local widths = M.widths(rows, avail, min_width)

  local out, origin = {}, {}
  local function emit(line, row)
    out[#out + 1], origin[#origin + 1] = line, row
  end

  local header = row_lines(rows[1], widths, aligns, total_width)
  emit(rule(widths, BORDER.tl, BORDER.t, BORDER.tr), 1)
  for _, line in ipairs(header) do
    emit(line, 1)
  end
  emit(rule(widths, BORDER.ml, BORDER.m, BORDER.mr), 1)

  for i = 2, #rows do
    if i > 2 then
      emit(rule(widths, BORDER.ml, BORDER.m, BORDER.mr), i)
    end
    for _, line in ipairs(row_lines(rows[i], widths, aligns, total_width)) do
      emit(line, i)
    end
  end
  emit(rule(widths, BORDER.bl, BORDER.b, BORDER.br), #rows)
  return out, #header + 1, origin
end

--- Split off leading indentation and blockquote markers, so a table inside a
--- callout (`> | a | b |`) or a list is recognised like any other.
---@param line string
---@return string prefix, string body
local function split_prefix(line)
  local prefix, body = line:match('^([%s>]*)(.*)$')
  return prefix or '', body or line
end

---@param prefix string
---@return integer number of blockquote levels
local function depth(prefix)
  local levels = 0
  for _ in prefix:gmatch('>') do
    levels = levels + 1
  end
  return levels
end

--- Collect the table starting at `start`; returns nil when there is none.
---@return string[][]|nil rows, string[]|nil aligns, integer|nil stop, string|nil prefix
local function collect(lines, start)
  local prefix, body = split_prefix(lines[start])
  if not body:match('^|') or not lines[start + 1] then
    return nil
  end
  local next_prefix, next_body = split_prefix(lines[start + 1])
  if depth(next_prefix) ~= depth(prefix) or not M.is_delimiter(next_body) then
    return nil
  end

  local rows, stop = { M.cells(body) }, start + 2
  local aligns = M.alignments(M.cells(next_body))
  while lines[stop] do
    local row_prefix, row_body = split_prefix(lines[stop])
    if depth(row_prefix) ~= depth(prefix) or not row_body:match('^|') then
      break
    end
    rows[#rows + 1] = M.cells(row_body)
    stop = stop + 1
  end
  return rows, aligns, stop - 1, prefix
end

--- Longest run of backticks in the rendered lines, so the fence can outrun it.
---@param rendered string[]
---@return integer
local function longest_backtick_run(rendered)
  local longest = 0
  for _, line in ipairs(rendered) do
    for run in line:gmatch('`+') do
      longest = math.max(longest, #run)
    end
  end
  return longest
end

--- Replace every pipe table in `lines` with a width-fitted box table.
--- Content inside fenced code blocks is left untouched.
---@param lines string[]
---@param width integer target window width
---@return string[] lines
---@return integer[] header_lines 1-indexed lines that hold table headers
---@return integer[] origin source line each output line came from
function M.transform(lines, width)
  local out, headers, origin, i, fenced = {}, {}, {}, 1, false
  while i <= #lines do
    local line = lines[i]
    if line:match('^[%s>]*```') or line:match('^[%s>]*~~~') then
      fenced = not fenced
    end
    local rows, aligns, stop, prefix = nil, nil, nil, ''
    if not fenced then
      rows, aligns, stop, prefix = collect(lines, i)
    end
    if rows then
      local indent = vim.fn.strdisplaywidth(prefix)
      local rendered, header_height, row_of = M.render(rows, aligns, width - indent)

      -- Fence the laid-out table. Cell text can still hold a stray backtick or
      -- an `_x_` that markdown reads as a code span or emphasis; parsed as
      -- markdown those run on across the wrapped lines, colouring half a table
      -- and shifting its borders through conceal. Inside a code fence nothing
      -- is parsed as inline markup, so the layout is exactly what was measured.
      local fence = string.rep('`', math.max(3, longest_backtick_run(rendered) + 1))
      out[#out + 1] = prefix .. fence
      origin[#origin + 1] = i

      for n, text in ipairs(rendered) do
        out[#out + 1] = prefix .. text
        -- row 1 is the header at `i`; the delimiter sits at i+1, so row r is at i+r
        origin[#origin + 1] = row_of[n] == 1 and i or (i + row_of[n])
        if n > 1 and n <= header_height then
          headers[#headers + 1] = #out
        end
      end

      out[#out + 1] = prefix .. fence
      origin[#origin + 1] = i
      i = stop + 1
    else
      out[#out + 1] = line
      origin[#origin + 1] = i
      i = i + 1
    end
  end
  return out, headers, origin
end

return M

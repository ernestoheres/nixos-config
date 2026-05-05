local ls = require("luasnip")
local extras = require("luasnip.extras")

local i = ls.insert_node
local s = ls.snippet
local t = ls.text_node
local rep = extras.rep

local M = {}

local function append_text(nodes, chunk)
  if chunk == "" then
    return
  end

  local lines = vim.split(chunk, "\n", { plain = true })
  if #lines == 1 then
    table.insert(nodes, t(chunk))
    return
  end

  table.insert(nodes, t(lines))
end

local function build_nodes(template)
  local nodes = {}
  local placeholders = {}
  local next_index = 1
  local cursor = 1

  while true do
    local start_pos, end_pos, name = template:find("{{([%w_]+)}}", cursor)
    if not start_pos then
      break
    end

    append_text(nodes, template:sub(cursor, start_pos - 1))

    local index = placeholders[name]
    if not index then
      index = next_index
      placeholders[name] = index
      next_index = next_index + 1
      table.insert(nodes, i(index, name))
    else
      table.insert(nodes, rep(index))
    end

    cursor = end_pos + 1
  end

  append_text(nodes, template:sub(cursor))
  return nodes
end

local function build_snippet(spec, default_filetype)
  vim.validate({
    trig = { spec.trig, "string" },
    name = { spec.name, "string" },
    template = { spec.template, "string" },
  })

  return s({
    trig = spec.trig,
    name = spec.name,
    dscr = spec.desc,
    filetype = spec.filetype or default_filetype,
  }, build_nodes(spec.template))
end

local function iter_specs(raw)
  if raw.trig then
    return { raw }
  end

  return raw
end

function M.load_filetype(filetype, snippet_dir)
  local snippets = {}
  local files = {}

  for name, type in vim.fs.dir(snippet_dir) do
    if type == "file" and name:sub(-4) == ".lua" then
      table.insert(files, name)
    end
  end

  table.sort(files)

  for _, name in ipairs(files) do
    local path = snippet_dir .. "/" .. name
    local chunk, load_error = loadfile(path)
    if not chunk then
      error(string.format("Failed to load snippet file %s: %s", path, load_error))
    end

    local ok, raw = pcall(chunk)
    if not ok then
      error(string.format("Failed to evaluate snippet file %s: %s", path, raw))
    end

    for _, spec in ipairs(iter_specs(raw)) do
      table.insert(snippets, build_snippet(spec, filetype))
    end
  end

  return snippets
end

return M

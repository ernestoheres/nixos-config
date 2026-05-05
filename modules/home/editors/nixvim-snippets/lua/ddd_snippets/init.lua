local loader = require("ddd_snippets.loader")

local M = {}

function M.setup()
  return true
end

function M.load_filetype(filetype, snippet_dir)
  return loader.load_filetype(filetype, snippet_dir)
end

return M

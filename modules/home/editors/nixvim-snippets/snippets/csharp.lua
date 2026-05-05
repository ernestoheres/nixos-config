require("ddd_snippets").setup()

local source = debug.getinfo(1, "S").source:sub(2)
local snippet_dir = source:gsub("%.lua$", "")

return require("ddd_snippets").load_filetype("csharp", snippet_dir)

require("ddd_snippets").setup()

local source = debug.getinfo(1, "S").source:sub(2)
local snippet_dir = vim.fs.dirname(source) .. "/csharp"

return require("ddd_snippets").load_filetype("cs", snippet_dir)

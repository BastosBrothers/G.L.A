local M = {}

local ns = vim.api.nvim_create_namespace("gla2_ui")

function M.setup()
  local hl = vim.api.nvim_set_hl
  hl(0, "Gla2Sidebar", { fg = "#cccccc", bg = "#252526" })
  hl(0, "Gla2Chat", { fg = "#cccccc", bg = "#1e1e1e" })
  hl(0, "Gla2Input", { fg = "#cccccc", bg = "#3c3c3c" })
  hl(0, "Gla2Float", { fg = "#cccccc", bg = "#252526" })
  hl(0, "Gla2Sep", { fg = "#1e1e1e" })
  hl(0, "Gla2Title", { fg = "#bbbbbb", bg = "#252526", bold = true })
  hl(0, "Gla2Muted", { fg = "#858585", bg = "#252526" })
  hl(0, "Gla2Accent", { fg = "#3794ff" })
  hl(0, "Gla2User", { fg = "#4fc1ff", bold = true })
  hl(0, "Gla2Name", { fg = "#cccccc", bold = true })
  hl(0, "Gla2Rule", { fg = "#3c3c3c" })
  hl(0, "Gla2Ok", { fg = "#89d185" })
  hl(0, "Gla2Warn", { fg = "#cca700" })
  hl(0, "Gla2Folder", { fg = "#dcb67a" })
  hl(0, "Gla2Hover", { bg = "#2a2d2e" })
  hl(0, "Gla2Status", { fg = "#ffffff", bg = "#007acc" })
  hl(0, "Gla2StatusNC", { fg = "#cccccc", bg = "#37373d" })
  hl(0, "Gla2Tab", { fg = "#ffffff", bg = "#1e1e1e", bold = true })
  hl(0, "Gla2TabFill", { fg = "#858585", bg = "#2d2d2d" })
end

function M.panel(win, kind)
  if not win or not vim.api.nvim_win_is_valid(win) then
    return
  end
  M.setup()
  local normal = kind == "chat" and "Gla2Chat" or (kind == "input" and "Gla2Input" or "Gla2Sidebar")
  vim.wo[win].number = false
  vim.wo[win].relativenumber = false
  vim.wo[win].signcolumn = "no"
  vim.wo[win].foldcolumn = "0"
  vim.wo[win].list = false
  vim.wo[win].wrap = kind == "chat"
  vim.wo[win].linebreak = kind == "chat"
  vim.wo[win].cursorline = kind == "side"
  vim.wo[win].cursorlineopt = "line"
  vim.wo[win].fillchars = "eob: "
  vim.wo[win].statuscolumn = ""
  vim.wo[win].winhighlight = table.concat({
    "Normal:" .. normal,
    "NormalNC:" .. normal,
    "EndOfBuffer:" .. normal,
    "CursorLine:Gla2Hover",
    "WinSeparator:Gla2Sep",
    "StatusLine:Gla2Status",
    "StatusLineNC:Gla2StatusNC",
  }, ",")
  if kind == "side" then
    vim.wo[win].statusline = "  EXPLORER"
  elseif kind == "chat" then
    vim.wo[win].statusline = "  CHAT"
  elseif kind == "input" then
    vim.wo[win].statusline = "  MENSAJE"
  end
end

function M.editor(win)
  if not win or not vim.api.nvim_win_is_valid(win) then
    return
  end
  M.setup()
  local buf = vim.api.nvim_win_get_buf(win)
  if vim.api.nvim_buf_is_valid(buf) and vim.bo[buf].buftype == "" then
    vim.bo[buf].modifiable = true
    vim.bo[buf].readonly = false
  end
  vim.wo[win].number = true
  vim.wo[win].signcolumn = "yes:1"
  vim.wo[win].cursorline = true
  vim.wo[win].statusline = "%#Gla2Status#  %f %= %l:%c  "
  vim.wo[win].winhighlight = "StatusLine:Gla2Status,StatusLineNC:Gla2StatusNC,WinSeparator:Gla2Sep,WinBar:Gla2Tab,WinBarNC:Gla2TabFill"
end

function M.float(win)
  if not win or not vim.api.nvim_win_is_valid(win) then
    return
  end
  M.setup()
  vim.wo[win].cursorline = true
  vim.wo[win].cursorlineopt = "line"
  vim.wo[win].winhighlight = "Normal:Gla2Float,NormalFloat:Gla2Float,FloatBorder:Gla2Accent,FloatTitle:Gla2Title,CursorLine:Gla2Hover"
end

function M.paint(buf, spec)
  if not buf or not vim.api.nvim_buf_is_valid(buf) then
    return
  end
  M.setup()
  vim.api.nvim_buf_clear_namespace(buf, ns, 0, -1)
  for _, item in ipairs(spec) do
    if item.line and item.group then
      vim.api.nvim_buf_add_highlight(buf, ns, item.group, item.line, item.col or 0, item.end_col or -1)
    end
  end
end

return M

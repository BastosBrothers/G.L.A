--[[
  Barra superior del editor (estilo pestaña).
  Hoy muestra el archivo activo. Luego podrá listar varios abiertos.
]]

local M = {}

local state = {
  open = {}, -- { path, name }
  current = nil,
}

local function is_editor_win(win)
  if not win or not vim.api.nvim_win_is_valid(win) then
    return false
  end
  local buf = vim.api.nvim_win_get_buf(win)
  local name = vim.api.nvim_buf_get_name(buf)
  local bt = vim.bo[buf].buftype
  if bt == "prompt" or bt == "nofile" then
    return false
  end
  if name == "gla2-chat" or name == "gla2-proyectos" then
    return false
  end
  return true
end

function M.remember(path)
  if not path or path == "" then
    return
  end
  path = vim.fn.fnamemodify(path, ":p")
  local name = vim.fn.fnamemodify(path, ":t")
  state.current = path
  for _, item in ipairs(state.open) do
    if item.path == path then
      item.name = name
      return
    end
  end
  table.insert(state.open, { path = path, name = name })
end

function M.paint(win)
  if not is_editor_win(win) then
    return
  end
  require("gla2.theme").setup()
  local buf = vim.api.nvim_win_get_buf(win)
  local path = vim.api.nvim_buf_get_name(buf)
  if path ~= "" then
    M.remember(path)
  end
  local title = path ~= "" and vim.fn.fnamemodify(path, ":t") or "sin archivo"
  -- Una sola pestaña visible; el resto queda listo para el sistema futuro.
  local label = title
  for _, item in ipairs(state.open) do
    if item.path == state.current then
      label = item.name
      break
    end
  end
  vim.wo[win].winbar = "%#Gla2Tab#  " .. label .. "  %*"
  require("gla2.theme").editor(win)
end

function M.list()
  return state.open
end

function M.current()
  return state.current
end

return M

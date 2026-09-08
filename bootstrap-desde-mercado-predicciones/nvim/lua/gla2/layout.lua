local M = {}

local listening = false

function M.sizes()
  local cols = vim.o.columns
  local side = math.min(32, math.max(26, math.floor(cols * 0.16)))
  local chat = math.min(36, math.max(26, math.floor(cols * 0.18)))
  local code_min = math.floor(cols / 2)
  if side + chat > cols - code_min then
    local budget = math.max(40, cols - code_min)
    side = math.min(22, math.floor(budget * 0.38))
    chat = math.max(24, budget - side)
  end
  return {
    side = side,
    chat = chat,
    input = 3,
  }
end

local function set_width(win, width)
  if win and vim.api.nvim_win_is_valid(win) then
    pcall(vim.api.nvim_win_set_width, win, width)
  end
end

local function set_height(win, height)
  if win and vim.api.nvim_win_is_valid(win) then
    pcall(vim.api.nvim_win_set_height, win, height)
  end
end

local remembered = {}

function M.apply(wins)
  wins = wins or {}
  if wins.side then
    remembered.side = wins.side
  end
  if wins.chat then
    remembered.chat = wins.chat
  end
  if wins.input then
    remembered.input = wins.input
  end
  vim.o.equalalways = false
  local size = M.sizes()
  set_width(remembered.side, size.side)
  set_width(remembered.chat, size.chat)
  set_height(remembered.input, size.input)
  if remembered.side and vim.api.nvim_win_is_valid(remembered.side) then
    vim.wo[remembered.side].winfixwidth = true
  end
  if remembered.chat and vim.api.nvim_win_is_valid(remembered.chat) then
    vim.wo[remembered.chat].winfixwidth = true
  end
  if remembered.input and vim.api.nvim_win_is_valid(remembered.input) then
    vim.wo[remembered.input].winfixheight = true
    vim.wo[remembered.input].winfixwidth = true
  end
end

function M.listen(get_wins)
  if listening then
    return
  end
  listening = true
  vim.api.nvim_create_autocmd("WinResized", {
    group = vim.api.nvim_create_augroup("gla2_layout", { clear = true }),
    callback = function()
      M.apply(get_wins())
    end,
  })
end

return M

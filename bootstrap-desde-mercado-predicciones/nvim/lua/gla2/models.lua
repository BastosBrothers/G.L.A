local M = {}

local state = {
  name = nil,
  create_name = nil,
  menu_buf = nil,
  menu_win = nil,
  items = {},
}

local function store_path()
  local dir = vim.fn.stdpath("data") .. "/gla2"
  vim.fn.mkdir(dir, "p")
  return dir .. "/model"
end

local function store_create_path()
  local dir = vim.fn.stdpath("data") .. "/gla2"
  vim.fn.mkdir(dir, "p")
  return dir .. "/model_create"
end

local function installed()
  local out = vim.fn.system({ "ollama", "list" })
  if vim.v.shell_error ~= 0 then
    return { "gla-2", "qwen2.5-coder:3b" }
  end
  local names = {}
  local first = true
  for line in out:gmatch("[^\r\n]+") do
    if first then
      first = false
    else
      local name = line:match("^(%S+)")
      if name and name ~= "NAME" then
        table.insert(names, name)
      end
    end
  end
  if #names == 0 then
    table.insert(names, "gla-2")
  end
  return names
end

local function has_model(want)
  local low = (want or ""):lower()
  for _, name in ipairs(installed()) do
    if name:lower() == low or name:lower() == (low .. ":latest") then
      return name
    end
  end
  return nil
end

local function is_gla2(name)
  local low = (name or ""):lower()
  return low == "gla-2" or low:find("^gla%-2:", 1) ~= nil
end

local function is_heavy(name)
  if is_gla2(name) then
    return false
  end
  local low = (name or ""):lower()
  return low:find("r1", 1, true) or low:find("14b", 1, true) or low:find("32b", 1, true)
end

function M.current()
  if state.name and state.name ~= "" then
    return state.name
  end
  if vim.fn.filereadable(store_path()) == 1 then
    local saved = vim.trim(table.concat(vim.fn.readfile(store_path()), ""))
    if saved ~= "" then
      state.name = saved
      return saved
    end
  end
  state.name = "gla-2"
  return state.name
end

function M.for_chat()
  return M.current()
end

function M.for_create()
  if state.create_name and state.create_name ~= "" then
    return state.create_name
  end
  if vim.fn.filereadable(store_create_path()) == 1 then
    local saved = vim.trim(table.concat(vim.fn.readfile(store_create_path()), ""))
    if saved ~= "" then
      state.create_name = saved
      return saved
    end
  end
  local preferred = has_model("qwen2.5-coder:3b") or has_model("qwen2.5-coder:7b")
  if preferred then
    return preferred
  end
  return M.current()
end

function M.weight()
  local name = M.current()
  if is_gla2(name) then
    return "gla-2"
  end
  return is_heavy(name) and "pesado" or "ligero"
end

function M.label()
  return "chat:" .. M.for_chat() .. "  create:" .. M.for_create()
end

local function close_menu()
  if state.menu_win and vim.api.nvim_win_is_valid(state.menu_win) then
    vim.api.nvim_win_close(state.menu_win, true)
  end
  state.menu_win = nil
  state.menu_buf = nil
  state.items = {}
end

function M.use(name)
  if not name or name == "" then
    return
  end
  state.name = name
  vim.fn.writefile({ name }, store_path())
  close_menu()
  local ok, workspace = pcall(require, "gla2.workspace")
  if ok then
    workspace.refresh()
  end
  local chat_ok, chat = pcall(require, "gla2.chat")
  if chat_ok and chat.render then
    chat.render()
  end
  vim.notify("Modelo chat: " .. name .. " (" .. M.weight() .. ")", vim.log.levels.INFO)
end

function M.use_create(name)
  if not name or name == "" then
    return
  end
  state.create_name = name
  vim.fn.writefile({ name }, store_create_path())
  close_menu()
  vim.notify("Modelo creación: " .. name, vim.log.levels.INFO)
  local chat_ok, chat = pcall(require, "gla2.chat")
  if chat_ok and chat.render then
    chat.render()
  end
end

function M.menu()
  close_menu()
  local names = installed()
  local items = {
    { label = "— Chat (respuestas / charla) —", name = nil },
    { label = "Chat → " .. M.for_chat(), name = M.for_chat(), kind = "chat" },
  }
  for _, name in ipairs(names) do
    table.insert(items, { label = "  chat: " .. name, name = name, kind = "chat" })
  end
  table.insert(items, { label = "— Creación (código / archivos) —", name = nil })
  table.insert(items, { label = "Create → " .. M.for_create(), name = M.for_create(), kind = "create" })
  local create_pref = has_model("qwen2.5-coder:3b")
  if create_pref then
    table.insert(items, { label = "  create: " .. create_pref .. " (recomendado)", name = create_pref, kind = "create" })
  end
  for _, name in ipairs(names) do
    table.insert(items, { label = "  create: " .. name, name = name, kind = "create" })
  end
  state.items = items

  local lines = { "" }
  local width = 42
  for _, item in ipairs(items) do
    local mark = "    "
    if item.kind == "chat" and item.name == M.for_chat() then
      mark = "  ● "
    elseif item.kind == "create" and item.name == M.for_create() then
      mark = "  ● "
    end
    local text = mark .. item.label
    width = math.max(width, vim.fn.strdisplaywidth(text) + 3)
    table.insert(lines, text)
  end

  state.menu_buf = vim.api.nvim_create_buf(false, true)
  vim.api.nvim_buf_set_lines(state.menu_buf, 0, -1, false, lines)
  vim.bo[state.menu_buf].bufhidden = "wipe"
  vim.bo[state.menu_buf].buftype = "nofile"
  state.menu_win = vim.api.nvim_open_win(state.menu_buf, true, {
    relative = "editor",
    row = 4,
    col = 3,
    width = math.min(width, 64),
    height = math.min(#lines, 22),
    style = "minimal",
    border = "rounded",
    title = " Modelos Gla-2 ",
    title_pos = "center",
  })
  require("gla2.theme").float(state.menu_win)

  local function pick()
    local line = vim.api.nvim_win_get_cursor(0)[1]
    local item = state.items[line - 1]
    if not item or not item.name then
      return
    end
    if item.kind == "create" then
      M.use_create(item.name)
    else
      M.use(item.name)
    end
  end
  vim.keymap.set("n", "<CR>", pick, { buffer = state.menu_buf, silent = true })
  vim.keymap.set("n", "<Esc>", close_menu, { buffer = state.menu_buf, silent = true })
  vim.keymap.set("n", "q", close_menu, { buffer = state.menu_buf, silent = true })
end

return M

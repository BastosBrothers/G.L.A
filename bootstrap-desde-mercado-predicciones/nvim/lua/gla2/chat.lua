local M = {}

local state = {
  chat_buf = nil,
  chat_win = nil,
  input_buf = nil,
  input_win = nil,
  target_buf = nil,
  busy = false,
  last = nil,
  root = nil,
  turns = {},
}

local function engine_root()
  if vim.g.gla2_engine and vim.g.gla2_engine ~= "" then
    return vim.g.gla2_engine
  end
  local here = debug.getinfo(1, "S").source:sub(2)
  return vim.fn.fnamemodify(here, ":h:h:h:h")
end

local function python_cmd()
  if vim.g.gla2_python and vim.g.gla2_python ~= "" then
    return vim.g.gla2_python
  end
  return "python"
end

local function mode_file()
  local dir = vim.fn.stdpath("data") .. "/gla2"
  vim.fn.mkdir(dir, "p")
  return dir .. "/auto_write"
end

local function auto_write()
  if vim.g.gla2_auto_write ~= nil then
    return vim.g.gla2_auto_write == true or vim.g.gla2_auto_write == 1
  end
  return vim.fn.filereadable(mode_file()) == 1
end

local function set_auto_write(on)
  vim.g.gla2_auto_write = on and true or false
  if on then
    vim.fn.writefile({ "1" }, mode_file())
  else
    pcall(vim.fn.delete, mode_file())
  end
end

local function history_file(root)
  local dir = vim.fn.stdpath("data") .. "/gla2/chats"
  vim.fn.mkdir(dir, "p")
  return dir .. "/" .. vim.fn.sha256(root) .. ".json"
end

local function save_history()
  if not state.root then
    return
  end
  local payload = vim.json.encode({ path = state.root, turns = state.turns })
  vim.fn.writefile({ payload }, history_file(state.root))
end

local function load_history(root)
  local path = history_file(root)
  if vim.fn.filereadable(path) == 0 then
    return {}
  end
  local ok, decoded = pcall(vim.json.decode, table.concat(vim.fn.readfile(path), "\n"))
  if not ok or type(decoded) ~= "table" or type(decoded.turns) ~= "table" then
    return {}
  end
  return decoded.turns
end

local function history_context()
  if #state.turns == 0 then
    return ""
  end
  local lines = { "Historial de este proyecto:" }
  local start = math.max(1, #state.turns - 7)
  for i = start, #state.turns do
    local turn = state.turns[i]
    local who = turn.role == "user" and "Usuario" or "Gla-2"
    local text = (turn.text or ""):gsub("\n", " ")
    if #text > 280 then
      text = text:sub(1, 280) .. "…"
    end
    table.insert(lines, who .. ": " .. text)
  end
  return table.concat(lines, "\n")
end

local function render_chat()
  if not state.chat_buf or not vim.api.nvim_buf_is_valid(state.chat_buf) then
    return
  end
  local theme = require("gla2.theme")
  local title = state.root and vim.fn.fnamemodify(state.root, ":t") or "sin proyecto"
  local model = require("gla2.models")
  local lines = {
    "  CHAT",
    "  " .. title .. "   ·   " .. model.current(),
    "",
  }
  local marks = {
    { line = 0, group = "Gla2Muted" },
    { line = 1, group = "Gla2Name" },
  }
  for _, turn in ipairs(state.turns) do
    if turn.role == "user" then
      table.insert(lines, "  tú")
      table.insert(marks, { line = #lines - 1, group = "Gla2User" })
      table.insert(lines, "")
      vim.list_extend(lines, vim.split("  " .. (turn.text or ""):gsub("\n", "\n  "), "\n", { plain = true }))
      table.insert(lines, "")
    else
      table.insert(lines, "  gla-2")
      table.insert(marks, { line = #lines - 1, group = "Gla2Accent" })
      table.insert(lines, "")
      for _, row in ipairs(vim.split(turn.text or "", "\n", { plain = true })) do
        table.insert(lines, row == "" and "" or ("  " .. row))
      end
      table.insert(lines, "")
    end
  end
  if state.busy and state.root then
    table.insert(lines, "  trabajando en " .. title .. "…")
    table.insert(marks, { line = #lines - 1, group = "Gla2Warn" })
  end
  vim.bo[state.chat_buf].modifiable = true
  vim.api.nvim_buf_set_lines(state.chat_buf, 0, -1, false, lines)
  vim.bo[state.chat_buf].modifiable = true
  theme.paint(state.chat_buf, marks)
  theme.panel(state.chat_win, "chat")
  if state.chat_win and vim.api.nvim_win_is_valid(state.chat_win) then
    vim.api.nvim_win_set_cursor(state.chat_win, { #lines, 0 })
  end
end

local function append(buf, lines)
  if not buf or not vim.api.nvim_buf_is_valid(buf) then
    return
  end
  local last = vim.api.nvim_buf_line_count(buf)
  if last == 1 and vim.api.nvim_buf_get_lines(buf, 0, 1, false)[1] == "" then
    vim.api.nvim_buf_set_lines(buf, 0, 1, false, lines)
  else
    vim.api.nvim_buf_set_lines(buf, last, last, false, lines)
  end
  if state.chat_win and vim.api.nvim_win_is_valid(state.chat_win) then
    local n = vim.api.nvim_buf_line_count(buf)
    vim.api.nvim_win_set_cursor(state.chat_win, { n, 0 })
  end
end

local function workspace()
  return require("gla2.workspace")
end

local function ignored_win(win)
  local side = workspace().sidebar_win()
  return win == state.chat_win or win == state.input_win or win == side
end

local function code_buf()
  if state.target_buf and vim.api.nvim_buf_is_valid(state.target_buf) then
    local name = vim.api.nvim_buf_get_name(state.target_buf)
    local bt = vim.bo[state.target_buf].buftype
    if bt == "" and name ~= "" then
      return state.target_buf
    end
  end
  local editor = workspace().editor_win()
  if editor then
    local buf = vim.api.nvim_win_get_buf(editor)
    if vim.bo[buf].buftype == "" and vim.api.nvim_buf_get_name(buf) ~= "" then
      state.target_buf = buf
      return buf
    end
  end
  for _, win in ipairs(vim.api.nvim_list_wins()) do
    if not ignored_win(win) then
      local buf = vim.api.nvim_win_get_buf(win)
      if vim.bo[buf].buftype == "" then
        state.target_buf = buf
        return buf
      end
    end
  end
  return nil
end

local function remember_target()
  local cur = vim.api.nvim_get_current_win()
  if not ignored_win(cur) then
    local buf = vim.api.nvim_win_get_buf(cur)
    if vim.bo[buf].buftype == "" then
      state.target_buf = buf
    end
  end
end

local function filetype_language(buf)
  local ft = vim.bo[buf].filetype
  if ft == "python" or ft == "rust" or ft == "c" then
    return ft
  end
  return nil
end

local function context_from(buf)
  local total = vim.api.nvim_buf_line_count(buf)
  local win = vim.fn.bufwinid(buf)
  local cursor = 1
  if win ~= -1 then
    cursor = vim.api.nvim_win_get_cursor(win)[1]
  end
  local from = math.max(1, cursor - 50)
  local to = math.min(total, cursor + 50)
  local lines = vim.api.nvim_buf_get_lines(buf, from - 1, to, false)
  return string.format("Líneas %d-%d del archivo activo:\n%s", from, to, table.concat(lines, "\n"))
end

local function diagnostics_of(buf)
  local items = {}
  for _, diag in ipairs(vim.diagnostic.get(buf)) do
    local line = (diag.lnum or 0) + 1
    table.insert(items, string.format("%s:%d: %s", diag.source or "lsp", line, diag.message or ""))
    if #items >= 12 then
      break
    end
  end
  return items
end

local function resolve_project_path(path)
  if not path or path == "" then
    return nil
  end
  local root = workspace().root()
  local is_abs = path:match("^%a:[/\\]") or path:sub(1, 1) == "/"
  if is_abs then
    return vim.fn.fnamemodify(path, ":p")
  end
  if root then
    return vim.fn.fnamemodify(root .. "/" .. path, ":p")
  end
  return vim.fn.fnamemodify(path, ":p")
end

local function open_in_editor(path)
  local win = workspace().editor_win()
  if not win then
    vim.cmd("edit " .. vim.fn.fnameescape(path))
    return vim.api.nvim_get_current_buf()
  end
  vim.api.nvim_set_current_win(win)
  vim.cmd("edit " .. vim.fn.fnameescape(path))
  return vim.api.nvim_get_current_buf()
end

local function same_file(path, bufname)
  if not path or path == "" then
    return true
  end
  if bufname == "" then
    return vim.fn.fnamemodify(path, ":t") ~= ""
  end
  local a = vim.fn.fnamemodify(path, ":p")
  local b = vim.fn.fnamemodify(bufname, ":p")
  if a == b then
    return true
  end
  return vim.fn.fnamemodify(path, ":t") == vim.fn.fnamemodify(bufname, ":t")
end

local function focus_code()
  local buf = code_buf()
  if not buf then
    return nil
  end
  local win = vim.fn.bufwinid(buf)
  if win ~= -1 then
    vim.api.nvim_set_current_win(win)
  end
  return buf
end

local function apply_replaces(replaces, buf)
  if not buf then
    return 0
  end
  local root = workspace().root()
  local bufname = vim.api.nvim_buf_get_name(buf)
  local applied = 0
  table.sort(replaces, function(a, b)
    return (a.start_line or 0) > (b.start_line or 0)
  end)
  for _, patch in ipairs(replaces) do
    local target = resolve_project_path(patch.path)
    if target and vim.fn.filereadable(target) == 1 and not same_file(target, bufname) then
      buf = open_in_editor(target)
      bufname = vim.api.nvim_buf_get_name(buf)
    end
    if target and root and not same_file(target, bufname) and not vim.startswith(target, root) then
      append(state.chat_buf, { "  (fuera del proyecto, no aplicado: " .. tostring(patch.path) .. ")" })
    elseif not same_file(patch.path, bufname) and not (target and same_file(target, bufname)) then
      append(state.chat_buf, { "  (parche de otro archivo, no aplicado: " .. tostring(patch.path) .. ")" })
    else
      local content = patch.content or ""
      local new_lines = vim.split(content, "\n", { plain = true })
      if new_lines[#new_lines] == "" then
        table.remove(new_lines)
      end
      local start_line = tonumber(patch.start_line) or 1
      local end_line = tonumber(patch.end_line) or start_line
      vim.api.nvim_buf_set_lines(buf, start_line - 1, end_line, false, new_lines)
      applied = applied + 1
    end
  end
  return applied
end

local function apply_diffs(diffs)
  if not diffs or #diffs == 0 then
    return 0
  end
  local patch = table.concat(diffs, "\n")
  local cwd = workspace().root() or vim.fn.getcwd()
  local buf = code_buf()
  if not workspace().root() and buf then
    local name = vim.api.nvim_buf_get_name(buf)
    if name ~= "" then
      cwd = vim.fn.fnamemodify(name, ":p:h")
    end
  end
  local ok = vim.system({ "git", "apply", "--unsafe-paths", "-" }, {
    stdin = patch,
    cwd = cwd,
    text = true,
  }):wait()
  if ok.code == 0 then
    vim.cmd("checktime")
    return #diffs
  end
  append(state.chat_buf, { "  (el diff no se pudo aplicar con git; quedó en el chat)" })
  return 0
end

local function apply_files(files)
  local root = workspace().root()
  if not root or not files or #files == 0 then
    return 0
  end
  local applied = 0
  local first = nil
  for _, item in ipairs(files) do
    local rel = (item.path or ""):gsub("\\", "/"):gsub("^/+", "")
    if rel == "" or rel:find("%.%.") then
      append(state.chat_buf, { "  (ruta inválida, no creada: " .. tostring(item.path) .. ")" })
    else
      local full = root .. "\\" .. rel:gsub("/", "\\")
      vim.fn.mkdir(vim.fn.fnamemodify(full, ":h"), "p")
      vim.fn.writefile(vim.split(item.content or "", "\n", { plain = true }), full)
      applied = applied + 1
      if not first then
        first = full
      end
    end
  end
  if first then
    open_in_editor(first)
  end
  return applied
end

local function apply_last()
  if not state.last or not state.last.patches then
    append(state.chat_buf, { "  (no hay parche pendiente)" })
    return
  end
  local buf = focus_code()
  local patches = state.last.patches
  local n = apply_files(patches.files or {})
  n = n + apply_replaces(patches.replaces or {}, buf)
  n = n + apply_diffs(patches.diffs or {})
  if n == 0 then
    append(state.chat_buf, { "  No se aplicó ningún cambio." })
    return
  end
  local name = buf and vim.fn.fnamemodify(vim.api.nvim_buf_get_name(buf), ":t") or "búfer"
  append(state.chat_buf, { "  Editado: " .. name })
  workspace().refresh()
end

local function on_reply(decoded)
  state.busy = false
  state.last = decoded
  local text = decoded.message or "(sin texto)"
  table.insert(state.turns, { role = "assistant", text = text })
  save_history()
  render_chat()
  local patches = decoded.patches or {}
  local has_patch = #(patches.replaces or {}) > 0 or #(patches.diffs or {}) > 0 or #(patches.files or {}) > 0
  if has_patch then
    append(state.chat_buf, { "Hay un cambio para el archivo abierto." })
    local yes = auto_write() or vim.fn.confirm("¿Aplicar el cambio de Gla-2 en el proyecto?", "&Sí\n&No", 1) == 1
    if yes then
      apply_last()
    else
      append(state.chat_buf, { "  Cambio no aplicado. :Gla2Apply para hacerlo después." })
    end
  end
end

local function send(text)
  text = vim.trim(text or "")
  if text == "" or state.busy then
    return
  end
  remember_target()
  local buf = code_buf()
  local root = workspace().root()
  if not root then
    append(state.chat_buf, { "Abre un proyecto a la izquierda antes de pedir cambios.", "" })
    return
  end
  state.root = root
  table.insert(state.turns, { role = "user", text = text })
  save_history()
  state.busy = true
  render_chat()

  local extra = workspace().file_index(text)
  local past = history_context()
  if past ~= "" then
    extra = extra .. "\n\n" .. past
  end
  if buf then
    extra = extra .. "\n\n" .. context_from(buf)
  end
  local payload_message = text
  local low = text:lower()
  local chatty = low:find("hola", 1, true)
    or low:find("cómo estás", 1, true)
    or low:find("como estas", 1, true)
    or low:find("qué tal", 1, true)
    or low:find("que tal", 1, true)
    or low:find("gracias", 1, true)
  if not chatty then
    payload_message = text .. "\n\nTrabaja solo dentro del proyecto activo. No toques otras carpetas."
  end
  local payload = {
    message = payload_message,
    language = (not chatty and buf) and filetype_language(buf) or nil,
    path = buf and vim.api.nvim_buf_get_name(buf) or root,
    diagnostics = (not chatty and buf) and diagnostics_of(buf) or {},
    extra_context = chatty and "" or extra,
    model = require("gla2.models").current(),
  }

  vim.system({ python_cmd(), "-m", "src.main", "json" }, {
    cwd = engine_root(),
    stdin = vim.json.encode(payload),
    text = true,
  }, function(result)
    vim.schedule(function()
      if not state.chat_buf or not vim.api.nvim_buf_is_valid(state.chat_buf) then
        state.busy = false
        return
      end
      if result.code ~= 0 and (not result.stdout or result.stdout == "") then
        state.busy = false
        table.insert(state.turns, { role = "assistant", text = "Error: " .. (result.stderr or "el motor no respondió") })
        save_history()
        render_chat()
        return
      end
      local ok, decoded = pcall(vim.json.decode, result.stdout or "")
      if not ok or type(decoded) ~= "table" then
        state.busy = false
        table.insert(state.turns, { role = "assistant", text = "Error: respuesta no JSON." })
        save_history()
        render_chat()
        return
      end
      if not decoded.ok then
        state.busy = false
        table.insert(state.turns, { role = "assistant", text = "Error: " .. (decoded.error or "falló") })
        save_history()
        render_chat()
        return
      end
      on_reply(decoded)
    end)
  end)
end

local function current_wins()
  return {
    side = require("gla2.workspace").sidebar_win(),
    chat = state.chat_win,
    input = state.input_win,
  }
end

local function ensure_chat()
  if state.chat_buf and vim.api.nvim_buf_is_valid(state.chat_buf) and state.chat_win and vim.api.nvim_win_is_valid(state.chat_win) then
    require("gla2.layout").apply(current_wins())
    return
  end

  remember_target()
  local layout = require("gla2.layout")
  local size = layout.sizes()
  vim.cmd("botright " .. size.chat .. "vsplit")
  state.chat_win = vim.api.nvim_get_current_win()
  state.chat_buf = vim.api.nvim_create_buf(false, true)
  vim.api.nvim_win_set_buf(state.chat_win, state.chat_buf)
  vim.bo[state.chat_buf].buftype = "nofile"
  vim.bo[state.chat_buf].bufhidden = "hide"
  vim.bo[state.chat_buf].swapfile = false
  vim.bo[state.chat_buf].filetype = "markdown"
  vim.api.nvim_buf_set_name(state.chat_buf, "gla2-chat")
  require("gla2.theme").panel(state.chat_win, "chat")
  vim.api.nvim_buf_set_lines(state.chat_buf, 0, -1, false, {
    "",
    "  GLA-2",
    "  Escribe abajo y pulsa Enter.",
    "",
  })
  vim.bo[state.chat_buf].modifiable = true

  vim.api.nvim_set_current_win(state.chat_win)
  vim.cmd("belowright " .. size.input .. "split")
  state.input_win = vim.api.nvim_get_current_win()
  state.input_buf = vim.api.nvim_create_buf(false, true)
  vim.api.nvim_win_set_buf(state.input_win, state.input_buf)
  vim.bo[state.input_buf].buftype = "prompt"
  vim.bo[state.input_buf].bufhidden = "hide"
  vim.bo[state.input_buf].swapfile = false
  vim.fn.prompt_setprompt(state.input_buf, "  › ")
  require("gla2.theme").panel(state.input_win, "input")
  layout.apply(current_wins())
  layout.listen(current_wins)
  vim.fn.prompt_setcallback(state.input_buf, function(text)
    if vim.bo[state.input_buf].modifiable then
      send(text)
    end
  end)
  vim.cmd("startinsert")
end

function M.render()
  render_chat()
end

function M.toggle_auto()
  set_auto_write(not auto_write())
  render_chat()
  vim.notify(auto_write() and "Gla-2: creación directa activada." or "Gla-2: vuelve a pedir confirmación.", vim.log.levels.INFO)
end

function M.save()
  save_history()
end

function M.bind_project(path)
  if not path or path == "" then
    return
  end
  if state.root == path then
    render_chat()
    return
  end
  if state.root then
    save_history()
  end
  state.root = path
  state.turns = load_history(path)
  state.busy = false
  render_chat()
end

function M.open()
  ensure_chat()
  if state.input_win and vim.api.nvim_win_is_valid(state.input_win) then
    vim.api.nvim_set_current_win(state.input_win)
    vim.cmd("startinsert")
  end
end

function M.apply_last()
  apply_last()
end

function M.send_text(text, from_range)
  ensure_chat()
  local extra = text or ""
  if from_range then
    local start_pos = vim.fn.getpos("'<")
    local end_pos = vim.fn.getpos("'>")
    local target = code_buf() or vim.api.nvim_get_current_buf()
    if start_pos[2] > 0 and end_pos[2] > 0 then
      local lines = vim.api.nvim_buf_get_lines(target, start_pos[2] - 1, end_pos[2], false)
      extra = extra .. "\n\nSelección:\n" .. table.concat(lines, "\n")
    end
  end
  send(extra)
end

return M

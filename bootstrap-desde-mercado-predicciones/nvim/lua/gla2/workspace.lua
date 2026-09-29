local M = {}

local state = {
  root = nil,
  sidebar_buf = nil,
  sidebar_win = nil,
  editor_win = nil,
  menu_buf = nil,
  menu_win = nil,
  menu_items = {},
  tree = {},
}

local rel_path
local collect

local ignore = {
  [".git"] = true,
  [".venv"] = true,
  ["venv"] = true,
  ["__pycache__"] = true,
  ["node_modules"] = true,
  [".pytest_cache"] = true,
}

local function data_file()
  local dir = vim.fn.stdpath("data") .. "/gla2"
  vim.fn.mkdir(dir, "p")
  return dir .. "/projects.json"
end

local function read_recent()
  local path = data_file()
  if vim.fn.filereadable(path) == 0 then
    return {}
  end
  local ok, decoded = pcall(vim.json.decode, table.concat(vim.fn.readfile(path), "\n"))
  if not ok or type(decoded) ~= "table" then
    return {}
  end
  return decoded
end

local function remember(path)
  path = vim.fn.fnamemodify(path, ":p"):gsub("[\\/]+$", "")
  local list = { path }
  for _, item in ipairs(read_recent()) do
    if item ~= path and vim.fn.isdirectory(item) == 1 then
      table.insert(list, item)
    end
    if #list >= 8 then
      break
    end
  end
  vim.fn.writefile({ vim.json.encode(list) }, data_file())
end

local function explorer_dialog(kind)
  local body
  if kind == "folder" then
    body = [[
Add-Type -AssemblyName System.Windows.Forms
$d = New-Object System.Windows.Forms.FolderBrowserDialog
$d.Description = 'Elige la carpeta del proyecto'
$d.ShowNewFolderButton = $true
$result = $d.ShowDialog()
if ($result -eq [System.Windows.Forms.DialogResult]::OK -and $d.SelectedPath) {
  Write-Output $d.SelectedPath
}
]]
  else
    body = [[
Add-Type -AssemblyName System.Windows.Forms
$d = New-Object System.Windows.Forms.OpenFileDialog
$d.Title = 'Abrir archivo del proyecto'
$d.Filter = 'Codigo|*.py;*.rs;*.c;*.h;*.lua;*.md;*.json;*.txt|Todos|*.*'
$d.CheckFileExists = $true
if ($d.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
  Write-Output $d.FileName
}
]]
  end
  local out = vim.fn.system({ "powershell", "-STA", "-NoProfile", "-Command", body })
  if vim.v.shell_error ~= 0 then
    vim.notify("No se pudo abrir el explorador.", vim.log.levels.ERROR)
    return nil
  end
  out = vim.trim(out or ""):gsub("\r", "")
  if out == "" then
    return nil
  end
  return vim.split(out, "\n", { plain = true })[1]
end

local function is_code_win(win)
  if not win or not vim.api.nvim_win_is_valid(win) then
    return false
  end
  if win == state.sidebar_win or win == state.menu_win then
    return false
  end
  local buf = vim.api.nvim_win_get_buf(win)
  local name = vim.api.nvim_buf_get_name(buf)
  local bt = vim.bo[buf].buftype
  if bt == "prompt" or bt == "nofile" or bt == "terminal" or bt == "quickfix" then
    return false
  end
  if name == "gla2-chat" or name == "gla2-proyectos" then
    return false
  end
  if name:find("gla2%-chat", 1) or name:find("gla2%-proyectos", 1) then
    return false
  end
  return true
end

local function editor_win()
  if is_code_win(state.editor_win) then
    return state.editor_win
  end
  for _, win in ipairs(vim.api.nvim_list_wins()) do
    if is_code_win(win) then
      state.editor_win = win
      return win
    end
  end
  return nil
end

local function unlock_buffer(buf)
  if not buf or not vim.api.nvim_buf_is_valid(buf) then
    return
  end
  vim.bo[buf].buftype = ""
  vim.bo[buf].modifiable = true
  vim.bo[buf].readonly = false
  vim.bo[buf].swapfile = true
end

local function open_in_editor(path)
  if not path or path == "" then
    return
  end
  if vim.fn.isdirectory(path) == 1 then
    return
  end
  if vim.fn.filereadable(path) ~= 1 then
    vim.notify("No se puede abrir: " .. path, vim.log.levels.WARN)
    return
  end
  vim.opt.mouse = "a"
  local win = editor_win()
  if not win then
    -- Crea el panel de código entre el explorador y el chat.
    if state.sidebar_win and vim.api.nvim_win_is_valid(state.sidebar_win) then
      vim.api.nvim_set_current_win(state.sidebar_win)
      vim.cmd("wincmd l")
    end
    vim.cmd("edit " .. vim.fn.fnameescape(path))
    state.editor_win = vim.api.nvim_get_current_win()
  else
    vim.api.nvim_set_current_win(win)
    vim.cmd("edit " .. vim.fn.fnameescape(path))
    state.editor_win = vim.api.nvim_get_current_win()
  end
  local buf = vim.api.nvim_win_get_buf(state.editor_win)
  unlock_buffer(buf)
  require("gla2.tabs").paint(state.editor_win)
  vim.api.nvim_set_current_win(state.editor_win)
  -- Como en VS Code: al abrir desde el explorador, se puede escribir ya.
  vim.cmd("stopinsert")
  vim.schedule(function()
    if state.editor_win and vim.api.nvim_win_is_valid(state.editor_win) then
      vim.api.nvim_set_current_win(state.editor_win)
      unlock_buffer(vim.api.nvim_win_get_buf(state.editor_win))
      vim.cmd("startinsert")
    end
  end)
end

local function activate_sidebar_line()
  local line = vim.api.nvim_win_get_cursor(0)[1]
  local path = state.tree[line]
  if path then
    open_in_editor(path)
    return
  end
  local text = vim.api.nvim_get_current_line()
  if text:find("modelo", 1, true) or text:find("gla%-2", 1) or text:find("qwen", 1, true) or text:find("r1", 1, true) then
    require("gla2.models").menu()
  else
    M.menu()
  end
end

local function direct_mode()
  if vim.g.gla2_auto_write ~= nil then
    return vim.g.gla2_auto_write == true or vim.g.gla2_auto_write == 1
  end
  return vim.fn.filereadable(vim.fn.stdpath("data") .. "/gla2/auto_write") == 1
end

local function short_path(path)
  if not path or path == "" then
    return ""
  end
  local show = path:gsub("\\", "/")
  if #show > 36 then
    show = "…" .. show:sub(-34)
  end
  return show
end

local function tree_lines()
  local lines = { "  EXPLORER", "" }
  local marks = { { line = 0, group = "Gla2Muted" } }
  local files = {}
  if not state.root then
    table.insert(lines, "  Abre una carpeta")
    table.insert(marks, { line = #lines - 1, group = "Gla2Muted" })
    return lines, marks, files
  end
  table.insert(lines, "  v " .. vim.fn.fnamemodify(state.root, ":t"))
  files[#lines] = state.root
  table.insert(marks, { line = #lines - 1, group = "Gla2Folder" })

  local function walk(dir, depth)
    if depth > 4 or #lines >= 40 then
      return
    end
    local ok, names = pcall(vim.fn.readdir, dir)
    if not ok or type(names) ~= "table" then
      return
    end
    table.sort(names)
    for _, name in ipairs(names) do
      if #lines >= 40 then
        return
      end
      if name:sub(1, 1) ~= "." and not ignore[name] then
        local child = dir .. "\\" .. name
        local indent = string.rep("  ", depth)
        if vim.fn.isdirectory(child) == 1 then
          table.insert(lines, "    " .. indent .. "v " .. name)
          files[#lines] = child
          table.insert(marks, { line = #lines - 1, group = "Gla2Folder" })
          walk(child, depth + 1)
        else
          table.insert(lines, "    " .. indent .. name)
          files[#lines] = child
          table.insert(marks, { line = #lines - 1, group = "Gla2Name" })
        end
      end
    end
  end
  walk(state.root, 1)
  if #lines <= 3 then
    table.insert(lines, "    carpeta vacía")
    table.insert(marks, { line = #lines - 1, group = "Gla2Muted" })
  end
  return lines, marks, files
end

local function paint_sidebar()
  if not state.sidebar_buf or not vim.api.nvim_buf_is_valid(state.sidebar_buf) then
    return
  end
  local theme = require("gla2.theme")
  local models = require("gla2.models")
  local lines, marks, files = tree_lines()
  state.tree = files
  table.insert(lines, "")
  table.insert(lines, "  " .. models.label())
  table.insert(marks, { line = #lines - 1, group = "Gla2Accent" })
  table.insert(lines, "  " .. (direct_mode() and "escritura directa" or "pide confirmación"))
  table.insert(marks, { line = #lines - 1, group = direct_mode() and "Gla2Ok" or "Gla2Warn" })
  table.insert(lines, "")
  table.insert(lines, "  enter  archivo o proyectos")
  table.insert(lines, "  m      modelo")
  table.insert(lines, "  a      carpeta")
  table.insert(marks, { line = #lines - 3, group = "Gla2Muted" })
  table.insert(marks, { line = #lines - 2, group = "Gla2Muted" })
  table.insert(marks, { line = #lines - 1, group = "Gla2Muted" })
  if state.root then
    table.insert(lines, "  " .. short_path(state.root))
    table.insert(marks, { line = #lines - 1, group = "Gla2Muted" })
  end
  vim.bo[state.sidebar_buf].modifiable = true
  vim.api.nvim_buf_set_lines(state.sidebar_buf, 0, -1, false, lines)
  vim.bo[state.sidebar_buf].modifiable = false
  theme.paint(state.sidebar_buf, marks)
  theme.panel(state.sidebar_win, "side")
end

local function close_menu()
  if state.menu_win and vim.api.nvim_win_is_valid(state.menu_win) then
    vim.api.nvim_win_close(state.menu_win, true)
  end
  state.menu_win = nil
  state.menu_buf = nil
  state.menu_items = {}
end

function M.root()
  return state.root
end

function M.editor_win()
  return editor_win()
end

function M.sidebar_win()
  return state.sidebar_win
end

local text_ext = {
  py = true, rs = true, c = true, h = true, lua = true, md = true,
  txt = true, json = true, toml = true, yml = true, yaml = true, ini = true,
}

function rel_path(path)
  local rel = path:sub(#state.root + 2)
  return rel:gsub("\\", "/")
end

function collect(dir, depth, files, limit)
  if depth > 4 or #files >= limit then
    return
  end
  local ok, names = pcall(vim.fn.readdir, dir)
  if not ok or type(names) ~= "table" then
    return
  end
  table.sort(names)
  for _, name in ipairs(names) do
    if #files >= limit then
      return
    end
    if name:sub(1, 1) ~= "." and not ignore[name] then
      local child = dir .. "\\" .. name
      if vim.fn.isdirectory(child) == 1 then
        collect(child, depth + 1, files, limit)
      else
        table.insert(files, child)
      end
    end
  end
end

function M.file_index(query)
  return M.context(query)
end

function M.context(query)
  if not state.root then
    return "(ningún proyecto abierto)"
  end
  local files = {}
  collect(state.root, 1, files, 40)
  local tops = {}
  local ok_top, names = pcall(vim.fn.readdir, state.root)
  if ok_top and type(names) == "table" then
    table.sort(names)
    for _, name in ipairs(names) do
      if name:sub(1, 1) ~= "." and not ignore[name] then
        local child = state.root .. "\\" .. name
        if vim.fn.isdirectory(child) == 1 then
          table.insert(tops, name)
        end
      end
    end
  end
  local needle = (query or ""):lower()
  local lines = {
    "Carpeta de trabajo: " .. state.root,
    "Edita o crea solo dentro de esta carpeta. Las rutas nuevas son relativas a ella.",
    "Si el pedido es un programa nuevo, crea una carpeta/archivo nuevos. No reutilices un subproyecto ajeno.",
    "Si un archivo ya existe y el usuario pide cambiarlo, modifica ese path.",
    "",
  }
  if #tops > 0 then
    table.insert(lines, "Subcarpetas de primer nivel (no mezclar entre sí salvo que el usuario lo pida):")
    for _, name in ipairs(tops) do
      table.insert(lines, "- " .. name .. "/")
    end
    table.insert(lines, "")
  end
  table.insert(lines, "Árbol:")
  for _, path in ipairs(files) do
    table.insert(lines, "- " .. rel_path(path))
  end
  if #files == 0 then
    table.insert(lines, "- (vacía)")
  end
  table.insert(lines, "")
  table.insert(lines, "Contenido relevante:")
  local sent = 0
  for _, path in ipairs(files) do
    if sent >= 2 then
      break
    end
    local rel = rel_path(path):lower()
    local name = rel:match("([^/]+)$") or rel
    local mentioned = needle:find(name, 1, true) or needle:find(rel, 1, true)
    local ext = path:match("%.([%w]+)$")
    if mentioned and ext and text_ext[ext:lower()] and vim.fn.getfsize(path) > 0 and vim.fn.getfsize(path) < 4000 then
      local ok_read, rows = pcall(vim.fn.readfile, path)
      if ok_read and type(rows) == "table" then
        local body = table.concat(rows, "\n")
        if not body:find("\0", 1, true) then
          table.insert(lines, "")
          table.insert(lines, "### " .. rel_path(path))
          table.insert(lines, body)
          sent = sent + 1
        end
      end
    end
  end
  if sent == 0 then
    table.insert(lines, "(sin volcar archivos enteros; usa el árbol)")
  end
  -- Índice ligero: últimas entregas de Gla-2 en este proyecto.
  local engine = vim.g.gla2_engine
  if not engine or engine == "" then
    local here = debug.getinfo(1, "S").source:sub(2)
    engine = vim.fn.fnamemodify(here, ":h:h:h:h")
  end
  local entregas = engine .. "/datos/entregas.jsonl"
  if state.root and vim.fn.filereadable(entregas) == 1 then
    local rows = vim.fn.readfile(entregas)
    local needle = state.root:gsub("[\\/]+$", ""):lower():gsub("\\", "/")
    local matched = {}
    for i = #rows, 1, -1 do
      local ok, row = pcall(vim.json.decode, rows[i])
      if ok and type(row) == "table" then
        local proj = tostring(row.project or ""):gsub("[\\/]+$", ""):lower():gsub("\\", "/")
        if proj ~= "" and (proj:find(needle, 1, true) or needle:find(proj, 1, true)) then
          local paths = row.paths or {}
          table.insert(matched, table.concat(paths, ", ") .. " ← " .. tostring(row.request or ""):sub(1, 80))
          if #matched >= 5 then
            break
          end
        end
      end
    end
    if #matched > 0 then
      table.insert(lines, "")
      table.insert(lines, "Entregas recientes:")
      for i = #matched, 1, -1 do
        table.insert(lines, "- " .. matched[i])
      end
    end
  end
  return table.concat(lines, "\n")
end

function M.open_project(path)
  path = vim.fn.fnamemodify(path, ":p"):gsub("[\\/]+$", "")
  if vim.fn.isdirectory(path) ~= 1 then
    vim.notify("Esa ruta no es una carpeta.", vim.log.levels.ERROR)
    return
  end
  state.root = path
  remember(path)
  vim.cmd("cd " .. vim.fn.fnameescape(path))
  paint_sidebar()
  local ok, chat = pcall(require, "gla2.chat")
  if ok then
    chat.bind_project(path)
  end
end

function M.refresh()
  paint_sidebar()
end

local function after_folder(path)
  if not path then
    return
  end
  M.open_project(path)
  vim.notify("Proyecto: " .. vim.fn.fnamemodify(path, ":t"), vim.log.levels.INFO)
end

local function after_file(path)
  if not path or vim.fn.filereadable(path) ~= 1 then
    return
  end
  M.open_project(vim.fn.fnamemodify(path, ":p:h"))
  open_in_editor(path)
end

function M.open_explorer_folder()
  close_menu()
  after_folder(explorer_dialog("folder"))
end

function M.open_explorer_file()
  close_menu()
  after_file(explorer_dialog("file"))
end

local function choose(item)
  close_menu()
  if not item then
    return
  end
  if item.action == "folder" then
    after_folder(explorer_dialog("folder"))
  elseif item.action == "file" then
    after_file(explorer_dialog("file"))
  elseif item.action == "recent" and item.path then
    M.open_project(item.path)
  end
end

function M.menu()
  close_menu()
  local items = {
    { label = "Abrir carpeta en el explorador", action = "folder" },
    { label = "Abrir archivo en el explorador", action = "file" },
  }
  local current = state.root
  for _, path in ipairs(read_recent()) do
    if path ~= current then
      table.insert(items, {
        label = vim.fn.fnamemodify(path, ":t"),
        action = "recent",
        path = path,
      })
    end
  end
  state.menu_items = items

  local lines = {}
  local width = 38
  table.insert(lines, "")
  for _, item in ipairs(items) do
    local mark = item.action == "recent" and "  · " or "  "
    local text = mark .. item.label
    width = math.max(width, vim.fn.strdisplaywidth(text) + 3)
    table.insert(lines, text)
  end

  state.menu_buf = vim.api.nvim_create_buf(false, true)
  vim.api.nvim_buf_set_lines(state.menu_buf, 0, -1, false, lines)
  vim.bo[state.menu_buf].bufhidden = "wipe"
  vim.bo[state.menu_buf].buftype = "nofile"

  local anchor = state.sidebar_win
  local row, col = 2, 1
  if anchor and vim.api.nvim_win_is_valid(anchor) then
    local pos = vim.api.nvim_win_get_position(anchor)
    row = pos[1] + 4
    col = pos[2] + 2
  end

  state.menu_win = vim.api.nvim_open_win(state.menu_buf, true, {
    relative = "editor",
    row = row,
    col = col,
    width = math.min(width, 54),
    height = #lines,
    style = "minimal",
    border = "rounded",
    title = " Proyectos ",
    title_pos = "center",
  })
  require("gla2.theme").float(state.menu_win)

  local function pick()
    local line = vim.api.nvim_win_get_cursor(0)[1]
    choose(state.menu_items[line - 1])
  end
  vim.keymap.set("n", "<CR>", pick, { buffer = state.menu_buf, silent = true })
  vim.keymap.set("n", "<Esc>", close_menu, { buffer = state.menu_buf, silent = true })
  vim.keymap.set("n", "q", close_menu, { buffer = state.menu_buf, silent = true })
end

function M.open()
  if not (state.sidebar_win and vim.api.nvim_win_is_valid(state.sidebar_win)) then
    local size = require("gla2.layout").sizes()
    vim.cmd("topleft " .. size.side .. "vsplit")
    state.sidebar_win = vim.api.nvim_get_current_win()
    state.sidebar_buf = vim.api.nvim_create_buf(false, true)
    vim.api.nvim_win_set_buf(state.sidebar_win, state.sidebar_buf)
    vim.bo[state.sidebar_buf].buftype = "nofile"
    vim.bo[state.sidebar_buf].bufhidden = "hide"
    vim.bo[state.sidebar_buf].swapfile = false
    vim.bo[state.sidebar_buf].filetype = "gla2projects"
    vim.api.nvim_buf_set_name(state.sidebar_buf, "gla2-proyectos")
    vim.wo[state.sidebar_win].number = false
    vim.wo[state.sidebar_win].signcolumn = "no"
    vim.wo[state.sidebar_win].cursorline = true
    vim.wo[state.sidebar_win].winfixwidth = true
    require("gla2.theme").panel(state.sidebar_win, "side")

    vim.keymap.set("n", "<CR>", activate_sidebar_line, { buffer = state.sidebar_buf, silent = true })
    vim.keymap.set("n", "m", function()
      require("gla2.models").menu()
    end, { buffer = state.sidebar_buf, silent = true })
    vim.keymap.set("n", "a", M.open_explorer_folder, { buffer = state.sidebar_buf, silent = true })
    vim.keymap.set("n", "<LeftMouse>", function()
      vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes("<LeftMouse>", true, false, true), "n", false)
      vim.schedule(activate_sidebar_line)
    end, { buffer = state.sidebar_buf, silent = true })

    for _, win in ipairs(vim.api.nvim_list_wins()) do
      if win ~= state.sidebar_win then
        local buf = vim.api.nvim_win_get_buf(win)
        local name = vim.api.nvim_buf_get_name(buf)
        if name ~= "gla2-chat" and vim.bo[buf].buftype ~= "prompt" then
          state.editor_win = win
          break
        end
      end
    end
  end
  local editor = editor_win()
  if editor then
    require("gla2.tabs").paint(editor)
  end
  require("gla2.layout").apply({
    side = state.sidebar_win,
    chat = nil,
    input = nil,
  })
  paint_sidebar()
  if state.editor_win and vim.api.nvim_win_is_valid(state.editor_win) then
    vim.api.nvim_set_current_win(state.editor_win)
  end
end

return M

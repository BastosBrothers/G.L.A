local chat = require("gla2.chat")
local workspace = require("gla2.workspace")

local M = {}

function M.open_chat()
  chat.open()
end

function M.open_projects()
  workspace.open()
  workspace.menu()
end

function M.ask(args, from_range)
  chat.send_text(args, from_range)
end

function M.open_models()
  require("gla2.models").menu()
end

function M.toggle_auto()
  chat.toggle_auto()
end

function M.apply_last()
  chat.apply_last()
end

function M.undo()
  chat.undo()
end

function M.aprender()
  chat.aprender()
end

function M.run_last()
  chat.run_last()
end

return M

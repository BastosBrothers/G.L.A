if vim.g.loaded_gla2 then
  return
end
vim.g.loaded_gla2 = 1

vim.api.nvim_create_user_command("Gla2", function(opts)
  require("gla2").ask(opts.args, opts.range ~= 0)
end, {
  nargs = "*",
  range = true,
  desc = "Enviar un mensaje a Gla-2",
})

vim.api.nvim_create_user_command("Gla2Projects", function()
  require("gla2").open_projects()
end, { desc = "Abrir el panel de proyectos" })

vim.api.nvim_create_user_command("Gla2Chat", function()
  require("gla2").open_chat()
end, { desc = "Abrir el chat de Gla-2" })

vim.api.nvim_create_user_command("Gla2Model", function()
  require("gla2").open_models()
end, { desc = "Elegir modelo ligero o pesado" })

vim.api.nvim_create_user_command("Gla2Auto", function()
  require("gla2").toggle_auto()
end, { desc = "Activar o quitar la creación directa de archivos" })

vim.api.nvim_create_user_command("Gla2Apply", function()
  require("gla2").apply_last()
end, { desc = "Aplicar el último cambio de Gla-2" })

vim.keymap.set("n", "<leader>gp", function()
  require("gla2").open_projects()
end, { desc = "Menú de proyectos" })

vim.keymap.set("n", "<leader>gc", function()
  require("gla2").open_chat()
end, { desc = "Abrir chat Gla-2" })

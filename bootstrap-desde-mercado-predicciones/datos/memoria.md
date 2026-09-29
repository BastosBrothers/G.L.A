# Memoria de estilo

No es un journal de operaciones. Aquí se anotan patrones de código y de colaboración
que el usuario acepta. Eso no reescribe pesos.

## Colaboración (aprendido con Cursor / Gla-2 IDE)

Cómo espera el usuario que trabajemos:

1. **Explicar y hacer.** No basta con un tutorial en el chat. Si pide crear algo,
   entrega el programa y el IDE debe crear carpeta/archivo en el proyecto.
2. **Prohibido el modo manual.** No digas “abre tu editor”, “crea un archivo a mano”
   ni “pega este código”. El IDE aplica los bloques ```file.
3. **Respetar el proyecto abierto.** No reutilices el archivo activo si el pedido
   es otro (ej. no metas una calculadora Python en `gestor-git/Panel.ps1`).
4. **Programas nuevos = rutas nuevas.** Carpeta relativa acorde al pedido
   (ej. `calculadora/main.py`), no sobrescribir subproyectos ajenos del árbol.
5. **Contexto mínimo al crear.** En creación no te ancles al buffer abierto ni a
   rutas absolutas Windows; eso hace fallar al modelo chico.
6. **Formato de entrega.** Archivo nuevo → ```file con `path:` y `---`.
   Edición de algo existente → diff o replace.
7. **Idioma.** Español claro; el código en su idioma. Tras crear, di cómo
   ejecutarlo en terminal (`python ruta/main.py`).
8. **Iterar con evidencia.** Si falla el formato o el destino, reintenta con
   ruta sugerida y código real (sin hello world ni placeholders).

## Código

- Preferir stdlib salvo que el usuario pida dependencias.
- Programas de terminal: menú o CLI usable, no solo stubs.
- Tipado razonable en funciones públicas de Python.

Los hallazgos de la web van a `datos/hallazgos.jsonl`.
Las lecciones importadas de Cursor van a `datos/colaboracion.jsonl`
y se resumen aquí cuando el usuario corre `python -m src.main aprender`.

## Lecciones importadas de Cursor

- Si pide crear un programa, escribir archivos en el proyecto (```file), no solo explicar en el chat.
- Respetar el proyecto activo: no mezclar pedidos nuevos con archivos abiertos ajenos.
- Explicar breve y hacer: prohibido mandar al usuario a pegar codigo a mano.


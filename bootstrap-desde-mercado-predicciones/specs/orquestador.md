# Orquestador DAG

Neovim llama este mismo contrato por `python -m src.main json` (un objeto JSON por stdin, uno por stdout). El motor no escribe el disco: el plugin aplica el parche tras confirmar.

## Solicitud

```json
{
  "message": "Añade validación al handler",
  "language": "python",
  "selection": "def create_user(payload):\n    ...",
  "diagnostics": ["pyright: missing return type"],
  "pinned_skills": ["python_web"],
  "extra_context": null
}
```

## Pasos

1. Detectar lenguaje (`language` o heurística sobre el texto).
2. Seleccionar skills de instrucción: protocol, pineados, `@skill`, core del lenguaje, dominio por triggers.
3. `resolve(nombres)` expande `depends_on` en orden topológico.
4. Registrar `tools` de las skills activas.
5. Inferencia. Si hay tool call, ejecutar, anexar el resultado y reanudar.
6. Extraer parches del texto final y devolverlos sin aplicarlos al disco (el IDE los aplicará).

## Respuesta

```json
{
  "message": "texto del modelo",
  "language": "python",
  "skills": ["edicion_diff", "python_core", "python_web"],
  "tools_available": ["ejecutar_linter", "buscar_documentacion_web"],
  "tool_trace": [
    {"name": "ejecutar_linter", "arguments": {"language": "python", "code": "..."}, "result": "OK"}
  ],
  "patches": {
    "diffs": ["--- a/app.py\n+++ b/app.py\n..."],
    "replaces": [
      {"path": "app.py", "start_line": 10, "end_line": 14, "content": "..."}
    ]
  }
}
```

## CLI

```text
python -m src.main skill graph python_web
python -m src.main chat
python -m src.main run "explica este handler" --language python --pin python_web
```

## Fuera de alcance aquí

Tree-sitter y Qdrant tienen hueco en `extra_context`: otro proceso puede pegar fragmentos recuperados. El motor no indexa el repo todavía.

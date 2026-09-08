# Protocolos de intercambio

## Function calling

Herramientas de esta fase, compartidas por cualquier skill de lenguaje o dominio:

| nombre | efecto |
|--------|--------|
| `buscar_documentacion_web` | DuckDuckGo; anota `datos/hallazgos.jsonl` |
| `ejecutar_linter` | `ruff`/`py_compile`, `rustc` o `gcc`/`clang` sobre un temporal |
| `crear_skill` | Crea `skills/<nombre>/SKILL.md` si no existe. Pide confirmación |
| `agregar_a_skill` | Añade una sección a una skill existente. Pide confirmación |
| `reescribir_identidad` | Reescribe `datos/identidad.md` y el SYSTEM del Modelfile. Pide confirmación |
| `crear_archivo` | Crea un archivo de texto en el equipo. Pide confirmación |
| `crear_carpeta` | Crea una carpeta en el equipo. Pide confirmación |

Nativo (OpenAI-compatible, Ollama o vLLM):

```json
{"name": "ejecutar_linter", "arguments": {"language": "python", "code": "def f():\n    return 1\n"}}
```

Respaldo si el modelo local no emite `tool_calls`:

```tool
{"name": "buscar_documentacion_web", "arguments": {"query": "fastapi response_model 0.115"}}
```

El orquestador pausa, ejecuta y reanuda con `role=tool`. Máximo 4 rondas.

## Diff unificado

```diff
--- a/src/app.py
+++ b/src/app.py
@@ -1,3 +1,4 @@
+from dataclasses import dataclass
 def main() -> None:
     pass
```

## Reemplazo por rango

```replace
path: src/app.py
start_line: 4
end_line: 6
---
def main() -> int:
    return 0
```

El motor valida el formato. No escribe el archivo: eso queda para el cliente (Neovim, fase posterior).

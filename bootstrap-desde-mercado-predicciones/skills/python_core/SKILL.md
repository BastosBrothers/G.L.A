---
name: python_core
kind: language
language: python
description: Reglas sintácticas y estilo de Python. Se carga sola o como dependencia de cualquier skill python_*.
triggers: [python, pytest, typing]
tools:
  - ejecutar_linter
  - buscar_documentacion_web
---

# Python core

## Estilo
- Python 3.11+ salvo que el usuario pida otra versión.
- Tipado explícito en funciones públicas.
- Errores concretos, no `except Exception` vacío.
- Preferir stdlib antes de añadir dependencias.

## Antes de entregar
- Archivo nuevo o programa desde cero: bloque ```file con el código completo del pedido.
- Editar algo que ya existe: diff o `replace`.
- Si el fragmento no es trivial, llama `ejecutar_linter` con `language=python`.
- No inventes APIs de terceros: si no estás seguro, `buscar_documentacion_web`.
- No entregues hello world ni demos del prompt cuando el usuario pidió otra cosa.

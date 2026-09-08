---
name: c_core
kind: language
language: c
description: Reglas de C (memoria, límites, errores). Base para dominios C futuros.
triggers: [gcc, clang, stdio]
tools:
  - ejecutar_linter
  - buscar_documentacion_web
---

# C core

## Estilo
- C11 salvo que el usuario indique otro estándar.
- Comprobar punteros y tamaños. No desbordar buffers.
- Liberar lo que se reserva en el mismo módulo, o documentar el dueño.
- Errores como código de retorno, no `abort` silencioso.

## Antes de entregar
- Diff o `replace`.
- Validar con `ejecutar_linter` y `language=c` si hay gcc o clang.

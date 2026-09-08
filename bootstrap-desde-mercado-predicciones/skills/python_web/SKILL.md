---
name: python_web
kind: domain
language: python
depends_on:
  - python_core
description: Extiende python_core para servicios HTTP (APIs, handlers, validación de entrada).
triggers: [fastapi, flask, http, endpoint, api]
tools:
  - buscar_documentacion_web
  - ejecutar_linter
---

# Python web

## Alcance
Handlers, esquemas de request/response, errores HTTP y pruebas del contrato.

## Reglas
- Validar entrada en el borde (tipos, campos obligatorios).
- No filtrar secretos ni trazas con tokens.
- Documentar el código de estado y el cuerpo de error.
- Si la librería (FastAPI, Starlette, httpx) puede haber cambiado, llamar `buscar_documentacion_web` antes de fijar firmas.

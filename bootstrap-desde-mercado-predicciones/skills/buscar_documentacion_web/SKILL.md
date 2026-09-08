---
name: buscar_documentacion_web
kind: tool
description: Sub-skill global. Investiga documentación y cambios de API; el hallazgo se registra, no se escribe solo en la skill.
tools: []
---

# buscar_documentacion_web

Herramienta del motor, no un prompt largo.
El modelo la invoca; `src/tools.py` ejecuta la búsqueda y anota `datos/hallazgos.jsonl`.

Promover un hallazgo a una skill es un paso humano o de una fase posterior, para no envenenar el catálogo con texto de la web.

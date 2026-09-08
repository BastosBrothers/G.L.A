# Datos en tres capas

El motor no entrena en esta fase. Las capas existen para no mezclar fuentes.

| Capa | Qué entra | Dónde | Regla |
|------|-----------|--------|--------|
| 1. Semilla | Proyectos de referencia, tests, notas de arquitectura | skills curadas a mano | No se genera sola |
| 2. Diversidad | Variantes de un algoritmo, docs oficiales, repos | Aún no hay ingesta automática | Validar con linter local antes de promover |
| 3. Web | APIs nuevas, firmas que el modelo no conoce | `datos/hallazgos.jsonl` vía `buscar_documentacion_web` | No reescribe `SKILL.md` |

La memoria de estilo (`datos/memoria.md`) es distinta: convenciones que el usuario acepte. El QLoRA (fase 3) solo podrá usar esa capa y parches aceptados, nunca el JSONL crudo de la web.

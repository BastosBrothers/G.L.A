# Gla-2

Motor de un asistente de **programación** autónomo, privado y open source. No es un proyecto de inversión ni de trading.

El trabajo actual es la IA y el motor, no el IDE. Neovim se conectará después al mismo contrato (`EngineRequest` / `EngineResponse`).

| Pieza | Estado |
|-------|--------|
| Inferencia local (Ollama ahora, vLLM después) | En este repo |
| Skills + orquestador DAG + function calling | En este repo |
| Diffs / reemplazo por rango | Protocolo listo; el motor no escribe el disco |
| Plugin Neovim, Tree-sitter, Qdrant | Fuera de alcance hasta estabilizar el motor |

Código y especificación: [`bootstrap-desde-mercado-predicciones/`](bootstrap-desde-mercado-predicciones/)

Criterio de evolución: [`NOTA-DESEMPENO.md`](NOTA-DESEMPENO.md)

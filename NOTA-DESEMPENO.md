# Nota de desempeño — Gla-2

Gla-2 se desarrolla aquí como **motor de programación**, no como estudio de mercados.

## Objetivo

Un orquestador local de skills que resuelva dependencias, llame herramientas y devuelva parches. El modelo base es DeepSeek (Ollama ahora, vLLM cuando haga falta). Sin costo recurrente y sin enviar el código a un proveedor.

## Reglas de este repo

1. Skills primero, LoRA después. Un archivo `SKILL.md` no es fine-tuning.
2. Tres capas de conocimiento, sin mezclarlas:
   - instrucción de skill (curada);
   - hallazgos web (`datos/hallazgos.jsonl`);
   - estilo aceptado (`datos/memoria.md`).
3. La web no reescribe skills sola.
4. El IDE de esta fase es el plugin Neovim en `nvim/`: manda búfer, selección y LSP, y aplica parches tras confirmar. No indexa el repo (Tree-sitter / Qdrant) todavía.
5. Nada de journal de operaciones, lados YES/NO ni pipelines de mercados.

## Siguiente trabajo del motor

- Más dominios que hereden de `*_core`, con el mismo `depends_on`.
- Recuperación de fragmentos (Tree-sitter / Qdrant) solo como relleno de `extra_context`.
- Captura de parches aceptados para un QLoRA futuro, aparte de este proceso.

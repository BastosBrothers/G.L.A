# Motor Gla-2

Asistente de programación local. Esta carpeta es el **motor de IA**: inferencia, skills y orquestador. Neovim y el resto del IDE quedan fuera hasta que este contrato esté estable.

El nombre de la carpeta es histórico (copia desde otro proyecto). El dominio de ese origen ya no vive aquí.

## Qué hace ahora

- Identidad Gla-2 sobre DeepSeek local (Ollama; vLLM más adelante, misma API).
- Skills con kinds: `language`, `domain`, `tool`, `protocol`.
- DAG: `python_web` carga `python_core` antes de entrar al prompt.
- Function calling: `buscar_documentacion_web`, `ejecutar_linter`.
- Salida de cambios como diff o reemplazo por rango. No se escriben archivos.

## Comandos

```text
python -m src.main skill list
python -m src.main skill graph python_web
python -m src.main chat
python -m src.main run "añade tipos a esta función" --language python
```

Ollama:

```text
ollama create gla-2 -f Modelfile
```

## Especificación

- [`specs/skill.schema.md`](specs/skill.schema.md)
- [`specs/orquestador.md`](specs/orquestador.md)
- [`specs/protocolos.md`](specs/protocolos.md)

## Fases

1. Hecho aquí: esquemas, DAG, protocolos de diff y tools, CLI del motor.
2. Seguir en local: más skills de dominio, validación más estricta, contexto por fragmentos.
3. QLoRA solo con código aceptado, no con texto de la web.
4. Qdrant / workers: después. El hueco es `extra_context` en la solicitud.

No mezclar con el proyecto de mercados. Eso no es este repositorio.

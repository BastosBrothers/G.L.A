# Esquema de skill (Fase 1)

Un skill es un directorio `skills/<nombre>/SKILL.md` con frontmatter.
El motor no usa LoRA para activarlos: los resuelve un DAG y los inyecta en el prompt, o los registra como herramientas.

```yaml
name: python_web          # snake_case, único
kind: domain              # language | domain | tool | protocol
language: python          # opcional; obliga el core <language>_core
depends_on:               # skills que el DAG carga antes
  - python_core
tools:                    # sub-skills invocables por function calling
  - buscar_documentacion_web
  - ejecutar_linter
description: Qué hace y cuándo usarlo.
triggers: [fastapi, endpoint]
always: false             # protocol/edicion_diff lo usa
```

## Kinds

| kind | Rol | ¿Cuerpo en el prompt? |
|------|-----|------------------------|
| `language` | Sintaxis y estilo base (`python_core`) | Sí |
| `domain` | Biblioteca o dominio; hereda `depends_on` | Sí, después de sus bases |
| `tool` | Herramienta compartida | No; solo el catálogo de function calling |
| `protocol` | Regla transversal (diffs) | Sí, siempre |

## Herencia

Activar `python_web` resuelve:

1. `python_core`
2. `python_web`

Las herramientas se unen por unión, sin duplicar.
Un ciclo en `depends_on` es error (`CycleError`).

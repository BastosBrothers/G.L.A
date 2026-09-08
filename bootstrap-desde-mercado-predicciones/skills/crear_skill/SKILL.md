---
name: crear_skill
kind: domain
description: Crea o amplía una skill cuando el usuario pide una habilidad nueva, por ejemplo un skill de Next.
triggers: [skill, habilidad, procedimiento]
tools:
  - crear_skill
  - agregar_a_skill
  - buscar_documentacion_web
---

# Crear un skill

Si el usuario pide un skill de un tema, no te quedes en un borrador. Llama `crear_skill` y escribe el archivo.

Ejemplos que deben crear una skill, no solo explicarla:
- "haz un skill de next"
- "crea un skill para FastAPI"
- "quiero un skill de rust async"

## Qué hacer
1. Saca el tema. "skill de next" → nombre `nextjs`.
2. Si la skill ya existe, usa `agregar_a_skill`. No la pises.
3. Si no existe, llama `crear_skill` con nombre, description, triggers y body.
4. Si la librería puede haber cambiado, llama `buscar_documentacion_web` antes de fijar APIs.
5. Tras la herramienta, di la ruta `skills/<nombre>/SKILL.md` y para qué queda activa.

## Cómo rellenarla
- `kind`: `domain`, salvo que sea la base de un lenguaje (`language`).
- `language`: `python`, `rust` o `c` solo si existe un core. Next, React o TypeScript van con `language` vacío: no hay `typescript_core`.
- `depends_on`: el core si existe (`python_web` → `python_core`). Si no hay core, lista vacía. No inventes un core.
- `triggers`: el nombre del stack y 2 o 3 alias reales (`next`, `nextjs`, `app router`).
- `body`: instrucciones para programar ese tema, no un ensayo. Incluye estructura, reglas y qué no inventar.

## Plantilla
```markdown
---
name: nextjs
kind: domain
depends_on: []
description: App Router de Next.js. Usar al crear o editar una app Next.
triggers: [next, nextjs, app router]
---

# Next.js

## Estructura
- App Router: `app/layout.tsx`, `app/page.tsx`, `app/api/.../route.ts`.
- Un componente de cliente solo si usa estado, efectos o eventos (`"use client"`).
- Datos y secretos en el servidor. No expongas claves en el cliente.

## Reglas
- TypeScript. No inventes props ni rutas de `next/*`.
- Si cambió la API de Next, llama `buscar_documentacion_web` antes de fijar firmas.
- Formularios y mutaciones en Server Actions o route handlers, no en un fetch suelto al cliente si basta el servidor.
```

## Nombre
snake_case, sin rutas. "next" y "next.js" → `nextjs`. "react native" → `react_native`.

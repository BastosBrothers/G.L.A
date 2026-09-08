---
name: nextjs
kind: domain
depends_on: []
tools:
  - ejecutar_linter
  - buscar_documentacion_web
description: App Router de Next.js. Usar al crear o editar una app Next.
triggers:
  - next
  - nextjs
  - app router
always: false
---

# Next.js

## Estructura
- App Router: `app/layout.tsx`, `app/page.tsx`, `app/api/.../route.ts`.
- Un componente de cliente solo si usa estado, efectos o eventos del navegador. Lleva `"use client"`.
- Datos y secretos en el servidor. No expongas claves en el cliente.

## Reglas
- TypeScript. No inventes props ni rutas de `next/*`.
- Formularios y mutaciones en Server Actions o route handlers si basta el servidor.
- Enlaces internos con `next/link`. Imagenes con `next/image` si el proyecto ya lo usa.
- Si cambio la API de Next, llama `buscar_documentacion_web` antes de fijar firmas.

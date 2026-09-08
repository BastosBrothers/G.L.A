---
name: postgresql
kind: domain
depends_on: []
tools:
  - ejecutar_linter
  - buscar_documentacion_web
description: Esquema, consultas parametrizadas e indices de PostgreSQL. Usar al escribir SQL o acceso a Postgres.
triggers:
  - postgresql
  - postgres
  - psql
  - sql
always: false
---

# PostgreSQL

## Alcance
Consultas, esquema, indices y acceso desde la aplicacion. No inventes columnas ni tipos.

## Esquema
- Nombres en snake_case. Claves primarias explicitas.
- Tipos reales: text, integer, bigint, numeric, boolean, timestamptz, uuid, jsonb.
- Fechas en timestamptz, no timestamp sin zona.
- Claves foraneas con ON DELETE explicito.

## Consultas
- Parametros, nunca concatenar entrada del usuario en el SQL.
- SELECT solo de las columnas que hacen falta.
- LIMIT en listados. Un indice para el filtro y el orden mas usados.
- Transaccion si hay mas de un INSERT o UPDATE que deben quedar juntos.

## Reglas
- Si no viste el esquema, dilo y no inventes tablas.
- Migraciones incrementales, no un DROP de produccion.
- Si la version de Postgres o del driver puede haber cambiado, llama `buscar_documentacion_web`.

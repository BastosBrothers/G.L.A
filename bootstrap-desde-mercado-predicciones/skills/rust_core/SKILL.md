---
name: rust_core
kind: language
language: rust
description: Reglas de Rust (ownership, Result, tipos). Base para dominios Rust futuros.
triggers: [rust, cargo, crate]
tools:
  - ejecutar_linter
  - buscar_documentacion_web
---

# Rust core

## Estilo
- `Result`/`Option` en fronteras; no `unwrap` en código de biblioteca.
- `thiserror` o errores propios solo si el usuario ya usa esa crate.
- Sin `unsafe` salvo que el usuario lo pida y se justifique.

## Antes de entregar
- Diff o `replace`.
- Validar con `ejecutar_linter` y `language=rust` si hay `rustc`.

---
name: python_ui_ux
kind: domain
language: python
depends_on:
  - python_core
description: UI/UX y área de usuario en Python (escritorio, TUI y UIs simples). Usar al diseñar interfaces usables, no solo lógica.
triggers:
  - ui
  - ux
  - interfaz
  - usuario
  - tkinter
  - customtkinter
  - textual
  - rich
  - streamlit
  - gradio
  - pysimplegui
  - formularios
  - pantalla
  - ventana
  - dashboard
tools:
  - buscar_documentacion_web
  - ejecutar_linter
---

# Python UI / UX (área de usuario)

## Cuándo
Pedidos de interfaz, menús visuales, formularios, paneles, dashboards ligeros,
apps de escritorio o TUI en Python. No sustituye `python_web` para APIs HTTP puras.

## Stack preferido (elige uno y sé consistente)
1. **Escritorio simple:** `tkinter` (stdlib) o `customtkinter` si el usuario pide look moderno.
2. **Terminal rica:** `rich` para salida; `textual` si es app TUI interactiva.
3. **UI web rápida local:** `streamlit` o `gradio` solo si el usuario lo pide o encaja el caso.
4. No metas PyQt/PySide salvo que el usuario lo pida (más peso y APIs frágiles).

Si la librería puede haber cambiado, llama `buscar_documentacion_web` antes de fijar widgets o firmas.

## UX (obligatorio)
- Un flujo claro: qué hace la pantalla, qué puede hacer el usuario, qué pasa después.
- Textos en **español** en la UI (botones, labels, errores, ayuda), salvo que pida otro idioma.
- Errores entendibles junto al control que falló; no traces crudas al usuario final.
- Confirmación antes de borrar o sobrescribir datos.
- Estados vacíos útiles (“aún no hay ítems; pulsa Añadir”).
- Atajos o Enter para la acción principal cuando sea natural.
- No satures: una tarea principal por vista; evita paredes de opciones.
- Contraste y jerarquía: título → acción principal → secundarias.
- Feedback inmediato (mensaje, deshabilitar botón mientras carga, spinner textual).

## Estructura de código
- Separar **lógica** (modelo/servicios) de **vista** (widgets / layout).
- Nombres claros: `build_window`, `on_submit`, `refresh_list`.
- Tipado en funciones públicas.
- Archivo nuevo → bloque ```file con path relativo (ej. `app_ui/main.py`).
- Si hay varios archivos: `main.py` (arranque), `ui.py` (vista), `services.py` (lógica).

## Reglas técnicas
- Preferir stdlib (`tkinter`) si basta; no añadas dependencias sin decirlo.
- No bloquees el hilo de UI con trabajo largo: usa after/threads con cuidado o indica “procesando…”.
- Validar entrada en el borde (tipos, rangos, campos vacíos) antes de llamar a la lógica.
- No inventes APIs de widgets; si dudas, documenta o busca.
- Entrega ejecutable: cómo abrir la UI (`python app_ui/main.py`) y qué debe verse.

## No hacer
- Hello world o demos del prompt cuando pidieron una UI real.
- Meter la interfaz dentro de un subproyecto ajeno (respetar carpeta de trabajo).
- Decir “abre el editor y pega el código”: el IDE crea los ```file.
- Copiar layouts genéricos sin adaptar al pedido del usuario.

# Ingeniería de prompt de Gla-2

Desglose de **cómo se construye lo que ve el modelo** en cada turno: capas, modos, pases y por qué cada pieza existe.  
Código fuente: [`src/context.py`](../src/context.py), [`src/orchestrator.py`](../src/orchestrator.py), [`src/main.py`](../src/main.py), [`Modelfile`](../Modelfile).

---

## 1. Vista general

Gla-2 no manda “un solo prompt estático”. Apila **varias capas** y, según el modo, **recorta** herramientas, skills y contexto del IDE.

```text
┌─────────────────────────────────────────────────────────────┐
│  Capa 0 — Modelfile Ollama (identidad base del modelo gla-2)│
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Capa 1 — SYSTEM_ROLE (contrato fijo del motor)             │
│  + Leyes + Identidad + Reloj + Skills + Tools + Memoria…    │
│  + apéndice de modo (charla | creación | edición)           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Capa 2 — mensaje usuario                                   │
│  pedido limpio + selección + diagnósticos + extra_context  │
│  (extra_context lo filtra el IDE / main.json según el modo) │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
           chat            create            edit
        (sin tools)    (sin tools,       (tools + skills
                         ```file,         DAG, linter…)
                         dual-pass)
```

El modelo efectivo lo elige [`models_route.model_for_mode`](../src/models_route.py): **charla → `gla-2`**, **creación → `qwen2.5-coder:3b`** (salvo override). El **pase B** (explicación) usa `model_for_explain` → `gla-2`. Create usa `build_create_system_prompt` (system slim ~20% del system completo).

---

## 2. Capa 0 — Modelfile (Ollama)

Archivo: `Modelfile`. Base actual: `qwen2.5-coder:1.5b` empaquetada como `gla-2`.

Incluye solo lo que debe sobrevivir **fuera** del orquestador (chat crudo de Ollama):

- Identidad: “eres Gla-2”, español, no fingir ser otro proveedor.
- Contrato mínimo de creación: frase → bloque(s) ```file → cómo probar.
- Prohibición de hello world / demos.
- Aviso de que skills/tools viven en `python -m src.main chat`, no en el chat crudo.

Esa capa es **corta a propósito**: el motor reinyecta el system completo en cada turno vía API.

---

## 3. Capa 1 — System prompt del motor

Función: `build_system_prompt()` en `context.py`.

### 3.1 Bloque fijo `SYSTEM_ROLE`

Instrucciones permanentes:

| Tema | Qué impone |
|------|------------|
| Rol | Asistente de programación local; explicar + hacer |
| Identidad | Solo Gla-2; nunca DeepSeek/ChatGPT/… |
| Skills | Seguir skills activas del DAG por encima de intuición genérica |
| Function calling | Solo si hace falta; nombres permitidos listados; no pegar JSON de tools en el chat |
| Creación | ```file con `path:` + `---` + código; rutas relativas nuevas; no pisar subproyectos ajenos |
| Edición | Diff unificado o ```replace por rangos |
| Estilo | Español en prosa; no inventar APIs ni fuentes falsas |

### 3.2 Secciones ensambladas (en orden)

1. **Leyes** (`datos/leyes.md` / `leyes.py`) — no reescribibles (verdad, no daño, secretos, consentimiento, etc.).
2. **Identidad editable** (`datos/identidad.md`) — tono/persona; el modelo puede cambiarla con herramienta, no las leyes.
3. **Reloj** — fecha/hora local (evita “hoy” inventado).
4. **Lenguaje de la solicitud** — python / rust / c / inferido.
5. **Catálogo de skills** — lista corta de todas las skills instaladas.
6. **Skills activos este turno** — cuerpo de las skills resueltas por el DAG (vacío en modo charla).
7. **Herramientas invocables** — catálogo filtrado (vacío en charla y en creación).
8. **Memoria de estilo** (`datos/memoria.md`) — patrones aceptados por el usuario.
9. **Pesos propios** — resumen de balances internos (no entrenan el base model).
10. **Aprendizajes de sandbox** — solo formas que validaron.

### 3.3 Apéndices de modo (orquestador)

Tras armar el system base, `orchestrator.run` añade:

**Modo charla**

- Respuesta breve en español.
- Sin herramientas, sin ```file, sin inventar skills.

**Modo creación**

- Contrato fijo: (1) 1–2 frases → (2) bloque(s) ```file → (3) cómo ejecutar.
- El IDE escribe: **prohibido** “abre el editor / pega a mano”.
- Sin stubs, hello world, rutas absolutas, `.ps1` si pidió Python.
- Si `_wants_multi_file`: varios ```file; prohibido fusionar en un `app/main.py` vacío.

**Modo edición** (sin apéndice extra de “modo”; usa system completo + tools)

- Skills DAG + tools (linter, docs, skills, escritura con confirmación).

---

## 4. Capa 2 — Mensaje de usuario

Función: `build_user_message()`.

```text
[mensaje del usuario, sin directivas /skill basura]

## Selección / fragmento   (si hay)
## Diagnósticos            (si hay)
## Contexto adicional      (extra_context)
```

### 4.1 Quién fabrica `extra_context`

**IDE (Neovim)** — `nvim/lua/gla2/chat.lua`:

| Situación | Qué manda |
|-----------|-----------|
| Creación simple | Nombre de proyecto + “crea solo archivos nuevos” (sin árbol gigante) |
| Creación + recall (“retomemos…”) | Historial de turnos (obligatorio) |
| Edición / no creación | Índice ligero del árbol + archivos mencionados + entregas recientes |
| Charla | Casi vacío |

**Puerta JSON** — `main.cmd_json`:

| Modo | Transformación |
|------|----------------|
| `create` | Tira árbol/Panel.ps1; deja instrucción corta + historial si venía + entregas del proyecto |
| `edit` / otro | Prefija proyecto activo y archivo abierto (solo como referencia de edición) |

**Orquestador (create)** — refuerza otra vez:

- Entregas recientes (`entregas.recent_for_project`).
- Si multi: pide N bloques ```file.
- Si no multi: “Usa esta ruta relativa: `{suggest}`” + formato path/---.

Así se evita que el modelo **1.5b/3b** copie rutas absolutas Windows o el buffer abierto (p. ej. `Panel.ps1`).

---

## 5. Clasificación de intención (antes del prompt)

Heurísticas en `orchestrator.py` (sobre el mensaje limpio):

| Detector | Efecto en el prompt |
|----------|---------------------|
| `is_conversational` | Fuerza modo **chat**; sin skills/tools/extra útil |
| `wants_code_creation` | Modo **create**; system de creación; sin tools |
| Ninguno de los anteriores | Modo **edit**; skills + tools |
| `_wants_multi_file` | Texto extra multi + no fusionar paths |
| `_suggest_create_path` | Ruta sugerida (`calculadora/main.py`, `ejercicios/01_…`, o `app/main.py`) |

El IDE también manda `mode` en el JSON; el orquestador puede **reforzar** chat/create si el texto lo deja claro.

---

## 6. Pases de inferencia (creación)

No es un solo completion:

```text
Pase A — código
  system (creación) + user (pedido + ruta/multi)
  → texto con ```file
  → extract_patches
  → filtros: stubs, tutoriales manuales, paths raros
  → si falla calidad: REINTENTO limpio (un system corto + “path: {suggest}”)

Pase B — explicación (solo si hay archivos reales)
  system: “2–3 frases, cómo ejecutar; sin ```file; el IDE ya escribe”
  → prosa
  → si sale tutorial/demo/JSON: prosa plantilla
  → mensaje final = prosa + fences reconstruidos desde patches del pase A
```

**Diseño clave:** los patches que aplica el IDE salen del **pase A** (o del reintento). El pase B **no regenera código**, solo la explicación. Así se evita que un segundo completion borre un programa bueno con un stub.

En creación: `num_predict` alto (~1400). En charla/edición: default del cliente.

---

## 7. Post-proceso del texto (no es “prompt”, pero cierra el contrato)

Tras la respuesta del modelo:

1. `clean_model_text` / `strip_tool_dumps` — quita basura de tools.
2. `extract_patches` — ```file, ```diff, ```replace.
3. Descarte de stubs (`_is_stub_content`).
4. `_normalize_create_paths` — corrige `main.py` suelto o paths ajenos; en multi no fusiona todo a una sola ruta.
5. Sustitución de tutoriales tipo “abre tu editor…” si ya hay patches.
6. Respuesta JSON al IDE: `message` + `patches` (el motor **no** escribe disco).

---

## 8. Por qué está partido así

| Problema observado | Respuesta de ingeniería |
|--------------------|-------------------------|
| Modelo chico copia el archivo abierto | Create con contexto mínimo; no mandar árbol completo |
| Responde tutorial en vez de código | Contrato ```file + rechazo de tutoriales + dual-pass |
| Stub `pass` / “aquí puedes agregar” | Filtro de stubs + reintento |
| Charla dispara tools o skills | Modo chat: skills/tools vacíos + apéndice “solo conversa” |
| Explicación reescribe el código a peor | Pase B solo prosa; patches congelados del pase A |
| Multi-archivo colapsa a un main vacío | Señales multi en system + user; normalización distinta |

---

## 9. Mapa rápido archivo → responsabilidad

| Archivo | Rol en el prompt |
|---------|------------------|
| `Modelfile` | Identidad base Ollama |
| `src/context.py` | `SYSTEM_ROLE` + ensamblado system/user |
| `src/leyes.py` / `datos/leyes.md` | Suelo no editable |
| `datos/identidad.md` | Persona editable |
| `datos/memoria.md` | Estilo / colaboración aceptada |
| `skills/*/SKILL.md` | Instrucciones de dominio cuando el DAG las activa |
| `src/orchestrator.py` | Modos, multi, suggest path, pases A/B, filtros |
| `src/main.py` (`json`) | Filtro de `extra_context` desde el IDE |
| `src/models_route.py` | Qué checkpoint Ollama habla en cada modo |
| `nvim/lua/gla2/chat.lua` | Qué contexto arma el IDE antes de llamar al motor |

---

## 10. Ejemplo mínimo (modo create)

**System (resumido):** SYSTEM_ROLE + leyes + identidad + “Modo creación: frase + ```file + cómo correr”.  
**User (resumido):**

```text
Hagamos una calculadora en python

## Contexto adicional

Proyecto: mi-app. Modo creación: ...
Usa esta ruta relativa: calculadora/main.py
Formato obligatorio: bloque ```file, path:, ---, código...
```

**Salida esperada del pase A:** uno o más bloques ```file válidos.  
**Salida al usuario (pase B + fences):** prosa corta + los mismos fences para que el IDE aplique.

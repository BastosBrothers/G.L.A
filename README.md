# G.L.A. (Gla-2)

**Asistente de programación autónomo, privado y local.**  
Motor de IA + IDE en Neovim. Inferencia en tu máquina (Ollama). Sin enviar tu código a la nube.

Repositorio: [BastosBrothers/G.L.A](https://github.com/BastosBrothers/G.L.A)

---

## Licencia y uso — lectura obligatoria

Este proyecto es **open source / código abierto**: puedes verlo, estudiarlo, modificarlo y usarlo.

**No está permitido usarlo con fines monetarios.**  
Queda **prohibido** explotarlo comercialmente, venderlo, cobrarlo como servicio, incluirlo en productos de pago o monetizar derivados sin autorización explícita y por escrito de los autores.

Resumen:

| Permitido | No permitido |
|-----------|--------------|
| Uso personal y educativo | Uso comercial o lucrativo |
| Estudiar y modificar el código | Vender el software o cobros por acceso |
| Compartir mejoras bajo la misma licencia | Integrarlo en un producto de pago sin permiso |
| Experimentar en local | Monetizar marcas, SaaS o consultoría “con G.L.A.” como producto |

Ver el archivo [`LICENSE`](LICENSE) completo.

---

## Finalidad

G.L.A. (motor **Gla-2**) nace para:

1. **Programar en local**, con privacidad: el modelo corre en tu PC.
2. **Orquestar skills** (habilidades modulares) con un DAG de dependencias.
3. **Entregar código real** al proyecto (bloques ` ```file `, diffs, replaces), no solo tutoriales en el chat.
4. Ofrecer un **IDE ligero en Neovim**: explorador, chat, escritura de archivos y feedback visual.

No es un proyecto de trading, mercados ni finanzas. El nombre de la carpeta interna es histórico.

---

## Qué incluye

### Motor (`bootstrap-desde-mercado-predicciones/`)

| Pieza | Función |
|-------|---------|
| `src/orchestrator.py` | Orquesta el turno: skills, tools, modos charla/creación, dual-pass explicar+hacer |
| `src/context.py` | System prompt, identidad, memoria, catálogo de skills |
| `src/skills.py` + `skills/` | Skills (`language`, `domain`, `tool`, `protocol`) |
| `src/diff.py` | Extrae ` ```file `, diffs y replaces |
| `src/main.py` | CLI: `chat`, `run`, `json`, `sandbox`, `skill`, `aprender` |
| `src/sandbox.py` | Pruebas multi-estilo y aprendizajes validados |
| `src/colaboracion.py` | Importa lecciones desde transcripts de Cursor → memoria |
| `Modelfile` | Modelo Ollama `gla-2` (base coder local) |
| `datos/` | Identidad, memoria de estilo, colaboración, pesos propios |

### IDE Neovim (`bootstrap-desde-mercado-predicciones/nvim/`)

| Pieza | Función |
|-------|---------|
| Chat + input | Hablar con Gla-2; spinner “trabajando” |
| Explorador | Abrir proyecto y archivos |
| Aplicación de parches | Crea carpetas/archivos del bloque ` ```file ` |
| Modo creación | Contexto mínimo; no pisa subproyectos ajenos; rechaza stubs vacíos |
| Temas / layout | UI tipo VS Code oscuro |

### Skills destacadas

- `python_core`, `python_web`, `python_ui_ux` — Python, APIs e interfaces
- `edicion_diff` — protocolo de parches
- `crear_skill` — crear/ampliar skills
- `postgresql`, `nextjs`, `rust_core`, `c_core`
- Tools: `buscar_documentacion_web`, `ejecutar_linter`

---

## Requisitos

- Python 3.11+
- [Ollama](https://ollama.com/) con modelo `gla-2` (o el configurado)
- Neovim (para el IDE)
- Dependencias: `bootstrap-desde-mercado-predicciones/requirements.txt`

---

## Puesta en marcha rápida

```text
cd bootstrap-desde-mercado-predicciones
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # o crea .env con la API de Ollama si aplica

ollama create gla-2 -f Modelfile
python -m src.main skill list
python -m src.main chat
```

### IDE

```text
iniciar-gla2.cmd
```

Configura el `init.lua` de Neovim apuntando a esta carpeta (`vim.g.gla2_engine`, `runtimepath`).

### Aprender de sesiones Cursor

```text
python -m src.main aprender
```

Importa lecciones de colaboración a `datos/colaboracion.jsonl` y actualiza `datos/memoria.md`.

---

## Cómo trabaja (flujo)

```text
Usuario (IDE o CLI)
    → EngineRequest (mensaje, lenguaje, contexto, modo)
    → Orquestador (skills DAG + prompt)
    → Modelo local (gla-2 / Ollama)
    → EngineResponse (texto + patches.files / diffs / replaces)
    → IDE aplica archivos en el proyecto (creación automática en modo create)
```

Principios de colaboración (memoria del proyecto):

- **Explicar y hacer**: no solo tutoriales; escribir archivos.
- **Respetar el proyecto abierto**: no mezclar subcarpetas ajenas.
- **Programas nuevos → rutas nuevas** (`calculadora/main.py`, etc.).
- **Sin uso comercial** del proyecto G.L.A. en sí (ver licencia).

---

## Versiones y snapshots

G.L.A. se publica en dos capas: **versión** (estable) y **snapshot** (punto intermedio).

### Versión (p. ej. `2.0`, rama `v2.0`)

La versión del producto sube cuando **una serie de snapshots se vuelve estable**: ya no es un experimento suelto, sino un conjunto coherente y usable.

Ejemplo: varias snapshots `A…`, `B…` y `C…` maduran → se corta **G.L.A. 2.0**.

### Snapshot

Una snapshot marca un cambio concreto **antes** (o entre) versiones estables. El nombre indica **qué tipo de cambio**, **cuándo** y **a qué versión pertenece**.

#### Tipos (letra)

| Letra | Qué cubre |
|-------|-----------|
| **A** | Funcionalidades de la IA (motor, orquestación, prompts, modos create/chat, etc.) |
| **B** | Cambios en el IDE en sí (Neovim: chat, explorador, aplicar parches, UX) |
| **C** | Recepción de skills, sandbox o formas de entrenamiento de la IA |
| **X** | Cambios muy grandes o de contenido variado (varias áreas a la vez) |

#### Números que acompañan la letra

Tras la letra van, en este orden:

1. **Fecha** — día, mes y año en dos dígitos cada uno: `DDMMAA`
2. **Versión** — la versión G.L.A. a la que pertenece esa snapshot (p. ej. `2.0`)

```text
{letra}{DDMMAA}{versión}
```

#### Ejemplo

`A2809262.0`

| Parte | Valor | Significado |
|-------|-------|-------------|
| Tipo | `A` | Snapshot de funcionalidades de la IA |
| Fecha | `280926` | 28 / 09 / 2026 |
| Versión | `2.0` | Pertenece a G.L.A. **2.0** |

Otros ejemplos:

- `B2809262.0` — cambio de IDE el 28/09/2026, en la línea 2.0  
- `C0110262.0` — skills / sandbox / entrenamiento el 01/10/2026, línea 2.0  
- `X1510262.1` — cambio grande y mixto el 15/10/2026, línea 2.1  

Cuando varias snapshots de una línea se consideran estables, sube la **versión** (p. ej. de `2.0` a `2.1`) y las snapshots nuevas llevan ya ese número.

---

## Documentación adicional

- [`NOTA-DESEMPENO.md`](NOTA-DESEMPENO.md) — criterios de evolución del motor
- [`bootstrap-desde-mercado-predicciones/ORIGEN.md`](bootstrap-desde-mercado-predicciones/ORIGEN.md) — origen del motor
- [`bootstrap-desde-mercado-predicciones/specs/`](bootstrap-desde-mercado-predicciones/specs/) — orquestador, skills, protocolos

---

## Contribuciones

Se aceptan mejoras educativas y técnicas **sin ánimo de lucro**. Al contribuir, aceptas que el código se publica bajo la misma licencia no comercial.

---

## Autores / org

[BastosBrothers](https://github.com/BastosBrothers) — proyecto **G.L.A.**

**Open source. Uso personal y educativo. Sin fines monetarios.**

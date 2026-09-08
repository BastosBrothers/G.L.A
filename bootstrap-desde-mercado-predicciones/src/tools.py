"""Herramientas compartidas (sub-skills) invocables por function calling."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from src.paths import HALLAZGOS_PATH
from src.research import format_research, search_web
from src.fs_ops import crear_archivo, crear_carpeta
from src.self_edit import agregar_a_skill, crear_skill, reescribir_identidad


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., str]


def _record_finding(tool: str, query: str, summary: str) -> None:
    HALLAZGOS_PATH.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "tool": tool,
        "query": query,
        "summary": summary[:2000],
    }
    with HALLAZGOS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def buscar_documentacion_web(query: str, max_results: int = 5) -> str:
    """Investiga docs/APIs en la web y guarda el hallazgo (no reescribe la skill)."""
    hits = search_web(query, max_results=max_results)
    block = format_research(query, hits)
    _record_finding("buscar_documentacion_web", query, block)
    return block


def ejecutar_linter(language: str, code: str, path: str | None = None) -> str:
    """
    Valida sintaxis/estilo de un fragmento en local.
    No modifica el árbol del usuario: escribe un temporal y lo borra.
    """
    lang = (language or "").strip().lower()
    snippet = code or ""
    if not snippet.strip():
        return "No hay código para validar."

    suffix = { "python": ".py", "rust": ".rs", "c": ".c" }.get(lang)
    if suffix is None:
        return f"Linter no configurado para `{lang}`. Soportados: python, rust, c."

    with tempfile.TemporaryDirectory(prefix="gla2-lint-") as tmp:
        target = Path(tmp) / f"snippet{suffix}"
        if path:
            target = Path(tmp) / Path(path).name
        target.write_text(snippet, encoding="utf-8")
        return _run_linter(lang, target)


def _run_linter(language: str, path: Path) -> str:
    if language == "python":
        if shutil.which("ruff"):
            cmd = ["ruff", "check", str(path)]
        else:
            cmd = ["python", "-m", "py_compile", str(path)]
    elif language == "rust":
        if not shutil.which("rustc"):
            return "rustc no está en PATH; no se pudo validar."
        cmd = ["rustc", "--edition", "2021", "--emit", "metadata", "-o", "nul", str(path)]
    else:
        compiler = shutil.which("gcc") or shutil.which("clang")
        if not compiler:
            return "gcc/clang no están en PATH; no se pudo validar."
        cmd = [compiler, "-fsyntax-only", str(path)]

    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return "El linter excedió 30 s."

    output = (completed.stdout or "") + (completed.stderr or "")
    output = output.strip() or "(sin salida)"
    status = "OK" if completed.returncode == 0 else f"FALLO ({completed.returncode})"
    return f"{status}\ncomando: {' '.join(cmd)}\n{output}"


def _schema_object(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


TOOL_SPECS: dict[str, ToolSpec] = {
    "buscar_documentacion_web": ToolSpec(
        name="buscar_documentacion_web",
        description=(
            "Busca documentación o cambios de API en la web. "
            "Úsala si falta contexto o la librería es reciente. No inventes APIs."
        ),
        parameters=_schema_object(
            {
                "query": {
                    "type": "string",
                    "description": "Consulta concreta: librería, símbolo, versión.",
                }
            },
            ["query"],
        ),
        handler=lambda query, **_: buscar_documentacion_web(query),
    ),
    "ejecutar_linter": ToolSpec(
        name="ejecutar_linter",
        description=(
            "Valida un fragmento con un linter local antes de entregar el cambio. "
            "Úsala cuando propongas código no trivial."
        ),
        parameters=_schema_object(
            {
                "language": {"type": "string", "description": "python | rust | c"},
                "code": {"type": "string", "description": "Código completo a validar."},
                "path": {
                    "type": "string",
                    "description": "Nombre de archivo opcional, solo para el temporal.",
                },
            },
            ["language", "code"],
        ),
        handler=lambda language, code, path=None, **_: ejecutar_linter(
            language, code, path
        ),
    ),
    "crear_skill": ToolSpec(
        name="crear_skill",
        description=(
            "Crea una skill nueva en skills/<nombre>/SKILL.md. "
            "Úsala cuando el usuario pida enseñar una habilidad. No pisa una existente."
        ),
        parameters=_schema_object(
            {
                "name": {"type": "string", "description": "snake_case, sin rutas."},
                "description": {"type": "string", "description": "Cuándo usarla."},
                "body": {"type": "string", "description": "Markdown de instrucciones."},
                "kind": {"type": "string", "description": "language | domain | protocol"},
                "language": {
                    "type": "string",
                    "description": "python, rust, c, typescript, javascript o vacío si no hay core.",
                },
                "depends_on": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Skills base que el DAG debe cargar antes.",
                },
                "triggers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Palabras que activan la skill.",
                },
            },
            ["name", "description", "body"],
        ),
        handler=lambda name, description, body, kind="domain", language=None, depends_on=None, triggers=None, **_: crear_skill(
            name,
            description,
            body,
            kind=kind,
            language=language,
            depends_on=depends_on,
            triggers=triggers,
        ),
    ),
    "agregar_a_skill": ToolSpec(
        name="agregar_a_skill",
        description=(
            "Añade una sección al final de una skill existente. No sustituye el archivo."
        ),
        parameters=_schema_object(
            {
                "name": {"type": "string", "description": "Skill existente."},
                "titulo": {"type": "string", "description": "Título de la sección nueva."},
                "texto": {"type": "string", "description": "Texto a añadir."},
            },
            ["name", "titulo", "texto"],
        ),
        handler=lambda name, titulo, texto, **_: agregar_a_skill(name, titulo, texto),
    ),
    "reescribir_identidad": ToolSpec(
        name="reescribir_identidad",
        description=(
            "Reescribe la identidad editable del modelo (datos/identidad.md y SYSTEM del Modelfile). "
            "No borra las leyes de suelo ni cambia src/."
        ),
        parameters=_schema_object(
            {
                "texto": {
                    "type": "string",
                    "description": "Nueva identidad, en español, sin contradecir las leyes.",
                }
            },
            ["texto"],
        ),
        handler=lambda texto, **_: reescribir_identidad(texto),
    ),
    "crear_archivo": ToolSpec(
        name="crear_archivo",
        description=(
            "Propone crear un archivo de texto en el equipo del usuario. "
            "El motor pide confirmación antes de escribir. Sin un sí, no crea nada."
        ),
        parameters=_schema_object(
            {
                "ruta": {"type": "string", "description": "Ruta absoluta o relativa al motor."},
                "contenido": {"type": "string", "description": "Texto del archivo."},
                "sobrescribir": {
                    "type": "boolean",
                    "description": "True solo si el usuario acepta reemplazar un archivo que ya existe.",
                },
            },
            ["ruta"],
        ),
        handler=lambda ruta, contenido="", sobrescribir=False, **_: crear_archivo(
            ruta, contenido, bool(sobrescribir)
        ),
    ),
    "crear_carpeta": ToolSpec(
        name="crear_carpeta",
        description=(
            "Propone crear una carpeta en el equipo del usuario. "
            "El motor pide confirmación antes de crearla."
        ),
        parameters=_schema_object(
            {
                "ruta": {"type": "string", "description": "Ruta absoluta o relativa al motor."},
            },
            ["ruta"],
        ),
        handler=lambda ruta, **_: crear_carpeta(ruta),
    ),
}

SELF_TOOLS = [
    "crear_skill",
    "agregar_a_skill",
    "reescribir_identidad",
    "crear_archivo",
    "crear_carpeta",
]
WRITE_TOOLS = set(SELF_TOOLS)


def openai_tools(names: list[str] | None = None) -> list[dict[str, Any]]:
    selected = names or list(TOOL_SPECS)
    tools: list[dict[str, Any]] = []
    for name in selected:
        spec = TOOL_SPECS.get(name)
        if spec is None:
            continue
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": spec.parameters,
                },
            }
        )
    return tools


def call_tool(name: str, arguments: dict[str, Any] | str | None) -> str:
    spec = TOOL_SPECS.get(name)
    if spec is None:
        return f"Herramienta desconocida: `{name}`."
    if isinstance(arguments, str):
        try:
            parsed = json.loads(arguments) if arguments.strip() else {}
        except json.JSONDecodeError as exc:
            return f"Argumentos JSON inválidos para `{name}`: {exc}"
    else:
        parsed = dict(arguments or {})
    try:
        return str(spec.handler(**parsed))
    except TypeError as exc:
        return f"Argumentos incorrectos para `{name}`: {exc}"
    except Exception as exc:  # noqa: BLE001
        return f"Error al ejecutar `{name}`: {exc}"


def format_tool_catalog(names: list[str] | None = None) -> str:
    selected = names or list(TOOL_SPECS)
    lines: list[str] = []
    for name in selected:
        spec = TOOL_SPECS.get(name)
        if spec is None:
            lines.append(f"- `{name}`: (no registrada en el motor)")
            continue
        lines.append(f"- `{spec.name}`: {spec.description}")
    return "\n".join(lines) if lines else "(Sin herramientas.)"

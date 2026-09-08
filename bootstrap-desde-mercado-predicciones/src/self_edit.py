"""Escritura que el modelo puede hacer sobre sí mismo: skills e identidad."""

from __future__ import annotations

import re
from pathlib import Path

from src.paths import BASE_GLA2, IDENTIDAD_PATH, MODELFILE_PATH, SKILLS_DIR
from src.skills import get_skill

_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,48}$")
_LANG_RE = re.compile(r"^[a-z][a-z0-9_]{0,24}$")
_KINDS = {"language", "domain", "protocol"}
_CORE_LANGS = {"python", "rust", "c"}


def _as_items(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _item(value: str) -> str:
    return value.strip().lower().replace("-", "_")


def _clean_name(name: str) -> str | None:
    needle = (name or "").strip().lower().replace("-", "_")
    if needle in {"..", ".", ""} or "/" in needle or "\\" in needle:
        return None
    if not _NAME_RE.match(needle):
        return None
    return needle


def _yaml_list(items: list[str]) -> str:
    cleaned = [item.strip() for item in items if item and item.strip()]
    if not cleaned:
        return "[]"
    return "\n" + "\n".join(f"  - {item}" for item in cleaned)


def crear_skill(
    name: str,
    description: str,
    body: str,
    *,
    kind: str = "domain",
    language: str | None = None,
    depends_on: list[str] | None = None,
    triggers: list[str] | None = None,
) -> str:
    """Crea skills/<nombre>/SKILL.md. No pisa una skill existente."""
    skill_name = _clean_name(name)
    if skill_name is None:
        return "Nombre inválido. Usa snake_case, sin rutas."
    if get_skill(skill_name) is not None:
        return f"Ya existe `{skill_name}`. Usa `agregar_a_skill` para sumar texto."

    skill_kind = (kind or "domain").strip().lower()
    if skill_kind not in _KINDS:
        return "kind permitido al crear: language, domain, protocol. Una tool nueva no es ejecutable."

    lang = (language or "").strip().lower().replace("-", "_")
    if lang in {"js", "node"}:
        lang = "javascript"
    if lang in {"ts"}:
        lang = "typescript"
    if lang and not _LANG_RE.match(lang):
        return "language inválido. Usa un identificador corto, o déjalo vacío."

    text = (body or "").strip()
    summary = (description or "").strip()
    if not summary or not text:
        return "Hacen falta description y body."

    deps = [_item(item) for item in _as_items(depends_on)]
    trigs = [item.strip().lower() for item in _as_items(triggers) if item.strip()]
    lang_line = f"language: {lang}\n" if lang else ""

    content = (
        "---\n"
        f"name: {skill_name}\n"
        f"kind: {skill_kind}\n"
        f"{lang_line}"
        f"depends_on: {_yaml_list(deps)}\n"
        "tools:\n"
        "  - ejecutar_linter\n"
        "  - buscar_documentacion_web\n"
        f"description: {summary}\n"
        f"triggers: {_yaml_list(trigs)}\n"
        "always: false\n"
        "---\n\n"
        f"{text}\n"
    )

    folder = SKILLS_DIR / skill_name
    target = folder / "SKILL.md"
    folder.mkdir(parents=True, exist_ok=False)
    target.write_text(content, encoding="utf-8")
    loaded = get_skill(skill_name)
    if loaded is None:
        return f"Se escribió {target} pero el cargador no la ve."
    return f"Skill creada: `{skill_name}` en {target.relative_to(SKILLS_DIR.parent)}"


def agregar_a_skill(name: str, titulo: str, texto: str) -> str:
    """Añade una sección al final de un SKILL.md. No sustituye el archivo."""
    skill_name = _clean_name(name)
    if skill_name is None:
        return "Nombre inválido."
    skill = get_skill(skill_name)
    if skill is None:
        return f"No existe `{skill_name}`. Usa `crear_skill`."

    heading = (titulo or "").strip()
    extra = (texto or "").strip()
    if not heading or not extra:
        return "Hacen falta titulo y texto."
    if heading.startswith("#"):
        heading = heading.lstrip("#").strip()

    path = skill.path
    current = path.read_text(encoding="utf-8").rstrip() + "\n"
    marker = f"## {heading}\n"
    if marker in current:
        return f"`{skill_name}` ya tiene la sección `{heading}`. Cambia el título o no dupliques."

    path.write_text(f"{current}\n{marker}\n{extra}\n", encoding="utf-8")
    return f"Añadido a `{skill_name}`: sección `{heading}`."


def reescribir_identidad(texto: str) -> str:
    """
    Reescribe la capa editable del modelo: datos/identidad.md y el SYSTEM del Modelfile.
    Las leyes de suelo siguen inyectadas por el motor y no viven en ese texto.
    """
    body = (texto or "").strip()
    if len(body) < 20:
        return "La identidad nueva es demasiado corta."
    if len(body) > 4000:
        return "La identidad nueva supera 4000 caracteres."

    IDENTIDAD_PATH.parent.mkdir(parents=True, exist_ok=True)
    IDENTIDAD_PATH.write_text(body + "\n", encoding="utf-8")
    _write_modelfile(body)
    return (
        "Identidad reescrita en datos/identidad.md y en el SYSTEM del Modelfile. "
        "Las leyes de suelo no se tocaron. "
        "Para que Ollama use el Modelfile nuevo: ollama create gla-2 -f Modelfile"
    )


def _write_modelfile(identidad: str) -> None:
    base = BASE_GLA2
    if MODELFILE_PATH.exists():
        first = MODELFILE_PATH.read_text(encoding="utf-8").splitlines()
        if first and first[0].startswith("FROM "):
            candidate = first[0].removeprefix("FROM ").strip()
            if candidate and "r1" not in candidate.lower():
                base = candidate

    system = (
        "Eres Gla-2: asistente de programación autónomo, privado y local.\n"
        "Preséntate solo como Gla-2. NUNCA digas que eres DeepSeek, ChatGPT, Claude, Llama ni otro proveedor.\n"
        "No pidas claves, tokens, seeds ni contraseñas.\n"
        "No harás daño ni buscarás vulnerar al usuario que te use.\n"
        "Programar es tu prioridad, no tu límite. Investiga y elabora lo que el usuario esté construyendo, en el dominio que sea.\n"
        "No inventes APIs ni resultados de herramientas.\n"
        "En el chat crudo de Ollama no orquestas skills. Usa: python -m src.main chat\n"
        "\n"
        "Identidad editable:\n"
        f"{identidad}\n"
    )
    # El SYSTEM de Ollama no puede contener la secuencia de cierre.
    system = system.replace('"""', "'")
    MODELFILE_PATH.write_text(
        f"FROM {base}\n\nSYSTEM \"\"\"{system}\"\"\"\n",
        encoding="utf-8",
    )


def read_identidad() -> str:
    if not IDENTIDAD_PATH.exists():
        return ""
    return IDENTIDAD_PATH.read_text(encoding="utf-8").strip()


def skill_file(name: str) -> Path | None:
    skill_name = _clean_name(name)
    if skill_name is None:
        return None
    path = SKILLS_DIR / skill_name / "SKILL.md"
    return path if path.is_file() else None

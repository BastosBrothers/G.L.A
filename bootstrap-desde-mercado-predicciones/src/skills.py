"""Carga y selección de skills modulares (lenguaje, dominio, herramienta)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from src.paths import SKILLS_DIR

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)
_SLASH_SKILL_RE = re.compile(
    r"(?:^|\s)/(?:skill|skills)\s+([a-z0-9][a-z0-9_]*)",
    re.IGNORECASE,
)
_AT_SKILL_RE = re.compile(r"@([a-z0-9][a-z0-9_]*)", re.IGNORECASE)

KINDS = {"language", "domain", "tool", "protocol"}
LANGUAGE_HINTS: dict[str, tuple[str, ...]] = {
    "python": ("python", "pytest", "fastapi", "django", "ruff", "pydantic"),
    "rust": ("rust", "cargo", "crate", "tokio"),
    "c": (" c ", "stdio", "gcc", "clang", ".c", "lenguaje c"),
}


@dataclass
class Skill:
    name: str
    description: str
    body: str
    path: Path
    kind: str = "domain"
    language: str | None = None
    depends_on: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    triggers: list[str] = field(default_factory=list)
    always: bool = False

    @property
    def catalog_line(self) -> str:
        flags: list[str] = [self.kind]
        if self.language:
            flags.append(self.language)
        if self.always:
            flags.append("always")
        deps = f" -> {', '.join(self.depends_on)}" if self.depends_on else ""
        return f"- `{self.name}` [{', '.join(flags)}]{deps}: {self.description}"


def _parse_scalar_list(lines: list[str], start: int) -> tuple[list[str], int]:
    items: list[str] = []
    i = start
    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()
        if not stripped:
            i += 1
            continue
        if stripped.startswith("- "):
            items.append(stripped[2:].strip().strip("\"'"))
            i += 1
            continue
        break
    return items, i


def _parse_frontmatter(raw: str) -> tuple[dict[str, object], str]:
    match = _FRONTMATTER_RE.match(raw.strip())
    if not match:
        return {}, raw.strip()

    meta: dict[str, object] = {}
    lines = match.group(1).splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if ":" not in line or line.startswith((" ", "\t")):
            i += 1
            continue
        key, value = line.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        if value == "":
            items, i = _parse_scalar_list(lines, i + 1)
            meta[key] = items
            continue
        if value in {">", ">-", "|", "|-"}:
            collected: list[str] = []
            i += 1
            while i < len(lines) and (
                lines[i].startswith((" ", "\t")) or lines[i].strip() == ""
            ):
                collected.append(lines[i].strip())
                i += 1
            meta[key] = " ".join(x for x in collected if x).strip()
            continue
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            meta[key] = [
                part.strip().strip("\"'")
                for part in inner.split(",")
                if part.strip()
            ]
            i += 1
            continue
        meta[key] = value.strip().strip("\"'")
        i += 1
    return meta, match.group(2).strip()


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "si", "sí"}


def _as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip().lower() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    return [part.strip().lower() for part in value_split(text) if part.strip()]


def value_split(text: str) -> list[str]:
    if "," in text:
        return text.split(",")
    return [text]


def load_skills() -> list[Skill]:
    """Carga skills desde skills/*/SKILL.md."""
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    skills: list[Skill] = []
    for skill_md in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        raw = skill_md.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(raw)
        name = str(meta.get("name") or skill_md.parent.name).strip().lower()
        kind = str(meta.get("kind") or "domain").strip().lower()
        if kind not in KINDS:
            kind = "domain"
        language = str(meta.get("language") or "").strip().lower() or None
        skills.append(
            Skill(
                name=name,
                description=str(meta.get("description") or "(Sin descripción)").strip(),
                body=body or raw,
                path=skill_md,
                kind=kind,
                language=language,
                depends_on=_as_list(meta.get("depends_on")),
                tools=_as_list(meta.get("tools")),
                triggers=_as_list(meta.get("triggers")),
                always=_truthy(meta.get("always")),
            )
        )
    return skills


def get_skill(name: str) -> Skill | None:
    needle = name.strip().lower()
    for skill in load_skills():
        if skill.name == needle:
            return skill
    return None


def skills_by_name(skills: list[Skill] | None = None) -> dict[str, Skill]:
    skills = skills if skills is not None else load_skills()
    return {skill.name: skill for skill in skills}


def format_catalog(skills: list[Skill] | None = None) -> str:
    skills = skills if skills is not None else load_skills()
    if not skills:
        return "(No hay skills en `skills/`. Añade carpetas con SKILL.md.)"
    return "\n".join(skill.catalog_line for skill in skills)


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9áéíóúñü_]{3,}", text.lower())}


def wants_skill_authoring(text: str) -> bool:
    low = f" {(text or '').lower()} "
    marks = (
        " skill de ",
        " skill para ",
        " skills de ",
        " crear skill",
        " crea un skill",
        " crea una skill",
        " haz un skill",
        " haz una skill",
        " nueva skill",
        " nuevo skill",
        " enseñame un skill",
        " enséñame un skill",
    )
    return any(mark in low for mark in marks)


def detect_language(text: str, explicit: str | None = None) -> str | None:
    if explicit:
        return explicit.strip().lower()
    lowered = f" {text.lower()} "
    for language, hints in LANGUAGE_HINTS.items():
        if any(hint in lowered for hint in hints):
            return language
    return None


def _explicit_names(user_text: str) -> list[str]:
    names: list[str] = []
    for match in _SLASH_SKILL_RE.finditer(user_text):
        names.append(match.group(1).lower())
    for match in _AT_SKILL_RE.finditer(user_text):
        names.append(match.group(1).lower())
    return names


def select_skills(
    user_text: str,
    *,
    max_domain: int = 3,
    forced: list[str] | None = None,
    language: str | None = None,
) -> list[Skill]:
    """
    Elige skills de instrucción (no tools):
    1) always=true y kind=protocol
    2) /skill, @nombre y pineados
    3) language core del lenguaje detectado
    4) coincidencia léxica de dominio
    Las dependencias se resuelven después en el DAG.
    """
    all_skills = load_skills()
    by_name = {skill.name: skill for skill in all_skills}
    chosen: dict[str, Skill] = {}

    for skill in all_skills:
        if skill.kind == "tool":
            continue
        if skill.always or skill.kind == "protocol":
            chosen[skill.name] = skill

    for name in list(forced or []) + _explicit_names(user_text):
        skill = by_name.get(name)
        if skill is not None and skill.kind != "tool":
            chosen[name] = skill

    detected = detect_language(user_text, language)
    if detected:
        core_name = f"{detected}_core"
        core = by_name.get(core_name)
        if core is not None:
            chosen[core.name] = core

    if wants_skill_authoring(user_text):
        author = by_name.get("crear_skill")
        if author is not None:
            chosen[author.name] = author

    query_tokens = _tokenize(user_text)
    scored: list[tuple[int, Skill]] = []
    for skill in all_skills:
        if skill.kind in {"tool", "protocol"} or skill.name in chosen:
            continue
        if skill.kind != "domain":
            # language cores ya se eligen por detect_language
            continue
        trigger_tokens = _tokenize(" ".join(skill.triggers))
        desc_tokens = _tokenize(skill.description)
        name_tokens = _tokenize(skill.name.replace("_", " "))
        # No puntuar solo por la palabra del lenguaje (python/rust/c): eso activa
        # todos los dominios del idioma ante cualquier pedido trivial.
        lang_noise = {skill.language} if skill.language else set()
        useful_desc = desc_tokens - lang_noise - {"core", "skill", "base", "extiende"}
        useful_name = name_tokens - lang_noise
        score = len(query_tokens & trigger_tokens) * 3
        score += len(query_tokens & useful_name) * 2
        score += len(query_tokens & useful_desc)
        # Nombre completo solo si no es meramente "<lang>_algo" sin trigger.
        full_name = skill.name.replace("_", " ")
        if full_name in user_text.lower() or skill.name in user_text.lower():
            score += 5
        if score > 0:
            scored.append((score, skill))
    scored.sort(key=lambda item: (-item[0], item[1].name))

    domain_added = 0
    for score, skill in scored:
        # Exige señal real (trigger/nombre útil), no ruido léxico débil.
        if score < 3:
            break
        if domain_added >= max_domain:
            break
        chosen[skill.name] = skill
        domain_added += 1

    result = list(chosen.values())
    result.sort(key=lambda skill: (skill.kind != "protocol", not skill.always, skill.name))
    return result


def format_skills_for_prompt(skills: list[Skill]) -> str:
    if not skills:
        return "(Ningún skill de instrucción activo en este turno.)"
    parts: list[str] = []
    for skill in skills:
        deps = ", ".join(skill.depends_on) or "(ninguna)"
        parts.append(
            f"### Skill: `{skill.name}` ({skill.kind})\n\n"
            f"_{skill.description}_\n\n"
            f"Depende de: {deps}\n\n"
            f"{skill.body.strip()}\n"
        )
    return "\n---\n".join(parts)


def strip_skill_directives(user_text: str) -> str:
    text = _SLASH_SKILL_RE.sub(" ", user_text)
    known = {skill.name for skill in load_skills()}

    def _repl(match: re.Match[str]) -> str:
        return " " if match.group(1).lower() in known else match.group(0)

    text = _AT_SKILL_RE.sub(_repl, text)
    return re.sub(r"\s+", " ", text).strip()

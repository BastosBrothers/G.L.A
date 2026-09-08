"""Orquestador de skills basado en grafo dirigido acíclico (DAG)."""

from __future__ import annotations

from dataclasses import dataclass, field

from src.skills import Skill, skills_by_name


class CycleError(ValueError):
    """Dependencia circular entre skills."""


class MissingSkillError(KeyError):
    """Una skill declara una dependencia que no existe."""


@dataclass
class ResolvedGraph:
    """Cierre de skills en orden topológico (dependencias primero)."""

    roots: list[str]
    ordered: list[Skill]
    tools: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

    @property
    def names(self) -> list[str]:
        return [skill.name for skill in self.ordered]


def resolve(
    names: list[str],
    catalog: dict[str, Skill] | None = None,
) -> ResolvedGraph:
    """
    Expande `depends_on` y devuelve el orden de carga.

    Ejemplo: activar `python_web` carga antes `python_core`.
    Las skills `tool` no se inyectan como cuerpo; se acumulan en `tools`.
    """
    catalog = catalog if catalog is not None else skills_by_name()
    visiting: set[str] = set()
    visited: set[str] = set()
    ordered: list[Skill] = []
    tools: list[str] = []
    missing: list[str] = []

    def visit(name: str) -> None:
        if name in visited:
            return
        if name in visiting:
            raise CycleError(f"Ciclo de skills al resolver `{name}`.")
        skill = catalog.get(name)
        if skill is None:
            missing.append(name)
            visited.add(name)
            return
        visiting.add(name)
        for dep in skill.depends_on:
            visit(dep)
        visiting.remove(name)
        visited.add(name)
        if skill.kind == "tool":
            if skill.name not in tools:
                tools.append(skill.name)
            return
        ordered.append(skill)
        for tool_name in skill.tools:
            if tool_name not in tools:
                tools.append(tool_name)

    roots = []
    for name in names:
        needle = name.strip().lower()
        if needle and needle not in roots:
            roots.append(needle)
        visit(needle)

    return ResolvedGraph(roots=roots, ordered=ordered, tools=tools, missing=missing)


def explain(graph: ResolvedGraph) -> str:
    lines = ["Orden de carga (dependencias primero):"]
    if not graph.ordered:
        lines.append("- (ninguna skill de instrucción)")
    for index, skill in enumerate(graph.ordered, start=1):
        deps = ", ".join(skill.depends_on) or "-"
        lines.append(f"{index}. `{skill.name}` ({skill.kind}) deps=[{deps}]")
    lines.append("")
    lines.append("Herramientas disponibles para function calling:")
    if graph.tools:
        lines.extend(f"- `{name}`" for name in graph.tools)
    else:
        lines.append("- (ninguna)")
    if graph.missing:
        lines.append("")
        lines.append("Dependencias ausentes: " + ", ".join(f"`{name}`" for name in graph.missing))
    return "\n".join(lines)

"""Creación de archivos y carpetas. El orquestador pide confirmación antes de llamar aquí."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.paths import ROOT

_BLOCKED = {
    (ROOT / "datos" / "leyes.md").resolve(),
    (ROOT / "src" / "leyes.py").resolve(),
}


def resolve_path(ruta: str) -> Path:
    raw = (ruta or "").strip().strip("\"'")
    if not raw:
        raise ValueError("Falta la ruta.")
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()


def _guard(path: Path) -> str | None:
    if path in _BLOCKED or (path.name == "leyes.md" and path.parent.name == "datos"):
        return "Esa ruta es de las leyes. No se puede crear ni reemplazar."
    if path.resolve() == (ROOT / "src" / "leyes.py").resolve():
        return "Esa ruta es de las leyes. No se puede crear ni reemplazar."
    return None


def crear_carpeta(ruta: str) -> str:
    path = resolve_path(ruta)
    blocked = _guard(path)
    if blocked:
        return blocked
    if path.exists() and not path.is_dir():
        return f"Ya existe un archivo en `{path}`. No se creó la carpeta."
    created = not path.exists()
    path.mkdir(parents=True, exist_ok=True)
    if created:
        return f"Carpeta creada: {path}"
    return f"La carpeta ya existía: {path}"


def crear_archivo(ruta: str, contenido: str = "", sobrescribir: bool = False) -> str:
    path = resolve_path(ruta)
    blocked = _guard(path)
    if blocked:
        return blocked
    if path.exists() and path.is_dir():
        return f"`{path}` es una carpeta. No se escribió un archivo encima."
    existed = path.exists()
    if existed and not sobrescribir:
        return f"Ya existe `{path}`. No se reemplazó. Pide sobrescribir y confirma de nuevo."
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contenido if contenido is not None else "", encoding="utf-8")
    action = "reemplazado" if existed else "creado"
    return f"Archivo {action}: {path}"


def validate_write_args(nombre: str, arguments: dict[str, Any] | None) -> str | None:
    """None si la llamada es válida; si no, el motivo del rechazo (sin preguntar al usuario)."""
    args = arguments or {}
    if nombre == "crear_archivo":
        ruta = str(args.get("ruta") or "").strip()
        if not ruta:
            return "Llamada inválida: `crear_archivo` requiere `ruta`. No se preguntó al usuario."
        return None
    if nombre == "crear_carpeta":
        ruta = str(args.get("ruta") or "").strip()
        if not ruta:
            return "Llamada inválida: `crear_carpeta` requiere `ruta`. No se preguntó al usuario."
        return None
    if nombre == "crear_skill":
        if not str(args.get("name") or "").strip():
            return "Llamada inválida: `crear_skill` requiere `name`."
        if not str(args.get("description") or "").strip() or not str(args.get("body") or "").strip():
            return "Llamada inválida: `crear_skill` requiere `description` y `body`."
        return None
    if nombre == "agregar_a_skill":
        if not str(args.get("name") or "").strip() or not str(args.get("titulo") or "").strip():
            return "Llamada inválida: `agregar_a_skill` requiere `name` y `titulo`."
        if not str(args.get("texto") or "").strip():
            return "Llamada inválida: `agregar_a_skill` requiere `texto`."
        return None
    if nombre == "reescribir_identidad":
        if len(str(args.get("texto") or "").strip()) < 20:
            return "Llamada inválida: `reescribir_identidad` requiere `texto` útil."
        return None
    return None


def describir_escritura(nombre: str, arguments: dict[str, Any] | None) -> str:
    """Texto que ve el usuario antes de decir sí o no. Nunca lanza."""
    args = arguments or {}
    invalid = validate_write_args(nombre, args)
    if invalid:
        return invalid
    try:
        if nombre == "crear_carpeta":
            path = resolve_path(str(args.get("ruta", "")))
            return f"Crear carpeta:\n{path}"
        if nombre == "crear_archivo":
            path = resolve_path(str(args.get("ruta", "")))
            content = str(args.get("contenido") or "")
            preview = content[:400] + ("…" if len(content) > 400 else "")
            extra = (
                "Reemplazará el archivo existente.\n"
                if args.get("sobrescribir")
                else ""
            )
            return f"Crear archivo:\n{path}\n{extra}Contenido:\n{preview or '(vacío)'}"
        if nombre == "crear_skill":
            return (
                f"Crear skill `{args.get('name')}` "
                f"en skills/{args.get('name')}/SKILL.md"
            )
        if nombre == "agregar_a_skill":
            return (
                f"Añadir a la skill `{args.get('name')}` "
                f"la sección `{args.get('titulo')}`"
            )
        if nombre == "reescribir_identidad":
            texto = str(args.get("texto") or "")
            preview = texto[:400] + ("…" if len(texto) > 400 else "")
            return f"Reescribir la identidad editable:\n{preview}"
    except Exception as exc:  # noqa: BLE001
        return f"No se pudo describir la escritura: {exc}"
    return f"Escritura `{nombre}`"

"""Importa lecciones de colaboración desde transcripts de Cursor hacia Gla-2."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from src.paths import MEMORIA_PATH, ROOT
from src.text import scrub

COLAB_PATH = ROOT / "datos" / "colaboracion.jsonl"

# Ruta típica de transcripts de esta sesión Cursor (Windows).
_DEFAULT_TRANSCRIPT_GLOBS = (
    Path.home()
    / ".cursor"
    / "projects"
    / "c-Users-mainp-OneDrive-Documentos-Gla-2"
    / "agent-transcripts",
)


def _transcript_dirs() -> list[Path]:
    dirs: list[Path] = []
    for base in _DEFAULT_TRANSCRIPT_GLOBS:
        if base.is_dir():
            dirs.append(base)
    # También buscar bajo .cursor/projects/*/agent-transcripts
    projects = Path.home() / ".cursor" / "projects"
    if projects.is_dir():
        for child in projects.iterdir():
            candidate = child / "agent-transcripts"
            if candidate.is_dir() and candidate not in dirs:
                dirs.append(candidate)
    return dirs


def _iter_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return rows
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _user_texts(rows: list[dict], limit: int = 40) -> list[str]:
    out: list[str] = []
    for row in rows:
        role = (row.get("role") or row.get("type") or "").lower()
        # Formatos Cursor: message.role / role
        msg = row.get("message") or row
        if isinstance(msg, dict):
            role = (msg.get("role") or role).lower()
            content = msg.get("content")
        else:
            content = row.get("content") or row.get("text")
        if role not in {"user", "human"}:
            continue
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(str(block.get("text") or ""))
                elif isinstance(block, str):
                    parts.append(block)
            text = "\n".join(parts)
        else:
            text = str(content or "")
        text = scrub(text).strip()
        if len(text) < 12:
            continue
        # Saltar ruido de sistema / plan attachments largos
        if text.startswith("Implement the plan") or text.startswith("<"):
            continue
        out.append(text[:500])
        if len(out) >= limit:
            break
    return out


_LESSON_RULES: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"calculadora|crea|hagamos|haz una|archivo", re.I),
        "Si pide crear un programa, escribir archivos en el proyecto (```file), no solo explicar en el chat.",
    ),
    (
        re.compile(r"gestor.?git|panel\.ps1|contexto|proyecto", re.I),
        "Respetar el proyecto activo: no mezclar pedidos nuevos con archivos abiertos ajenos.",
    ),
    (
        re.compile(r"explica|tutorial|chat|peg", re.I),
        "Explicar breve y hacer: prohibido mandar al usuario a pegar codigo a mano.",
    ),
    (
        re.compile(r"spinner|trabajando|busy", re.I),
        "Mostrar estado mientras el modelo trabaja (feedback visible en el IDE).",
    ),
]


def extract_lessons(user_snippets: list[str]) -> list[str]:
    found: list[str] = []
    blob = "\n".join(user_snippets)
    for pattern, lesson in _LESSON_RULES:
        if pattern.search(blob) and lesson not in found:
            found.append(lesson)
    return found


def _load_known() -> set[str]:
    known: set[str] = set()
    if not COLAB_PATH.exists():
        return known
    for row in _iter_jsonl(COLAB_PATH):
        note = str(row.get("lesson") or "").strip()
        if note:
            known.add(note)
    return known


def _append_lessons(lessons: list[str], source: str) -> int:
    if not lessons:
        return 0
    COLAB_PATH.parent.mkdir(parents=True, exist_ok=True)
    known = _load_known()
    added = 0
    with COLAB_PATH.open("a", encoding="utf-8") as handle:
        for lesson in lessons:
            if lesson in known:
                continue
            row = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "source": source,
                "lesson": lesson,
            }
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            known.add(lesson)
            added += 1
    return added


def _refresh_memoria() -> None:
    """Sincroniza un bloque breve de lecciones Cursor dentro de memoria.md."""
    if not COLAB_PATH.exists():
        return
    lessons: list[str] = []
    for row in _iter_jsonl(COLAB_PATH):
        note = str(row.get("lesson") or "").strip()
        if note and note not in lessons:
            lessons.append(note)
    lessons = lessons[-12:]
    if not lessons:
        return
    block = (
        "\n\n## Lecciones importadas de Cursor\n\n"
        + "\n".join(f"- {item}" for item in lessons)
        + "\n"
    )
    current = ""
    if MEMORIA_PATH.exists():
        current = scrub(MEMORIA_PATH.read_text(encoding="utf-8", errors="surrogatepass"))
    marker = "## Lecciones importadas de Cursor"
    if marker in current:
        head = current.split(marker, 1)[0].rstrip()
        current = head + block
    else:
        current = current.rstrip() + block
    MEMORIA_PATH.write_text(current + "\n", encoding="utf-8")


def aprender_desde_cursor(*, max_files: int = 8) -> str:
    """Lee transcripts recientes, extrae lecciones y actualiza memoria."""
    dirs = _transcript_dirs()
    if not dirs:
        return "No encontré carpetas agent-transcripts de Cursor."
    files: list[Path] = []
    for folder in dirs:
        files.extend(sorted(folder.glob("**/*.jsonl"), key=lambda p: p.stat().st_mtime))
    files = files[-max_files:]
    snippets: list[str] = []
    sources: list[str] = []
    for path in files:
        rows = _iter_jsonl(path)
        texts = _user_texts(rows)
        if texts:
            snippets.extend(texts)
            sources.append(path.name)
    lessons = extract_lessons(snippets)
    # Siempre reforzar el núcleo de esta colaboración IDE.
    core = [
        "Si pide crear un programa, escribir archivos en el proyecto (```file), no solo explicar en el chat.",
        "Respetar el proyecto activo: no mezclar pedidos nuevos con archivos abiertos ajenos.",
        "Explicar breve y hacer: prohibido mandar al usuario a pegar codigo a mano.",
    ]
    for item in core:
        if item not in lessons:
            lessons.append(item)
    added = _append_lessons(lessons, source=",".join(sources) or "cursor")
    _refresh_memoria()
    return (
        f"Transcripts leídos: {len(files)}. "
        f"Lecciones nuevas: {added}. "
        f"Total en tanda: {len(lessons)}. "
        f"Memoria actualizada: {MEMORIA_PATH.name}."
    )

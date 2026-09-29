"""Ejecutar un script del proyecto con timeout (sandbox ligero)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from src.text import scrub


def run_project_script(
    path: str,
    *,
    cwd: str | None = None,
    stdin_text: str = "",
    timeout: float = 8.0,
) -> str:
    target = Path(path).expanduser()
    if not target.is_file():
        return f"No existe el archivo: {path}"
    if target.suffix.lower() not in {".py"}:
        return "Por ahora solo se ejecutan archivos .py"
    work = Path(cwd).expanduser() if cwd else target.parent
    try:
        completed = subprocess.run(
            [sys.executable, str(target)],
            cwd=str(work),
            input=stdin_text or None,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        return f"(timeout {timeout}s) El programa no terminó a tiempo."
    except OSError as exc:
        return f"Error al ejecutar: {scrub(exc)}"
    out = (completed.stdout or "").strip()
    err = (completed.stderr or "").strip()
    code = completed.returncode
    parts = [f"exit={code}"]
    if out:
        parts.append("--- stdout ---\n" + out[:4000])
    if err:
        parts.append("--- stderr ---\n" + err[:2000])
    if not out and not err:
        parts.append("(sin salida)")
    return "\n".join(parts)

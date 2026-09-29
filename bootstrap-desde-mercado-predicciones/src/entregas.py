"""Diario de entregas: qué escribió Gla-2 en cada proyecto."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.paths import ROOT
from src.text import scrub

ENTREGAS_PATH = ROOT / "datos" / "entregas.jsonl"


def record_delivery(
    *,
    project: str,
    request: str,
    paths: list[str],
    note: str = "",
) -> None:
    if not paths:
        return
    ENTREGAS_PATH.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "project": scrub(project)[:400],
        "request": scrub(request)[:500],
        "paths": [scrub(p)[:200] for p in paths[:20]],
        "note": scrub(note)[:300],
    }
    with ENTREGAS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def recent_for_project(project: str, *, limit: int = 8) -> str:
    """Texto corto para inyectar en el prompt (recall / creación)."""
    if not ENTREGAS_PATH.exists() or not project:
        return ""
    needle = project.replace("\\", "/").rstrip("/").lower()
    rows: list[dict] = []
    for line in ENTREGAS_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        proj = str(row.get("project") or "").replace("\\", "/").rstrip("/").lower()
        if needle and needle not in proj and proj not in needle:
            # también match por nombre de carpeta
            if Path(needle).name.lower() not in proj:
                continue
        rows.append(row)
    picked = rows[-limit:]
    if not picked:
        return ""
    lines = ["Entregas recientes de Gla-2 en este proyecto:"]
    for row in picked:
        paths = ", ".join(row.get("paths") or [])
        req = (row.get("request") or "")[:120]
        lines.append(f"- {paths} ← {req}")
    return "\n".join(lines)

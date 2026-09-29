"""Contrato de entrega. El sandbox solo aprende de este formato, no de parches."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from src.paths import FORMATO_PATH

EJEMPLO = """```file
path: main.py
---
# código completo del programa que pidió el usuario
```"""

PLANTILLA = f"""Regla dura de entrega. Tu respuesta completa debe ser solo bloques así:

{EJEMPLO}

Obligatorio:
1. Empieza con ```file
2. La siguiente línea es exactamente: path: main.py
3. La siguiente línea es exactamente: ---
4. Luego el código Python completo del pedido (no un hello world ni print("hola")).
5. Cierra con ```
6. Sin texto antes, sin texto después, sin ```python, sin # file.
"""

_STRICT_RE = re.compile(
    r"```file[ \t]*\npath:[ \t]*([A-Za-z_][\w./-]*)[ \t]*\n---[ \t]*\n(.*?)```",
    re.DOTALL | re.IGNORECASE,
)


def extraer(text: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for match in _STRICT_RE.finditer(text or ""):
        path = match.group(1).strip().replace("\\", "/")
        content = match.group(2).strip()
        if not path or ".." in path.split("/") or not content:
            continue
        found.append((path, content + "\n"))
    return found


def motivo_de(text: str) -> str:
    low = (text or "").lower()
    if "```python" in low or "```py" in low:
        return "usó ```python en vez de ```file"
    if "# file" in low:
        return "puso el nombre en un comentario # file"
    if "```file" in low and "path:" not in low:
        return "faltó la línea path:"
    if "```file" in low:
        return "el bloque ```file no tenía path y --- en líneas separadas"
    return "no entregó un bloque ```file"


def recordar(ok: bool, text: str) -> None:
    FORMATO_PATH.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "ok": ok,
        "motivo": "" if ok else motivo_de(text),
    }
    with FORMATO_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def lecciones(limit: int = 3) -> str:
    if not FORMATO_PATH.exists():
        return f"Ejemplo correcto:\n{EJEMPLO}"
    rows: list[dict] = []
    for line in FORMATO_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    mal = [row.get("motivo") for row in rows if not row.get("ok") and row.get("motivo")]
    vistos: list[str] = []
    for item in reversed(mal):
        if item not in vistos:
            vistos.append(item)
        if len(vistos) >= limit:
            break
    parts = [f"Ejemplo correcto:\n{EJEMPLO}"]
    if vistos:
        parts.append(
            "Errores que ya cometiste y no debes repetir:\n"
            + "\n".join(f"- {item}." for item in vistos)
        )
    return "\n\n".join(parts)


def correccion(motivo: str) -> str:
    return (
        f"Tu respuesta anterior falló: {motivo}. "
        "Reescribe TODO el programa pedido otra vez. "
        f"Usa exactamente este molde:\n{EJEMPLO}\n"
        "El cuerpo debe implementar lo que pidió el usuario. "
        "Prohibido hello world, print(\"hola\") o copiar el ejemplo. Sin explicación."
    )

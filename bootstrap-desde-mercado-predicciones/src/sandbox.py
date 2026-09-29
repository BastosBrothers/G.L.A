"""Sandbox: una petición, varias formas, y solo lo validado se recuerda."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from src.deepseek_client import chat
from src.formato import PLANTILLA, correccion, extraer, lecciones, motivo_de, recordar
from src.neuronas import (
    ajustar,
    cerebro_de,
    instruccion_desde_pesos,
    rasgos_de,
    registrar_experimento,
    restaurar,
    resumen,
    snapshot,
)
from src.paths import APRENDIZAJES_PATH, MODELO_GLA2, SANDBOX_DIR

STYLES = (
    (
        "procedural",
        "Hazlo de forma procedural: funciones sueltas, poco estado, flujo directo.",
    ),
    (
        "modular",
        "Hazlo modular: separa datos, reglas y menú en funciones claras. Un archivo principal y otro de lógica si hace falta.",
    ),
    (
        "objetos",
        "Hazlo con clases pequeñas: un tipo para el registro y otro para el menú. Sin frameworks.",
    ),
)


@dataclass
class VariantResult:
    style: str
    folder: Path
    ok: bool
    files: list[str] = field(default_factory=list)
    check: str = ""
    note: str = ""


def recent_lessons(limit: int = 6) -> str:
    if not APRENDIZAJES_PATH.exists():
        return "(Aún no hay aprendizajes de sandbox.)"
    rows: list[dict] = []
    for line in APRENDIZAJES_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    picked = [row for row in rows if row.get("ok")][-limit:]
    if not picked:
        return "(Aún no hay aprendizajes validados.)"
    lines = []
    for row in picked:
        style = str(row.get("style") or "?")
        note = str(row.get("note") or "validó")[:120]
        lines.append(f"- {style}: {note}")
    return "\n".join(lines)


def _record(result: VariantResult, request: str) -> None:
    APRENDIZAJES_PATH.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "request": request[:400],
        "style": result.style,
        "ok": result.ok,
        "files": result.files,
        "note": result.note[:500],
        "folder": str(result.folder),
    }
    with APRENDIZAJES_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _safe_rel(raw: str) -> str | None:
    rel = raw.replace("\\", "/").strip().lstrip("/")
    parts = [part for part in rel.split("/") if part not in ("", ".")]
    if not parts or ".." in parts or any(part.lower() == "r1" for part in parts):
        return None
    for part in parts:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]{0,80}", part):
            return None
    return "/".join(parts)


def _write_variant(folder: Path, text: str) -> list[str]:
    folder.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for path, content in extraer(text):
        rel = _safe_rel(path)
        if not rel or not rel.endswith(".py"):
            continue
        target = folder.joinpath(*rel.split("/"))
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        except OSError:
            continue
        written.append(rel)
    recordar(bool(written), text)
    if not written:
        (folder / "respuesta.md").write_text(text, encoding="utf-8")
        written.append("respuesta.md")
    return written


def _check(folder: Path, files: list[str]) -> tuple[bool, str]:
    py_files = [folder / name for name in files if name.endswith(".py")]
    if not py_files:
        other = [name for name in files if not name.endswith(".md")]
        if other:
            return False, "No es Python: " + ", ".join(other)
        return False, "Formato inválido. Hace falta ```file, path: y ---."
    notes: list[str] = []
    ok = True
    for path in py_files:
        completed = subprocess.run(
            [sys.executable, "-m", "py_compile", str(path)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if completed.returncode != 0:
            ok = False
            notes.append((completed.stderr or completed.stdout or path.name).strip())
    if ok:
        return True, "Sintaxis Python válida."
    return False, " | ".join(notes)[:400]


def _ask(request: str, style: str, instruction: str, *, extra: str = "") -> str:
    system = (
        "Eres Gla-2 en un sandbox local. No eres DeepSeek ni R1. "
        "Cumple la petición solo en Python.\n\n"
        + PLANTILLA
        + "\n\n"
        + lecciones()
    )
    user = (
        f"Petición: {request}\n\n"
        f"Forma: {style}. {instruction}\n"
        "Responde solo con el bloque ```file. Incluye un punto de entrada ejecutable."
    )
    if extra:
        user = f"{user}\n\n{extra}"
    turn = chat(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
        tools=None,
        model=cerebro_de(MODELO_GLA2),
        num_predict=900,
    )
    return turn.content or ""


def _one(
    request: str,
    root: Path,
    style: str,
    instruction: str,
    *,
    extra: str = "",
) -> VariantResult:
    folder = root / style
    text = _ask(request, style, instruction, extra=extra)
    files = _write_variant(folder, text)
    # Un reintento: el modelo ve su fallo de formato y lo corrige.
    if files == ["respuesta.md"]:
        text = _ask(
            request,
            style,
            instruction,
            extra=correccion(motivo_de(text)),
        )
        files = _write_variant(folder, text)
    ok, check = _check(folder, files)
    note = check if ok else f"No validó: {check}"
    result = VariantResult(
        style=style,
        folder=folder,
        ok=ok,
        files=files,
        check=check,
        note=note,
    )
    _record(result, request)
    return result


def run_sandbox(request: str, *, styles: tuple[tuple[str, str], ...] = STYLES) -> tuple[list[VariantResult], dict]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    root = SANDBOX_DIR / stamp
    results: list[VariantResult] = []
    for style, instruction in styles:
        results.append(_one(request, root, style, instruction))

    ok_vectors = [
        rasgos_de(item.style, item.folder, item.files) for item in results if item.ok
    ]
    # Un fallo de formato no castiga el estilo: solo baja rasgos si hubo .py inválido.
    bad_vectors = [
        rasgos_de(item.style, item.folder, item.files)
        for item in results
        if not item.ok and any(name.endswith(".py") for name in item.files)
    ]
    antes_pesos = snapshot()
    if ok_vectors or bad_vectors:
        ajuste = ajustar(ok_vectors, bad_vectors)
    else:
        ajuste = {
            "pasos": antes_pesos.get("pasos"),
            "delta": 0.0,
            "balances": antes_pesos.get("balances"),
        }
    antes_ok = sum(1 for item in results if item.ok)

    extra = instruccion_desde_pesos()
    probe_style = "ajustado"
    probe_instruction = "Repite la petición aplicando el ajuste neuronal, sin copiar una forma que falló."
    try:
        probe = _one(request, root, probe_style, probe_instruction, extra=extra)
    except Exception:
        restaurar(antes_pesos)
        raise
    results.append(probe)
    revertido = not probe.ok
    if revertido:
        restaurar(antes_pesos)
        ajuste = {
            "pasos": antes_pesos.get("pasos"),
            "delta": 0.0,
            "balances": antes_pesos.get("balances"),
        }
    registrar_experimento(
        request,
        antes_ok=antes_ok,
        despues_ok=probe.ok,
        delta=0.0 if revertido else float(ajuste.get("delta") or 0),
        revertido=revertido,
    )
    experimento = {
        "antes_ok": antes_ok,
        "despues_ok": probe.ok,
        "delta": ajuste.get("delta"),
        "balances": ajuste.get("balances"),
        "revertido": revertido,
        "resumen": resumen(),
    }
    return results, experimento


def format_report(request: str, results: list[VariantResult], experimento: dict | None = None) -> str:
    lines = [f"Sandbox: {request}", ""]
    for item in results:
        flag = "válida" if item.ok else "falló"
        lines.append(f"- {item.style}: {flag}")
        lines.append(f"  carpeta: {item.folder}")
        lines.append(f"  archivos: {', '.join(item.files) or '-'}")
        lines.append(f"  {item.check}")
    learned = [item.style for item in results if item.ok and item.style != "ajustado"]
    lines.append("")
    if learned:
        lines.append("Aprendió de: " + ", ".join(learned))
    else:
        lines.append("Ninguna forma base validó.")
    if experimento:
        despues = "válida" if experimento.get("despues_ok") else "falló"
        if experimento.get("revertido"):
            lines.append(
                "R1 congelado. Gla-2 movió pesos en el sandbox y los revirtió: la pasada ajustada falló."
            )
        else:
            lines.append(
                f"R1 congelado. Gla-2 movió pesos solo en el sandbox (delta {experimento.get('delta')}). Se quedan."
            )
        lines.append(
            f"Antes: {experimento.get('antes_ok')}/{max(len(results) - 1, 1)} válidas. "
            f"Después del ajuste: {despues}."
        )
        lines.append(str(experimento.get("resumen") or ""))
    return "\n".join(lines)

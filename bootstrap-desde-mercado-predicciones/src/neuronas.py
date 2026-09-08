"""Pesos propios de Gla-2. R1 no se toca.

El sandbox mueve un vector de balances (floats reales) solo con lo que validó.
Esos números cambian la siguiente prueba: no es una nota pegada a mano.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.paths import BALANCES_PATH, EXPERIMENTOS_PATH, MODELO_CONGELADO, MODELO_GLA2

RASGOS = (
    "procedural",
    "modular",
    "objetos",
    "pocos_archivos",
    "funciones",
    "clases",
    "entrada_main",
    "manejo_errores",
    "validar_entrada",
    "corto",
)

LR = 0.2
TOPE = 1.5


def cerebro_de(modelo: str | None) -> str:
    nombre = (modelo or MODELO_GLA2).strip() or MODELO_GLA2
    if "r1" in nombre.lower():
        raise ValueError(f"R1 está congelado. No se ajustan pesos de {MODELO_CONGELADO}.")
    return MODELO_GLA2


def _ceros() -> list[float]:
    return [0.0 for _ in RASGOS]


def cargar() -> list[float]:
    if not BALANCES_PATH.exists():
        return _ceros()
    try:
        data = json.loads(BALANCES_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _ceros()
    raw = data.get("balances") if isinstance(data, dict) else None
    if not isinstance(raw, list) or len(raw) != len(RASGOS):
        return _ceros()
    out: list[float] = []
    for item in raw:
        try:
            out.append(float(item))
        except (TypeError, ValueError):
            out.append(0.0)
    return out


def _guardar(balances: list[float], pasos: int) -> None:
    BALANCES_PATH.parent.mkdir(parents=True, exist_ok=True)
    BALANCES_PATH.write_text(
        json.dumps(
            {
                "modelo": MODELO_GLA2,
                "congelado": MODELO_CONGELADO,
                "pasos": pasos,
                "balances": [round(value, 4) for value in balances],
                "rasgos": list(RASGOS),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _pasos() -> int:
    if not BALANCES_PATH.exists():
        return 0
    try:
        data = json.loads(BALANCES_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    try:
        return int(data.get("pasos") or 0)
    except (TypeError, ValueError):
        return 0


def snapshot() -> dict:
    """Copia de los pesos propios, para revertir si el ajuste no valida."""
    return {
        "existed": BALANCES_PATH.exists(),
        "balances": cargar(),
        "pasos": _pasos(),
    }


def restaurar(state: dict) -> None:
    """Vuelve los pesos de Gla-2 al snapshot. No toca R1."""
    if not state.get("existed"):
        if BALANCES_PATH.exists():
            BALANCES_PATH.unlink()
        return
    _guardar(list(state.get("balances") or _ceros()), int(state.get("pasos") or 0))


def _clip(value: float) -> float:
    return max(-TOPE, min(TOPE, value))


def rasgos_de(style: str, folder: Path, files: list[str]) -> list[float]:
    text = ""
    for name in files:
        path = folder / name
        if path.is_file() and name.endswith(".py"):
            try:
                text += "\n" + path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
    low = text.lower()
    py_count = sum(1 for name in files if name.endswith(".py"))
    vector = [0.0 for _ in RASGOS]
    index = {name: i for i, name in enumerate(RASGOS)}
    if style in index:
        vector[index[style]] = 1.0
    vector[index["pocos_archivos"]] = 1.0 if py_count <= 2 else 0.0
    vector[index["funciones"]] = 1.0 if low.count("def ") >= 2 else 0.0
    vector[index["clases"]] = 1.0 if "class " in low else 0.0
    vector[index["entrada_main"]] = 1.0 if 'if __name__' in low else 0.0
    vector[index["manejo_errores"]] = 1.0 if "try:" in low or "except " in low else 0.0
    vector[index["validar_entrada"]] = 1.0 if "strip(" in low or "isdigit" in low else 0.0
    vector[index["corto"]] = 1.0 if 0 < len(text) <= 1800 else 0.0
    return vector


def ajustar(vectores_ok: list[list[float]], vectores_mal: list[list[float]]) -> dict:
    """Sube lo que validó y baja lo que falló. Devuelve el cambio de norma."""
    antes = cargar()
    balances = list(antes)
    if vectores_ok:
        for vector in vectores_ok:
            for i, feature in enumerate(vector):
                if feature:
                    balances[i] = _clip(balances[i] + LR * (feature - balances[i] * 0.15))
    elif vectores_mal:
        for vector in vectores_mal:
            for i, feature in enumerate(vector):
                if feature:
                    balances[i] = _clip(balances[i] - LR * feature)

    pasos = _pasos() + (1 if vectores_ok or vectores_mal else 0)
    _guardar(balances, pasos)
    delta = sum((a - b) ** 2 for a, b in zip(balances, antes)) ** 0.5
    return {
        "pasos": pasos,
        "delta": round(delta, 4),
        "balances": [round(value, 4) for value in balances],
    }


def instruccion_desde_pesos(min_abs: float = 0.25) -> str:
    balances = cargar()
    ranked = sorted(zip(RASGOS, balances), key=lambda item: abs(item[1]), reverse=True)
    altos = [name for name, value in ranked if value >= min_abs][:3]
    bajos = [name for name, value in ranked if value <= -min_abs][:2]
    if not altos and not bajos:
        return ""
    parts = ["Ajuste neuronal de Gla-2 (R1 no interviene)."]
    if altos:
        parts.append("Sube estos balances: " + ", ".join(altos) + ".")
    if bajos:
        parts.append("Baja estos balances: " + ", ".join(bajos) + ".")
    parts.append("Repite la petición en Python, en un archivo main.py. No uses R1 ni rutas con .. .")
    return " ".join(parts)


def resumen() -> str:
    balances = cargar()
    if not any(abs(value) >= 0.05 for value in balances):
        return "(Gla-2 aún no movió pesos. R1 sigue congelado.)"
    pares = [f"{name}={value:.2f}" for name, value in zip(RASGOS, balances) if abs(value) >= 0.05]
    return "Balances Gla-2: " + ", ".join(pares)


def registrar_experimento(
    request: str,
    *,
    antes_ok: int,
    despues_ok: bool,
    delta: float,
    revertido: bool = False,
) -> None:
    EXPERIMENTOS_PATH.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "request": request[:400],
        "antes_ok": antes_ok,
        "despues_ok": despues_ok,
        "mejoro": despues_ok and antes_ok == 0,
        "delta_pesos": delta,
        "revertido": revertido,
        "modelo": MODELO_GLA2,
        "congelado": MODELO_CONGELADO,
    }
    with EXPERIMENTOS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")

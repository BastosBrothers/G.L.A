"""Resolución de modelo por modo (charla vs creación vs explicación)."""

from __future__ import annotations

import os

from src.deepseek_client import get_model

DEFAULT_CHAT = "gla-2"
DEFAULT_CREATE = "qwen2.5-coder:3b"
DEFAULT_CREATE_HARD = "qwen2.5-coder:7b"
_LIGHT = {"gla-2", "gla-2:latest", "qwen2.5-coder:1.5b", "qwen2.5-coder:1.5b:latest"}


def _env(name: str, default: str) -> str:
    return (os.getenv(name) or default).strip() or default


def model_for_mode(
    mode: str | None,
    *,
    explicit: str | None = None,
    hard: bool = False,
) -> str:
    """Charla → gla-2; creación → coder 3b (o 7b si hard y está forzado por env).

    Si el usuario eligió un modelo pesado/explícito distinto del ligero, se respeta.
    """
    chosen = (explicit or "").strip()
    m = (mode or "").strip().lower()
    if m == "create":
        create_m = _env("OLLAMA_MODEL_CREATE", DEFAULT_CREATE)
        if hard:
            hard_m = _env("OLLAMA_MODEL_CREATE_HARD", DEFAULT_CREATE_HARD)
            # Solo escala a hard si el usuario no forzó un ligero y hay override útil.
            # Si hard_m no está instalado, el cliente Ollama fallará; el orquestador
            # puede pasar hard=False. Aquí devolvemos hard_m cuando hard y sin chosen pesado.
            if not chosen or chosen.lower() in _LIGHT or chosen.lower().startswith("gla-2"):
                # Preferir hard solo si OLLAMA_MODEL_CREATE_HARD está seteado o create ya es 7b.
                if os.getenv("OLLAMA_MODEL_CREATE_HARD"):
                    return hard_m
                return create_m
        if not chosen or chosen.lower() in _LIGHT or chosen.lower().startswith("gla-2"):
            return create_m
        return chosen
    if m in {"chat", "talk", "explain"}:
        chat_m = _env("OLLAMA_MODEL_CHAT", DEFAULT_CHAT)
        if not chosen or chosen.lower() in _LIGHT or chosen.lower().startswith("gla-2"):
            return chat_m
        return chosen
    return chosen or get_model()


def model_for_explain(*, explicit: str | None = None) -> str:
    """Pase B (prosa): siempre el modelo ligero de charla."""
    return model_for_mode("explain", explicit=explicit)


def create_num_predict(*, multi: bool = False) -> int:
    if multi:
        return int(_env("GLA2_CREATE_PREDICT_MULTI", "1800"))
    return int(_env("GLA2_CREATE_PREDICT", "900"))

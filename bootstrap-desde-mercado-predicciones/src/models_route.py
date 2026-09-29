"""Resolución de modelo por modo (charla vs creación)."""

from __future__ import annotations

import os

from src.deepseek_client import get_model

DEFAULT_CHAT = "gla-2"
DEFAULT_CREATE = "qwen2.5-coder:3b"
_LIGHT = {"gla-2", "gla-2:latest", "qwen2.5-coder:1.5b", "qwen2.5-coder:1.5b:latest"}


def model_for_mode(
    mode: str | None,
    *,
    explicit: str | None = None,
) -> str:
    """Charla → gla-2; creación → coder 3b (o OLLAMA_MODEL_CREATE).

    Si el usuario eligió un modelo pesado/explícito distinto del ligero, se respeta.
    """
    chosen = (explicit or "").strip()
    m = (mode or "").strip().lower()
    if m == "create":
        create_m = (
            (os.getenv("OLLAMA_MODEL_CREATE") or DEFAULT_CREATE).strip()
            or DEFAULT_CREATE
        )
        if not chosen or chosen.lower() in _LIGHT or chosen.lower().startswith("gla-2"):
            return create_m
        return chosen
    if m in {"chat", "talk"}:
        chat_m = (os.getenv("OLLAMA_MODEL_CHAT") or DEFAULT_CHAT).strip() or DEFAULT_CHAT
        if not chosen or chosen.lower() in _LIGHT or chosen.lower().startswith("gla-2"):
            return chat_m
        return chosen
    return chosen or get_model()

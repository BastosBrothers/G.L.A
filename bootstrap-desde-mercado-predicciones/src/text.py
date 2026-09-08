"""Texto limpio para JSON y prompts. Evita surrogates rotos de Windows/Lua."""

from __future__ import annotations

from typing import Any


def scrub(text: object) -> str:
    raw = "" if text is None else str(text)
    try:
        return raw.encode("utf-8", "surrogatepass").decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
        return "".join(
            ch if not (0xD800 <= ord(ch) <= 0xDFFF) else "\uFFFD" for ch in raw
        )


def scrub_tree(value: Any) -> Any:
    if isinstance(value, str):
        return scrub(value)
    if isinstance(value, list):
        return [scrub_tree(item) for item in value]
    if isinstance(value, dict):
        return {str(key): scrub_tree(item) for key, item in value.items()}
    return value

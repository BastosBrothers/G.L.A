"""Cliente de inferencia: Ollama ahora, vLLM u otra API OpenAI-compatible después."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from src.paths import ENV_PATH, ROOT
from src.text import scrub

load_dotenv(ENV_PATH)
load_dotenv(ROOT / ".env")

DEFAULT_OLLAMA_BASE = "http://127.0.0.1:11434/v1"
DEFAULT_OLLAMA_MODEL = "gla-2"

_TOOL_FENCE_RE = re.compile(
    r"```(?:tool|tool_call|function|json)\s*\n(.*?)```",
    re.DOTALL | re.IGNORECASE,
)
_BARE_TOOL_RE = re.compile(
    r"\{\s*\"name\"\s*:\s*\"([^\"]+)\"\s*,\s*\"arguments\"\s*:\s*(\{.*?\})\s*\}",
    re.DOTALL,
)


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ModelTurn:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)


def get_provider() -> str:
    """ollama | api. vLLM se usa como provider=api con base local."""
    raw = (os.getenv("LLM_PROVIDER", "ollama") or "ollama").strip().lower()
    if raw in {"deepseek", "remote", "vllm"}:
        return "api"
    return raw


def get_model() -> str:
    provider = get_provider()
    if provider == "ollama":
        return (
            os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL).strip()
            or DEFAULT_OLLAMA_MODEL
        )
    return (
        os.getenv("API_MODEL")
        or os.getenv("DEEPSEEK_MODEL")
        or "deepseek-chat"
    ).strip()


def get_client() -> OpenAI:
    provider = get_provider()
    if provider == "ollama":
        base_url = (
            os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE).strip()
            or DEFAULT_OLLAMA_BASE
        )
        return OpenAI(api_key="ollama", base_url=base_url)

    api_key = (os.getenv("API_KEY") or os.getenv("DEEPSEEK_API_KEY") or "local").strip()
    base_url = (
        os.getenv("API_BASE_URL") or "https://api.deepseek.com"
    ).strip()
    return OpenAI(api_key=api_key, base_url=base_url)


def _parse_arguments(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {"_raw": raw}
        return parsed if isinstance(parsed, dict) else {"value": parsed}
    return {"value": raw}


def _calls_from_message(message: Any) -> list[ToolCall]:
    calls: list[ToolCall] = []
    for index, item in enumerate(getattr(message, "tool_calls", None) or []):
        function = getattr(item, "function", None)
        name = getattr(function, "name", None) or ""
        if not name:
            continue
        calls.append(
            ToolCall(
                id=str(getattr(item, "id", None) or f"call_{index}"),
                name=name,
                arguments=_parse_arguments(getattr(function, "arguments", None)),
            )
        )
    return calls


def _calls_from_text(content: str) -> list[ToolCall]:
    calls: list[ToolCall] = []
    for index, match in enumerate(_TOOL_FENCE_RE.finditer(content)):
        raw = match.group(1).strip()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict) or "name" not in payload:
            continue
        arguments = payload.get("arguments") or {}
        if not isinstance(arguments, dict):
            arguments = {"value": arguments}
        calls.append(
            ToolCall(
                id=str(payload.get("id") or f"text_{index}"),
                name=str(payload["name"]),
                arguments=arguments,
            )
        )
    if calls:
        return calls
    for index, match in enumerate(_BARE_TOOL_RE.finditer(content)):
        try:
            arguments = json.loads(match.group(2))
        except json.JSONDecodeError:
            continue
        if not isinstance(arguments, dict):
            continue
        calls.append(
            ToolCall(
                id=f"bare_{index}",
                name=match.group(1),
                arguments=arguments,
            )
        )
    return calls


def strip_tool_dumps(content: str) -> str:
    cleaned = _TOOL_FENCE_RE.sub("", content or "")
    cleaned = _BARE_TOOL_RE.sub("", cleaned)
    return scrub(re.sub(r"\n{3,}", "\n\n", cleaned).strip())


def _scrub_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in messages:
        row = dict(item)
        if isinstance(row.get("content"), str):
            row["content"] = scrub(row["content"])
        out.append(row)
    return out


def _int_env(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def chat(
    messages: list[dict[str, Any]],
    *,
    temperature: float = 0.2,
    tools: list[dict[str, Any]] | None = None,
    model: str | None = None,
    num_predict: int | None = None,
) -> ModelTurn:
    """Un turno de inferencia. Si el proveedor no soporta tools, se parsea el texto."""
    client = get_client()
    chosen = (model or "").strip() or get_model()
    messages = _scrub_messages(messages)
    heavy = any(token in chosen.lower() for token in ("r1", "70b", "32b", "14b"))
    num_predict = num_predict or _int_env("OLLAMA_NUM_PREDICT", 1200 if heavy else 500)
    num_ctx = _int_env("OLLAMA_NUM_CTX", 4096)
    think = (os.getenv("OLLAMA_THINK", "false") or "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "si",
        "sí",
    }
    kwargs: dict[str, Any] = {
        "model": chosen,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": num_predict,
        "extra_body": {
            "keep_alive": (os.getenv("OLLAMA_KEEP_ALIVE") or "30m").strip(),
            "think": think,
            "options": {
                "num_predict": num_predict,
                "num_ctx": num_ctx,
            },
        },
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    try:
        response: Any = client.chat.completions.create(**kwargs)
    except Exception:
        if not tools:
            raise
        kwargs.pop("tools", None)
        kwargs.pop("tool_choice", None)
        response = client.chat.completions.create(**kwargs)

    message = response.choices[0].message
    content = scrub(message.content or "").strip()
    tool_calls = _calls_from_message(message)
    if not tool_calls and content:
        tool_calls = _calls_from_text(content)
    if not content and not tool_calls:
        content = "(Respuesta vacía del modelo.)"
    return ModelTurn(content=content, tool_calls=tool_calls)

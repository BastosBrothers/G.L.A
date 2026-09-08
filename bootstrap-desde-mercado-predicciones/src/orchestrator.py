"""Middleware: resuelve el DAG, llama al modelo y pausa para function calling."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from src.context import build_system_prompt, build_user_message
from src.dag import resolve
from src.deepseek_client import ModelTurn, chat, strip_tool_dumps
from src.diff import PatchSet, extract_patches
from src.fs_ops import validate_write_args
from src.skills import Skill, detect_language, select_skills, strip_skill_directives, wants_skill_authoring
from src.text import scrub
from src.tools import SELF_TOOLS, WRITE_TOOLS, call_tool, openai_tools

_WRITE_INTENT = (
    "crea el archivo",
    "crear archivo",
    "guarda el archivo",
    "guardar el archivo",
    "guarda esto",
    "guardar esto",
    "escribe en",
    "escribir en",
    "crear carpeta",
    "crea la carpeta",
    "crea una carpeta",
    "mkdir",
    "touch ",
    "guardar como",
    "en disco",
    "crear skill",
    "crea un skill",
    "crea una skill",
    "haz un skill",
    "haz una skill",
    "skill de ",
    "skill para ",
    "nueva skill",
    "nuevo skill",
    "reescribe tu identidad",
    "reescribir identidad",
)

_CHAT_MARKS = (
    "hola",
    "buenas",
    "buen dia",
    "buen día",
    "hey",
    "hello",
    "hi ",
    "qué tal",
    "que tal",
    "cómo estás",
    "como estas",
    "como está",
    "cómo estas",
    "gracias",
    "quién eres",
    "quien eres",
    "qué eres",
    "que eres",
)

_CODE_MARKS = (
    "haz ",
    "crea ",
    "crear ",
    "programa",
    "código",
    "codigo",
    "archivo",
    "función",
    "funcion",
    "arregla",
    "edita",
    "refactor",
    "implementa",
    "bug",
    "error",
    "test",
    "script",
    ".py",
    "skill",
)


def wants_disk_write(text: str) -> bool:
    low = (text or "").lower()
    return any(token in low for token in _WRITE_INTENT)


def is_conversational(text: str) -> bool:
    """Saludo o charla corta: no tools, respuesta humana."""
    low = (text or "").strip().lower()
    if not low or len(low) > 160:
        return False
    if any(mark in low for mark in _CODE_MARKS):
        return False
    if wants_skill_authoring(low) or wants_disk_write(low):
        return False
    return any(mark in low for mark in _CHAT_MARKS)


def clean_model_text(text: str) -> str:
    """Quita thinking y basura típica de R1 / fugas de plantilla."""
    if not text:
        return text
    think_open = "<" + "think" + ">"
    think_close = "</" + "think" + ">"
    cleaned = text
    while True:
        start = cleaned.lower().find(think_open)
        if start < 0:
            # variante que a veces aparece en volcados
            start = cleaned.find("<think>")
            open_len = len("<think>") if start >= 0 else 0
            close_alt = "</think>"
        else:
            open_len = len(think_open)
            close_alt = think_close
        if start < 0:
            break
        end = cleaned.find(close_alt, start)
        if end < 0:
            end = cleaned.lower().find(think_close, start)
            close_len = len(think_close) if end >= 0 else 0
        else:
            close_len = len(close_alt)
        if end < 0:
            cleaned = cleaned[:start]
            break
        cleaned = cleaned[:start] + cleaned[end + close_len :]

    sys_open = "<｜system▁instruction｜>"
    while sys_open in cleaned:
        start = cleaned.find(sys_open)
        end = cleaned.find(sys_open, start + len(sys_open))
        if end < 0:
            cleaned = cleaned[:start]
            break
        cleaned = cleaned[:start] + cleaned[end + len(sys_open) :]

    for junk in (think_open, think_close, "</think>", "<think>", sys_open):
        cleaned = cleaned.replace(junk, "")
    return scrub(re.sub(r"\n{3,}", "\n\n", cleaned).strip())


def available_tools_for(message: str, graph_tools: list[str]) -> list[str]:
    if is_conversational(message):
        return []
    tools = [name for name in graph_tools if name not in SELF_TOOLS]
    if wants_disk_write(message):
        for name in SELF_TOOLS:
            if name not in tools:
                tools.append(name)
    return tools


@dataclass
class EngineRequest:
    message: str
    language: str | None = None
    selection: str | None = None
    diagnostics: list[str] | None = None
    pinned_skills: list[str] | None = None
    extra_context: str | None = None
    model: str | None = None


@dataclass
class ToolTrace:
    name: str
    arguments: dict[str, Any]
    result: str


@dataclass
class EngineResponse:
    message: str
    skills: list[str]
    tools_available: list[str]
    tool_trace: list[ToolTrace] = field(default_factory=list)
    patches: PatchSet | None = None
    language: str | None = None

    def to_dict(self) -> dict[str, Any]:
        patches = self.patches
        return {
            "message": self.message,
            "language": self.language,
            "skills": self.skills,
            "tools_available": self.tools_available,
            "tool_trace": [
                {
                    "name": item.name,
                    "arguments": item.arguments,
                    "result": item.result,
                }
                for item in self.tool_trace
            ],
            "patches": {
                "diffs": list(patches.diffs) if patches else [],
                "replaces": [
                    {
                        "path": item.path,
                        "start_line": item.start_line,
                        "end_line": item.end_line,
                        "content": item.content,
                    }
                    for item in (patches.replaces if patches else [])
                ],
                "files": [
                    {"path": item.path, "content": item.content}
                    for item in (patches.files if patches else [])
                ],
                "errors": list(patches.errors) if patches else [],
            },
        }

    def summary(self) -> str:
        names = ", ".join(self.skills) or "(ninguno)"
        tools = ", ".join(self.tools_available) or "(ninguna)"
        return (
            f"Lenguaje: {self.language or '-'}\n"
            f"Skills: {names}\n"
            f"Herramientas: {tools}\n"
            f"Llamadas: {len(self.tool_trace)}"
        )


def _tool_result_message(name: str, call_id: str, result: str) -> dict[str, Any]:
    return {
        "role": "tool",
        "tool_call_id": call_id,
        "name": name,
        "content": result,
    }


def _assistant_message(turn: ModelTurn) -> dict[str, Any]:
    payload: dict[str, Any] = {"role": "assistant", "content": turn.content or ""}
    if turn.tool_calls:
        payload["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.name,
                    "arguments": json.dumps(call.arguments, ensure_ascii=False),
                },
            }
            for call in turn.tool_calls
        ]
    return payload


def run(
    request: EngineRequest,
    *,
    max_tool_rounds: int = 4,
    confirm_write=None,
) -> EngineResponse:
    language = detect_language(request.message, request.language)
    if request.selection:
        language = detect_language(request.selection, language)

    selected: list[Skill] = select_skills(
        request.message,
        forced=request.pinned_skills,
        language=language,
    )
    graph = resolve([skill.name for skill in selected])
    tool_names = available_tools_for(request.message, list(graph.tools))
    language = language or next(
        (skill.language for skill in graph.ordered if skill.language),
        None,
    )

    clean = strip_skill_directives(request.message) or request.message
    talk = is_conversational(clean)
    system = build_system_prompt(
        active_skills=[] if talk else graph.ordered,
        tool_names=tool_names,
        language=language,
    )
    if talk:
        system += (
            "\n\n## Modo charla\n\n"
            "El usuario solo conversa. Responde en español, natural y breve. "
            "No llames herramientas. No entregues JSON ni bloques ```file. "
            "No inventes skills ni archivos.\n"
        )
    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": system,
        },
        {
            "role": "user",
            "content": build_user_message(
                clean,
                selection=None if talk else request.selection,
                diagnostics=None if talk else request.diagnostics,
                extra_context=None if talk else request.extra_context,
            ),
        },
    ]
    tools = [] if talk else openai_tools(tool_names)
    trace: list[ToolTrace] = []
    final = ModelTurn(content="")

    for round_index in range(max_tool_rounds + 1):
        final = chat(messages, tools=tools or None, model=request.model)
        if not final.tool_calls:
            break
        if talk:
            # Charla: ignora tool dumps y pide texto humano una vez.
            final = chat(
                messages
                + [
                    {
                        "role": "user",
                        "content": "Responde solo con texto humano. Sin JSON ni herramientas.",
                    }
                ],
                tools=None,
                model=request.model,
            )
            break
        if round_index >= max_tool_rounds:
            break
        messages.append(_assistant_message(final))
        for call in final.tool_calls:
            if call.name in WRITE_TOOLS:
                invalid = validate_write_args(call.name, call.arguments)
                if invalid:
                    result = invalid
                elif confirm_write is None or not confirm_write(
                    call.name, call.arguments
                ):
                    result = "El usuario no confirmó. No se creó ni se modificó nada."
                else:
                    result = call_tool(call.name, call.arguments)
            else:
                result = call_tool(call.name, call.arguments)
            trace.append(
                ToolTrace(name=call.name, arguments=call.arguments, result=result)
            )
            messages.append(_tool_result_message(call.name, call.id, result))

    text = strip_tool_dumps(clean_model_text(final.content or ""))
    if talk and (not text or text.startswith("{")):
        text = "Hola. Estoy bien, listo para ayudarte a programar. ¿Qué quieres hacer?"
    if final.tool_calls and not text and not talk:
        text = "(El modelo pidió herramientas pero se alcanzó el límite de rondas.)"
    return EngineResponse(
        message=text,
        skills=[] if talk else graph.names,
        tools_available=tool_names,
        tool_trace=trace,
        patches=None if talk else extract_patches(text),
        language=language,
    )

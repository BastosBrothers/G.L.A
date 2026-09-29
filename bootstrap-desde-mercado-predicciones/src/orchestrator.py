"""Middleware: resuelve el DAG, llama al modelo y pausa para function calling."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from src.context import build_create_system_prompt, build_system_prompt, build_user_message
from src.dag import resolve
from src.deepseek_client import ModelTurn, chat, strip_tool_dumps
from src.diff import NewFile, PatchSet, extract_patches
from src.entregas import recent_for_project
from src.fs_ops import validate_write_args
from src.models_route import create_num_predict, model_for_explain, model_for_mode
from src.skills import (
    Skill,
    detect_language,
    get_skill,
    select_skills,
    strip_skill_directives,
    wants_skill_authoring,
)
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
    "haga",
    "hagamos",
    "vamos a",
    "crea ",
    "crear ",
    "armemos",
    "armar ",
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
    "calculadora",
    "menú",
    "menu",
    "bug",
    "error",
    "test",
    "script",
    "python",
    ".py",
    "skill",
)

_CREATE_MARKS = (
    "haz ",
    "haga",
    "hagamos",
    "vamos a",
    "crea ",
    "crear ",
    "cree ",
    "armemos",
    "armar ",
    "arma ",
    "implementa",
    "programa ",
    "programar",
    "escribe un",
    "escribe una",
    "hazme ",
    "quiero una",
    "quiero un",
    "necesito una",
    "necesito un",
    "calculadora",
    "nuevo proyecto",
    "desde cero",
    # Enunciados / inglés (SPOJ, etc.)
    "your program",
    "write a program",
    "write a python",
    "brute-force",
    "brute force",
    "rewrite small numbers",
    "stop processing input",
    "all numbers at input",
    "sample input",
    "sample output",
    "enunciado",
    "resuelve",
    "resolver",
)


def wants_disk_write(text: str) -> bool:
    low = (text or "").lower()
    return any(token in low for token in _WRITE_INTENT)


def wants_code_creation(text: str) -> bool:
    """Pide un programa/archivo nuevo (no solo editar o charlar)."""
    low = (text or "").strip().lower()
    if not low:
        return False
    if any(mark in low for mark in _CREATE_MARKS):
        return True
    if re.search(r"\b(haz|crea|crear|arm[ae]|implementa|programa)\b", low):
        return True
    # Problema de programación con E/S típica.
    if ("input" in low and "output" in low) and (
        "42" in low or "program" in low or "integer" in low
    ):
        return True
    return False


def is_conversational(text: str) -> bool:
    """Saludo o charla corta: no tools, respuesta humana."""
    low = (text or "").strip().lower()
    if not low or len(low) > 160:
        return False
    if any(mark in low for mark in _CODE_MARKS):
        return False
    if wants_code_creation(low) or wants_skill_authoring(low) or wants_disk_write(low):
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
    # Creación: sin tools para evitar JSON basura; el IDE aplica bloques ```file.
    if wants_code_creation(message) and not wants_disk_write(message):
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
    project_root: str | None = None
    mode: str | None = None


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
    language = detect_language(request.message, None) or detect_language(
        request.message, request.language
    )
    if request.selection and not language:
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
    create = (not talk) and wants_code_creation(clean)
    mode = (request.mode or ("chat" if talk else ("create" if create else "edit"))).lower()
    if talk:
        mode = "chat"
    elif create:
        mode = "create"
    multi = bool(create and _wants_multi_file(clean))
    resolved_model = model_for_mode(mode, explicit=request.model, hard=multi)

    if create:
        core = get_skill(f"{language}_core") if language else None
        system = build_create_system_prompt(
            language=language,
            multi=multi,
            core_skill=core,
        )
    else:
        system = build_system_prompt(
            active_skills=[] if talk else graph.ordered,
            tool_names=[] if talk else tool_names,
            language=language,
        )
    if talk:
        system += (
            "\n\n## Modo charla\n\n"
            "El usuario solo conversa. Responde en español, natural y breve. "
            "No llames herramientas. No entregues JSON ni bloques ```file. "
            "No inventes skills ni archivos.\n"
        )
    suggest = _suggest_create_path(clean, language) if create else None
    user_extra = None if talk else request.extra_context
    if create:
        user_extra = (
            (user_extra or "").strip()
            or "Modo creación: archivos nuevos relativos al proyecto."
        )
        deliveries = recent_for_project(request.project_root or "")
        if deliveries:
            user_extra += "\n\n" + deliveries
        if multi:
            expected = _expected_file_count(clean)
            declared = _paths_from_request(clean, language)
            path_hint = ""
            if declared:
                path_hint = " Paths exactos:\n" + "\n".join(f"- {p}" for p in declared)
            user_extra += (
                f"\nEntrega exactamente {expected} bloques ```file "
                "(uno por archivo), código real correlacionado. "
                "Imports entre archivos del mismo directorio: "
                "`from modulo import ...` (sin prefijo de paquete). "
                "Prohibido un stub único en app/main.py."
                f"{path_hint}"
            )
        elif suggest:
            user_extra += (
                f"\nUsa esta ruta relativa: {suggest}\n"
                "Formato obligatorio: bloque ```file, línea path:, línea ---, "
                "luego el código real completo, luego cierre ```. "
                "Sin cuerpo vacío y sin rutas absolutas."
            )
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": build_user_message(
                clean,
                selection=None if talk else request.selection,
                diagnostics=None if talk else request.diagnostics,
                extra_context=user_extra,
            ),
        },
    ]
    tools = [] if (talk or create) else openai_tools(tool_names)
    trace: list[ToolTrace] = []
    final = ModelTurn(content="")
    predict = create_num_predict(multi=multi) if create else None
    text = ""
    patches: PatchSet | None = None

    # 3+ archivos: el 3b colapsa en un solo main → create secuencial de entrada.
    if create and multi and _expected_file_count(clean) >= 3:
        targets = _paths_from_request(clean, language) or _default_multi_paths(
            clean, language, _expected_file_count(clean)
        )
        patches = _create_files_sequential(
            clean,
            language=language,
            paths=targets,
            model=resolved_model,
        )
        text = (
            f"Creé {len(patches.files)} archivos correlacionados "
            f"({', '.join(f.path for f in patches.files)})."
        )
    else:
        for round_index in range(max_tool_rounds + 1):
            final = chat(
                messages,
                tools=tools or None,
                model=resolved_model,
                num_predict=predict,
            )
            if not final.tool_calls:
                break
            if talk or create:
                if talk:
                    nudge = "Responde solo con texto humano. Sin JSON ni herramientas."
                elif multi:
                    nudge = (
                        f"Entrega {_expected_file_count(clean)} bloques ```file "
                        "distintos con código completo. Sin JSON."
                    )
                else:
                    nudge = (
                        f"Entrega el programa en ```file con path: {suggest}. "
                        "Código completo. Sin JSON ni rutas absolutas."
                    )
                final = chat(
                    messages + [{"role": "user", "content": nudge}],
                    tools=None,
                    model=resolved_model,
                    num_predict=predict,
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
        if create and (
            _looks_like_demo_echo(text)
            or not _create_output_ok(text, language, suggest, user_message=clean)
        ):
            retry_messages = _create_retry_messages(
                clean, language, suggest, multi=multi
            )
            final = chat(
                retry_messages,
                tools=None,
                model=resolved_model,
                num_predict=predict,
            )
            text = strip_tool_dumps(clean_model_text(final.content or ""))
        if (not talk) and (not text or text.startswith("(")) and (
            final.tool_calls or "límite de rondas" in (text or "")
        ):
            suggest = suggest or _suggest_create_path(clean, language)
            final = chat(
                _create_retry_messages(clean, language, suggest, multi=False),
                tools=None,
                model=resolved_model,
                num_predict=predict or 1400,
            )
            text = strip_tool_dumps(clean_model_text(final.content or ""))
            create = True
        if final.tool_calls and not text and not talk:
            text = (
                "No pude terminar con herramientas. "
                "Reintenta el pedido o pide: crea el programa en un archivo Python."
            )
        patches = None if talk else extract_patches(text)
        if create and suggest and patches and patches.files:
            patches.files = _normalize_create_paths(
                patches.files, suggest, language, multi=multi
            )
        if patches and patches.files:
            real = [f for f in patches.files if not _is_stub_content(f.content or "")]
            dropped = len(patches.files) - len(real)
            patches.files = real
            if dropped and not real and create:
                text = (
                    (text or "").rstrip()
                    + "\n\n(No apliqué stubs vacíos. Vuelve a pedir los ejercicios "
                    "con el historial o pega el código a conservar.)"
                )

        if create and multi and patches is not None:
            need = _expected_file_count(clean)
            declared = _paths_from_request(clean, language)
            if not _multi_delivery_ok(patches.files, clean):
                if need < 3:
                    retry = chat(
                        _create_retry_messages(clean, language, suggest, multi=True),
                        tools=None,
                        model=resolved_model,
                        num_predict=predict,
                    )
                    retry_text = strip_tool_dumps(clean_model_text(retry.content or ""))
                    retry_patches = extract_patches(retry_text)
                    if retry_patches.files:
                        retry_patches.files = [
                            f
                            for f in _normalize_create_paths(
                                retry_patches.files,
                                suggest or "app/main.py",
                                language,
                                multi=True,
                            )
                            if not _is_stub_content(f.content or "")
                        ]
                    if _multi_delivery_ok(retry_patches.files, clean):
                        patches = retry_patches
                        text = retry_text
                if not _multi_delivery_ok(patches.files, clean):
                    targets = declared or _default_multi_paths(clean, language, need)
                    if len(targets) >= 2:
                        seq = _create_files_sequential(
                            clean,
                            language=language,
                            paths=targets,
                            model=resolved_model,
                        )
                        if len(seq.files) >= max(2, need) or _multi_delivery_ok(
                            seq.files, clean
                        ):
                            patches = seq
                            text = (
                                f"Creé {len(seq.files)} archivos correlacionados "
                                f"({', '.join(f.path for f in seq.files)})."
                            )

    if create and patches and patches.files:
        patches.files = _fix_sibling_imports(patches.files)

    if create and patches and patches.files:
        text = _explain_create_pass(
            clean,
            code_text=text,
            patches=patches,
            language=language,
            model=model_for_explain(explicit=request.model),
        )
    elif text and _is_manual_tutorial(text) and patches and patches.files:
        text = _format_create_message(
            "Entregué el código en el proyecto. No hace falta pegarlo a mano.",
            patches,
        )

    return EngineResponse(
        message=text,
        skills=[] if talk else graph.names,
        tools_available=tool_names,
        tool_trace=trace,
        patches=patches,
        language=language,
    )



def _expected_file_count(message: str) -> int:
    declared = _paths_from_request(message, None)
    if len(declared) >= 2:
        return len(declared)
    low = (message or "").lower()
    if re.search(r"\b(cuatro|4)\b", low):
        return 4
    if re.search(r"\b(tres|3)\b", low):
        return 3
    if re.search(r"\b(dos|2)\b", low):
        return 2
    if _wants_multi_file(low):
        return 2
    return 1


def _paths_from_request(message: str, language: str | None) -> list[str]:
    """Paths explícitos del pedido (p. ej. tienda/precios.py)."""
    ext = {"python": "py", "rust": "rs", "c": "c"}.get((language or "python"), "py")
    found: list[str] = []
    for match in re.finditer(
        rf"([A-Za-z_][\w.-]*(?:/[A-Za-z_][\w.-]*)+\.{ext})",
        message or "",
        re.IGNORECASE,
    ):
        path = match.group(1).replace("\\", "/")
        low = path.lower()
        if low not in {p.lower() for p in found}:
            found.append(path)
    return found[:8]


def _default_multi_paths(message: str, language: str | None, need: int) -> list[str]:
    ext = {"python": "py", "rust": "rs", "c": "c"}.get((language or "python"), "py")
    low = (message or "").lower()
    folder = "proyecto"
    for word in ("tienda", "notas", "tareas", "calc", "juego", "api", "bot"):
        if word in low:
            folder = word
            break
    named = re.search(r"\b([a-z][a-z0-9_]{2,20})/", low)
    if named and named.group(1) not in {"app", "src", "path", "http", "https"}:
        folder = named.group(1)
    if need <= 2:
        return [f"{folder}/ops.{ext}", f"{folder}/main.{ext}"]
    if need == 3:
        return [
            f"{folder}/mod_a.{ext}",
            f"{folder}/mod_b.{ext}",
            f"{folder}/main.{ext}",
        ]
    return [f"{folder}/mod_{i}.{ext}" for i in range(1, need)] + [f"{folder}/main.{ext}"]


def _create_files_sequential(
    clean: str,
    *,
    language: str | None,
    paths: list[str],
    model: str | None,
) -> PatchSet:
    """Crea un ```file por llamada. Más lento, mucho más fiable con 3b."""
    files: list[NewFile] = []
    prior: list[str] = []
    lang = language or "python"
    for path in paths:
        prior_block = ""
        if prior:
            prior_block = (
                "Archivos ya creados (no los reescribas; impórtalos si hace falta):\n"
                + "\n".join(prior)
                + "\n\n"
            )
        siblings = [p.rsplit("/", 1)[-1].rsplit(".", 1)[0] for p in paths if p != path]
        import_hint = ""
        if siblings:
            import_hint = (
                "Si importas un hermano del mismo directorio usa "
                f"`from {siblings[0]} import ...` (sin prefijo de carpeta).\n"
            )
        turn = chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Eres Gla-2. Ahora entregas UN solo archivo. "
                        "Un bloque ```file con path: exactamente el pedido, "
                        "línea ---, código completo real. Sin otros archivos. "
                        "Sin ```python suelto. Sin stubs."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Pedido global:\n{clean}\n\n"
                        f"{prior_block}"
                        f"Escribe SOLO este archivo ahora: {path}\n"
                        f"Lenguaje: {lang}\n"
                        f"{import_hint}"
                        "Formato exacto:\n"
                        f"```file\npath: {path}\n---\n"
                        "# código completo\n```"
                    ),
                },
            ],
            tools=None,
            model=model,
            num_predict=900,
        )
        chunk = strip_tool_dumps(clean_model_text(turn.content or ""))
        extracted = extract_patches(chunk)
        chosen: NewFile | None = None
        for item in extracted.files:
            if _is_stub_content(item.content or ""):
                continue
            item_path = (item.path or "").replace("\\", "/")
            if item_path == path or item_path.endswith("/" + path.split("/")[-1]):
                item.path = path
                chosen = item
                break
        if chosen is None:
            for item in extracted.files:
                if not _is_stub_content(item.content or ""):
                    item.path = path
                    chosen = item
                    break
        if chosen is None:
            # Último recurso: cuerpo dentro de fences file mal formados / python.
            recovered = extract_patches(chunk).files
            for item in recovered:
                if not _is_stub_content(item.content or ""):
                    item.path = path
                    chosen = item
                    break
        if chosen is not None:
            files.append(chosen)
            preview = (chosen.content or "").strip().splitlines()
            head = "\n".join(preview[:12])
            prior.append(f"- {path}:\n```\n{head}\n```")
    return PatchSet(diffs=[], replaces=[], files=files, errors=[])


def _create_retry_messages(
    clean: str,
    language: str | None,
    suggest: str | None,
    *,
    multi: bool,
) -> list[dict[str, str]]:
    if multi:
        n = _expected_file_count(clean)
        paths = _paths_from_request(clean, language) or _default_multi_paths(
            clean, language, n
        )
        path_lines = "\n".join(f"- {p}" for p in paths)
        system = (
            "Eres Gla-2. Entrega EXACTAMENTE varios bloques ```file "
            "(path relativo + --- + código completo). "
            "Cada archivo correlacionado. Imports del mismo directorio: "
            "`from modulo import ...`. Sin stubs ni un solo main vacío."
        )
        user = (
            f"{clean}\n\n"
            f"Obligatorio: {len(paths)} bloques ```file distintos con código real.\n"
            f"Paths exactos:\n{path_lines}\n"
            "No fusiones todo en app/main.py ni ejercicios/main.py solo."
        )
    else:
        system = (
            "Eres Gla-2. Entrega el programa pedido en un bloque ```file "
            "con path relativo y código completo y real. "
            "Puedes poner una frase breve antes; lo importante es el código."
        )
        user = (
            f"{clean}\n\n"
            f"Entrega un bloque ```file con path: {suggest or 'app/main.py'} "
            "y el código completo debajo de ---. "
            "Sin rutas absolutas, sin editar otros archivos, sin placeholders."
        )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _multi_delivery_ok(files: list, user_message: str) -> bool:
    if not files:
        return False
    need = _expected_file_count(user_message)
    real = [f for f in files if not _is_stub_content(getattr(f, "content", "") or "")]
    if len(real) < max(2, need):
        return False
    # Un solo archivo que importa un paquete inexistente no cuenta como multi.
    if len(real) == 1:
        body = (real[0].content or "").lower()
        if "import " in body and "from " in body:
            return False
    declared = _paths_from_request(user_message, None)
    if declared and len(real) >= need:
        got = { (getattr(f, "path", "") or "").replace("\\", "/").lower() for f in real }
        # Al menos la mitad de los paths pedidos (o main + otro).
        hits = sum(1 for p in declared if p.lower() in got or any(g.endswith("/" + p.split("/")[-1].lower()) for g in got))
        if hits < min(2, len(declared)):
            return False
    return True


def _fix_sibling_imports(files: list) -> list:
    """from paquete.mod → from mod si ambos viven en paquete/."""
    by_parent: dict[str, set[str]] = {}
    for item in files:
        path = (item.path or "").replace("\\", "/")
        if "/" not in path:
            continue
        parent, name = path.rsplit("/", 1)
        stem = name.rsplit(".", 1)[0]
        by_parent.setdefault(parent, set()).add(stem)

    for item in files:
        path = (item.path or "").replace("\\", "/")
        if "/" not in path or not item.content:
            continue
        parent = path.rsplit("/", 1)[0]
        pkg = parent.split("/")[-1]
        siblings = by_parent.get(parent) or set()
        content = item.content
        for stem in siblings:
            # from notas.ops import X  → from ops import X
            content = re.sub(
                rf"\bfrom\s+{re.escape(pkg)}\.{re.escape(stem)}\s+import\b",
                f"from {stem} import",
                content,
            )
            content = re.sub(
                rf"\bimport\s+{re.escape(pkg)}\.{re.escape(stem)}\b",
                f"import {stem}",
                content,
            )
        item.content = content
    return files


def _run_hint_for_paths(paths: list[str], language: str | None) -> str:
    if not paths:
        return "python main.py"
    lang = language or "python"
    if lang == "rust":
        return "cargo run"
    if lang == "c":
        return "compila y ejecuta el binario"
    mains = [p for p in paths if p.replace("\\", "/").endswith("main.py")]
    target = mains[0] if mains else paths[0]
    return f"python {target}"


def _explain_create_pass(
    user_request: str,
    *,
    code_text: str,
    patches: PatchSet,
    language: str | None,
    model: str | None,
) -> str:
    """Pase B: prosa corta sin regenerar código. patches ya vienen del pase A."""
    _ = code_text  # el fence visible se reconstruye desde patches
    paths = [item.path for item in patches.files if item.path]
    path_list = ", ".join(f"`{p}`" for p in paths) or "`(archivo)`"
    run_hint = _run_hint_for_paths(paths, language)

    explain = chat(
        [
            {
                "role": "system",
                "content": (
                    "Eres Gla-2. Explica en español, en 2–3 frases, qué hace el programa "
                    "y cómo ejecutarlo en terminal. "
                    "Prohibido decir que el usuario abra el editor, cree archivos a mano "
                    "o pegue código: el IDE ya escribe los archivos. "
                    "Sin bloques ```file, sin JSON, solo prosa."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Pedido del usuario: {user_request.strip()}\n"
                    f"Archivos que el IDE va a crear: {path_list}\n"
                    f"Comando típico: {run_hint}\n"
                    "Explica qué hace y cómo probarlo."
                ),
            },
        ],
        tools=None,
        model=model,
        num_predict=160,
    )
    prose = strip_tool_dumps(clean_model_text(explain.content or "")).strip()
    if (
        not prose
        or prose.startswith("{")
        or "```file" in prose.lower()
        or _looks_like_demo_echo(prose)
        or _is_manual_tutorial(prose)
    ):
        prose = (
            f"Voy a crear {path_list} en el proyecto. "
            f"Para probarlo: `{run_hint}`."
        )
    # Mensaje estable: prosa + fences ```file reales (el IDE aplica patches, no el tutorial).
    return _format_create_message(prose, patches)


def _is_manual_tutorial(text: str) -> bool:
    low = (text or "").lower()
    marks = (
        "abre tu editor",
        "abre el editor",
        "crea un nuevo archivo",
        "editor de código favorito",
        "agrega el siguiente código",
        "paso 1:",
        "pega el código",
    )
    return any(mark in low for mark in marks)


def _format_create_message(prose: str, patches: PatchSet) -> str:
    parts = [prose.strip()] if prose.strip() else []
    for item in patches.files:
        body = (item.content or "").rstrip() + "\n"
        parts.append(f"```file\npath: {item.path}\n---\n{body}```")
    parts.append("El IDE crea estos archivos solos en el proyecto (no hace falta pegarlos a mano).")
    return "\n\n".join(parts)


def _normalize_create_paths(
    files: list,
    suggest: str,
    language: str | None,
    *,
    multi: bool = False,
) -> list:
    """Si el modelo entregó main.py suelto, súbelo a la ruta sugerida.
    En multi-archivo no fusionar todo a un solo path."""
    want_ext = {
        "python": ".py",
        "rust": ".rs",
        "c": ".c",
    }.get((language or "python"), ".py")
    fixed = []
    for index, item in enumerate(files):
        path = (item.path or "").replace("\\", "/")
        low = path.lower()
        bare = "/" not in path
        wrong_place = any(
            token in low for token in ("gestor-git", "panel.ps1", "hola-mundo")
        )
        if multi:
            if wrong_place or (want_ext and not path.endswith(want_ext)):
                item.path = f"ejercicios/{index + 1:02d}_main{want_ext}"
            elif bare:
                stem = path.rsplit(".", 1)[0] or f"ej{index + 1}"
                item.path = f"ejercicios/{stem}{want_ext}"
        elif wrong_place or bare or not path.endswith(want_ext):
            item.path = suggest
        fixed.append(item)
    return fixed


def _wants_multi_file(message: str) -> bool:
    low = (message or "").lower()
    marks = (
        "tres archivos",
        "tres ejercicios",
        "archivos separados",
        "retomemos",
        "retomar",
        "varios archivos",
        "cada ejercicio",
        "correspondientes",
        "separados",
    )
    if any(mark in low for mark in marks):
        return True
    return bool(re.search(r"\b(dos|tres|cuatro|2|3|4)\s+archivos?\b", low))


def _is_stub_content(content: str) -> bool:
    low = (content or "").lower()
    if not low.strip():
        return True
    if "aquí va el código" in low or "aqui va el codigo" in low:
        return True
    if "puedes agregar tu código" in low or "puedes agregar tu codigo" in low:
        return True
    if "aquí puedes agregar" in low or "aqui puedes agregar" in low:
        return True
    compact = re.sub(r"\s+", " ", low)
    if "def main(" in compact and " pass" in compact and len(compact) < 180:
        return True
    compact_nospace = re.sub(r"\s", "", content or "")
    if len(compact_nospace) < 40:
        # Funciones cortas reales (return / print) no son stub.
        if "return" in low or "print(" in low or "input(" in low:
            return False
        return True
    return False


def _suggest_create_path(message: str, language: str | None) -> str:
    low = (message or "").lower()
    ext = {"python": "py", "rust": "rs", "c": "c"}.get((language or "python"), "py")
    # Si el usuario ya dio un path concreto, úsalo.
    explicit = re.search(
        rf"([a-z0-9_\-]+(?:/[a-z0-9_\-]+)+\.{ext})",
        low,
    )
    if explicit and not _wants_multi_file(low):
        return explicit.group(1)
    if _wants_multi_file(low):
        # Preferir carpeta nombrada (notas/, tienda/, calc_mod/) si aparece.
        folder = re.search(r"\b([a-z][a-z0-9_]{1,24})/", low)
        if folder and folder.group(1) not in {"app", "src", "path"}:
            return f"{folder.group(1)}/main.{ext}"
        return f"proyecto/main.{ext}"
    for word, folder in (
        ("calculadora", "calculadora"),
        ("calculator", "calculadora"),
        ("answer to life", "life"),
        ("universe, and everything", "life"),
        ("42", "life"),
        ("menu", "menu"),
        ("menú", "menu"),
        ("juego", "juego"),
        ("api", "api"),
        ("bot", "bot"),
        ("script", "script"),
        ("hola", "hola_nombre"),
        ("suma", "suma_dos"),
        ("tabla", "tabla_5"),
    ):
        if word in low:
            return f"{folder}/main.{ext}"
    return f"app/main.{ext}"


def _create_output_ok(
    text: str,
    language: str | None,
    suggest: str | None,
    *,
    user_message: str | None = None,
) -> bool:
    patches = extract_patches(text or "")
    if not patches.files:
        return False
    want_ext = {
        "python": ".py",
        "rust": ".rs",
        "c": ".c",
    }.get((language or "python"), ".py")
    probe = user_message if user_message is not None else text
    multi = _wants_multi_file(probe or "")
    if multi and len(patches.files) < 2:
        return False
    for item in patches.files:
        path = (item.path or "").replace("\\", "/").lower()
        body = (item.content or "").strip()
        if _is_stub_content(body):
            return False
        if path.endswith((".ps1", ".bat", ".cmd")) and want_ext == ".py":
            return False
        if "gestor-git" in path or "panel.ps1" in path:
            return False
        if want_ext and not path.endswith(want_ext):
            return False
        if ":" in path or path.startswith("/"):
            return False
    return True


def _looks_like_demo_echo(text: str) -> bool:
    low = (text or "").lower()
    if "print(\"hola\")" in low or "print('hola')" in low:
        return True
    if "hola mundo" in low or "¡hola mundo!" in low or "hola-mundo" in low:
        return True
    if "aquí va el código" in low or "aqui va el codigo" in low:
        return True
    if "puedes agregar tu código" in low or "puedes agregar tu codigo" in low:
        return True
    if "aquí puedes agregar" in low or "aqui puedes agregar" in low:
        return True
    if "agregar_a_skill" in low and "```file" not in low:
        return True
    if re.search(r"path:\s*[a-z]:[\\/]", low) or re.search(r"```file,\s*[a-z]:", low):
        return True
    if "gestor-git" in low or "panel.ps1" in low:
        return True
    if "```file" in low and "---" in low:
        patches = extract_patches(text)
        if not patches.files:
            return True
        if all(_is_stub_content(f.content or "") for f in patches.files):
            return True
    return False

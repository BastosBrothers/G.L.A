"""Contrato IDE: tests sin Ollama (detección, stubs, tutoriales, multi-archivo)."""

from __future__ import annotations

import os

from src.models_route import model_for_mode
from src.orchestrator import (
    _create_output_ok,
    _is_manual_tutorial,
    _is_stub_content,
    _looks_like_demo_echo,
    _wants_multi_file,
    wants_code_creation,
)


def run_checks() -> list[str]:
    errors: list[str] = []

    spoj = (
        "Your program is to use the brute-force approach. "
        "Stop processing input after reading in the number 42. "
        "Sample Input / Sample Output"
    )
    if not wants_code_creation(spoj):
        errors.append("SPOJ inglés debería activar creación")

    calc = "hagamos una calculadora para terminal en python"
    if not wants_code_creation(calc):
        errors.append("calculadora debería activar creación")

    multi = "retomemos los tres ejercicios, hagamos tres archivos separados"
    if not _wants_multi_file(multi):
        errors.append("retomemos/tres archivos debería ser multi")

    stub = (
        "def main():\n"
        "    # Aqui puedes agregar tu codigo para los ejercicios\n"
        "    pass\n\n"
        "if __name__ == '__main__':\n"
        "    main()\n"
    )
    if not _is_stub_content(stub):
        errors.append("stub pass debería detectarse")

    fence = f"```file\npath: app/main.py\n---\n{stub}```"
    if not _looks_like_demo_echo(fence):
        errors.append("fence stub debería ser demo echo")
    if _create_output_ok(fence, "python", "app/main.py"):
        errors.append("fence stub no debería pasar _create_output_ok")

    tutorial = "Abre tu editor de código favorito y crea un nuevo archivo"
    if not _is_manual_tutorial(tutorial):
        errors.append("tutorial manual debería detectarse")

    real = (
        "```file\npath: life/main.py\n---\n"
        "def main() -> None:\n"
        "    while True:\n"
        "        n = int(input())\n"
        "        if n == 42:\n"
        "            break\n"
        "        print(n)\n\n"
        "if __name__ == '__main__':\n"
        "    main()\n"
        "```"
    )
    if not _create_output_ok(real, "python", "life/main.py"):
        errors.append("programa life real debería pasar _create_output_ok")

    # Aislar de OLLAMA_MODEL_* del entorno del usuario.
    old_create = os.environ.pop("OLLAMA_MODEL_CREATE", None)
    old_chat = os.environ.pop("OLLAMA_MODEL_CHAT", None)
    try:
        create_default = model_for_mode("create", explicit=None)
        if create_default != "qwen2.5-coder:3b":
            errors.append(f"create default esperado qwen2.5-coder:3b, got {create_default}")
        create_from_light = model_for_mode("create", explicit="gla-2")
        if create_from_light != "qwen2.5-coder:3b":
            errors.append("create con gla-2 explícito debería escalar a coder:3b")
        chat_default = model_for_mode("chat", explicit=None)
        if chat_default != "gla-2":
            errors.append(f"chat default esperado gla-2, got {chat_default}")
        heavy = model_for_mode("create", explicit="qwen2.5-coder:7b")
        if heavy != "qwen2.5-coder:7b":
            errors.append("create debe respetar modelo pesado explícito")
    finally:
        if old_create is not None:
            os.environ["OLLAMA_MODEL_CREATE"] = old_create
        if old_chat is not None:
            os.environ["OLLAMA_MODEL_CHAT"] = old_chat

    return errors


def main() -> int:
    errs = run_checks()
    if errs:
        print("FAIL")
        for item in errs:
            print(f"- {item}")
        return 1
    print("OK: contrato IDE (creación, stubs, tutoriales, multi-archivo, modelos)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

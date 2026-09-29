"""Contrato IDE: tests sin Ollama (detección, stubs, tutoriales, multi-archivo)."""

from __future__ import annotations

import os
from types import SimpleNamespace

from src.diff import extract_patches
from src.models_route import create_num_predict, model_for_explain, model_for_mode
from src.orchestrator import (
    _create_output_ok,
    _expected_file_count,
    _fix_sibling_imports,
    _is_manual_tutorial,
    _is_stub_content,
    _looks_like_demo_echo,
    _multi_delivery_ok,
    _paths_from_request,
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
    if _expected_file_count(multi) != 3:
        errors.append("tres archivos → expected 3")

    three_paths = (
        "crea tres archivos: tienda/precios.py, tienda/carrito.py y tienda/main.py"
    )
    got_paths = _paths_from_request(three_paths, "python")
    if got_paths != ["tienda/precios.py", "tienda/carrito.py", "tienda/main.py"]:
        errors.append(f"paths_from_request falló: {got_paths}")
    if _expected_file_count(three_paths) != 3:
        errors.append("3 paths explícitos → expected 3")

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

    multi_one = (
        "```file\npath: ejercicios/main.py\n---\n"
        "from tienda import carrito\n"
        "print(carrito.total([1]))\n"
        "```"
    )
    if _create_output_ok(
        multi_one,
        "python",
        "ejercicios/main.py",
        user_message="crea tres archivos separados correlacionados",
    ):
        errors.append("un solo fence no debería pasar create_ok en multi")

    files = [
        SimpleNamespace(
            path="notas/ops.py",
            content="def sumar(a, b):\n    return a + b\n",
        ),
        SimpleNamespace(
            path="notas/main.py",
            content="from notas.ops import sumar\nprint(sumar(1, 2))\n",
        ),
    ]
    fixed = _fix_sibling_imports(files)
    if "from ops import sumar" not in fixed[1].content:
        errors.append("imports de hermano deberían volverse relativos")
    if not _multi_delivery_ok(fixed, "dos archivos separados correlacionados"):
        errors.append("dos archivos reales deberían pasar multi_delivery_ok")

    # Fence roto típico: ```file con solo el path + código en ```python.
    broken = (
        "Voy a crear la lista.\n"
        "```file\n"
        "tareas/store.py\n"
        "```\n"
        "```python\n"
        "import json\n"
        "def cargar():\n"
        "    return []\n"
        "def guardar(lista):\n"
        "    pass\n"
        "```\n"
        "```file\n"
        "tareas/main.py\n"
        "```\n"
        "```python\n"
        "from store import cargar, guardar\n"
        "def main():\n"
        "    print(cargar())\n"
        "if __name__ == '__main__':\n"
        "    main()\n"
        "```\n"
    )
    recovered = extract_patches(broken).files
    if len(recovered) < 2:
        errors.append(f"fence file+python debería recuperar 2 archivos, got {len(recovered)}")
    else:
        paths = {item.path.replace('\\', '/') for item in recovered}
        if "tareas/store.py" not in paths or "tareas/main.py" not in paths:
            errors.append(f"paths recuperados incorrectos: {paths}")
        if "def cargar" not in (recovered[0].content + recovered[1].content):
            errors.append("código python no se emparejó al path")

    old_create = os.environ.pop("OLLAMA_MODEL_CREATE", None)
    old_chat = os.environ.pop("OLLAMA_MODEL_CHAT", None)
    try:
        create_default = model_for_mode("create", explicit=None)
        if create_default != "qwen2.5-coder:3b":
            errors.append(f"create default esperado qwen2.5-coder:3b, got {create_default}")
        if model_for_explain() != "gla-2":
            errors.append("explain debería usar gla-2")
        if create_num_predict(multi=False) < 100:
            errors.append("predict create demasiado bajo")
        if create_num_predict(multi=True) <= create_num_predict(multi=False):
            errors.append("predict multi debería ser mayor que simple")
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

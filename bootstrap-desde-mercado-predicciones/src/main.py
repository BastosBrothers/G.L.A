"""CLI del motor Gla-2 y contrato JSON para Neovim."""

from __future__ import annotations

import argparse
import json
import sys

from src.dag import explain, resolve
from src.deepseek_client import get_model, get_provider
from src.fs_ops import describir_escritura
from src.orchestrator import EngineRequest, run
from src.paths import ROOT
from src.sandbox import format_report, run_sandbox
from src.skills import format_catalog, get_skill, load_skills
from src.text import scrub, scrub_tree


def _confirm_write(name: str, arguments: dict) -> bool:
    from src.fs_ops import validate_write_args

    invalid = validate_write_args(name, arguments)
    if invalid:
        print(f"\n{invalid}")
        return False
    print("\nGla-2 quiere escribir en tu equipo. Aún no se ha creado nada.")
    print(describir_escritura(name, arguments))
    try:
        answer = input("¿Confirmas? [s/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return answer in {"s", "si", "sí", "y", "yes"}


def cmd_chat(args: argparse.Namespace) -> int:
    print(
        "Gla-2 — motor de programación "
        "(comandos: /skills | /skill nombre | /pin nombre | /unpin | /graph | salir)\n"
        f"Inferencia: {get_provider()} / {get_model()}\n"
    )
    pinned: list[str] = []

    while True:
        try:
            user_input = input("Tú> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nHasta luego.")
            return 0
        if not user_input:
            continue
        low = user_input.lower()
        if low in {"salir", "exit", "quit"}:
            print("Hasta luego.")
            return 0
        if low in {"/skills", "skills"}:
            print(format_catalog())
            if pinned:
                print("Pineados:", ", ".join(pinned))
            continue
        if low == "/graph":
            print("Indica una skill: /graph python_web")
            continue
        if low.startswith("/graph "):
            name = user_input.split(maxsplit=1)[1].strip().lower()
            print(explain(resolve([name])))
            continue
        if low.startswith("/pin "):
            name = user_input.split(maxsplit=1)[1].strip().lower()
            if get_skill(name) is None:
                print(f"No existe skill `{name}`.")
            elif name not in pinned:
                pinned.append(name)
                print(f"Pineado: `{name}`")
            else:
                print(f"Ya estaba pineado: `{name}`")
            continue
        if low in {"/unpin", "/unpin all"}:
            pinned.clear()
            print("Skills pineados limpiados.")
            continue
        if low.startswith("/skill ") and len(user_input.split()) == 2:
            _print_skill(user_input.split(maxsplit=1)[1].strip().lower())
            continue

        request = EngineRequest(
            message=user_input,
            language=args.language,
            pinned_skills=pinned,
        )
        try:
            response = run(request, confirm_write=_confirm_write)
        except Exception as exc:  # noqa: BLE001
            print(f"Error: {exc}")
            continue
        print(f"\n[{response.summary()}]\n")
        print(f"Gla-2> {response.message}\n")
        if response.patches and (response.patches.diffs or response.patches.replaces):
            print(
                f"Parches: {len(response.patches.diffs)} diff(s), "
                f"{len(response.patches.replaces)} reemplazo(s).\n"
            )
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    request = EngineRequest(
        message=args.message,
        language=args.language,
        selection=args.selection,
        pinned_skills=args.pin,
    )
    try:
        response = run(request, confirm_write=_confirm_write)
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}")
        return 1
    print(response.summary())
    print()
    print(response.message)
    return 0


def cmd_json(_: argparse.Namespace) -> int:
    """Contrato de Neovim: un JSON por stdin, un JSON por stdout. No escribe el disco."""
    raw = scrub(sys.stdin.buffer.read().decode("utf-8", errors="surrogatepass"))
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as exc:
        print(json.dumps({"ok": False, "error": f"JSON inválido: {exc}"}, ensure_ascii=False))
        return 1
    if not isinstance(payload, dict):
        print(json.dumps({"ok": False, "error": "La solicitud debe ser un objeto."}, ensure_ascii=False))
        return 1
    payload = scrub_tree(payload)
    message = scrub(payload.get("message") or "").strip()
    if not message:
        print(json.dumps({"ok": False, "error": "Falta message."}, ensure_ascii=False))
        return 1

    extra = payload.get("extra_context")
    path = payload.get("path")
    if path:
        prefix = f"Archivo activo: {path}"
        extra = f"{prefix}\n\n{extra}" if extra else prefix

    request = EngineRequest(
        message=message,
        language=payload.get("language") or None,
        selection=payload.get("selection") or None,
        diagnostics=payload.get("diagnostics") or None,
        pinned_skills=payload.get("pinned_skills") or None,
        extra_context=extra,
        model=(str(payload.get("model") or "").strip() or None),
    )
    try:
        response = run(request, confirm_write=None)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": scrub(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(scrub_tree({"ok": True, **response.to_dict()}), ensure_ascii=False))
    return 0


def cmd_sandbox(args: argparse.Namespace) -> int:
    print("Sandbox: la misma petición en varias formas. Esto tarda.\n")
    try:
        results, experimento = run_sandbox(args.message)
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}")
        return 1
    print(format_report(args.message, results, experimento))
    return 0


def cmd_skill_list(_: argparse.Namespace) -> int:
    print(format_catalog())
    return 0


def _print_skill(name: str) -> int:
    skill = get_skill(name)
    if skill is None:
        print(f"No existe skill `{name}`.")
        print(format_catalog())
        return 1
    print(f"# {skill.name} ({skill.kind})")
    print(skill.description)
    print()
    print(skill.body)
    print(f"\nArchivo: {skill.path.relative_to(ROOT)}")
    return 0


def cmd_skill_show(args: argparse.Namespace) -> int:
    return _print_skill(args.name)


def cmd_skill_graph(args: argparse.Namespace) -> int:
    names = args.names or [skill.name for skill in load_skills() if skill.kind != "tool"]
    print(explain(resolve(names)))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.main",
        description="Gla-2: motor de programación (skills DAG + inferencia local).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_chat = sub.add_parser("chat", help="Chat del motor, sin IDE")
    p_chat.add_argument("--language", default=None, help="python | rust | c")
    p_chat.set_defaults(func=cmd_chat)

    p_run = sub.add_parser("run", help="Una solicitud (contrato futuro del IDE)")
    p_run.add_argument("message", help="Qué debe hacer el motor")
    p_run.add_argument("--language", default=None)
    p_run.add_argument("--selection", default=None, help="Fragmento de código")
    p_run.add_argument("--pin", action="append", default=None, help="Skill a forzar")
    p_run.set_defaults(func=cmd_run)

    p_json = sub.add_parser("json", help="Contrato Neovim: JSON stdin → JSON stdout")
    p_json.set_defaults(func=cmd_json)

    p_box = sub.add_parser("sandbox", help="Probar una petición de varias formas y guardar lo validado")
    p_box.add_argument("message", help="Qué debe cumplir el modelo")
    p_box.set_defaults(func=cmd_sandbox)

    p_skill = sub.add_parser("skill", help="Catálogo y grafo de skills")
    skill_sub = p_skill.add_subparsers(dest="skill_command", required=True)
    p_sl = skill_sub.add_parser("list", help="Listar skills")
    p_sl.set_defaults(func=cmd_skill_list)
    p_ss = skill_sub.add_parser("show", help="Ver un skill")
    p_ss.add_argument("name")
    p_ss.set_defaults(func=cmd_skill_show)
    p_sg = skill_sub.add_parser("graph", help="Resolver el DAG")
    p_sg.add_argument("names", nargs="*", help="Raíces; vacío = todas las de instrucción")
    p_sg.set_defaults(func=cmd_skill_graph)

    return parser


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                pass


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())

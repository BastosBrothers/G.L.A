"""Parches: git diff unificado o reemplazo por rango de líneas."""

from __future__ import annotations

import re
from dataclasses import dataclass


DIFF_FENCE_RE = re.compile(r"```(?:diff|patch)\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
REPLACE_FENCE_RE = re.compile(r"```replace\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
FILE_FENCE_RE = re.compile(
    r"```file(?:[ \t]+([^\n`]+))?[ \t]*\n(.*?)```",
    re.DOTALL | re.IGNORECASE,
)
PY_FENCE_RE = re.compile(
    r"```(?:python|py)(?:[ \t]+([^\n`]+))?[ \t]*\n(.*?)```",
    re.DOTALL | re.IGNORECASE,
)
_SEP_RE = re.compile(r"\n---[ \t]*\n")
_FILE_COMMENT_RE = re.compile(
    r"^\s*#\s*(?:file:?\s+)?([A-Za-z_][\w./-]*\.[A-Za-z0-9]+)(?:\s+---)?\s*$",
    re.IGNORECASE,
)
def _python_bodies(model_text: str) -> list[tuple[str, str]]:
    closed = list(PY_FENCE_RE.finditer(model_text))
    if closed:
        return [(match.group(1) or "", match.group(2)) for match in closed]
    open_fence = re.search(
        r"```(?:python|py)(?:[ \t]+([^\n`]+))?[ \t]*\n(.*)\Z",
        model_text,
        re.DOTALL | re.IGNORECASE,
    )
    if not open_fence:
        return []
    return [(open_fence.group(1) or "", open_fence.group(2))]


def _split_file_comments(body: str, fallback: str) -> list[NewFile]:
    chunks: list[tuple[str, list[str]]] = []
    current_path = _path_from_token(fallback)
    current: list[str] = []
    for line in body.splitlines():
        named = _FILE_COMMENT_RE.match(line)
        if named:
            path = _path_from_token(named.group(1))
            if _usable_path(path):
                if current and _usable_path(current_path):
                    chunks.append((current_path, current))
                current_path = path
                current = []
                continue
        current.append(line)
    if current and _usable_path(current_path):
        chunks.append((current_path, current))
    files: list[NewFile] = []
    for path, rows in chunks:
        content = "\n".join(rows).strip()
        if content:
            files.append(NewFile(path=path, content=content + "\n"))
    return files


@dataclass
class LineReplace:
    path: str
    start_line: int
    end_line: int
    content: str


@dataclass
class NewFile:
    path: str
    content: str


@dataclass
class PatchSet:
    diffs: list[str]
    replaces: list[LineReplace]
    files: list[NewFile]
    errors: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors


def _looks_like_unified_diff(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    return stripped.startswith(("diff --git ", "--- ", "+++ ", "@@ ")) or "\n@@ " in stripped


def parse_replace_block(raw: str) -> LineReplace | str:
    """
    Formato:
    path: src/foo.py
    start_line: 10
    end_line: 18
    ---
    contenido nuevo
    """
    text = raw.strip()
    if "\n---\n" not in text and not text.startswith("---\n"):
        header, _, content = text.partition("\n---\n")
        if not _:
            return "Bloque replace sin separador `---`."
    else:
        header, _, content = text.partition("\n---\n")

    fields: dict[str, str] = {}
    for line in header.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip().lower()] = value.strip()

    path = fields.get("path", "")
    if not path:
        return "Bloque replace sin `path`."
    try:
        start_line = int(fields.get("start_line", "0"))
        end_line = int(fields.get("end_line", "0"))
    except ValueError:
        return "start_line y end_line deben ser enteros."
    if start_line < 1 or end_line < start_line:
        return "Rango de líneas inválido."
    return LineReplace(
        path=path,
        start_line=start_line,
        end_line=end_line,
        content=content.rstrip("\n") + "\n",
    )


def _path_from_token(token: str) -> str:
    path = token.strip().strip("\"'")
    comment = _FILE_COMMENT_RE.match(path)
    if comment:
        path = comment.group(1).strip()
    if path.lower().startswith("path:"):
        path = path.split(":", 1)[1].strip().strip("\"'")
    path = path.replace("\\", "/")
    path = re.split(r"\s+---", path, maxsplit=1)[0].strip()
    if path.endswith("---"):
        path = path[:-3].strip()
    found = re.findall(r"[A-Za-z_][A-Za-z0-9_.-]*\.[A-Za-z0-9]+", path)
    py = [name for name in found if name.endswith(".py")]
    if py:
        return py[-1]
    if found and " " not in path and "./" not in path:
        return found[-1]
    return path


def _usable_path(path: str) -> bool:
    if not path or path.startswith("/") or ":" in path:
        return False
    parts = [part for part in path.replace("\\", "/").split("/") if part not in ("", ".")]
    if not parts or ".." in parts:
        return False
    for part in parts:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]{0,80}", part):
            return False
    return "." in parts[-1]


def parse_file_block(raw: str, fence_path: str = "") -> NewFile | str:
    text = raw.strip()
    path = _path_from_token(fence_path)
    for line in text.splitlines()[:4]:
        candidate = _path_from_token(line)
        if _usable_path(candidate):
            path = candidate
            break
    match = _SEP_RE.search(text)
    if match:
        header, content = text[: match.start()], text[match.end() :]
        for line in header.splitlines():
            candidate = _path_from_token(line)
            if _usable_path(candidate):
                path = candidate
                break
    else:
        content = text
        first, _, rest = text.partition("\n")
        candidate = _path_from_token(first)
        if _usable_path(candidate):
            path = candidate
            content = rest or text
    content = re.sub(r"\n---[ \t]*$", "", content.rstrip())
    if not _usable_path(path):
        return "Bloque file con path inválido."
    if not content.strip():
        return "Bloque file sin código."
    return NewFile(path=path, content=content.rstrip("\n") + "\n")


def extract_patches(model_text: str) -> PatchSet:
    diffs: list[str] = []
    replaces: list[LineReplace] = []
    files: list[NewFile] = []
    errors: list[str] = []

    for match in DIFF_FENCE_RE.finditer(model_text):
        block = match.group(1).strip()
        if not _looks_like_unified_diff(block):
            errors.append("Bloque ```diff que no parece un diff unificado.")
            continue
        diffs.append(block + ("\n" if not block.endswith("\n") else ""))

    for match in REPLACE_FENCE_RE.finditer(model_text):
        parsed = parse_replace_block(match.group(1))
        if isinstance(parsed, str):
            errors.append(parsed)
        else:
            replaces.append(parsed)

    for match in FILE_FENCE_RE.finditer(model_text):
        parsed = parse_file_block(match.group(2), match.group(1) or "")
        if isinstance(parsed, str):
            errors.append(parsed)
        else:
            files.append(parsed)

    if not files:
        py_blocks = _python_bodies(model_text)
        for index, (fence_path, body) in enumerate(py_blocks):
            if not fence_path and len(py_blocks) == 1 and "# file" not in body.lower():
                fence_path = "main.py"
            files.extend(_split_file_comments(body, fence_path))

    return PatchSet(diffs=diffs, replaces=replaces, files=files, errors=errors)


def apply_line_replace(source: str, patch: LineReplace) -> str:
    """Aplica un reemplazo por rango (1-indexado, inclusive) sobre un texto."""
    lines = source.splitlines(keepends=True)
    start = patch.start_line - 1
    end = patch.end_line
    if start < 0 or end > len(lines):
        raise ValueError(
            f"Rango {patch.start_line}-{patch.end_line} fuera de archivo ({len(lines)} líneas)."
        )
    new_lines = patch.content.splitlines(keepends=True)
    if new_lines and not new_lines[-1].endswith("\n"):
        new_lines[-1] += "\n"
    return "".join(lines[:start] + new_lines + lines[end:])

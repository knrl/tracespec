"""Symbols: the unit a code link points at. Standard library only.

A code link is a symbol with a hash of its own text, not a file, so an edit elsewhere in a shared file does not flag
unrelated rules. Three resolvers, best first:
  ast       Python, exact (functions, classes, methods, and '<module>' for the top-level statements)
  ctags     universal-ctags, when installed, for the other languages
  regions   anything else: indentation blocks, named by their first line. Approximate, but far tighter than a file.
A symbol id is 'path::qualified.name'. Its hash is taken over its text with line endings and trailing blanks normalised.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

MODULE = "<module>"
_CTAGS: str | None | bool = False        # False: not looked for yet; None: not available


def normalise(text: str) -> str:
    lines = [l.rstrip() for l in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def text_hash(text: str) -> str:
    return hashlib.sha256(normalise(text).encode("utf-8")).hexdigest()[:16]


def _unique(path: str, name: str, seen: dict[str, int]) -> str:
    base = f"{path}::{name}"
    seen[base] = seen.get(base, 0) + 1
    return base if seen[base] == 1 else f"{base}#{seen[base]}"


def _make(path: str, name: str, kind: str, start: int, end: int, lines: list[str], seen: dict[str, int]) -> dict:
    return {"id": _unique(path, name, seen), "name": name, "kind": kind, "start": start, "end": end,
            "hash": text_hash("\n".join(lines[start - 1:end]))}


# ---- python ------------------------------------------------------------------------------------------------

def python_symbols(path: str, text: str) -> list[dict] | None:
    """Exact symbols of a Python file, or None when it does not parse."""
    try:
        tree = ast.parse(text.lstrip(chr(0xFEFF)))          # a byte order mark is not a syntax error
    except (SyntaxError, ValueError):
        return None
    lines = text.replace("\r\n", "\n").split("\n")
    seen: dict[str, int] = {}
    spans: list[tuple[int, int]] = []
    out: list[dict] = []

    def visit(body, stack: list[str]) -> None:
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                start = min([node.lineno] + [d.lineno for d in node.decorator_list])
                end = node.end_lineno or node.lineno
                qual = ".".join(stack + [node.name])
                kind = "class" if isinstance(node, ast.ClassDef) else ("method" if stack else "function")
                out.append(_make(path, qual, kind, start, end, lines, seen))
                if not stack:
                    spans.append((start, end))
                if isinstance(node, ast.ClassDef):
                    visit(node.body, stack + [node.name])
            elif isinstance(node, (ast.If, ast.Try, ast.With, ast.AsyncWith, ast.For, ast.While)):
                for attr in ("body", "orelse", "finalbody"):
                    visit(getattr(node, attr, []) or [], stack)
                for h in getattr(node, "handlers", []) or []:
                    visit(h.body, stack)

    visit(tree.body, [])
    covered = set()
    for s, e in spans:
        covered.update(range(s, e + 1))
    rest = [lines[i - 1] for i in range(1, len(lines) + 1) if i not in covered and lines[i - 1].strip()]
    if rest:
        out.append({"id": f"{path}::{MODULE}", "name": MODULE, "kind": "module", "start": 1, "end": len(lines),
                    "hash": text_hash("\n".join(rest))})
    return out


# ---- ctags -------------------------------------------------------------------------------------------------

def ctags_available() -> str | None:
    global _CTAGS
    if _CTAGS is False:
        exe = shutil.which("ctags")
        _CTAGS = None
        if exe:
            try:
                p = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=10)
                if "Universal Ctags" in p.stdout:
                    _CTAGS = exe
            except (OSError, subprocess.TimeoutExpired):
                pass
    return _CTAGS or None


def parse_ctags_json(output: str, path: str, text: str) -> list[dict] | None:
    """Symbols from universal-ctags JSON lines. None if any tag lacks an end line (then the file falls back to regions)."""
    lines = text.replace("\r\n", "\n").split("\n")
    seen: dict[str, int] = {}
    out = []
    for raw in output.splitlines():
        try:
            t = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if t.get("_type") != "tag" or t.get("kind") in ("variable", "local", "parameter", "member", "field", "macro"):
            continue
        if "line" not in t or "end" not in t:
            return None
        scope = re.sub(r"^[a-z]+:", "", t.get("scope", "") or "")
        name = f"{scope}.{t['name']}" if scope else t["name"]
        out.append(_make(path, name, t.get("kind", "symbol"), int(t["line"]), int(t["end"]), lines, seen))
    return out or None


def ctags_symbols(project: Path, path: str, text: str) -> list[dict] | None:
    exe = ctags_available()
    if not exe:
        return None
    try:
        p = subprocess.run([exe, "--output-format=json", "--fields=+neKS", "-f", "-", str(project / path)],
                           capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return parse_ctags_json(p.stdout, path, text) if p.returncode == 0 else None


# ---- regions (the fallback) --------------------------------------------------------------------------------

_CONTINUE = ("}", ")", "]", "end", "else", "elif", "except", "finally", "case ", "//", "#", "/*", "*", "<!--", "-->", "@")


def region_symbols(path: str, text: str) -> list[dict]:
    """Indentation blocks: a block starts at a line in column 0 and runs to the line before the next one. Lines in column 0
    that close or continue a block ('}', 'else', comments, decorators) stay in the block they belong to."""
    lines = text.replace("\r\n", "\n").split("\n")
    seen: dict[str, int] = {}
    blocks: list[list] = []                       # [start, end, name]
    for i, line in enumerate(lines, 1):
        if not line.strip():
            continue
        top = not line[0].isspace() and not line.startswith(_CONTINUE)
        if top or not blocks:
            name = re.sub(r"\s+", " ", line.strip())[:60] if top else "(preamble)"
            blocks.append([i, i, "@" + name])
        else:
            blocks[-1][1] = i
    return [_make(path, name, "region", s, e, lines, seen) for s, e, name in blocks]


# ---- resolve -----------------------------------------------------------------------------------------------

def resolve(project: Path, path: str, text: str) -> dict:
    """{'resolver': ..., 'symbols': [...]} for one file."""
    if path.endswith(".py"):
        syms = python_symbols(path, text)
        if syms is not None:
            return {"resolver": "ast", "symbols": syms}
    else:
        syms = ctags_symbols(project, path, text)
        if syms:
            return {"resolver": "ctags", "symbols": syms}
    syms = region_symbols(path, text)
    if not syms:
        n = len(text.replace("\r\n", "\n").split("\n"))
        syms = [{"id": f"{path}::<file>", "name": "<file>", "kind": "file", "start": 1, "end": n, "hash": text_hash(text)}]
    return {"resolver": "regions", "symbols": syms}

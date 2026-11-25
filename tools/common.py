"""Shared helpers of the tracespec tools (check.py, guard.py, results.py). Standard library only.

The project is the nearest folder above a path that holds .tracespec.json. Its `layout` says which paths are
tests, which are code, which are protected, and how the tests are run.
"""
from __future__ import annotations

import functools
import hashlib
import json
import os
import re
from pathlib import Path

STATE = ".tracespec.json"
SKIP_DIRS = {".git", "node_modules", ".venv", "__pycache__", ".idea", ".vscode", ".pytest_cache", ".mypy_cache",
             ".ruff_cache", ".gradle"}
ROOT_SKIP_DIRS = {"venv", "dist", "target", "bin", "obj"}      # build output at the project root; real code deeper down

DEFAULT_LAYOUT = {
    "tests": ["tests/**"],            # hidden from the coder; the only place the test writer may write
    "code": ["src/**"],               # hidden from the test writer
    "protected": [STATE, ".tracespec-check.json", ".tracespec-junit.xml", ".tracespec/**", "docs/features/**"],  # neither agent writes here
    "testCmd": [],                    # argv that runs the whole test suite and writes JUnit XML
    "testEnv": {},                    # extra environment variables for testCmd
    "junit": ".tracespec-junit.xml",  # JUnit XML file or glob, relative to the project
    "refPattern": "",                 # optional regex an external reference must match (for example [A-Z]+-\\d+)
    "refRequired": False,             # true: every goal needs an external reference (a ticket, an issue)
    "overviewDir": "docs/features",   # the one developer-facing document per change (docs/features/<change>.md)
    "knownFailing": [],               # tests that failed before the feature (baseline); never blamed on the feature
}

ID_PREFIXES = "NFR|FR|AC|NG|ASM|OPEN|G|D|R|Q|T"
ID_RE = re.compile(rf"(?<![A-Za-z0-9])({ID_PREFIXES})-(\d+)(?![A-Za-z0-9])")
# in test names and files an ID may be written AC-3, AC_3 or AC3
TEST_ID_RE = re.compile(r"(?<![A-Za-z])(AC|FR|NFR)[-_]?(\d+)(?!\d)")


def test_ids(text: str) -> list[str]:
    """Spec IDs named in a test name or text, normalised to AC-3 form, in order, without repeats."""
    seen: list[str] = []
    for m in TEST_ID_RE.finditer(text or ""):
        i = f"{m.group(1)}-{int(m.group(2))}"
        if i not in seen:
            seen.append(i)
    return seen


# ---- globs -------------------------------------------------------------------------------------------------

def _is_dir_name(pat: str) -> bool:
    last = pat.rstrip("/").split("/")[-1]
    return not any(c in pat for c in "*?[") and "." not in last


def norm_glob(pat: str) -> str:
    pat = pat.replace("\\", "/").strip()
    while pat.startswith("./"):
        pat = pat[2:]
    pat = pat.strip("/")
    return pat + "/**" if _is_dir_name(pat) else pat


@functools.lru_cache(maxsize=1024)
def glob_to_re(pat: str) -> re.Pattern:
    pat = norm_glob(pat)
    out, i = "", 0
    while i < len(pat):
        if pat.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
        elif pat.startswith("/**", i) and i + 3 == len(pat):
            out += "(?:/.*)?"
            i += 3
        elif pat.startswith("**", i):
            out += ".*"
            i += 2
        elif pat[i] == "*":
            out += "[^/]*"
            i += 1
        elif pat[i] == "?":
            out += "[^/]"
            i += 1
        else:
            out += re.escape(pat[i])
            i += 1
    return re.compile("^" + out + "$")


def matches(rel: str | None, pats: list[str]) -> bool:
    if rel is None:
        return False
    rel = rel.replace("\\", "/")
    return any(glob_to_re(p).match(rel) for p in pats)


def literal_prefix(pat: str) -> str:
    """The folder a glob starts in ('src/**' -> 'src', '**/test_*.py' -> '')."""
    parts = norm_glob(pat).split("/")
    keep = []
    for part in parts:
        if any(c in part for c in "*?["):
            break
        keep.append(part)
    if keep and keep == parts:  # a plain file path: its folder
        keep = keep[:-1]
    return "/".join(keep)


def inside(rel: str | None, folder: str) -> bool:
    """rel is folder itself or below it ('.' is the project root)."""
    if rel is None:
        return False
    if folder in ("", "."):
        return True
    return rel == folder or rel.startswith(folder + "/")


# ---- project, state, layout --------------------------------------------------------------------------------

def find_project(path: str | Path) -> Path | None:
    p = Path(path).resolve()
    for d in [p, *p.parents]:
        if (d / STATE).is_file():
            return d
    return None


class StateError(Exception):
    """The state file exists but cannot be used. Never treated as an empty project: a write would erase it."""


def load_state(project: Path) -> dict:
    try:
        text = (project / STATE).read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except (OSError, UnicodeDecodeError) as e:
        raise StateError(f"{STATE} cannot be read: {e}")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise StateError(f"{STATE} is not valid JSON ({e}). Restore it from git; nothing was changed")
    if not isinstance(data, dict):
        raise StateError(f"{STATE} must contain a JSON object. Restore it from git; nothing was changed")
    return data


def write_atomic(path: Path, text: str) -> None:
    """Write a file so that a crash leaves either the old or the new content, never a half-written one."""
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    os.replace(tmp, path)


def layout_of(project: Path | None) -> tuple[dict, list[str]]:
    """The project's layout with defaults filled in, and a list of problems (an invalid entry falls back)."""
    layout = json.loads(json.dumps(DEFAULT_LAYOUT))
    problems: list[str] = []
    if project is None:
        return layout, problems
    given = load_state(project).get("layout")
    if given is None:
        return layout, problems
    if not isinstance(given, dict):
        return layout, ["layout is not an object"]
    for key, default in DEFAULT_LAYOUT.items():
        if key not in given:
            continue
        v = given[key]
        ok = (isinstance(v, str) if key in ("junit", "overviewDir", "refPattern") else
              isinstance(v, bool) if key == "refRequired" else
              isinstance(v, dict) if key == "testEnv" else
              isinstance(v, list) and all(isinstance(x, str) for x in v))
        if ok:
            layout[key] = v
        else:
            problems.append(f"layout.{key} has the wrong type; default used")
    return layout, problems


def classify(rel: str | None, layout: dict) -> str:
    """'protected', 'test', 'code' or 'other'. A path that is both test and code counts as a test."""
    if rel is None:
        return "other"
    if matches(rel, layout["protected"]):
        return "protected"
    if matches(rel, layout["tests"]):
        return "test"
    if matches(rel, layout["code"]):
        return "code"
    return "other"


def walk_files(project: Path):
    """Relative posix paths of the project's files, without build and tool folders."""
    for root, dirs, files in os.walk(project):
        top = Path(root) == project
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not (top and d in ROOT_SKIP_DIRS)]
        for f in files:
            yield (Path(root) / f).relative_to(project).as_posix()


def active_change(state: dict, name: str | None = None) -> tuple[str | None, dict]:
    """(name, entry) of the named change, or of the active one."""
    name = name or state.get("activeChange")
    entries = state.get("changes") or {}
    return name, (entries.get(name) or {})


INTERNAL = ".tracespec"     # agent-oriented files: living specs, changes, locks, ledgers, matrices


def internal_dir(project: Path) -> Path:
    return project / INTERNAL


def specs_dir(project: Path) -> Path:
    """The living specs: one folder per capability. Internal: for the agents, not for review."""
    return project / INTERNAL / "specs"


def changes_dir(project: Path) -> Path:
    return project / INTERNAL / "changes"


def overview_path(project: Path, layout: dict, change: str) -> Path:
    """The developer-facing overview of a change."""
    return project / layout["overviewDir"] / f"{change}.md"


def change_dir(project: Path, name: str) -> Path:
    return changes_dir(project) / name


def archive_dir(project: Path) -> Path:
    return changes_dir(project) / "archive"


def file_hash(path: Path) -> str | None:
    """Hash of a file's content with line endings normalised; None if it cannot be read."""
    try:
        data = path.read_bytes().replace(b"\r\n", b"\n")
    except OSError:
        return None
    return hashlib.sha256(data).hexdigest()[:16]


def fingerprint_text(text: str) -> str:
    """Hash of a document without its Version and Status lines (they change at approval)."""
    keep = [l.rstrip() for l in text.replace("\r\n", "\n").split("\n")
            if not re.match(r"^\s*(\*\*)?(Version|Status)(\*\*)?\s*:", l)]
    return hashlib.sha256("\n".join(keep).strip().encode("utf-8")).hexdigest()[:16]


def fingerprint_code(project: Path, layout: dict) -> str:
    h = hashlib.sha256()
    for rel in sorted(walk_files(project)):
        if classify(rel, layout) != "code":
            continue
        h.update(rel.encode("utf-8"))
        try:
            h.update((project / rel).read_bytes())
        except OSError:
            pass
    return h.hexdigest()[:16]

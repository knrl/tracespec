"""The developer-facing overview of a change: one short Markdown file, docs/features/<change>.md. Standard library only.

Everything else tracespec writes is for the agents and lives in .tracespec/. This one file is for people, so it is small and
only about what a reviewer needs: why the feature exists, how it is designed, and which components make it up. It is written by
the coordinator from the code that was built, and checked here only for being there, complete and honest (component paths must
exist). Nothing in it is generated: the rules, criteria, tests and code locations are one `check.py --trace` away.
"""
from __future__ import annotations

import re
from pathlib import Path

from common import overview_path

MAX_LINES = 60      # a warning above this: the overview should be read in a minute
MIN_BODY = 30       # characters of narrative a required section must have
# (the words a heading may contain, the name shown in findings). "architecture" is still accepted for "design".
REQUIRED = [(("purpose",), "Purpose"), (("design", "architecture"), "Design"), (("key components",), "Key components")]
FALLBACK = ("# {title}\n\n## Purpose\n\n<<purpose>>\n\n## Design\n\n<<design>>\n\n## Key components\n\n"
            "| Component | Path | Responsibility |\n|---|---|---|\n| <<name>> | `<<path>>` | <<what>> |\n")


def skeleton(title: str) -> str:
    tpl = Path(__file__).resolve().parent.parent / "templates" / "overview.md"
    try:
        text = tpl.read_text(encoding="utf-8")
    except OSError:
        return FALLBACK.format(title=title)
    return text.replace("# <<Feature title>>", f"# {title}", 1)


def create(project: Path, layout: dict, name: str, title: str) -> tuple[Path, bool]:
    """Write the skeleton if the overview does not exist yet. Returns (path, created)."""
    path = overview_path(project, layout, name)
    if path.is_file():
        return path, False
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(skeleton(title))
    return path, True


# ---- the checks --------------------------------------------------------------------------------------------

def sections(text: str) -> dict[str, str]:
    """Lower-case level-2 heading -> its body (up to the next heading of level 1 or 2)."""
    out: dict[str, list[str]] = {}
    current = None
    for line in text.replace("\r\n", "\n").split("\n"):
        m = re.match(r"^(#{1,2})\s+(.*\S)\s*$", line)
        if m:
            current = m.group(2).lower() if len(m.group(1)) == 2 else None
            if current is not None:
                out[current] = []
            continue
        if current is not None:
            out[current].append(line)
    return {k: "\n".join(v) for k, v in out.items()}


def component_paths(body: str) -> list[str]:
    """The Path column of the Key components table."""
    paths = []
    for line in body.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2 or set(cells[1]) <= set("-: ") or cells[1].lower() == "path":
            continue
        p = cells[1].strip("` ")
        if p and "<<" not in p and not p.startswith(("http://", "https://")) and (" " not in p):
            paths.append(p)
    return paths


def check_overview(project: Path, layout: dict, name: str, add) -> None:
    """Findings for docs/features/<change>.md: add(code, severity, message, owner='agent')."""
    path = overview_path(project, layout, name)
    rel = path.relative_to(project).as_posix() if path.is_absolute() else str(path)
    if not path.is_file():
        add("OVERVIEW001", "error", f"{rel} does not exist: run `check.py <project> --overview`, then write it")
        return
    text = path.read_text(encoding="utf-8", errors="replace")
    secs = sections(text)
    for keys, title in REQUIRED:
        body = next((b for h, b in secs.items() if any(k in h for k in keys)), None)
        if body is None:
            add("OVERVIEW004", "error", f"{rel} has no section '{title}'")
        elif len(re.sub(r"\s+", "", re.sub(r"<!--.*?-->", "", body, flags=re.S))) < MIN_BODY:
            add("OVERVIEW007", "error", f"the '{title}' section of {rel} is empty or too short")
    prose = re.sub(r"```.*?```|`[^`\n]*`", "", text, flags=re.S)       # code may say TODO or use <<
    if re.search(r"\bTBD\b|\bTODO\b|<<[^<>\n]+>>", prose):
        add("OVERVIEW005", "error", f"{rel} still has TBD, TODO or <<placeholder>> text")
    kc = next((b for h, b in secs.items() if "key components" in h), "")
    missing = [p for p in component_paths(kc) if not (project / p).exists()]
    if missing:
        add("OVERVIEW003", "error", f"{rel} names components that do not exist: {', '.join(missing)}")
    lines = len([l for l in text.splitlines() if l.strip()])
    if lines > MAX_LINES:
        add("OVERVIEW002", "warning", f"{rel} has {lines} lines: keep it short (about {MAX_LINES} at most), design first")

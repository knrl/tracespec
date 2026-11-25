"""The developer-facing overview of a change: one concise Markdown file, docs/features/<change>.md. Standard library only.

Everything else tracespec writes is for the agents and lives in .tracespec/. This one file is for people. It has two
parts that never mix:
  - the narrative (purpose, how it fits, architecture, key components, data flow), written by the coordinator from the
    code that was built, and checked here only for being there, complete and honest (component paths must exist);
  - a facts block between two markers, generated here from the specs, tasks, tests and matrix, and refreshed at will.
"""
from __future__ import annotations

import re
from pathlib import Path

import links
import living
import tracing
from common import overview_path

BEGIN = "<!-- tracespec:facts:begin -->"
END = "<!-- tracespec:facts:end -->"
MAX_LINES = 120
MIN_BODY = 30       # characters of narrative a required section must have
REQUIRED = [("purpose", "Purpose"), ("fits into", "How it fits into the codebase"), ("architecture", "Architecture"),
            ("key components", "Key components"), ("data flow", "Data flow")]
FALLBACK = ("# {title}\n\n## Purpose\n\n<<purpose>>\n\n## How it fits into the codebase\n\n<<fit>>\n\n## Architecture\n\n"
            "<<architecture>>\n\n## Key components\n\n| Component | Path | Responsibility |\n|---|---|---|\n| <<name>> | `<<path>>` | "
            "<<what>> |\n\n## Data flow\n\n<<flow>>\n\n## Facts (generated)\n\n" + BEGIN + "\n" + END + "\n")


def skeleton(title: str) -> str:
    tpl = Path(__file__).resolve().parent.parent / "templates" / "overview.md"
    try:
        text = tpl.read_text(encoding="utf-8")
    except OSError:
        return FALLBACK.format(title=title)
    return text.replace("# <<Feature title>>", f"# {title}", 1)


# ---- the generated facts -----------------------------------------------------------------------------------

def build_facts(project: Path, layout: dict, name: str, ch: dict, ops: dict, caps_before: dict, caps_after: dict,
                model: dict | None, status: str, internal: str) -> str:
    tasks = tracing.parse_tasks(ch["tasks_text"])
    touched = {i for i, o in ops.items() if o in ("ADDED", "MODIFIED")}
    out = [f"**Status:** {status} · **Change:** `{name}` · **Capabilities:** {', '.join(sorted(caps_after)) or 'none'}",
           f"**Agent records (no review needed):** `{internal}`", "", "### Behavior at a glance", ""]
    for cap in sorted(caps_after):
        state = caps_after[cap]
        before = caps_before.get(cap) or living.empty_cap()
        out += [f"**{cap}**: {state['purpose']}", "", "| Rule | Change | What it says |", "|---|---|---|"]
        rows = 0
        for q in sorted(state["rules"], key=living.id_key):
            if q in touched:
                out.append(f"| {q} | {ops[q].lower()} | {state['rules'][q][1].replace('|', '/')} |")
                rows += 1
        for q in sorted((i for i, o in ops.items() if o == "REMOVED" and i.startswith(("FR-", "NFR-")) and i in before["rules"]),
                        key=living.id_key):
            out.append(f"| {q} | removed | {before['rules'][q][1].replace('|', '/')} |")
            rows += 1
        if not rows:
            out.append("| - | - | no rule changed |")
        unchanged = len([q for q in state["rules"] if q not in touched])
        out += ["", f"{unchanged} other rule(s) of this capability are unchanged.", ""]

    code = sorted({f for d in tasks.values() for f in d["files"]})
    if not code:
        code = sorted({p for p in re.findall(r"\|\s*`?([^|`\s]+)`?\s*\|\s*(?:new|changed)", ch["text"])})
    acs = {i for i in touched if i.startswith("AC-")}
    tests = sorted({t for files in links.test_files_for(project, layout, acs).values() for t in files})
    out += ["### Where to look", "",
            f"- Code: {', '.join(f'`{p}`' for p in code) or 'not recorded'}",
            f"- Tests: {', '.join(f'`{p}`' for p in tests) or 'none found'}",
            f"- Living specs: {', '.join(f'`.tracespec/specs/{c}/spec.md`' for c in sorted(caps_after))}", "",
            "### How it is verified", ""]
    if model and model.get("ran"):
        rr, ar = model["req_result"], model["ac_result"]
        out.append(f"- {sum(1 for v in rr.values() if v == 'PASS')} of {len(rr)} rules and "
                   f"{sum(1 for v in ar.values() if v == 'PASS')} of {len(ar)} criteria pass in the last run "
                   f"({len(model['cases'])} tests).")
    else:
        out.append("- Not run yet.")
    out.append("- Each criterion has a test whose name carries its number (`check.py` decides this, not the author).")
    return "\n".join(out)


def refresh(project: Path, layout: dict, name: str, facts: str, title: str, create: bool = False) -> Path | None:
    """Write the facts block into the overview (creating the skeleton first when asked). Returns its path."""
    path = overview_path(project, layout, name)
    if not path.is_file():
        if not create:
            return None
        path.parent.mkdir(parents=True, exist_ok=True)
        text = skeleton(title)
    else:
        text = path.read_text(encoding="utf-8", errors="replace")
    block =f"{BEGIN}\n{facts}\n{END}"
    if BEGIN in text and END in text:
        text = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END), lambda m: block, text, count=1, flags=re.S)
    else:
        text = text.rstrip() + f"\n\n## Facts (generated)\n\n{block}\n"
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    return path


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
        add("OVERVIEW001", "error", f"{rel} does not exist: run `check.py <project> --overview`, then write its narrative")
        return
    text = path.read_text(encoding="utf-8", errors="replace")
    secs = sections(text)
    for key, title in REQUIRED:
        body = next((b for h, b in secs.items() if key in h), None)
        if body is None:
            add("OVERVIEW004", "error", f"{rel} has no section '{title}'")
        elif len(re.sub(r"\s+", "", re.sub(r"<!--.*?-->", "", body, flags=re.S))) < MIN_BODY:
            add("OVERVIEW007", "error", f"the '{title}' section of {rel} is empty or too short")
    prose = re.sub(r"```.*?```|`[^`\n]*`", "", text, flags=re.S)       # code may say TODO or use <<
    if re.search(r"\bTBD\b|\bTODO\b|<<[^<>\n]+>>", prose):
        add("OVERVIEW005", "error", f"{rel} still has TBD, TODO or <<placeholder>> text")
    if BEGIN not in text or END not in text:
        add("OVERVIEW006", "error", f"{rel} has no facts block: run `check.py <project> --overview`")
    kc = next((b for h, b in secs.items() if "key components" in h), "")
    missing = [p for p in component_paths(kc) if not (project / p).exists()]
    if missing:
        add("OVERVIEW003", "error", f"{rel} names components that do not exist: {', '.join(missing)}")
    lines = len(text.splitlines())
    if lines > MAX_LINES:
        add("OVERVIEW002", "warning", f"{rel} has {lines} lines: it should be concise (about {MAX_LINES} at most)")

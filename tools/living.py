"""Living specs and deltas for tracespec. Standard library only.

A living spec is .tracespec/specs/<capability>/spec.md: the current behaviour of one capability, as tables of rules (FR, NFR),
acceptance criteria (AC) and non-goals (NG), plus the rules that were withdrawn. Only `check.py --archive` writes it.

A change describes what differs in a delta: rows under ADDED, MODIFIED or REMOVED headings, per capability. The merge
is deterministic: nothing here is judged by a model.
"""
from __future__ import annotations

import copy
import hashlib
import re
from pathlib import Path

from common import ID_RE, specs_dir

OPS = ("ADDED", "MODIFIED", "REMOVED")
MIN_COLS = {"rules": 3, "criteria": 4, "nongoals": 3}      # ID | Rule | Source;  ID | Covers | Given/When/Then | Source
TABLES = ("rules", "criteria", "nongoals")
SEP = re.compile(r"\s*\|[\s:|-]+\|\s*$")
SOURCE = re.compile(r"\b(?:Q|ASM|OPEN|G)-\d+\b")
RULE_IDS = re.compile(r"(?<![A-Za-z0-9])((?:NFR|FR)-\d+)(?![A-Za-z0-9])")


def table_of(i: str) -> str | None:
    if i.startswith(("FR-", "NFR-")):
        return "rules"
    if i.startswith("AC-"):
        return "criteria"
    if i.startswith("NG-"):
        return "nongoals"
    return None


def cells_of(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def row_hash(cells: list[str]) -> str:
    text = "|".join(" ".join(c.split()) for c in cells)
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def id_key(i: str) -> tuple[str, int]:
    p, n = i.rsplit("-", 1)
    return p, int(n)


# ---- deltas ------------------------------------------------------------------------------------------------

def parse_deltas(text: str, default_cap: str | None = None) -> tuple[list[dict], dict[str, str]]:
    """The delta rows in a text, and the Purpose lines by capability.

    A heading 'Capability: <name>' sets the capability (a file under specs/<name>/ sets it by default). A heading whose
    first word is ADDED, MODIFIED or REMOVED sets the operation; a heading of level 1 or 2 that is neither ends it.
    Rows are table rows whose first cell is an FR, NFR, AC or NG ID."""
    rows: list[dict] = []
    purposes: dict[str, str] = {}
    cap, op = default_cap, None
    for line in text.replace("\r\n", "\n").split("\n"):
        s = line.strip()
        if s.startswith("#"):
            level = len(s) - len(s.lstrip("#"))
            title = s.lstrip("#").strip()
            m = re.match(r"(?i)capability\s*:\s*([a-z0-9][a-z0-9_.-]*)", title)
            if m:
                cap, op = m.group(1).lower(), None
                continue
            first = title.split()[0].upper().strip(":") if title else ""
            if first in OPS:
                op = first
                continue
            if level <= 2:
                op = None
            continue
        if cap and op is None:
            m = re.match(r"(?i)purpose\s*:\s*(.+)", s)
            if m:
                purposes[cap] = m.group(1).strip()
                continue
        if op and s.startswith("|") and not SEP.match(line):
            cells = cells_of(line)
            first = cells[0].strip("*` ")
            if ID_RE.fullmatch(first) and table_of(first):
                rows.append({"cap": cap, "op": op, "id": first, "cells": [first] + cells[1:]})
    return rows, purposes


def behavior_hashes(rows: list[dict]) -> dict[str, str]:
    """'OP:ID' -> hash of the delta row. A change here is a change of a rule or criterion."""
    return {f"{r['op']}:{r['id']}": row_hash(r["cells"]) for r in rows}


# ---- living specs ------------------------------------------------------------------------------------------

def empty_cap() -> dict:
    return {"purpose": "", "rules": {}, "criteria": {}, "nongoals": {}, "withdrawn": {}}


def parse_living(text: str) -> dict:
    cap = empty_cap()
    section = None
    for line in text.replace("\r\n", "\n").split("\n"):
        s = line.strip()
        if s.startswith("#"):
            t = s.lstrip("#").strip().lower()
            section = ("rules" if "behavior rules" in t else "criteria" if "acceptance criteria" in t
                       else "nongoals" if "non-goals" in t else "withdrawn" if "withdrawn" in t else None)
            continue
        m = re.match(r"(?i)purpose\s*:\s*(.+)", s)
        if m and section is None:
            cap["purpose"] = m.group(1).strip()
            continue
        if section and s.startswith("|") and not SEP.match(line):
            cells = cells_of(line)
            first = cells[0].strip("*` ")
            if ID_RE.fullmatch(first):
                cap[section][first] = [first] + cells[1:]
    return cap


def _rows_md(cap: dict, table: str) -> list[str]:
    return ["| " + " | ".join(c.replace("|", "/") for c in cap[table][i]) + " |"
            for i in sorted(cap[table], key=id_key)]


def render_living(name: str, cap: dict) -> str:
    out = [f"# Capability: {name}", "", f"Purpose: {cap['purpose']}", "",
           "> Living spec: how this capability behaves now. Written only by `check.py --archive`; never edit it by hand.",
           "> A change proposes edits as a delta; the audit flags any other edit.", "",
           "## Behavior rules", "", "| ID | Rule | Source |", "|---|---|---|", *_rows_md(cap, "rules"), "",
           "## Acceptance criteria", "", "| ID | Covers | Given / When / Then | Source |", "|---|---|---|---|",
           *_rows_md(cap, "criteria"), "",
           "## Non-goals", "", "| ID | Not part of this capability | Source |", "|---|---|---|", *_rows_md(cap, "nongoals"), "",
           "## Withdrawn", "", "Kept so an ID is never reused.", "", "| ID | Was | Reason | By change |", "|---|---|---|---|",
           *_rows_md(cap, "withdrawn"), ""]
    return "\n".join(out)


def load_living(project: Path) -> dict[str, dict]:
    """capability name -> state, for every .tracespec/specs/<name>/spec.md."""
    out: dict[str, dict] = {}
    root = specs_dir(project)
    if root.is_dir():
        for d in sorted(root.iterdir()):
            f = d / "spec.md"
            if d.is_dir() and f.is_file():
                out[d.name] = parse_living(f.read_text(encoding="utf-8"))
    return out


def all_ids(caps: dict[str, dict]) -> dict[str, str]:
    """Every ID used in any living spec (also withdrawn ones) -> its capability."""
    out: dict[str, str] = {}
    for name, cap in caps.items():
        for table in (*TABLES, "withdrawn"):
            for i in cap[table]:
                out[i] = name
    return out


def living_row_hashes(cap: dict) -> dict[str, str]:
    return {i: row_hash(cap[t][i]) for t in TABLES for i in cap[t]}


# ---- merge -------------------------------------------------------------------------------------------------

def _source(cell: str, change: str) -> str:
    if SOURCE.search(cell) and f"({change})" not in cell:
        return f"{cell} ({change})"
    return cell


def _shape(cells: list[str], table: str, change: str) -> list[str]:
    n = MIN_COLS[table]
    out = (cells + [""] * n)[:n]
    out[-1] = _source(out[-1], change)
    return out


def merge(cap: dict | None, rows: list[dict], change: str, purpose: str | None) -> tuple[dict, list[tuple[str, str]], dict]:
    """Apply one capability's delta rows to its living state. Returns (new state, problems, ops by ID).
    Problems are (code, message); with any problem the new state must not be written."""
    new = copy.deepcopy(cap) if cap else empty_cap()
    is_new = cap is None or not any(new[t] for t in TABLES)
    problems: list[tuple[str, str]] = []
    ops: dict[str, str] = {}
    seen: set[str] = set()
    existing = {i for t in (*TABLES, "withdrawn") for i in new[t]}
    for r in rows:
        i, op, cells = r["id"], r["op"], r["cells"]
        table = table_of(i)
        if i in seen:
            problems.append(("DELTA011", f"{i} appears twice in the delta"))
            continue
        seen.add(i)
        need = 2 if op == "REMOVED" else MIN_COLS[table]
        if len(cells) < need:
            problems.append(("DELTA008", f"{op} row {i} has {len(cells)} columns; it needs {need}"))
            continue
        if op == "ADDED":
            if i in existing:
                problems.append(("DELTA001", f"{i} is ADDED, but it already exists in the living specs (or was withdrawn): "
                                 "use the next free ID (check.py --next-id)"))
                continue
            new[table][i] = _shape(cells, table, change)
        elif op == "MODIFIED":
            if i not in new[table]:
                problems.append(("DELTA002", f"{i} is MODIFIED, but it is not in the capability's living spec"))
                continue
            new[table][i] = _shape(cells, table, change)
        else:
            if i not in new[table]:
                problems.append(("DELTA002", f"{i} is REMOVED, but it is not in the capability's living spec"))
                continue
            old = new[table].pop(i)
            new["withdrawn"][i] = [i, old[2] if table == "criteria" else old[1], cells[1], change]
        ops[i] = op
    if is_new:
        if not purpose or len(purpose) < 20:
            problems.append(("DELTA009", "a new capability needs a 'Purpose:' line of at least 20 characters under its "
                             "'Capability:' heading"))
        else:
            new["purpose"] = purpose
    elif purpose and purpose != new["purpose"]:
        new["purpose"] = purpose
    return new, problems, ops


def validate_state(cap: dict) -> list[tuple[str, str]]:
    """Consistency of a capability after a merge."""
    out: list[tuple[str, str]] = []
    covered: set[str] = set()
    for i, c in cap["criteria"].items():
        covers = RULE_IDS.findall(c[1])
        if not covers:
            out.append(("SPEC004", f"{i} names no FR or NFR it covers"))
        for r in covers:
            if r not in cap["rules"]:
                out.append(("SPEC014", f"{i} covers {r}, which is not a rule of this capability"))
            covered.add(r)
    for i, c in cap["rules"].items():
        if i not in covered:
            out.append(("SPEC001", f"{i} has no acceptance criterion once the change is merged"))
        if not SOURCE.search(c[2]):
            out.append(("SPEC005", f"{i} names no source (a Q, ASM, OPEN or G)"))
    return out

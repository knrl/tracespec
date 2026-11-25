"""Building the trace graph. Standard library only.

`change_graph` turns one change (its proposal, its tasks, the merged capabilities, the current symbols) into nodes and edges.
`assemble_baseline` merges that with a capability's previous baseline, refreshes the hashes, and prunes what no longer exists;
it is what archive and reconfirm write. The same `change_graph` feeds the live query for a change that is still in flight.

Node ids: rules, criteria and non-goals are project-wide (FR-12); goals, questions, assumptions, designs and tasks are
namespaced by the change (add-discount/Q-1, add-discount/T-2); code and tests are 'path::qualified.name'; a file is its path.
"""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

import current
import living
import tracing
from common import classify, file_hash, test_ids, walk_files

ORIGIN = re.compile(r"\b(?:Q|ASM|OPEN|G)-\d+\b")
SOURCE_CHANGE = re.compile(r"\(([^)]+)\)\s*$")
ORIGIN_KINDS = {"Q": "question", "G": "goal", "ASM": "assumption", "OPEN": "open"}
NODE_KINDS_ROW = ("rule", "criterion", "nongoal")
LEAF_KINDS = ("symbol", "test", "file")


def refs_of(cell: str) -> list[str]:
    """External references in a Ref cell: tickets, issues, URLs, any text, separated by commas or semicolons."""
    return [r.strip() for r in re.split(r"[,;]", cell or "") if r.strip() and r.strip() not in ("-", "n/a", "none")]


def row_kind(i: str) -> str:
    return "rule" if i.startswith(("FR-", "NFR-")) else "criterion" if i.startswith("AC-") else "nongoal"


# ---- origins: goals, questions, assumptions, and the external references on them ----------------------------

HEADER_REF = re.compile(r"^\s*Refs?(?:erences?)?\s*:\s*(.+?)\s*$", re.I | re.M)
CHANGE = "Change"        # the pseudo-goal that carries a change-level reference: <change>/Change


def origin_graph(change: str, proposal: str) -> tuple[dict, set]:
    nodes: dict[str, tuple] = {}
    edges: set[tuple] = set()
    head = HEADER_REF.search("\n".join((proposal or "").splitlines()[:12]))
    if head and refs_of(head.group(1)):
        nodes[f"{change}/{CHANGE}"] = ("goal", f"the change {change}", None)
        for ref in refs_of(head.group(1)):
            nodes[ref] = ("ref", "", None)
            edges.add((f"{change}/{CHANGE}", ref, "ref"))
    for i, row in tracing.named_rows(proposal or "").items():
        prefix = i.split("-")[0]
        if prefix not in ORIGIN_KINDS:
            continue
        if prefix == "Q":
            text = f"{tracing.cell(row, 'question', fallback=1)} -- {tracing.cell(row, 'answer', fallback=2)}"
        elif prefix == "G":
            text = tracing.cell(row, "goal", fallback=1)
        else:
            text = tracing.cell(row, "item", fallback=1)
        nid = f"{change}/{i}"
        nodes[nid] = (ORIGIN_KINDS[prefix], text.strip()[:300], None)
        for ref in refs_of(tracing.cell(row, "ref")):
            nodes[ref] = ("ref", "", None)
            edges.add((nid, ref, "ref"))
        for sid in ORIGIN.findall(tracing.cell(row, "source")):
            if sid != i:
                edges.add((nid, f"{change}/{sid}", "source"))
    return nodes, edges


def source_edges(rows: dict[str, list[str]], nodes: dict, source_col: int) -> set:
    """rule or design -> goal/question, from its Source cell ('Q-1, Q-2 (add-cart)') and the nodes that exist."""
    out = set()
    for i, cells in rows.items():
        cell = cells[source_col] if len(cells) > source_col else ""
        m = SOURCE_CHANGE.search(cell)
        if not m:
            continue
        for sid in ORIGIN.findall(cell):
            target = f"{m.group(1)}/{sid}"
            if target in nodes:
                out.add((i, target, "source"))
    return out


# ---- tests -------------------------------------------------------------------------------------------------

def test_files_for(project: Path, layout: dict, ac_ids: set[str]) -> dict[str, list[str]]:
    """AC id -> test files whose text names it (AC3, AC_3 and AC-3 all count). The fallback when no test symbol is named so."""
    found: dict[str, list[str]] = {}
    for rel in walk_files(project):
        if classify(rel, layout) != "test":
            continue
        try:
            text = (project / rel).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for i in test_ids(text):
            if i in ac_ids:
                found.setdefault(i, []).append(rel)
    return {k: sorted(v) for k, v in found.items()}


def test_links(project: Path, layout: dict, ac_ids: set[str], syms: dict, files: dict) -> tuple[dict, set]:
    """Test symbols whose name carries an AC number; a test file that names it is the fallback."""
    nodes: dict[str, tuple] = {}
    edges: set[tuple] = set()
    named: set[str] = set()
    for sid, s in sorted(syms.items()):
        if classify(s["path"], layout) != "test" or s["kind"] in ("module", "file"):
            continue
        for ac in test_ids(s["name"]):
            if ac in ac_ids:
                nodes[sid] = ("test", s["name"], s["hash"])
                edges.add((sid, ac, "verifies"))
                named.add(ac)
    fallback = test_files_for(project, layout, ac_ids - named)
    for ac, paths in fallback.items():
        for p in paths:
            nodes[p] = ("test", "", files.get(p) or file_hash(project / p))
            edges.add((p, ac, "verifies"))
    return nodes, edges


# ---- one change --------------------------------------------------------------------------------------------

def change_graph(project: Path, layout: dict, name: str, ch: dict, caps_after: dict, syms: dict, files: dict):
    """(nodes, edges, cap_of) for a change: its origins, the merged rules and criteria, design, tasks, code and tests."""
    nodes, edges = origin_graph(name, ch["proposal"] or "")
    cap_of: dict[str, str] = {}
    rule_rows: dict[str, list[str]] = {}
    for cap, st in caps_after.items():
        for table in ("rules", "criteria", "nongoals"):
            for i, cells in st[table].items():
                text = cells[2] if table == "criteria" else cells[1]
                nodes[i] = (row_kind(i), text, living.row_hash(cells))
                cap_of[i] = cap
                if table == "rules":
                    rule_rows[i] = cells
        for ac, c in st["criteria"].items():
            for r in living.RULE_IDS.findall(c[1]):
                if r in st["rules"]:
                    edges.add((ac, r, "covers"))
    design = {i: r for i, r in tracing.named_rows(ch["text"]).items() if i.startswith("D-")}
    for i, row in design.items():
        nodes[f"{name}/{i}"] = ("design", tracing.cell(row, "decision", fallback=1)[:300], None)
        for sid in ORIGIN.findall(" ".join(list(row.values())[2:])):
            if f"{name}/{sid}" in nodes:
                edges.add((f"{name}/{i}", f"{name}/{sid}", "source"))
    edges |= source_edges(rule_rows, nodes, 2)       # older origins are linked again when a baseline is assembled
    if f"{name}/{CHANGE}" in nodes:                  # a change-level reference covers every rule the change adds or modifies
        for r in ch["rows"]:
            if r["op"] in ("ADDED", "MODIFIED") and r["id"] in rule_rows:
                edges.add((r["id"], f"{name}/{CHANGE}", "source"))
    for tid, t in tracing.parse_tasks(ch["tasks_text"]).items():
        tn = f"{name}/{tid}"
        nodes[tn] = ("task", re.sub(r"\s*\((?:serves|needs).*$", "", t["text"])[:200], None)
        for sid in t["serves"]:
            target = f"{name}/{sid}" if sid.startswith("D-") else sid
            if target in nodes:
                edges.add((tn, target, "serves"))
        for sym in t["symbols"]:
            if sym in syms:
                nodes[sym] = ("test" if classify(syms[sym]["path"], layout) == "test" else "symbol", syms[sym]["kind"], syms[sym]["hash"])
                edges.add((sym, tn, "built_by"))
        if not t["symbols"]:
            for f in t["files"]:
                h = files.get(f) or file_hash(project / f)
                if h:
                    nodes[f] = ("file", "", h)
                    edges.add((f, tn, "built_by"))
    ac_ids = {i for i in nodes if i.startswith("AC-")}
    tn_nodes, tn_edges = test_links(project, layout, ac_ids, syms, files)
    nodes.update(tn_nodes)
    edges |= tn_edges
    return nodes, edges, cap_of


# ---- a capability's baseline -------------------------------------------------------------------------------

def _neighbours(n: str, kind: str, parents: dict, children: dict) -> set[str]:
    if kind in NODE_KINDS_ROW:
        return parents[n] | children[n]
    if kind in ("goal", "question", "assumption", "open"):
        return parents[n]
    if kind == "task":
        return parents[n] | children[n]
    if kind == "design":
        return parents[n]
    return set()


def closure(nodes: dict, edges: set, cap_of: dict, cap: str) -> tuple[dict, set]:
    """The part of a change graph that belongs to one capability: its rows, what they came from, and what was built for them."""
    parents, children = defaultdict(set), defaultdict(set)
    for s, d, _k in edges:
        parents[s].add(d)
        children[d].add(s)
    seeds = {i for i, c in cap_of.items() if c == cap}
    seen, stack = set(seeds), list(seeds)
    while stack:
        n = stack.pop()
        for m in _neighbours(n, nodes[n][0] if n in nodes else "", parents, children):
            if m in seen or m not in nodes:
                continue
            if m in cap_of and cap_of[m] != cap:
                continue
            seen.add(m)
            stack.append(m)
    return {i: nodes[i] for i in seen if i in nodes}, {e for e in edges if e[0] in seen and e[1] in seen}


def assemble_baseline(project: Path, layout: dict, cap: str, state: dict, change_nodes: dict, change_edges: set, old: dict | None,
                      touched: set[str], removed: set[str], syms: dict, files: dict) -> tuple[dict, set]:
    """The new baseline of a capability: the previous one carried over, this change merged in, hashes refreshed from what
    is true now, and nodes whose symbol or file no longer exists dropped (archive re-baselines the capability)."""
    nodes: dict[str, tuple] = {}
    edges: set[tuple] = set()
    if old:
        for i, v in old["nodes"].items():
            if v[0] not in NODE_KINDS_ROW and i not in removed:
                nodes[i] = v
        for s, d, k in old["edges"]:
            if k in ("ref", "built_by") or (k == "source" and ("/" in s or d.endswith("/" + CHANGE))):
                edges.add((s, d, k))
            elif k == "serves" and d not in touched and d not in removed:
                edges.add((s, d, k))
    nodes.update(change_nodes)
    edges |= change_edges
    rule_rows = {i: state["rules"][i] for i in state["rules"]}
    edges |= source_edges(rule_rows, nodes, 2)
    # rows come from the merged spec
    for table in ("rules", "criteria", "nongoals"):
        for i, cells in state[table].items():
            nodes[i] = (row_kind(i), cells[2] if table == "criteria" else cells[1], living.row_hash(cells))
    # refresh code, test and file hashes from now; drop what is gone
    for i, (kind, text, _h) in list(nodes.items()):
        if kind in LEAF_KINDS:
            h = current.hash_now(i, syms, files)
            if h is None:
                del nodes[i]
            else:
                nodes[i] = (kind, text, h)
    edges = {e for e in edges if e[0] in nodes and e[1] in nodes}
    served = {s for s, d, k in edges if k == "serves"}
    for i, v in list(nodes.items()):
        if v[0] == "task" and i not in served:
            del nodes[i]
    edges = {e for e in edges if e[0] in nodes and e[1] in nodes}
    linked = {x for e in edges for x in e[:2]}
    for i, v in list(nodes.items()):
        if v[0] in LEAF_KINDS and i not in linked:
            del nodes[i]
    return nodes, edges

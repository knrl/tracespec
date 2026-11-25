"""The trace graph and its query: `check.py --trace <anything>`. Standard library only.

The graph is loaded from the baseline databases (one per capability) plus any change still in flight, then joined with the live
layer (current hashes, last test results). Edges run child -> parent, so 'up' climbs from code to the ticket, 'down' goes the other
way. A query answers in one pass over in-memory adjacency lists; nothing is rebuilt on disk.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

import current
import living
import store
from common import ID_RE, specs_dir

KIND_ORDER = {"ref": 0, "goal": 1, "question": 1, "assumption": 1, "open": 1, "rule": 2, "nongoal": 2, "criterion": 3,
              "design": 3, "test": 4, "task": 4, "symbol": 5, "file": 5}
LABEL = {"ref": "ref", "goal": "goal", "question": "question", "assumption": "assumption", "open": "open question",
         "rule": "rule", "nongoal": "non-goal", "criterion": "criterion", "design": "design", "test": "test", "task": "task",
         "symbol": "code", "file": "file"}
STORY_KINDS = ("test", "symbol", "file", "task", "design")      # for these the default answer is the whole story of their rule
EDGE_LABEL = {"covers": "covers", "source": "from", "ref": "ref", "verifies": "verifies", "serves": "serves", "built_by": "built by"}


class Graph:
    def __init__(self) -> None:
        self.nodes: dict[str, dict] = {}
        self.parents: dict[str, list[tuple[str, str]]] = defaultdict(list)    # id -> [(edge kind, parent id)]
        self.children: dict[str, list[tuple[str, str]]] = defaultdict(list)
        self._edges: set[tuple] = set()

    def add_node(self, i: str, kind: str, text: str, hash_: str | None, cap: str | None = None, flag: str | None = None) -> None:
        old = self.nodes.get(i)
        if old and not flag and old.get("flag"):
            return
        self.nodes[i] = {"kind": kind, "text": text or "", "hash": hash_, "cap": cap or (old or {}).get("cap"), "flag": flag}

    def add_edge(self, src: str, dst: str, kind: str) -> None:
        if (src, dst, kind) in self._edges:
            return
        self._edges.add((src, dst, kind))
        self.parents[src].append((kind, dst))
        self.children[dst].append((kind, src))

    def add_baseline(self, cap: str, base: dict) -> None:
        for i, (kind, text, h) in base["nodes"].items():
            self.add_node(i, kind, text, h, cap)
        for s, d, k in base["edges"]:
            self.add_edge(s, d, k)

    def add_change(self, name: str, nodes: dict, edges: set, cap_of: dict, ops: dict) -> None:
        """A change that is still in flight: its rows override the baseline's, marked with the operation."""
        for i, (kind, text, h) in nodes.items():
            flag = f"in flight: {ops[i].lower()}" if i in ops else ("in flight" if "/" in i else None)
            self.add_node(i, kind, text, h, cap_of.get(i), flag)
        for s, d, k in edges:
            self.add_edge(s, d, k)

    def sorted_children(self, i: str) -> list[tuple[str, str]]:
        return sorted(self.children.get(i, []), key=lambda e: (KIND_ORDER.get(self.nodes.get(e[1], {}).get("kind", ""), 9), e[1]))


def build(project: Path, inflight: list[tuple] | None = None) -> Graph:
    """Baselines of every capability, plus changes in flight: [(name, nodes, edges, cap_of, ops)]."""
    g = Graph()
    root = specs_dir(project)
    if root.is_dir():
        for d in sorted(x for x in root.iterdir() if x.is_dir()):
            base = store.read_baseline(project, d.name)
            if base:
                g.add_baseline(d.name, base)
    for name, nodes, edges, cap_of, ops in inflight or []:
        g.add_change(name, nodes, edges, cap_of, ops)
    return g


# ---- what each node looks like now -------------------------------------------------------------------------

class Now:
    """The live layer, loaded once per query."""

    def __init__(self, project: Path) -> None:
        self.syms = current.current_symbols(project)
        self.files = current.current_files(project)
        self.runs = current.run_state(project)
        self.by_hash: dict[str, str] = {}
        for sid, s in self.syms.items():
            self.by_hash.setdefault(s["hash"], sid)

    def state(self, g: Graph, i: str) -> str:
        n = g.nodes[i]
        if n["kind"] in ("symbol", "test", "file"):
            if n.get("flag"):
                return ""
            now = current.hash_now(i, self.syms, self.files)
            if now == n["hash"]:
                return "ok"
            if now is None:
                moved = self.by_hash.get(n["hash"] or "")
                return f"MISSING (same text now at {moved})" if moved and moved != i else "MISSING"
            return "CHANGED since the last archive"
        if n["kind"] == "criterion":
            r = self.runs.get(i)
            if not r:
                return "not run"
            return f"run: {r['status']}" + (" (stale: a linked file changed since)" if r["stale"] else " (fresh)")
        return ""


# ---- resolving what was asked about ------------------------------------------------------------------------

def resolve(g: Graph, now: Now, target: str) -> list[str]:
    t = target.strip()
    if t in g.nodes:
        return [t]
    m = re.fullmatch(r"(.+?):(\d+)", t)
    if m and "::" not in t:                       # path:line -> the symbol that covers the line
        hits = [sid for sid, s in now.syms.items() if s["path"] == m.group(1).replace("\\", "/") and s["start"] <= int(m.group(2)) <= s["end"]
                and s["kind"] not in ("module", "file")]
        hits = sorted(hits, key=lambda sid: now.syms[sid]["end"] - now.syms[sid]["start"])[:1] or \
            [sid for sid, s in now.syms.items() if s["path"] == m.group(1) and s["start"] <= int(m.group(2)) <= s["end"]][:1]
        return [h for h in hits if h in g.nodes] or hits
    if ID_RE.fullmatch(t) and t.split("-")[0] in ("Q", "G", "T", "D", "ASM", "OPEN"):
        return sorted(i for i in g.nodes if i.endswith("/" + t))
    if "::" in t or "/" in t or "." in t:
        path = t.replace("\\", "/")
        exact = [i for i in g.nodes if i == path or i.startswith(path + "::")]
        if exact:
            return sorted(exact)
    refs = [i for i, n in g.nodes.items() if n["kind"] == "ref" and i.lower() == t.lower()]
    if refs:
        return refs
    caps = sorted({n["cap"] for n in g.nodes.values() if n["cap"]})
    if t in caps:
        return sorted((i for i, n in g.nodes.items() if n["cap"] == t and n["kind"] == "rule"), key=lambda x: living.id_key(x))
    tests = sorted(i for i, n in g.nodes.items() if n["kind"] == "test" and (t in i or t in n["text"]))
    return tests


# ---- walking and rendering ---------------------------------------------------------------------------------

def label(g: Graph, now: Now, i: str, edge: str | None = None) -> str:
    n = g.nodes[i]
    text = n["text"].replace("\n", " ")
    text = (text[:72] + "...") if len(text) > 75 else text
    state = now.state(g, i)
    bits = [x for x in (n.get("flag"), state) if x]
    cap = f" [{n['cap']}]" if n["kind"] in ("rule", "criterion", "nongoal") and n["cap"] else ""
    lead = f"{EDGE_LABEL.get(edge, edge)}  " if edge else ""
    return f"{lead}{LABEL[n['kind']]} {i}{cap}  {text}".rstrip() + (f"   <{'; '.join(bits)}>" if bits else "")


def ancestors(g: Graph, i: str, depth: int) -> list[tuple[int, str, str]]:
    out, seen = [], {i}

    def go(n: str, d: int, via: str | None) -> None:
        if d > depth:
            return
        for kind, p in sorted(g.parents.get(n, []), key=lambda e: (KIND_ORDER.get(g.nodes.get(e[1], {}).get("kind", ""), 9), e[1])):
            if p in seen or p not in g.nodes:
                continue
            seen.add(p)
            out.append((d, p, kind))
            go(p, d + 1, kind)

    go(i, 1, None)
    return out


def render(g: Graph, now: Now, targets: list[str], mode: str, depth: int, limit: int) -> tuple[list[str], set[str]]:
    """Text lines and the set of node ids shown."""
    lines: list[str] = []
    shown: set[str] = set()
    expanded: set[str] = set()

    def down(n: str, d: int, edge: str | None, mark: set[str], path: set[str]) -> None:
        if d > depth or n in path:
            return
        shown.add(n)
        lines.append("  " * d + ("==> " if n in mark else "") + label(g, now, n, edge))
        if n in expanded and g.children.get(n):
            lines[-1] += "   (children shown above)"
            return
        expanded.add(n)
        for kind, c in g.sorted_children(n):
            if c in g.nodes:
                down(c, d + 1, kind, mark, path | {n})

    def up(n: str, d: int, path: set[str]) -> None:
        """Ancestors as a tree growing upward from n, each marked with ^."""
        if d > depth:
            return
        for kind, p in sorted(g.parents.get(n, []), key=lambda e: (KIND_ORDER.get(g.nodes.get(e[1], {}).get("kind", ""), 9), e[1])):
            if p in path or p not in g.nodes:
                continue
            shown.add(p)
            lines.append("  " * d + "^ " + label(g, now, p, kind))
            up(p, d + 1, path | {n})

    for t in targets:
        n = g.nodes[t]
        story = mode == "story" or (mode == "both" and n["kind"] in STORY_KINDS)
        if story:
            tops = [a for _d, a, _k in ancestors(g, t, depth) if g.nodes[a]["kind"] == "rule"] or [t]
            roots = [x for x in tops if not any(x != y and y in {a for _d, a, _k in ancestors(g, x, depth)} for y in tops)] or tops
            for r in sorted(set(roots)):
                for _d, p, k in reversed(ancestors(g, r, depth)):
                    if g.nodes[p]["kind"] in ("ref", "goal", "question", "assumption", "open"):
                        shown.add(p)
                        lines.append(f"^ {label(g, now, p, k)}")
                down(r, 0, None, {t}, set())
        else:
            if mode == "down":
                down(t, 0, None, {t}, set())
            else:
                shown.add(t)
                lines.append("==> " + label(g, now, t))
                up(t, 1, {t})
                if mode == "both":
                    for kind, c in g.sorted_children(t):
                        if c in g.nodes:
                            down(c, 1, kind, set(), {t})
    if len(lines) > limit:
        extra = len(lines) - limit
        lines = lines[:limit] + [f"... {extra} more line(s); narrow it with --depth or --limit"]
    return lines, shown


def to_json(g: Graph, now: Now, shown: set[str], targets: list[str]) -> dict:
    return {"targets": targets,
            "nodes": [{"id": i, "kind": g.nodes[i]["kind"], "text": g.nodes[i]["text"], "capability": g.nodes[i]["cap"],
                       "state": now.state(g, i), "flag": g.nodes[i]["flag"]} for i in sorted(shown) if i in g.nodes],
            "edges": [{"from": s, "to": d, "kind": k} for s, d, k in sorted(g._edges) if s in shown and d in shown]}


def to_mermaid(g: Graph, shown: set[str]) -> str:
    ids = {i: f"n{n}" for n, i in enumerate(sorted(shown))}
    out = ["flowchart TD"]
    for i, nid in ids.items():
        text = g.nodes[i]["text"].replace('"', "'")[:40]
        short = i.split("::")[-1] if "::" in i else i
        out.append(f'  {nid}["{LABEL[g.nodes[i]["kind"]]} {short}<br/>{text}"]')
    for s, d, k in sorted(g._edges):
        if s in ids and d in ids:
            out.append(f"  {ids[d]} -->|{EDGE_LABEL.get(k, k)}| {ids[s]}")
    return "\n".join(out)


def living_matrix(g: Graph, now: Now, caps: dict[str, dict]) -> str:
    """Markdown of every capability: rule -> criteria -> tests -> code -> last result. A snapshot of the live graph, on request."""
    def esc(text: str) -> str:
        return (text or "").replace("|", "/").replace("\n", " ").strip()

    out = ["# Living traceability matrix", "",
           "Exported by `check.py --export --living` from the trace store. It is a snapshot: ask `check.py --trace` for the live answer.", ""]
    for cap in sorted(caps):
        st = caps[cap]
        out += [f"## {cap}", "", f"Purpose: {st['purpose']}", "",
                "| Rule | Text | Criteria | Tests | Code | Result |", "|---|---|---|---|---|---|"]
        for q in sorted(st["rules"], key=living.id_key):
            acs = sorted((c for k, c in g.children.get(q, []) if k == "covers"), key=living.id_key)
            tests = sorted({t for ac in acs for k, t in g.children.get(ac, []) if k == "verifies"})
            tasks = {tk for node in [q, *acs] for k, tk in g.children.get(node, []) if k == "serves"}
            code = sorted({s for tk in tasks for k, s in g.children.get(tk, []) if k == "built_by"})
            res = [now.runs.get(a) for a in acs]
            if not acs:
                verdict = "NO AC"
            elif any(r is None for r in res):
                verdict = "not run"
            else:
                bad = next((r["status"] for r in res if r["status"] != "PASS"), None)
                verdict = (bad or "PASS") + (" (stale)" if any(r["stale"] for r in res) else "")
            out.append(f"| {q} | {esc(st['rules'][q][1])} | {', '.join(acs) or '-'} | {esc(', '.join(tests)) or '-'} | "
                       f"{esc(', '.join(code)) or '-'} | {verdict} |")
        if st["withdrawn"]:
            out += ["", "Withdrawn: " + ", ".join(sorted(st["withdrawn"], key=living.id_key))]
        out.append("")
    return "\n".join(out) + "\n"

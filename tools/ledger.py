"""The ledger, the audit and reconfirm for the living specs. Standard library only.

Per capability, next to its spec.md (all written only by check.py, all in the protected paths):
  trace.db       the baseline graph (store.py): rows, links, and a hash for every symbol and file, as at the last archive
  history.jsonl  an append-only ledger; each line holds the hash of the line before it, the hash of spec.md and the hash of
                 the baseline, so a hand edit of the spec, the database or the ledger breaks the chain

Tamper-evident, not tamper-proof: any edit outside the process shows up as a finding from `--audit`.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path

import current
import links
import living
import store
from common import classify, fingerprint_text, specs_dir

LEAF = ("symbol", "test", "file")
ROW_KINDS = ("rule", "criterion", "nongoal")


def spec_hash(text: str) -> str:
    return fingerprint_text(text)


def line_hash(line: str) -> str:
    return hashlib.sha256(line.encode("utf-8")).hexdigest()[:16]


def cap_path(project: Path, cap: str) -> Path:
    return specs_dir(project) / cap


# ---- history.jsonl -----------------------------------------------------------------------------------------

def ledger_lines(project: Path, cap: str) -> list[str]:
    try:
        text = (cap_path(project, cap) / "history.jsonl").read_text(encoding="utf-8")
    except OSError:
        return []
    return [l for l in text.split("\n") if l.strip()]


def append_ledger(project: Path, cap: str, entry: dict) -> None:
    lines = ledger_lines(project, cap)
    prev = line_hash(lines[-1]) if lines else "genesis"
    line = json.dumps(dict(entry, seq=len(lines) + 1, prev=prev), sort_keys=True)
    p = cap_path(project, cap)
    p.mkdir(parents=True, exist_ok=True)
    with open(p / "history.jsonl", "a", encoding="utf-8", newline="\n") as f:
        f.write(line + "\n")


def verify_ledger(project: Path, cap: str, current_spec_hash: str, current_trace_hash: str | None = None) -> list[str]:
    lines = ledger_lines(project, cap)
    if not lines:
        return ["the ledger (history.jsonl) is missing or empty"]
    problems: list[str] = []
    prev = "genesis"
    last: dict = {}
    for n, line in enumerate(lines, 1):
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            return [f"ledger line {n} is not valid JSON"]
        if entry.get("seq") != n:
            problems.append(f"ledger line {n} has seq {entry.get('seq')}")
        if entry.get("prev") != prev:
            problems.append(f"ledger line {n} does not continue the chain: an earlier line was changed or removed")
        prev = line_hash(line)
        last = entry
    if last.get("specHash") != current_spec_hash:
        problems.append("spec.md differs from the hash in the last ledger line")
    if current_trace_hash is not None and last.get("traceHash") != current_trace_hash:
        problems.append("trace.db differs from the hash in the last ledger line: it was changed outside an archive")
    return problems


# ---- git and tasks -----------------------------------------------------------------------------------------

def changed_files(project: Path) -> list[str] | None:
    """Files git reports as changed or new, or None when this is not a git repository."""
    try:
        p = subprocess.run(["git", "-C", str(project), "status", "--porcelain", "-uall"],
                           capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if p.returncode != 0:
        return None
    return [line[3:].split(" -> ")[-1].strip().strip('"').replace("\\", "/") for line in p.stdout.splitlines()]


def tick_task(tasks_text: str, tid: str, files: list[str], syms: list[str]) -> str | None:
    """The tasks text with T-n ticked and its files and symbols recorded; None if the task is not found."""
    import tracing
    out, hit = [], False
    for line in tasks_text.replace("\r\n", "\n").split("\n"):
        m = re.match(r"^(\s*[-*]\s*)\[( |x|X)\](\s+)(T-\d+)\b(.*)$", line)
        if m and m.group(4) == tid and not hit:
            body = tracing.split_progress(m.group(5))[0]
            line = f"{m.group(1)}[x]{m.group(3)}{tid}{body}"
            if files:
                line += f" files: {', '.join(files)}"
            if syms:
                line += f" symbols: {tracing.SYM_SEP.join(syms)}"
            hit = True
        out.append(line)
    return "\n".join(out) if hit else None


# ---- reading a baseline ------------------------------------------------------------------------------------

def parents_of(base: dict) -> dict[str, list[str]]:
    out: dict[str, list[str]] = defaultdict(list)
    for s, d, _k in base["edges"]:
        out[s].append(d)
    return out


def affected(base: dict, node: str) -> tuple[list[str], list[str]]:
    """(rules, criteria) a node serves: climb through the tasks and criteria that point at it."""
    parents = parents_of(base)
    seen, stack = {node}, [node]
    while stack:
        n = stack.pop()
        for p in parents.get(n, []):
            if p not in seen and p in base["nodes"] and base["nodes"][p][0] in ("task", "criterion", "rule", "design"):
                seen.add(p)
                stack.append(p)
    rules = sorted((i for i in seen if base["nodes"].get(i, ("",))[0] == "rule"), key=living.id_key)
    crit = sorted((i for i in seen if base["nodes"].get(i, ("",))[0] == "criterion"), key=living.id_key)
    return rules, crit


def basis_nodes(project: Path) -> dict[str, list[str]]:
    """criterion -> the test and code nodes its result depends on (for marking a run stale when one of them changes)."""
    out: dict[str, list[str]] = {}
    root = specs_dir(project)
    names = sorted(d.name for d in root.iterdir() if d.is_dir()) if root.is_dir() else []
    for cap in names:
        base = store.read_baseline(project, cap)
        if not base:
            continue
        children: dict[str, list[str]] = defaultdict(list)
        for s, d, _k in base["edges"]:
            children[d].append(s)
        for ac, (kind, _t, _h) in base["nodes"].items():
            if kind != "criterion":
                continue
            rules = [d for s, d, k in base["edges"] if s == ac and k == "covers"]
            nodes, stack = set(), [ac, *rules]
            while stack:
                n = stack.pop()
                for c in children.get(n, []):
                    if c in nodes:
                        continue
                    if base["nodes"].get(c, ("",))[0] in LEAF or base["nodes"].get(c, ("",))[0] == "task":
                        nodes.add(c)
                        stack.append(c)
            out[ac] = sorted(n for n in nodes if base["nodes"][n][0] in LEAF)
    return out


# ---- audit -------------------------------------------------------------------------------------------------

def _finding(cap: str, code: str, severity: str, message: str) -> dict:
    return {"capability": cap, "code": code, "severity": severity, "message": message}


def audit(project: Path, layout: dict, cases: list[dict] | None) -> list[dict]:
    """Compare the living specs, their tests and code with the baseline. cases: a fresh test run, or None to skip it."""
    current.sync(project, layout)
    syms, files = current.current_symbols(project), current.current_files(project)
    by_hash: dict[str, str] = {}
    for sid, s in syms.items():
        by_hash.setdefault(s["hash"], sid)
    out: list[dict] = []
    root = specs_dir(project)
    names = sorted(d.name for d in root.iterdir() if d.is_dir()) if root.is_dir() else []
    passing = {i for c in (cases or []) if c["status"] == "pass" for i in c["ids"]}
    all_ac: set[str] = set()
    for cap in names:
        spec_file = cap_path(project, cap) / "spec.md"
        base = store.read_baseline(project, cap)
        if not spec_file.is_file():
            out.append(_finding(cap, "DRIFT-SPEC", "error", "spec.md is missing"))
            continue
        text = spec_file.read_text(encoding="utf-8")
        state = living.parse_living(text)
        all_ac |= set(state["criteria"])
        if base is None:
            out.append(_finding(cap, "DRIFT-SPEC", "error", "there is no trace.db: this spec was not written by an archive"))
            continue
        for p in verify_ledger(project, cap, spec_hash(text), base["hash"]):
            out.append(_finding(cap, "DRIFT-SPEC", "error", p))
        rows_now = living.living_row_hashes(state)
        rows_then = {i: h for i, (k, _t, h) in base["nodes"].items() if k in ROW_KINDS}
        if rows_now != rows_then:
            changed = sorted({i for i in rows_now if rows_then.get(i) != rows_now[i]} | (set(rows_then) - set(rows_now)),
                             key=living.id_key)
            out.append(_finding(cap, "DRIFT-SPEC", "error", "spec.md was edited outside a change"
                                + (f" (rows {', '.join(changed)})" if changed else "") + ": revert it, or redo the edit through a change"))
        for i, (kind, _t, h) in sorted(base["nodes"].items()):
            if kind not in LEAF:
                continue
            now = current.hash_now(i, syms, files)
            if now == h:
                continue
            code = "DRIFT-TEST" if kind == "test" else "DRIFT-CODE"
            rules, crit = affected(base, i)
            if now is None:
                moved = by_hash.get(h or "")
                what = (f"is gone (the same text is now at {moved}: renamed or moved)" if moved and moved != i
                        else "was deleted or renamed")
            else:
                what = "changed since the last archive"
            out.append(_finding(cap, code, "error", f"{i} {what}; it serves {', '.join(rules) or 'no rule'}"
                                f" and criteria {', '.join(crit) or 'none'}: if the behaviour changed, propose a change; "
                                "if it did not, `--reconfirm`"))
        if cases is not None:
            for i in sorted(state["criteria"], key=living.id_key):
                if i not in passing:
                    out.append(_finding(cap, "UNCOVERED", "error", f"{i} has no passing test in a fresh run"))
    if cases is not None:
        named = {i for c in cases for i in c["ids"] if i.startswith("AC-")}
        for i in sorted(named - all_ac, key=living.id_key):
            out.append(_finding("-", "UNLINKED-TEST", "warning",
                                f"a test names {i}, which no living spec defines (a change in flight may add it)"))
    return out


# ---- reconfirm ---------------------------------------------------------------------------------------------

def capabilities_for(project: Path, names: list[str]) -> tuple[list[str], list[str]]:
    """Resolve capability names and requirement IDs to capabilities. Returns (capabilities, unknown arguments)."""
    caps = living.load_living(project)
    index = living.all_ids(caps)
    found, unknown = [], []
    for n in names:
        cap = n if n in caps else index.get(n)
        if cap is None:
            unknown.append(n)
        elif cap not in found:
            found.append(cap)
    return found, unknown


def reconfirm(project: Path, layout: dict, cap_names: list[str], note: str, cases: list[dict]) -> tuple[bool, list[str]]:
    """Re-verify capabilities whose code or tests changed but whose behaviour did not.
    Allowed only if the spec is untouched and every criterion has a passing test now. A symbol that was renamed or moved is
    followed (same text, new place); one that is gone is unlinked and reported."""
    current.sync(project, layout)
    syms, files = current.current_symbols(project), current.current_files(project)
    by_hash: dict[str, str] = {}
    for sid, s in syms.items():
        by_hash.setdefault(s["hash"], sid)
    passing = {i for c in cases if c["status"] == "pass" for i in c["ids"]}
    plan = []
    for cap in cap_names:
        spec_file = cap_path(project, cap) / "spec.md"
        base = store.read_baseline(project, cap)
        if base is None or not spec_file.is_file():
            return False, [f"{cap}: no baseline to reconfirm against"]
        text = spec_file.read_text(encoding="utf-8")
        state = living.parse_living(text)
        problems = verify_ledger(project, cap, spec_hash(text), base["hash"])
        rows_then = {i: h for i, (k, _t, h) in base["nodes"].items() if k in ROW_KINDS}
        if problems or rows_then != living.living_row_hashes(state):
            return False, [f"{cap}: the spec drifted ({problems[0] if problems else 'rows changed'}): "
                           "a reconfirm cannot cover a changed rule or criterion; propose a change"]
        missing = [i for i in state["criteria"] if i not in passing]
        if missing:
            return False, [f"{cap}: no passing test for {', '.join(sorted(missing, key=living.id_key))}"]
        plan.append((cap, text, state, base))
    msgs = []
    for cap, text, state, base in plan:
        nodes = {i: v for i, v in base["nodes"].items() if v[0] not in ("test",)}
        edges = {e for e in base["edges"] if e[2] != "verifies"}
        refreshed, followed, dropped = 0, [], []
        for i, (kind, t, h) in list(nodes.items()):
            if kind not in LEAF:
                continue
            now = current.hash_now(i, syms, files)
            if now is None:
                new = by_hash.get(h or "")
                if new and new != i and "::" in i:
                    nodes[new] = (kind, t, h)
                    edges = {(new if s == i else s, new if d == i else d, k) for s, d, k in edges}
                    followed.append(f"{i} -> {new}")
                del nodes[i]
                if not new:
                    dropped.append(i)
                continue
            if now != h:
                nodes[i] = (kind, t, now)
                refreshed += 1
        tn, te = links.test_links(project, layout, set(state["criteria"]), syms, files)
        nodes.update(tn)
        edges |= te
        edges = {e for e in edges if e[0] in nodes and e[1] in nodes}
        linked = {x for e in edges for x in e[:2]}
        nodes = {i: v for i, v in nodes.items() if v[0] not in LEAF or i in linked}
        edges = {e for e in edges if e[0] in nodes and e[1] in nodes}
        meta = dict(base["meta"])
        trace_hash = store.write_baseline(project, cap, nodes, edges, meta)
        append_ledger(project, cap, {"event": "reconfirm", "note": note, "specHash": spec_hash(text), "traceHash": trace_hash,
                                     "refreshed": refreshed, "followed": followed, "unlinked": dropped})
        msg = f"{cap}: reconfirmed ({refreshed} hash(es) refreshed, {len(state['criteria'])} criteria pass)"
        if followed:
            msg += f"; followed: {', '.join(followed)}"
        if dropped:
            msg += f"; UNLINKED (gone): {', '.join(dropped)}"
        msgs.append(msg)
    return True, msgs

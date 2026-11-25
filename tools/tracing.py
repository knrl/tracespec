"""Traceability for tracespec: the deterministic coverage checks and the generated matrices.

Used by check.py. Standard library only. Nothing here is judged by a model: every verdict comes from the spec's tables,
the task list and the JUnit results of a real test run.

The chain:  Q / ASM  ->  FR / NFR  ->  AC (acceptance criterion)  ->  test (its name carries the AC)  ->  result
            AC / FR  ->  T (task)  ->  code files        D (design decision)  ->  T (task)
"""
from __future__ import annotations

import re
from pathlib import Path

from common import ID_RE

RULE = ("FR-", "NFR-")
TASK_LINE = re.compile(r"^\s*[-*]\s*\[( |x|X)\]\s+(T-\d+)\b(.*)$")
SYMBOLS = re.compile(r"\bsymbols:\s*(.*)$")
FILES = re.compile(r"\bfiles:\s*(.*?)\s*(?=\bsymbols:|$)")
SYM_SEP = " ;; "      # symbol ids may contain spaces and commas (regions), so they get their own separator


def id_key(i: str) -> tuple[str, int]:
    p, n = i.rsplit("-", 1)
    return p, int(n)


# ---- tables and tasks --------------------------------------------------------------------------------------

def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def named_rows(text: str) -> dict[str, dict[str, str]]:
    """ID -> {lower-case column header: cell}, for every table row whose first cell is an ID."""
    out: dict[str, dict[str, str]] = {}
    lines = text.splitlines()
    sep = re.compile(r"\s*\|[\s:|-]+\|\s*")
    for n, line in enumerate(lines):
        if not line.lstrip().startswith("|") or sep.fullmatch(line):
            continue
        if n + 1 < len(lines) and sep.fullmatch(lines[n + 1]):
            headers = [h.lower() for h in _cells(line)]
            m = n + 2
            while m < len(lines) and lines[m].lstrip().startswith("|"):
                cells = _cells(lines[m])
                first = cells[0].strip("*` ")
                if ID_RE.fullmatch(first):
                    out[first] = {headers[k] if k < len(headers) else f"col{k}": c for k, c in enumerate(cells)}
                m += 1
    return out


def cell(row: dict[str, str], *names: str, fallback: int | None = None) -> str:
    for key, value in row.items():
        if any(n in key for n in names):
            return value
    if fallback is not None:
        vals = list(row.values())
        return vals[fallback] if fallback < len(vals) else ""
    return ""


def ids_of(text: str) -> list[str]:
    seen: list[str] = []
    for m in ID_RE.finditer(text or ""):
        i = f"{m.group(1)}-{m.group(2)}"
        if i not in seen:
            seen.append(i)
    return seen


def split_progress(rest: str) -> tuple[str, list[str], list[str]]:
    """A task line's text without its progress notes, and the files and symbols recorded in them."""
    sm = SYMBOLS.search(rest)
    syms = [s.strip() for s in sm.group(1).split(";;") if s.strip()] if sm else []
    rest = SYMBOLS.sub("", rest) if sm else rest
    fm = FILES.search(rest)
    files = [f.strip() for f in fm.group(1).split(",") if f.strip()] if fm else []
    return FILES.sub("", rest).rstrip(), files, syms


def parse_tasks(text: str | None) -> dict[str, dict]:
    """Checkbox tasks: '- [ ] T-2 Reject empty cart (serves FR-12, AC-31, needs T-1) files: a.py symbols: a.py::f'.
    Returns T-n -> {done, text, serves (IDs other than tasks), needs (task IDs), files, symbols}."""
    out: dict[str, dict] = {}
    for line in (text or "").replace("\r\n", "\n").split("\n"):
        m = TASK_LINE.match(line)
        if not m:
            continue
        body, files, syms = split_progress(m.group(3))
        ids = [i for i in ids_of(body) if i != m.group(2)]
        out[m.group(2)] = {"done": m.group(1) != " ", "text": body.strip(), "files": files, "symbols": syms,
                           "serves": [i for i in ids if not i.startswith("T-")],
                           "needs": [i for i in ids if i.startswith("T-")]}
    return out


def normalize_tasks(text: str) -> str:
    """The text with every task line reduced to '- [ ] T-n ...' without its files: ticking a task or recording its
    files is progress, not an edit of the approved document."""
    out = []
    for line in text.replace("\r\n", "\n").split("\n"):
        m = TASK_LINE.match(line)
        if m:
            line = f"- [ ] {m.group(2)}" + split_progress(m.group(3))[0]
        out.append(line)
    return "\n".join(out)


# ---- the model ---------------------------------------------------------------------------------------------

def effective_spec(caps_after: dict[str, dict], design_text: str) -> str:
    """One text with the post-merge rules and criteria of the touched capabilities and the change's design tables,
    in the shape named_rows reads."""
    out = ["| ID | Rule | Source |", "|---|---|---|"]
    for cap in caps_after.values():
        out += ["| " + " | ".join(c) + " |" for c in cap["rules"].values()]
    out += ["", "| ID | Covers | Given / When / Then | Source |", "|---|---|---|---|"]
    for cap in caps_after.values():
        out += ["| " + " | ".join(c) + " |" for c in cap["criteria"].values()]
    return "\n".join(out) + "\n\n" + (design_text or "")


def build(spec: str, tasks: str | None, cases: list[dict] | None, baseline: list[str] | None,
          ops: dict[str, str] | None = None, other_ac: set[str] | None = None) -> dict:
    """Everything the checks and the matrix need, from the documents and (if tests ran) the results."""
    ops = ops or {}
    other_ac = other_ac or set()      # criteria of capabilities this change does not touch
    srows = named_rows(spec)
    ac_rows = {i: r for i, r in srows.items() if i.startswith("AC-")}
    rules = {i: r for i, r in srows.items() if i.startswith(RULE)}
    designs = {i: r for i, r in srows.items() if i.startswith("D-")}
    task_rows = parse_tasks(tasks)

    ac_covers = {a: [i for i in ids_of(cell(r, "covers", fallback=1)) if i.startswith(RULE)] for a, r in ac_rows.items()}
    req_acs = {q: [a for a, cov in ac_covers.items() if q in cov] for q in rules}
    removed_ac = {i for i, o in ops.items() if o == "REMOVED" and i.startswith("AC-")}

    tests_of: dict[str, list[dict]] = {a: [] for a in ac_rows}
    unknown_ac: dict[str, list[str]] = {}
    new_without_ac: list[str] = []
    skipped_only: list[str] = []
    if cases is not None:
        base = set(baseline) if baseline is not None else None
        for c in cases:
            acs = [i for i in c["ids"] if i.startswith("AC-")]
            for a in acs:
                if a in tests_of:
                    tests_of[a].append(c)
                elif a not in other_ac:
                    unknown_ac.setdefault(a, []).append(c["name"])
            if base is not None and c["name"] not in base and not acs:
                new_without_ac.append(c["name"])
        for a, cs in tests_of.items():
            if cs and all(c["status"] == "skip" for c in cs):
                skipped_only.append(a)

    def ac_result(a: str) -> str:
        if cases is None:
            return "not run"
        live = [c for c in tests_of[a] if c["status"] != "skip"]
        if not live:
            return "NO TEST"
        if any(c["status"] in ("fail", "error") for c in live):
            return "FAIL"
        return "PASS"

    def req_result(q: str) -> str:
        acs = req_acs[q]
        if not acs:
            return "NO AC"
        rs = [ac_result(a) for a in acs]
        for bad in ("NO TEST", "FAIL", "not run"):
            if bad in rs:
                return bad
        return "PASS"

    task_serves = {t: d["serves"] for t, d in task_rows.items()}
    served = {i for ids in task_serves.values() for i in ids}
    return {"srows": srows, "ac_rows": ac_rows, "rules": rules, "designs": designs, "task_rows": task_rows,
            "ac_covers": ac_covers, "req_acs": req_acs, "tests_of": tests_of, "unknown_ac": unknown_ac,
            "new_without_ac": new_without_ac, "skipped_only": skipped_only, "task_serves": task_serves,
            "served": served, "ac_result": {a: ac_result(a) for a in ac_rows},
            "req_result": {q: req_result(q) for q in rules}, "ran": cases is not None, "cases": cases or [],
            "ops": ops, "removed_ac": removed_ac}


# ---- the deterministic checks ------------------------------------------------------------------------------

def check(model: dict, gate: int, tasks_exist: bool, baseline_known: bool, add) -> dict:
    """Add findings with add(code, severity, message, owner='agent'); return the coverage numbers."""
    m = model
    ops = m["ops"]
    touched = {i for i, o in ops.items() if o in ("ADDED", "MODIFIED")}
    if gate >= 3:
        if not tasks_exist:
            add("TASK000", "error", "the task list does not exist: write tasks.md (or the tasks in proposal.md)")
        else:
            for a in sorted((i for i in m["ac_rows"] if i in touched), key=id_key):
                if a not in m["served"]:
                    add("TASK001", "error", f"{a} is in no task (a task line must name it)")
            for d in sorted(m["designs"], key=id_key):
                if d not in m["served"]:
                    add("TASK002", "error", f"{d} is in no task (a task line must name it)")
            for t, ids in m["task_serves"].items():
                for i in ids:
                    if i not in m["srows"] and i not in ops:
                        add("TASK003", "error", f"{t} serves {i}, which the spec does not define")
        if not baseline_known:
            add("TEST008", "warning", "no baseline of existing tests is recorded (check.py --baseline), so new tests "
                "without an acceptance criterion cannot be found")
    if m["ran"]:
        for a, cov in m["ac_covers"].items():
            if m["ac_result"][a] == "NO TEST" and gate >= 3:
                add("TEST001", "error", f"{a} (covers {', '.join(cov) or 'nothing'}) has no test in the run: no test name "
                    f"carries {a}" + (", or all of them are skipped" if a in m["skipped_only"] else ""))
        for a, names in m["unknown_ac"].items():
            if a in m["removed_ac"]:
                add("TEST002", "error", f"a test names {a}, which this change removes: delete or rewrite it ({', '.join(names[:3])})")
            else:
                add("TEST002", "error", f"a test names {a}, which the spec does not define: {', '.join(names[:3])}")
        for n in m["new_without_ac"]:
            add("TEST005", "error", f"new test '{n}' names no acceptance criterion: add the AC number to its name, "
                "or remove the test")
        if gate == 3:
            for a, cs in m["tests_of"].items():
                live = [c for c in cs if c["status"] != "skip"]
                if not live or not all(c["status"] == "pass" for c in live):
                    continue
                if ops.get(a) == "MODIFIED":
                    add("TEST007", "error", f"{a} was modified, but its tests still pass: update a test to the new "
                        "behaviour so that it fails before the code changes")
                elif ops.get(a) == "ADDED":
                    add("TEST006", "warning", f"{a}: its tests already pass before the feature code exists; "
                        "the test writer must say why (a test that cannot fail proves nothing)")
        if gate >= 4:
            for a in m["ac_rows"]:
                if m["ac_result"][a] != "PASS":
                    add("TEST004", "error", f"{a} has no passing test in the run ({m['ac_result'][a]})")
    if gate >= 4:
        open_tasks = [t for t, d in m["task_rows"].items() if not d["done"]]
        if open_tasks:
            add("TASK004", "error", f"tasks not done: {', '.join(sorted(open_tasks, key=id_key))} "
                "(tick with check.py --task-done)")
    r = m["req_result"]
    return {"requirements": len(r), "requirementsPass": sum(1 for v in r.values() if v == "PASS"),
            "ac": len(m["ac_rows"]), "acPass": sum(1 for v in m["ac_result"].values() if v == "PASS"),
            "touched": len(touched), "removed": sum(1 for o in ops.values() if o == "REMOVED")}


# ---- the matrices ------------------------------------------------------------------------------------------

def esc(text: str) -> str:
    return (text or "").replace("|", "/").replace("\n", " ").strip()


def matrix(model: dict, title: str, spec_version: str, run_info: str) -> str:
    m = model
    rr, ar, ops = m["req_result"], m["ac_result"], m["ops"]
    count = lambda d, v: sum(1 for x in d.values() if x == v)  # noqa: E731
    out = [f"# Traceability matrix: {title}", "",
           "Generated by `check.py`. Do not edit: the next check overwrites this file. Every verdict comes from the "
           "spec's tables, the task list and a real test run. A test counts for an acceptance criterion only when its "
           "name carries the AC number. Rows cover the touched capabilities as they will be after the change.", "",
           f"Proposal version: {spec_version} · Tests: {run_info}", "", "## Summary", "",
           "| | Total | Pass | Fail | No test | No AC | Not run |", "|---|---|---|---|---|---|---|",
           f"| Requirements (FR, NFR) | {len(rr)} | {count(rr, 'PASS')} | {count(rr, 'FAIL')} | {count(rr, 'NO TEST')} | "
           f"{count(rr, 'NO AC')} | {count(rr, 'not run')} |",
           f"| Acceptance criteria (AC) | {len(ar)} | {count(ar, 'PASS')} | {count(ar, 'FAIL')} | {count(ar, 'NO TEST')} | 0 | "
           f"{count(ar, 'not run')} |", ""]

    out += ["## 1. Requirements → acceptance criteria → tests", "",
            "| Requirement | Change | Rule | Acceptance criteria | Tests | Result |", "|---|---|---|---|---|---|"]
    for q in sorted(m["rules"], key=id_key):
        row = m["rules"][q]
        acs = m["req_acs"][q]
        tests = [c["name"] for a in acs for c in m["tests_of"][a]]
        out.append(f"| {q} | {ops.get(q, 'unchanged')} | {esc(cell(row, 'rule', fallback=1))} | "
                   f"{', '.join(acs) or '-'} | {esc(', '.join(dict.fromkeys(tests))) or '-'} | {rr[q]} |")
    removed = sorted((i for i, o in ops.items() if o == "REMOVED"), key=id_key)
    if removed:
        out += ["", f"Removed by this change: {', '.join(removed)}"]

    out += ["", "## 2. Acceptance criteria → tests", "",
            "| Acceptance criterion | Change | Criterion | Covers | Tests | Result |", "|---|---|---|---|---|---|"]
    for a in sorted(m["ac_rows"], key=id_key):
        row = m["ac_rows"][a]
        tests = [f"{c['name']} ({c['status']})" for c in m["tests_of"][a]]
        out.append(f"| {a} | {ops.get(a, 'unchanged')} | {esc(cell(row, 'given', 'criterion', 'example', fallback=2))} | "
                   f"{', '.join(m['ac_covers'][a]) or '-'} | {esc(', '.join(tests)) or '-'} | {ar[a]} |")

    out += ["", "## 3. Tests → acceptance criteria", "",
            "Every test of the run that names an acceptance criterion, with the criterion it checks.", "",
            "| Test | Acceptance criteria | Criterion | Result |", "|---|---|---|---|"]
    rows3 = 0
    for c in m["cases"]:
        acs = [i for i in c["ids"] if i in m["ac_rows"]]
        if not acs:
            continue
        rows3 += 1
        text = "; ".join(f"{a}: {esc(cell(m['ac_rows'][a], 'given', 'criterion', 'example', fallback=2))}" for a in acs)
        out.append(f"| {esc(c['name'])} | {', '.join(acs)} | {text} | {c['status'].upper()} |")
    if not rows3:
        out.append("| - | - | - | - |")
    if m["new_without_ac"]:
        out += ["", "New tests with **no** acceptance criterion (not allowed):", ""] + [f"- {esc(n)}" for n in m["new_without_ac"]]

    out += ["", "## 4. Design decisions → tasks", "",
            "| Design decision | Decision | Source | Tasks |", "|---|---|---|---|"]
    for d in sorted(m["designs"], key=id_key):
        row = m["designs"][d]
        ts = [t for t, ids in m["task_serves"].items() if d in ids]
        out.append(f"| {d} | {esc(cell(row, 'decision', fallback=1))} | "
                   f"{', '.join(ids_of(' '.join(list(row.values())[2:]))) or '-'} | {', '.join(ts) or '-'} |")
    if not m["designs"]:
        out.append("| - | - | - | - |")

    out += ["", "## 5. Tasks", "", "| Task | Done | Serves | Code files |", "|---|---|---|---|"]
    for t in sorted(m["task_rows"], key=id_key):
        d = m["task_rows"][t]
        out.append(f"| {t} | {'yes' if d['done'] else 'no'} | {', '.join(d['serves']) or '-'} | "
                   f"{esc(', '.join(d['files'])) or '-'} |")
    if not m["task_rows"]:
        out.append("| - | - | - | - |")
    return "\n".join(out) + "\n"


def write_text(path: Path, text: str) -> None:
    try:
        path.write_text(text, encoding="utf-8")
    except OSError:
        pass

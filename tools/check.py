#!/usr/bin/env python3
"""Mechanical checks and commands for a tracespec project. Standard library only.
The coordinator runs it; the build agents do not.

Everything agent-oriented lives in .tracespec/ (a change is .tracespec/changes/<name>/; living specs are
.tracespec/specs/<capability>/). The one file for people is docs/features/<change>.md.

Set up and health:
    check.py <folder> --init                   create .tracespec.json from what the folder looks like (stack, tests, test command)
    check.py [<project>] --doctor [--no-run]   is this machine and project ready? Python, git, agents and their guard hook,
                                               the test command (run once unless --no-run)

Checks:
    check.py <project>                         structural checks of the active change
    check.py <project> --gate <n>              n = 1 questions, 2 proposal, 3 tests written, 4 build, 5 close
                                               (gates 3, 4, 5 run the tests)
    check.py <project> --change <name>         another change than the active one
    check.py <project> --matrix                run the tests and print the change's traceability matrix
    check.py <project> --audit [--no-run] [--ci]   compare the living specs, tests and code with the lock (drift)

Commands that write (the tool does the bookkeeping; the agents cannot):
    check.py <project> --baseline              step 0: run the suite, record existing tests and uncommitted files
    check.py <project> --approve change --by NAME --words "..."    record the developer's approval of the proposal
    check.py <project> --approve build  --by NAME --words "..."    record a build approval (only when asked)
    check.py <project> --amend --note "..."    record an edit of an approved proposal that changed no delta row
    check.py <project> --task-start T-n        remember which files are dirty before a task
    check.py <project> --task-done T-n         tick the task if its criteria pass, and record the files it changed
    check.py <project> --archive --ir-open N   close: merge the deltas into the living specs, lock, move to archive/
    check.py <project> --reconfirm <capability|ID>... --note "..."   refresh the lock after a refactor (tests must pass)
    check.py <project> --overview              create the skeleton of the developer overview (docs/features/<change>.md)

Reading (the trace store is binary; this is how you ask it):
    check.py <project> --trace <target> [--up|--down|--story] [--depth N] [--limit N] [--json|--mermaid]
        target: a rule or criterion ID, a test name, a task (T-2), a file, file::symbol, file:line, a ticket, a capability
    check.py <project> --impact <target>       the same as --trace
    check.py <project> --list | --view | --show <change> [--diff] | --next-id FR|NFR|AC|NG
    check.py <project> --export FILE [--living]   write a matrix as Markdown, on request (a snapshot of the live graph)
    check.py <project> --sync [--quiet]        refresh the live layer (runs at the start of every command anyway)
    check.py <project> --install-hooks         git hooks that run --sync after commit, merge and checkout
    check.py --fingerprint <file> | check.py <project> --fingerprint code | check.py --detect <project>

Coverage is judged from the tests that really ran: a requirement is covered when an acceptance criterion names it and a
test whose name carries that AC number ran, and from gate 4 on it passes. A new test (not in the baseline) with no AC
number in its name is an error. Findings print one per line: CODE severity [owner] message. Exit 0 = no errors,
1 = errors, 2 = cannot check.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import current  # noqa: E402
import graph  # noqa: E402
import ledger  # noqa: E402
import links  # noqa: E402
import living  # noqa: E402
import overview  # noqa: E402
import store  # noqa: E402
import tracing  # noqa: E402
from common import (ID_RE, STATE, StateError, active_change, archive_dir, change_dir, changes_dir, classify,  # noqa: E402
                    find_project, fingerprint_code, fingerprint_text, layout_of, load_state, matches, overview_path,
                    specs_dir, write_atomic)

REQUIRED_HEADINGS = ["goal", "existing code facts", "interfaces the tests call", "affected areas"]
SOURCE_IDS = re.compile(r"\b(Q|ASM|OPEN|G)-\d+\b")
APPROVAL_HEADER = "| Document | Version | Approver's words (exact) | Name | Date | Gate | Fingerprint |"
AMENDMENT_HEADER = "| Date | Proposal version | Note | Fingerprint before | Fingerprint after |"
NEW_LOG = ("# Review log\n\n## Approvals\n\n" + APPROVAL_HEADER + "\n|---|---|---|---|---|---|---|\n\n"
           "## Amendments\n\nEdits to an approved proposal that changed no delta row.\n\n" + AMENDMENT_HEADER +
           "\n|---|---|---|---|---|\n\n## Review notes\n\n| ID | Note (word for word) | Outcome | Date |\n|---|---|---|---|\n")


# ---- small helpers -----------------------------------------------------------------------------------------

def read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def run_tests(project: Path, layout: dict):
    """Run the suite and record the result per criterion with the hashes it depends on (so it can be marked stale)."""
    import results
    cases, err = results.run_tests(project, layout, verbose=True)
    if not err:
        current.sync(project, layout)
        current.record_run(project, cases, ledger.basis_nodes(project))
    return cases, err


def table_rows(text: str) -> list[list[str]]:
    return [[c.strip() for c in line.strip().strip("|").split("|")] for line in text.splitlines()
            if line.lstrip().startswith("|")]


def defined_ids(text: str) -> dict[str, list[list[str]]]:
    """ID -> the table rows that define it (an ID is defined as the first cell of a table row)."""
    out: dict[str, list[list[str]]] = {}
    for cells in table_rows(text):
        first = cells[0].strip("*` ")
        if ID_RE.fullmatch(first):
            out.setdefault(first, []).append(cells)
    return out


def ids_in(text: str) -> set[str]:
    return {f"{m.group(1)}-{m.group(2)}" for m in ID_RE.finditer(text)}


class Findings:
    def __init__(self) -> None:
        self.items: list[dict] = []

    def add(self, code: str, severity: str, message: str, owner: str = "agent") -> None:
        self.items.append({"code": code, "severity": severity, "owner": owner, "message": message})

    @property
    def errors(self) -> int:
        return sum(1 for f in self.items if f["severity"] == "error")


def print_findings(f: Findings) -> None:
    for item in f.items:
        print(f"{item['code']} {item['severity']} [{item['owner']}] {item['message']}")


def today() -> str:
    import datetime
    return datetime.date.today().isoformat()


def save_state(project: Path, state: dict) -> None:
    write_atomic(project / STATE, json.dumps(state, indent=2))


def opt(args: list[str], name: str) -> str | None:
    """The value after a flag, or None when it is missing (a following flag is not a value)."""
    if name not in args or args.index(name) + 1 >= len(args):
        return None
    value = args[args.index(name) + 1]
    return None if value.startswith("--") else value


def int_opt(args: list[str], name: str, default: int, low: int = 0, high: int = 10**6) -> int:
    """An integer option; raises UsageError with a plain message when the value is missing or out of range."""
    if name not in args:
        return default
    raw = opt(args, name)
    try:
        value = int(raw) if raw is not None else None
    except ValueError:
        value = None
    if value is None or not low <= value <= high:
        raise UsageError(f"{name} needs a whole number from {low} to {high}")
    return value


class UsageError(Exception):
    pass


KNOWN_FLAGS = frozenset("""--amend --approve --archive --audit --baseline --by --change --ci --depth --detect --diff --doctor --down
--export --fingerprint --gate --help --impact --init --install-hooks --ir-open --json --limit --list --living --matrix --mermaid
--next-id --no-run --note --overview --quiet --reconfirm --run --show --story --sync --task-done --task-start --trace --up
--version --view --words""".split())


def rest_after(args: list[str], name: str) -> list[str]:
    """Positional values after a flag, up to the next flag."""
    if name not in args:
        return []
    out = []
    for a in args[args.index(name) + 1:]:
        if a.startswith("--"):
            break
        out.append(a)
    return out


def append_row(path: Path, header_start: str, row: str) -> None:
    """Add a row at the end of the table whose header line starts with header_start (the log is created if missing)."""
    text = read(path) or NEW_LOG
    lines = text.split("\n")
    for n, line in enumerate(lines):
        if line.startswith(header_start):
            m = n + 1
            while m < len(lines) and lines[m].lstrip().startswith("|"):
                m += 1
            lines.insert(m, row)
            break
    else:
        lines += ["", header_start, "|---|", row]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def set_status_line(path: Path, status: str) -> None:
    lines = (read(path) or "").split("\n")
    for n, line in enumerate(lines[:12]):
        if re.match(r"^\s*(\*\*)?Status(\*\*)?\s*:", line):
            lines[n] = f"Status: {status}"
            break
    path.write_text("\n".join(lines), encoding="utf-8")


def doc_version(text: str) -> str:
    m = re.search(r"^\s*Version\s*:\s*(\S+)", "\n".join(text.splitlines()[:12]), re.M)
    return m.group(1) if m else "?"


def affected_paths(text: str) -> list[str]:
    """The paths in the 'Affected areas' table (first column)."""
    out, on = [], False
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            on = "affected areas" in line.lower()
            continue
        if on and line.lstrip().startswith("|"):
            first = line.strip().strip("|").split("|")[0].strip().strip("*` ")
            if not first or set(first) <= set("-: ") or first.lower() == "path" or "<<" in first:
                continue
            out.append(first.replace("\\", "/"))
    return out


def design_rows_text(text: str) -> str:
    """The D-n rows of a text as one table, so the delta tables are not mistaken for design."""
    rows = {i: r for i, r in tracing.named_rows(text).items() if i.startswith("D-")}
    out = ["| ID | Decision | Why | Source |", "|---|---|---|---|"]
    for i, r in rows.items():
        out.append("| " + " | ".join(r.values()) + " |")
    return "\n".join(out) + "\n"


# ---- loading a change --------------------------------------------------------------------------------------

def load_change(project: Path, name: str) -> dict:
    """The documents of .tracespec/changes/<name>/ and the delta rows in them (in proposal.md and in specs/<cap>/spec.md)."""
    d = change_dir(project, name)
    proposal, design, tasks = read(d / "proposal.md"), read(d / "design.md"), read(d / "tasks.md")
    rows, purposes = [], {}
    texts = [tracing.normalize_tasks(t) for t in (proposal, design) if t]
    if proposal:
        r, p = living.parse_deltas(proposal, None)
        rows += r
        purposes.update(p)
    sdir = d / "specs"
    if sdir.is_dir():
        for sd in sorted(x for x in sdir.iterdir() if x.is_dir()):
            t = read(sd / "spec.md")
            if t:
                texts.append(t)
                r, p = living.parse_deltas(t, sd.name.lower())
                rows += r
                purposes.update(p)
    return {"dir": d, "proposal": proposal, "design": design, "tasks": tasks, "rows": rows, "purposes": purposes,
            "text": "\n\n".join(texts), "tasks_text": tasks if tasks is not None else proposal}


def other_added_ids(project: Path, skip: str) -> dict[str, str]:
    """IDs that other active changes ADD -> the change name."""
    out: dict[str, str] = {}
    root = changes_dir(project)
    if not root.is_dir():
        return out
    for d in sorted(root.iterdir()):
        if d.is_dir() and d.name not in ("archive", skip):
            for r in load_change(project, d.name)["rows"]:
                if r["op"] == "ADDED":
                    out[r["id"]] = d.name
    return out


# ---- the checks of a change --------------------------------------------------------------------------------

def check_text(ch: dict, known: set[str], gate: int, f: Findings, layout: dict | None = None) -> None:
    text, proposal = ch["text"], ch["proposal"] or ""
    defs = defined_ids(text)
    for i, rows in defs.items():
        if len(rows) > 1:
            f.add("SPEC003", "error", f"{i} is defined {len(rows)} times in the change's documents")
    header = "\n".join(proposal.splitlines()[:12])
    if not re.search(r"^\s*Version\s*:\s*\S+", header, re.M) or not re.search(r"^\s*Status\s*:\s*\S+", header, re.M):
        f.add("SPEC006", "error", "proposal.md needs 'Version:' and 'Status:' lines in its header")
    for ref in sorted(ids_in(text)):
        if ref not in known and ref not in defs:
            f.add("SPEC002", "error", f"{ref} is named in the change but defined nowhere (change or living specs)")
    for r in ch["rows"]:
        if r["op"] in ("ADDED", "MODIFIED") and r["id"].startswith(("FR-", "NFR-")):
            if not SOURCE_IDS.search(" ".join(r["cells"][1:])):
                f.add("SPEC005", "error", f"{r['id']} names no source (a Q, ASM, OPEN or G)")
    for i, rows in defs.items():
        if i.startswith("D-") and not SOURCE_IDS.search(" ".join(rows[0][1:])):
            f.add("SPEC005", "error", f"{i} names no source (a Q, ASM, OPEN or G)")
    if gate >= 1 and not any(i.startswith("Q-") for i in defined_ids(proposal)):
        f.add("CLR001", "error", "proposal.md has no recorded question (Q-n rows)")
    if gate >= 2:
        lowered = [l.lower() for l in text.splitlines() if l.lstrip().startswith("#")]
        for h in REQUIRED_HEADINGS:
            if not any(h in l for l in lowered):
                f.add("SPEC008", "error", f"the change has no section '{h}'")
        for i, rows in defs.items():
            if i.startswith(("ASM-", "OPEN-")) and any(c.strip().lower() == "open" for c in rows[0][1:]):
                f.add("SPEC007", "error", f"{i} is still open: confirm it, answer it or withdraw it", "developer")
        if re.search(r"\bTBD\b|\bTODO\b|<<", text):
            f.add("SPEC009", "error", "the change still has TBD, TODO or <<placeholder>> text")
        if not affected_paths(text):
            f.add("SPEC013", "error", "'Affected areas' lists no path")
        if not ch["rows"]:
            f.add("DELTA012", "error", "the change has no delta rows (ADDED, MODIFIED or REMOVED under a capability)")
        layout = layout or {}
        pattern = layout.get("refPattern") or ""
        for i, row in tracing.named_rows(proposal).items():
            if not i.startswith("G-"):
                continue
            refs = links.refs_of(tracing.cell(row, "ref"))
            if layout.get("refRequired") and not refs:
                f.add("REF001", "error", f"{i} has no external reference (refRequired is on): add a ticket or issue in its Ref column")
            for r in refs:
                if pattern and not re.fullmatch(pattern, r):
                    f.add("REF002", "error", f"{i}: reference '{r}' does not match refPattern {pattern}")


def check_deltas(project: Path, ch: dict, name: str, caps: dict[str, dict], f: Findings):
    """Merge the delta into the living specs in memory and check the result. Returns (caps_after, ops, touched by cap)."""
    idx = living.all_ids(caps)
    others = other_added_ids(project, name)
    by_cap: dict[str, list[dict]] = {}
    for r in ch["rows"]:
        if not r["cap"]:
            f.add("DELTA006", "error", f"{r['op']} row {r['id']} is outside a 'Capability: <name>' heading")
            continue
        by_cap.setdefault(r["cap"], []).append(r)
    seen: dict[str, str] = {}
    for cap, rows in by_cap.items():
        for r in rows:
            if r["id"] in seen and seen[r["id"]] != cap:
                f.add("DELTA011", "error", f"{r['id']} is used in two capabilities ({seen[r['id']]}, {cap}); IDs are project-wide")
            seen[r["id"]] = cap
            if r["op"] == "ADDED" and idx.get(r["id"]) not in (None, cap):
                f.add("DELTA001", "error", f"{r['id']} is ADDED, but another capability ({idx[r['id']]}) already uses it")
            if r["op"] == "ADDED" and r["id"] in others:
                f.add("DELTA005", "error", f"{r['id']} is also ADDED by the active change '{others[r['id']]}': take another ID")
    caps_after: dict[str, dict] = {}
    ops: dict[str, str] = {}
    touched: dict[str, set[str]] = {}
    for cap, rows in by_cap.items():
        new, problems, cap_ops = living.merge(caps.get(cap), rows, name, ch["purposes"].get(cap))
        for code, msg in problems:
            f.add(code, "error", f"[{cap}] {msg}")
        if not problems:
            for code, msg in living.validate_state(new):
                f.add(code, "error", f"[{cap}] {msg}")
            caps_after[cap] = new
        else:
            caps_after[cap] = caps.get(cap) or living.empty_cap()
        ops.update(cap_ops)
        touched[cap] = {i for i, o in cap_ops.items() if o in ("ADDED", "MODIFIED")}
    return caps_after, ops, touched


def baseline_file(project: Path, name: str) -> Path:
    return change_dir(project, name) / "baseline.json"


def read_baseline(project: Path, name: str, feat: dict) -> tuple[list[str] | None, list[str]]:
    """The test names that existed before the change and the files that were already dirty. They live in the change folder
    (removed at archive), not in the state file; projects from before 0.1.1 kept them in the state file."""
    try:
        d = json.loads(baseline_file(project, name).read_text(encoding="utf-8"))
        return d.get("tests"), d.get("dirty") or []
    except (OSError, ValueError):
        return feat.get("baselineTests"), feat.get("baselineDirty") or []


def out_of_scope(project: Path, layout: dict, name: str, feat: dict, text: str) -> list[str] | None:
    """Changed files that are neither tests, protected, build folders nor in 'Affected areas'. None: no git."""
    from common import SKIP_DIRS
    files = ledger.changed_files(project)
    if files is None:
        return None
    allowed = affected_paths(text)
    skip = set(read_baseline(project, name, feat)[1])
    bad = []
    for rel in files:
        if rel in skip or rel == ".gitignore" or rel == STATE or rel.startswith(".tracespec/") or classify(rel, layout) in ("protected", "test"):
            continue
        if any(part in SKIP_DIRS for part in rel.split("/")[:-1]):
            continue
        if not any(matches(rel, [a]) for a in allowed):
            bad.append(rel)
    return bad


# ---- the evaluation ----------------------------------------------------------------------------------------

def evaluate(project: Path, layout: dict, problems: list[str], change: str | None, gate: int, run: bool,
             matrix: bool = False, redo_approval: bool = False):
    """All checks for one gate. Returns (findings, stats, context). context is None without a change to read."""
    f = Findings()
    for p in problems:
        f.add("STATE001", "error", p, "developer")
    state = load_state(project)
    name, feat = active_change(state, change)
    if not name or not feat:
        f.add("STATE002", "error", "no active change in .tracespec.json: name one with --change NAME, or start one with "
              "/tracespec propose", "developer")
        return f, {}, None
    ch = load_change(project, name)
    stats: dict = {"change": name, "tier": "small" if feat.get("tier") == "small" else "standard"}
    ctx = {"state": state, "name": name, "feat": feat, "ch": ch, "fdir": ch["dir"]}
    if ch["proposal"] is None:
        if gate >= 1:
            f.add("SPEC000", "error", f".tracespec/changes/{name}/proposal.md does not exist")
        return f, stats, ctx

    caps = living.load_living(project)
    known = set(living.all_ids(caps)) | set(tracing.parse_tasks(ch["tasks_text"]))
    check_text(ch, known, gate, f, layout)
    caps_after, ops, touched = check_deltas(project, ch, name, caps, f)
    ctx.update(caps=caps, caps_after=caps_after, ops=ops, touched=touched)
    fr = sum(1 for r in ch["rows"] if r["op"] != "REMOVED" and r["id"].startswith(("FR-", "NFR-")))
    stats["rules"] = fr
    if feat.get("tier") == "small" and fr > 3:
        f.add("TIER001", "warning", f"the change touches {fr} rules: it has outgrown the small tier. Switch it to "
              "standard (tier in the state file) and split the proposal, design and tasks", "developer")

    approved = dict(feat.get("spec") or {})
    if redo_approval:
        approved["status"] = "draft"
    fp = fingerprint_text(ch["text"])
    if approved.get("status") == "approved":
        if approved.get("fingerprint") != fp:
            now, then = living.behavior_hashes(ch["rows"]), approved.get("rows")
            if then is None or now != then:
                changed = sorted(set(now) ^ set(then or {}) | {k for k in now if k in (then or {}) and now[k] != then[k]})
                f.add("SPEC010", "error", "a delta row changed after approval"
                      + (f" ({', '.join(changed)})" if changed else "") + ": make it a new draft version (next version, "
                      "status Draft) and approve it again", "developer")
            else:
                f.add("SPEC012", "error" if gate >= 5 else "warning", "the approved proposal was edited, but no delta row "
                      "changed: record it with `check.py <project> --amend --note \"...\"`")
        if gate >= 3:
            base = approved.get("baseRows") or {}
            for cap, rows in {c: [r for r in ch["rows"] if r["cap"] == c] for c in touched}.items():
                now_rows = living.living_row_hashes(caps.get(cap) or living.empty_cap())
                for r in rows:
                    if r["op"] in ("MODIFIED", "REMOVED") and base.get(r["id"]) not in (None, now_rows.get(r["id"])):
                        f.add("DELTA010", "error", f"{r['id']} changed in the living spec after this change was approved "
                              "(another change was archived): re-read it, update the delta, approve again", "developer")
    elif gate >= 3:
        f.add("GATE001", "error", "the proposal is not approved yet: tests and code wait for the approval", "developer")
    if re.search(r"^\s*Status\s*:\s*approved", "\n".join(ch["proposal"].splitlines()[:12]), re.I | re.M) \
            and approved.get("status") != "approved" and not redo_approval:
        f.add("SPEC011", "error", "the proposal says Approved but no approval is recorded in the state file", "developer")

    cases = None
    run_info = "not run"
    if gate >= 3 or run or matrix:
        cases, err = run_tests(project, layout)
        if err:
            f.add("TEST003", "error", "the tests could not be run: " + err, "developer")
            cases = None
        else:
            known_failing = set(layout["knownFailing"])
            for c in cases:
                if c["status"] in ("fail", "error") and c["name"] not in known_failing and gate >= 4:
                    f.add("TEST003", "error", f"test fails: {c['name']} -- {c['reason']}")
            run_info = f"{len(cases)} run, {sum(1 for c in cases if c['status'] in ('fail', 'error'))} failing"
    ctx["cases"] = cases
    if gate >= 3 or matrix:
        baseline = read_baseline(project, name, feat)[0]
        effective = tracing.effective_spec(caps_after, design_rows_text(ch["text"]))
        other_ac = {i for cap, st in caps.items() if cap not in caps_after for i in st["criteria"]}
        model = tracing.build(effective, ch["tasks_text"], cases, baseline, ops, other_ac)
        stats.update(tracing.check(model, gate, bool(tracing.parse_tasks(ch["tasks_text"])), baseline is not None, f.add))
        stats["tests"] = len(cases) if cases is not None else None
        ctx["run_info"] = run_info
        ctx["model"] = model
    if gate >= 4:
        bad = out_of_scope(project, layout, name, feat, ch["text"])
        if bad:
            f.add("CHG001", "error", "changed files outside the change's 'Affected areas': " + ", ".join(bad[:8]) +
                  (" ..." if len(bad) > 8 else "") + ". Revert them, or add them to design.md (an amendment if no delta row "
                  "changes)", "developer")
        if bad is None:
            stats["scope"] = "not checked (no git)"
            f.add("CHG002", "warning", "the scope check (changed files against 'Affected areas') was skipped: this is not a "
                  "git repository", "developer")
        task_rows = tracing.parse_tasks(ch["tasks_text"])
        for i, o in sorted(ops.items()):
            if o in ("ADDED", "MODIFIED") and i.startswith(("FR-", "NFR-", "AC-")):
                if not [x for d in task_rows.values() if i in d["serves"] for x in d["files"]]:
                    f.add("LINK001", "warning", f"{i} has no code recorded on its tasks: the audit cannot see code drift for "
                          "it (run --task-start before each task, --task-done after)")
    if gate >= 5:
        overview.check_overview(project, layout, name, f.add)
    ctx["approved"] = approved
    return f, stats, ctx


# ---- detection (step 0) ------------------------------------------------------------------------------------

def detect(project: Path) -> dict:
    has = lambda *names: any((project / n).exists() for n in names)  # noqa: E731
    junit = ".tracespec-junit.xml"
    if has("pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "pytest.ini"):
        runner = ["uv", "run", "pytest"] if has("uv.lock") else ["python", "-m", "pytest"]
        return {"stack": "python", "tests": ["tests/**", "**/test_*.py", "**/*_test.py"], "code": ["**/*.py"],
                "testCmd": runner + ["-q", f"--junitxml={junit}"], "testEnv": {}, "junit": junit}
    if has("package.json"):
        pkg = read(project / "package.json") or ""
        tests = ["**/*.test.*", "**/*.spec.*", "test/**", "tests/**", "__tests__/**"]
        code = ["src/**", "lib/**", "app/**"]
        if "vitest" in pkg:
            return {"stack": "node (vitest)", "tests": tests, "code": code, "testEnv": {}, "junit": junit,
                    "testCmd": ["npx", "vitest", "run", "--reporter=junit", f"--outputFile={junit}"]}
        return {"stack": "node (jest; needs the jest-junit package)", "tests": tests, "code": code, "junit": junit,
                "testCmd": ["npx", "jest", "--reporters=jest-junit"],
                "testEnv": {"JEST_JUNIT_OUTPUT_DIR": ".", "JEST_JUNIT_OUTPUT_NAME": junit}}
    if has("go.mod"):
        return {"stack": "go (needs gotestsum)", "tests": ["**/*_test.go"], "code": ["**/*.go"], "testEnv": {},
                "testCmd": ["gotestsum", "--junitfile", junit, "./..."], "junit": junit}
    if has("pom.xml"):
        return {"stack": "java (maven)", "tests": ["src/test/**"], "code": ["src/main/**"], "testEnv": {},
                "testCmd": ["mvn", "-q", "test"], "junit": "target/surefire-reports/TEST-*.xml"}
    if has("build.gradle", "build.gradle.kts"):
        wrapper = ["gradlew.bat"] if sys.platform == "win32" else ["./gradlew"]
        return {"stack": "java/kotlin (gradle)", "tests": ["src/test/**"], "code": ["src/main/**"], "testEnv": {},
                "testCmd": (wrapper if has("gradlew", "gradlew.bat") else ["gradle"]) + ["test"],
                "junit": "build/test-results/test/*.xml"}
    if any(project.glob("*.sln")) or any(project.glob("**/*.csproj")):
        return {"stack": "dotnet (needs the JunitXml.TestLogger package)", "tests": ["**/*Tests/**", "**/*.Tests/**"],
                "code": ["**/*.cs"], "testEnv": {}, "junit": junit,
                "testCmd": ["dotnet", "test", "--logger", f"junit;LogFilePath={junit}"]}
    return {"stack": "unknown", "tests": [], "code": [], "testCmd": [], "testEnv": {}, "junit": junit}


# ---- commands that write -----------------------------------------------------------------------------------

def cmd_approve(project, layout, problems, kind, args) -> int:
    by, words, change = opt(args, "--by"), opt(args, "--words"), opt(args, "--change")
    if not by or not words:
        print("--approve needs --by \"name\" and --words \"the approver's exact words\"")
        return 2
    gate = 2 if kind == "change" else 5
    f, stats, ctx = evaluate(project, layout, problems, change, gate, run=gate >= 4, redo_approval=(kind == "change"))
    print_findings(f)
    if f.errors or ctx is None or ctx["ch"]["proposal"] is None:
        print(f"NOT APPROVED: {f.errors} error(s) to fix first")
        return 1
    state, name, feat, ch = ctx["state"], ctx["name"], ctx["feat"], ctx["ch"]
    fp, version = fingerprint_text(ch["text"]), doc_version(ch["proposal"])
    log = ch["dir"] / "review_log.md"
    if kind == "change":
        base = {}
        for r in ch["rows"]:
            if r["op"] in ("MODIFIED", "REMOVED") and r["cap"]:
                base[r["id"]] = living.living_row_hashes(ctx["caps"].get(r["cap"]) or living.empty_cap()).get(r["id"])
        feat["spec"] = {"version": version, "status": "approved", "approvedBy": [by], "approvedOn": today(),
                        "fingerprint": fp, "rows": living.behavior_hashes(ch["rows"]), "baseRows": base}
        feat.setdefault("gates", []).append({"step": "approve", "version": version, "approvedBy": [by], "words": words,
                                             "date": today(), "note": ""})
        feat["phase"] = "apply"
        set_status_line(ch["dir"] / "proposal.md", "Approved")
        append_row(log, "| Document | Version |", f"| Proposal | {version} | {words} | {by} | {today()} | approve | {fp} |")
        print(f"APPROVED proposal v{version} by {by}. Next: apply.")
    else:
        code = fingerprint_code(project, layout)
        feat.setdefault("gates", []).append({"step": "build", "version": version, "approvedBy": [by], "words": words,
                                             "date": today(), "note": "code " + code})
        feat["codeFingerprint"] = code
        append_row(log, "| Document | Version |", f"| Build | {version} | {words} | {by} | {today()} | build | {code} |")
        print(f"BUILD APPROVED by {by} (code {code}). Archive it next: check.py <project> --archive --ir-open 0")
    save_state(project, state)
    return 0


def cmd_amend(project, layout, problems, args) -> int:
    """Record an edit of an approved proposal that changed no delta row."""
    note, change = opt(args, "--note"), opt(args, "--change")
    if not note:
        print("--amend needs --note \"what changed and why\"")
        return 2
    state = load_state(project)
    name, feat = active_change(state, change)
    ch = load_change(project, name) if name else None
    approved = (feat or {}).get("spec") or {}
    if not ch or ch["proposal"] is None or approved.get("status") != "approved":
        print("there is no approved proposal to amend")
        return 2
    now, then = living.behavior_hashes(ch["rows"]), approved.get("rows")
    if then is None or now != then:
        print("NOT AN AMENDMENT: a delta row changed. Make a new draft version and approve it again")
        return 1
    fp = fingerprint_text(ch["text"])
    if fp == approved.get("fingerprint"):
        print("nothing to amend: the proposal is as approved")
        return 0
    old, approved["fingerprint"] = approved.get("fingerprint"), fp
    feat.setdefault("amendments", []).append({"date": today(), "note": note, "from": old, "to": fp})
    append_row(ch["dir"] / "review_log.md", "| Date | Proposal version |",
               f"| {today()} | {doc_version(ch['proposal'])} | {note} | {old} | {fp} |")
    save_state(project, state)
    print(f"amendment recorded (proposal v{doc_version(ch['proposal'])} stays approved)")
    return 0


def record_baseline(project: Path, layout: dict, state: dict, change: str | None) -> int:
    """Run the suite before the change and record the names of the existing tests (step 0)."""
    import results
    name, feat = active_change(state, change)
    if not name or not feat:
        print("no active change in .tracespec.json: name one with --change NAME, or start one with /tracespec propose")
        return 2
    cases, err = results.run_tests(project, layout, verbose=True)
    if err:
        print("CANNOT RUN: " + err)
        return 2
    dirty = ledger.changed_files(project) or []
    for old in ("baselineTests", "baselineDirty"):        # moved out of the state file
        feat.pop(old, None)
    d = baseline_file(project, name)
    d.parent.mkdir(parents=True, exist_ok=True)
    d.write_text(json.dumps({"tests": sorted(c["name"] for c in cases), "dirty": dirty}), encoding="utf-8")
    save_state(project, state)
    bad = [c for c in cases if c["status"] in ("fail", "error")]
    print(f"baseline recorded: {len(cases)} tests, {len(bad)} failing, {len(dirty)} uncommitted file(s)")
    for c in bad:
        print(f"FAIL {c['name']} -- {c['reason']}")
    if bad:
        print("Ask the developer whether to put these names into layout.knownFailing.")
    return 0


def cmd_task_start(project, layout, args) -> int:
    """Note the hash of every code symbol before a task, so --task-done can tell which symbols the task touched."""
    tid = opt(args, "--task-start")
    state = load_state(project)
    name, feat = active_change(state, opt(args, "--change"))
    if not name or not tid:
        print("--task-start T-n (with an active change)")
        return 2
    n = current.take_snapshot(project, layout, f"{name}/{tid}")
    print(f"{tid} started ({n} code symbols noted)")
    return 0


def cmd_task_done(project, layout, args) -> int:
    """Tick a task, but only when every criterion it serves has a passing test, and record the symbols it touched."""
    tid = opt(args, "--task-done")
    state = load_state(project)
    name, feat = active_change(state, opt(args, "--change"))
    if not name or not tid:
        print("--task-done T-n (with an active change)")
        return 2
    ch = load_change(project, name)
    tasks = tracing.parse_tasks(ch["tasks_text"])
    if tid not in tasks:
        print(f"{tid} is not in the task list")
        return 2
    removed = {r["id"] for r in ch["rows"] if r["op"] == "REMOVED"}      # a removed criterion has no test any more
    acs = [i for i in tasks[tid]["serves"] if i.startswith("AC-") and i not in removed]
    if acs:
        cases, err = run_tests(project, layout)
        if err:
            print("CANNOT RUN: " + err)
            return 2
        passing = ledger.passing_ids(layout, cases)
        missing = [a for a in acs if a not in passing]
        if missing:
            print(f"NOT DONE: no passing test for {', '.join(missing)}")
            return 1
    key = f"{name}/{tid}"
    touched = current.touched_since(project, layout, key)
    if touched is None:
        print(f"warning: no --task-start for {tid}, so the symbols it touched cannot be recorded (the audit will not see code drift for it)")
        touched = []
    files = sorted({s["path"] for s in touched})
    syms = [s["id"] for s in touched]
    target = ch["dir"] / "tasks.md" if ch["tasks"] is not None else ch["dir"] / "proposal.md"
    new = ledger.tick_task(read(target) or "", tid, files, syms)
    if new is None:
        print(f"{tid} has no checkbox line in {target.name}")
        return 2
    target.write_text(new, encoding="utf-8")
    current.drop_snapshot(project, key)
    print(f"{tid} done" + (f"; {len(syms)} symbol(s) in {len(files)} file(s)" if syms else "; no code symbol recorded"))
    return 0


def cmd_archive(project, layout, problems, args) -> int:
    """Close a change: merge its deltas into the living specs, lock them, and move the folder to the archive."""
    ir = opt(args, "--ir-open")
    if ir is None or not ir.isdigit():
        print("--archive needs --ir-open N: the number of independent-review findings that are still open")
        return 2
    f, stats, ctx = evaluate(project, layout, problems, opt(args, "--change"), 5, run=True)
    print_findings(f)
    if f.errors or ctx is None or ctx["ch"]["proposal"] is None:
        print(f"NOT ARCHIVED: {f.errors} error(s) to fix first")
        return 1
    if int(ir) > 0:
        print(f"NOT ARCHIVED: {ir} review finding(s) still open. Ask the developer to decide, then archive again")
        return 1
    state, name, feat, ch = ctx["state"], ctx["name"], ctx["feat"], ctx["ch"]
    caps, caps_after, touched, cases = ctx["caps"], ctx["caps_after"], ctx["touched"], ctx["cases"] or []
    drift = []
    for cap in caps_after:
        if cap not in caps:
            continue
        text = read(specs_dir(project) / cap / "spec.md") or ""
        base = store.read_baseline(project, cap)
        if base is None:
            drift.append(f"{cap}: no baseline: this spec was not written by an archive")
            continue
        probs = ledger.verify_ledger(project, cap, ledger.spec_hash(text), base["hash"])
        if probs:
            drift.append(f"{cap}: {probs[0]}")
    if drift:
        print("NOT ARCHIVED: a living spec drifted. Revert it or redo the edit through a change:\n  " + "\n  ".join(drift))
        return 1

    syms, files = current.current_symbols(project), current.current_files(project)
    change_nodes, change_edges, cap_of = links.change_graph(project, layout, name, ch, caps_after, syms, files)
    rows_by_cap: dict[str, list[str]] = {}
    for r in ch["rows"]:
        rows_by_cap.setdefault(r["cap"], []).append(f"{r['op']}:{r['id']}")
    written = []
    for cap, state_after in caps_after.items():
        text = living.render_living(cap, state_after)
        old = store.read_baseline(project, cap)
        cn, ce = links.closure(change_nodes, change_edges, cap_of, cap)
        removed = {r["id"] for r in ch["rows"] if r["cap"] == cap and r["op"] == "REMOVED"}
        bn, be = links.assemble_baseline(project, layout, cap, state_after, cn, ce, old, touched.get(cap, set()), removed, syms, files)
        d = specs_dir(project) / cap
        d.mkdir(parents=True, exist_ok=True)
        with open(d / "spec.md", "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        meta = {"capability": cap, "specHash": ledger.spec_hash(text),
                "changes": sorted(set((old or {"meta": {}})["meta"].get("changes", [])) | {name})}
        trace_hash = store.write_baseline(project, cap, bn, be, meta)
        ledger.append_ledger(project, cap, {"event": "archive", "change": name, "date": today(),
                                            "rows": sorted(rows_by_cap.get(cap, [])), "specHash": ledger.spec_hash(text),
                                            "traceHash": trace_hash})
        written.append(cap)
    notes = []
    for cap in sorted(set(caps) - set(caps_after)):      # other capabilities: refresh their baseline if their tests pass
        base = store.read_baseline(project, cap)
        if base and any(current.hash_now(i, syms, files) != h for i, (k, _t, h) in base["nodes"].items() if k in ledger.LEAF):
            ok, msgs = ledger.reconfirm(project, layout, [cap], f"automatic: archive of {name}", cases)
            notes += msgs if ok else [f"{cap}: left as drifted: {msgs[0]}"]
    current.record_run(project, cases, ledger.basis_nodes(project))

    dest = archive_dir(project) / f"{today()}-{name}"
    words = "archived: every criterion passes, no review finding open, no file outside the affected areas"
    feat.setdefault("gates", []).append({"step": "archive", "version": doc_version(ch["proposal"]), "approvedBy": ["automatic"],
                                         "words": words, "date": today(), "note": ""})
    append_row(ch["dir"] / "review_log.md", "| Document | Version |",
               f"| Archive | {doc_version(ch['proposal'])} | {words} | automatic | {today()} | archive | "
               f"{fingerprint_code(project, layout)} |")
    archive_dir(project).mkdir(parents=True, exist_ok=True)
    baseline_file(project, name).unlink(missing_ok=True)
    shutil.move(str(ch["dir"]), str(dest))
    # An archived change keeps a small stub: the approval record is in its review_log.md and the ledger, the rest is not read again.
    approved = feat.get("spec") or {}
    stub = {"title": feat.get("title"), "tier": feat.get("tier", "standard"), "phase": "archived",
            "archivedAs": dest.relative_to(project).as_posix(),
            "approvedBy": approved.get("approvedBy"), "approvedOn": approved.get("approvedOn")}
    feat.clear()
    feat.update({k: v for k, v in stub.items() if v is not None})
    if state.get("activeChange") == name:
        state["activeChange"] = None
    save_state(project, state)
    print(f"ARCHIVED {name}: living specs updated for {', '.join(written)}; moved to {feat['archivedAs']}")
    for n in notes:
        print("  " + n)
    return 0


def cmd_overview(project, layout, problems, args) -> int:
    """Create the developer overview of a change if it is missing. It is written by hand and never rewritten by the tool."""
    name, feat = active_change(load_state(project), opt(args, "--change"))
    if not name or not feat:
        print("no active change: name one with --change NAME, or start one with /tracespec propose")
        return 2
    path, created = overview.create(project, layout, name, feat.get("title") or name)
    rel = path.relative_to(project).as_posix()
    print(f"created {rel}: now write its three sections (purpose, design, key components), briefly" if created
          else f"{rel} already exists: the tool never rewrites it")
    return 0


def cmd_audit(project, layout, problems, args) -> int:
    cases = None
    if "--no-run" not in args:
        cases, err = run_tests(project, layout)
        if err:
            print("CANNOT RUN: " + err + " (the audit needs a test run; use --no-run for the hash checks only)")
            return 2
    found = ledger.audit(project, layout, cases)
    errors = sum(1 for x in found if x["severity"] == "error")
    by_cap: dict[str, list[dict]] = {}
    for x in found:
        by_cap.setdefault(x["capability"], []).append(x)
    for cap in sorted(by_cap):
        print(f"[{cap}]")
        for x in by_cap[cap]:
            print(f"  {x['code']} {x['severity']} {x['message']}")
    caps = living.load_living(project)
    print(f"audit: {len(caps)} capabilit{'y' if len(caps) == 1 else 'ies'}, {errors} error(s), "
          f"{len(found) - errors} warning(s)" + (" (tests not run)" if cases is None else ""))
    return 1 if errors else 0


def cmd_reconfirm(project, layout, args) -> int:
    names, note = rest_after(args, "--reconfirm"), opt(args, "--note")
    if not names or not note:
        print("--reconfirm <capability or ID>... --note \"why the behaviour did not change\"")
        return 2
    caps, unknown = ledger.capabilities_for(project, names)
    if unknown:
        print("unknown capability or ID: " + ", ".join(unknown))
        return 2
    cases, err = run_tests(project, layout)
    if err:
        print("CANNOT RUN: " + err)
        return 2
    ok, msgs = ledger.reconfirm(project, layout, caps, note, cases)
    for m in msgs:
        print(m)
    return 0 if ok else 1


# ---- commands that read ------------------------------------------------------------------------------------

def bar(done: int, total: int, width: int = 10) -> str:
    n = round(width * done / total) if total else 0
    return "[" + "#" * n + "-" * (width - n) + "]"


def cmd_list(project) -> int:
    state = load_state(project)
    rows = []
    for name, feat in (state.get("changes") or {}).items():
        ch = load_change(project, name) if feat.get("phase") != "archived" else None
        t = tracing.parse_tasks(ch["tasks_text"]) if ch else {}
        prog = (f"{sum(1 for x in t.values() if x['done'])}/{len(t)} tasks" if t
                else "finished" if feat.get("phase") == "archived" else "no tasks")
        approved = ("approved" if feat.get("phase") == "archived" or (feat.get("spec") or {}).get("status") == "approved"
                    else "draft")
        rows.append((name, feat.get("phase") or "propose", approved, prog, feat.get("tier", "standard")))
    if not rows:
        print("No changes.")
    for r in rows:
        print(f"{r[0]:<28} {r[1]:<9} {r[2]:<9} {r[3]:<14} {r[4]}")
    return 0


def cmd_show(project, args) -> int:
    state = load_state(project)
    name, feat = active_change(state, opt(args, "--show"))
    if not feat:
        print(f"{name}: no such change")
        return 2
    if feat.get("phase") == "archived":
        print(f"{name} is archived: {feat.get('archivedAs')}")
        return 0
    ch = load_change(project, name)
    caps = living.load_living(project)
    print(f"{name}  ({feat.get('phase', 'propose')}, {feat.get('tier', 'standard')}, "
          f"proposal v{doc_version(ch['proposal'] or '')})")
    by_cap: dict[str, list[dict]] = {}
    for r in ch["rows"]:
        by_cap.setdefault(r["cap"] or "(no capability)", []).append(r)
    for cap, rows in by_cap.items():
        print(f"  {cap}")
        for r in rows:
            c = r["cells"]
            text = c[2] if r["id"].startswith("AC-") and len(c) > 2 else (c[1] if len(c) > 1 else "")
            print(f"    {r['op']:<8} {r['id']:<7} {text}")
            if "--diff" in args and r["op"] == "MODIFIED":
                tbl = living.table_of(r["id"])
                old = (caps.get(cap) or living.empty_cap())[tbl].get(r["id"]) if tbl else None
                if old:
                    print(f"      - {old[2] if tbl == 'criteria' else old[1]}")
                    print(f"      + {text}")
    return 0


def cmd_view(project, layout) -> int:
    state = load_state(project)
    print(f"tracespec: {project.name}")
    print("\nActive changes")
    shown = False
    for name, feat in (state.get("changes") or {}).items():
        if feat.get("phase") == "archived":
            continue
        shown = True
        ch = load_change(project, name)
        t = tracing.parse_tasks(ch["tasks_text"])
        done = sum(1 for x in t.values() if x["done"])
        approved = "approved" if (feat.get("spec") or {}).get("status") == "approved" else "draft"
        print(f"  {name:<26} {feat.get('phase', 'propose'):<8} {approved:<9} {bar(done, len(t))} {done}/{len(t)} tasks")
    if not shown:
        print("  none")
    print("\nCapabilities")
    caps = living.load_living(project)
    found = ledger.audit(project, layout, None)
    for cap, st in caps.items():
        errs = [x for x in found if x["capability"] == cap and x["severity"] == "error"]
        status = "ok" if not errs else f"DRIFT ({len(errs)})"
        print(f"  {cap:<26} {len(st['rules'])} rules, {len(st['criteria'])} criteria, "
              f"{len(st['withdrawn'])} withdrawn   {status}")
    if not caps:
        print("  none yet (the first archive creates one)")
    runs = current.run_state(project)
    stale = sorted(a for a, r in runs.items() if r["stale"])
    print(f"\nTest results: {len(runs)} criteria recorded, {len(stale)} stale"
          + (f" ({', '.join(stale[:8])})" if stale else ""))
    print("(hash checks only; run --audit for the full audit with tests)")
    return 0


def cmd_init(folder: Path) -> int:
    """Create .tracespec.json from detect(): the layout a developer would otherwise have to write by hand."""
    if not folder.is_dir():
        print(f"{folder}: not a folder")
        return 2
    existing = find_project(folder)
    if existing is not None:
        print(f"{existing / STATE} already exists" + ("" if existing == folder else f" (this folder is inside that project)")
              + ": nothing changed. `check.py <project> --doctor` checks it")
        return 2
    found = detect(folder)
    layout = {k: found[k] for k in ("tests", "code", "testCmd", "testEnv", "junit")}
    state = {"process": "tracespec", "processVersion": "2.0", "activeChange": None, "changes": {}, "layout": layout}
    write_atomic(folder / STATE, json.dumps(state, indent=2))
    print(f"created {STATE} for a {found['stack']} project")
    print(f"  tests:    {', '.join(layout['tests']) or '(none found)'}")
    print(f"  code:     {', '.join(layout['code']) or '(none found)'}")
    print(f"  test cmd: {' '.join(layout['testCmd']) or '(none found)'}")
    if found["stack"] == "unknown":
        print("The stack was not recognised: edit layout in .tracespec.json (tests, code, testCmd, junit; see docs/customization.md).")
    elif "needs" in found["stack"]:
        print(f"Note: {found['stack']}.")
    print("Next: `check.py <folder> --doctor` to check the setup, then /tracespec propose <your request> in Claude Code.")
    return 0


def cmd_next_id(project, args) -> int:
    prefix = opt(args, "--next-id")
    if prefix not in ("FR", "NFR", "AC", "NG"):
        print("--next-id FR | NFR | AC | NG")
        return 2
    used = set(living.all_ids(living.load_living(project)))
    root = changes_dir(project)
    if root.is_dir():
        for d in root.iterdir():
            if d.is_dir() and d.name != "archive":
                used |= {r["id"] for r in load_change(project, d.name)["rows"]}
    nums = [int(i.split("-")[1]) for i in used if i.startswith(prefix + "-")]
    print(f"{prefix}-{max(nums, default=0) + 1}")
    return 0


# ---- the live layer and the query -------------------------------------------------------------------------

def inflight_graphs(project: Path, layout: dict) -> list[tuple]:
    """The graph of every change that is not archived yet: [(name, nodes, edges, cap_of, ops)]."""
    state = load_state(project)
    caps = living.load_living(project)
    syms, files = current.current_symbols(project), current.current_files(project)
    out = []
    for name, feat in (state.get("changes") or {}).items():
        if feat.get("phase") == "archived":
            continue
        ch = load_change(project, name)
        if ch["proposal"] is None:
            continue
        caps_after, ops, _touched = check_deltas(project, ch, name, caps, Findings())
        nodes, edges, cap_of = links.change_graph(project, layout, name, ch, caps_after, syms, files)
        out.append((name, nodes, edges, cap_of, ops))
    return out


def cmd_sync(project, layout, args) -> int:
    stats = current.sync(project, layout)
    if "--quiet" not in args:
        print(f"synced: {stats['files']} file(s), {stats['rehashed']} rehashed, {stats['reparsed']} re-resolved, {stats['gone']} gone")
    return 0


def cmd_trace(project, layout, args) -> int:
    flag = "--trace" if "--trace" in args else "--impact"
    target = opt(args, flag)
    if not target or target.startswith("--"):
        print(f"{flag} <target>: a rule or criterion ID, a test name, a task (T-2), a file, file::symbol, file:line, a ticket, a capability")
        return 2
    depth = int_opt(args, "--depth", 8, 1, 50)
    limit = int_opt(args, "--limit", 120, 1, 10000)
    g = graph.build(project, inflight_graphs(project, layout))
    now = graph.Now(project)
    ids = graph.resolve(g, now, target)
    if not ids:
        print(f"nothing found for '{target}' (try a rule or criterion ID, a test name, a task like T-2, a file, file::symbol, "
              "file:line, a ticket or a capability)")
        return 1
    mode = "up" if "--up" in args else "down" if "--down" in args else "story" if "--story" in args else "both"
    lines, shown = graph.render(g, now, ids[:12], mode, depth, limit)
    if "--json" in args:
        print(json.dumps(graph.to_json(g, now, shown, ids[:12]), indent=2))
    elif "--mermaid" in args:
        print(graph.to_mermaid(g, now, shown))
    else:
        print("\n".join(lines))
        if len(ids) > 12:
            print(f"({len(ids)} matches; showing 12. Be more specific.)")
    return 0


def cmd_export(project, layout, problems, args) -> int:
    out = opt(args, "--export")
    if not out or out.startswith("--"):
        print("--export FILE [--living]")
        return 2
    if "--living" in args:
        text = graph.living_matrix(graph.build(project, []), graph.Now(project), living.load_living(project))
    else:
        f, stats, ctx = evaluate(project, layout, problems, opt(args, "--change"), 3, run=True, matrix=True)
        if ctx is None or not ctx.get("model"):
            print_findings(f)
            return 2
        text = tracing.matrix(ctx["model"], ctx["feat"].get("title") or ctx["name"],
                              (ctx.get("approved") or {}).get("version") or "draft", ctx.get("run_info", ""))
    Path(out).write_text(text, encoding="utf-8")
    print(f"wrote {out}")
    return 0


def cmd_install_hooks(project) -> int:
    """Git hooks that keep the live layer current after a commit, merge or checkout. They never block."""
    hooks = project / ".git" / "hooks"
    if not (project / ".git").is_dir():
        print("not a git repository (or a worktree): nothing installed")
        return 2
    hooks.mkdir(exist_ok=True)
    script = Path(__file__).resolve().as_posix()
    block = ("# tracespec:begin\n"
             f'python "{script}" "{project.as_posix()}" --sync --quiet >/dev/null 2>&1 || true\n'
             "# tracespec:end\n")
    for name in ("post-commit", "post-merge", "post-checkout"):
        p = hooks / name
        text = p.read_text(encoding="utf-8") if p.is_file() else "#!/bin/sh\n"
        if "# tracespec:begin" in text:
            text = re.sub(r"# tracespec:begin.*?# tracespec:end\n", lambda m: block, text, flags=re.S)
        else:
            text = text.rstrip("\n") + "\n" + block
        with open(p, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        try:
            os.chmod(p, 0o755)
        except OSError:
            pass
    print("installed git hooks: post-commit, post-merge, post-checkout (each runs --sync, never blocks)")
    print("optional, for Claude Code: add this to .claude/settings.json to refresh after every edit:")
    print(json.dumps({"hooks": {"PostToolUse": [{"matcher": "Edit|Write|MultiEdit", "hooks": [
        {"type": "command", "command": f'python "{script}" "{project.as_posix()}" --sync --quiet'}]}]}}, indent=2))
    return 0


# ---- main --------------------------------------------------------------------------------------------------

def main(argv: list[str]) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass
    if not argv:
        print(__doc__)
        return 2
    if any(a in ("-h", "--help") for a in argv):
        print(__doc__)
        return 0
    if any(a in ("--version", "-V") for a in argv):
        print(read(Path(__file__).resolve().parent.parent / "VERSION") or "unknown", end="")
        return 0
    unknown = [a for a in argv if a.startswith("--") and a not in KNOWN_FLAGS]
    if unknown:
        print(f"unknown option {unknown[0]} (check.py --help lists them)")
        return 2
    if argv[0].startswith("--") and argv[0] not in ("--fingerprint", "--detect", "--doctor"):
        print(f"the project folder comes first: check.py <project> {argv[0]} ...")
        return 2
    try:
        return run(argv)
    except (StateError, UsageError) as e:
        print(e)
        return 2


def run(argv: list[str]) -> int:
    if argv[0] == "--fingerprint" and len(argv) == 2:
        text = read(Path(argv[1]))
        if text is None:
            print(f"cannot read {argv[1]}")
            return 2
        print(fingerprint_text(text))
        return 0
    if argv[0] == "--detect" and len(argv) == 2:
        print(json.dumps(detect(Path(argv[1]).resolve()), indent=2))
        return 0

    if "--init" in argv:
        return cmd_init(Path(argv[0]).resolve())
    if "--doctor" in argv:
        import doctor
        start = Path.cwd() if argv[0] == "--doctor" else Path(argv[0])
        code, text = doctor.report(doctor.doctor(find_project(start), run="--no-run" not in argv))
        print(text)
        return code

    project = find_project(argv[0])
    if project is None:
        print(f"{argv[0]}: no {STATE} in this folder or above it (check.py <folder> --init sets one up)")
        return 2
    args = argv[1:]
    layout, problems = layout_of(project)
    if "--fingerprint" in args and args[args.index("--fingerprint") + 1:] == ["code"]:
        print(fingerprint_code(project, layout))
        return 0
    try:
        current.sync(project, layout)          # the live layer follows the working tree on every command
    except Exception:                                # a broken cache must never stop a command
        pass
    change = opt(args, "--change")
    if "--baseline" in args:
        return record_baseline(project, layout, load_state(project), change)
    if "--approve" in args:
        kind = {"spec": "change"}.get(opt(args, "--approve"), opt(args, "--approve"))
        if kind not in ("change", "build"):
            print("--approve change | build")
            return 2
        return cmd_approve(project, layout, problems, kind, args)
    for flag, fn in (("--archive", cmd_archive), ("--amend", cmd_amend)):
        if flag in args:
            return fn(project, layout, problems, args)
    if "--overview" in args:
        return cmd_overview(project, layout, problems, args)
    if "--audit" in args:
        return cmd_audit(project, layout, problems, args)
    if "--reconfirm" in args:
        return cmd_reconfirm(project, layout, args)
    if "--task-start" in args:
        return cmd_task_start(project, layout, args)
    if "--task-done" in args:
        return cmd_task_done(project, layout, args)
    if "--list" in args:
        return cmd_list(project)
    if "--show" in args:
        return cmd_show(project, args)
    if "--view" in args:
        return cmd_view(project, layout)
    if "--trace" in args or "--impact" in args:
        return cmd_trace(project, layout, args)
    if "--export" in args:
        return cmd_export(project, layout, problems, args)
    if "--sync" in args:
        return cmd_sync(project, layout, args)
    if "--install-hooks" in args:
        return cmd_install_hooks(project)
    if "--next-id" in args:
        return cmd_next_id(project, args)

    gate = int_opt(args, "--gate", 0, 0, 5)
    f, stats, ctx = evaluate(project, layout, problems, change, gate, run="--run" in args or gate >= 4,
                             matrix="--matrix" in args)
    rc = finish(project, f, stats, gate)
    if "--matrix" in args and ctx and ctx.get("model"):
        print(tracing.matrix(ctx["model"], ctx["feat"].get("title") or ctx["name"],
                             (ctx.get("approved") or {}).get("version") or "draft", ctx.get("run_info", "")))
    return rc


def finish(project: Path, f: Findings, stats: dict, gate: int) -> int:
    print_findings(f)
    report = {"gate": gate, "errors": f.errors, "stats": stats, "findings": f.items}
    try:
        (project / ".tracespec-check.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    except OSError:
        pass
    print(f"{f.errors} error(s)" + (f"; {json.dumps(stats)}" if stats else ""))
    return 1 if f.errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

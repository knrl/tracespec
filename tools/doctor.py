"""The checks behind `check.py --doctor`: is this machine, and this project, ready to use TraceSpec?

Each check returns a (level, message) pair: "ok", "warn" (works, but look at it) or "FAIL" (it will not work). Nothing here changes
a project (the local cache folder may be created); the one test run is optional (`--no-run`). Standard library only.
"""
from __future__ import annotations

import json
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402
import results  # noqa: E402
import store  # noqa: E402

AGENTS = ("tracespec-coder", "tracespec-test-writer")
MIN_PYTHON = (3, 10)
Check = tuple[str, str]


def default_agents_dir() -> Path:
    return Path.home() / ".claude" / "agents"


def machine_checks() -> list[Check]:
    out: list[Check] = []
    v = sys.version_info
    out.append(("ok" if v >= MIN_PYTHON else "FAIL", f"Python {v.major}.{v.minor}.{v.micro}" +
                ("" if v >= MIN_PYTHON else f": TraceSpec needs {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer")))
    out.append(("ok", "git found") if shutil.which("git") else
               ("warn", "git not found: the scope check (CHG001) and the git hooks are off. Everything else works"))
    out.append(("ok", "universal-ctags found (symbols for languages other than Python)") if shutil.which("ctags") else
               ("ok", "universal-ctags not installed (optional: other languages use indentation regions)"))
    return out


def hook_command(agent_text: str) -> list[str] | None:
    """The guard hook's command line from an agent file, as a list of arguments."""
    m = re.search(r'^\s*command:\s*"(.*)"\s*$', agent_text, re.M)
    if not m:
        return None
    try:
        return shlex.split(m.group(1).replace('\\"', '"'))
    except ValueError:
        return None


def agent_checks(agents_dir: Path, project: Path | None, layout: dict | None) -> list[Check]:
    out: list[Check] = []
    for name in AGENTS:
        path = agents_dir / f"{name}.md"
        if not path.is_file():
            out.append(("FAIL", f"agent {name} is not installed in {agents_dir}: run `python install.py` from the TraceSpec "
                                "repository, then restart Claude Code"))
            continue
        cmd = hook_command(path.read_text(encoding="utf-8", errors="replace"))
        if not cmd or len(cmd) < 3 or "guard.py" not in cmd[1]:
            out.append(("FAIL", f"agent {name} has no guard hook: without it the agents can see each other's work. "
                                "Run `python install.py` again"))
            continue
        python, guard, role = cmd[0], Path(cmd[1]), cmd[2]
        if not (Path(python).is_file() or shutil.which(python)):
            out.append(("FAIL", f"agent {name}: the hook's Python ({python}) does not exist, so the guard cannot run and nothing is "
                                "isolated. Run `python install.py` again with the Python you use"))
            continue
        if not guard.is_file():
            out.append(("FAIL", f"agent {name}: the hook script {guard} does not exist. Run `python install.py` again"))
            continue
        verdict = smoke_test(python, guard, role, project, layout)
        out.append(verdict if verdict else ("ok", f"agent {name} installed, its guard hook starts"))
    return out


def smoke_test(python: str, guard: Path, role: str, project: Path | None, layout: dict | None) -> Check | None:
    """Ask the real hook to read a file that must be hidden from this role. None when the project gives nothing to test with."""
    if project is None or layout is None:
        return None
    globs = layout["tests"] if role == "coder" else layout["code"]
    prefix = next((p for p in (common.literal_prefix(g) for g in globs) if p), None)
    if prefix is None:
        return None
    event = {"cwd": str(project), "tool_name": "Read", "tool_input": {"file_path": str(project / prefix / "probe.txt")}}
    try:
        p = subprocess.run([python, str(guard), role], input=json.dumps(event), capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired) as e:
        return ("FAIL", f"the {role} guard hook could not run: {e}")
    if '"deny"' not in p.stdout:
        return ("FAIL", f"the {role} guard hook let a read of {prefix}/ through (exit {p.returncode}): the isolation does not work. "
                        f"{p.stderr.strip()[-200:]}")
    return None


def project_checks(project: Path, run: bool) -> list[Check]:
    out: list[Check] = []
    try:
        common.load_state(project)
    except common.StateError as e:
        return [("FAIL", str(e))]
    layout, problems = common.layout_of(project)
    out.append(("ok", f"project: {project}"))
    out += [("warn", p) for p in problems]
    if not layout["tests"] or not layout["code"]:
        out.append(("warn", "layout.tests or layout.code is empty: the agents cannot be kept apart. Fill them in .tracespec.json"))
    cmd = layout["testCmd"]
    if not cmd:
        out.append(("FAIL", "layout.testCmd is empty: set the command that runs your tests and writes JUnit XML"))
        return out
    if not (shutil.which(cmd[0]) or (project / cmd[0]).is_file()):
        out.append(("FAIL", f"the test command's program '{cmd[0]}' was not found on PATH"))
        return out
    try:
        with store.cache(project):
            pass
        out.append(("ok", "the local cache (.tracespec/cache) is writable"))
    except Exception as e:                                   # noqa: BLE001
        out.append(("FAIL", f"the local cache cannot be used: {e}"))
    if not run:
        out.append(("ok", f"test command: {' '.join(cmd)} (not run: --no-run)"))
        return out
    cases, err = results.run_tests(project, layout, verbose=True)
    if err:
        out.append(("FAIL", f"the test command does not work: {err}"))
        return out
    bad = [c for c in cases if c["status"] in ("fail", "error")]
    if not cases:
        out.append(("warn", "the test command ran but found no tests"))
    elif bad:
        out.append(("warn", f"the test command works: {len(cases)} tests, {len(bad)} failing now. Failing tests are recorded by "
                            "--baseline and do not block a change, but fix them when you can"))
    else:
        out.append(("ok", f"the test command works: {len(cases)} tests, all passing, JUnit report read"))
    return out


def doctor(project: Path | None, agents_dir: Path | None = None, run: bool = True) -> list[Check]:
    try:
        layout = common.layout_of(project)[0] if project is not None else None
    except common.StateError:
        layout = None                                        # project_checks reports it
    checks = machine_checks()
    if project is None:
        checks.append(("warn", "no .tracespec.json here or above: run `check.py <folder> --init` to set up a project"))
    else:
        checks += project_checks(project, run)
    checks += agent_checks(agents_dir or default_agents_dir(), project, layout)
    return checks


def report(checks: list[Check]) -> tuple[int, str]:
    lines = [f"[{level:<4}] {msg}" for level, msg in checks]
    fails = sum(1 for level, _ in checks if level == "FAIL")
    warns = sum(1 for level, _ in checks if level == "warn")
    lines.append(f"doctor: {fails} problem(s), {warns} warning(s)" + ("" if fails else ". Ready."))
    return (1 if fails else 0), "\n".join(lines)

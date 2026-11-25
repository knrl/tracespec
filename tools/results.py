#!/usr/bin/env python3
"""Run a tracespec project's tests and report only what the build agents may see.

    python results.py <project>            all tests
    python results.py <project> AC-12 FR-3 only tests whose name carries one of these IDs

The command is layout.testCmd in .tracespec.json; it must write JUnit XML to layout.junit (a file or a glob).
For each test: its name, the spec IDs in the name (AC-3, AC_3 and AC3 all count), pass / fail / error / skip, and
the first line of the reason (cut to 200 characters). Never the test code, never a traceback, never the code under
test, and the command's own output is thrown away.
Exit codes: 0 all selected tests pass, 1 some fail (or a requested ID has no test), 2 the tests could not be run.
"""
from __future__ import annotations

import glob
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import find_project, layout_of, test_ids  # noqa: E402

TIMEOUT = 900


def first_line(text: str | None) -> str:
    text = (text or "").strip()
    line = text.splitlines()[0].strip() if text else ""
    return line if len(line) <= 200 else line[:197] + "..."


def parse_junit(files: list[Path]) -> list[dict]:
    cases = []
    for f in files:
        root = ET.parse(f).getroot()
        for tc in root.iter("testcase"):
            name = tc.get("name") or ""
            classname = (tc.get("classname") or "").split(".")[-1]
            label = f"{classname}::{name}" if classname else name
            status, reason = "pass", ""
            for child in tc:
                if child.tag == "failure":
                    status, reason = "fail", first_line(child.get("message") or child.text)
                elif child.tag == "error":
                    status, reason = "error", first_line(child.get("message") or child.text)
                elif child.tag == "skipped":
                    status, reason = "skip", first_line(child.get("message"))
            cases.append({"name": label, "ids": test_ids(label), "status": status, "reason": reason})
    return cases


def run_tests(project: Path, layout: dict, verbose: bool = False) -> tuple[list[dict], str | None]:
    """Run the suite; (cases, None) or ([], why it could not be run). verbose adds the last lines of the command's error
    output to that reason: for the coordinator only, since it can contain test or code text."""
    cmd = layout["testCmd"]
    if not cmd:
        return [], "layout.testCmd is empty in .tracespec.json: discovery (propose) must set the test command"
    pattern = str(project / layout["junit"])
    for old in glob.glob(pattern, recursive=True):
        try:
            os.remove(old)
        except OSError:
            pass
    env = dict(os.environ, **{k: str(v) for k, v in layout["testEnv"].items()})
    try:
        ran = subprocess.run(cmd, cwd=project, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
                             errors="replace", timeout=TIMEOUT)
    except FileNotFoundError:
        return [], f"the test command '{cmd[0]}' was not found"
    except subprocess.TimeoutExpired:
        return [], f"the test command ran longer than {TIMEOUT} seconds"
    files = [Path(p) for p in glob.glob(pattern, recursive=True)]
    if not files:
        tail = " | ".join((ran.stderr or "").strip().splitlines()[-5:]) if verbose else ""
        why = f" Its last error output: {tail}" if tail else " Run it yourself in the project folder to see why."
        return [], (f"the test command wrote no JUnit file at {layout['junit']}: it may have failed before running any "
                    f"test. Command: {' '.join(cmd)}." + why)
    try:
        cases = parse_junit(files)
    except ET.ParseError as e:
        return [], f"the JUnit file could not be read: {e}"
    finally:
        for f in files:                      # the report holds test source and tracebacks: no agent may read it afterwards
            try:
                f.unlink()
            except OSError:
                pass
    return cases, None


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    project = find_project(sys.argv[1])
    if project is None:
        print(f"{sys.argv[1]}: no .tracespec.json found in this folder or above it")
        return 2
    layout, _ = layout_of(project)
    wanted = [a for a in sys.argv[2:]]
    cases, err = run_tests(project, layout)
    if err:
        print("CANNOT RUN: " + err)
        return 2
    selected = [c for c in cases if not wanted or any(w in c["ids"] for w in wanted)]
    for c in selected:
        ids = ", ".join(c["ids"]) or "-"
        line = f"{c['status'].upper():5} [{ids}] {c['name']}"
        if c["reason"] and c["status"] != "pass":
            line += f" -- {c['reason']}"
        print(line)
    missing = [w for w in wanted if not any(w in c["ids"] for c in cases)]
    for w in missing:
        print(f"NO TEST for {w}")
    n = {s: sum(1 for c in selected if c["status"] == s) for s in ("pass", "fail", "error", "skip")}
    print(f"{n['pass']} passed, {n['fail']} failed, {n['error']} error, {n['skip']} skipped"
          + (f" ({len(cases)} tests in all)" if wanted else ""))
    return 0 if not (n["fail"] or n["error"] or missing) and selected else 1


if __name__ == "__main__":
    sys.exit(main())

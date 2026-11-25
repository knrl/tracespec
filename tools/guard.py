#!/usr/bin/env python3
"""PreToolUse hook for the two build agents of tracespec. Standard library only.

    python guard.py coder     the coding agent: never sees the tests; may write anywhere except tests and protected paths
    python guard.py tester    the test agent:   never sees the code; writes only the tests

The project is the nearest folder above the path in use that holds .tracespec.json (or above the session's
folder). Which paths are tests, code and protected comes from its `layout` (globs, see common.py). A path that
matches both tests and code counts as a test.

Both agents: no search that could cover the hidden paths, no recursive listing, and the tests run only through
results.py (never the test runner itself, check.py or the configured test command).
Reads the hook event (JSON) on stdin and prints a deny decision, or nothing to allow.

This is a guard against mistakes, not against an adversary: a shell command can always be written in a way no
pattern catches. The agents' instructions say the same rules; the guard makes an honest slip fail loudly.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import classify, find_project, inside, layout_of, literal_prefix  # noqa: E402

ROLES = ("coder", "tester")
READ_TOOLS = {"Read", "NotebookRead"}
WRITE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
SEARCH_TOOLS = {"Grep", "Glob"}
SHELL_TOOLS = {"Bash", "PowerShell"}
# running tests directly would show test or code text in tracebacks; results.py shows one line per test
DIRECT_TEST_RUN = re.compile(
    r"\b(pytest|py\.test|unittest|nose2?|tox|jest|vitest|mocha|rspec|phpunit|gotestsum)\b"
    r"|\b(npm|yarn|pnpm|bun)\s+(run\s+)?test\b|\bgo\s+test\b|\bdotnet\s+test\b|\bcargo\s+test\b"
    r"|\bmvn\b|\bgradlew?\b|check\.py")
RECURSIVE = re.compile(
    r"\b(grep|egrep|fgrep)\b[^|;&]*\s-\w*[rR]|\brg\b|\bfind\b|\btree\b|\bls\b[^|;&]*-\w*R"
    r"|Get-ChildItem[^|;&]*-Recurse|\bdir\b[^|;&]*/s|\bgci\b[^|;&]*-r")


def deny(reason: str) -> None:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                             "permissionDecision": "deny",
                                             "permissionDecisionReason": reason}}))
    sys.exit(0)


def locate(cwd: Path, p: str) -> tuple[Path | None, str | None]:
    """The project a path belongs to and the path relative to it (forward slashes, '.' for the project itself)."""
    if not p:
        return None, None
    path = Path(p)
    if not path.is_absolute():
        path = cwd / path
    path = path.resolve()
    project = find_project(path) or find_project(cwd.resolve())
    if project is None:
        return None, None
    try:
        return project, path.relative_to(project).as_posix() or "."
    except ValueError:
        return None, None


def segment_pattern(folder: str) -> re.Pattern:
    """Matches the folder's last name as a whole path segment ('tests', not 'run_tests.py')."""
    name = re.escape(folder.split("/")[-1])
    return re.compile(r"(^|[\s\\/'\"=:(,*<>|;&`{\[@])" + name + r"([\s\\/'\"),*<>|;&`}\]]|$)", re.IGNORECASE)


# git subcommands that print file contents (a diff of an uncommitted test, a grep through the tests) or restore files
GIT_SHOWS_CONTENT = re.compile(
    r"\bgit\b[^|;&]*?\s(diff|difftool|show|grep|stash|blame|cat-file|archive|restore|checkout)\b"
    r"|\bgit\b[^|;&]*?\slog\b[^|;&]*(\s-\w*[pu]\b|--(patch|stat|name|raw|summary|cc))")


def shell_paths(cmd: str) -> list[str]:
    """The words of a shell command that could be paths (quotes and the value of --opt=value taken off)."""
    out = []
    for word in re.split(r"[\s;|&<>()`]+", cmd):
        word = word.split("=")[-1].strip("'\"")
        if word and not word.startswith("-"):
            out.append(word)
    return out


class Rules:
    """What one role may see and change in one project."""

    def __init__(self, role: str, project: Path | None, cwd: Path):
        self.role = role
        self.project = project
        self.layout, _ = layout_of(project or cwd)
        lay = self.layout
        self.hidden_globs = lay["tests"] if role == "coder" else lay["code"]
        self.hidden_kind = "test" if role == "coder" else "code"
        self.prefixes = [literal_prefix(g) for g in self.hidden_globs]
        shown = ", ".join(self.hidden_globs)
        if role == "coder":
            self.why = (f"The coding agent never sees the tests (tracespec): {shown} are hidden. "
                        "Build from the spec; see which examples fail with results.py.")
        else:
            self.why = (f"The test agent never sees the code (tracespec): {shown} are hidden. "
                        "Write the tests from the spec: its 'Existing code facts' and 'Interfaces the tests call'.")

    def hidden_at(self, r: str | None) -> bool:
        return classify(r, self.layout) == self.hidden_kind

    def covers_hidden(self, r: str) -> bool:
        """A search in folder r could reach hidden files."""
        return any(p == "" or r == "." or inside(p, r) for p in self.prefixes)

    def write_denied(self, r: str) -> str | None:
        kind = classify(r, self.layout)
        if self.role == "tester":
            if kind != "test":
                return (f"You may only change test files ({', '.join(self.layout['tests'])}), not {r}. The code, the "
                        "spec and the settings change through the coding agent, the main agent and the people who approve them.")
            return None
        if kind == "protected":
            return (f"{r} is protected: you may not change {', '.join(self.layout['protected'])}. The spec, the state file "
                    "and the project documents change through the main agent and the people who approve them.")
        return None


def main() -> None:
    role = sys.argv[1] if len(sys.argv) > 1 else ""
    if role not in ROLES:
        deny(f"guard.py needs a role: {', '.join(ROLES)}")
    try:
        event = json.load(sys.stdin)
        cwd = Path(event.get("cwd") or os.getcwd())
        tool = str(event.get("tool_name", ""))
        data = event.get("tool_input") or {}
        if not isinstance(data, dict):
            raise ValueError("tool_input is not an object")
    except (ValueError, AttributeError, OSError):          # a hook that cannot read its event must not let the call through
        deny("The guard could not read the tool call (tracespec), so it was stopped. Try again; if it keeps happening, "
             "tell the developer.")

    if tool in READ_TOOLS | WRITE_TOOLS:
        project, r = locate(cwd, str(data.get("file_path") or data.get("notebook_path") or ""))
        if project is None:
            sys.exit(0)
        rules = Rules(role, project, cwd)
        if rules.hidden_at(r):
            deny(f"{r} is hidden from you. {rules.why}")
        if tool in WRITE_TOOLS:
            reason = rules.write_denied(r)
            if reason:
                deny(reason)
        sys.exit(0)

    if tool in SEARCH_TOOLS:
        target = str(data.get("path") or "")
        if target:
            project, r = locate(cwd, target)
        else:
            project, r = find_project(cwd.resolve()), "."
        if project is not None:
            rules = Rules(role, project, cwd)
            if rules.hidden_at(r) or rules.covers_hidden(r or "."):
                if "" in rules.prefixes:
                    deny("Searching is off: the hidden files sit next to other files, so no search can leave them out. "
                         f"Read the files you need by name. {rules.why}")
                deny(f"Searching {r} would cover the hidden files. Give path= a folder that contains none of them, "
                     f"for example docs/ or the folder you write in. {rules.why}")
            pattern = str(data.get("pattern") or "") + " " + str(data.get("glob") or "")
            path_glob = str(data.get("pattern") or "") if tool == "Glob" else str(data.get("glob") or "")   # Grep's pattern is text
            if re.search(r"(^|[\s/\\])\.\.([\s/\\]|$)|^([/~]|[A-Za-z]:)", path_glob):
                deny("A search pattern may not climb out of the folder (..) or start at the root or the home folder; "
                     f"give the folder in path= and keep the pattern inside it. {rules.why}")
            for p in rules.prefixes:
                if p and segment_pattern(p).search(pattern):
                    deny(f"The search pattern names {p}/. {rules.why}")
        sys.exit(0)

    if tool in SHELL_TOOLS:
        cmd = str(data.get("command") or "")
        project = find_project(cwd.resolve())
        if project is None:                                # a session opened elsewhere: the project is named by an absolute path
            for word in shell_paths(cmd):
                if Path(word).is_absolute() and (project := find_project(Path(word))) is not None:
                    break
        rules = Rules(role, project, cwd)
        for p in rules.prefixes:
            if p and segment_pattern(p).search(cmd):
                deny(f"The command names {p}/. {rules.why}")
        for word in shell_paths(cmd):                      # also catches ../ detours and globs with no folder prefix
            where, rel = locate(cwd, word)
            if where is not None and rules.hidden_at(rel):
                deny(f"The command reads {rel}. {rules.why}")
        if GIT_SHOWS_CONTENT.search(cmd):
            deny("git commands that print file contents (diff, show, grep, log -p, stash, blame, restore, checkout) could show "
                 f"the hidden files. Use git status, or read the files you may see by name. {rules.why}")
        test_cmd = " ".join(rules.layout["testCmd"])
        if DIRECT_TEST_RUN.search(cmd) or (test_cmd and test_cmd in cmd):
            deny("Run the tests only with: python <tracespec skill folder>/tools/results.py <project folder> "
                 "[AC-n ...] (it reports which tests pass or fail, without showing test or code text).")
        if RECURSIVE.search(cmd):
            deny("Recursive listing or searching could show the hidden files. Use the Grep or Glob tool with a path, "
                 f"or name the folder you need. {rules.why}")
        sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    main()

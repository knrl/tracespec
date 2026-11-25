#!/usr/bin/env python3
"""Install TraceSpec for Claude Code.

    python install.py                       skill -> ~/.claude/skills/tracespec, agents -> ~/.claude/agents
    python install.py --claude-dir DIR      use DIR instead of ~/.claude
    python install.py --skills-dir S --agents-dir A

The skill is copied (the folders SKILL.md, process.md, workflows, templates and tools are replaced, so an update leaves no
stale files). If this repository is already cloned to <skills dir>/tracespec, nothing is copied and only the two agents are
written. The agent files in templates/agents contain a {skill_dir} placeholder for the hook; it is replaced by the real path.
Standard library only. Restart Claude Code afterwards: skills and agents are read when a session starts.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ITEMS = ["SKILL.md", "process.md", "workflows", "templates", "tools"]


def install(skills_dir: Path, agents_dir: Path) -> list[str]:
    target = skills_dir / "tracespec"
    done: list[str] = []
    if target.resolve() == HERE:
        done.append(f"skill: already in place at {target}")
    else:
        target.mkdir(parents=True, exist_ok=True)
        for name in ITEMS:
            src, dst = HERE / name, target / name
            if dst.is_dir():
                shutil.rmtree(dst)
            if src.is_dir():
                shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            else:
                shutil.copy2(src, dst)
        done.append(f"skill: copied to {target}")
    agents_dir.mkdir(parents=True, exist_ok=True)
    for tpl in sorted((HERE / "templates" / "agents").glob("*.md")):
        text = tpl.read_text(encoding="utf-8").replace("{skill_dir}", target.resolve().as_posix())
        with open(agents_dir / tpl.name, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        done.append(f"agent: {agents_dir / tpl.name}")
    return done


def main() -> int:
    ap = argparse.ArgumentParser(description="Install TraceSpec for Claude Code.")
    ap.add_argument("--claude-dir", type=Path, default=Path.home() / ".claude")
    ap.add_argument("--skills-dir", type=Path)
    ap.add_argument("--agents-dir", type=Path)
    args = ap.parse_args()
    skills = args.skills_dir or args.claude_dir / "skills"
    agents = args.agents_dir or args.claude_dir / "agents"
    for line in install(skills, agents):
        print(line)
    print("\nRestart Claude Code, then try: /tracespec explore <what you want to change>")
    return 0


if __name__ == "__main__":
    sys.exit(main())

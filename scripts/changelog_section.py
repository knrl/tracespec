#!/usr/bin/env python3
"""Print one version's section of CHANGELOG.md (the text under '## [x.y.z] - date'). Used by the release workflow.

    python scripts/changelog_section.py 0.1.0
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def section(text: str, version: str) -> str | None:
    m = re.search(rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[|^\[[^\]]+\]: |\Z)", text, re.M | re.S)
    return m.group(1).strip() if m else None


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__)
        return 2
    body = section((ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), argv[0])
    if not body:
        print(f"CHANGELOG.md has no section for version {argv[0]}", file=sys.stderr)
        return 1
    print(body)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

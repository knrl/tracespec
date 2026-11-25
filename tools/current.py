"""What is true now: the live layer next to the baseline. Standard library only.

`sync` keeps a local cache of every code and test file's hash and symbols. It is incremental: a file whose size and modification
time are unchanged is not even re-read, and symbols are re-resolved only for a file whose content hash changed. It runs at the
start of every check.py command, so the current layer follows the working tree without a daemon. Test runs are not started
here (they are slow): a recorded result is marked stale instead, as soon as a file it depended on changes.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import time
from pathlib import Path

import store
import symbols
from common import classify, file_hash, walk_files


# A file whose modification time is within this window of the moment it was cached may have been written again, with the same
# size, in the same clock tick: the file system cannot tell. Git calls such an entry "racily clean" and re-reads it; so do we.
RACY_NS = 2_000_000_000


def sync(project: Path, layout: dict) -> dict:
    """Bring the cache up to date with the working tree. Returns counts."""
    stats = {"files": 0, "rehashed": 0, "reparsed": 0, "gone": 0}
    with store.cache(project) as c:
        known = {p: (m, s, h, seen) for p, m, s, h, seen in c.execute("SELECT path, mtime_ns, size, hash, seen_ns FROM filecache")}
        parsed = {p: fh for p, fh in c.execute("SELECT path, filehash FROM symcache")}
        seen = set()
        for rel in walk_files(project):
            if classify(rel, layout) not in ("code", "test"):
                continue
            path = project / rel
            try:
                st = path.stat()
            except OSError:
                continue
            row = known.get(rel)
            trusted = (row and row[0] == st.st_mtime_ns and row[1] == st.st_size and row[3] is not None
                       and st.st_mtime_ns < row[3] - RACY_NS)
            if trusted:
                h = row[2]
            else:
                h = file_hash(path)
                if h is None:
                    continue
                c.execute("INSERT OR REPLACE INTO filecache VALUES (?, ?, ?, ?, ?)", (rel, st.st_mtime_ns, st.st_size, h, time.time_ns()))
                stats["rehashed"] += 1
            seen.add(rel)
            stats["files"] += 1
            if parsed.get(rel) != h:
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                res = ({"resolver": "binary", "symbols": []} if chr(0) in text       # a binary file has no symbols to link
                       else symbols.resolve(project, rel, text))
                c.execute("INSERT OR REPLACE INTO symcache VALUES (?, ?, ?, ?)", (rel, h, res["resolver"], json.dumps(res["symbols"])))
                stats["reparsed"] += 1
        for rel in set(known) | set(parsed):
            if rel not in seen:
                c.execute("DELETE FROM filecache WHERE path=?", (rel,))
                c.execute("DELETE FROM symcache WHERE path=?", (rel,))
                stats["gone"] += 1
    return stats


def current_symbols(project: Path) -> dict[str, dict]:
    """symbol id -> {path, name, kind, start, end, hash}, for every code and test file (after a sync)."""
    out: dict[str, dict] = {}
    with store.cache(project) as c:
        for path, blob in c.execute("SELECT path, symbols FROM symcache"):
            for s in json.loads(blob):
                out[s["id"]] = dict(s, path=path)
    return out


def current_files(project: Path) -> dict[str, str]:
    with store.cache(project) as c:
        return {p: h for p, h in c.execute("SELECT path, hash FROM filecache")}


WHOLE_TREE = "*"      # the basis of a result that no baseline links to code yet: any change to any code or test file counts


def hash_now(node: str, syms: dict, files: dict) -> str | None:
    """The current hash of a symbol id ('path::name'), a file path, or WHOLE_TREE (all of them together)."""
    if node == WHOLE_TREE:
        return hashlib.sha1("|".join(f"{p}:{h}" for p, h in sorted(files.items())).encode()).hexdigest()[:16]
    if "::" in node:
        s = syms.get(node)
        return s["hash"] if s else None
    return files.get(node)


# ---- task snapshots ----------------------------------------------------------------------------------------

def take_snapshot(project: Path, layout: dict, task: str) -> int:
    """Remember the hash of every code symbol before a task. Returns how many."""
    sync(project, layout)
    syms = current_symbols(project)
    rows = [(task, i, s["hash"]) for i, s in syms.items() if classify(s["path"], layout) == "code"]
    with store.cache(project) as c:
        c.execute("DELETE FROM snapshot WHERE task=?", (task,))
        c.executemany("INSERT INTO snapshot VALUES (?, ?, ?)", rows)
    return len(rows)


def touched_since(project: Path, layout: dict, task: str) -> list[dict] | None:
    """Code symbols that are new or whose text changed since the task's snapshot. None if there is no snapshot."""
    with store.cache(project) as c:
        before = {n: h for n, h in c.execute("SELECT node, hash FROM snapshot WHERE task=?", (task,))}
    if not before:
        return None
    sync(project, layout)
    out = []
    for i, s in sorted(current_symbols(project).items()):
        if classify(s["path"], layout) == "code" and before.get(i) != s["hash"]:
            out.append(s)
    return out


def drop_snapshot(project: Path, task: str) -> None:
    with store.cache(project) as c:
        c.execute("DELETE FROM snapshot WHERE task=?", (task,))


# ---- test runs, and when they go stale ---------------------------------------------------------------------

def record_run(project: Path, cases: list[dict], basis: dict[str, list[str]]) -> None:
    """Store the result of a run per acceptance criterion, with the hash of every node it depends on at that moment.
    basis: criterion -> the test and code nodes linked to it in the baseline."""
    syms, files = current_symbols(project), current_files(project)
    by_ac: dict[str, list[dict]] = {}
    for case in cases:
        for i in case["ids"]:
            if i.startswith("AC-"):
                by_ac.setdefault(i, []).append(case)
    now = datetime.datetime.now().isoformat(timespec="seconds")
    with store.cache(project) as c:
        c.execute("DELETE FROM acrun")
        c.execute("DELETE FROM acbasis")
        for ac in sorted(set(by_ac) | set(basis)):
            live = [x for x in by_ac.get(ac, []) if x["status"] != "skip"]
            status = ("NO TEST" if not live else "FAIL" if any(x["status"] in ("fail", "error") for x in live) else "PASS")
            c.execute("INSERT INTO acrun VALUES (?, ?, ?, ?)", (ac, status, json.dumps([x["name"] for x in by_ac.get(ac, [])]), now))
            for node in basis.get(ac) or [WHOLE_TREE]:     # a criterion of a change in flight has no baseline yet
                h = hash_now(node, syms, files)
                if h:
                    c.execute("INSERT OR REPLACE INTO acbasis VALUES (?, ?, ?)", (ac, node, h))


def run_state(project: Path) -> dict[str, dict]:
    """criterion -> {status, at, stale}: stale when a node the result depended on has changed since the run."""
    syms, files = current_symbols(project), current_files(project)
    out: dict[str, dict] = {}
    with store.cache(project) as c:
        for ac, status, at in c.execute("SELECT ac, status, at FROM acrun"):
            out[ac] = {"status": status, "at": at, "stale": False}
        for ac, node, h in c.execute("SELECT ac, node, hash FROM acbasis"):
            if ac in out and hash_now(node, syms, files) != h:
                out[ac]["stale"] = True
    return out

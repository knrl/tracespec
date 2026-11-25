"""The trace store. Standard library only (sqlite3). Binary on purpose: it is read through `check.py --trace`, never by hand.

Two kinds of database:
  .tracespec/specs/<capability>/trace.db   the BASELINE of a capability: the graph of nodes and edges and a hash for every
        row, symbol and file as they were at the last archive or reconfirm. Written only by check.py. Committed.
  .tracespec/cache/current.db              what is true NOW: file and symbol hashes (cached by content), the last test
        results, the task snapshots. Derived and rebuildable; never committed (the cache folder gets its own .gitignore).

Edges are stored child -> parent (the thing above it in the chain ticket > goal > rule > criterion > test/task > code):
  covers (criterion -> rule), source (rule or goal or design -> its goal/question/assumption), ref (goal/question -> external ref),
  verifies (test -> criterion), serves (task -> rule, criterion or design), built_by (symbol or file -> task).
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import sqlite3
from pathlib import Path

from common import INTERNAL, specs_dir

EDGE_KINDS = ("covers", "source", "ref", "verifies", "serves", "built_by")

BASELINE_SCHEMA = """
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE node(id TEXT PRIMARY KEY, kind TEXT NOT NULL, text TEXT, hash TEXT);
CREATE TABLE edge(src TEXT NOT NULL, dst TEXT NOT NULL, kind TEXT NOT NULL, PRIMARY KEY(src, dst, kind));
CREATE INDEX edge_dst ON edge(dst);
"""

CACHE_SCHEMA = """
CREATE TABLE IF NOT EXISTS filecache(path TEXT PRIMARY KEY, mtime_ns INTEGER, size INTEGER, hash TEXT);
CREATE TABLE IF NOT EXISTS symcache(path TEXT PRIMARY KEY, filehash TEXT, resolver TEXT, symbols TEXT);
CREATE TABLE IF NOT EXISTS acrun(ac TEXT PRIMARY KEY, status TEXT, tests TEXT, at TEXT);
CREATE TABLE IF NOT EXISTS acbasis(ac TEXT, node TEXT, hash TEXT, PRIMARY KEY(ac, node));
CREATE TABLE IF NOT EXISTS snapshot(task TEXT, node TEXT, hash TEXT, PRIMARY KEY(task, node));
"""


# ---- baseline ----------------------------------------------------------------------------------------------

def baseline_path(project: Path, cap: str) -> Path:
    return specs_dir(project) / cap / "trace.db"


def canonical_hash(nodes: dict[str, tuple], edges: set[tuple], meta: dict | None = None) -> str:
    """Hash of the content of a baseline, independent of how SQLite laid the file out."""
    h = hashlib.sha256()
    for i in sorted(nodes):
        h.update(json.dumps([i, *nodes[i]], sort_keys=True).encode("utf-8"))
    for e in sorted(edges):
        h.update(json.dumps(list(e)).encode("utf-8"))
    for k in sorted(meta or {}):
        h.update(json.dumps([k, meta[k]]).encode("utf-8"))
    return h.hexdigest()[:16]


def write_baseline(project: Path, cap: str, nodes: dict[str, tuple], edges: set[tuple], meta: dict) -> str:
    """Write a capability's baseline (nodes: id -> (kind, text, hash); edges: (src, dst, kind)). Returns its canonical hash."""
    path = baseline_path(project, cap)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".db.tmp")
    if tmp.exists():
        tmp.unlink()
    conn = sqlite3.connect(tmp)
    try:
        conn.executescript(BASELINE_SCHEMA)
        conn.executemany("INSERT INTO meta VALUES (?, ?)", sorted((k, json.dumps(v, sort_keys=True)) for k, v in meta.items()))
        conn.executemany("INSERT INTO node VALUES (?, ?, ?, ?)", sorted((i, *nodes[i]) for i in nodes))
        conn.executemany("INSERT INTO edge VALUES (?, ?, ?)", sorted(edges))
        conn.commit()
    finally:
        conn.close()
    os.replace(tmp, path)
    return canonical_hash(nodes, edges, meta)


def read_baseline(project: Path, cap: str) -> dict | None:
    path = baseline_path(project, cap)
    if not path.is_file():
        return None
    try:
        conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    except sqlite3.Error:
        return None
    try:
        meta = {k: json.loads(v) for k, v in conn.execute("SELECT key, value FROM meta")}
        nodes = {i: (k, t, h) for i, k, t, h in conn.execute("SELECT id, kind, text, hash FROM node")}
        edges = {(s, d, k) for s, d, k in conn.execute("SELECT src, dst, kind FROM edge")}
    except sqlite3.Error:
        return None
    finally:
        conn.close()
    return {"meta": meta, "nodes": nodes, "edges": edges, "hash": canonical_hash(nodes, edges, meta)}


# ---- the current cache -------------------------------------------------------------------------------------

def cache_path(project: Path) -> Path:
    return project / INTERNAL / "cache" / "current.db"


@contextlib.contextmanager
def cache(project: Path):
    """The local cache connection (created on first use, with a .gitignore that keeps it out of version control)."""
    path = cache_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    ignore = path.parent.parent / ".gitignore"
    if not ignore.exists():
        ignore.write_text("cache/\n", encoding="utf-8")
    conn = sqlite3.connect(path)
    try:
        conn.executescript(CACHE_SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()

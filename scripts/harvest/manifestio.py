#!/usr/bin/env python3
"""
Shared manifest / TSV I/O for the harvest pipeline — the single source of truth
for the schema and the on-disk dialect.

Why this module exists: the doctrine ("the manifest is canon, never hand-edit,
never delete rows") is only as strong as the weakest open() call. All manifest
reads/writes must go through read_rows()/write_rows() so that:
  - encoding is always UTF-8 regardless of locale (Windows defaults to cp936 /
    cp1252 and crashes on the first "Ł" in an author name otherwise),
  - writes are atomic (tmp file + os.replace) — a mid-run kill can never
    truncate the canon file,
  - the escape dialect is symmetric between writer and reader (QUOTE_NONE +
    backslash escapes; embedded tabs/backslashes round-trip),
  - the header is validated loudly instead of silently mis-aligning columns.
"""
from __future__ import annotations
import csv, os, sys
from pathlib import Path

SCHEMA_VERSION = 2

# v2 adds `doi` and `code_url`. v1 files (15 columns) are upgraded on read —
# missing fields become empty strings and are written back in v2 order.
HEADERS = ["id","title","authors","venue","year","track","category","arxiv_id",
           "openreview_id","anthology_id","doi","pdf_url","abstract_url",
           "code_url","slug","downloaded","notes"]

V1_HEADERS = ["id","title","authors","venue","year","track","category","arxiv_id",
              "openreview_id","anthology_id","pdf_url","abstract_url","slug",
              "downloaded","notes"]

DIALECT = dict(delimiter="\t", quoting=csv.QUOTE_NONE, escapechar="\\")


def read_rows(path: Path) -> list[dict]:
    """Read a manifest / per-venue TSV. Accepts v1 or v2 headers; always
    returns rows with the full v2 field set (missing fields empty)."""
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.reader(f, **DIALECT)
        try:
            header = next(reader)
        except StopIteration:
            sys.exit(f"{path}: empty file")
        if header == HEADERS:
            cols = HEADERS
        elif header == V1_HEADERS:
            cols = V1_HEADERS
        else:
            sys.exit(f"{path}: header mismatch\n"
                     f"  expected (v{SCHEMA_VERSION}): {HEADERS}\n"
                     f"  or (v1):  {V1_HEADERS}\n"
                     f"  got:      {header}")
        rows: list[dict] = []
        for vals in reader:
            if not any(v.strip() for v in vals):
                continue  # blank / ghost line (e.g. stray \r\r\n from old runs)
            r = dict(zip(cols, vals))
            for h in HEADERS:
                r.setdefault(h, "")
            rows.append(r)
        return rows


def write_rows(path: Path, rows: list[dict]) -> None:
    """Atomically write rows in schema order (tmp file + os.replace — atomic
    on both POSIX and Windows)."""
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HEADERS, **DIALECT)
        w.writeheader()
        for r in rows:
            w.writerow({h: r.get(h, "") for h in HEADERS})
    os.replace(tmp, path)


def pdf_ok(path: Path) -> bool:
    """Cheap PDF integrity check: header magic + %%EOF trailer in the last 1KB.
    Catches truncated downloads without a full parse (stdlib-only). Shared by
    download.py (resume check) and verify.py (audit) so they agree on 'ok'."""
    try:
        if not path.is_file() or path.stat().st_size <= 1024:
            return False
        with path.open("rb") as f:
            head = f.read(8)
            f.seek(-1024, 2)
            tail = f.read()
        return head.startswith(b"%PDF") and b"%%EOF" in tail
    except OSError:
        return False

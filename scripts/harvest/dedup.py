#!/usr/bin/env python3
"""
Merge per-venue TSVs into a corpus master manifest with cross-venue dedup.

Reads every *.tsv in wiki/topics/<corpus>/collection/ (except duplicates.tsv),
merges them, and writes:
  wiki/topics/<corpus>/manifest.tsv               — canonical merged manifest (ids assigned)
  wiki/topics/<corpus>/collection/duplicates.tsv  — non-canonical rows (audit trail)

Canonical selection when the same paper appears in multiple venues:
  1. Archival source first: anthology_id/doi present > openreview_id >
     arXiv-only > no identifier. The camera-ready/archival version is the
     version of record (workshop 2025 then main conference 2026 → the 2026
     camera-ready wins, not the earliest sighting).
  2. Tie → latest year.
  3. Tie → venue priority (see --venues or priorities.json), then track
     priority: oral > spotlight > main > poster > findings >
     datasets-benchmarks > accepted.

Dedup signals (a pair is a duplicate if ANY of these holds):
  - Same arxiv_id (version suffix vN ignored) or same DOI.
  - Exact normalized-title match AND author check (first-author lastname match
    OR ≥50% author-set overlap).
  - Same first-author lastname AND title token-Jaccard ≥ 0.8 AND author check
    (catches preprint → camera-ready title edits).

Re-run safe: if manifest.tsv already exists it is read first; rows that still
resolve to the same (venue, year, slug) keep their id / downloaded / notes,
and new rows get ids that CONTINUE each venue-year sequence — existing ids are
never renumbered (entity pages and error logs cite them). A row whose
canonical venue-year changed (e.g. a new archival version now wins) is treated
as new; verify.py will flag the old on-disk files as orphans.

Venue priority: pass --venues "ACL,EMNLP,ICLR,ICML,NeurIPS" (highest first), or
drop a JSON list into wiki/topics/<corpus>/collection/priorities.json.
Unlisted venues rank below listed ones, alphabetically.

Usage:
  dedup.py --corpus <name> [--venues "A,B,C"] [--dry-run]
"""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path
from collections import defaultdict

from manifestio import read_rows, write_rows

ROOT = Path(__file__).resolve().parent.parent.parent

TRACK_PRIORITY = {"oral":0, "spotlight":1, "main":2, "poster":3,
                  "findings":4, "datasets-benchmarks":5, "accepted":6, "":7}

# ---------- normalization helpers (pure functions; unit-tested in tests/) ----------

def norm_title(t: str) -> str:
    t = t.lower()
    t = re.sub(r"[^a-z0-9\s]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def title_tokens(t: str) -> set[str]:
    return set(norm_title(t).split())

def norm_arxiv(a: str) -> str:
    return re.sub(r"v\d+$", "", a.strip().lower())

def norm_doi(d: str) -> str:
    d = d.strip().lower()
    for pre in ("https://doi.org/", "http://doi.org/", "doi:"):
        if d.startswith(pre):
            d = d[len(pre):]
    return d

def lastnames(authors: str) -> set[str]:
    """Extract lowercase first words of each `Last, First` segment."""
    out = set()
    for seg in authors.split(";"):
        seg = seg.strip()
        if not seg: continue
        first = seg.split(",")[0].strip().lower()
        first = re.sub(r"[^a-z]+", "", first)
        if first:
            out.add(first)
    return out

def first_author_lastname(authors: str) -> str:
    s = authors.split(";")[0].strip()
    if not s: return ""
    return re.sub(r"[^a-z]+", "", s.split(",")[0].strip().lower())

def author_overlap_ok(a: str, b: str) -> bool:
    la, lb = lastnames(a), lastnames(b)
    if not la or not lb: return False
    fa, fb = first_author_lastname(a), first_author_lastname(b)
    if fa and fb and fa == fb:
        return True
    overlap = len(la & lb)
    smaller = min(len(la), len(lb))
    return smaller > 0 and overlap / smaller >= 0.5

def source_rank(row: dict) -> int:
    """Archival version of record first (camera-ready beats preprint)."""
    if row.get("anthology_id") or row.get("doi"): return 0
    if row.get("openreview_id"): return 1
    if row.get("arxiv_id"): return 2
    return 3

# ---------- clustering ----------

def cluster_indices(all_rows: list[dict]) -> list[list[int]]:
    """Union-find over the three dedup signals (see module docstring)."""
    n = len(all_rows)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    # Signal 1: shared identifier — unconditional match.
    by_id: dict[tuple, list[int]] = defaultdict(list)
    for i, r in enumerate(all_rows):
        if r["arxiv_id"]: by_id[("axv", norm_arxiv(r["arxiv_id"]))].append(i)
        if r["doi"]:      by_id[("doi", norm_doi(r["doi"]))].append(i)
    for idxs in by_id.values():
        for j in idxs[1:]:
            union(idxs[0], j)

    # Signal 2: exact normalized title + author check.
    by_title: dict[str, list[int]] = defaultdict(list)
    for i, r in enumerate(all_rows):
        by_title[norm_title(r["title"])].append(i)
    for idxs in by_title.values():
        for a in range(len(idxs)):
            for b in range(a + 1, len(idxs)):
                if author_overlap_ok(all_rows[idxs[a]]["authors"],
                                     all_rows[idxs[b]]["authors"]):
                    union(idxs[a], idxs[b])

    # Signal 3: same first author + fuzzy title (retitled preprints).
    # Blocked by first-author lastname to stay near-linear.
    by_fa: dict[str, list[int]] = defaultdict(list)
    for i, r in enumerate(all_rows):
        fa = first_author_lastname(r["authors"])
        if fa: by_fa[fa].append(i)
    for idxs in by_fa.values():
        toks = {i: title_tokens(all_rows[i]["title"]) for i in idxs}
        for a in range(len(idxs)):
            ta = toks[idxs[a]]
            if not ta: continue
            for b in range(a + 1, len(idxs)):
                if find(idxs[a]) == find(idxs[b]): continue
                tb = toks[idxs[b]]
                if not tb: continue
                jac = len(ta & tb) / len(ta | tb)
                if jac >= 0.8 and author_overlap_ok(all_rows[idxs[a]]["authors"],
                                                    all_rows[idxs[b]]["authors"]):
                    union(idxs[a], idxs[b])

    clusters: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        clusters[find(i)].append(i)
    return list(clusters.values())

def pick_canonical(cluster: list[dict], rank_key) -> tuple[dict, list[dict]]:
    """Sort by rank, pick the winner, backfill the winner's empty identifier /
    URL fields from the losers (the preprint row often carries the arxiv_id
    the camera-ready row lacks), and note cross-venue acceptances."""
    cl = sorted(cluster, key=rank_key)
    winner, others = cl[0], cl[1:]
    for o in others:
        for field in ("arxiv_id", "openreview_id", "anthology_id", "doi",
                      "pdf_url", "abstract_url", "code_url"):
            if not winner[field] and o[field]:
                winner[field] = o[field]
    if others:
        cross = [f"{o['venue']} {o['year']} ({o['track']})" for o in others]
        extra = "also accepted at: " + "; ".join(cross)
        winner["notes"] = (winner["notes"] + " | " + extra).strip(" |") if winner["notes"] else extra
    return winner, others

def carry_over_and_assign_ids(canonical: list[dict], old_rows: list[dict]) -> dict:
    """Preserve id / downloaded / notes for rows still at the same
    (venue, year, slug); number new rows AFTER the highest existing sequence
    per venue-year. Existing ids are never reassigned."""
    old_by_key = {(r["venue"], r["year"], r["slug"]): r for r in old_rows}
    seq: dict[str, int] = defaultdict(int)
    id_re = re.compile(r"_(\d+)$")
    for r in old_rows:
        m = id_re.search(r["id"])
        if m:
            seq[f"{r['venue']}_{r['year']}"] = max(
                seq[f"{r['venue']}_{r['year']}"], int(m.group(1)))
    carried = 0
    matched = set()
    for r in canonical:
        key3 = (r["venue"], r["year"], r["slug"])
        o = old_by_key.get(key3)
        if o and o["id"]:
            r["id"] = o["id"]
            if o["downloaded"]:
                r["downloaded"] = o["downloaded"]
            if o["notes"] and o["notes"] not in (r["notes"] or ""):
                r["notes"] = (r["notes"] + " | " + o["notes"]).strip(" |") if r["notes"] else o["notes"]
            carried += 1
            matched.add(key3)
        else:
            r["id"] = ""
    for r in canonical:
        if not r["id"]:
            key = f"{r['venue']}_{r['year']}"
            seq[key] += 1
            r["id"] = f"{key}_{seq[key]:03d}"
    dropped = [o for k, o in old_by_key.items() if k not in matched]
    return {"carried": carried, "dropped": dropped}

# ---------- main ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--venues", default=None,
                    help="comma-separated venue priority, highest first")
    ap.add_argument("--dry-run", action="store_true",
                    help="compute and print the summary without writing anything")
    args = ap.parse_args()

    topic_dir = ROOT / "wiki" / "topics" / args.corpus
    coll_dir = topic_dir / "collection"
    manifest = topic_dir / "manifest.tsv"
    duplicates_out = coll_dir / "duplicates.tsv"

    # Venue priority: CLI > priorities.json > none (alphabetical fallback).
    venue_priority: dict[str, int] = {}
    if args.venues:
        venue_priority = {v.strip(): i for i, v in enumerate(args.venues.split(","))}
    elif (coll_dir / "priorities.json").is_file():
        order = json.loads((coll_dir / "priorities.json").read_text(encoding="utf-8"))
        venue_priority = {v: i for i, v in enumerate(order)}

    def vprio(venue: str):
        return (venue_priority.get(venue, 999), venue)

    def rank_key(row: dict) -> tuple:
        return (source_rank(row),
                -int(row["year"] or 0),
                vprio(row["venue"]),
                TRACK_PRIORITY.get(row["track"], 99))

    venue_files = sorted(p for p in coll_dir.glob("*.tsv")
                         if p.name != "duplicates.tsv")
    if not venue_files:
        sys.exit(f"no per-venue TSVs found in {coll_dir}")

    all_rows: list[dict] = []
    for p in venue_files:
        all_rows.extend(read_rows(p))
    print(f"Loaded {len(all_rows)} rows from {len(venue_files)} files.", file=sys.stderr)

    canonical: list[dict] = []
    duplicates: list[dict] = []
    dup_groups = 0
    for idxs in cluster_indices(all_rows):
        cluster = [all_rows[i] for i in idxs]
        if len(cluster) == 1:
            canonical.append(cluster[0])
            continue
        dup_groups += 1
        winner, others = pick_canonical(cluster, rank_key)
        canonical.append(winner)
        duplicates.extend(others)

    canonical.sort(key=lambda r: (vprio(r["venue"]), int(r["year"] or 0),
                                  r["title"].lower()))

    old_rows = read_rows(manifest) if manifest.is_file() else []
    stats = carry_over_and_assign_ids(canonical, old_rows)
    if old_rows:
        print(f"Carry-over: {stats['carried']} rows kept id/downloaded/notes "
              f"from the existing manifest.", file=sys.stderr)
        if stats["dropped"]:
            print(f"WARNING: {len(stats['dropped'])} existing manifest rows no longer "
                  f"resolve to the same (venue, year, slug); download state NOT carried:",
                  file=sys.stderr)
            for o in stats["dropped"][:10]:
                print(f"  - {o['id']} downloaded={o['downloaded']} {o['title'][:60]}",
                      file=sys.stderr)
            if len(stats["dropped"]) > 10:
                print(f"  … {len(stats['dropped']) - 10} more", file=sys.stderr)
            print("  Run verify.py to reconcile on-disk files.", file=sys.stderr)

    if not args.dry_run:
        write_rows(manifest, canonical)
        write_rows(duplicates_out, duplicates)

    print(f"\n=== DEDUP SUMMARY ===")
    print(f"Input rows:           {len(all_rows)}")
    print(f"Unique papers:        {len(canonical)}")
    print(f"Duplicate rows:       {len(duplicates)}")
    print(f"Cross-venue dup grps: {dup_groups}")
    print(f"\n=== CANONICAL BY VENUE ===")
    by_venue = defaultdict(int)
    for r in canonical: by_venue[f"{r['venue']}_{r['year']}"] += 1
    for k in sorted(by_venue):
        print(f"  {k}: {by_venue[k]}")
    if args.dry_run:
        print("\nDRY RUN — nothing written.")
    else:
        print(f"\nOutputs:\n  {manifest}\n  {duplicates_out}")

if __name__ == "__main__":
    main()

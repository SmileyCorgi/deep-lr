#!/usr/bin/env python3
"""
Merge per-venue TSVs into a corpus master manifest with cross-venue dedup.

Reads every *.tsv in wiki/topics/<corpus>/collection/ (except duplicates.tsv),
merges them, and writes:
  wiki/topics/<corpus>/manifest.tsv               — canonical merged manifest (ids assigned)
  wiki/topics/<corpus>/collection/duplicates.tsv  — non-canonical rows (audit trail)

Canonical selection when the same paper appears in multiple venues:
  1. Earliest year wins (preprint accepted at X 2025 then re-listed at Y 2026 → 2025).
  2. Tie on year → venue priority (see --venues or priorities.json).
  3. Tie on year+venue → track priority: oral > spotlight > main > poster >
     findings > datasets-benchmarks > accepted.

Dedup signal (both must hold — title match alone can be a coincidence):
  - Normalized title match (lowercase, alphanumeric+space, collapsed).
  - First-author lastname match OR ≥50% author-set overlap.

Venue priority: pass --venues "ACL,EMNLP,ICLR,ICML,NeurIPS" (highest first), or
drop a JSON list into wiki/topics/<corpus>/collection/priorities.json.
Unlisted venues rank below listed ones, alphabetically.

Usage:
  dedup.py --corpus <name> [--venues "A,B,C"]
"""
from __future__ import annotations
import argparse, csv, json, re, sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent.parent

HEADERS = ["id","title","authors","venue","year","track","category","arxiv_id",
           "openreview_id","anthology_id","pdf_url","abstract_url","slug",
           "downloaded","notes"]

TRACK_PRIORITY = {"oral":0, "spotlight":1, "main":2, "poster":3,
                  "findings":4, "datasets-benchmarks":5, "accepted":6, "":7}

def norm_title(t: str) -> str:
    t = t.lower()
    t = re.sub(r"[^a-z0-9\s]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

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

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--venues", default=None,
                    help="comma-separated venue priority, highest first")
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
        order = json.loads((coll_dir / "priorities.json").read_text())
        venue_priority = {v: i for i, v in enumerate(order)}

    def vprio(venue: str):
        # Listed venues first (by position), then unlisted alphabetically.
        return (venue_priority.get(venue, 999), venue)

    def canonical_rank(row: dict) -> tuple:
        return (int(row["year"] or 9999),
                vprio(row["venue"]),
                TRACK_PRIORITY.get(row["track"], 99))

    venue_files = sorted(p for p in coll_dir.glob("*.tsv")
                         if p.name != "duplicates.tsv")
    if not venue_files:
        sys.exit(f"no per-venue TSVs found in {coll_dir}")

    all_rows: list[dict] = []
    for p in venue_files:
        with p.open() as f:
            reader = csv.DictReader(f, delimiter="\t", fieldnames=HEADERS)
            header = next(reader)  # skip header
            assert list(header.values()) == HEADERS, f"{p.name} header mismatch: {header}"
            for r in reader:
                for h in HEADERS:
                    r.setdefault(h, "")
                all_rows.append(r)

    print(f"Loaded {len(all_rows)} rows from {len(venue_files)} files.", file=sys.stderr)

    # Group by normalized title
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in all_rows:
        groups[norm_title(r["title"])].append(r)

    canonical: list[dict] = []
    duplicates: list[dict] = []
    dup_groups = 0
    for nt, rows in groups.items():
        if len(rows) == 1:
            canonical.append(rows[0])
            continue
        # Within this title-group, partition by author-overlap
        clusters: list[list[dict]] = []
        for r in rows:
            placed = False
            for cl in clusters:
                if author_overlap_ok(cl[0]["authors"], r["authors"]):
                    cl.append(r); placed = True; break
            if not placed:
                clusters.append([r])
        for cl in clusters:
            if len(cl) == 1:
                canonical.append(cl[0])
            else:
                dup_groups += 1
                cl_sorted = sorted(cl, key=canonical_rank)
                winner = cl_sorted[0]
                others = cl_sorted[1:]
                cross = [f"{o['venue']} {o['year']} ({o['track']})" for o in others]
                extra = "also accepted at: " + "; ".join(cross)
                winner["notes"] = (winner["notes"] + " | " + extra).strip(" |") if winner["notes"] else extra
                canonical.append(winner)
                duplicates.extend(others)

    # Sort canonical, then assign ids <VENUE>_<YEAR>_NNN
    canonical.sort(key=lambda r: (vprio(r["venue"]), int(r["year"] or 0),
                                  r["title"].lower()))
    seq = defaultdict(int)
    for r in canonical:
        key = f"{r['venue']}_{r['year']}"
        seq[key] += 1
        r["id"] = f"{key}_{seq[key]:03d}"

    for path, rows in ((manifest, canonical), (duplicates_out, duplicates)):
        with path.open("w") as f:
            w = csv.DictWriter(f, fieldnames=HEADERS, delimiter="\t",
                               quoting=csv.QUOTE_NONE, escapechar="\\")
            w.writeheader()
            for r in rows:
                w.writerow({h: r.get(h, "") for h in HEADERS})

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
    print(f"\nOutputs:\n  {manifest}\n  {duplicates_out}")

if __name__ == "__main__":
    main()

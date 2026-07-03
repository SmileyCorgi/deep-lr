#!/usr/bin/env python3
"""
Integrity check: cross-reference a corpus manifest against on-disk PDFs/abstracts.

Categories reported:
  - manifest_says_yes_but_no_pdf       (lying about downloaded)
  - pdf_without_abstract               (PDF without abstract sidecar)
  - manifest_says_no_but_pdf_exists    (lag — should be set to yes)
  - pdf_orphan / abstract_orphan       (on disk, not in manifest)
  - rows_with_no_url_source            (cannot be downloaded by current scripts)

Writes wiki/topics/<corpus>/verification.md with the report.

Usage:
  verify.py --corpus <name>
"""
import argparse, csv, time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    args = ap.parse_args()

    topic_dir = ROOT / "wiki" / "topics" / args.corpus
    manifest = topic_dir / "manifest.tsv"
    report = topic_dir / "verification.md"
    raw = ROOT / "raw" / "papers" / args.corpus

    rows = list(csv.DictReader(manifest.open(), delimiter="\t"))
    by_slug = {(r["venue"], r["year"], r["slug"]): r for r in rows}

    issues: dict[str, list] = defaultdict(list)
    venue_stats: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    # Manifest → disk
    for r in rows:
        venue = r["venue"]; year = r["year"]; slug = r["slug"]; rid = r["id"]
        pdf = raw / f"{venue}_{year}" / f"{slug}.pdf"
        abs_md = raw / f"{venue}_{year}" / f"{slug}.abstract.md"
        pdf_ok = pdf.exists() and pdf.stat().st_size > 1024
        abs_ok = abs_md.exists() and abs_md.stat().st_size > 100
        vk = f"{venue}_{year}"
        venue_stats[vk]["total"] += 1
        if pdf_ok: venue_stats[vk]["pdf_on_disk"] += 1
        if abs_ok: venue_stats[vk]["abs_on_disk"] += 1

        st = r["downloaded"]
        if st == "yes" and not pdf_ok:
            issues["manifest_says_yes_but_no_pdf"].append((rid, venue, year, slug))
        if pdf_ok and not abs_ok:
            issues["pdf_without_abstract"].append((rid, venue, year, slug))
        if st in ("", "no") and pdf_ok:
            issues["manifest_says_no_but_pdf_exists"].append((rid, venue, year, slug))
        if st in ("", "no") and not r["pdf_url"] and not r["arxiv_id"]:
            issues["rows_with_no_url_source"].append((rid, venue, year, slug, r["notes"][:80]))

    # Disk → manifest (find orphans)
    if raw.exists():
        for venue_dir in sorted(raw.iterdir()):
            if not venue_dir.is_dir(): continue
            parts = venue_dir.name.rsplit("_", 1)
            if len(parts) != 2: continue
            v, y = parts
            for f in venue_dir.iterdir():
                if f.suffix == ".pdf":
                    slug = f.stem
                    if (v, y, slug) not in by_slug:
                        issues["pdf_orphan"].append((venue_dir.name, slug))
                elif f.name.endswith(".abstract.md"):
                    slug = f.name[:-len(".abstract.md")]
                    if (v, y, slug) not in by_slug:
                        issues["abstract_orphan"].append((venue_dir.name, slug))

    # Compose report
    lines = ["# Manifest ↔ Filesystem Integrity Report",
             "",
             f"Run: {time.strftime('%Y-%m-%d')} · corpus `{args.corpus}` · script `verify.py`",
             "",
             "## Per-venue counts",
             "",
             "| venue | rows | pdf on disk | abstracts on disk |",
             "|---|---|---|---|"]
    for vk in sorted(venue_stats):
        s = venue_stats[vk]
        lines.append(f"| {vk} | {s['total']} | {s['pdf_on_disk']} | {s['abs_on_disk']} |")
    lines.append("")
    lines.append("## Issues")
    lines.append("")
    if not any(issues.values()):
        lines.append("**No issues found.** Manifest is consistent with disk.")
    else:
        for kind, items in issues.items():
            lines.append(f"### {kind} ({len(items)})")
            if not items: continue
            for ex in items[:8]:
                lines.append(f"  - `{' | '.join(str(x) for x in ex)}`")
            if len(items) > 8:
                lines.append(f"  - … {len(items) - 8} more (see manifest)")
            lines.append("")

    report.write_text("\n".join(lines))
    print("=== INTEGRITY CHECK ===")
    for k, v in issues.items():
        print(f"  {k}: {len(v)}")
    print(f"\nReport: {report}")

if __name__ == "__main__":
    main()

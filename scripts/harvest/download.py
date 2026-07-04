#!/usr/bin/env python3
"""
Smart downloader for a deep-lr literature corpus.

Reads wiki/topics/<corpus>/manifest.tsv. For each row with downloaded in {"no", ""}:
  - Fetches the abstract (source adapters: ACL Anthology HTML, CVF Open Access
    HTML, OpenReview API, arXiv API, generic conference "virtual site" HTML).
  - Downloads the PDF (canonical pdf_url with arXiv fallback, then arXiv title search).
  - Writes raw/papers/<corpus>/<venue>_<year>/<slug>.{pdf,abstract.md}.
  - Updates manifest.tsv `downloaded` column to "yes" on success.
  - Logs failures with diagnosis to wiki/topics/<corpus>/collection/download-errors.log.

Resume-safe: skips rows whose target files already exist on disk AND pass the
PDF integrity check (%PDF header + %%EOF trailer — truncated files re-fetch).
Polite: per-host minimum intervals + exponential backoff on 429/503 honoring
Retry-After. The manifest is checkpointed atomically every 25 rows, so a
mid-run crash loses at most 25 rows of bookkeeping and can never truncate it.

Usage:
  download.py --corpus <name>                     # full run on all queued rows
  download.py --corpus <name> --pilot N           # N stratified random rows (validate first!)
  download.py --corpus <name> --venue ACL_2025    # limit to one venue-year
  download.py --corpus <name> --id ACL_2025_001   # single row

Doctrine (learned the hard way — see scripts/harvest/README.md):
  - Mechanical fetching at scale belongs in THIS script, not in LLM-agent loops.
    Agents are poor at sitting through HTTP 429 backoffs.
  - Always pilot (--pilot 20) before a full run.
  - The manifest is canon: never hand-edit downloaded flags; let this script or
    `verify.py --fix` reconcile them.

Extending to a new discipline: add an abstract extractor for your source
(PubMed, SSRN, bioRxiv, ...) and wire it into get_abstract(). Everything else
(rate limiting, retries, sidecars, manifest bookkeeping) is source-agnostic.
"""
from __future__ import annotations
import argparse, json, os, random, re, socket, sys, time, urllib.parse, urllib.request
from html.parser import HTMLParser
from pathlib import Path
from collections import defaultdict
from urllib.error import HTTPError, URLError

from manifestio import read_rows, write_rows, pdf_ok

# scripts/harvest/download.py → repo root is two levels up.
ROOT = Path(__file__).resolve().parent.parent.parent

# Set to a real contact address — polite crawling etiquette (arXiv asks for it).
# Either edit here or export DEEPLR_CONTACT_EMAIL.
CONTACT_EMAIL = os.environ.get("DEEPLR_CONTACT_EMAIL", "you@example.com")

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      f"(KHTML, like Gecko) AcademicResearchBot/1.0 (mailto:{CONTACT_EMAIL})")
last_request_at: dict[str, float] = defaultdict(float)

# Per-host minimum interval. OpenReview and arXiv enforce strict rate limits.
HOST_INTERVAL = {
    "api2.openreview.net":      2.5,
    "openreview.net":           2.5,
    "export.arxiv.org":         3.0,   # arXiv asks for max ~1 req / 3s
    "arxiv.org":                3.0,
    "aclanthology.org":         0.5,
    "openaccess.thecvf.com":    1.0,
}
DEFAULT_INTERVAL = 1.0

# Retryable failures: rate limiting, transient server errors, network blips.
RETRY_CODES = {"HTTP 429", "HTTP 503", "timeout"}
BACKOFFS = [8, 20, 45]   # seconds between attempts
MAX_RETRY_AFTER = 120    # cap on server-requested Retry-After

def retryable(err: str) -> bool:
    return err in RETRY_CODES or err.startswith("transient:")

def polite_wait(url: str):
    host = urllib.parse.urlparse(url).netloc
    interval = HOST_INTERVAL.get(host, DEFAULT_INTERVAL)
    elapsed = time.monotonic() - last_request_at[host]
    if elapsed < interval:
        time.sleep(interval - elapsed)
    last_request_at[host] = time.monotonic()

def fetch_once(url: str, timeout: int, accept: str) -> tuple[bytes | None, str | None, str | None]:
    """Returns (body, error, retry_after_header)."""
    polite_wait(url)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read(), None, None
    except HTTPError as e:
        ra = e.headers.get("Retry-After") if e.headers else None
        return None, f"HTTP {e.code}", ra
    except URLError as e:
        reason = e.reason
        if isinstance(reason, (socket.timeout, TimeoutError)):
            return None, "timeout", None
        if isinstance(reason, (ConnectionResetError, ConnectionAbortedError,
                               ConnectionRefusedError, socket.gaierror)):
            return None, f"transient: {type(reason).__name__}", None
        msg = str(reason)
        return None, ("timeout" if "timed out" in msg.lower() else f"URLError: {msg}"), None
    except TimeoutError:
        return None, "timeout", None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}", None

def fetch(url: str, timeout: int = 30, accept: str = "*/*") -> tuple[bytes | None, str | None]:
    """Fetch with retry on 429/503/timeout/connection blips, honoring Retry-After."""
    body, err, ra = fetch_once(url, timeout, accept)
    if err is None: return body, None
    for delay in BACKOFFS:
        if not retryable(err): break
        if ra:
            try:
                delay = max(delay, min(int(float(ra)), MAX_RETRY_AFTER))
            except ValueError:
                pass
        time.sleep(delay)
        body, err, ra = fetch_once(url, timeout, accept)
        if err is None: return body, None
    return None, err

# ---------- Abstract extractors (source adapters) ----------

class DivAttrParser(HTMLParser):
    """Extract text content of the first <div> whose `attr` contains NEEDLE."""
    def __init__(self, needle: str, attr: str = "class"):
        super().__init__()
        self.needle = needle
        self.attr = attr
        self.depth = 0; self.inside = False; self.buf: list[str] = []
    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "div" and self.needle in (d.get(self.attr, "") or "") and not self.inside:
            self.inside = True; self.depth = 1
        elif self.inside:
            self.depth += 1
    def handle_endtag(self, tag):
        if self.inside:
            self.depth -= 1
            if self.depth == 0:
                self.inside = False
    def handle_data(self, data):
        if self.inside:
            self.buf.append(data)

def _extract_div(url: str, needle: str, attr: str = "class") -> tuple[str | None, str | None]:
    html, err = fetch(url)
    if err: return None, err
    p = DivAttrParser(needle, attr)
    try: p.feed(html.decode("utf-8", errors="replace"))
    except Exception as e: return None, f"parse failed: {e}"
    text = re.sub(r"\s+", " ", "".join(p.buf)).strip()
    text = re.sub(r"^abstract\s*", "", text, flags=re.I)
    return (text, None) if text else (None, "abstract empty")

def abstract_from_anthology(row: dict) -> tuple[str | None, str | None]:
    url = row["abstract_url"]
    if not url: return None, "no abstract_url"
    return _extract_div(url, "acl-abstract")

def abstract_from_cvf(row: dict) -> tuple[str | None, str | None]:
    """CVF Open Access (openaccess.thecvf.com) paper pages — the archival home
    of CVPR/ICCV/WACV. Abstract lives in <div id="abstract">."""
    url = row["abstract_url"]
    if not url: return None, "no abstract_url"
    return _extract_div(url, "abstract", attr="id")

def abstract_from_openreview(row: dict) -> tuple[str | None, str | None]:
    fid = row["openreview_id"]
    if not fid: return None, "no openreview_id"
    url = f"https://api2.openreview.net/notes?forum={fid}&details=replyCount"
    body, err = fetch(url)
    if err: return None, err
    try:
        j = json.loads(body)
        for note in j.get("notes", []):
            if note.get("id") == fid or note.get("forum") == fid:
                c = note.get("content", {})
                abs_field = c.get("abstract", {})
                # API v2 wraps values in {"value": ...}
                text = abs_field.get("value") if isinstance(abs_field, dict) else abs_field
                if text: return re.sub(r"\s+", " ", text).strip(), None
    except Exception as e:
        return None, f"json parse failed: {e}"
    return None, "abstract not in API response"

def abstract_from_arxiv(arxiv_id: str) -> tuple[str | None, str | None]:
    url = f"https://export.arxiv.org/api/query?id_list={arxiv_id}"
    body, err = fetch(url)
    if err: return None, err
    m = re.search(r"<summary>(.*?)</summary>", body.decode("utf-8", errors="replace"), re.S)
    if not m: return None, "no <summary> in arxiv response"
    return re.sub(r"\s+", " ", m.group(1)).strip(), None

def abstract_from_virtual_site(row: dict) -> tuple[str | None, str | None]:
    """Conference 'virtual site' pages (icml.cc/neurips.cc/iclr.cc virtual/...)
    share the abstract-text-inner div convention."""
    url = row["abstract_url"]
    if not url: return None, "no abstract_url"
    return _extract_div(url, "abstract-text-inner")

def get_abstract(row: dict) -> tuple[str | None, str | None]:
    """Adapter dispatch, most-reliable source first. Add new disciplines here."""
    if row["anthology_id"] and row["abstract_url"]:
        return abstract_from_anthology(row)
    if "thecvf.com" in (row["abstract_url"] or ""):
        return abstract_from_cvf(row)
    if row["openreview_id"]:
        return abstract_from_openreview(row)
    if row["arxiv_id"]:
        return abstract_from_arxiv(row["arxiv_id"])
    if row["abstract_url"] and "/virtual/" in row["abstract_url"]:
        return abstract_from_virtual_site(row)
    return None, "no abstract source"

# ---------- arXiv title search (PDF fallback of last resort) ----------

def arxiv_title_search(title: str) -> tuple[str | None, str]:
    """Return (arxiv_id, diag). High-confidence match only."""
    q = urllib.parse.quote(f'ti:"{title}"')
    url = f"https://export.arxiv.org/api/query?search_query={q}&max_results=3"
    body, err = fetch(url)
    if err: return None, err
    text = body.decode("utf-8", errors="replace")
    entries = re.findall(r"<entry>(.*?)</entry>", text, re.S)
    if not entries: return None, "no entries"
    def norm(t): return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", t.lower())).strip()
    target = norm(title)
    for e in entries:
        id_m = re.search(r"<id>http[s]?://arxiv\.org/abs/([^<]+)</id>", e)
        t_m = re.search(r"<title>(.*?)</title>", e, re.S)
        if not id_m or not t_m: continue
        cand = norm(t_m.group(1))
        if cand == target:
            return id_m.group(1).strip(), "exact match"
        # Fuzzy: 0.92+ Jaccard on word sets
        ws1, ws2 = set(target.split()), set(cand.split())
        if ws1 and ws2:
            jac = len(ws1 & ws2) / len(ws1 | ws2)
            if jac >= 0.92:
                return id_m.group(1).strip(), f"high-confidence ({jac:.2f})"
    return None, "no high-confidence match"

# ---------- PDF download ----------

def download_pdf(url: str, dest: Path) -> tuple[bool, str]:
    body, err = fetch(url, timeout=60, accept="application/pdf")
    if err: return False, err
    if not body or len(body) < 1024: return False, f"too small ({len(body) if body else 0} bytes)"
    if not body.startswith(b"%PDF"): return False, f"not PDF (head={body[:8]!r})"
    if b"%%EOF" not in body[-1024:]: return False, "truncated (no %%EOF trailer)"
    dest.write_bytes(body)
    return True, "ok"

def get_pdf_for_row(row: dict, dest: Path) -> tuple[bool, str, str]:
    """Returns (success, strategy, error)."""
    # Strategy 1: canonical pdf_url
    if row["pdf_url"]:
        ok, err = download_pdf(row["pdf_url"], dest)
        if ok: return True, "primary", ""
        # Strategy 2: if arxiv_id known, fall back to arXiv
        if row["arxiv_id"]:
            arxiv_url = f"https://arxiv.org/pdf/{row['arxiv_id']}.pdf"
            ok2, err2 = download_pdf(arxiv_url, dest)
            if ok2: return True, "arxiv-fallback", ""
            return False, "none", f"primary:{err}; arxiv:{err2}"
        return False, "none", err
    # No pdf_url: try arXiv direct
    if row["arxiv_id"]:
        arxiv_url = f"https://arxiv.org/pdf/{row['arxiv_id']}.pdf"
        ok, err = download_pdf(arxiv_url, dest)
        if ok: return True, "arxiv-direct", ""
        return False, "none", f"arxiv:{err}"
    # Last resort: arXiv title search
    aid, diag = arxiv_title_search(row["title"])
    if aid:
        arxiv_url = f"https://arxiv.org/pdf/{aid}.pdf"
        ok, err = download_pdf(arxiv_url, dest)
        if ok:
            row["arxiv_id"] = aid
            return True, f"arxiv-search ({diag})", ""
        return False, "none", f"arxiv-search-found-but-download-failed:{err}"
    return False, "none", f"arxiv-search:{diag}"

# ---------- Sidecar writer ----------

def write_abstract_sidecar(row: dict, abstract: str, dest: Path):
    fm = {
        "id": row["id"],
        "title": row["title"].replace('"', "'"),
        "authors": row["authors"],
        "venue": row["venue"],
        "year": row["year"],
        "track": row["track"],
        "category": row["category"],
        "arxiv_id": row["arxiv_id"],
        "openreview_id": row["openreview_id"],
        "anthology_id": row["anthology_id"],
        "doi": row["doi"],
        "abstract_url": row["abstract_url"],
        "pdf_url": row["pdf_url"],
        "code_url": row["code_url"],
    }
    lines = ["---"]
    for k, v in fm.items():
        if v: lines.append(f'{k}: "{v}"')
    lines.append("---\n")
    lines.append(f"# {row['title']}\n")
    lines.append(f"**Authors:** {row['authors']}\n")
    lines.append(f"**Venue:** {row['venue']} {row['year']} ({row['track']})\n")
    if row["notes"]:
        lines.append(f"**Notes:** {row['notes']}\n")
    lines.append("## Abstract\n")
    lines.append(abstract.strip() + "\n")
    dest.write_text("\n".join(lines), encoding="utf-8")

# ---------- Main ----------

def process_row(row: dict, raw_base: Path) -> tuple[str, str]:
    """Returns (status, detail). status in {downloaded, skipped, failed, partial}."""
    if not (row.get("slug") or "").strip():
        return "failed", "empty slug (check manifest column alignment)"
    venue_dir = raw_base / f"{row['venue']}_{row['year']}"
    venue_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = venue_dir / f"{row['slug']}.pdf"
    abs_path = venue_dir / f"{row['slug']}.abstract.md"

    pdf_done = pdf_ok(pdf_path)   # integrity check, not just existence
    abs_done = abs_path.exists() and abs_path.stat().st_size > 100

    if not abs_done:
        text, err = get_abstract(row)
        if text:
            write_abstract_sidecar(row, text, abs_path)
            abs_done = True
        else:
            return "failed", f"abstract: {err}"

    if not pdf_done:
        ok, strategy, err = get_pdf_for_row(row, pdf_path)
        if ok:
            return "downloaded", strategy
        elif abs_done:
            return "partial", f"pdf: {err}"
        else:
            return "failed", f"pdf: {err}"
    return "downloaded", "already on disk"

def normalize_error(detail: str) -> str:
    """Aggregate error reasons WITHOUT losing HTTP status codes: 404 vs 429
    demand opposite responses (fix URLs vs slow down), so only non-status
    digits (ids, sizes) are collapsed to N."""
    return re.sub(r"(?<!HTTP )\b\d+\b", "N", detail).split(";")[0][:80]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True,
                    help="corpus name — reads wiki/topics/<corpus>/manifest.tsv, "
                         "writes raw/papers/<corpus>/")
    ap.add_argument("--pilot", type=int, default=0)
    ap.add_argument("--venue", default=None, help="e.g., ACL_2025")
    ap.add_argument("--id", default=None)
    ap.add_argument("--max", type=int, default=0)
    args = ap.parse_args()

    topic_dir = ROOT / "wiki" / "topics" / args.corpus
    manifest = topic_dir / "manifest.tsv"
    if not manifest.is_file():
        sys.exit(f"manifest not found: {manifest}")
    raw_base = ROOT / "raw" / "papers" / args.corpus
    error_log = topic_dir / "collection" / "download-errors.log"
    error_log.parent.mkdir(parents=True, exist_ok=True)

    all_rows = read_rows(manifest)
    queue = [r for r in all_rows if r["downloaded"] in ("", "no")]
    if args.id:
        queue = [r for r in queue if r["id"] == args.id]
    elif args.venue:
        queue = [r for r in queue if f"{r['venue']}_{r['year']}" == args.venue]
    if args.pilot:
        random.seed(42)
        # Stratified pilot: sample evenly across venue-years
        by_v = defaultdict(list)
        for r in queue: by_v[f"{r['venue']}_{r['year']}"].append(r)
        sampled = []
        per = max(1, args.pilot // max(1, len(by_v)))
        for v, rs in by_v.items():
            sampled.extend(random.sample(rs, min(per, len(rs))))
        queue = sampled[:args.pilot]
    if args.max:
        queue = queue[:args.max]

    print(f"Processing {len(queue)} rows.", flush=True)
    errors_f = open(error_log, "a", encoding="utf-8")
    errors_f.write(f"\n=== run start {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
    stats = defaultdict(int)
    error_reasons: dict[str, int] = defaultdict(int)
    by_venue: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for i, row in enumerate(queue, 1):
        status, detail = process_row(row, raw_base)
        stats[status] += 1
        by_venue[f"{row['venue']}_{row['year']}"][status] += 1
        if status in ("failed", "partial"):
            errors_f.write(f"{row['id']}\t{status}\t{detail}\t{row['title'][:80]}\n")
            error_reasons[normalize_error(detail)] += 1
        if status == "downloaded":
            row["downloaded"] = "yes"
        if i % 25 == 0 or i == len(queue):
            # Checkpoint: atomic manifest write + flushed error log, so a
            # mid-run crash loses at most 25 rows of bookkeeping.
            write_rows(manifest, all_rows)
            errors_f.flush()
            print(f"  [{i}/{len(queue)}] dl={stats['downloaded']} partial={stats['partial']} failed={stats['failed']}", flush=True)

    errors_f.close()
    if queue:
        write_rows(manifest, all_rows)

    print("\n=== SUMMARY ===")
    for k in ("downloaded", "partial", "failed", "skipped"):
        print(f"  {k}: {stats[k]}")
    print("\n=== BY VENUE-YEAR ===")
    for v in sorted(by_venue):
        print(f"  {v}: " + ", ".join(f"{k}={by_venue[v][k]}" for k in ("downloaded","partial","failed")))
    if error_reasons:
        print("\n=== TOP ERROR REASONS ===")
        for reason, n in sorted(error_reasons.items(), key=lambda x: -x[1])[:10]:
            print(f"  {n}× {reason}")

if __name__ == "__main__":
    main()

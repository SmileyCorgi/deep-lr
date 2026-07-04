# Harvest toolkit — manifest-driven literature collection

Stdlib-only Python scripts for building a paper corpus at scale (hundreds to
thousands of papers). Battle-tested on a 2,500-paper corpus across
ACL/EMNLP/ICLR/ICML/NeurIPS 2025–2026.

## The pipeline

```
1. COLLECT   LLM agents (or scripts) enumerate accepted papers per venue-year
             → one TSV per venue-year in wiki/topics/<corpus>/collection/
2. DEDUP     python scripts/harvest/dedup.py --corpus <name> [--dry-run]
             → merges venue TSVs into wiki/topics/<corpus>/manifest.tsv
3. DOWNLOAD  python scripts/harvest/download.py --corpus <name> --pilot 20
             → validate; then run without --pilot for the full corpus
4. VERIFY    python scripts/harvest/verify.py --corpus <name> [--fix]
             → manifest ↔ filesystem cross-check, writes verification.md;
               --fix reconciles `downloaded` flags with disk truth
```

(Windows note: use `python` or `py -3`; bare `python3` is often a Microsoft
Store stub. All scripts are stdlib-only, Python ≥3.9.)

Files land in `raw/papers/<corpus>/<VENUE>_<YEAR>/<slug>.{pdf,abstract.md}`.

## Manifest schema (TSV, tab-separated, 17 columns, schema v2)

| column | meaning |
|---|---|
| `id` | `<VENUE>_<YEAR>_NNN`, assigned by dedup.py; stable across re-runs |
| `title`, `authors` | authors as `Last, First; Last, First; …` |
| `venue`, `year`, `track` | track ∈ oral/spotlight/main/poster/findings/… |
| `category` | your topical tag (used for tiered digestion later) |
| `arxiv_id`, `openreview_id`, `anthology_id`, `doi` | source ids — fill what you have |
| `pdf_url`, `abstract_url` | canonical URLs |
| `code_url` | official code / weights repo, if any (grab it during COLLECT) |
| `slug` | filename stem, lowercase-hyphenated |
| `downloaded` | `yes` / `no` / empty — maintained by download.py / `verify.py --fix` only |
| `notes` | free text; dedup.py appends cross-venue acceptances here |

v1 manifests (15 columns, no `doi`/`code_url`) are upgraded automatically on
the next read. All manifest I/O goes through `manifestio.py` — the single
source of truth for schema, UTF-8 encoding, the escape dialect, and atomic
writes. Scripts must never `open()` the manifest directly.

**The manifest is canon.** Never hand-edit `downloaded`; let download.py or
`verify.py --fix` reconcile it. Never delete rows — corrections go in `notes`.
Re-running dedup.py is safe: rows keep their `id`/`downloaded`/`notes` as long
as they still resolve to the same (venue, year, slug), and new ids continue
each venue-year sequence.

## Tests

`python -m unittest discover scripts/harvest/tests -v` — covers title/author
normalization, all three dedup signals, archival-first canonical selection,
re-run carry-over, and the TSV round-trip with hostile characters (tabs,
backslashes, non-ASCII). Run after touching any harvest script.

## Operating doctrine (lessons that cost real time)

- **Scripts, not agents, for mechanical fetching.** LLM agents are poor at
  sitting through HTTP 429 backoff waits. Have agents produce/verify the
  manifest; have this script fetch.
- **Pilot then scale.** Always `--pilot 20` first, read the error breakdown,
  fix, then full-run. Never blind-retry a failing pattern.
- **Archive, don't delete.** When a collection phase ends, move working TSVs
  and logs into `collection/archive/` with a README explaining each file's
  origin. PDFs may be deleted after digestion — they are recoverable from
  `pdf_url` — but abstract sidecars and the manifest are permanent.
- **Bounded downloads.** If you shell out with curl instead, always set
  `--max-time`; unbounded parallel curl loops hang.

## External API quirks (verified 2026-05)

- **OpenReview API v2**: filter with `content.venue=<string>`, *not*
  `content.venueid`. Values are wrapped: `{"value": ...}`.
- **arXiv**: hard rate limit ~1 request / 3 s on both `export.arxiv.org` API
  and PDF fetches; 429s are common — the downloader backs off 8/20/45 s and
  honors `Retry-After`. Include a contact email in your User-Agent (set
  `CONTACT_EMAIL` in download.py or export `DEEPLR_CONTACT_EMAIL`).
- **ACL Anthology**: event pages (`aclanthology.org/events/<venue>-<year>/`)
  are the complete accepted list; abstracts are in `div.acl-abstract`.
- **CVF Open Access** (openaccess.thecvf.com) — CVPR/ICCV/WACV archival home:
  `openaccess.thecvf.com/CVPR<year>?day=all` lists every accepted paper, each
  with an HTML abstract page (`div#abstract`) and a direct PDF link. No harsh
  rate limits observed; the downloader still spaces requests 1 s apart.
- **Conference virtual sites** (icml.cc, neurips.cc, iclr.cc `/virtual/`):
  abstracts in `div.abstract-text-inner`; PDFs usually absent until the
  OpenReview archive opens (~conference time).

## Extending to another discipline

Add an abstract extractor in `download.py` (e.g. PubMed E-utilities, bioRxiv
API, SSRN) and wire it into `get_abstract()`. If your discipline has an
"also published at" pattern (workshops → journal), the dedup rules already
handle it; adjust venue priority via `--venues` or
`collection/priorities.json`.

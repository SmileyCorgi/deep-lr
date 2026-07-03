# Harvest toolkit — manifest-driven literature collection

Stdlib-only Python scripts for building a paper corpus at scale (hundreds to
thousands of papers). Battle-tested on a 2,500-paper corpus across
ACL/EMNLP/ICLR/ICML/NeurIPS 2025–2026.

## The pipeline

```
1. COLLECT   LLM agents (or scripts) enumerate accepted papers per venue-year
             → one TSV per venue-year in wiki/topics/<corpus>/collection/
2. DEDUP     python3 scripts/harvest/dedup.py --corpus <name>
             → merges venue TSVs into wiki/topics/<corpus>/manifest.tsv
3. DOWNLOAD  python3 scripts/harvest/download.py --corpus <name> --pilot 20
             → validate; then run without --pilot for the full corpus
4. VERIFY    python3 scripts/harvest/verify.py --corpus <name>
             → manifest ↔ filesystem cross-check, writes verification.md
```

Files land in `raw/papers/<corpus>/<VENUE>_<YEAR>/<slug>.{pdf,abstract.md}`.

## Manifest schema (TSV, tab-separated, 15 columns)

| column | meaning |
|---|---|
| `id` | `<VENUE>_<YEAR>_NNN`, assigned by dedup.py |
| `title`, `authors` | authors as `Last, First; Last, First; …` |
| `venue`, `year`, `track` | track ∈ oral/spotlight/main/poster/findings/… |
| `category` | your topical tag (used for tiered digestion later) |
| `arxiv_id`, `openreview_id`, `anthology_id` | source ids — fill what you have |
| `pdf_url`, `abstract_url` | canonical URLs |
| `slug` | filename stem, lowercase-hyphenated |
| `downloaded` | `yes` / `no` / empty — maintained by download.py only |
| `notes` | free text; dedup.py appends cross-venue acceptances here |

**The manifest is canon.** Never hand-edit `downloaded`; let download.py or a
reconcile pass fix it. Never delete rows — corrections go in `notes`.

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
  and PDF fetches; 429s are common — the downloader backs off 8/20/45 s.
  Include a contact email in your User-Agent (set `CONTACT_EMAIL` in
  download.py).
- **ACL Anthology**: event pages (`aclanthology.org/events/<venue>-<year>/`)
  are the complete accepted list; abstracts are in `div.acl-abstract`.
- **Conference virtual sites** (icml.cc, neurips.cc, iclr.cc `/virtual/`):
  abstracts in `div.abstract-text-inner`; PDFs usually absent until the
  OpenReview archive opens (~conference time).

## Extending to another discipline

Add an abstract extractor in `download.py` (e.g. PubMed E-utilities, bioRxiv
API, SSRN) and wire it into `get_abstract()`. If your discipline has an
"also published at" pattern (workshops → journal), the dedup rules already
handle it; adjust venue priority via `--venues` or
`collection/priorities.json`.

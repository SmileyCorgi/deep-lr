---
name: lit-harvest
description: Build a literature corpus at scale (hundreds to thousands of papers) — scope with the user, collect accepted-paper lists into per-venue TSVs, dedup into a manifest, download PDFs+abstracts politely, verify integrity, then digest in tiers (anchor entity pages + 1-line tail). Use when the user says "collect all papers on X", "build a corpus from venues Y/Z", "harvest the literature on X", or wants systematic multi-venue coverage rather than a handful of papers.
---

# Literature harvest (corpus collection → tiered digestion)

Codified from a 2,500-paper harvest across ACL/EMNLP/ICLR/ICML/NeurIPS
2025–2026. The pipeline scripts live in `scripts/harvest/` (read its README
for the manifest schema and API quirks). Division of labor is the core idea:
**agents for judgment (scoping, relevance, reading); scripts for mechanics
(fetching, deduping, counting).**

## Phase 0 — Scope (checkpoint with the user, don't guess)

Create `wiki/topics/<corpus-name>/README.md` stating: research scope (what's
in/out), target venues & years, category taxonomy for tagging rows, and any
conditional venues (e.g. "ICML 2026 if the archive has opened"). Ask the user
to sign off on open scope questions before launching collection. Corpus layout:

```
wiki/topics/<corpus>/
├── README.md            ← scope + current state (keep a "Current state" table)
├── manifest.tsv         ← canon (produced by dedup.py)
├── collection/          ← per-venue TSVs, working scripts, logs
│   └── archive/         ← retired working files (archive, don't delete)
└── verification.md      ← produced by verify.py
raw/papers/<corpus>/<VENUE>_<YEAR>/<slug>.{pdf,abstract.md}
```

## Phase 1 — Collect (agents enumerate; one TSV per venue-year)

Dispatch parallel `general-purpose` subagents, one per venue-year, to
enumerate accepted papers matching the scope and emit TSV rows in the
17-column manifest schema v2 (`scripts/harvest/README.md`). Source guidance:

- **ACL/EMNLP**: anthology event pages are complete; abstracts in `div.acl-abstract`.
- **OpenReview venues (ICLR/ICML/NeurIPS)**: API v2, filter `content.venue=<string>` — NOT `content.venueid`.
- **CVF venues (CVPR/ICCV/WACV)**: `openaccess.thecvf.com/<VENUE><year>?day=all`
  is the complete accepted list; each paper has an HTML abstract page
  (`div#abstract`) and a direct PDF link.
- **Not-yet-published venues**: collect URL-only rows (abstract_url from the
  conference virtual site); mark notes `pdf-pending`; re-run download later.
- Fill every id you can get (arxiv_id, openreview_id, anthology_id, doi) — they
  are the download fallback chain AND the strongest dedup signal. Grab
  `code_url` when the listing shows it (arXiv/OpenReview pages usually do).

Have each agent tag rows with a `category` from the taxonomy — this powers
tiered digestion later.

## Phase 2 — Dedup → manifest

```bash
python scripts/harvest/dedup.py --corpus <name> --venues "ACL,EMNLP,ICLR,ICML,NeurIPS" --dry-run
python scripts/harvest/dedup.py --corpus <name> --venues "..."   # then for real
```
Archival version wins (anthology/DOI > openreview > arXiv-only), then latest
year, then venue/track priority. Cross-venue acceptances are annotated in
`notes`. Re-running after adding venues is safe — existing ids and download
state carry over. Review `collection/duplicates.tsv` once. Also grep
`wiki/entities/` and `raw/papers/` top level for papers a `paper-sweep`
already filed (match by arxiv_id/title): update those entity pages to point
at the corpus copy instead of double-filing.

## Phase 3 — Download (pilot first, always)

```bash
python scripts/harvest/download.py --corpus <name> --pilot 20   # validate
python scripts/harvest/download.py --corpus <name>              # full run
```
Read the error breakdown from the pilot before scaling. Do NOT replace this
with agent-driven fetching — agents handle HTTP 429 waits badly. Expect
OpenReview/arXiv rate limits to dominate failures; the script backs off
automatically. Long runs: use `run_in_background`.

## Phase 4 — Verify

```bash
python scripts/harvest/verify.py --corpus <name>        # report
python scripts/harvest/verify.py --corpus <name> --fix  # reconcile flags with disk
```
Zero manifest lies and zero orphans is the bar. Reconcile before digesting —
`--fix` is the sanctioned way (never hand-edit `downloaded`).

## Phase 5 — Tiered digestion

Never write a full page per paper at corpus scale. The proven tiering:

1. **Pilot cluster**: pick one high-value category (~50 papers), write full
   entity pages (template: `meta/templates/entity-page.md`), plus a topic
   synthesis page with thematic clusters + cross-cutting findings + open
   questions.
2. **Broader corpus**: partition the rest into ~10 clusters (title-based
   partition is more precise than abstract-matching). Per cluster: ~5 anchors
   get full entity pages; the tail gets **1-line entries with first-sentence
   syntheses** inline in `wiki/topics/<cluster>.md`, grouped by sub-theme.
3. Update `index.md` after each cluster; log each as
   `## [YYYY-MM-DD] ingest | cluster N (<name>) — M papers + K anchors`.

**Anchor selection is a ranked judgment, not a vibe** — score candidates by:
track (oral/spotlight first) → citation count (one Semantic Scholar query) →
cross-cluster mentions → user override. Present the tiering to the user
(Hard rules below); before creating a page, check `wiki/entities/` for an
existing one.

**Entity-page honesty rules:**
- Set `reading: abstract` unless you actually read the full text; an
  abstract-read page must not state numbers the abstract doesn't contain
  (mark claims "(abstract-claimed)"). Fill Results properly only for anchors
  you deep-read.
- **Visual disciplines (hard rule)**: before ANY PDF deletion, extract each
  anchor's architecture figure + main results figure to
  `raw/assets/<corpus>/<slug>/` (pdf skill / pymupdf) and reference them in
  the entity page's `## Key figures`. An architecture you only described in
  prose is half-lost.
- If a paper reports numbers on a tracked benchmark page
  (`wiki/comparisons/`, `type: benchmark`), append a SOTA-table row.

**Promotion rule** (works in reverse too): a tail entry that accumulates ≥3
wikilink citations shows up in lint — promote it to a full entity page.

## Phase 6 — Consolidate & clean

- Move working TSVs/logs to `collection/archive/` with a README documenting
  each file's origin.
- Update the corpus README "Current state" table (rows, downloaded, pending,
  re-run instructions).
- PDFs may be deleted after full digestion **only after** checking (a) every
  PDF has an abstract sidecar, and (b) every anchor's key figures are
  extracted to `raw/assets/` (visual disciplines). Manifest URLs make PDFs
  recoverable; lost figures of a deleted PDF are not recoverable in practice.
  Log the cleanup.
- Produce a **"read these yourself"** list for the user: the 3–5 papers of
  the harvest a human should read in the original, with one line on why.
  Put it in the topic page's anchor table ("Read by human?" column).
- Run `python portal/build.py --lint`; fix findings. Commit per cluster.

## Hard rules

- Manifest is canon; scripts maintain `downloaded` (or `verify.py --fix`),
  never hand-edits.
- Pilot before scale at every mechanical step.
- Checkpoint scope and tiering decisions with the user (AskUserQuestion) —
  these are judgment calls the user owns.
- Log every phase in `log.md`; one commit per phase/cluster.

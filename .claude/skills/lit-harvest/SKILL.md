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
15-column manifest schema (`scripts/harvest/README.md`). Source guidance:

- **ACL/EMNLP**: anthology event pages are complete; abstracts in `div.acl-abstract`.
- **OpenReview venues (ICLR/ICML/NeurIPS)**: API v2, filter `content.venue=<string>` — NOT `content.venueid`.
- **Not-yet-published venues**: collect URL-only rows (abstract_url from the
  conference virtual site); mark notes `pdf-pending`; re-run download later.
- Fill every id you can get (arxiv_id, openreview_id, anthology_id) — they are
  the download fallback chain.

Have each agent tag rows with a `category` from the taxonomy — this powers
tiered digestion later.

## Phase 2 — Dedup → manifest

```bash
python3 scripts/harvest/dedup.py --corpus <name> --venues "ACL,EMNLP,ICLR,ICML,NeurIPS"
```
Earliest year wins; ties break by venue then track priority. Cross-venue
acceptances are annotated in `notes`. Review `collection/duplicates.tsv` once.

## Phase 3 — Download (pilot first, always)

```bash
python3 scripts/harvest/download.py --corpus <name> --pilot 20   # validate
python3 scripts/harvest/download.py --corpus <name>              # full run
```
Read the error breakdown from the pilot before scaling. Do NOT replace this
with agent-driven fetching — agents handle HTTP 429 waits badly. Expect
OpenReview/arXiv rate limits to dominate failures; the script backs off
automatically. Long runs: use `run_in_background`.

## Phase 4 — Verify

```bash
python3 scripts/harvest/verify.py --corpus <name>
```
Zero manifest lies and zero orphans is the bar. Reconcile before digesting.

## Phase 5 — Tiered digestion

Never write a full page per paper at corpus scale. The proven tiering:

1. **Pilot cluster**: pick one high-value category (~50 papers), write full
   entity pages (template: `meta/templates/entity-page.md`; abstract-primary
   reading is usually enough), plus a topic synthesis page with thematic
   clusters + cross-cutting findings + open questions.
2. **Broader corpus**: partition the rest into ~10 clusters (title-based
   partition is more precise than abstract-matching). Per cluster: ~5 anchors
   get full entity pages; the tail gets **1-line entries with first-sentence
   syntheses** inline in `wiki/topics/<cluster>.md`, grouped by sub-theme.
3. Update `index.md` after each cluster; log each as
   `## [YYYY-MM-DD] ingest | cluster N (<name>) — M papers + K anchors`.

## Phase 6 — Consolidate & clean

- Move working TSVs/logs to `collection/archive/` with a README documenting
  each file's origin.
- Update the corpus README "Current state" table (rows, downloaded, pending,
  re-run instructions).
- PDFs may be deleted after full digestion **only after** checking every PDF
  has an abstract sidecar; manifest URLs make them recoverable. Log the
  cleanup.

## Hard rules

- Manifest is canon; scripts maintain `downloaded`, never hand-edits.
- Pilot before scale at every mechanical step.
- Checkpoint scope and tiering decisions with the user (AskUserQuestion) —
  these are judgment calls the user owns.
- Log every phase in `log.md`.

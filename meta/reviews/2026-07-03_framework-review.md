# Framework review — 2026-07-03

Five-persona review panel (simulated: NLP professor, CV professor, and three
PhD students — first-year/usability, systems/infra, knowledge-management)
independently read the whole template repo and critiqued the framework design.
This file is the consolidated minutes + the implementation record. Full
per-reviewer reports lived in the session transcript; the actionable content
is all here.

## Consensus findings (independently hit by ≥2 reviewers)

1. **Conventions weren't machine-checked contracts** — index.md vs portal
   drift, unmaintained `sources:` field, four naming schemes with no
   validator. (usability + KM + systems)
2. **The two collection pipelines didn't know about each other** — a paper
   swept from arXiv and later harvested at camera-ready got two entity pages
   and two files. (NLP + CV professors)
3. **Abstract-primary digestion contradicted the entity template** — template
   demanded conditioned Results numbers the abstract doesn't contain
   (structurally inducing fabrication), and figures were systematically lost
   before PDF deletion. (NLP + CV professors)
4. **Human reading was not a first-class citizen** — no mechanism told the
   human what to read; risk of "beautiful wiki, empty brain".
   (NLP professor + first-year PhD)
5. **Windows/encoding was broken in practice** — `python3` is a Store stub
   here; harvest scripts had no `encoding=` and died on the first non-GBK
   character. (first-year + systems PhDs; systems PhD verified cp936 locally)

## Highest-value individual findings

- systems PhD: `dedup.py` rerun destroyed download state and renumbered ids;
  manifest writes were non-atomic (kill → truncated canon); error
  normalization collapsed HTTP 404/429 into `HTTP NNN`, destroying exactly
  the pilot diagnostics the doctrine sells.
- KM PhD: frontmatter spec and `portal/build.py` had already diverged
  (`venue`/`entity_kind` read by code, absent from spec/templates); overwrite
  updates to Synthesis sections silently destroy the field's understanding-
  over-time — the one loss git can't practically recover.
- CV professor: no comparison template existed despite the schema claiming
  five types; benchmarks/SOTA had no first-class home; dataset entities can't
  use author-keyword-year slugs.
- NLP professor: synthesis had no adversarial review before becoming
  canonical; `(unverified)` guarded only fabricated IDs, not misattribution/
  number drift; dedup's earliest-year-wins is backwards for NLP (archival
  version is the version of record).
- first-year PhD: bootstrap demanded answers an undecided student can't give;
  no recovery guidance and no commit discipline anywhere.

## What was implemented (all of it, 2026-07-03)

- **P0** `scripts/harvest/manifestio.py` (schema v2 +doi/+code_url, UTF-8,
  atomic writes, symmetric dialect, shared `pdf_ok`); dedup rerun carry-over
  + `--dry-run` + archival-first + 3-signal matching; download Retry-After /
  transient retries / %%EOF check / per-25-row checkpoints / status-code-
  preserving error aggregation / CVF adapter; `verify.py --fix`; 20 unit
  tests; `python3`→`python` everywhere.
- **P1** deep-dive reviewer gate (Step 3.5) + evidence grades + required
  "read these yourself"; entity template `Key figures` + `reading:` honesty
  rule; new benchmark/comparison/dataset/method templates; topic `## Timeline`
  (append-only) + site-wide dated `## Superseded`; typed links
  (improves/refutes/uses/extends) in schema and portal graph; paper-sweep
  pre-download dedup + tiering + reject lists; lit-harvest anchor criteria +
  figure-extraction hard rule + promotion rule.
- **P2** portal lint expansion (frontmatter contract, malformed wikilinks,
  duplicate slugs, index.md drift, stale pages, merge candidates, strict
  mode); CLAUDE.md: direction-undecided bootstrap, minimal-first-day, Idea
  lifecycle, Commit & recovery; skills table with scale/preconditions;
  backlog format aligned with the parser.

## Deliberate decisions (the disagreements, adjudicated)

- index.md stays hand-curated (the one-liners are its value); the build
  script lints its coverage instead of generating it.
- `sources:` frontmatter deleted rather than auto-written; backlink counts
  are computed at build time.
- `entities/` directory NOT split by kind; `entity_kind` frontmatter + per-
  kind slug rules instead (directory splits complicate wikilink resolution).

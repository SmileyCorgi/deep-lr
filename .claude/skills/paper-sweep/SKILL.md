---
name: paper-sweep
description: Periodic "what's new" discovery sweep over recently published literature — dual-channel parallel search (venue/preprint listings + trending/curated channels), dedup, download the winners, and file entity pages with a fixed section layout. Use when the user says "what's new this month", "find the latest papers on X since <date>", "sweep arXiv/PubMed for recent work", or wants recurring literature monitoring.
---

# Paper sweep (periodic discovery ingest)

Codified from a 16-paper dual-channel sweep (arXiv listings + HuggingFace
Daily Papers). Adapt channels to the discipline configured in `CLAUDE.md` §0.

## Pipeline

### 1. Scope the window
Date range = since the last sweep (check `log.md` for the previous
`ingest | ... sweep` entry) up to today. Confirm topical scope with the user
only if it differs from the repo's standing topics.

### 2. Dual-channel parallel discovery
Launch two `general-purpose` subagents concurrently with an explicit
**coordination rule** so their picks don't collide:

- **Channel A — completeness**: primary listings (arXiv categories, PubMed
  query, SSRN section, journal ToCs). Biased toward papers the trending
  channel will miss.
- **Channel B — signal**: trending/curated channels (HuggingFace Daily Papers,
  Semantic Scholar highly-cited-recent, field newsletters, awesome-list
  diffs). Threshold on the channel's own signal (e.g. upvotes ≥ N).
- Coordination rule: Channel B wins overlaps; Channel A biases to non-trending
  discovery. Each returns ~8 picks with ids, one-line reasons, and signal
  stats.

### 3. Download & file
- Download PDFs to `raw/papers/` as `YYYY-MM-DD_<author>-<slug>.pdf` via a
  bounded script (sequential, ~4 s spacing, `--max-time` set; validate PDF
  magic bytes) — not via agent loops.
- Verify title/authors/date against the live abstract page before writing.
- One entity page per paper in `wiki/entities/` using the sweep layout:
  frontmatter + TL;DR + **Abstract / Methodology / Experimental Design /
  Results / Key Takeaways** + Links.

### 4. Cross-cluster signals
After filing, write 3–5 bullets on what the batch says *together* (converging
sub-areas, new evaluation axes, contradictions with existing wiki claims).
Put these in the `log.md` entry and in `index.md`'s batch block.

### 5. Integrate & log
- Update `index.md` with a dated batch section (split by channel).
- Topic-page touch-ups may be **queued** ("pending topic touch-up") if the
  batch is large — but record the queue explicitly in the log entry so it
  isn't lost.
- `log.md`: `## [YYYY-MM-DD] ingest | N latest <field> papers (<channels> sweep)`.

## Recurring use
For standing monitoring, the user can schedule this skill (e.g. via /schedule
or a cron routine) — keep each run's window contiguous with the last so
nothing falls in a gap.

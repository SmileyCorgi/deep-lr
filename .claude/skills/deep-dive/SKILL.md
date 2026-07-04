---
name: deep-dive
description: Saturate one research topic — partition it into sub-threads, dispatch parallel research subagents to deep-read the literature, then consolidate into a single synthesis page with cross-cutting findings and next-step opportunities. Use when the user says "go deep on X", "deep dive into topic X", "what does the literature really say about X", or a topic page has grown big enough to deserve a structured synthesis.
---

# Deep dive (parallel literature synthesis)

Codified from three production deep-dives (multi-agent: 263 papers / 5 agents;
agentic training: ~70 anchors / 6 agents; summarization: ~50 anchors / 4
agents). The output is ONE canonical synthesis page — per-agent reports are
scaffolding and get deleted.

## Pipeline

### 1. Partition
Split the topic into **4–6 sub-threads** (by sub-literature, not by venue).
If a `wiki/topics/<topic>.md` page exists, derive threads from its structure;
otherwise propose threads and checkpoint with the user.

### 2. Dispatch parallel research subagents (one per thread)
Launch `general-purpose` agents concurrently (single message, multiple Agent
calls). Each agent's brief:
- Enumerate the thread's key papers (existing corpus/manifest first, then web:
  arXiv listings, survey reference lists, "awesome" lists).
- **Deep-read ~8–15 anchor papers** — prefer HTML full text (ar5iv/arxiv.org/html,
  publisher HTML) over PDFs for speed. **Exception:** in visually dense
  disciplines (CV, robotics — check the topic's nature), anchors' architecture
  and main-results figures must be viewed from the PDF or project page; ar5iv
  drops/breaks figures and half the paper lives in them.
- Return: per-anchor findings (problem/method/headline numbers **with their
  in-source location** — "Table 3", "abstract"), thread-level storyline,
  contradictions found, and full citation ids.
- Write intermediate output to a `temp_<topic>/` working folder.

### 3. Consolidate → synthesis draft
Write `wiki/synthesis/<topic>-deep-dive.md` (template:
`meta/templates/synthesis-page.md`) as a **draft** (`status: stub`):
- Per-thread sections (the storyline, not paper-by-paper lists).
- **Every claim carries an evidence grade**: [source-backed] (with citation +
  in-source location), [inference] (reasoning stated), or [unknown].
- **Cross-cutting findings** (aim for 5–8) — the lessons that only appear when
  threads are read together. This is the page's reason to exist.
- Tensions/contradictions surfaced explicitly.
- Concrete next-step opportunities (ranked) and open questions.
- **"Read these yourself"** (required, not optional): the 3–5 anchors a human
  must read in the original, each with one line on why — most contested claim,
  most load-bearing result, most surprising method.

### 3.5 Reviewer gate (before the page becomes canonical)
Dispatch ONE independent reviewer subagent. Give it ONLY the synthesis draft
and access to raw sources (abstracts/full text) — **not** the per-thread
reports, so it cannot inherit their errors. Its brief: attack the draft like
a hostile reviewer — strongest rejection risks first; spot-check 5 random
[source-backed] claims against the actual sources; flag any number that
lacks a location or any claim graded above its evidence.
Then respond to every objection in the draft's `## Review` section (fix,
rebut with evidence, or downgrade the claim). Only after that: set
`status: growing` — the page is now canonical.

### 4. Integrate
- Update/expand `wiki/topics/<topic>.md`: Synthesis section, anchor table
  (with the "Read by human?" column), and a `## Timeline` line if the
  storyline changed direction.
- New anchor papers get entity pages **only if** they'll be cited again
  (anchors-plus-inline-tail rule); check `wiki/entities/` for an existing page
  before creating one (a paper-sweep may have filed it already); create via
  `meta/templates/entity-page.md` with an honest `reading:` value.
- Update `index.md`; append `log.md`:
  `## [YYYY-MM-DD] synthesis | <topic>-deep-dive`.

### 5. Prune & verify
- Delete `temp_<topic>/` after consolidation. The synthesis is canonical;
  per-agent reports are noise once merged.
- Run `python portal/build.py --lint`; fix findings.
- Commit (`synthesis | <topic>-deep-dive`).

## Quality rules

- **Verify citations**: any paper id supplied by a subagent that is newer than
  your knowledge cutoff gets flagged `(unverified)` in the synthesis until
  checked against the live source.
- Headline numbers must carry their conditions (benchmark, model, setting)
  AND their in-source location ("Table 3") — a number without its setting is
  a future contradiction; a number without its location is unauditable.
- Prefer mechanisms over claims: for each cross-cutting finding, state WHY it
  holds, not just that N papers agree.
- If two threads disagree, that disagreement is a finding — never average it
  away.

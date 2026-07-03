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
  publisher HTML) over PDFs for speed.
- Return: per-anchor findings (problem/method/headline numbers), thread-level
  storyline, contradictions found, and full citation ids.
- Write intermediate output to a `temp_<topic>/` working folder.

### 3. Consolidate → synthesis page
Write `wiki/synthesis/<topic>-deep-dive.md`:
- Per-thread sections (the storyline, not paper-by-paper lists).
- **Cross-cutting findings** (aim for 5–8) — the lessons that only appear when
  threads are read together. This is the page's reason to exist.
- Tensions/contradictions surfaced explicitly.
- Concrete next-step opportunities (ranked) and open questions.
- Optional: role-based reading paths.

### 4. Integrate
- Update/expand `wiki/topics/<topic>.md` (synthesis section + anchor table).
- New anchor papers get entity pages **only if** they'll be cited again
  (anchors-plus-inline-tail rule); create pages via `meta/templates/entity-page.md`.
- Update `index.md`; append `log.md`:
  `## [YYYY-MM-DD] synthesis | <topic>-deep-dive`.

### 5. Prune
Delete `temp_<topic>/` after consolidation. The synthesis is canonical;
per-agent reports are noise once merged.

## Quality rules

- **Verify citations**: any paper id supplied by a subagent that is newer than
  your knowledge cutoff gets flagged `(unverified)` in the synthesis until
  checked against the live source.
- Headline numbers must carry their conditions (benchmark, model, setting) —
  a number without its setting is a future contradiction.
- Prefer mechanisms over claims: for each cross-cutting finding, state WHY it
  holds, not just that N papers agree.
- If two threads disagree, that disagreement is a finding — never average it
  away.

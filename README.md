# deep-lr

**Deep Literature Research** — a general-purpose, LLM-operated framework for
literature retrieval, organization, and knowledge management in **any
discipline**. You curate sources and ask questions; your coding agent (Claude
Code or similar) harvests, digests, cross-links, and keeps everything current.

Extracted and generalized from a production agentic-AI research workbench that
processed a 2,500-paper corpus, four topic deep-dives, and a diagram-first
publishing pipeline.

## What's inside

| Layer | What it does |
|---|---|
| `CLAUDE.md` | The schema: zoning, update rules, conventions. This is the framework's brain. |
| `llm-wiki.md` | The underlying doctrine (LLM-maintained wiki pattern). |
| `raw/` → `wiki/` | Immutable sources → LLM-owned synthesis (topics / entities / concepts / comparisons / synthesis). |
| `scripts/harvest/` | Stdlib-only corpus pipeline: collect → dedup → download (rate-limit-aware) → verify. Manifest-driven, resume-safe. |
| `.claude/skills/` | 5 workflows: `lit-harvest` (corpus building), `deep-dive` (parallel topic synthesis), `paper-sweep` (periodic what's-new), `good-question` (research-question shaping), `research-to-blog` (diagram-first posts). |
| `html/` + `portal/` | Browsable research workbench over `wiki/`: dashboard, entity browser, force-directed knowledge graph, activity stream, ⌘K search. Zero dependencies. |
| `blog/` + `html/` | Optional publishing surface with a zero-dep `canvas` diagram DSL (matrix / timeline / flow / bars / grid). |
| `experiments/`, `ideas/` | Experiment lifecycle (active → archived) and idea backlog. |

Everything is markdown + stdlib Python + vanilla JS. No installs required.
Obsidian works as the reading UI (optional: Dataview + Templater plugins).

## Quickstart

1. Copy this repo (or `git clone`) to a new project folder.
2. Open it in Claude Code and say:
   > Bootstrap this repo for **<your discipline>** research.
   The agent runs the `CLAUDE.md` §0 protocol: interviews you, fills the
   config, creates seed topic pages.
3. Start working:
   - "Collect all papers on X from venues Y" → `lit-harvest`
   - "Add this paper" → ingest flow
   - "What's the state of X?" → query flow (answers file back into the wiki)
   - "Go deep on X" → `deep-dive`
   - "What's new this month?" → `paper-sweep`
4. Browse: `python3 -m http.server 8765` from the repo root →
   portal at `http://127.0.0.1:8765/html/portal/index.html`
   (regenerate with `python3 portal/build.py` after wiki changes).

## Design principles

- **Three-layer zoning**: raw sources are immutable; synthesis is iterative;
  the schema governs both. Never mix raw with synthesis.
- **Anchors + inline tail**: at corpus scale, ~5 anchor papers per cluster get
  full pages; the rest live as 1-line syntheses in topic pages.
- **Scripts for mechanics, agents for judgment**: fetching at scale is a
  Python script's job (agents are bad at HTTP 429 waits); relevance and
  reading are the agent's job.
- **Pilot then scale**: every mechanical pipeline validates on ~20 items first.
- **Archive, don't delete**: manifests and abstracts are permanent; PDFs are
  recoverable from URLs; retired working files go to `archive/` with a README.
- **Occam's Razor**: fewer pages, fewer folders; a page must earn its keep.

## Adapting to your discipline

- **Sources**: `scripts/harvest/download.py` ships adapters for arXiv,
  OpenReview, and the ACL Anthology; add one function for PubMed/SSRN/bioRxiv
  etc. and wire it into `get_abstract()` (see `scripts/harvest/README.md`).
- **Templates**: page skeletons in `meta/templates/`.
- **Branding**: site title strings live in `html/index.html`, `html/post.html`,
  and `html/portal/*.html` ("deep-lr" by default).

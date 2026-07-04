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

**The minimal first day** (works even if your research direction isn't settled):

1. Copy this repo (or `git clone`) to a new project folder.
2. Open it in Claude Code and say:
   > Bootstrap this repo for **<your discipline>** research.
   The agent runs the `CLAUDE.md` §0 protocol: interviews you, fills the
   config, creates seed topic pages. Direction undecided? Say so — the agent
   runs `good-question` first and bootstraps thin (1–2 tentative topics;
   topics are cheap to rename/delete later).
3. Hand it the 2–3 papers you already have: "Add this paper" (ingest flow).
   That's a complete, useful first day — corpus harvests and deep dives earn
   their complexity later.
4. Browse: `python serve.py` from the repo root →
   portal at `http://127.0.0.1:8765/html/portal/index.html`
   (regenerate with `python portal/build.py` after wiki changes).
   Every wiki page and blog post has a **✎ notes** widget — margin notes you
   write in the browser land in `raw/notes/web/` and the agent integrates
   them next session. (Plain `python -m http.server 8765` also works; notes
   then stay in the browser with an export button.)

**Growing from there:**
   - "Build me a reading list on X (~30–50 papers)" → small `lit-harvest`
   - "Collect all papers on X from venues Y" → full `lit-harvest`
   - "What's the state of X?" → query flow (answers file back into the wiki)
   - "Go deep on X" → `deep-dive` (with an adversarial reviewer gate)
   - "What's new this month?" → `paper-sweep`
   - "Is this a good research idea?" → `good-question` + the idea lifecycle
     (capture → shape → promote to experiment)
   - Made a mess? Every operation is one commit — `git revert` and move on.

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

## Template vs. content

A working copy of this repo holds two things with different lifecycles: the
**framework** (scripts, portal, skills, templates — keeps improving) and your
**research content** (wiki, raw sources, posts — private by default). They
stay separable by design:

- Name the framework's GitHub remote `template` (not `origin`).
- Publish framework improvements with `python scripts/template_sync.py --push`
  — it copies only template-zone paths into a worktree of `template/main`,
  resets the four bootstrap-mixed files from `meta/template-state/`, validates
  (tests + builds + strict lint), and refuses to commit if any content path
  sneaks in. Research content structurally cannot reach the template repo.
- Pull framework updates the ordinary way: `git fetch template && git merge
  template/main` (content files never conflict — they're not in the template).

## Adapting to your discipline

- **Sources**: `scripts/harvest/download.py` ships adapters for arXiv,
  OpenReview, the ACL Anthology, and CVF Open Access (CVPR/ICCV/WACV); add one
  function for PubMed/SSRN/bioRxiv etc. and wire it into `get_abstract()`
  (see `scripts/harvest/README.md`).
- **Visual disciplines**: anchors' key figures are extracted to `raw/assets/`
  before any PDF cleanup, and benchmark pages (`type: benchmark`) track SOTA
  tables append-only over time.
- **Templates**: page skeletons in `meta/templates/`.
- **Branding**: site title strings live in `html/index.html`, `html/post.html`,
  and `html/portal/*.html` ("deep-lr" by default).

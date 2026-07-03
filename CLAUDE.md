# deep-lr — Schema & Operating Guide

This repository is a **living, LLM-maintained knowledge base** for literature
research in ANY discipline. It follows the [LLM Wiki](./llm-wiki.md) pattern:
humans curate sources and ask questions; the LLM compiles, integrates, prunes,
and keeps everything current.

deep-lr = **deep literature research**: retrieval (corpus harvesting at scale),
organization (tiered digestion into an interlinked wiki), and knowledge
management (query → synthesis → file-back, plus a browsable portal and a
publishing surface).

---

## 0. Project config (fill in at bootstrap)

> **Bootstrap protocol.** On the first session in a fresh copy of this repo,
> the LLM must interview the user and fill in this section, then delete this
> blockquote. Ask: (1) discipline & research mission, (2) 5–10 seed topics,
> (3) primary source venues/databases (conferences? journals? arXiv? PubMed?),
> (4) owner name + contact email (also set `CONTACT_EMAIL` in
> `scripts/harvest/download.py`), (5) site title if the blog/portal will be
> used (default "deep-lr"). Then: create `wiki/topics/<topic>.md` stubs for the
> seed topics, link them from `index.md`, and append a `log.md` bootstrap entry.

- **Discipline / mission**: _(unset)_
- **Owner**: _(unset)_
- **Bootstrapped**: _(unset)_
- **Seed topics**: _(unset — tracked as pages under `wiki/topics/`; each topic
  page is the entry point to its sub-literature, entities, and open questions)_

The topic list is mutable. Add a topic by creating `wiki/topics/<topic>.md`
and linking it from `index.md`.

---

## 1. Mission

Conduct continuous literature research on the configured discipline — guide,
discover, design, and resolve open problems. This is a general-purpose,
reusable workbench: any research topic in the discipline should be runnable
here without restructuring the repo.

---

## 2. Architecture (zoning)

Three layers, strictly separated. **Never mix raw sources with synthesis.**

```
deep-lr/
├── CLAUDE.md            ← this file (the schema)
├── llm-wiki.md          ← reference doctrine (immutable)
├── index.md             ← content catalog (wiki TOC)
├── log.md               ← chronological activity log
│
├── raw/                 ← IMMUTABLE source layer
│   ├── papers/          ← PDFs; corpus subdirs raw/papers/<corpus>/<VENUE>_<YEAR>/
│   ├── articles/        ← web clips (markdown), blog posts
│   ├── notes/           ← meeting notes, transcripts, raw thoughts
│   └── assets/          ← images, figures, data files
│
├── wiki/                ← LLM-OWNED synthesis layer
│   ├── topics/          ← one page per topic; corpus sub-projects live here too
│   ├── entities/        ← papers, methods, datasets, people, orgs
│   ├── concepts/        ← cross-cutting ideas
│   ├── comparisons/     ← tables / matrices across entities
│   └── synthesis/       ← multi-source essays, theses, position pieces
│
├── experiments/         ← active research work
│   ├── active/          ← in-progress (free-form, intermediate saves OK)
│   └── archived/        ← completed pipelines (raw data + concise docs)
│
├── ideas/               ← forward-looking research questions
│   └── backlog.md       ← prioritized idea tracker
│
├── scripts/harvest/     ← manifest-driven corpus collection (see its README)
│
├── blog/                ← optional public-facing writing surface
├── html/                ← static site: blog renderer + portal workbench
├── portal/build.py      ← regenerates html/portal/index.json from wiki/
└── meta/                ← templates + project-level conventions
```

### Zone ownership & write rules

| Zone | Who writes | Mutability | When LLM touches it |
|---|---|---|---|
| `raw/` | Human (mostly) | Append-only; never edit existing files | Reads only; may add new files when fetching sources |
| `wiki/` | LLM | Continuously updated | On every ingest, query that yields insight, or lint pass |
| `experiments/active/` | LLM + human | Freely mutable | During active experimentation |
| `experiments/archived/` | LLM | Frozen after archival | Only to read; modifications require a new dated subdir |
| `ideas/` | Both | Append-mostly; prune on promotion | When new questions arise or items get promoted |
| `scripts/` | LLM | Stable; extend for new source adapters | When a new discipline/source needs an extractor |
| `meta/` | Both | Stable; rare edits | Only when conventions or templates change |
| `blog/` | LLM drafts on user trigger; user approves before `status: published` flip | Append-mostly; edits OK during draft phase | Only on explicit user trigger. **Canonical contract: `blog/README.md`.** Run `python3 blog/build.py --lint` before publishing; `python3 blog/build.py` after every post change. |
| `html/` | LLM | Static site; never touch `wiki/` or `raw/` from JS at runtime (read-only fetches of `wiki/entities/<slug>.md` for the references modal are OK) | Edit when the design contract in `blog/design/CHOSEN.md` changes |
| `index.md`, `log.md` | LLM | Continuously updated | Every operation |

---

## 3. Update rules

### Ingest (new source → `raw/`)
1. Place the file in the correct `raw/<subzone>/` directory. Filename: `YYYY-MM-DD_<short-slug>.<ext>` (corpus files instead follow `raw/papers/<corpus>/<VENUE>_<YEAR>/<slug>.*`).
2. Read it; discuss key takeaways briefly with the user.
3. Write/update a **source page** in `wiki/entities/` named after the source.
4. Update every affected `wiki/topics/`, `wiki/concepts/`, `wiki/comparisons/` page. Flag contradictions with newer/older sources explicitly.
5. Update `index.md` (add the new page; revise any one-line summaries that shifted).
6. Append a `log.md` entry: `## [YYYY-MM-DD] ingest | <title>`.

### Corpus harvest (large-scale collection → tiered digestion)
Use the **`lit-harvest`** skill. Summary: scope the corpus with the user →
collect per-venue TSVs → `dedup.py` → `download.py --pilot` → full download →
`verify.py` → tiered digestion (**anchors get full entity pages; the tail gets
1-line inline entries in the topic page**). PDFs may be deleted after digestion
(recoverable from URLs); abstracts and the manifest are permanent.

### Query (user asks a question)
1. Read `index.md` first to locate relevant wiki pages; drill in.
2. Synthesize answer with **citations to wiki pages and raw sources**.
3. If the answer is non-trivial and reusable, **file it back** as a new page (usually under `wiki/synthesis/` or `wiki/comparisons/`).
4. Append a `log.md` entry: `## [YYYY-MM-DD] query | <one-line question>`.

### Deep dive (saturating a topic)
Use the **`deep-dive`** skill: partition the topic into 4–6 sub-threads,
dispatch parallel research subagents, deep-read anchor papers, and file a
`wiki/synthesis/<topic>-deep-dive.md` with cross-cutting findings. Delete the
temp working folder after consolidation — the synthesis is canonical.

### Experiment lifecycle
1. **Start**: create `experiments/active/<YYYY-MM-DD>_<slug>/` with a `README.md` stating hypothesis, method, and success criteria.
2. **During**: intermediate saves are fine inside this dir.
3. **On completion**: produce a concise consolidation — `README.md` (final hypothesis, method, results, takeaways, 1–3 pages), `raw/` subdir (preserved data, configs, seeds, exact commands), `figures/` (final plots only). Delete intermediate scratch.
4. **Archive**: `mv experiments/active/<slug> experiments/archived/<slug>`. Freeze.
5. Update `wiki/synthesis/` or relevant topic pages. Append `log.md`: `## [YYYY-MM-DD] experiment-archived | <slug>`.

### Lint (periodic health check; run on request or every ~10 ingests)
Check for: contradictions across pages, stale claims, orphan pages, concepts mentioned but lacking a page, missing cross-references, idea-tracker items ripe for promotion, scratch files lingering in `experiments/active/`. Report findings; apply fixes with user approval. Log as `## [YYYY-MM-DD] lint | <scope>`. The portal build also reports broken wikilinks and orphans: `python3 portal/build.py --lint`.

### Pruning (Occam's Razor in action)
- A page exists only if it earns its keep: it's referenced, or it's a topic/concept entry point.
- Merge two pages into one when their content overlaps >60%.
- Move outdated claims to a `## Superseded` section rather than silently deleting.
- Delete intermediate experiment scratch on archival; never delete raw sources or archived experiment evidence.

---

## 4. Operating principles

**First Principles.** Before applying any framework or borrowing a result, ask: what is the underlying mechanism? State assumptions explicitly. When a finding seems surprising, re-derive — don't trust transitive claims.

**Occam's Razor.** Prefer the simplest structure that fits. Fewer pages, fewer directories, fewer abstractions. If a folder has one file in it for three months, it shouldn't be a folder. New zones must justify themselves with at least 3 distinct planned entries.

**Pristine record-keeping.** Raw evidence is sacred; synthesis is iterative. Once a pipeline completes, the artifact set is: (raw data, concise writeup, conclusion logged). Intermediate noise gets pruned. Archive, don't delete: working files from a finished collection phase go to an `archive/` subdir with a README, not to the trash.

**Pilot then scale.** Validate every mechanical pipeline on ~20 items before the full run. Diagnose failures from the error breakdown; never blind-retry.

**Scripts for mechanical work.** Fetching, counting, renaming at scale → Python scripts (`scripts/`). LLM agents for judgment: relevance filtering, reading, synthesis.

**Linkage over hierarchy.** Use `[[wikilinks]]` (Obsidian-style) liberally across `wiki/`. Folders are coarse zoning; meaning lives in the graph.

**Verify citations.** Sub-agent-supplied paper IDs (arXiv, DOI) newer than the model's knowledge cutoff get flagged `(unverified)` until checked against the source.

---

## 5. Conventions

- **Filenames**: lowercase, hyphen-separated. Dates as `YYYY-MM-DD`. Source files in `raw/` prefixed by date.
- **Entity slugs**: `<firstauthor-lastname>-<keyword>-<year>` (e.g. `smith-catalysis-2026`); surveys may use `YYYY_author_short`.
- **Page frontmatter** (for `wiki/` pages; enables Dataview queries and the portal):
  ```yaml
  ---
  type: topic | entity | concept | comparison | synthesis
  tags: [your-tags]
  created: YYYY-MM-DD
  updated: YYYY-MM-DD
  sources: 0
  ---
  ```
- **Entity page layout**: TL;DR / Problem / Method / Results / Key contributions / Links (templates in `meta/templates/`).
- **Cross-links**: `[[entity-name]]` or `[[topic-name]]`. Bare wikilinks; Obsidian resolves them.
- **Log entry prefix**: `## [YYYY-MM-DD] <op> | <subject>` (parseable: `grep "^## \[" log.md`). Ops: bootstrap, ingest, query, synthesis, experiment-archived, lint, blog, dashboard, harvest, cleanup.
- **Citations in synthesis**: `([[entity-slug]])` or footnote-style with link to the raw source.

---

## 6. Tool & resource management

### Local project skills (`.claude/skills/`)
| Skill | When to use |
|---|---|
| `lit-harvest` | Building a paper corpus at scale: scope → collect → dedup → download → verify → tiered digestion. |
| `deep-dive` | Saturating one topic: parallel subagent sweep → anchor deep-reads → synthesis page. |
| `paper-sweep` | Periodic "what's new" discovery sweep over recent publications; ingests the winners. |
| `good-question` | Shaping / stress-testing a research question, hypothesis, or project direction. |
| `research-to-blog` | Turning a paper / synthesis / topic into a diagram-first blog post (canvas DSL); stops at the draft gate. |

### Generic agents & skills (host-provided)
Use `Explore` for repo search, `general-purpose` for open-ended multi-step web
research, `Plan` for implementation strategy. Useful host skills when present:
`pdf` (extract text/tables from papers), `pptx`/`theme-factory` (decks),
`doc-coauthoring`, `deep-research` (fan-out fact-checked reports),
`webapp-testing` (Playwright verification of the html layer).

### Project scripts (stdlib-only; no installs required)
- `scripts/harvest/{dedup,download,verify}.py` — corpus pipeline (see `scripts/harvest/README.md`).
- `blog/build.py` — walks `blog/posts/*.md` → `blog/index.json`. Modes: `--include-drafts`, `--lint`, `--strict`.
- `portal/build.py` — walks `wiki/` + `ideas/` + `log.md` → `html/portal/index.json` (pages, backlinks, graph, stats, orphans, broken links). `--lint` mode reports health only.
- Serve the site locally: `python3 -m http.server 8765` from the repo root → blog at `/html/index.html`, portal at `/html/portal/index.html`.

### Obsidian plugins (user installs manually; optional)
**Dataview** (frontmatter queries, dashboards) and **Templater** (page templates from `meta/templates/`).

---

## 7. Workflow quick-reference

- **"Bootstrap this repo for <discipline>"** → §0 bootstrap protocol.
- **"Add this paper"** → ingest flow (§3).
- **"Collect all papers on X from venues Y"** → `lit-harvest` skill.
- **"What's the state of X?"** → query flow (§3); file the answer back if substantive.
- **"Go deep on topic X"** → `deep-dive` skill.
- **"What's new this month?"** → `paper-sweep` skill.
- **"Is this a good research question?"** → `good-question` skill.
- **"Start an experiment on Y"** → experiment lifecycle (§3).
- **"Capture this idea"** → append to `ideas/backlog.md` with date and trigger condition.
- **"Health check"** → lint flow (§3) + `python3 portal/build.py --lint`.
- **"Summarize recent work"** → `grep "^## \[" log.md | tail -N`.
- **"Turn this research into a webpage / diagram-first post"** → `research-to-blog` skill (never auto-publishes).
- **"Publish this to the blog"** → `blog/README.md` §6 pre-publish checklist; wait for the user's explicit go-ahead.

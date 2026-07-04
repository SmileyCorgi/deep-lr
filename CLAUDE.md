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
> `scripts/harvest/download.py` or export `DEEPLR_CONTACT_EMAIL`), (5) site
> title if the blog/portal will be used (default "deep-lr"). Then: create
> `wiki/topics/<topic>.md` stubs for the seed topics, link them from
> `index.md`, and append a `log.md` bootstrap entry.
>
> **Direction still undecided?** Don't force answers. Run the `good-question`
> skill first; a one-sentence mission and 1–2 *tentative* topics are a valid
> bootstrap — topics are cheap to add, rename, and delete later. The minimal
> first day is: bootstrap thin → ingest the 2–3 papers you already have
> (§3 Ingest, one at a time) → look at the portal. Everything else (corpus
> harvest, deep dives) earns its complexity only after that works.

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
│   ├── comparisons/     ← tables / matrices; benchmark pages (`type: benchmark`)
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
| `blog/` | LLM drafts on user trigger; user approves before `status: published` flip | Append-mostly; edits OK during draft phase | Only on explicit user trigger. **Canonical contract: `blog/README.md`.** Run `python blog/build.py --lint` before publishing; `python blog/build.py` after every post change. |
| `html/` | LLM | Static site; JS never writes `wiki/` or `raw/` at runtime — with ONE exception: the note widget POSTs *human* margin notes through `serve.py` into `raw/notes/web/` (human input → raw zone; read-only fetches of `wiki/entities/<slug>.md` for the references modal are OK) | Edit when the design contract in `blog/design/CHOSEN.md` changes |
| `index.md`, `log.md` | LLM | Continuously updated | Every operation |

---

## 3. Update rules

### Ingest (new source → `raw/`)
1. Place the file in the correct `raw/<subzone>/` directory. Filename: `YYYY-MM-DD_<short-slug>.<ext>` (corpus files instead follow `raw/papers/<corpus>/<VENUE>_<YEAR>/<slug>.*`).
2. Read it; discuss key takeaways briefly with the user.
3. Write/update a **source page** in `wiki/entities/` (pick the template by `entity_kind`; set `reading:` honestly).
4. Update every affected `wiki/topics/`, `wiki/concepts/`, `wiki/comparisons/` page. Flag contradictions with newer/older sources explicitly. If the paper reports a number on a tracked benchmark page, append a row to its SOTA table. If a topic's Synthesis changed *direction*, append a `## Timeline` line.
5. Update `index.md` (add the new page; revise any one-line summaries that shifted).
6. Append a `log.md` entry: `## [YYYY-MM-DD] ingest | <title>`. Commit (see Commit & recovery).

### Corpus harvest (large-scale collection → tiered digestion)
Use the **`lit-harvest`** skill. Summary: scope the corpus with the user →
collect per-venue TSVs → `dedup.py` → `download.py --pilot` → full download →
`verify.py` → tiered digestion (**anchors get full entity pages; the tail gets
1-line inline entries in the topic page**). For visually dense disciplines,
anchors' key figures are extracted to `raw/assets/` BEFORE any PDF deletion.
PDFs may be deleted after digestion (recoverable from URLs); abstracts, the
manifest, and extracted figures are permanent.

### Query (user asks a question)
1. Read `index.md` first to locate relevant wiki pages; drill in.
2. Synthesize answer with **citations to wiki pages and raw sources**.
3. If the answer is non-trivial and reusable, **file it back** as a new page (usually under `wiki/synthesis/` or `wiki/comparisons/`).
4. Append a `log.md` entry: `## [YYYY-MM-DD] query | <one-line question>`. Commit.

### Deep dive (saturating a topic)
Use the **`deep-dive`** skill: partition the topic into 4–6 sub-threads,
dispatch parallel research subagents, deep-read anchor papers, pass the
**independent reviewer gate** (a subagent that sees only the draft + raw
sources and attacks it), and file a `wiki/synthesis/<topic>-deep-dive.md`
with cross-cutting findings, evidence grades, and a "read these yourself"
list. Delete the temp working folder after consolidation — the synthesis is
canonical.

### Experiment lifecycle
1. **Start**: create `experiments/active/<YYYY-MM-DD>_<slug>/` with a `README.md` stating hypothesis, method, and success criteria.
2. **During**: intermediate saves are fine inside this dir.
3. **On completion**: produce a concise consolidation — `README.md` (final hypothesis, method, results, takeaways, 1–3 pages), `raw/` subdir (preserved data, configs, seeds, exact commands), `figures/` (final plots only). Delete intermediate scratch.
4. **Archive**: `mv experiments/active/<slug> experiments/archived/<slug>`. Freeze.
5. Update `wiki/synthesis/` or relevant topic pages. Append `log.md`: `## [YYYY-MM-DD] experiment-archived | <slug>`.

### Lint (health check; triggered, not remembered)
Run `python portal/build.py --lint` at the **end of every harvest digestion
and every deep-dive** (the skills' closing steps say so) and on request —
"every ~10 ingests" is not a memory an LLM has across sessions.

The script does the mechanical half: broken/malformed wikilinks, orphans,
duplicate slugs, frontmatter contract violations, index.md drift, stale pages
(cited but long-unupdated — a finite re-read list), merge candidates
(out-link overlap). The LLM then does the judgment half:
- **Sampling audit** — for each synthesis page touched since the last lint,
  randomly pick 5 cited claims and re-read the raw source; >1/5 wrong → set
  the page `status: stub` pending re-verification. (Same pilot-then-trust
  logic the harvest pipeline uses.)
- **Promotion** — tail entries cited ≥3 times across wiki pages → propose a
  full entity page; backlog ideas whose trigger condition has been met →
  propose promotion (see Idea lifecycle).
- Contradictions across pages, concepts mentioned but lacking a page, scratch
  lingering in `experiments/active/`.
- **Web notes** — read new entries in `raw/notes/web/` (the user's margin
  notes from the portal/blog); act on each (answer, update the page, or file
  an idea), then append `— processed YYYY-MM-DD: <what was done>` under the
  note. Never delete the notes themselves (raw zone).

Report findings; apply fixes with user approval. Log as `## [YYYY-MM-DD] lint | <scope>`. Commit.

### Pruning (Occam's Razor in action)
- A page exists only if it earns its keep: it's referenced, or it's a topic/concept entry point.
- Merge candidates come from lint (out-link Jaccard > 0.5) — an operational signal, not an unenforceable "overlap >60%" eyeball rule. The merge decision stays with LLM + user.
- Move outdated claims to `## Superseded` (any wiki page may carry one) rather than silently deleting. Every entry: `- (YYYY-MM) claim — superseded by [[y]]: reason`. **Superseding requires re-reading both raw sources** — never adjudicate from wiki-page paraphrases (First Principles).
- Delete intermediate experiment scratch on archival; never delete raw sources or archived experiment evidence.

### Idea lifecycle (capture → shape → execute)
1. **Capture**: append to `ideas/backlog.md` — date, trigger condition, 2-line sketch. Cheap; no quality bar at this stage.
2. **Shape**: when an idea gets serious, run the **`good-question`** skill against it; file the sharpened question + evidence audit back into the entry.
3. **Promote**: shaped idea + met trigger → start an experiment (see Experiment lifecycle) or a deep-dive; set `Promoted to:` in the backlog entry.
4. **Prune**: during lint, close ideas superseded or refuted by new literature (note why; don't silently delete).

### Commit & recovery (git discipline)
- **Every §3 operation ends with a commit**, message = its log prefix (e.g. `ingest | <title>`). One operation = one commit = one rollback point; never batch a day's operations into one commit.
- A wiki page went wrong → `git checkout -- <file>` (uncommitted) or `git revert <commit>` (committed). A raw file misfiled → `git mv` to the right zone + a `cleanup` log entry. Mid-operation mess → `git stash`, inspect, decide.
- `raw/` and `experiments/archived/` are append-only: fix mistakes by adding corrections, not by rewriting history.

---

## 4. Operating principles

**First Principles.** Before applying any framework or borrowing a result, ask: what is the underlying mechanism? State assumptions explicitly. When a finding seems surprising, re-derive — don't trust transitive claims.

**Occam's Razor.** Prefer the simplest structure that fits. Fewer pages, fewer directories, fewer abstractions. If a folder has one file in it for three months, it shouldn't be a folder. New zones must justify themselves with at least 3 distinct planned entries.

**Pristine record-keeping.** Raw evidence is sacred; synthesis is iterative. Once a pipeline completes, the artifact set is: (raw data, concise writeup, conclusion logged). Intermediate noise gets pruned. Archive, don't delete: working files from a finished collection phase go to an `archive/` subdir with a README, not to the trash.

**Pilot then scale.** Validate every mechanical pipeline on ~20 items before the full run. Diagnose failures from the error breakdown; never blind-retry.

**Scripts for mechanical work.** Fetching, counting, renaming at scale → Python scripts (`scripts/`). LLM agents for judgment: relevance filtering, reading, synthesis.

**Linkage over hierarchy.** Use `[[wikilinks]]` (Obsidian-style) liberally across `wiki/`. Folders are coarse zoning; meaning lives in the graph.

**Verify citations.** Sub-agent-supplied paper IDs (arXiv, DOI) newer than the model's knowledge cutoff get flagged `(unverified)` until checked against the source. But fabricated IDs are the rare failure — the common ones are misattribution (A's result filed under B) and number drift (78.3 → 87.3). Those are caught by the lint sampling audit and by requiring every number to carry its in-source location ("Table 3").

**The wiki is a map for reading, not a substitute for it.** Every deep-dive and harvest outputs a "read these yourself" list; topic pages track what the human has actually read; synthesis pages carry `human_verified:` and the portal shows it. A knowledge base that quietly replaces the researcher's own reading is a failure mode, not a feature.

---

## 5. Conventions

- **Filenames**: lowercase, hyphen-separated. Dates as `YYYY-MM-DD`. Source files in `raw/` prefixed by date.
- **Entity slugs by `entity_kind`** (a wikilink only works if the name is what people naturally write):
  - `paper`: `<firstauthor-lastname>-<keyword>-<year>` (e.g. `smith-catalysis-2026`). Surveys too — no separate survey format.
  - `method` / `dataset` / `model`: the canonical community name (`transformer`, `coco`, `sam-2`). The introducing paper may be a separate, cross-linked `paper` page.
  - `person`: `firstname-lastname` · `org`: canonical name.
- **Page frontmatter** — a machine-checked contract, not a suggestion (`python portal/build.py --lint` enforces it):
  ```yaml
  ---
  type: topic | entity | concept | comparison | benchmark | synthesis
  entity_kind: paper | method | dataset | model | person | org  # entity pages only
  venue: "VENUE YEAR"             # paper entities; feeds the portal heatmap
  track: oral                     # paper entities, optional
  reading: abstract | full-text   # paper entities: how deep it was ACTUALLY read
  status: stub | growing | stable
  human_verified: none | spot-checked | deep-read   # synthesis pages
  aliases: []                     # other names (method name vs paper name)
  tags: [your-tags]
  created: YYYY-MM-DD
  updated: YYYY-MM-DD
  ---
  ```
  There is **no `sources:` field** — backlink counts are computed by the portal build, never hand-maintained.
- **Page layouts**: templates in `meta/templates/` — entity (paper), method, dataset, topic, synthesis, comparison, benchmark, experiment. A `reading: abstract` page must not state numbers the abstract doesn't contain (mark claims "(abstract-claimed)").
- **Cross-links**: bare `[[entity-name]]` wikilinks; Obsidian resolves them. Where the *relation* is load-bearing, use the typed form — closed verb set, Dataview-compatible: `improves:: [[x]]`, `refutes:: [[x]]`, `uses:: [[x]]`, `extends:: [[x]]`. Plain `[[x]]` means "mentions". Do not invent new verbs; four is the vocabulary.
- **Timeline & Superseded**: topic pages keep an append-only `## Timeline` (one line per *directional* change of the Synthesis — polarity flip, anchor-set change, open question opened/closed). Any wiki page may carry `## Superseded`; entries have date + superseding source + reason.
- **Log entry prefix**: `## [YYYY-MM-DD] <op> | <subject>` (parseable: `grep "^## \[" log.md`). Ops: bootstrap, ingest, query, synthesis, experiment-archived, lint, blog, harvest, cleanup.
- **Citations in synthesis**: `([[entity-slug]], Table 3)` — always with the in-source location, so a spot-check is O(1). Claims carry evidence grades per the synthesis template: **[source-backed] / [inference] / [unknown]**.

---

## 6. Tool & resource management

### Local project skills (`.claude/skills/`)
| Skill | When to use | Typical scale / precondition |
|---|---|---|
| `lit-harvest` | Systematic multi-venue corpus: scope → collect → dedup → download → verify → tiered digestion. | 100s–1000s of papers. For a **30–50 paper reading list** (the everyday mid-size need), run it with a single collection TSV and skip the pilot. |
| `deep-dive` | Saturating one topic: parallel subagent sweep → anchor deep-reads → reviewer gate → synthesis page. | 8–15 anchors; most useful after some entities/corpus exist. |
| `paper-sweep` | Periodic "what's new" discovery sweep; tiered ingestion of the winners. | Recent window (weeks–a month). Checks manifest + entities first — never double-files a paper the corpus already has. |
| `good-question` | Shaping / stress-testing a research question, hypothesis, or direction — including at bootstrap when the direction is undecided. | Any time; needs no corpus. |
| `research-to-blog` | Turning a paper / synthesis / topic into a diagram-first blog post (canvas DSL); stops at the draft gate. | Needs the artifact to exist in `wiki/` or `raw/`. |

### Generic agents & skills (host-provided)
Use `Explore` for repo search, `general-purpose` for open-ended multi-step web
research, `Plan` for implementation strategy. Useful host skills when present:
`pdf` (extract text/tables from papers), `pptx`/`theme-factory` (decks),
`doc-coauthoring`, `deep-research` (fan-out fact-checked reports),
`webapp-testing` (Playwright verification of the html layer).

### Project scripts (stdlib-only; no installs required)
Invoke with `python` (`py -3` also works on Windows; bare `python3` is often a
Microsoft Store stub there).
- `scripts/harvest/{dedup,download,verify}.py` — corpus pipeline. All manifest I/O goes through `scripts/harvest/manifestio.py` (schema, UTF-8, atomic writes — single source of truth; see `scripts/harvest/README.md`). Tests: `python -m unittest discover scripts/harvest/tests`.
- `blog/build.py` — walks `blog/posts/*.md` → `blog/index.json`. Modes: `--include-drafts`, `--lint`, `--strict`.
- `portal/build.py` — walks `wiki/` + `ideas/` + `log.md` → `html/portal/index.json` (pages, backlinks, typed-link graph, stats, orphans, broken links) **and the mechanical half of lint** (frontmatter contract, malformed wikilinks, index.md drift, stale pages, merge candidates). `--lint` reports only; `--strict` fails on findings.
- `serve.py` — the local workbench server: `python serve.py` (defaults to port 8765) → blog at `/html/index.html`, portal at `/html/portal/index.html`. Also exposes the web-notes API: notes written on blog posts / wiki pages append to `raw/notes/web/<ctx>-<slug>.md`. Plain `python -m http.server 8765` still works, but notes then stay in the browser (localStorage + export button).
- `scripts/template_sync.py` — **template–content separation**: publishes template-grade changes (scripts, portal, html, skills, meta, docs) to the git remote named `template`, never research content. Content zones aren't in its copy manifest; the four mixed files (CLAUDE.md §0, index.md, log.md, backlog) are swapped for pristine forms from `meta/template-state/`; a leakage guard aborts if any wiki/raw/experiments/blog-posts path gets staged; the harvest tests + both builds + strict lint run inside the worktree before commit. Dry-run by default; `--push` to publish. **Never `git push template` directly from this repo** — always go through the script. When you improve a template file mid-research, note it and sync at a natural pause.

### Obsidian plugins (user installs manually; optional)
**Dataview** (frontmatter queries, dashboards) and **Templater** (page templates from `meta/templates/`).

---

## 7. Workflow quick-reference

- **"Bootstrap this repo for <discipline>"** → §0 bootstrap protocol.
- **"I don't know my direction yet"** → `good-question` skill first, then a thin bootstrap (1–2 tentative topics).
- **"Add this paper"** → ingest flow (§3).
- **"Build me a reading list on X (~30–50 papers)"** → small `lit-harvest` (single collection TSV, skip pilot); anchors get entity pages.
- **"Collect all papers on X from venues Y"** → `lit-harvest` skill.
- **"What's the state of X?"** → query flow (§3); file the answer back if substantive.
- **"Go deep on topic X"** → `deep-dive` skill.
- **"What's new this month?"** → `paper-sweep` skill.
- **"Is this a good research question?"** → `good-question` skill (Idea lifecycle §3: capture → shape → promote).
- **"Start an experiment on Y"** → experiment lifecycle (§3).
- **"Capture this idea"** → append to `ideas/backlog.md` with date and trigger condition.
- **"Something in the wiki broke / got mangled"** → Commit & recovery (§3): `git checkout`/`revert`, then lint.
- **"Health check"** → lint flow (§3) + `python portal/build.py --lint`.
- **"Summarize recent work"** → `grep "^## \[" log.md | tail -N`.
- **"Turn this research into a webpage / diagram-first post"** → `research-to-blog` skill (never auto-publishes).
- **"Publish this to the blog"** → `blog/README.md` §6 pre-publish checklist; wait for the user's explicit go-ahead.

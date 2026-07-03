# blog/

Public-facing writing surface for deep-lr. The homepage at
`/html/index.html` and the post page at `/html/post.html` read everything in
this directory; nothing here is server-rendered.

**This file is the single source of truth** for: the upload-trigger protocol,
the frontmatter contract, the renderer's expectations on post structure, the
expectations on cited wiki entities, and the maintenance commands. Keep it
canonical — do not duplicate this content into the plan file, CLAUDE.md, or
PM design docs.

---

## 1. Upload-trigger protocol (strict)

The blog is curated. Posts only land here when the **user** triggers them.
Claude's job is to *propose* — never to publish autonomously.

| When Claude should propose | When Claude must NOT propose |
|---|---|
| A multi-turn thread reaches a natural conclusion that's reusable in future work | After every routine query / micro-task |
| A wiki synthesis lands that is self-contained and citation-ready | While the thread is still mid-exploration |
| A paper-skim batch wraps with a defensible position | When the conclusion isn't settled |
| A finished experiment produces a concrete takeaway | As a way to "save" intermediate state |

**How Claude proposes**, in one line:

> "this thread wrapped up a substantive line on [topic]; want me to draft a
> blog post for the [category] section? (~600 words, ~5 citations)"

**What happens after the user says yes:**

1. Claude drafts `blog/posts/<slug>.md` with `status: draft`.
2. User reviews; iterates with Claude on the draft.
3. User says publish. Claude flips `status: draft → published` and runs the
   pre-publish checklist (§6).
4. `python3 blog/build.py` regenerates `index.json`. Post appears on the
   homepage.

**Hard rules:**

- No auto-publish. Ever. The user types the word "publish".
- No nag re-asks. One offer per natural endpoint; if the user passes, drop it
  unless they re-engage the topic.
- Status `published` is a contract: it means the user has read the rendered
  page end-to-end and signed off.

---

## 2. Layout

```
blog/
├── README.md          ← this file (canonical contract)
├── categories.json    ← category slug → label / accent / blurb
├── build.py           ← regen index.json + lint citations
├── index.json         ← generated catalog (do not edit by hand)
├── posts/             ← one markdown file per post; filename = <slug>.md
├── assets/            ← images / figures referenced by posts
└── design/            ← PM design docs + mockups (frozen reference)
```

The rendered site lives in `/html/`:

| File | Role |
|---|---|
| `html/index.html` | Catalog of all published posts (PM-B "Index-archive") |
| `html/post.html` | Single post viewer (PM-C "Readable"), reads `?slug=…` |
| `html/lib/style.css` | All visual tokens; shared across both pages |
| `html/lib/blog.js` | Catalog rendering + post renderer + references modal |
| `html/lib/markdown.js` | `marked.js` (CDN) + thin wrapper for `[[wiki]]` syntax |

The site is fully static. The only external runtime dependency is `marked.js`,
loaded once per post page from a CDN.

---

## 3. Frontmatter contract

Every post in `blog/posts/` must begin with a YAML-ish fence:

```markdown
---
title: Agent Challenges — Why No System Closes the Loop on OOD Learning
date: 2026-05-17
slug: agent-challenges
category: paper-research
status: draft
dek: 11 challenges across memory, retrieval, belief tracking, self-evolution.
tags: [ood, memory, self-evolution]
focus_label: KEY FINDINGS
---
```

| Key | Required | Notes |
|---|---|---|
| `title` | yes | Headline. Use em-dash for subtitle, not colon. |
| `date` | yes | `YYYY-MM-DD`. Affects sort + year dividers on the catalog. |
| `slug` | yes | Lowercase kebab-case. **Must match the filename** (`<slug>.md`). |
| `category` | yes | One of the keys in `categories.json`. |
| `status` | yes | `draft` or `published`. Drafts excluded from the public index. |
| `dek` | optional | One-sentence summary. Shown on catalog row + post header. ≤140 chars. |
| `tags` | optional | List of short slugs. Compact display: first 2 + "+N". |
| `focus_label` | optional | Label shown above the focus block. Defaults to `THE GIST`. |

Reading time is computed by `build.py` (220 wpm) — never declared.

---

## 4. Post-body conventions (PM-C "Readable" renderer)

The post renderer post-processes the rendered HTML in six stages. The author
writes plain markdown; the renderer applies the structure.

### Stage 1 — Focus block (the first H2)

If the **first** `<h2>` is named `Key findings`, `The gist`, `TL;DR`, or
`Bottom line up front` (case-insensitive), it (and everything up to the next
H2) is lifted into the tinted card at the top. The H2 itself is dropped; the
content is rendered as a bulleted list.

```markdown
## Key findings

- finding 1 ...
- finding 2 ...
- finding 3 ...
```

If you don't want a focus block, just start with a numbered section heading.

### Stage 2 — Numbered sections

Every other `<h2>` becomes an entry in both the inline TOC (top of body) and
the sticky left-rail side-TOC. Convention: prefix headings with `N.` for the
in-body reading cue; the renderer strips the number for TOC display.

```markdown
## 1. Motivation
## 2. The eleven challenges in one screen
## 3. Compositional retrieval is the bottleneck
```

A post with no body H2s renders without TOCs (single-section essay).

### Stage 3 — Citations: `[[slug]]`

Use Obsidian wikilink syntax. The renderer:

1. De-duplicates by slug; each unique slug gets a stable number `[N]`.
2. Inserts a `<sup>[N]</sup>` at every occurrence.
3. Generates a numbered References block at the end of the post.
4. **Asynchronously fetches `/wiki/entities/<slug>.md`** and replaces the
   slug placeholder with: title + authors + venue + arxiv/openreview/pdf
   badges. Clicking the title opens a popup with the entity's `## TL;DR`.

For (4) to render nicely, the cited entity file must contain (see §5):
- `# Title` (H1)
- `**Authors:**` line
- `**Venue:**` line
- `## TL;DR` section
- At least one of: `openreview.net/...`, `arxiv.org/abs/...`, or `[pdf](...)` URL

Citation forms supported:
- `[[zou-reducing-2026]]` — slug only
- `[[zou-reducing-2026|T³]]` — slug with display alias (alias currently
  ignored by the numbering pass, but reserved for future use; safe to write)

### Stages 4–6

- Inline + side TOC built from section list (Stage 4).
- Side-TOC scroll-coupled visibility: hidden while inline TOC is in viewport,
  fades in once you scroll past the inline TOC (Stage 5).
- Smooth-scroll on every in-page anchor click; ESC closes reference popup
  (Stage 6).

---

## 5. Wiki entity expectations

Every `[[slug]]` citation in a post **resolves to** `wiki/entities/<slug>.md`.
For the references modal to render the full popup, the entity file should
look like this:

```markdown
---
type: entity
entity_kind: paper
venue: ICLR 2026
track: oral
themes: [...]
---

# Reducing Belief Deviation in RL for Active Reasoning of LLM Agents (T³)

**Authors:** Zou, Deyu; Chen, Yongqiang; Wang, Jianxiang; …
**Venue:** ICLR 2026 (**oral**) · **ID:** `ICLR_2026_440` · **Slug:** `zou-reducing-2026`
**Links:** [openreview](https://openreview.net/forum?id=r8hzDA3pUY) · [pdf](https://openreview.net/pdf?id=r8hzDA3pUY) · local: `raw/papers/.../zou-reducing-2026.pdf`

## TL;DR
Identify **belief deviation** — internal beliefs drifting from true state — as
the dominant failure mode of LLM RL agents in multi-turn active reasoning. **T³**
detects excessive deviation and truncates training trajectories to keep credit
on informative prefixes.

## Problem
...
```

| Field | What the renderer extracts |
|---|---|
| `# Title` | First H1 → modal title + references row title |
| `**Authors:**` | Comma/semicolon list → compacted to "Surname, Surname et al." |
| `**Venue:**` | Up to first `·` → modal eyebrow + ref row meta |
| `arxiv.org/abs/<id>` | First match anywhere → `[arxiv]` badge |
| `openreview.net/forum?…` | First match → `[openreview]` badge |
| `[pdf](https://…)` | First match → `[pdf]` badge (only shown if no arxiv/openreview) |
| `## TL;DR` | Section body → popup body (inline `**bold**` + `` `code` `` preserved) |

If an entity file is missing or lacks these fields, `build.py --lint` warns
and the references row falls back to the slug-only display. **Fix the entity,
not the post.**

---

## 6. Pre-publish checklist

Before flipping a post from `draft` to `published`:

```bash
# 1. lint the post + its citations
python3 blog/build.py --include-drafts --lint

# 2. fix any warnings (missing entities, missing TL;DR/Authors/Venue/link in entities)

# 3. open the draft and read it end-to-end in the rendered view
python3 blog/build.py --include-drafts
open "http://127.0.0.1:8765/html/post.html?slug=<slug>"

# 4. visual gate (eyeball, not automated):
#    - focus block reads as the "15-second decide-to-dive-in" hook
#    - section numbering in TOC matches body
#    - every citation popup has a real title + TL;DR + at least one link
#    - no console errors

# 5. flip the status in the markdown frontmatter:
#    status: draft  →  status: published

# 6. regen the public index (drops drafts, includes the freshly-published post)
python3 blog/build.py

# 7. confirm it appears on the homepage
open "http://127.0.0.1:8765/html/index.html"
```

For a stricter publish gate (treat citation warnings as errors):

```bash
python3 blog/build.py --strict
```

---

## 7. Categories

| Slug | Label | Accent | What goes here |
|---|---|---|---|
| `final-idea` | final idea | `#B0552A` (terracotta) | Research positions that have settled enough to publish |
| `deep-conversation` | deep conversation | `#3A6E5B` (forest) | Multi-turn exchanges that produced something worth keeping |
| `paper-research` | paper research | `#3B5A8C` (slate) | Distillations of the wider literature |

To add a category, edit `categories.json` and re-run `build.py`. The homepage
filter chips and post-detail accents pick up the new category automatically.

**Don't proliferate categories.** Three is enough until the catalog passes ~30
posts. Adding a fourth requires (a) at least 3 planned posts that don't fit
the existing three and (b) a clear blurb that differentiates it from the
others.

---

## 8. Maintenance

| Command | When to run |
|---|---|
| `python3 blog/build.py` | After every post add / edit. Drops drafts. |
| `python3 blog/build.py --include-drafts` | Local preview including drafts. |
| `python3 blog/build.py --lint` | Pre-publish citation lint, no write. |
| `python3 blog/build.py --strict` | Publish gate: warnings → errors. |

**What lint catches** (warnings, not errors by default):

- `[[slug]]` citations whose `wiki/entities/<slug>.md` doesn't exist.
- Cited entities missing H1 / Authors / Venue / TL;DR / arxiv-or-openreview-or-pdf link.

**What validation catches** (always errors):

- Missing required frontmatter keys.
- `slug` that doesn't match the filename.
- `category` not in `categories.json`.
- `date` not in `YYYY-MM-DD` format.
- `status` not `draft` or `published`.

**What is NOT checked** (and is on the author):

- Whether the post is actually good.
- Whether the focus block earns its 15-second hook.
- Whether the section structure makes sense.
- Whether tags are coherent across the catalog.

---

## 9. Design docs (frozen reference)

| File | What it specifies |
|---|---|
| `design/PM-B.md` + `PM-B-mockup.html` | Homepage (catalog) — visual + layout spec |
| `design/PM-C.md` + `PM-C-mockup.html` | Post detail page — visual + layout spec (§5 references and §7 side-TOC animation both overridden by `CHOSEN.md`) |
| `design/CHOSEN.md` | Decisions of record + as-built deltas. Append a new dated section on any future design change rather than editing the PM docs. |

---

## 10. Canvas blocks (diagrams)

The post renderer turns a fenced `canvas` code block into a themed `<figure>` —
zero new dependencies, auto-themed to the post's category accent. The renderer
is `html/lib/canvas.js`, wired as **stage 0** of `renderPost` (before the
focus/TOC/citation passes). Authoring is a flat, line-oriented DSL an LLM can
emit reliably.

````markdown
```canvas
type: <matrix|timeline|flow|bars|grid>
caption: short caption (supports **bold**, *italics*, `code`, [text](url))
source: arXiv 2512.16301        # optional provenance tag, right-aligned in caption
accent: paper                   # paper | deep | final (default: paper)
<body rows — format depends on type>
```
````

**Primitives**

| `type` | body row syntax | use for |
|---|---|---|
| `matrix` | `rows: A \| T` · `cols: …` · then `r,c :: cell md` (1-based) | 2×2 / N×M tables. Single-letter rows auto-tag cells `A1/A2/T1/T2`. |
| `timeline` | `label \| title \| subtitle` (one node per row) | evolution / chronology lanes |
| `flow` | `A -> B -> C` · `loop: X -> Y \| label` · `state: A=trained, B=frozen` · `note: …` | `Input→Agent→Tool→Reward` loops |
| `bars` | `axis: A \| B` then `label \| valA \| valB` (values 0–100) | two-series trade-off comparisons |
| `grid` | `cols: N` then `title :: body` (one card per row) | application-domain card decks |

**Hard rules**

1. **Never write `[[slug]]` inside a canvas block.** The citation expander
   (`markdown.js`) rewrites it *before* marked parses and it becomes inert
   escaped text that corrupts the cell. Use `[text](url)` instead. `build.py`
   strips fences before linting so a stray `[[slug]]` here won't false-warn.
2. Cell/caption markdown supports only `**bold**`, `*italics*`, `` `code` ``,
   and `[text](url)`. No raw HTML, no images, no nested fences.
3. A malformed block **degrades to its original visible code block**
   (`pre[data-canvas-error]`, dashed outline) — it never blanks the page.

**Why it's safe:** figures emit no `<h2>` and no `a.wiki-cite`, so the
section-numbering, TOC, citation-numbering, and scroll-spy stages all skip
them. Canvas content is excluded from reading-time automatically (fenced blocks
are stripped in `build.py`). All SVG/grid markup is constructed by the renderer;
author strings are escaped then passed through the minimal inline-md pass only.

**Considered and rejected: Mermaid.js.** It would add a second mid-size CDN
runtime dependency against the vanilla design value, has no first-class 2×2
primitive (the central artifact for taxonomy posts), and themes poorly against
the system-font / hairline house style. The five hand-built primitives cover
every diagram we need at zero dependency cost. (Design record: the canvas
component was specced by a 3-PM / 2-engineer / synthesis pass on 2026-06-03, then
visually redesigned via a 2-researcher / 4-mockup / synthesis pass on 2026-06-04
— Mermaid re-evaluated and rejected again. Decisions + the 4 rendered mockup
directions are in `design/CHOSEN.md` and `design/canvas-explorations/`.)

**Rendering (v2, 2026-06-04) — editorial + depth.** The look is hand-authored
inline SVG + CSS (no library): dot-grid figure ground, layered tinted shadows,
per-column accent tints, icon tag pills, semantic *trained* (elevated + flame)
vs *frozen* (flat + dashed + snowflake) state, gradient feedback loops with
knockout label-plates, era-graded timelines. **The DSL above is unchanged** —
v2 is a renderer-only upgrade. Two authoring conveniences the renderer derives
automatically (still no DSL change):

- In a `matrix`/`flow` cell, a leading `**bold**` becomes the card **title**,
  inline `` `code` `` spans become example **chips**, and the rest is the body —
  so write cells as `**A1 · Title** — method text. \`Model\`, \`Model\``.
- Single-letter `matrix` rows render a friendly name (`A`→Agent, `T`→Tool,
  `M`→Memory, `S`→Skill) while still auto-tagging cells `A1/T2/…` from the letter.
- `timeline` subtitles ending in `(XXX)` render `XXX` as a method pill under the
  node (e.g. `... trace ranking (DPO)` → a `DPO` pill).

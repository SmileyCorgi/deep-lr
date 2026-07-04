# Chosen design: PM-B · Index-archive

**Decided by**: project owner
**Date**: 2026-05-17
**Decision**: Build to PM-B's spec as-is. No hybrid moves requested. PM-A (editorial direction) was rejected; its docs have been removed as the decision is final.

## Why PM-B

User feedback verbatim: *"我更喜欢PM-B设计的，这个很好"* — direct preference for the index-archive direction over the editorial direction. No further constraints or hybrid asks.

## Implementation source of truth

- **Design doc**: `blog/design/PM-B.md` — read end-to-end before writing code; sections 4 (tokens), 5 (category nav), 7 (mobile collapse) are the most prescriptive.
- **Visual reference**: `blog/design/PM-B-mockup.html` — open in browser to confirm interpretation. Reuse the inline CSS as the starting basis for `html/lib/style.css`; reuse the vanilla-JS filter/sort logic as the starting basis for `html/lib/blog.js`.

## Carry-forward open questions (defer, don't decide yet)

- **Tag-based filter view**: PM-B proposed introducing one when the catalog passes ~30 posts. Not part of v1. Don't build tag UI now; do emit tags into `index.json` so the future view has data to consume.

## What this decision does NOT cover (still TBD post-build)

- First-post content draft (Phase E). The dev build only needs to render an empty-or-near-empty catalog correctly; first post writing happens after the site is verified.
- Hosting / deploy story. Local-first for now (`python -m http.server` from repo root).

---

# Chosen design (post-detail evolution): PM-C · Readable

**Decided by**: project owner
**Date**: 2026-05-17 (Phase G, after first-post review)
**Scope**: post-detail page only (`html/post.html`). Homepage stays PM-B as-is.

## Decision

Approve PM-C with **one explicit refinement** to the side-TOC behavior (overriding PM-C §7 "no appear/disappear animation"):

### REFINEMENT — side-TOC scroll-coupled visibility

**User spec verbatim:** *"the side-TOC can follow me if I scroll the page. The animation will be like: if there is index in the page it will not show. But if I scroll down to content and the index not there, the side index will appear and follow my scroll until the index returns."*

Translated to implementation:
1. The side-TOC is **hidden by default** when the page first loads (because the inline TOC is in viewport above the body).
2. As the user scrolls down, the moment the inline TOC leaves the viewport, the side-TOC **fades in** (opacity 0→1, small `translateX(-6px)→0` slide) over ~180–220ms ease-out, then sticks to the viewport.
3. While the inline TOC is out of viewport, the side-TOC remains visible and tracks the active section (existing scroll-spy from PM-C §7).
4. As soon as the user scrolls back up and the inline TOC re-enters the viewport, the side-TOC **fades out** with the inverse transition.
5. Mechanism: an Intersection Observer on the inline-TOC element. `aria-hidden` + `opacity` + `transform` toggles. No layout shift, no scroll jank.

Avoid visible "popping" — the transition should feel like the rail is **handing off** with the inline TOC, not appearing/disappearing.

## Resolved open questions

- **References format**: ship **slug-only** (per PM-C mockup default). Entity titles can be a future enhancement; out of scope for v1.

## Implementation source of truth

- **Design doc**: `blog/design/PM-C.md` — read end-to-end. §4 (focus block), §5 (citations + de-dup), §6 (inline TOC), §7 (side-TOC) are prescriptive. **§7's "no appear/disappear animation" is overridden by the refinement above.**
- **Visual reference**: `blog/design/PM-C-mockup.html` — open to confirm focus-block, references, scroll-spy behavior. Replicate everything except the always-visible side-TOC.
- **Existing site**: `html/post.html`, `html/lib/blog.js` (`renderPost`), `html/lib/style.css`, `html/lib/markdown.js`. Modify in place — do NOT touch the homepage.

## What this decision does NOT cover

- Migrating other future posts to the new structure — the convention is documented in PM-C §8 (authoring); the only existing post (`agent-challenges`) already conforms (it starts with `## Key findings`).
- Re-running `build.py` — `focus_label` (optional new frontmatter key) defaults to `THE GIST`; existing posts work without changes.

---

# As-built (2026-05-18)

PM-C §5 ("slug-only references") was superseded post-launch. References now
render as **title + authors + venue + [arxiv]/[openreview]/[pdf] badges**,
with a click-to-open popup showing the entity's `## TL;DR`. The renderer
fetches `/wiki/entities/<slug>.md` async and falls back to the slug if any
field is missing.

Also fixed during shake-out: side-TOC `position: sticky` had no room to
operate because `.post-layout` used `align-items: start` (sized cells to
content). Fix in `html/lib/style.css`: `align-items: stretch` on the layout
+ `align-self: stretch` on the side-TOC column.

The **canonical contract** for both is `blog/README.md` (§5 wiki-entity
expectations, §6 pre-publish checklist). PM-C / PM-B docs above remain
frozen as the original design narrative.

---

# Chosen design (canvas component): zero-dep declarative DSL

**Decided by**: project owner (via a 3-PM / 2-engineer / synthesis design pass)
**Date**: 2026-06-03
**Scope**: a new diagram/figure embed for posts (`html/lib/canvas.js`). First use: the arXiv 2512.16301 adaptation-survey post.

## Decision

Ship a fenced ```` ```canvas ```` block parsed by a new vanilla-JS renderer into themed inline-SVG / CSS-grid `<figure>`s. **Five primitives:** `matrix`, `timeline`, `flow`, `bars`, `grid`. **Zero new runtime dependencies.**

Chosen from three PM concepts: **Concept 1 (declarative DSL → renderer-built SVG/HTML)** as the core, hybridized with two low-risk borrowings from Concept 3 (auto "Figure N" numbering + an optional `source:` provenance tag, and the multi-panel `grid`). **Concept 2 (Mermaid.js) was rejected** — both engineering reviews scored vanilla **8.5** vs Mermaid **4.5**; Mermaid adds a mid-size CDN dep against the house "marked.js is the sole runtime dependency" value, has **no first-class 2×2 primitive** (the survey's load-bearing artifact), and themes poorly against the system-font/hairline aesthetic. Concept 3's raw-`svg`/`image` escape hatches and the lightbox were **deferred** out of v1 (they are the only XSS / overlay surface).

## As-built

- New file `html/lib/canvas.js` (IIFE → `window.BlogCanvas.render`). DOM built via `createElement`/`createElementNS`; author strings escaped then passed through a `**bold**`/`*italic*`/`` `code` ``/`[text](url)` inline pass (mirrors the `openRefModal` idiom). No `innerHTML` of an unescaped string.
- `html/lib/blog.js`: one line in `renderPost` — `if (window.BlogCanvas) window.BlogCanvas.render(bodyEl);` immediately after `bodyEl.innerHTML = html;` and before `liftFocusBlock`. Stage 0; synchronous; figures carry no `<h2>`/`a.wiki-cite` so all downstream stages skip them.
- `html/post.html`: `<script src="/html/lib/canvas.js" defer>` before `blog.js`.
- `html/lib/style.css`: `.canvas` figure frame + figcaption + matrix/grid CSS-grid + `data-accent → --c` + 640px matrix stack (keeps A1/A2/T1/T2 tags) + reduced-motion no-op. Existing tokens only; no new box-shadow.
- `blog/build.py`: `lint_citations` strips ```` ``` ```` fences before `CITE_RE` (symmetric with `reading_time`), so a stray `[[slug]]` in a canvas caption is inert.
- Contract documented in `blog/README.md` §10.

**Open item deferred to a fast-follow if needed:** raw-`svg`/`image` canvas types + a click-to-zoom lightbox (the original Concept 3 "drop in any good-looking figure" surface). v1 covers all four survey diagrams with the five DSL primitives; revisit only if a post needs a bitmap/effect image the DSL can't express.

---

# Canvas v2 — visual redesign (editorial + depth)

**Decided by**: project owner (picked from 4 rendered mockups)
**Date**: 2026-06-04
**Trigger**: v1 render was rejected as "just a box + a bunch of text, you can't see anything clearly" — a wireframe, not a finished diagram.

## Process

A research + mockup workflow: 2 researchers (diagram-rendering landscape + premium-diagram design techniques, web-sourced) → 4 engineers each building a fully-rendered standalone HTML of the *same* three survey diagrams (2×2 / flow / timeline) in a distinct aesthetic direction → a design-lead synthesis. The four directions are frozen at `blog/design/canvas-explorations/{A-handdrawn,B-product-depth,C-editorial,D-mermaid-themed}.html`.

**Ranking** (design-lead + user): **C Editorial/Distill 9.2** · B Product-depth 8.6 · A Hand-drawn (rough.js) 6 · D Mermaid 3.2.

**Mermaid rejected again, on first principles for this task**: ~1 MB gzipped (100–200× the marked.js-only footprint) for fixed-content figures; its default output *is* the wireframe failure mode; and it has no native 2×2 — which is the load-bearing artifact. Research consensus (Distill, Lil'Log): top-tier publications hand-author SVG and reserve auto-layout for throwaway sketches.

## Decision

**User picked the Hybrid C+B** (recommended): Direction **C (editorial/Distill)** as the structural spine — axis labels, Trained/Frozen/Reward legend, figure captions, color-coded columns, exquisite legibility — **plus Direction B's depth kit** — layered tinted shadows, gradient/accent icon tag pills, semantic state (trained = elevated + flame badge; frozen = flat + dashed + snowflake badge), gradient feedback loop with a knockout label-plate.

**Key insight (the reason this is a renderer-only change):** the complaint was a *rendering-quality* deficit, not an architecture or authoring-language gap. The `canvas` DSL already encodes every semantic the premium mockups display (accent → `--c`, single-letter rows → auto-tag, `state:` → trained/frozen, `loop:` + label, captions, `source:`). v1 just rendered it flat. So v2 upgrades only the visual layer.

## As-built (zero new deps; DSL 100% unchanged)

- `html/lib/canvas.js` rewritten **rendering layer only** — same parser, same DSL. New: a `<defs>` injector (two-layer `feDropShadow`, uid-suffixed markers), a lucide-ish inline-SVG icon set (`agent`/`tool`/`reward`/`input`/`memory`/`flame`/`frozen`) keyed by a name heuristic, a `parseCell()` that splits a matrix/flow cell's `**title**` / body / `` `code` `` chips for richer layout (no DSL change), and per-accent concrete hex maps (`ACCENT_SOFT`/`_SOFTSTROKE`/`_DK`) because `color-mix()` isn't reliable in SVG presentation attributes. Single-letter matrix rows get friendly display names via `ROW_ALIAS` ({A:Agent, T:Tool, M:Memory, S:Skill}) while the auto-tag still derives from the raw letter.
- `html/lib/style.css` canvas block fully replaced: dot-grid figure ground, layered `--cv-shadow` token, `.cv-matrix` (relative wrapper + inner `.cv-matrix-grid`, absolute axis labels, rotated row headers), `.cv-cell` (per-cell `--qc` accent tint + rail + depth), `.cv-tag` icon pills, `.cv-legend`, `.cv-grid`/`.cv-card`. Responsive matrix collapse keeps the A1/A2/T1/T2 tags; reduced-motion preserved.
- **No change** to `blog.js`, `markdown.js`, `build.py`, the DSL, or any post. The existing `adapting-agents-mapped` post rendered dramatically better with zero edits.

Verified headless (Playwright) against the live post: 9 figures, all five primitives, auto-tags, 2-line timeline wrap, mobile matrix collapse with tags intact, 0 console errors, 0 degraded blocks. Crops archived during review.

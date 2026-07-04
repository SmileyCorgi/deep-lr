---
name: research-to-blog
description: Turn a research artifact (arXiv paper/URL/PDF, a wiki synthesis or entity page, a topic, or a finished thread) into a diagram-first blog post on this repo's static site — minimal prose, maximal canvas diagrams. Use when the user says things like "turn this paper/survey/research into a webpage/blog post", "make a diagram-heavy post about X", "把这篇研究做成网页/博客", or activates the research→webpage need. Analyzes the source, maps its structure to canvas primitives, drafts the post, verifies the render headless, and stops at the draft gate (never auto-publishes).
---

# Research → Blog (diagram-first)

Convert research into a **published-quality, diagram-first** post for the repo's
blog (`blog/posts/*.md`, rendered by `html/post.html`). The house style is
**minimal text, maximal diagrams** authored in the `canvas` block DSL.

## Operating principles

- **Diagrams carry the argument; prose connects them.** One or two sentences per
  section, then a `canvas` figure. If a paragraph restates what a diagram shows, cut it.
- **The renderer is already premium — author data, not pixels.** `html/lib/canvas.js`
  (v2, editorial+depth) handles shadows, color-coding, icons, state, layout. Your job is
  to pick the right primitive and feed it clean DSL. Never hand-build SVG/HTML in a post.
- **Faithful, not embellished.** Diagram only what the source supports. If a chart is a
  qualitative reading (e.g. a trade-off the paper states directionally, not as numbers),
  say so in the caption.
- **Never auto-publish.** Draft → user reads the rendered page → user says "publish".
  See `blog/README.md` §1 and §6.
- If the user writes in Chinese, respond in Chinese unless asked otherwise.
- Read the canonical contracts before writing: `blog/README.md` (frontmatter §3, post
  conventions §4, citations §4/§5, **canvas DSL §10**, pre-publish §6) and `CLAUDE.md` §3
  (ingest/query flow). This SKILL summarizes; those files win on conflict.

## Inputs accepted

arXiv abstract/PDF URL · a local PDF in `raw/papers/` · a `wiki/` synthesis or entity
page · a topic name · a wrapped-up conversation/thread. If the source is ambiguous or
multiple, ask one short question; otherwise proceed.

## Two house styles

| Style | When | Shape |
|---|---|---|
| **Distillation** (default) | 单篇论文 / 单个 synthesis 的浓缩 | 4–9 figures，极简散文，图带论证 |
| **Tutorial**（教学长文，Lilian Weng 式） | 用户要"全面的教学类"文章覆盖一个技术领域 | 10–14 编号节、10–13 figures；每节 1–3 句 + 图 + **坑/误解**拆解；倒数第二节"学习地图"收束（自查清单 + 深挖阅读路径 + 经典博客延伸阅读映射表）；末节按主题分组的完整文献清单。骨架：`meta/templates/blog-post-tutorial.md` |

Tutorial 风格的硬约定（实测踩坑，模板注释里有完整清单）：无 LaTeX（公式用
行内代码）；matrix rows 用**多字母**标签（单字母 A/T/M/S 会被渲染器自动
别名成 Agent/Tool/Memory/Skill）；`[[entity]]` 只给会反复引用的锚点论文，
长尾文献用文末分组的普通链接；中英混排后检查形近非 ASCII 字符（如西里尔
字母）混入；成稿后对照相关经典博客（如 Lilian Weng 归档）把互补文章编成
映射表并做内联指引。

## Pipeline

### 1. Analyze the source
- Fetch/read it. For a long paper, prefer the arXiv HTML (`arxiv.org/html/<id>`) and/or a
  research subagent; extract: the **central framework/taxonomy**, the **evolution/timeline**,
  key **entities** (methods/systems/people) with years, **trade-offs/comparisons**,
  **application domains**, and **open problems**. Note any headline numbers and named figures.
- Decide the post's **thesis** (the one-line "why this matters") and a 3–5 bullet gist.

### 2. Map structure → canvas primitives
Pick the primitive that matches the *shape* of each piece of content:

| Source content shape | Canvas primitive |
|---|---|
| A 2×2 / N×M taxonomy, classification, quadrant framework | `matrix` (load-bearing — make it the hero) |
| Chronology / evolution / objective arc / version history | `timeline` |
| A process, pipeline, training loop, or feedback cycle | `flow` (use `state:` for trained/frozen, `loop:` for feedback) |
| A two-way comparison along several dimensions | `bars` (values 0–100; label qualitative readings as such) |
| An enumeration: domains, challenges, methods, contributions | `grid` (card deck) |

Aim for **4–9 figures**. If a section has no diagrammable shape, keep it to a sentence or fold it in.

### 3. Ingest the source as a wiki entity (so citations resolve)
- Create/update `wiki/entities/<slug>.md` per `blog/README.md` §5 (needs `# Title`,
  `**Authors:**`, `**Venue:**`, `## TL;DR`, and one arxiv/openreview/pdf link). Survey slug
  convention: `YYYY_author_short`. This makes the post's `[[slug]]` citation render in the
  references modal. Update `index.md` (Surveys/Entities) and append a `log.md` ingest line.

### 4. Draft the post
- Write `blog/posts/<slug>.md` with the frontmatter contract (§3): `title` (em-dash subtitle,
  not colon), `date`, `slug` (== filename), `category` (`paper-research` for distillations),
  `status: draft`, `dek` (≤140 chars), `tags`, optional `focus_label`.
- First H2 = the focus block: name it `## The gist` (or Key findings / TL;DR / Bottom line up front).
- Each numbered `## N. …` section: 1–2 sentences + one or more `canvas` blocks.
- Citations: `[[entity-slug]]` in PROSE only. **Never put `[[ ]]` inside a canvas block** —
  use `source:` + plain text / `[text](url)` instead (see §10). Cite only entities that exist.
- Author the canvas blocks with the cheat-sheet below; lean on the auto-conveniences
  (bold title + `code` chips, single-letter row aliasing, timeline `(XXX)` method pills).

### 5. Verify the render (do not skip — this is why v1 looked flat)
```bash
python blog/build.py --include-drafts --lint     # 0 warnings on the new post
python blog/build.py --include-drafts            # put draft in index.json for preview
( python -m http.server 8765 >/tmp/agentblog.log 2>&1 & )   # if not already up
python .claude/skills/research-to-blog/scripts/verify_render.py <slug>
```
`verify_render.py` reports figure count/types, degraded blocks, console errors, and writes
a full-page screenshot + per-figure crops to `/tmp/canvas_check/`. **Read the crops** — every
figure must be legible and premium (the bar: "a finished figure, not a box of text"). Fix
any `data-canvas-error`, truncation, or overflow, then re-run.

### 6. Present & gate
- Give the user the preview URL `http://127.0.0.1:8765/html/post.html?slug=<slug>`, a one-line
  summary of the figures, and any honesty flags (qualitative charts, unverified IDs).
- Leave `status: draft`. Only on the user's explicit "publish": flip to `published`, run the
  §6 pre-publish checklist, `python blog/build.py` (drops drafts), confirm on the homepage,
  append a `log.md` `blog | published` line.

## Canvas DSL cheat-sheet (canonical: `blog/README.md` §10)

A figure is a fenced ` ```canvas ` block. Line 1 = `type:`; then `key: value` directives;
then body rows. Directives: `caption:` (**bold**/*italic*/`code`/[text](url)), `source:`
(right-aligned provenance), `accent:` `paper|deep|final`.

- **matrix** — `rows: A | T` · `cols: … | …` · then `r,c :: **Title** — body. \`Model\`, \`Model\``
  (1-based; single-letter rows auto-tag cells A1/T2… and alias A→Agent, T→Tool; cells color by column).
- **timeline** — one node per row: `label | title | subtitle`. A trailing `(XXX)` in the
  subtitle becomes a method pill; nodes era-grade paper→deep→final.
- **flow** — `Input -> Agent -> Tool -> Reward` · `state: Agent=trained, Tool=frozen`
  (trained=elevated+badge, frozen=dashed+badge) · `loop: Reward -> Agent | label` · `note: …`.
- **bars** — `axis: A | B` then `label | valA | valB` (0–100).
- **grid** — `cols: N` then `title :: body` per card.

Hard rules: no `[[ ]]` inside a canvas; cell/caption md is only bold/italic/code/link; a
malformed block degrades to a visible code block (never blanks the page).

## What NOT to do
- Don't add a diagram library (Mermaid/D3/etc.) — rejected twice; the DSL covers our needs at
  zero dep. (See `blog/design/CHOSEN.md`.)
- Don't write walls of prose with one diagram at the end. Diagram-first means diagram-first.
- Don't invent citations or numbers. Don't publish without the user's word.
- Don't change the canvas DSL or `canvas.js` to fit one post — extend the renderer deliberately
  (new primitive, documented) only if a genuinely new content shape recurs.

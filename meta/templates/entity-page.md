---
type: entity
entity_kind: paper
venue: "VENUE YEAR"
track: ""
reading: abstract
status: stub
aliases: []
tags: []
created: {{date}}
updated: {{date}}
---

<!--
frontmatter contract (linted by portal/build.py):
  entity_kind: paper | method | dataset | model | person | org
  reading:     abstract | full-text — how deep the source was ACTUALLY read
  status:      stub | growing | stable
  aliases:     other names this page is known by (method name vs paper name)
-->

# {{Full Paper Title}}

**Authors:** Last, First; Last, First; …
**Venue:** VENUE YEAR (track)

## TL;DR

One or two sentences: the claim, the mechanism, the headline number with its
setting.

## Problem

What gap or failure this work addresses; why prior approaches fall short.

## Method

The mechanism, stated so it could be re-derived. Name the components the rest
of the wiki will link to. Use typed links where the relation is load-bearing:
`improves:: [[prior-method]]`, `uses:: [[dataset-slug]]`, `refutes:: [[claim-source]]`.

## Key figures

<!-- For visually dense papers: extract the architecture figure and main
     results figure to raw/assets/<corpus>/<slug>/ BEFORE deleting the PDF
     (lit-harvest Phase 5 hard rule). One line each. Delete this section only
     if the paper genuinely carries its content in text. -->

![arch](../../raw/assets/{{corpus}}/{{slug}}/fig-arch.png) — one line: what it shows.

## Results

Headline numbers WITH their conditions (benchmark, baseline, setting) AND
their location in the source ("Table 3", "abstract") so a spot-check is O(1).

If `reading: abstract`, this section may only restate claims the abstract
itself makes, each marked "(abstract-claimed)" — never numbers or comparisons
the abstract does not contain. Upgrade `reading:` to `full-text` when the
paper is actually read.

## Key contributions

- …
- …

## Links

- arxiv: https://arxiv.org/abs/XXXX.XXXXX
- pdf: raw/papers/…
- code: (official repo, or "none found YYYY-MM")
- weights: (HF / model zoo, if any)
- related: [[other-entity]], [[topic-page]]

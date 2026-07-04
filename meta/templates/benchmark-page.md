---
type: benchmark
status: growing
aliases: []
tags: []
created: {{date}}
updated: {{date}}
---

# {{Benchmark name}}

One paragraph: what capability this benchmark measures and why the field
tracks it. Lives in `wiki/comparisons/` (frontmatter `type: benchmark` is the
contract; the directory is only a default).

## Protocol

- **Dataset / split:** (which split is the reported one; link `uses:: [[dataset-slug]]`)
- **Metric:** exact definition (mAP@[.5:.95], top-1, EM, …)
- **Common gotchas:** the setting differences that make numbers incomparable
  (backbone, training schedule, extra data, test-time tricks). Numbers in the
  SOTA table below are only comparable when these match.

## SOTA table

<!-- APPEND-ONLY: add rows, never rewrite history — the climb over time IS
     the content. Newest on top. Every number carries its setting. -->

| Date | Method | Score | Key setting | Source |
|---|---|---|---|---|
| YYYY-MM | [[entity-slug]] | 00.0 | backbone / data / schedule | Table N of [[entity-slug]] |

## Superseded

- (YYYY-MM) claim/row X — superseded by [[y]]: reason (e.g. leaderboard
  version change, metric redefinition).

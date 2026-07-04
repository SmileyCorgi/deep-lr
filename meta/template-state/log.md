# Log

Chronological, append-only record of operations on the wiki. Entry format:

```
## [YYYY-MM-DD] <op> | <subject>
- short note
```

Parseable with: `grep "^## \[" log.md | tail -N`

## [2026-07-04] framework | template-content separation + tutorial blog style
- `scripts/template_sync.py`: one-command sync of template-grade files to the
  template remote; content zones (wiki/raw/experiments/blog posts) are never
  copied. Pristine states of the four mixed files live in `meta/template-state/`.
- Blog gains a second house style: Tutorial (Lilian-Weng-style teaching long
  form) — skeleton in `meta/templates/blog-post-tutorial.md`, conventions in
  the research-to-blog skill.

## [2026-07-03] lint | framework review (5-persona panel) + full overhaul
- Simulated review panel (NLP prof, CV prof, 3 PhDs) audited the template;
  minutes + implementation record in `meta/reviews/2026-07-03_framework-review.md`.
- All P0/P1/P2 findings implemented: manifest I/O hardened (manifestio.py,
  schema v2), rerun-safe dedup, frontmatter made a lint-enforced contract,
  reviewer gate + evidence grades for synthesis, visual evidence chain +
  benchmark pages, Timeline/Superseded conventions, typed links, pipeline
  cross-dedup, idea lifecycle, commit & recovery discipline.

## [2026-07-03] bootstrap | deep-lr framework packaged
- Framework extracted and generalized from the Agent_Research workbench
  (schema, harvest scripts, portal, blog + canvas DSL, 5 skills).
- Repo is in clean template state: no raw sources, no wiki pages, project
  config unset. Next step: run the §0 bootstrap protocol in CLAUDE.md for a
  concrete discipline.

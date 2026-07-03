# Log

Chronological, append-only record of operations on the wiki. Entry format:

```
## [YYYY-MM-DD] <op> | <subject>
- short note
```

Parseable with: `grep "^## \[" log.md | tail -N`

## [2026-07-03] bootstrap | deep-lr framework packaged
- Framework extracted and generalized from the Agent_Research workbench
  (schema, harvest scripts, portal, blog + canvas DSL, 5 skills).
- Repo is in clean template state: no raw sources, no wiki pages, project
  config unset. Next step: run the §0 bootstrap protocol in CLAUDE.md for a
  concrete discipline.

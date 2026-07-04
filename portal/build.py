#!/usr/bin/env python3
"""
portal/build.py — emit html/portal/index.json from wiki/, ideas/backlog.md, log.md.

Python stdlib only. Mirrors blog/build.py patterns: hand-rolled frontmatter,
YAML-ish list/value parser, regex wikilink extraction. The portal renderer is
runtime-static — this script is the only place that knows how to walk the repo.

Usage:
    python portal/build.py            # write html/portal/index.json
    python portal/build.py --lint     # validate only; no write
    python portal/build.py --strict   # lint warnings become non-zero exit

Lint checks (mechanical rules stay in scripts, not in LLM memory):
    broken wikilinks · orphan pages · malformed wikilinks (e.g. spaces) ·
    duplicate slugs · frontmatter contract (type enum, date formats,
    entity_kind on entities, deprecated fields) · index.md coverage drift ·
    stale pages (cited but long-unupdated) · merge candidates (high out-link
    overlap)

Output shape (abridged; see emit_index for full):

    {
      "generated": "2026-06-02T...",
      "stats": {
        "topics": 14, "entities": 107, "synthesis": 4,
        "manifest_papers": 2508, "pdfs_on_disk": 1635,
        "log_entries": 26, "ideas": 0,
        "venue_year": {"ICLR 2026": {"2026": 20}, ...}
      },
      "pages": [
        {"slug": "...", "type": "topic|entity|synthesis|comparison|concept|corpus",
         "title": "...", "path": "wiki/topics/memory.md",
         "frontmatter": {...}, "tldr": "...", "h1": "...", "updated": "YYYY-MM-DD",
         "out_links": ["slug1","slug2"], "h2": ["§1 ...", ...]}
      ],
      "backlinks": {"slug": [{"from": "src-slug", "context": "first 120 chars"}]},
      "forward":   {"slug": "wiki/topics/memory.md"},
      "log":       [{"date": "YYYY-MM-DD", "op": "ingest", "subject": "...",
                     "body": "...", "links": ["slug","slug"]}],
      "ideas":     [{"title": "...", "date": "...", "trigger": "...", "sketch": "...",
                     "promoted_to": "..."}],
      "graph": {
        "nodes": [{"id": "...", "type": "topic|entity|synthesis", "title": "...",
                   "topics": ["memory"], "venue": "ICLR 2026", "track": "oral",
                   "updated": "...", "degree_in": 0, "degree_out": 0}],
        "edges": [{"source": "...", "target": "...", "weight": 1}]
      },
      "orphans":      ["slug-no-inbound"],
      "broken_links": [{"from": "src-slug", "target": "missing-slug"}]
    }
"""

import argparse
import datetime as _dt
import json
import os
import re
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WIKI_DIR = os.path.join(REPO_ROOT, "wiki")
IDEAS_PATH = os.path.join(REPO_ROOT, "ideas", "backlog.md")
LOG_PATH = os.path.join(REPO_ROOT, "log.md")
INDEX_MD_PATH = os.path.join(REPO_ROOT, "index.md")
OUT_PATH = os.path.join(REPO_ROOT, "html", "portal", "index.json")

# Topic-subdirectory pages (e.g. agent-memory-corpus/README.md) get the
# directory prefix in the slug to avoid collision with top-level page slugs.
TOPIC_SUBDIR_TYPE = "corpus"

WIKI_RE = re.compile(r"\[\[([A-Za-z0-9][A-Za-z0-9._\-/]*)(?:\|[^\]\n]+)?\]\]")
# Any [[...]] that WIKI_RE would silently skip (spaces, leading symbols, …) —
# silent misses corrupt the graph/orphan analysis, so lint makes them loud.
RAW_WIKI_RE = re.compile(r"\[\[([^\]]*)\]\]")
# Typed links: a small closed verb set (open vocabularies drift into synonyms).
# Dataview-compatible inline fields: `improves:: [[x]]`.
TYPED_LINK_VERBS = ("improves", "refutes", "uses", "extends")
TYPED_RE = re.compile(
    r"\b(%s)::\s*\[\[([A-Za-z0-9][A-Za-z0-9._\-/]*)(?:\|[^\]\n]+)?\]\]"
    % "|".join(TYPED_LINK_VERBS))
ALLOWED_TYPES = {"topic", "entity", "concept", "comparison", "benchmark",
                 "synthesis", "corpus"}
ENTITY_KINDS = {"paper", "method", "dataset", "model", "person", "org"}
DATE_FM_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
STALE_DAYS = 90
LOG_HEADER_RE = re.compile(r"^## \[(\d{4}-\d{2}-\d{2})\] ([a-z\-]+) \| (.+)$")
H1_RE = re.compile(r"^# (.+)$", re.MULTILINE)
H2_RE = re.compile(r"^## (.+)$", re.MULTILINE)
TLDR_RE = re.compile(r"^## TL;DR\s*\n(.+?)(?:\n## |\Z)", re.DOTALL | re.MULTILINE)


# Console output must survive non-UTF-8 terminals (Windows cp936/GBK):
# degrade unencodable characters instead of crashing the lint run.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(errors="replace")
        except (ValueError, OSError):
            pass


def _err(msg):
    sys.stderr.write("[portal] ERROR: " + msg + "\n")


def _warn(msg):
    sys.stderr.write("[portal] WARN:  " + msg + "\n")


def _info(msg):
    sys.stdout.write("[portal] " + msg + "\n")


# ---------- frontmatter ----------------------------------------------------

def parse_frontmatter(text, source_path):
    """Return (meta_dict, body_str). Permissive: missing/malformed frontmatter
    is non-fatal — emit empty dict and treat the whole file as body. This is
    a read-only renderer over an LLM-curated wiki; we do not want to crash on
    every imperfect page."""
    if not text.startswith("---"):
        return {}, text
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.DOTALL)
    if not m:
        _warn("frontmatter fence not closed: " + source_path)
        return {}, text
    raw = m.group(1)
    body = m.group(2)
    meta = {}
    for raw_line in raw.splitlines():
        line = raw_line.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if not key:
            continue
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            items = []
            if inner:
                # Tokenize quoted-or-bare, comma-separated.
                cur = ""
                in_q = None
                for ch in inner + ",":
                    if in_q:
                        if ch == in_q:
                            in_q = None
                        else:
                            cur += ch
                    elif ch in ('"', "'"):
                        in_q = ch
                    elif ch == "," and not in_q:
                        cur = cur.strip()
                        if cur:
                            items.append(cur)
                        cur = ""
                    else:
                        cur += ch
            meta[key] = items
        else:
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
            meta[key] = val
    return meta, body


# ---------- wiki page walk --------------------------------------------------

def slug_for(rel_path):
    """Slug = filename stem; subdirectory pages get dir/stem to avoid collision."""
    base = rel_path[:-3] if rel_path.endswith(".md") else rel_path
    return base


def extract_tldr(body, page_type):
    """Pick a 1-2 sentence preview. Entities have a `## TL;DR` section; topics
    and synthesis fall back to the first prose paragraph after H1."""
    m = TLDR_RE.search(body)
    if m:
        tldr = m.group(1).strip()
        # Strip leading blockquote markers and emphasis noise.
        tldr = re.sub(r"^>\s*", "", tldr, flags=re.MULTILINE)
        # First paragraph only.
        para = tldr.split("\n\n")[0].strip()
        return _clip(para.replace("**", ""), 320)
    # Fallback: first non-empty prose paragraph after H1.
    parts = re.split(r"\n# .+\n", body, maxsplit=1)
    rest = parts[1] if len(parts) > 1 else body
    for para in rest.split("\n\n"):
        s = para.strip()
        if not s or s.startswith("#") or s.startswith(">") or s.startswith("|"):
            continue
        if s.startswith("---"):
            continue
        return _clip(re.sub(r"\s+", " ", s).replace("**", ""), 320)
    return ""


def _clip(s, n):
    if len(s) <= n:
        return s
    cut = s[:n].rsplit(" ", 1)[0]
    return cut + "…"


def extract_h2(body):
    return [m.group(1).strip() for m in H2_RE.finditer(body)]


def extract_h1(body):
    m = H1_RE.search(body)
    return m.group(1).strip() if m else ""


def extract_outlinks(body):
    """Unique slugs in `[[slug]]` order of first appearance."""
    seen = []
    seen_set = set()
    for m in WIKI_RE.finditer(body):
        slug = m.group(1).strip()
        # Normalize: drop anchor / pipe display; lowercase the venue prefixes
        # are intentionally not normalized — wiki slugs are case-stable.
        if slug not in seen_set:
            seen_set.add(slug)
            seen.append(slug)
    return seen


def extract_typed_links(body):
    """`verb:: [[slug]]` typed links. Returns [(verb, slug), ...] deduped."""
    out = []
    seen = set()
    for m in TYPED_RE.finditer(body):
        pair = (m.group(1), m.group(2).strip())
        if pair not in seen:
            seen.add(pair)
            out.append(pair)
    return out


def find_malformed_wikilinks(body):
    """[[...]] spans that WIKI_RE silently skips — these vanish from the graph,
    backlinks, and orphan detection, so they must be loud, not silent."""
    bad = []
    for m in RAW_WIKI_RE.finditer(body):
        target = m.group(1).split("|")[0].strip()
        if not re.match(r"^[A-Za-z0-9][A-Za-z0-9._\-/]*$", target):
            bad.append(m.group(1)[:60])
    return bad


def lint_frontmatter(page):
    """The frontmatter contract from CLAUDE.md §5, machine-checked."""
    issues = []
    if page["type"] == "corpus":
        # Corpus subdir pages (READMEs, verify.py reports) are working
        # artifacts, not wiki contract pages.
        return issues
    meta = page["frontmatter"]
    t = meta.get("type", "")
    if not t:
        issues.append("missing frontmatter `type`")
    elif t not in ALLOWED_TYPES:
        issues.append("invalid type %r (allowed: %s)" % (t, sorted(ALLOWED_TYPES)))
    for k in ("created", "updated"):
        v = meta.get(k, "")
        if v and not DATE_FM_RE.match(str(v)):
            issues.append("%s not YYYY-MM-DD: %r" % (k, v))
    if page["type"] == "entity":
        ek = meta.get("entity_kind", "")
        if not ek:
            issues.append("entity page missing `entity_kind`")
        elif ek not in ENTITY_KINDS:
            issues.append("invalid entity_kind %r (allowed: %s)"
                          % (ek, sorted(ENTITY_KINDS)))
    if "sources" in meta:
        issues.append("deprecated field `sources` — drop it; "
                      "backlink counts are computed by this script")
    return issues


def walk_wiki():
    """Yield (page_type, slug, abs_path, rel_path) for every .md under wiki/.
    Topic subdir pages (under wiki/topics/<sub>/) get type "corpus" so the
    renderer can show them as collection artifacts rather than topic peers."""
    for sub in ("topics", "entities", "synthesis", "comparisons", "concepts"):
        root = os.path.join(WIKI_DIR, sub)
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames.sort()
            for fn in sorted(filenames):
                if not fn.endswith(".md"):
                    continue
                abs_path = os.path.join(dirpath, fn)
                rel_to_sub = os.path.relpath(abs_path, root)  # e.g. memory.md or corpus/README.md
                # Forward slashes always: this string becomes a URL in the
                # portal ("Source" link) — os.sep backslashes break it.
                rel_to_repo = os.path.relpath(abs_path, REPO_ROOT).replace(os.sep, "/")
                if os.sep in rel_to_sub:
                    # Subdirectory page — slug includes the dir, type = corpus.
                    slug = slug_for(rel_to_sub).replace(os.sep, "/")
                    yield (TOPIC_SUBDIR_TYPE, slug, abs_path, rel_to_repo)
                else:
                    page_type = sub[:-1] if sub.endswith("s") else sub  # topics -> topic
                    # singularize special cases
                    if sub == "synthesis":
                        page_type = "synthesis"
                    elif sub == "topics":
                        page_type = "topic"
                    elif sub == "entities":
                        page_type = "entity"
                    elif sub == "comparisons":
                        page_type = "comparison"
                    elif sub == "concepts":
                        page_type = "concept"
                    slug = slug_for(rel_to_sub)
                    yield (page_type, slug, abs_path, rel_to_repo)


# ---------- log -------------------------------------------------------------

def parse_log(path):
    """Parse `## [YYYY-MM-DD] <op> | <subject>` headers + bullet bodies.
    Returns list of dicts in source order (newest first, matching log.md)."""
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    entries = []
    cur = None
    for line in text.splitlines():
        m = LOG_HEADER_RE.match(line)
        if m:
            if cur:
                entries.append(_finalize_log(cur))
            cur = {"date": m.group(1), "op": m.group(2), "subject": m.group(3).strip(),
                   "body_lines": []}
            continue
        if cur is not None:
            # End on the next H2 of any kind.
            if line.startswith("## "):
                entries.append(_finalize_log(cur))
                cur = None
                continue
            cur["body_lines"].append(line)
    if cur:
        entries.append(_finalize_log(cur))
    return entries


def _finalize_log(cur):
    body = "\n".join(cur.pop("body_lines")).strip()
    links = []
    seen = set()
    for m in WIKI_RE.finditer(body):
        s = m.group(1).strip()
        if s not in seen:
            seen.add(s)
            links.append(s)
    cur["body"] = body
    cur["links"] = links
    return cur


# ---------- ideas -----------------------------------------------------------

IDEA_HEADER_RE = re.compile(r"^## (?!\s*<).+$", re.MULTILINE)


def parse_ideas(path):
    """Parse ideas/backlog.md. Format per entry:
        ## <title>
        - Date: YYYY-MM-DD
        - Trigger: ...
        - Sketch: ...
        - Promoted to: ...
    The header text in italics (e.g. `## _empty_`) is ignored. Returns a list."""
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    entries = []
    # Skip the format example block by starting after the first --- divider.
    parts = text.split("\n---\n", 1)
    body = parts[1] if len(parts) > 1 else text
    cur = None
    for line in body.splitlines():
        if line.startswith("## ") and not line.startswith("## <") and not line.lstrip("# ").startswith("_"):
            if cur:
                entries.append(cur)
            cur = {"title": line[3:].strip(), "date": "", "trigger": "",
                   "sketch": "", "promoted_to": ""}
            continue
        if cur is None:
            continue
        sline = line.strip()
        for prefix, key in (("- Date:", "date"), ("- Trigger:", "trigger"),
                            ("- Sketch:", "sketch"), ("- Promoted to:", "promoted_to")):
            if sline.startswith(prefix):
                cur[key] = sline[len(prefix):].strip()
                break
    if cur:
        entries.append(cur)
    return entries


# ---------- index.md hand-curated summaries --------------------------------

INDEX_SUMMARY_RE = re.compile(
    r"-\s+\[\*?\*?([a-z0-9][a-z0-9_\-/]+)\*?\*?\][^—]*—\s*(.+)$"
)


def parse_index_summaries(path):
    """Map slug -> one-line human-curated summary scraped from index.md.
    Returns (summaries, unparsed) — unparsed lines look like entries but fail
    the pattern; they are reported by lint instead of silently dropped."""
    out = {}
    unparsed = []
    if not os.path.isfile(path):
        return out, unparsed
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped.startswith("- ["):
                continue
            # Extract anchor text + everything after the em-dash separator.
            m = re.match(r"-\s+\[(?:\*\*)?([^\]\*]+)(?:\*\*)?\]\([^)]+\)\s+—\s+(.+)$", stripped)
            if not m:
                unparsed.append(stripped[:100])
                continue
            label = m.group(1).strip().lower()
            summary = m.group(2).strip()
            # Normalize markdown emphasis off of the summary.
            summary = re.sub(r"_\*+_?", "", summary)
            out[label] = summary
    return out, unparsed


def parse_index_targets(path):
    """All markdown link targets in index.md, normalized repo-relative —
    used to detect drift between the hand-curated index and wiki/ contents."""
    targets = set()
    if not os.path.isfile(path):
        return targets
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    for m in re.finditer(r"\]\(([^)#]+)", text):
        t = m.group(1).strip()
        if t.startswith("./"):
            t = t[2:]
        targets.add(t.replace("\\", "/"))
    return targets


# ---------- manifest counters (best-effort) ---------------------------------

def manifest_stats():
    """Return (papers_in_manifest, pdfs_on_disk). Best-effort; returns
    zeros if no corpus sub-project is present. Generic: sums every
    wiki/topics/*/manifest.tsv and every *.pdf under raw/papers/."""
    papers = 0
    topics_dir = os.path.join(WIKI_DIR, "topics")
    if os.path.isdir(topics_dir):
        for sub in sorted(os.listdir(topics_dir)):
            manifest = os.path.join(topics_dir, sub, "manifest.tsv")
            if not os.path.isfile(manifest):
                continue
            try:
                with open(manifest, encoding="utf-8") as fh:
                    lines = fh.readlines()
                # First line may be a header; count non-empty data lines.
                for ln in lines[1:]:
                    if ln.strip():
                        papers += 1
            except Exception as e:
                _warn("manifest read failed (%s): %s" % (sub, e))
    pdf_root = os.path.join(REPO_ROOT, "raw", "papers")
    pdfs = 0
    if os.path.isdir(pdf_root):
        for dirpath, _, filenames in os.walk(pdf_root):
            for fn in filenames:
                if fn.endswith(".pdf"):
                    pdfs += 1
    return papers, pdfs


# ---------- topic membership for entities ----------------------------------

def derive_topic_membership(pages):
    """For each entity, list which topic pages link to it. The topic page is
    authoritative — frontmatter `category:` is a hint but the page itself is
    truth (an entity might be cited from a topic page it doesn't tag)."""
    membership = {}
    for p in pages:
        if p["type"] != "topic":
            continue
        for slug in p["out_links"]:
            membership.setdefault(slug, []).append(p["slug"])
    # Dedupe.
    for k, v in membership.items():
        seen = []
        seenset = set()
        for x in v:
            if x not in seenset:
                seenset.add(x)
                seen.append(x)
        membership[k] = seen
    return membership


# ---------- main build ------------------------------------------------------

def build():
    pages = []
    slug_index = {}
    duplicate_slugs = []

    for page_type, slug, abs_path, rel_path in walk_wiki():
        try:
            with open(abs_path, encoding="utf-8") as fh:
                raw = fh.read()
        except Exception as e:
            _warn("read failed %s: %s" % (rel_path, e))
            continue
        meta, body = parse_frontmatter(raw, rel_path)
        # Frontmatter `type:` is the contract; the directory is only a default.
        # This is what lets a benchmark page live in wiki/comparisons/.
        fm_type = str(meta.get("type", ""))
        if fm_type in ALLOWED_TYPES and page_type != TOPIC_SUBDIR_TYPE:
            page_type = fm_type
        page = {
            "slug": slug,
            "type": page_type,
            "path": rel_path,
            "h1": extract_h1(body),
            "title": extract_h1(body) or slug,
            "frontmatter": meta,
            "tldr": extract_tldr(body, page_type),
            "h2": extract_h2(body),
            "out_links": extract_outlinks(body),
            "typed_links": [{"rel": v, "target": t} for v, t in extract_typed_links(body)],
            "updated": meta.get("updated", ""),
            "created": meta.get("created", ""),
            "tags": meta.get("tags", []) if isinstance(meta.get("tags", []), list) else [],
            "venue": meta.get("venue", ""),
            "track": meta.get("track", ""),
            "category": meta.get("category", ""),
            "entity_kind": meta.get("entity_kind", ""),
            "status": meta.get("status", ""),
            "human_verified": meta.get("human_verified", ""),
            "malformed_links": find_malformed_wikilinks(body),
        }
        pages.append(page)
        if slug in slug_index:
            _warn("duplicate slug %s (%s vs %s)" %
                  (slug, slug_index[slug]["path"], rel_path))
            duplicate_slugs.append({"slug": slug,
                                    "a": slug_index[slug]["path"],
                                    "b": rel_path})
        slug_index[slug] = page

    # Backlinks + broken-link detection.
    backlinks = {}
    forward = {p["slug"]: p["path"] for p in pages}
    broken = []
    for p in pages:
        for tgt in p["out_links"]:
            if tgt in slug_index:
                backlinks.setdefault(tgt, []).append({
                    "from": p["slug"],
                    "from_type": p["type"],
                    "from_title": p["title"],
                })
            else:
                broken.append({"from": p["slug"], "target": tgt})

    # Orphans = pages with zero inbound wikilinks AND not topics (topics are
    # entry points by design; corpus pages are working artifacts).
    orphans = []
    for p in pages:
        if p["type"] in ("topic", "synthesis", "corpus"):
            continue
        if not backlinks.get(p["slug"]):
            orphans.append(p["slug"])

    # Topic membership for entities (used by graph colors).
    topic_membership = derive_topic_membership(pages)

    # Log + ideas.
    log = parse_log(LOG_PATH)
    ideas = parse_ideas(IDEAS_PATH)

    # Curated summaries from index.md (override topic tldrs when available).
    curated, index_unparsed = parse_index_summaries(INDEX_MD_PATH)
    for p in pages:
        if p["type"] == "topic" and p["slug"] in curated:
            p["curated_summary"] = curated[p["slug"]]

    # Index drift: wiki pages the hand-curated index.md forgot to list.
    # (index.md keeps the human one-liners; this script keeps it honest.)
    index_targets = parse_index_targets(INDEX_MD_PATH)
    index_missing = [p["path"].replace(os.sep, "/") for p in pages
                     if p["type"] != "corpus"
                     and p["path"].replace(os.sep, "/") not in index_targets]

    # Stats.
    venue_year = {}
    for p in pages:
        if p["type"] != "entity":
            continue
        v = p.get("venue", "")
        if not v:
            continue
        # Venue field is like "ICLR 2026"; split out the year for the heatmap.
        m = re.match(r"^(.+?)\s+(\d{4})$", v.strip())
        if m:
            venue_name = m.group(1).strip()
            year = m.group(2)
        else:
            venue_name = v
            year = (p.get("created", "")[:4] or "?")
        venue_year.setdefault(venue_name, {}).setdefault(year, 0)
        venue_year[venue_name][year] += 1

    papers_in_manifest, pdfs_on_disk = manifest_stats()

    counts_by_type = {}
    for p in pages:
        counts_by_type[p["type"]] = counts_by_type.get(p["type"], 0) + 1

    stats = {
        "topics": counts_by_type.get("topic", 0),
        "entities": counts_by_type.get("entity", 0),
        "synthesis": counts_by_type.get("synthesis", 0),
        "comparisons": counts_by_type.get("comparison", 0),
        "benchmarks": counts_by_type.get("benchmark", 0),
        "concepts": counts_by_type.get("concept", 0),
        "corpus_pages": counts_by_type.get("corpus", 0),
        "manifest_papers": papers_in_manifest,
        "pdfs_on_disk": pdfs_on_disk,
        "log_entries": len(log),
        "ideas": len(ideas),
        "broken_links": len(broken),
        "orphans": len(orphans),
        "venue_year": venue_year,
    }

    # Graph: nodes for topic, entity, synthesis; edges = wikilinks among those.
    GRAPH_TYPES = {"topic", "entity", "synthesis"}
    nodes_by_id = {}
    for p in pages:
        if p["type"] not in GRAPH_TYPES:
            continue
        # Compact node payload — the page payload above carries the full data
        # the page renderer needs; the graph only needs what's drawn or hovered.
        nodes_by_id[p["slug"]] = {
            "id": p["slug"],
            "type": p["type"],
            "title": p["title"] or p["slug"],
            "topics": topic_membership.get(p["slug"], [p["slug"]] if p["type"] == "topic" else []),
            "venue": p.get("venue", ""),
            "track": p.get("track", ""),
            "updated": p.get("updated", ""),
            "tldr": _clip(p.get("tldr", ""), 220),
            "degree_in": 0,
            "degree_out": 0,
        }
    edges_map = {}  # (src,tgt) -> weight
    edge_rels = {}  # (src,tgt) -> typed relation, when one was declared
    for p in pages:
        if p["slug"] not in nodes_by_id:
            continue
        for tgt in p["out_links"]:
            if tgt not in nodes_by_id:
                continue
            key = (p["slug"], tgt)
            edges_map[key] = edges_map.get(key, 0) + 1
        for tl in p["typed_links"]:
            if tl["target"] in nodes_by_id:
                key = (p["slug"], tl["target"])
                edges_map.setdefault(key, 1)
                edge_rels[key] = tl["rel"]
    edges = []
    for (src, tgt), w in edges_map.items():
        edges.append({"source": src, "target": tgt, "weight": w,
                      "rel": edge_rels.get((src, tgt), "mentions")})
        nodes_by_id[src]["degree_out"] += 1
        nodes_by_id[tgt]["degree_in"] += 1
    graph = {"nodes": list(nodes_by_id.values()), "edges": edges}

    # ---- lint payloads (computed here, reported in main) ----

    # Frontmatter contract violations.
    fm_issues = []
    for p in pages:
        for issue in lint_frontmatter(p):
            fm_issues.append({"page": p["slug"], "issue": issue})

    # Malformed wikilinks (silently invisible to the graph otherwise).
    malformed = [{"page": p["slug"], "raw": raw_link}
                 for p in pages for raw_link in p["malformed_links"]]

    # Stale: cited from somewhere but not updated in STALE_DAYS — a finite
    # re-read list, instead of "remember to look for stale claims".
    today = _dt.date.today()
    stale = []
    for p in pages:
        u = p.get("updated", "")
        if not (u and DATE_FM_RE.match(str(u)) and backlinks.get(p["slug"])):
            continue
        try:
            age = (today - _dt.date.fromisoformat(str(u))).days
        except ValueError:
            continue
        if age > STALE_DAYS:
            stale.append({"page": p["slug"], "updated": u, "age_days": age,
                          "inbound": len(backlinks[p["slug"]])})
    stale.sort(key=lambda x: -x["age_days"])

    # Merge candidates: two non-topic pages whose out-link sets overlap
    # heavily probably cover the same ground (operational stand-in for the
    # unenforceable "overlap > 60%" prose rule). Only entity-to-entity links
    # count — everything links the same topic/synthesis hubs, which would
    # flag every anchor pair as a false positive.
    def _entity_links(p):
        return {t for t in p["out_links"]
                if slug_index.get(t, {}).get("type") == "entity"}
    merge_candidates = []
    linkful = [(p, _entity_links(p)) for p in pages
               if p["type"] not in ("topic", "corpus")]
    linkful = [(p, s) for p, s in linkful if len(s) >= 3]
    for i in range(len(linkful)):
        pi, si = linkful[i]
        for j in range(i + 1, len(linkful)):
            pj, sj = linkful[j]
            jac = len(si & sj) / len(si | sj)
            if jac > 0.5:
                merge_candidates.append({"a": pi["slug"], "b": pj["slug"],
                                         "jaccard": round(jac, 2)})

    lint = {
        "duplicate_slugs": duplicate_slugs,
        "frontmatter_issues": fm_issues,
        "malformed_wikilinks": malformed,
        "index_md_missing": index_missing,
        "index_md_unparsed": index_unparsed,
        "stale_pages": stale,
        "merge_candidates": merge_candidates,
    }

    # Final assembly.
    out = {
        "schema": 1,
        "generated": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "stats": stats,
        "pages": pages,
        "backlinks": backlinks,
        "forward": forward,
        "log": log,
        "ideas": ideas,
        "graph": graph,
        "orphans": orphans,
        "broken_links": broken,
        "lint": lint,
    }
    return out


# ---------- entry point -----------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lint", action="store_true",
                    help="validate only; no write")
    ap.add_argument("--strict", action="store_true",
                    help="lint warnings → non-zero exit")
    args = ap.parse_args()

    out = build()

    # Reporting.
    s = out["stats"]
    _info("topics=%d entities=%d synthesis=%d corpus=%d log=%d ideas=%d" %
          (s["topics"], s["entities"], s["synthesis"], s["corpus_pages"],
           s["log_entries"], s["ideas"]))
    _info("graph: nodes=%d edges=%d" % (len(out["graph"]["nodes"]),
                                        len(out["graph"]["edges"])))
    if out["broken_links"]:
        _warn("%d broken wikilinks" % len(out["broken_links"]))
        for b in out["broken_links"][:10]:
            _warn("  %s → [[%s]]" % (b["from"], b["target"]))
        if len(out["broken_links"]) > 10:
            _warn("  ... (%d more)" % (len(out["broken_links"]) - 10))
    if out["orphans"]:
        _info("%d orphan entities (no inbound wikilinks)" % len(out["orphans"]))

    lint = out["lint"]
    for item in lint["frontmatter_issues"][:20]:
        _warn("frontmatter %s: %s" % (item["page"], item["issue"]))
    if len(lint["frontmatter_issues"]) > 20:
        _warn("  ... (%d more frontmatter issues)" % (len(lint["frontmatter_issues"]) - 20))
    for item in lint["malformed_wikilinks"][:10]:
        _warn("malformed wikilink in %s: [[%s]] (invisible to graph/backlinks)"
              % (item["page"], item["raw"]))
    for path in lint["index_md_missing"][:10]:
        _warn("index.md does not list %s" % path)
    for line in lint["index_md_unparsed"][:5]:
        _warn("index.md entry not parseable (want `- [slug](path) — summary`): %s" % line)
    for item in lint["stale_pages"][:10]:
        _info("stale: %s (updated %s, %d days ago, %d inbound links)"
              % (item["page"], item["updated"], item["age_days"], item["inbound"]))
    for item in lint["merge_candidates"][:10]:
        _info("merge candidate: %s <-> %s (out-link Jaccard %.2f)"
              % (item["a"], item["b"], item["jaccard"]))

    hard_findings = (out["broken_links"] or out["orphans"]
                     or lint["duplicate_slugs"]
                     or lint["frontmatter_issues"] or lint["malformed_wikilinks"]
                     or lint["index_md_missing"] or lint["index_md_unparsed"])

    if args.lint:
        if args.strict and hard_findings:
            return 1
        return 0

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, separators=(",", ":"))
    sz = os.path.getsize(OUT_PATH)
    _info("wrote %s (%.1f KB)" % (os.path.relpath(OUT_PATH, REPO_ROOT), sz / 1024.0))

    if args.strict and hard_findings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

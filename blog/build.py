#!/usr/bin/env python3
"""
blog/build.py — emit blog/index.json from blog/posts/*.md.

Python stdlib only. Hand-rolled frontmatter parser (YAML-ish). Validates
required keys, prints clear errors, exits non-zero on bad post. Lints
[[wiki-slug]] citations against /wiki/entities/ and warns on missing
entities or entities lacking the metadata the references modal needs.

Usage:
    python3 blog/build.py                  # public index (drops status: draft)
    python3 blog/build.py --include-drafts # include drafts (for local preview)
    python3 blog/build.py --lint           # lint only, do not write index.json
    python3 blog/build.py --strict         # treat citation warnings as errors

The generated file is blog/index.json, sorted by date desc, of the shape:

    {
      "generated": "2026-05-17T19:47:00Z",
      "posts": [
        {
          "slug": "...",
          "title": "...",
          "date": "YYYY-MM-DD",
          "category": "final-idea|deep-conversation|paper-research",
          "dek": "...",
          "tags": [...],
          "reading_time": <int minutes>,
          "status": "published|draft"
        }
      ]
    }
"""

import argparse
import datetime as _dt
import json
import os
import re
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
POSTS_DIR = os.path.join(REPO_ROOT, "blog", "posts")
CATS_PATH = os.path.join(REPO_ROOT, "blog", "categories.json")
OUT_PATH = os.path.join(REPO_ROOT, "blog", "index.json")
ENTITIES_DIR = os.path.join(REPO_ROOT, "wiki", "entities")

REQUIRED_KEYS = {"title", "date", "category", "slug", "status"}
ALLOWED_STATUS = {"draft", "published"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
WORDS_PER_MIN = 220  # rough reading-rate target

CITE_RE = re.compile(r"\[\[([a-z0-9][a-z0-9_\-]*)(?:\|[^\]]+)?\]\]")


def _err(msg):
    sys.stderr.write("[build.py] ERROR: " + msg + "\n")


def _warn(msg):
    sys.stderr.write("[build.py] WARN:  " + msg + "\n")


def _info(msg):
    sys.stdout.write("[build.py] " + msg + "\n")


def parse_frontmatter(text, source_path):
    """
    Return (meta_dict, body_str). Frontmatter is a leading `---\\n...\\n---\\n`
    block. Supports:
      key: value
      key: "quoted value"
      key: [a, b, c]
      key: [a, "b c", d]
    Values are strings; lists are arrays of strings.
    """
    if not text.startswith("---"):
        return {}, text

    # Find the closing fence.
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.DOTALL)
    if not m:
        raise ValueError(
            "frontmatter fence not closed in {}".format(source_path)
        )

    raw = m.group(1)
    body = m.group(2)
    meta = {}

    for raw_line in raw.splitlines():
        line = raw_line.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            raise ValueError(
                "malformed frontmatter line (no colon) in {}: {!r}".format(
                    source_path, raw_line
                )
            )
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()

        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            items = []
            if inner:
                # Tokenize: respect double quotes.
                tokens = []
                cur = []
                in_q = False
                for ch in inner:
                    if ch == '"':
                        in_q = not in_q
                        continue
                    if ch == "," and not in_q:
                        tokens.append("".join(cur).strip())
                        cur = []
                        continue
                    cur.append(ch)
                if cur:
                    tokens.append("".join(cur).strip())
                items = [t for t in tokens if t != ""]
            meta[key] = items
        else:
            if val.startswith('"') and val.endswith('"') and len(val) >= 2:
                val = val[1:-1]
            elif val.startswith("'") and val.endswith("'") and len(val) >= 2:
                val = val[1:-1]
            meta[key] = val

    return meta, body


def reading_time(body):
    # Strip code fences and HTML tags loosely; word-count what remains.
    cleaned = re.sub(r"```.*?```", "", body, flags=re.DOTALL)
    cleaned = re.sub(r"`[^`]*`", "", cleaned)
    cleaned = re.sub(r"<[^>]+>", "", cleaned)
    words = re.findall(r"\w+", cleaned)
    n = len(words)
    if n == 0:
        return 1
    minutes = max(1, round(n / WORDS_PER_MIN))
    return int(minutes)


def validate_post(meta, body, source_path, valid_categories):
    missing = REQUIRED_KEYS - set(meta.keys())
    if missing:
        raise ValueError(
            "{}: missing required frontmatter keys: {}".format(
                source_path, ", ".join(sorted(missing))
            )
        )
    if meta["status"] not in ALLOWED_STATUS:
        raise ValueError(
            "{}: status must be one of {}, got {!r}".format(
                source_path, sorted(ALLOWED_STATUS), meta["status"]
            )
        )
    if not DATE_RE.match(str(meta["date"])):
        raise ValueError(
            "{}: date must be YYYY-MM-DD, got {!r}".format(
                source_path, meta["date"]
            )
        )
    if valid_categories and meta["category"] not in valid_categories:
        raise ValueError(
            "{}: category {!r} is not in categories.json ({})".format(
                source_path, meta["category"], sorted(valid_categories)
            )
        )
    slug_re = re.compile(r"^[a-z0-9][a-z0-9\-]*$")
    if not slug_re.match(str(meta["slug"])):
        raise ValueError(
            "{}: slug must be lowercase kebab-case, got {!r}".format(
                source_path, meta["slug"]
            )
        )
    # Slug must match the filename so /post.html?slug=… resolves the body.
    expected_fname = meta["slug"] + ".md"
    actual_fname = os.path.basename(source_path)
    if expected_fname != actual_fname:
        raise ValueError(
            "{}: slug {!r} does not match filename {!r} (expected {!r})".format(
                source_path, meta["slug"], actual_fname, expected_fname
            )
        )


# -------------------------------------------------------------------------
# Citation lint — for every [[slug]] in the post body, check that the wiki
# entity exists and has the metadata the references modal needs:
#   - H1 title          (# Title)
#   - **Authors:** line
#   - **Venue:** line
#   - ## TL;DR section
#   - at least one link: openreview / arxiv / pdf
# Missing entities → warning. Missing metadata → warning. Warnings do not
# fail the build unless --strict.
# -------------------------------------------------------------------------

def lint_citations(post_slug, body, entities_by_slug):
    """Return list of (level, message) tuples. level is 'warn' or 'error'."""
    issues = []
    # Strip ```fenced``` blocks first: a [[slug]] inside a canvas block is
    # rendered as inert text (the citation expander runs before marked, but the
    # fence escapes it), so it must not be linted as a real citation. Symmetric
    # with reading_time's fence strip above.
    body = re.sub(r"```.*?```", "", body, flags=re.DOTALL)
    cites = sorted(set(CITE_RE.findall(body)))
    if not cites:
        return issues

    for cited in cites:
        if cited not in entities_by_slug:
            issues.append((
                "warn",
                "[{}] cite [[{}]] → wiki/entities/{}.md does not exist"
                .format(post_slug, cited, cited),
            ))
            continue
        meta = entities_by_slug[cited]
        gaps = []
        if not meta["has_h1"]: gaps.append("H1 title")
        if not meta["has_authors"]: gaps.append("**Authors:**")
        if not meta["has_venue"]: gaps.append("**Venue:**")
        if not meta["has_tldr"]: gaps.append("## TL;DR")
        if not meta["has_link"]: gaps.append("openreview/arxiv/pdf link")
        if gaps:
            issues.append((
                "warn",
                "[{}] cite [[{}]] → entity missing: {}"
                .format(post_slug, cited, ", ".join(gaps)),
            ))
    return issues


def scan_entities():
    """Return {slug: {has_h1, has_authors, has_venue, has_tldr, has_link}}."""
    out = {}
    if not os.path.isdir(ENTITIES_DIR):
        return out
    for fname in os.listdir(ENTITIES_DIR):
        if not fname.endswith(".md") or fname.startswith("."):
            continue
        slug = fname[:-3]
        try:
            with open(os.path.join(ENTITIES_DIR, fname), "r", encoding="utf-8") as f:
                text = f.read()
        except OSError:
            continue
        # Strip frontmatter for body scan.
        body = text
        if body.startswith("---"):
            mm = re.match(r"^---\s*\n.*?\n---\s*\n?(.*)$", body, re.DOTALL)
            if mm:
                body = mm.group(1)
        out[slug] = {
            "has_h1": bool(re.search(r"^#\s+\S", body, re.MULTILINE)),
            "has_authors": bool(re.search(r"\*\*Authors?:\*\*", body)),
            "has_venue": bool(re.search(r"\*\*Venue:\*\*", body)),
            "has_tldr": bool(re.search(r"^##\s+TL;?DR", body,
                                       re.MULTILINE | re.IGNORECASE)),
            "has_link": bool(re.search(
                r"openreview\.net|arxiv\.org|\[pdf\]\(http", body)),
        }
    return out


def load_categories():
    if not os.path.exists(CATS_PATH):
        return set()
    try:
        with open(CATS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return set(data.keys())
    except (json.JSONDecodeError, OSError) as e:
        _err("could not read categories.json: " + str(e))
    return set()


def main():
    parser = argparse.ArgumentParser(description="Build blog/index.json")
    parser.add_argument(
        "--include-drafts",
        action="store_true",
        help="include posts with status: draft (default: drop them)",
    )
    parser.add_argument(
        "--lint",
        action="store_true",
        help="lint only; do not write blog/index.json",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="treat citation-lint warnings as errors (CI publish gate)",
    )
    args = parser.parse_args()

    valid_cats = load_categories()
    if not os.path.isdir(POSTS_DIR):
        os.makedirs(POSTS_DIR, exist_ok=True)
        _info("created empty blog/posts/")

    md_files = sorted(
        f for f in os.listdir(POSTS_DIR)
        if f.endswith(".md") and not f.startswith(".")
    )

    posts = []
    errors = []
    warnings = []

    entities_by_slug = scan_entities()

    for fname in md_files:
        path = os.path.join(POSTS_DIR, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
            meta, body = parse_frontmatter(text, path)
            validate_post(meta, body, path, valid_cats)
        except (ValueError, OSError) as e:
            errors.append(str(e))
            continue

        # Citation lint (only matters for posts going into the public index,
        # but we always run it so drafts get warnings too).
        cite_issues = lint_citations(meta["slug"], body, entities_by_slug)
        for level, msg in cite_issues:
            if args.strict and level == "warn":
                errors.append(msg)
            else:
                warnings.append(msg)

        if meta["status"] == "draft" and not args.include_drafts:
            continue

        entry = {
            "slug": meta["slug"],
            "title": meta["title"],
            "date": meta["date"],
            "category": meta["category"],
            "dek": meta.get("dek", ""),
            "tags": meta.get("tags", []) if isinstance(meta.get("tags"), list) else [],
            "reading_time": reading_time(body),
            "status": meta["status"],
        }
        # PM-C optional focus-block label override (default rendered by
        # the client-side post renderer is "THE GIST").
        if meta.get("focus_label"):
            entry["focus_label"] = meta["focus_label"]
        posts.append(entry)

    for w in warnings:
        _warn(w)
    if errors:
        for e in errors:
            _err(e)
        sys.exit(1)

    posts.sort(key=lambda p: p["date"], reverse=True)

    if args.lint:
        _info("lint OK ({} post{}, {} warning{})".format(
            len(md_files),
            "" if len(md_files) == 1 else "s",
            len(warnings),
            "" if len(warnings) == 1 else "s",
        ))
        return

    out = {
        "generated": _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "posts": posts,
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
        f.write("\n")

    _info("wrote {} ({} post{}, {} warning{})".format(
        os.path.relpath(OUT_PATH, REPO_ROOT),
        len(posts),
        "" if len(posts) == 1 else "s",
        len(warnings),
        "" if len(warnings) == 1 else "s",
    ))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
serve.py — local workbench server: the static site plus web-note capture.

Drop-in replacement for `python -m http.server 8765` (run from anywhere; it
serves the repo root). Adds one API the static pages use to persist notes:

    GET  /api/notes?ctx=<blog|wiki>&slug=<slug>   → {"ok":true,"markdown":...,"count":N}
    POST /api/notes  {"ctx","slug","title","selection","text"}
                                                   → {"ok":true,"file":...}

Notes are appended to raw/notes/web/<ctx>-<slug>.md — the raw zone, because a
web note is HUMAN input (marginalia), not LLM synthesis. The LLM reads new
notes during the next session/lint and integrates them (see CLAUDE.md §3).

If the site is served by plain http.server instead, the note widget degrades
to browser localStorage with an export button — nothing breaks, but notes
don't reach the repo until pasted.

Binds 127.0.0.1 only. Stdlib only. Usage:  python serve.py [port]
"""
from __future__ import annotations
import json, re, sys, time, urllib.parse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NOTES_DIR = ROOT / "raw" / "notes" / "web"
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,80}$")
CONTEXTS = {"blog", "wiki"}
MAX_NOTE = 20_000


def note_file(ctx: str, slug: str) -> Path:
    return NOTES_DIR / f"{ctx}-{slug}.md"


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    # ---- api ----

    def _params(self):
        q = urllib.parse.urlparse(self.path).query
        return {k: v[0] for k, v in urllib.parse.parse_qs(q).items()}

    def _json(self, code: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _valid(self, ctx: str, slug: str) -> bool:
        return ctx in CONTEXTS and bool(SLUG_RE.match(slug or ""))

    def do_GET(self):
        if urllib.parse.urlparse(self.path).path == "/api/notes":
            p = self._params()
            ctx, slug = p.get("ctx", ""), p.get("slug", "")
            if not self._valid(ctx, slug):
                return self._json(400, {"ok": False, "error": "bad ctx/slug"})
            f = note_file(ctx, slug)
            md = f.read_text(encoding="utf-8") if f.is_file() else ""
            count = md.count("\n## [")
            return self._json(200, {"ok": True, "markdown": md, "count": count})
        return super().do_GET()

    def do_POST(self):
        if urllib.parse.urlparse(self.path).path != "/api/notes":
            return self.send_error(404)
        try:
            n = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(min(n, MAX_NOTE * 2)))
        except (ValueError, json.JSONDecodeError):
            return self._json(400, {"ok": False, "error": "bad json"})
        ctx = str(data.get("ctx", ""))
        slug = str(data.get("slug", ""))
        text = str(data.get("text", "")).strip()
        selection = str(data.get("selection", "")).strip()
        title = str(data.get("title", "")).strip()
        if not self._valid(ctx, slug):
            return self._json(400, {"ok": False, "error": "bad ctx/slug"})
        if not text or len(text) > MAX_NOTE:
            return self._json(400, {"ok": False, "error": "empty or oversized note"})

        NOTES_DIR.mkdir(parents=True, exist_ok=True)
        f = note_file(ctx, slug)
        parts = []
        if not f.is_file():
            parts.append(f"# Web notes — {ctx}/{slug}\n")
            if title:
                parts.append(f"\nPage: {title}\n")
        parts.append(f"\n## [{time.strftime('%Y-%m-%d %H:%M')}]\n\n")
        if selection:
            quoted = "\n".join("> " + ln for ln in selection.splitlines()[:12])
            parts.append(quoted + "\n\n")
        parts.append(text + "\n")
        with f.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write("".join(parts))
        rel = f.relative_to(ROOT).as_posix()
        return self._json(200, {"ok": True, "file": rel})


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"deep-lr workbench: http://127.0.0.1:{port}/html/portal/index.html")
    print(f"notes API on — web notes append to {NOTES_DIR.relative_to(ROOT).as_posix()}/")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

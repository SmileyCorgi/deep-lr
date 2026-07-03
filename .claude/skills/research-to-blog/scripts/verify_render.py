#!/usr/bin/env python3
"""
verify_render.py — headless render check for a diagram-first blog post.

Loads html/post.html?slug=<slug> in headless Chromium, asserts every ```canvas```
block became a <figure>, reports figure types / degraded blocks / console errors,
and writes a full-page screenshot + per-figure crops to an output dir so the agent
can eyeball that each diagram is legible and premium ("a finished figure, not a box
of text"). Exit code 0 = clean, 1 = problems found.

Usage:
    python3 verify_render.py <slug> [--base http://127.0.0.1:8765] [--out /tmp/canvas_check]

Assumes the static server is already running (start from repo root:
    python3 -m http.server 8765 ). Requires Playwright (pip install playwright;
playwright install chromium).
"""
import argparse, json, os, sys

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--base", default="http://127.0.0.1:8765")
    ap.add_argument("--out", default="/tmp/canvas_check")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: Playwright not installed. `pip install playwright && playwright install chromium`")
        return 2

    url = f"{args.base}/html/post.html?slug={args.slug}"
    errors = []
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        pg = b.new_page(viewport={"width": 900, "height": 1400}, device_scale_factor=2)
        pg.on("console", lambda m: errors.append(f"{m.type}: {m.text}") if m.type in ("error", "warning") else None)
        pg.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        try:
            pg.goto(url, wait_until="networkidle", timeout=20000)
        except Exception as e:
            print(f"ERROR: could not load {url} — is the server running? ({e})")
            b.close(); return 2
        pg.wait_for_timeout(1400)  # let marked + canvas.js finish

        report = pg.evaluate("""() => {
          const figs = Array.from(document.querySelectorAll('figure.canvas'));
          const byType = {};
          figs.forEach(f => { const t=(f.className.match(/canvas--(\\w+)/)||[])[1]||'?'; byType[t]=(byType[t]||0)+1; });
          return {
            figures: figs.length,
            byType,
            degraded: document.querySelectorAll('pre[data-canvas-error]').length,
            leftover: document.querySelectorAll('pre > code.language-canvas').length,
            figNums: Array.from(document.querySelectorAll('.canvas-num')).map(e=>e.textContent),
            sections: Array.from(document.querySelectorAll('.post-body h2')).map(e=>e.textContent.trim()),
            focusBlock: !(document.getElementById('focus-block')||{hidden:true}).hidden,
          };
        }""")

        pg.screenshot(path=os.path.join(args.out, f"{args.slug}__full.png"), full_page=True)
        figs = pg.query_selector_all("figure.canvas")
        for i, f in enumerate(figs):
            try:
                f.scroll_into_view_if_needed()
                t = pg.evaluate("(el)=>(el.className.match(/canvas--(\\w+)/)||[])[1]||'fig'", f)
                f.screenshot(path=os.path.join(args.out, f"{args.slug}__{i:02d}_{t}.png"))
            except Exception:
                pass
        b.close()

    problems = []
    if report["figures"] == 0: problems.append("no figures rendered")
    if report["degraded"]: problems.append(f"{report['degraded']} degraded (data-canvas-error) block(s)")
    if report["leftover"]: problems.append(f"{report['leftover']} unrendered ```canvas``` block(s)")
    hard_errors = [e for e in errors if e.startswith(("error", "pageerror"))]
    if hard_errors: problems.append(f"{len(hard_errors)} console error(s)")

    print(json.dumps({"url": url, **report, "console": errors, "crops_dir": args.out}, indent=2))
    if problems:
        print("\nFAIL: " + "; ".join(problems))
        print(f"Inspect crops in {args.out}/ and fix, then re-run.")
        return 1
    print(f"\nOK: {report['figures']} figures rendered, no errors/degraded blocks.")
    print(f"Now READ the crops in {args.out}/ — every figure must be legible & premium.")
    return 0

if __name__ == "__main__":
    sys.exit(main())

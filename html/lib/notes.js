/* notes.js — margin notes on blog posts and wiki pages.
 *
 * Served by serve.py → notes persist to raw/notes/web/<ctx>-<slug>.md (the
 * repo's raw zone; the LLM integrates them next session). Served by plain
 * http.server → degrades to localStorage + an export button. Zero deps.
 *
 * Context detection: /html/post.html?slug=…        → ctx "blog"
 *                    /html/portal/page.html?slug=… → ctx "wiki"
 */
(function () {
  "use strict";

  var slug = new URLSearchParams(location.search).get("slug");
  if (!slug || !/^[a-z0-9][a-z0-9._-]*$/.test(slug)) return;
  var ctx = location.pathname.indexOf("/portal/") !== -1 ? "wiki" : "blog";
  var lsKey = "deeplr-notes:" + ctx + ":" + slug;
  var apiOk = null; // null = unknown, probed on first open

  // ---------- styles ----------
  var css = [
    "#dlr-notes-btn{position:fixed;right:18px;bottom:18px;z-index:9000;",
    "font:600 13px/1 system-ui,sans-serif;padding:10px 14px;border-radius:20px;",
    "border:1px solid #b8b2a7;background:#fffdf7;color:#3f3a33;cursor:pointer;",
    "box-shadow:0 2px 8px rgba(0,0,0,.12)}",
    "#dlr-notes-btn:hover{background:#f4efe4}",
    "#dlr-notes-panel{position:fixed;right:18px;bottom:64px;z-index:9001;",
    "width:min(360px,calc(100vw - 36px));max-height:70vh;display:none;",
    "flex-direction:column;background:#fffdf7;border:1px solid #b8b2a7;",
    "border-radius:10px;box-shadow:0 6px 24px rgba(0,0,0,.18);",
    "font:14px/1.5 system-ui,sans-serif;color:#3f3a33}",
    "#dlr-notes-panel.open{display:flex}",
    "#dlr-notes-head{padding:10px 14px;border-bottom:1px solid #e5dfd2;",
    "display:flex;justify-content:space-between;align-items:center}",
    "#dlr-notes-head b{font-size:13px}",
    "#dlr-notes-mode{font-size:11px;color:#8a8375}",
    "#dlr-notes-list{overflow-y:auto;padding:10px 14px;flex:1;min-height:40px}",
    "#dlr-notes-list pre{white-space:pre-wrap;font:12px/1.5 ui-monospace,monospace;",
    "margin:0;color:#55503f}",
    "#dlr-notes-list .dlr-empty{color:#8a8375;font-size:12px}",
    "#dlr-notes-form{border-top:1px solid #e5dfd2;padding:10px 14px;display:flex;",
    "flex-direction:column;gap:8px}",
    "#dlr-notes-quote{font-size:11px;color:#8a8375;border-left:3px solid #d8d0bd;",
    "padding-left:8px;max-height:60px;overflow:hidden}",
    "#dlr-notes-text{resize:vertical;min-height:64px;font:13px/1.5 system-ui,sans-serif;",
    "padding:8px;border:1px solid #cfc8b8;border-radius:6px;background:#fff}",
    "#dlr-notes-actions{display:flex;gap:8px;justify-content:flex-end}",
    "#dlr-notes-actions button{font:600 12px/1 system-ui,sans-serif;padding:8px 12px;",
    "border-radius:6px;border:1px solid #b8b2a7;background:#fff;cursor:pointer}",
    "#dlr-notes-save{background:#3f3a33!important;color:#fffdf7!important}"
  ].join("");
  var style = document.createElement("style");
  style.textContent = css;
  document.head.appendChild(style);

  // ---------- dom ----------
  var btn = document.createElement("button");
  btn.id = "dlr-notes-btn";
  btn.textContent = "✎ notes";
  var panel = document.createElement("div");
  panel.id = "dlr-notes-panel";
  panel.innerHTML =
    '<div id="dlr-notes-head"><b>Notes — <span id="dlr-notes-slug"></span></b>' +
    '<span id="dlr-notes-mode">…</span></div>' +
    '<div id="dlr-notes-list"><span class="dlr-empty">loading…</span></div>' +
    '<div id="dlr-notes-form">' +
    '<div id="dlr-notes-quote" hidden></div>' +
    '<textarea id="dlr-notes-text" placeholder="write a note… (saved to raw/notes/web/ when served by serve.py)"></textarea>' +
    '<div id="dlr-notes-actions">' +
    '<button id="dlr-notes-export" hidden>export .md</button>' +
    '<button id="dlr-notes-save">save</button></div></div>';

  function $(id) { return document.getElementById(id); }

  function mount() {
    document.body.appendChild(btn);
    document.body.appendChild(panel);
    $("dlr-notes-slug").textContent = slug;
    btn.addEventListener("click", toggle);
    $("dlr-notes-save").addEventListener("click", save);
    $("dlr-notes-export").addEventListener("click", exportLocal);
  }

  function toggle() {
    var open = panel.classList.toggle("open");
    if (!open) return;
    // Capture the current selection as a quote for the note.
    var sel = String(window.getSelection ? window.getSelection() : "").trim();
    var q = $("dlr-notes-quote");
    if (sel) { q.hidden = false; q.textContent = sel.slice(0, 400); q.dataset.sel = sel.slice(0, 1200); }
    else { q.hidden = true; q.textContent = ""; delete q.dataset.sel; }
    refresh();
  }

  // ---------- storage ----------
  function probe() {
    return fetch("/api/notes?ctx=" + ctx + "&slug=" + encodeURIComponent(slug))
      .then(function (r) { if (!r.ok) throw 0; return r.json(); })
      .then(function (j) { apiOk = true; return j; })
      .catch(function () { apiOk = false; return null; });
  }

  function localNotes() {
    try { return JSON.parse(localStorage.getItem(lsKey) || "[]"); }
    catch (e) { return []; }
  }

  function localMarkdown() {
    return localNotes().map(function (n) {
      var s = "## [" + n.ts + "]\n\n";
      if (n.selection) s += n.selection.split("\n").map(function (l) { return "> " + l; }).join("\n") + "\n\n";
      return s + n.text + "\n";
    }).join("\n");
  }

  function refresh() {
    probe().then(function (j) {
      var list = $("dlr-notes-list");
      var mode = $("dlr-notes-mode");
      var exp = $("dlr-notes-export");
      if (apiOk) {
        mode.textContent = "→ raw/notes/web/";
        exp.hidden = true;
        var md = (j && j.markdown) || "";
        list.innerHTML = md
          ? "<pre></pre>"
          : '<span class="dlr-empty">no notes yet on this page</span>';
        if (md) list.querySelector("pre").textContent = md;
        btn.textContent = "✎ notes" + (j && j.count ? " (" + j.count + ")" : "");
      } else {
        mode.textContent = "local only (serve.py not running)";
        exp.hidden = false;
        var md2 = localMarkdown();
        list.innerHTML = md2
          ? "<pre></pre>"
          : '<span class="dlr-empty">no notes yet (stored in this browser — use export)</span>';
        if (md2) list.querySelector("pre").textContent = md2;
        var n = localNotes().length;
        btn.textContent = "✎ notes" + (n ? " (" + n + ")" : "");
      }
      list.scrollTop = list.scrollHeight;
    });
  }

  function save() {
    var ta = $("dlr-notes-text");
    var text = ta.value.trim();
    if (!text) return;
    var q = $("dlr-notes-quote");
    var selection = q.dataset.sel || "";
    var title = document.title || "";
    var done = function () { ta.value = ""; q.hidden = true; delete q.dataset.sel; refresh(); };
    if (apiOk) {
      fetch("/api/notes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ctx: ctx, slug: slug, title: title, selection: selection, text: text })
      }).then(function (r) { if (!r.ok) throw 0; return r.json(); })
        .then(done)
        .catch(function () { apiOk = false; saveLocal(text, selection); done(); });
    } else {
      saveLocal(text, selection);
      done();
    }
  }

  function saveLocal(text, selection) {
    var ns = localNotes();
    var d = new Date();
    var pad = function (x) { return String(x).padStart(2, "0"); };
    ns.push({
      ts: d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()) +
          " " + pad(d.getHours()) + ":" + pad(d.getMinutes()),
      selection: selection, text: text
    });
    try { localStorage.setItem(lsKey, JSON.stringify(ns)); } catch (e) { /* full */ }
  }

  function exportLocal() {
    var md = "# Web notes — " + ctx + "/" + slug + " (exported from localStorage)\n\n" + localMarkdown();
    var blob = new Blob([md], { type: "text/markdown" });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = ctx + "-" + slug + ".md";
    a.click();
    URL.revokeObjectURL(a.href);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
  } else {
    mount();
  }
})();

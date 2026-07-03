/* =========================================================================
   deep-lr — markdown renderer wrapper
   Loads marked.js from CDN once, exposes window.BlogMarkdown.render(md).

   Extensions:
     - Resolves Obsidian-style [[entity-slug]] citations to discreet links
       pointing at /wiki/entities/<slug>.md. Rewrite is text-only so the
       user can decide later whether to render targets in-blog or just
       link out to raw Obsidian files.
   ========================================================================= */

(function () {
  "use strict";

  const MARKED_SRC = "https://cdn.jsdelivr.net/npm/marked/marked.min.js";

  // [[slug]] or [[slug|display text]]
  const WIKI_RE = /\[\[([^\[\]\|\n]+)(?:\|([^\[\]\n]+))?\]\]/g;

  function expandWikiCitations(md) {
    return md.replace(WIKI_RE, function (_m, slug, display) {
      const target = slug.trim();
      const safe = target.replace(/[^A-Za-z0-9._\-\/]/g, "-");
      const label = (display || target).trim();
      const url = "/wiki/entities/" + safe + ".md";
      // Markdown link with a class hook for styling. Marked will keep
      // attributes on inline HTML; we use an <a> directly for that reason.
      return '<a class="wiki-cite" href="' + url + '" target="_blank" rel="noopener">' +
        escapeAttr(label) + "</a>";
    });
  }

  function escapeAttr(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function basicFallback(md) {
    // Extreme fallback if marked.js fails to load: escape and pre-wrap.
    return '<pre style="white-space:pre-wrap; font-family:inherit;">' +
      escapeAttr(md) + "</pre>";
  }

  let markedPromise = null;
  function loadMarked() {
    if (window.marked) return Promise.resolve(window.marked);
    if (markedPromise) return markedPromise;
    markedPromise = new Promise(function (resolve, reject) {
      const s = document.createElement("script");
      s.src = MARKED_SRC;
      s.async = true;
      s.onload = function () { resolve(window.marked); };
      s.onerror = function () { reject(new Error("failed to load marked.js")); };
      document.head.appendChild(s);
    });
    return markedPromise;
  }

  // Render is sync from the caller's view by short-circuiting if marked is
  // already present; otherwise we kick off the load and let the caller retry,
  // but to keep call sites simple we expose a sync + async path.

  function renderSync(md) {
    if (!window.marked) return basicFallback(md || "");
    const pre = expandWikiCitations(String(md || ""));
    try {
      const m = window.marked;
      // marked v4+: marked.parse; older: marked()
      if (typeof m.parse === "function") return m.parse(pre);
      if (typeof m === "function") return m(pre);
    } catch (e) {
      return basicFallback(md || "");
    }
    return basicFallback(md || "");
  }

  function renderAsync(md) {
    return loadMarked().then(function () { return renderSync(md); },
      function () { return basicFallback(md || ""); });
  }

  // Public API. Callers can use the sync form once marked has loaded.
  window.BlogMarkdown = {
    render: function (md) {
      // If marked isn't loaded yet, kick off load and return a placeholder
      // that will be replaced once marked is ready. To keep blog.js simple
      // we synchronously block-load via XHR? No — instead we run the async
      // version and return its result via a sentinel that triggers a re-render.
      if (window.marked) return renderSync(md);
      // Fire-and-forget load; consumers should call renderAsync if they
      // need the resolved HTML. For our consumer (blog.js) we want the
      // first call to wait, so we use a synchronous-ish bridge by loading
      // marked before invocation. blog.js calls render *after* DOM ready
      // and post fetch, which gives marked.js time to land, but we don't
      // rely on that — we kick the load now and return a temporary node
      // that will be swapped in by renderAsyncInto.
      loadMarked(); // start loading
      return basicFallback(md);
    },
    renderAsync: renderAsync,
    loadMarked: loadMarked
  };

  // Kick off marked loading immediately so it's likely ready by the time
  // the post body needs rendering.
  loadMarked().catch(function () { /* swallow — fallback already covers */ });
})();

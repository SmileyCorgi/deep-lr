/* =========================================================================
   deep-lr — Portal shared client
   Owns:
     - data load (index.json) with caching
     - ⌘K palette (instant fuzzy over slug+title+tags; recent queries in localStorage)
     - wikilink resolver: rewrites [[slug]] in rendered HTML to portal links
       with hover-card preview (TL;DR pulled from the prebuilt index)
     - tiny markdown wrapper around marked.js (CDN; reused from blog)
   ========================================================================= */

(function () {
  "use strict";

  const INDEX_URL = "/html/portal/index.json";
  const MARKED_SRC = "https://cdn.jsdelivr.net/npm/marked/marked.min.js";
  const RECENT_KEY = "ar.portal.recent";
  const RECENT_MAX = 8;

  let indexPromise = null;
  let markedPromise = null;

  // -------- index ---------------------------------------------------------
  function loadIndex() {
    if (indexPromise) return indexPromise;
    indexPromise = fetch(INDEX_URL, { cache: "no-cache" }).then(function (r) {
      if (!r.ok) throw new Error("index.json HTTP " + r.status);
      return r.json();
    }).then(function (idx) {
      // Build lookup maps once.
      idx._bySlug = {};
      (idx.pages || []).forEach(function (p) { idx._bySlug[p.slug] = p; });
      return idx;
    });
    return indexPromise;
  }

  // -------- marked --------------------------------------------------------
  function loadMarked() {
    if (window.marked) return Promise.resolve(window.marked);
    if (markedPromise) return markedPromise;
    markedPromise = new Promise(function (resolve, reject) {
      const s = document.createElement("script");
      s.src = MARKED_SRC; s.async = true;
      s.onload = function () { resolve(window.marked); };
      s.onerror = function () { reject(new Error("marked.js load failed")); };
      document.head.appendChild(s);
    });
    return markedPromise;
  }

  // -------- wikilink preprocessing ---------------------------------------
  // Convert [[slug]] in raw markdown to an <a> with class="wiki" so marked
  // can pass it through and we don't have to re-walk DOM after render.
  const WIKI_RE = /\[\[([A-Za-z0-9][A-Za-z0-9._\-\/]*)(?:\|([^\]\n]+))?\]\]/g;

  function expandWikilinks(md, idx) {
    return md.replace(WIKI_RE, function (_m, slug, display) {
      const target = slug.trim();
      const label = (display || target).trim();
      const exists = idx._bySlug.hasOwnProperty(target);
      const cls = exists ? "wiki" : "wiki broken";
      const title = exists ? "" : ' title="not in wiki"';
      const href = exists
        ? "/html/portal/page.html?slug=" + encodeURIComponent(target)
        : "/wiki/entities/" + encodeURIComponent(target) + ".md";
      return '<a class="' + cls + '" data-slug="' + escapeAttr(target) +
             '" href="' + href + '"' + title + '>' + escapeHtml(label) + "</a>";
    });
  }

  function escapeAttr(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function escapeHtml(s) { return escapeAttr(s); }

  // -------- public: render markdown --------------------------------------
  function renderMarkdown(md, mountEl) {
    return Promise.all([loadIndex(), loadMarked()]).then(function (arr) {
      const idx = arr[0];
      const marked = arr[1];
      const expanded = expandWikilinks(md, idx);
      mountEl.innerHTML = marked.parse(expanded);
      attachWikiHovercards(mountEl, idx);
      return idx;
    });
  }

  // -------- hover cards ---------------------------------------------------
  let hcEl = null;
  function ensureHc() {
    if (hcEl) return hcEl;
    hcEl = document.createElement("div");
    hcEl.className = "hovercard";
    hcEl.style.display = "none";
    document.body.appendChild(hcEl);
    return hcEl;
  }
  function showHc(target, slug, idx) {
    const p = idx._bySlug[slug];
    if (!p) return;
    const hc = ensureHc();
    let meta = "";
    if (p.type === "entity") {
      const bits = [p.venue, p.track].filter(Boolean).join(" · ");
      meta = bits || "entity";
    } else {
      meta = p.type;
    }
    hc.innerHTML =
      '<div class="hc-title">' + escapeHtml(p.title || p.slug) + "</div>" +
      '<div class="hc-meta">' + escapeHtml(meta) + "</div>" +
      '<div class="hc-body">' + escapeHtml(p.tldr || "(no preview)") + "</div>";
    const r = target.getBoundingClientRect();
    hc.style.display = "block";
    const top = window.scrollY + r.bottom + 6;
    const maxLeft = window.innerWidth - hc.offsetWidth - 8;
    const left = Math.min(window.scrollX + r.left, maxLeft);
    hc.style.left = left + "px";
    hc.style.top = top + "px";
  }
  function hideHc() {
    if (hcEl) hcEl.style.display = "none";
  }

  function attachWikiHovercards(root, idx) {
    const links = root.querySelectorAll("a.wiki[data-slug]");
    links.forEach(function (a) {
      if (a.classList.contains("broken")) return;
      a.addEventListener("mouseenter", function () {
        showHc(a, a.getAttribute("data-slug"), idx);
      });
      a.addEventListener("mouseleave", hideHc);
    });
  }

  // -------- rail ----------------------------------------------------------
  const RAIL_ITEMS = [
    { href: "/html/portal/index.html",      icon: "⌂", label: "Home", active: "home" },
    { href: "/html/portal/topics.html",     icon: "T", label: "Topics", active: "topics" },
    { href: "/html/portal/entities.html",   icon: "E", label: "Entities", active: "entities" },
    { href: "/html/portal/synthesis.html",  icon: "S", label: "Synthesis", active: "synthesis" },
    { href: "/html/portal/graph.html",      icon: "◯", label: "Graph", active: "graph" },
    { href: "/html/portal/activity.html",   icon: "A", label: "Activity", active: "activity" },
  ];

  function mountRail(activeKey) {
    const shell = document.querySelector(".shell");
    if (!shell) return;
    const rail = document.createElement("aside");
    rail.className = "rail";
    let html = '<a class="rail-brand" href="/html/portal/index.html"><span class="dot"></span>AR</a>';
    html += '<nav>';
    RAIL_ITEMS.forEach(function (it) {
      const cls = it.active === activeKey ? "active" : "";
      html += '<a href="' + it.href + '" class="' + cls + '">' +
              '<span class="icon">' + it.icon + "</span>" + it.label + "</a>";
    });
    html += "</nav>";
    html += '<div class="rail-foot">' +
            '<a href="/html/index.html" title="blog">Blog →</a>' +
            '<a href="#" id="open-palette" title="cmd-K">' +
              '<kbd>⌘K</kbd>' +
            '</a></div>';
    rail.innerHTML = html;
    shell.insertBefore(rail, shell.firstChild);
    document.getElementById("open-palette").addEventListener("click", function (e) {
      e.preventDefault(); openPalette();
    });
  }

  // -------- palette -------------------------------------------------------
  let paletteEl = null;
  let paletteState = { open: false, results: [], cursor: 0, items: [] };

  function buildPaletteItems(idx) {
    const items = [];
    (idx.pages || []).forEach(function (p) {
      if (p.type === "corpus") return; // hide corpus pages from palette by default
      items.push({
        slug: p.slug,
        title: p.title || p.slug,
        type: p.type,
        hint: p.type === "entity"
          ? [p.venue, p.track].filter(Boolean).join(" · ")
          : (p.tldr || "").slice(0, 80),
        haystack: (p.slug + " " + (p.title || "") + " " +
                   (p.tags || []).join(" ") + " " +
                   (p.venue || "") + " " +
                   (p.category || "")).toLowerCase(),
        href: "/html/portal/page.html?slug=" + encodeURIComponent(p.slug),
      });
    });
    // Add log entries as findable items too.
    (idx.log || []).forEach(function (e, i) {
      items.push({
        slug: "log#" + i,
        title: e.date + " · " + e.subject,
        type: "log:" + e.op,
        hint: e.op,
        haystack: (e.date + " " + e.op + " " + e.subject).toLowerCase(),
        href: "/html/portal/activity.html#" + i,
      });
    });
    return items;
  }

  function ensurePalette() {
    if (paletteEl) return;
    paletteEl = document.createElement("div");
    paletteEl.className = "palette-backdrop";
    paletteEl.innerHTML =
      '<div class="palette" role="dialog" aria-label="Quick find">' +
        '<input type="text" id="pal-input" placeholder="search topics, entities, log…" autocomplete="off" />' +
        '<div class="results" id="pal-results"></div>' +
        '<div class="foot">' +
          '<span><kbd>↑</kbd><kbd>↓</kbd> navigate <kbd>↵</kbd> open <kbd>esc</kbd> close</span>' +
          '<span id="pal-count">0</span>' +
        "</div>" +
      "</div>";
    document.body.appendChild(paletteEl);
    paletteEl.addEventListener("click", function (e) {
      if (e.target === paletteEl) closePalette();
    });
    document.getElementById("pal-input").addEventListener("input", paletteSearch);
    document.getElementById("pal-input").addEventListener("keydown", paletteKeydown);
    document.getElementById("pal-results").addEventListener("click", function (e) {
      let t = e.target;
      while (t && t !== this && !t.dataset.idx) t = t.parentNode;
      if (t && t.dataset.idx) {
        const i = parseInt(t.dataset.idx, 10);
        const item = paletteState.results[i];
        if (item) navigateTo(item);
      }
    });
  }

  function openPalette() {
    ensurePalette();
    loadIndex().then(function (idx) {
      paletteState.items = paletteState.items.length ? paletteState.items : buildPaletteItems(idx);
      paletteEl.classList.add("open");
      paletteState.open = true;
      const inp = document.getElementById("pal-input");
      inp.value = "";
      paletteSearch();
      setTimeout(function () { inp.focus(); }, 10);
    });
  }
  function closePalette() {
    if (!paletteEl) return;
    paletteEl.classList.remove("open");
    paletteState.open = false;
  }

  function paletteSearch() {
    const q = (document.getElementById("pal-input").value || "").trim().toLowerCase();
    const all = paletteState.items;
    let results;
    if (!q) {
      // Show recent + a default mix: topics, syntheses, then a few entities.
      const recent = (loadRecent() || []).map(function (slug) {
        return all.find(function (it) { return it.slug === slug; });
      }).filter(Boolean);
      const seen = new Set(recent.map(function (it) { return it.slug; }));
      const pri = function (it) {
        return it.type === "topic" ? 0
             : it.type === "synthesis" ? 1
             : it.type === "entity" ? 2 : 3;
      };
      const rest = all.filter(function (it) { return !seen.has(it.slug); })
                      .sort(function (a, b) { return pri(a) - pri(b) || a.title.localeCompare(b.title); })
                      .slice(0, 30);
      results = recent.concat(rest);
    } else {
      const terms = q.split(/\s+/).filter(Boolean);
      results = all.filter(function (it) {
        return terms.every(function (t) { return it.haystack.indexOf(t) !== -1; });
      });
      // Prefer slug/title prefix matches.
      results.sort(function (a, b) {
        const ap = (a.slug.startsWith(q) || a.title.toLowerCase().startsWith(q)) ? 0 : 1;
        const bp = (b.slug.startsWith(q) || b.title.toLowerCase().startsWith(q)) ? 0 : 1;
        if (ap !== bp) return ap - bp;
        return a.title.localeCompare(b.title);
      });
      results = results.slice(0, 60);
    }
    paletteState.results = results;
    paletteState.cursor = 0;
    paletteRender();
  }

  function paletteRender() {
    const box = document.getElementById("pal-results");
    const cnt = document.getElementById("pal-count");
    cnt.textContent = paletteState.results.length + " results";
    if (!paletteState.results.length) {
      box.innerHTML = '<div class="empty">no matches</div>';
      return;
    }
    box.innerHTML = paletteState.results.map(function (it, i) {
      const cur = i === paletteState.cursor ? " cursor" : "";
      return '<div class="result' + cur + '" data-idx="' + i + '">' +
               '<span class="type">' + escapeHtml(it.type) + "</span>" +
               '<span class="title">' + escapeHtml(it.title) + "</span>" +
               '<span class="hint">' + escapeHtml(it.hint || "") + "</span>" +
             "</div>";
    }).join("");
  }

  function paletteKeydown(e) {
    if (e.key === "Escape") { closePalette(); return; }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      paletteState.cursor = Math.min(paletteState.cursor + 1, paletteState.results.length - 1);
      paletteRender();
      scrollCursorIntoView();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      paletteState.cursor = Math.max(paletteState.cursor - 1, 0);
      paletteRender();
      scrollCursorIntoView();
    } else if (e.key === "Enter") {
      e.preventDefault();
      const item = paletteState.results[paletteState.cursor];
      if (item) navigateTo(item);
    }
  }
  function scrollCursorIntoView() {
    const cur = document.querySelector(".palette .result.cursor");
    if (cur) cur.scrollIntoView({ block: "nearest" });
  }

  function navigateTo(item) {
    pushRecent(item.slug);
    window.location.href = item.href;
  }
  function loadRecent() {
    try { return JSON.parse(localStorage.getItem(RECENT_KEY) || "[]"); }
    catch (_) { return []; }
  }
  function pushRecent(slug) {
    if (slug.startsWith("log#")) return;
    let arr = loadRecent();
    arr = arr.filter(function (s) { return s !== slug; });
    arr.unshift(slug);
    arr = arr.slice(0, RECENT_MAX);
    try { localStorage.setItem(RECENT_KEY, JSON.stringify(arr)); } catch (_) {}
  }

  // global keyboard shortcuts
  document.addEventListener("keydown", function (e) {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      if (paletteState.open) closePalette(); else openPalette();
      return;
    }
    if (e.key === "/" && document.activeElement && document.activeElement.tagName !== "INPUT" && document.activeElement.tagName !== "TEXTAREA") {
      e.preventDefault();
      if (!paletteState.open) openPalette();
    }
  });

  // -------- exports -------------------------------------------------------
  window.Portal = {
    loadIndex: loadIndex,
    renderMarkdown: renderMarkdown,
    mountRail: mountRail,
    openPalette: openPalette,
    closePalette: closePalette,
    escapeHtml: escapeHtml,
    escapeAttr: escapeAttr,
    expandWikilinks: expandWikilinks,
    attachWikiHovercards: attachWikiHovercards,
  };
})();

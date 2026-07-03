/* =========================================================================
   deep-lr — canvas blocks (v2: editorial / depth)
   A zero-dependency declarative diagram layer for blog posts.

   Authors write a fenced ```canvas block; marked.js emits it as
   <pre><code class="language-canvas">…</code></pre>. window.BlogCanvas.render
   runs as a stage-0 pass in renderPost (before the focus/TOC/citation stages)
   and swaps each such <pre> for a themed <figure class="canvas">.

   Five primitives: matrix · timeline · flow · bars · grid.
   No runtime dependency (marked.js is the only library, reused for inline md).

   v2 redesign (2026-06-04): the DSL is UNCHANGED — only the rendering is
   upgraded from flat wireframe to an editorial/Distill look with depth:
   layered tinted shadows, dot-grid grounds, per-column accent tints, icon
   tag pills, semantic trained/frozen state (elevated+gradient vs dashed+muted),
   gradient feedback loops with knockout label plates, era-graded timelines.
   Chosen direction: hybrid of design-explorations C (editorial) + B (depth).
   See blog/design/CHOSEN.md and blog/design/canvas-explorations/.

   Hard rule (also in blog/README): do NOT write [[slug]] inside a canvas block.
   ========================================================================= */

(function () {
  "use strict";

  var SVGNS = "http://www.w3.org/2000/svg";
  var ACCENTS = { paper: 1, deep: 1, final: 1 };
  var ACCENT_HEX = { paper: "#3B5A8C", deep: "#3A6E5B", final: "#B0552A" };
  var ACCENT_SOFT = { paper: "#f3f6fb", deep: "#f1f7f3", final: "#f7ece3" };
  var ACCENT_SOFTSTROKE = { paper: "#cfdbec", deep: "#cfe2d8", final: "#e3c4af" };
  var ACCENT_DK = { paper: "#2c466f", deep: "#2c5446", final: "#8a3f1d" };
  var ACCENT_LIST = ["paper", "deep", "final"];
  // friendly display names for single-letter matrix row labels (display only;
  // the auto-tag A1/T1 still derives from the raw letter). Falls back to raw.
  var ROW_ALIAS = { A: "Agent", T: "Tool", M: "Memory", S: "Skill" };

  var figureCounter = 0;
  var svgUid = 0;

  /* ---------- string helpers ---------- */

  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function inlineMd(s) {
    var out = escapeHtml(s);
    out = out.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    out = out.replace(/\*([^*]+)\*/g, "<em>$1</em>");
    out = out.replace(/`([^`]+)`/g, "<code>$1</code>");
    out = out.replace(/\[([^\]]+)\]\(([^)]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener">$1</a>');
    return out;
  }

  function stripMd(s) {
    return String(s == null ? "" : s)
      .replace(/\*\*([^*]+)\*\*/g, "$1")
      .replace(/\*([^*]+)\*/g, "$1")
      .replace(/`([^`]+)`/g, "$1")
      .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1");
  }

  function splitPipes(s) {
    return String(s == null ? "" : s).split("|").map(function (x) { return x.trim(); });
  }

  function wrap(text, maxChars, maxLines) {
    var words = String(text).split(/\s+/).filter(Boolean);
    var lines = [], cur = "";
    for (var i = 0; i < words.length; i++) {
      var w = words[i];
      if (cur && (cur + " " + w).length > maxChars) { lines.push(cur); cur = w; }
      else { cur = cur ? cur + " " + w : w; }
    }
    if (cur) lines.push(cur);
    if (maxLines && lines.length > maxLines) {
      lines = lines.slice(0, maxLines);
      lines[maxLines - 1] = lines[maxLines - 1].replace(/.$/, "…");
    }
    return lines;
  }

  function accentHexOf(name) { return ACCENT_HEX[name] || ACCENT_HEX.paper; }

  /* ---------- inline-SVG icon set (lucide-ish, 24x24 stroke paths) ---------- */
  var ICONS = {
    agent: '<rect x="5" y="5" width="14" height="14" rx="2"/><rect x="9" y="9" width="6" height="6" rx="1"/><path d="M9 2v2M15 2v2M9 20v2M15 20v2M2 9h2M2 15h2M20 9h2M20 15h2"/>',
    tool: '<path d="M14.7 6.3a4 4 0 0 0-5.6 5.6l-6.4 6.4a1.5 1.5 0 0 0 2.1 2.1l6.4-6.4a4 4 0 0 0 5.6-5.6l-2.6 2.6-2.1-2.1z"/>',
    reward: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.4"/>',
    input: '<path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><path d="M10 17l5-5-5-5"/><path d="M15 12H3"/>',
    output: '<path d="M5 3H3a0 0 0 0 0 0 0v18a0 0 0 0 0 0 0h2"/><path d="M9 7l5 5-5 5"/><path d="M14 12H4"/>',
    memory: '<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M9 4v16M15 4v16M4 9h5M4 15h5M15 9h5M15 15h5"/>',
    flame: '<path d="M12 2c1 3 1 5 1 8 1 0 2-1 2-3 2 2 3 4 3 6a6 6 0 0 1-12 0c0-4 3-7 6-11z"/>',
    frozen: '<path d="M12 2v20M4.2 7l15.6 10M19.8 7L4.2 17"/>',
    node: '<circle cx="12" cy="12" r="4"/>'
  };
  function iconFor(label) {
    var s = String(label || "").toLowerCase();
    if (/agent|policy|model|llm/.test(s)) return "agent";
    if (/memor|store|cache|kv/.test(s)) return "memory";
    if (/tool|retriev|search|exec|code|env/.test(s)) return "tool";
    if (/reward|signal|score|verif/.test(s)) return "reward";
    if (/output|answer|response/.test(s)) return "output";
    if (/input|query|task|prompt/.test(s)) return "input";
    return null;
  }
  // an <svg> icon element for HTML contexts (matrix/grid tag pills)
  function iconEl(name, cls) {
    if (!name || !ICONS[name]) return null;
    var e = document.createElementNS(SVGNS, "svg");
    e.setAttribute("viewBox", "0 0 24 24");
    e.setAttribute("fill", "none");
    e.setAttribute("stroke", "currentColor");
    e.setAttribute("stroke-width", "2.2");
    e.setAttribute("stroke-linecap", "round");
    e.setAttribute("stroke-linejoin", "round");
    e.setAttribute("class", cls || "cv-ico");
    e.innerHTML = ICONS[name];
    return e;
  }

  /* ---------- SVG helpers ---------- */

  function svg(name, attrs) {
    var e = document.createElementNS(SVGNS, name);
    if (attrs) for (var k in attrs) if (attrs.hasOwnProperty(k)) e.setAttribute(k, attrs[k]);
    return e;
  }

  function svgText(x, y, str, opts) {
    opts = opts || {};
    var t = svg("text", {
      x: x, y: y, "text-anchor": opts.anchor || "middle",
      "font-size": opts.size || 13, "font-weight": opts.weight || 400
    });
    if (opts.mono) t.setAttribute("class", "mono");
    if (opts.fill) t.setAttribute("fill", opts.fill);
    if (opts.style) t.setAttribute("font-style", opts.style);
    if (opts.spacing) t.setAttribute("letter-spacing", opts.spacing);
    t.textContent = str;
    return t;
  }

  // build an <svg> with a <defs> carrying: layered soft shadow, ink + accent
  // arrow markers, and a vertical accent gradient. ids are uid-suffixed so
  // multiple canvases on one page never cross-reference.
  function makeSvg(w, h, accentHex) {
    var uid = "cv" + (++svgUid);
    var root = svg("svg", { viewBox: "0 0 " + w + " " + h, role: "presentation" });
    root.setAttribute("preserveAspectRatio", "xMidYMid meet");
    root.style.overflow = "visible";
    var defs = svg("defs");
    // two-layer tinted soft shadow
    var f = svg("filter", { id: uid + "-soft", x: "-30%", y: "-40%", width: "160%", height: "190%" });
    f.appendChild(svg("feDropShadow", { dx: 0, dy: 1, stdDeviation: 1, "flood-color": "#2a2622", "flood-opacity": 0.10 }));
    f.appendChild(svg("feDropShadow", { dx: 0, dy: 6, stdDeviation: 9, "flood-color": "#2a2622", "flood-opacity": 0.13 }));
    defs.appendChild(f);
    // markers
    function marker(id, color, w2) {
      var m = svg("marker", { id: id, viewBox: "0 0 10 10", refX: 8.5, refY: 5, markerWidth: w2 || 7, markerHeight: w2 || 7, orient: "auto-start-reverse" });
      m.appendChild(svg("path", { d: "M0 0 L10 5 L0 10 z", fill: color }));
      return m;
    }
    defs.appendChild(marker(uid + "-arr", "#4A4842"));
    defs.appendChild(marker(uid + "-arrA", accentHex, 7.5));
    // vertical accent gradient (available for future use)
    var g = svg("linearGradient", { id: uid + "-grad", x1: 0, y1: 0, x2: 0, y2: 1 });
    g.innerHTML = '<stop offset="0" stop-color="' + accentHex + '" stop-opacity="0.95"/><stop offset="1" stop-color="' + accentHex + '"/>';
    defs.appendChild(g);
    root.appendChild(defs);
    return { root: root, uid: uid, shadow: "url(#" + uid + "-soft)", arr: "url(#" + uid + "-arr)", arrA: "url(#" + uid + "-arrA)", grad: "url(#" + uid + "-grad)" };
  }

  /* ---------- spec parser (UNCHANGED DSL) ---------- */
  var DIRECTIVE = /^(caption|source|accent|cols|rows|axis|loop|state|note)\s*:(?!:)\s*([\s\S]*)$/;

  function parseSpec(raw) {
    var lines = String(raw == null ? "" : raw).replace(/\r/g, "").split("\n");
    var type = null, dirs = {}, rows = [];
    for (var i = 0; i < lines.length; i++) {
      var t = lines[i].trim();
      if (!t) continue;
      if (type === null) {
        var mt = /^type\s*:\s*([A-Za-z]+)/.exec(t);
        if (!mt) throw new Error("canvas: first line must be `type: <name>`");
        type = mt[1].toLowerCase();
        continue;
      }
      var d = DIRECTIVE.exec(t);
      if (d) { dirs[d[1]] = d[2].trim(); continue; }
      rows.push(t);
    }
    if (!type) throw new Error("canvas: missing type");
    return { type: type, dirs: dirs, rows: rows };
  }

  // split a rich matrix/flow cell into {title, body, chips} without DSL change.
  // "**A1 · Title** — method text. `Model`, `Model`" → title/body/chips
  function parseCell(md) {
    var title = "", rest = String(md == null ? "" : md);
    var tm = /^\s*\*\*([^*]+)\*\*\s*/.exec(rest);
    if (tm) { title = tm[1].trim(); rest = rest.slice(tm[0].length); }
    rest = rest.replace(/^\s*[—–-]\s*/, "");
    var chips = [];
    rest = rest.replace(/`([^`]+)`/g, function (_m, c) { chips.push(c); return ""; });
    rest = rest.replace(/\s*,\s*,/g, ",").replace(/[\s,]+$/, "").replace(/\s{2,}/g, " ").trim();
    // strip a leading "A1 · " style tag from the title (the pill already shows it)
    title = title.replace(/^[A-Za-z]\d+\s*[·∙.\-:]\s*/, "").trim();
    return { title: title, body: rest, chips: chips };
  }

  /* ---------- figure shell ---------- */

  function makeFigure(type, dirs) {
    var fig = document.createElement("figure");
    fig.className = "canvas canvas--" + type;
    var accent = (dirs.accent || "paper").trim();
    fig.setAttribute("data-accent", ACCENTS[accent] ? accent : "paper");
    fig.setAttribute("role", "img");
    if (dirs.caption) fig.setAttribute("aria-label", stripMd(dirs.caption));
    return fig;
  }

  function addCaption(fig, dirs, n) {
    if (!dirs.caption && !dirs.source) return;
    var fc = document.createElement("figcaption");
    var html = '<span class="canvas-num">Figure ' + n + "</span>";
    if (dirs.source) html += '<span class="canvas-source">' + escapeHtml(dirs.source) + "</span>";
    if (dirs.caption) html += inlineMd(dirs.caption);
    fc.innerHTML = html;
    fig.appendChild(fc);
  }

  function chipRow(chips, accentName) {
    if (!chips || !chips.length) return null;
    var ex = document.createElement("div");
    ex.className = "cv-ex";
    var lbl = document.createElement("span"); lbl.className = "cv-ex-lbl"; lbl.textContent = "e.g.";
    ex.appendChild(lbl);
    chips.forEach(function (c) {
      var s = document.createElement("span"); s.className = "cv-chip"; s.textContent = c; ex.appendChild(s);
    });
    return ex;
  }

  /* ============================ primitives ============================ */

  /* --- matrix: NxM, CSS grid, per-column accent, icon tag, depth --- */
  function renderMatrix(spec) {
    var rowLabels = splitPipes(spec.dirs.rows || "");
    var colLabels = splitPipes(spec.dirs.cols || "");
    if (!rowLabels.length || !colLabels.length)
      throw new Error("canvas matrix: needs `rows:` and `cols:`");
    var nCols = colLabels.length;
    var cells = {};
    spec.rows.forEach(function (r) {
      var m = /^(\d+)\s*,\s*(\d+)\s*::\s*([\s\S]*)$/.exec(r);
      if (m) cells[m[1] + "," + m[2]] = m[3].trim();
    });
    var autoTag = rowLabels.every(function (l) { return /^[A-Za-z]$/.test(l); });

    var mx = el("div", "cv-matrix");
    var axc = el("div", "cv-ax-cols"); axc.innerHTML = "<span>Signal source &rarr;</span>";
    var axr = el("div", "cv-ax-rows"); axr.innerHTML = "<span>What is optimized &darr;</span>";
    mx.appendChild(axc); mx.appendChild(axr);

    var grid = el("div", "cv-matrix-grid");
    grid.style.gridTemplateColumns = "112px repeat(" + nCols + ", 1fr)";

    // header row
    grid.appendChild(el("div", "cv-corner"));
    colLabels.forEach(function (c, ci) {
      var h = el("div", "cv-colhead");
      h.style.setProperty("--qc", accentHexOf(ACCENT_LIST[ci % 3]));
      h.innerHTML = '<span class="ch">' + inlineMd(c) + "</span>";
      grid.appendChild(h);
    });

    for (var ri = 0; ri < rowLabels.length; ri++) {
      var rawRow = rowLabels[ri];
      var rh = el("div", "cv-rowhead");
      var disp = autoTag ? (ROW_ALIAS[rawRow.toUpperCase()] || rawRow) : rawRow;
      rh.innerHTML = '<span class="inner">' + escapeHtml(disp) + "</span>";
      grid.appendChild(rh);
      var rowIcon = iconFor(disp) || (autoTag ? (/^a/i.test(rawRow) ? "agent" : "tool") : null);
      for (var ci2 = 0; ci2 < nCols; ci2++) {
        var hex = accentHexOf(ACCENT_LIST[ci2 % 3]);
        var cell = el("div", "cv-cell");
        cell.style.setProperty("--qc", hex);
        var parsed = parseCell(cells[(ri + 1) + "," + (ci2 + 1)] || "");
        if (autoTag) {
          var tag = el("span", "cv-tag");
          var ic = iconEl(rowIcon, "cv-tag-ico"); if (ic) tag.appendChild(ic);
          tag.appendChild(document.createTextNode(rawRow + (ci2 + 1)));
          cell.appendChild(tag);
        }
        if (parsed.title) {
          var ttl = el("p", "cv-cell-title"); ttl.innerHTML = inlineMd(parsed.title); cell.appendChild(ttl);
        }
        if (parsed.body) {
          var bd = el("p", "cv-cell-body"); bd.innerHTML = inlineMd(parsed.body); cell.appendChild(bd);
        }
        var ex = chipRow(parsed.chips); if (ex) cell.appendChild(ex);
        grid.appendChild(cell);
      }
    }
    mx.appendChild(grid);
    return mx;
  }

  /* --- flow: elevated cards, semantic trained/frozen, gradient loop --- */
  function renderFlow(spec) {
    var chainLine = spec.rows.find(function (r) { return r.indexOf("->") !== -1; }) || "";
    var nodes = chainLine.split("->").map(function (x) { return x.trim(); }).filter(Boolean);
    if (!nodes.length) throw new Error("canvas flow: needs a `A -> B -> C` chain");
    var state = {};
    if (spec.dirs.state) spec.dirs.state.split(",").forEach(function (p) {
      var kv = p.split("="); if (kv.length === 2) state[kv[0].trim()] = kv[1].trim().toLowerCase();
    });
    var accentName = (spec.dirs.accent || "paper");
    var accentHex = accentHexOf(accentName), accentDk = ACCENT_DK[accentName] || "#2c466f";
    var finalHex = ACCENT_HEX.final;

    var n = nodes.length;
    var PAD = 14, BW = 150, GAP = 52, BH = 70, topY = 40;
    var totalW = PAD * 2 + n * BW + (n - 1) * GAP;
    var hasLoop = !!spec.dirs.loop, hasNote = !!spec.dirs.note;
    var midY = topY + BH / 2;
    var loopDip = topY + BH + 70;
    var plateY = loopDip - 6;
    var noteY = (hasLoop ? loopDip + 30 : topY + BH + 30);
    var totalH = noteY + (hasNote ? 6 : -10);
    var S = makeSvg(totalW, totalH, accentHex);
    var root = S.root;

    function boxX(i) { return PAD + i * (BW + GAP); }
    function role(node) {
      var s = node.toLowerCase();
      if (state[node] === "trained") return "trained";
      if (state[node] === "frozen") return "frozen";
      if (/reward|signal|score/.test(s)) return "reward";
      if (/output|answer/.test(s)) return "reward";
      if (/input|query|task|prompt/.test(s)) return "input";
      return "neutral";
    }

    // forward connectors
    for (var i = 0; i < n - 1; i++) {
      var x1 = boxX(i) + BW, x2 = boxX(i + 1);
      root.appendChild(svg("line", { x1: x1 + 3, y1: midY, x2: x2 - 3, y2: midY, stroke: "#4A4842", "stroke-width": 1.7, "marker-end": S.arr }));
    }

    // feedback loop (drawn under boxes, before boxes so plate sits above line)
    if (hasLoop) {
      var lp = splitPipes(spec.dirs.loop);
      var ends = lp[0].split("->").map(function (x) { return x.trim(); });
      var label = lp[1] || "";
      var si = nodes.indexOf(ends[0]), ti = nodes.indexOf(ends[1]);
      if (si !== -1 && ti !== -1) {
        var sx = boxX(si) + BW / 2, tx = boxX(ti) + BW / 2, by = topY + BH;
        root.appendChild(svg("path", {
          d: "M" + sx + " " + by + " C " + sx + " " + loopDip + ", " + tx + " " + (loopDip + 10) + ", " + tx + " " + (by + 4),
          fill: "none", stroke: finalHex, "stroke-width": 1.9, "stroke-dasharray": "7 5", "marker-end": S.arrA, class: "cv-loop-path"
        }));
        if (label) {
          var lw = Math.min(300, 13 + stripMd(label).length * 6.6);
          var cxm = (sx + tx) / 2;
          root.appendChild(svg("rect", { x: cxm - lw / 2, y: plateY - 13, width: lw, height: 24, rx: 12, fill: ACCENT_SOFT.final, stroke: "#e3c4af" }));
          root.appendChild(svgText(cxm, plateY + 3.5, stripMd(label), { size: 11.5, weight: 700, fill: finalHex, mono: true }));
        }
      }
    }

    // nodes
    nodes.forEach(function (node, i2) {
      var x = boxX(i2), r = role(node), label = stripMd(node);
      var g = svg("g");
      if (r === "trained") {
        var gg = svg("g", { filter: S.shadow });
        gg.appendChild(svg("rect", { x: x, y: topY, width: BW, height: BH, rx: 12, fill: accentHex, stroke: accentDk }));
        root.appendChild(gg);
        root.appendChild(svgText(x + BW / 2, midY - 2, label, { size: 16, weight: 700, fill: "#fff" }));
        badge(root, x + BW / 2, topY + BH - 16, "TRAINED", "#fff", "rgba(255,255,255,.16)", "flame");
      } else if (r === "frozen") {
        root.appendChild(svg("rect", { x: x, y: topY + 3, width: BW, height: BH - 6, rx: 12, fill: "#F4F1EA", stroke: "#d9d3c6", "stroke-dasharray": "5 4" }));
        root.appendChild(svgText(x + BW / 2, midY - 2, label, { size: 15.5, weight: 600, fill: "#8A877F" }));
        badge(root, x + BW / 2, topY + BH - 16, "FROZEN", "#8A877F", "#fff", "frozen", "#d9d3c6");
      } else if (r === "reward") {
        var rg = svg("g", { filter: S.shadow });
        rg.appendChild(svg("rect", { x: x, y: topY + 6, width: BW, height: BH - 12, rx: 11, fill: ACCENT_SOFT.final, stroke: "#e3c4af" }));
        root.appendChild(rg);
        root.appendChild(svgText(x + BW / 2, midY - 1, label, { size: 14.5, weight: 650, fill: finalHex }));
        root.appendChild(svgText(x + BW / 2, midY + 15, "exec. outcome", { size: 9.5, fill: "#c07a52", mono: true }));
      } else {
        root.appendChild(svg("rect", { x: x, y: topY + 8, width: BW, height: BH - 16, rx: 10, fill: "#F4F1EA", stroke: "#E4DFD3" }));
        root.appendChild(svgText(x + BW / 2, midY - 1, label, { size: 14, weight: 600, fill: "#1A1916" }));
        root.appendChild(svgText(x + BW / 2, midY + 15, "task / query", { size: 9.5, fill: "#8A877F", mono: true }));
      }
    });

    // note
    if (hasNote) root.appendChild(svgText(totalW / 2, noteY, stripMd(spec.dirs.note), { size: 11.5, fill: "#8A877F", style: "italic" }));

    // legend below the svg
    var wrapEl = document.createElement("div");
    wrapEl.appendChild(root);
    var leg = el("div", "cv-legend");
    leg.innerHTML =
      '<span class="it"><span class="sw" style="background:' + accentHex + '"></span>Trained (weights updated)</span>' +
      '<span class="it"><span class="sw dashed"></span>Frozen</span>' +
      '<span class="it"><span class="sw" style="background:' + finalHex + '"></span>Reward / signal</span>';
    wrapEl.appendChild(leg);
    return wrapEl;
  }

  function badge(root, cx, cy, txt, fg, bg, icon, stroke) {
    var w = 16 + txt.length * 6.2;
    var g = svg("g", { transform: "translate(" + (cx - w / 2) + "," + (cy - 9) + ")" });
    g.appendChild(svg("rect", { x: 0, y: 0, width: w, height: 18, rx: 9, fill: bg, stroke: stroke || "none" }));
    var tx = 9;
    if (icon && ICONS[icon]) {
      var gi = svg("g", { transform: "translate(6,3.2) scale(0.5)", fill: "none", stroke: fg, "stroke-width": 2.2, "stroke-linecap": "round", "stroke-linejoin": "round" });
      gi.innerHTML = ICONS[icon];
      g.appendChild(gi); tx = 19;
    }
    g.appendChild(svgText(tx, 12.5, txt, { anchor: "start", size: 9.5, weight: 700, fill: fg, mono: true, spacing: ".04em" }));
    root.appendChild(g);
  }

  /* --- timeline: spine + arrow, era-graded nodes, detail cards --- */
  function renderTimeline(spec) {
    var nodes = spec.rows.map(function (r) {
      var p = splitPipes(r);
      return { label: p[0] || "", title: p[1] || "", sub: p[2] || "" };
    });
    if (!nodes.length) throw new Error("canvas timeline: no nodes");
    var n = nodes.length, W = 272, PAD = 30;
    var totalW = Math.max(n * W, 540), spineY = 120;
    var totalH = 178;
    var S = makeSvg(totalW, totalH, accentHexOf(spec.dirs.accent || "deep"));
    var root = S.root;
    var cx0 = PAD + W / 2, cxN = totalW - PAD - W / 2;
    // spine
    root.appendChild(svg("line", { x1: PAD, y1: spineY, x2: totalW - PAD + 6, y2: spineY, stroke: "#1A1916", "stroke-width": 1.4, "marker-end": S.arr }));
    nodes.forEach(function (node, i) {
      var aName = ACCENT_LIST[i % 3], hex = accentHexOf(aName);
      var cx = n === 1 ? totalW / 2 : cx0 + (cxN - cx0) * (i / (n - 1));
      var last = i === n - 1;
      // stem
      root.appendChild(svg("line", { x1: cx, y1: spineY, x2: cx, y2: 76, stroke: hex, "stroke-width": 1 }));
      // detail card
      var cardW = Math.min(W - 16, 218), cx0b = cx - cardW / 2;
      var subLines = wrap(stripMd(node.sub).replace(/\s*\([^)]*\)\s*$/, ""), 27, 2);
      var cardH = subLines.length > 1 ? 58 : 48;
      var cardG = svg("g", { filter: S.shadow });
      cardG.appendChild(svg("rect", { x: cx0b, y: 14, width: cardW, height: cardH, rx: 9, fill: ACCENT_SOFT[aName], stroke: ACCENT_SOFTSTROKE[aName] }));
      root.appendChild(cardG);
      root.appendChild(svgText(cx, 33, stripMd(node.title), { size: 12.5, weight: 650, fill: "#1A1916" }));
      subLines.forEach(function (ln, k) {
        root.appendChild(svgText(cx, 48 + k * 12.5, ln, { size: 10.5, fill: "#4A4842" }));
      });
      // node dot (last = larger + halo)
      if (last) root.appendChild(svg("circle", { cx: cx, cy: spineY, r: 13, fill: "none", stroke: hex, "stroke-width": 1, "stroke-opacity": .4 }));
      root.appendChild(svg("circle", { cx: cx, cy: spineY, r: last ? 7.5 : 6.5, fill: last ? hex : "#FBF9F4", stroke: hex, "stroke-width": 2.4 }));
      // year
      root.appendChild(svgText(cx, spineY + 20, stripMd(node.label), { size: 13, weight: 700, fill: hex, mono: true }));
      // method pill from trailing (XXX) in sub
      var pm = /\(([^)]+)\)\s*$/.exec(node.sub);
      if (pm) {
        var ptxt = pm[1], pw = 16 + ptxt.length * 6.4;
        root.appendChild(svg("rect", { x: cx - pw / 2, y: spineY + 30, width: pw, height: 17, rx: 8.5, fill: hex }));
        root.appendChild(svgText(cx, spineY + 42, ptxt, { size: 9.5, weight: 700, fill: "#fff", mono: true }));
      }
    });
    return root;
  }

  /* --- bars: two-series horizontal, rounded caps, value chips --- */
  function renderBars(spec) {
    var series = splitPipes(spec.dirs.axis || "A | B");
    var rows = spec.rows.map(function (r) {
      var p = splitPipes(r);
      return { label: p[0] || "", a: parseFloat(p[1]) || 0, b: parseFloat(p[2]) || 0 };
    });
    if (!rows.length) throw new Error("canvas bars: no rows");
    var aHex = accentHexOf(spec.dirs.accent || "paper"), bHex = "#8A877F";
    var GUTTER = 150, BAR = 330, RIGHT = 46, legendY = 16;
    var W = GUTTER + BAR + RIGHT, rowH = 46, barH = 14, gap = 6;
    var startY = 40, H = startY + rows.length * rowH + 6;
    var S = makeSvg(W, H, aHex); var root = S.root;
    // legend
    root.appendChild(svg("rect", { x: GUTTER, y: legendY - 10, width: 12, height: 12, rx: 3, fill: aHex }));
    root.appendChild(svgText(GUTTER + 18, legendY, series[0] || "A", { anchor: "start", size: 12, weight: 600, fill: "#4A4842" }));
    var off = GUTTER + 18 + (series[0] || "A").length * 7.4 + 24;
    root.appendChild(svg("rect", { x: off, y: legendY - 10, width: 12, height: 12, rx: 3, fill: bHex }));
    root.appendChild(svgText(off + 18, legendY, series[1] || "B", { anchor: "start", size: 12, weight: 600, fill: "#4A4842" }));
    rows.forEach(function (row, i) {
      var top = startY + i * rowH;
      root.appendChild(svgText(GUTTER - 12, top + barH + 2, stripMd(row.label), { anchor: "end", size: 12.5, weight: 500, fill: "#1A1916" }));
      [["a", aHex, top], ["b", bHex, top + barH + gap]].forEach(function (cfg) {
        var val = Math.max(0, Math.min(100, row[cfg[0]])), w = (val / 100) * BAR;
        root.appendChild(svg("rect", { x: GUTTER, y: cfg[2], width: BAR, height: barH, rx: barH / 2, fill: "#EFEAE0" }));
        root.appendChild(svg("rect", { x: GUTTER, y: cfg[2], width: Math.max(barH, w), height: barH, rx: barH / 2, fill: cfg[1] }));
        root.appendChild(svgText(GUTTER + Math.max(barH, w) + 8, cfg[2] + barH - 2.5, String(val), { anchor: "start", size: 11, weight: 600, fill: cfg[1], mono: true }));
      });
    });
    return root;
  }

  /* --- grid: card deck, elevation + accent rail --- */
  function renderGrid(spec) {
    var cols = parseInt(spec.dirs.cols, 10) || 2;
    var hex = accentHexOf(spec.dirs.accent || "paper");
    var g = el("div", "cv-grid"); g.style.setProperty("--cols", cols); g.style.setProperty("--qc", hex);
    spec.rows.forEach(function (r) {
      var m = /^([\s\S]+?)\s*::\s*([\s\S]*)$/.exec(r);
      if (!m) return;
      var card = el("div", "cv-card");
      var t = el("div", "cv-card-title"); t.innerHTML = inlineMd(m[1].trim());
      var b = el("div", "cv-card-body"); b.innerHTML = inlineMd(m[2].trim());
      card.appendChild(t); card.appendChild(b); g.appendChild(card);
    });
    if (!g.childNodes.length) throw new Error("canvas grid: no cards");
    return g;
  }

  /* ---------- small DOM + color helpers ---------- */
  function el(tag, cls) { var e = document.createElement(tag); if (cls) e.className = cls; return e; }

  var RENDERERS = { matrix: renderMatrix, timeline: renderTimeline, flow: renderFlow, bars: renderBars, grid: renderGrid };

  /* ============================ entry ============================ */
  function render(bodyEl) {
    if (!bodyEl || !bodyEl.querySelectorAll) return;
    figureCounter = 0; svgUid = 0;
    var blocks = bodyEl.querySelectorAll("pre > code.language-canvas");
    Array.prototype.forEach.call(blocks, function (code) {
      var pre = code.parentNode;
      try {
        var spec = parseSpec(code.textContent);
        var renderer = RENDERERS[spec.type];
        if (!renderer) throw new Error("canvas: unknown type `" + spec.type + "`");
        var fig = makeFigure(spec.type, spec.dirs);
        fig.appendChild(renderer(spec));
        figureCounter++;
        addCaption(fig, spec.dirs, figureCounter);
        pre.replaceWith(fig);
      } catch (err) {
        pre.setAttribute("data-canvas-error", (err && err.message) || "canvas parse error");
      }
    });
  }

  window.BlogCanvas = { render: render };
})();

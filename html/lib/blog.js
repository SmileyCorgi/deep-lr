/* =========================================================================
   deep-lr — blog runtime (vanilla JS, no framework)

   Two entry points share this file:
     1. /html/index.html  : reads /blog/index.json + /blog/categories.json,
                            renders filter chips, year-grouped rows, sort.
     2. /html/post.html   : reads ?slug=... , fetches the markdown body,
                            renders the article + "more in this category" footer.

   Page is detected by presence of #post-list (index) vs #post-frame (post).
   ========================================================================= */

(function () {
  "use strict";

  const INDEX_URL = "/blog/index.json";
  const CATS_URL = "/blog/categories.json";
  const POSTS_BASE = "/blog/posts/";

  // ---- shared helpers -----------------------------------------------------

  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function fetchJSON(url) {
    return fetch(url, { cache: "no-cache" }).then(function (r) {
      if (!r.ok) throw new Error(url + " " + r.status);
      return r.json();
    });
  }

  function fetchText(url) {
    return fetch(url, { cache: "no-cache" }).then(function (r) {
      if (!r.ok) throw new Error(url + " " + r.status);
      return r.text();
    });
  }

  // Compact tag display: first 2 tags + "+N" suffix.
  function tagDisplay(tags) {
    if (!tags || !tags.length) return "";
    const head = tags.slice(0, 2).join(" · ");
    const extra = tags.length > 2 ? " +" + (tags.length - 2) : "";
    return head + extra;
  }

  // Build a row anchor element (same shape as PM-B mockup).
  function buildRow(post) {
    const a = document.createElement("a");
    a.className = "row";
    a.href = "/html/post.html?slug=" + encodeURIComponent(post.slug);
    a.setAttribute("data-cat", post.category);

    const tagStr = tagDisplay(post.tags);
    const dekHtml = post.dek
      ? '<p class="dek">' + escapeHtml(post.dek) + "</p>"
      : "";
    const tagHtml = tagStr
      ? '<span class="sep">·</span><span>' + escapeHtml(tagStr) + "</span>"
      : "";
    const rtHtml = (post.reading_time != null)
      ? '<span>' + Number(post.reading_time) + " min</span>"
      : "";

    a.innerHTML =
      '<div class="date">' + escapeHtml(post.date) + "</div>" +
      '<div class="body">' +
        '<div class="title-line">' +
          '<span class="title">' + escapeHtml(post.title) + "</span>" +
          '<span class="badge" data-cat="' + escapeHtml(post.category) + '">' +
            '<span class="dot-cat"></span>' + escapeHtml(post.category) +
          "</span>" +
        "</div>" +
        dekHtml +
        '<div class="meta">' + rtHtml + tagHtml + "</div>" +
      "</div>";
    return a;
  }

  // ---- INDEX PAGE ---------------------------------------------------------

  function initIndex() {
    const listEl = document.getElementById("post-list");
    const chipsEl = document.getElementById("chips");
    const sortEl = document.getElementById("sort");
    const footerCountEl = document.getElementById("footer-count");
    const footerUpdatedEl = document.getElementById("footer-updated");

    const state = { cat: "all", sort: "desc" };
    let posts = [];
    let categories = {}; // slug -> { label, accent, blurb }

    function categoryCount(catSlug) {
      if (catSlug === "all") return posts.length;
      let n = 0;
      for (let i = 0; i < posts.length; i++) if (posts[i].category === catSlug) n++;
      return n;
    }

    function renderChips() {
      const parts = [];
      parts.push(
        '<button class="chip ' + (state.cat === "all" ? "is-active" : "") +
        '" data-cat="all" type="button">all <span class="count">' +
        categoryCount("all") + "</span></button>"
      );
      const slugs = Object.keys(categories);
      for (let i = 0; i < slugs.length; i++) {
        const slug = slugs[i];
        const label = categories[slug].label || slug;
        parts.push(
          '<button class="chip ' + (state.cat === slug ? "is-active" : "") +
          '" data-cat="' + escapeHtml(slug) + '" type="button">' +
            '<span class="dot"></span>' + escapeHtml(label) +
            ' <span class="count">' + categoryCount(slug) + "</span>" +
          "</button>"
        );
      }
      chipsEl.innerHTML = parts.join("");
      chipsEl.querySelectorAll(".chip").forEach(function (btn) {
        btn.addEventListener("click", function () {
          state.cat = btn.dataset.cat;
          renderChips();
          renderList();
        });
      });
    }

    function renderList() {
      const filtered = posts.filter(function (p) {
        return state.cat === "all" || p.category === state.cat;
      });
      filtered.sort(function (a, b) {
        return state.sort === "desc"
          ? String(b.date).localeCompare(String(a.date))
          : String(a.date).localeCompare(String(b.date));
      });

      listEl.innerHTML = "";

      if (filtered.length === 0) {
        const e = document.createElement("div");
        e.className = "empty";
        if (posts.length === 0) {
          e.textContent = "no posts yet — the first one will land here.";
        } else {
          e.textContent = "no posts in this category yet.";
        }
        listEl.appendChild(e);
        footerCountEl.textContent = "0";
        return;
      }

      // Group by year, preserving sort order.
      const groups = [];
      const seen = {};
      for (let i = 0; i < filtered.length; i++) {
        const p = filtered[i];
        const y = String(p.date).slice(0, 4);
        if (!seen[y]) {
          seen[y] = { year: y, posts: [] };
          groups.push(seen[y]);
        }
        seen[y].posts.push(p);
      }

      for (let g = 0; g < groups.length; g++) {
        const group = groups[g];
        const div = document.createElement("div");
        div.className = "year-divider";
        div.innerHTML =
          '<span class="year">' + escapeHtml(group.year) + "</span>" +
          '<span class="leader"></span>' +
          '<span class="count">' + group.posts.length +
          " post" + (group.posts.length === 1 ? "" : "s") + "</span>";
        listEl.appendChild(div);
        for (let i = 0; i < group.posts.length; i++) {
          listEl.appendChild(buildRow(group.posts[i]));
        }
      }
      footerCountEl.textContent = String(filtered.length);
    }

    // Wire sort buttons (already in DOM).
    sortEl.querySelectorAll("button").forEach(function (btn) {
      btn.addEventListener("click", function () {
        sortEl.querySelectorAll("button").forEach(function (b) {
          b.classList.remove("is-active");
        });
        btn.classList.add("is-active");
        state.sort = btn.dataset.sort;
        renderList();
      });
    });

    // Load data and render.
    Promise.all([
      fetchJSON(CATS_URL).catch(function () { return {}; }),
      fetchJSON(INDEX_URL).catch(function () { return { posts: [] }; })
    ]).then(function (results) {
      categories = results[0] || {};
      const idx = results[1] || {};
      posts = Array.isArray(idx.posts) ? idx.posts : [];
      if (idx.generated && footerUpdatedEl) {
        const d = String(idx.generated).slice(0, 10);
        footerUpdatedEl.textContent = " · last updated " + d;
      }
      renderChips();
      renderList();
    }).catch(function (err) {
      listEl.innerHTML = '<div class="empty">failed to load index: ' +
        escapeHtml(err.message) + "</div>";
    });
  }

  // ---- POST PAGE ----------------------------------------------------------

  function getQueryParam(name) {
    const m = window.location.search.match(
      new RegExp("[?&]" + name + "=([^&]*)")
    );
    return m ? decodeURIComponent(m[1].replace(/\+/g, " ")) : "";
  }

  function initPost() {
    const frame = document.getElementById("post-frame");
    const status = document.getElementById("post-status");
    const moreSection = document.getElementById("more-in-cat");
    const moreLabel = document.getElementById("more-label");
    const moreList = document.getElementById("more-list");

    const slug = getQueryParam("slug");
    if (!slug) {
      status.textContent = "no post slug given. ← back to the catalog.";
      return;
    }

    document.title = "deep-lr — " + slug;

    // Fetch index first so we have metadata, dek, category siblings.
    fetchJSON(INDEX_URL).then(function (idx) {
      const all = (idx && Array.isArray(idx.posts)) ? idx.posts : [];
      const post = all.find(function (p) { return p.slug === slug; });
      if (!post) {
        renderPostNotFound(slug);
        return;
      }
      document.title = "deep-lr — " + post.title;
      return fetchText(POSTS_BASE + slug + ".md").then(function (md) {
        renderPost(post, md);
        renderSiblings(post, all);
      }).catch(function () {
        renderPost(post, "*Post body not found at `" +
          POSTS_BASE + slug + ".md`.*");
        renderSiblings(post, all);
      });
    }).catch(function () {
      // No index — try the markdown directly as a last resort.
      fetchText(POSTS_BASE + slug + ".md").then(function (md) {
        renderPost({
          slug: slug,
          title: slug,
          date: "",
          category: "",
          dek: "",
          reading_time: null,
          tags: []
        }, md);
      }).catch(function () { renderPostNotFound(slug); });
    });

    function renderPostNotFound(s) {
      status.innerHTML =
        "post <code>" + escapeHtml(s) + "</code> not found. " +
        '<br><br><a href="/html/index.html">&larr; back to all posts</a>';
    }

    function stripFrontmatter(md) {
      // If the markdown still has YAML frontmatter, strip it for rendering.
      if (md.slice(0, 4) === "---\n" || md.slice(0, 4) === "---\r") {
        const end = md.indexOf("\n---", 3);
        if (end !== -1) {
          let rest = md.slice(end + 4);
          // Drop the trailing newline after the closing ---
          if (rest.charAt(0) === "\n" || rest.charAt(0) === "\r") rest = rest.replace(/^\r?\n/, "");
          return rest;
        }
      }
      return md;
    }

    // -----------------------------------------------------------------
    // PM-C "Readable" post renderer.
    //
    // Pipeline (after marked.js produces the body HTML):
    //   1. Render header (meta row, title, dek, byline) into .post-header.
    //   2. Lift the first <h2> matching the focus-heading regex (and all
    //      siblings up to the next <h2>) into the .focus-block container,
    //      reformatted as a bulleted list with a label.
    //   3. Walk remaining <h2>s; build inline-TOC and side-TOC entries.
    //      Strip leading "N. " numbering from displayed labels.
    //   4. Walk all <a class="wiki-cite">; replace with numbered
    //      <sup class="cite-ref"> links and emit a de-duplicated
    //      references list in .references.
    //   5. Wire up Intersection Observers:
    //      a. Active-section highlight on body H2s (and #references-heading)
    //         with rootMargin '-30% 0px -60% 0px'.
    //      b. Side-TOC scroll-coupled visibility, observing the inline TOC.
    //         While inline TOC intersects viewport → side-TOC hidden;
    //         while inline TOC is offscreen → side-TOC visible.
    //   6. Smooth-scroll on every in-page anchor click (covers TOC + cite).
    // -----------------------------------------------------------------

    // Headings whose text matches this lift into the focus block.
    const FOCUS_HEADING_RE = /^(key findings|the gist|tldr|tl;dr|bottom line up front)\s*:?\s*$/i;
    const DEFAULT_FOCUS_LABEL = "THE GIST";

    function slugify(text) {
      return String(text || "")
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "");
    }

    // Strip leading "N. " / "N: " from a section title (for TOC display).
    function stripSectionNumber(text) {
      return String(text || "").replace(/^\s*\d+\s*[.:)\-]\s*/, "");
    }

    function renderPost(post, rawMd) {
      const md = stripFrontmatter(rawMd || "");

      // Hide the loading status, reveal the shell skeleton.
      if (status) status.hidden = true;
      const shell = document.getElementById("post-shell");
      if (shell) shell.hidden = false;

      renderPostHeader(post);

      const bodyEl = document.getElementById("post-body");
      if (bodyEl) bodyEl.innerHTML = '<p class="post-body-loading">rendering…</p>';

      const renderer = (window.BlogMarkdown && window.BlogMarkdown.renderAsync)
        ? window.BlogMarkdown.renderAsync(md)
        : Promise.resolve("<pre>" + escapeHtml(md) + "</pre>");

      renderer.then(function (html) {
        if (!bodyEl) return;
        bodyEl.innerHTML = html;

        // Stage 0: swap ```canvas blocks for themed figures BEFORE the H2/TOC/
        // citation walks (figures carry no <h2>/a.wiki-cite, so those stages
        // skip them). See html/lib/canvas.js + blog/README "Canvas blocks".
        if (window.BlogCanvas) window.BlogCanvas.render(bodyEl);

        // Post-process the rendered DOM in order.
        const focusLabel = (post.focus_label || DEFAULT_FOCUS_LABEL).toString();
        liftFocusBlock(bodyEl, focusLabel);
        const sections = collectSections(bodyEl);
        buildInlineToc(sections);
        buildSideToc(sections);
        processCitations(bodyEl);
        wireSmoothScroll();
        wireScrollSpy(sections);
        wireSideTocVisibility();
      });
    }

    function renderPostHeader(post) {
      const headerEl = document.getElementById("post-header");
      if (!headerEl) return;
      const rt = (post.reading_time != null)
        ? post.reading_time + " min read"
        : "";
      const dateHtml = post.date
        ? '<span>' + escapeHtml(post.date) + "</span>"
        : "";
      const catHtml = post.category
        ? '<span class="cat-badge" data-cat="' + escapeHtml(post.category) +
          '">' + escapeHtml(post.category) + "</span>"
        : "";
      const rtHtml = rt ? '<span>' + escapeHtml(rt) + "</span>" : "";
      const dekHtml = post.dek
        ? '<p class="post-dek">' + escapeHtml(post.dek) + "</p>"
        : "";
      const tagStr = (post.tags && post.tags.length)
        ? "tags: " + post.tags.join(", ")
        : "";
      // Site author byline — set your name here when adopting the framework.
      const SITE_AUTHOR = "deep-lr";
      const bylineHtml =
        '<p class="post-byline">' + escapeHtml(SITE_AUTHOR) +
        (tagStr ? " · " + escapeHtml(tagStr) : "") +
        "</p>";

      headerEl.innerHTML =
        '<div class="post-meta-row">' + dateHtml + catHtml + rtHtml + "</div>" +
        '<h1 class="post-h1">' + escapeHtml(post.title) + "</h1>" +
        dekHtml +
        bylineHtml;
    }

    // Walk the rendered body. If the first <h2> matches FOCUS_HEADING_RE,
    // move it and the siblings up to the next <h2> into the focus-block.
    // The H2 itself is dropped; its children are reformatted as <ul><li>…</li></ul>.
    function liftFocusBlock(bodyEl, focusLabel) {
      const focusEl = document.getElementById("focus-block");
      if (!focusEl) return;

      const firstH2 = bodyEl.querySelector("h2");
      if (!firstH2) return;
      const headingText = (firstH2.textContent || "").trim();
      if (!FOCUS_HEADING_RE.test(headingText)) return;

      // Collect siblings between firstH2 (inclusive of its content) and the
      // next H2 (exclusive). We drop the H2 itself — the focus block has
      // its own label.
      const content = [];
      let node = firstH2.nextSibling;
      while (node && !(node.nodeType === 1 && node.tagName === "H2")) {
        const next = node.nextSibling;
        content.push(node);
        node = next;
      }
      firstH2.parentNode.removeChild(firstH2);

      // Try to find a UL/OL inside the lifted content; otherwise wrap each
      // non-empty paragraph into a list item.
      let listSource = null;
      for (let i = 0; i < content.length; i++) {
        if (content[i].nodeType === 1 &&
            (content[i].tagName === "UL" || content[i].tagName === "OL")) {
          listSource = content[i];
          break;
        }
      }

      const ul = document.createElement("ul");
      if (listSource) {
        const items = listSource.querySelectorAll(":scope > li");
        items.forEach(function (li) {
          const newLi = document.createElement("li");
          newLi.innerHTML = li.innerHTML;
          ul.appendChild(newLi);
        });
      } else {
        for (let i = 0; i < content.length; i++) {
          const n = content[i];
          if (n.nodeType === 1 && n.tagName === "P" && n.textContent.trim()) {
            const li = document.createElement("li");
            li.innerHTML = n.innerHTML;
            ul.appendChild(li);
          }
        }
      }

      // Remove the lifted nodes from the body.
      for (let i = 0; i < content.length; i++) {
        const n = content[i];
        if (n.parentNode) n.parentNode.removeChild(n);
      }

      focusEl.innerHTML =
        '<p class="focus-label">' + escapeHtml(focusLabel) + "</p>" +
        '<hr class="focus-divider" />';
      focusEl.appendChild(ul);
      focusEl.hidden = false;
    }

    // Assign stable IDs to body H2s and return [{id, displayText, el}, …].
    function collectSections(bodyEl) {
      const h2s = bodyEl.querySelectorAll("h2");
      const result = [];
      const used = {};
      h2s.forEach(function (h2) {
        const rawText = (h2.textContent || "").trim();
        const display = stripSectionNumber(rawText);
        let id = h2.id;
        if (!id) {
          // Prefer the raw (numbered) text for slug uniqueness.
          let base = slugify(rawText) || "section";
          id = base;
          let n = 2;
          while (used[id] || document.getElementById(id)) {
            id = base + "-" + n;
            n++;
          }
          h2.id = id;
        }
        used[id] = true;
        // Use the stripped display text in the heading too — keeps body
        // visually clean (PM-C §6 strips "N." from TOC; body keeps N.).
        // Per spec we KEEP the number in the body, so leave h2 textContent alone.
        result.push({ id: id, display: display, el: h2 });
      });
      return result;
    }

    function buildInlineToc(sections) {
      const toc = document.getElementById("inline-toc");
      if (!toc) return;
      if (!sections.length) {
        toc.hidden = true;
        return;
      }
      const items = sections.map(function (s, i) {
        return '<li><a href="#' + s.id + '">' +
          '<span class="num">' + (i + 1) + "</span>" +
          '<span class="label">' + escapeHtml(s.display) + "</span>" +
          "</a></li>";
      }).join("");
      toc.innerHTML =
        '<button class="inline-toc-toggle" type="button" id="inline-toc-toggle">' +
          '<span>On this page (' + sections.length + ")</span>" +
          '<span class="chev">▾</span>' +
        "</button>" +
        '<p class="inline-toc-head">ON THIS PAGE</p>' +
        '<ol>' + items + '</ol>';
      toc.hidden = false;

      // Mobile collapse default.
      function applyInlineTocCollapse() {
        if (window.matchMedia("(max-width: 640px)").matches) {
          toc.setAttribute("data-open", "false");
        } else {
          toc.setAttribute("data-open", "true");
        }
      }
      applyInlineTocCollapse();
      window.addEventListener("resize", applyInlineTocCollapse);
      const toggle = document.getElementById("inline-toc-toggle");
      if (toggle) {
        toggle.addEventListener("click", function () {
          toc.setAttribute(
            "data-open",
            toc.getAttribute("data-open") === "true" ? "false" : "true"
          );
        });
      }
    }

    function buildSideToc(sections) {
      const side = document.getElementById("side-toc");
      if (!side) return;
      if (!sections.length) {
        side.hidden = true;
        return;
      }
      const items = sections.map(function (s, i) {
        return '<li><a href="#' + s.id + '" data-target="' + s.id + '">' +
          '<span class="num">' + (i + 1) + "</span>" +
          '<span class="label">' + escapeHtml(s.display) + "</span>" +
          "</a></li>";
      });
      // R. References row — references section is only added later if
      // the post has any citations; we always render the row but it links
      // to #references-heading which exists when references are visible.
      items.push(
        '<li><a href="#references-heading" data-target="references-heading">' +
          '<span class="num">R</span>' +
          '<span class="label">References</span>' +
        "</a></li>"
      );
      side.innerHTML =
        '<p class="side-label">ON THIS PAGE</p>' +
        '<ol>' + items.join("") + '</ol>';
    }

    // Replace every <a class="wiki-cite"> with a numbered <sup class="cite-ref">
    // and populate the references list. Returns count of unique slugs.
    function processCitations(bodyEl) {
      const cites = bodyEl.querySelectorAll("a.wiki-cite");
      if (!cites.length) {
        // Hide references entirely if no citations.
        const refsSection = document.getElementById("references");
        if (refsSection) refsSection.hidden = true;
        return 0;
      }

      const seen = {};       // slug -> number
      const order = [];      // slugs in first-occurrence order
      const occCount = {};   // slug -> int

      cites.forEach(function (a) {
        // The href is /wiki/entities/<slug>.md — derive slug.
        const href = a.getAttribute("href") || "";
        let slug = "";
        const m = href.match(/\/wiki\/entities\/([^/]+?)\.md$/);
        if (m) {
          slug = m[1];
        } else {
          // Fall back to link text as the slug identifier.
          slug = slugify(a.textContent || "");
        }
        if (!seen[slug]) {
          seen[slug] = order.length + 1;
          order.push(slug);
          occCount[slug] = 0;
        }
        occCount[slug] += 1;
        const n = seen[slug];
        const occId = "cite-" + n + "-" + occCount[slug];

        const sup = document.createElement("sup");
        sup.className = "cite-ref";
        sup.id = occId;
        const link = document.createElement("a");
        link.href = "#ref-" + n;
        link.setAttribute("aria-label", "reference " + n);
        link.textContent = "[" + n + "]";
        sup.appendChild(link);
        a.parentNode.replaceChild(sup, a);
      });

      const refsSection = document.getElementById("references");
      const list = document.getElementById("refs-list");
      if (!refsSection || !list) return order.length;
      list.innerHTML = "";
      order.forEach(function (slug, i) {
        const n = i + 1;
        const li = document.createElement("li");
        li.id = "ref-" + n;
        li.className = "ref-item";
        // Slug-only placeholder; enhanceReferences swaps in title+arxiv async.
        li.innerHTML =
          '<span class="ref-num">[' + n + "]</span>" +
          '<div class="ref-body">' +
            '<span class="ref-slug-fallback">' + escapeHtml(slug) + "</span>" +
          "</div>" +
          '<a class="ref-back" href="#cite-' + n + '-1" ' +
            'title="back to first citation" aria-label="back to citation ' + n +
            '">↑</a>';
        list.appendChild(li);
      });
      refsSection.hidden = false;
      enhanceReferences(order);
      return order.length;
    }

    // ---------------------------------------------------------------
    // References enhancement: for each cited slug, fetch the wiki entity
    // markdown, extract title + authors + venue + arxiv/openreview/pdf
    // links + TL;DR, and replace the slug fallback with a richer row that
    // opens an abstract popup on click.
    // ---------------------------------------------------------------

    const _entityCache = {};

    function parseEntityMeta(md) {
      let body = md || "";
      if (body.slice(0, 4) === "---\n" || body.slice(0, 4) === "---\r") {
        const end = body.indexOf("\n---", 3);
        if (end !== -1) body = body.slice(end + 4).replace(/^\r?\n/, "");
      }
      const meta = { title: "", authors: "", venue: "", track: "",
                     arxiv: "", openreview: "", pdf: "", tldr: "" };

      const titleM = body.match(/^#\s+(.+?)\s*$/m);
      if (titleM) meta.title = titleM[1].trim();

      const authM = body.match(/\*\*Authors?:\*\*\s*([^\n]+)/);
      if (authM) {
        // Trim to first 3 surnames + et al. for compactness.
        const raw = authM[1].trim().replace(/\s+/g, " ");
        const parts = raw.split(/;|,(?=\s*[A-Z])/).map(function (s) {
          return s.trim();
        }).filter(Boolean);
        const surnames = parts.map(function (p) {
          // "Zou, Deyu" → "Zou"; "Deyu Zou" → "Zou"
          if (p.indexOf(",") !== -1) return p.split(",")[0].trim();
          const tokens = p.split(/\s+/);
          return tokens[tokens.length - 1];
        });
        meta.authors = surnames.length <= 3
          ? surnames.join(", ")
          : surnames.slice(0, 3).join(", ") + " et al.";
      }

      const venueM = body.match(/\*\*Venue:\*\*\s*([^\n·]+)/);
      if (venueM) meta.venue = venueM[1].trim();

      const arxivM = body.match(/https?:\/\/arxiv\.org\/(?:abs|pdf)\/[^\s)>\]]+/);
      if (arxivM) meta.arxiv = arxivM[0].replace(/\.pdf$/, "");

      const orM = body.match(/https?:\/\/openreview\.net\/forum\?[^\s)>\]]+/);
      if (orM) meta.openreview = orM[0];

      const pdfM = body.match(/\[pdf\]\((https?:\/\/[^)]+)\)/i);
      if (pdfM) meta.pdf = pdfM[1];

      const tldrM = body.match(/##\s+TL;?DR\s*\n([\s\S]*?)(?=\n##\s|$)/i);
      if (tldrM) meta.tldr = tldrM[1].trim();

      return meta;
    }

    function fetchEntity(slug) {
      if (_entityCache[slug]) return Promise.resolve(_entityCache[slug]);
      return fetchText("/wiki/entities/" + slug + ".md")
        .then(function (md) {
          const meta = parseEntityMeta(md);
          _entityCache[slug] = meta;
          return meta;
        }).catch(function () {
          _entityCache[slug] = null;
          return null;
        });
    }

    function renderRefLinks(meta) {
      const out = [];
      if (meta.arxiv) {
        out.push('<a class="ref-link" href="' + escapeHtml(meta.arxiv) +
          '" target="_blank" rel="noopener">arxiv</a>');
      }
      if (meta.openreview) {
        out.push('<a class="ref-link" href="' + escapeHtml(meta.openreview) +
          '" target="_blank" rel="noopener">openreview</a>');
      }
      if (meta.pdf && !meta.arxiv && !meta.openreview) {
        out.push('<a class="ref-link" href="' + escapeHtml(meta.pdf) +
          '" target="_blank" rel="noopener">pdf</a>');
      }
      return out.join("");
    }

    function enhanceReferences(order) {
      order.forEach(function (slug, i) {
        const n = i + 1;
        const li = document.getElementById("ref-" + n);
        if (!li) return;
        fetchEntity(slug).then(function (meta) {
          if (!meta || !meta.title) return; // leave slug fallback
          const bodyEl = li.querySelector(".ref-body");
          if (!bodyEl) return;
          const venuePart = meta.venue
            ? '<span>' + escapeHtml(meta.venue) + "</span>"
            : "";
          const authorPart = meta.authors
            ? '<span>' + escapeHtml(meta.authors) + "</span>"
            : "";
          const metaJoiner = (authorPart && venuePart)
            ? '<span class="sep">·</span>' : "";
          const linksHtml = renderRefLinks(meta);
          bodyEl.innerHTML =
            '<button type="button" class="ref-title" data-ref-slug="' +
              escapeHtml(slug) + '">' + escapeHtml(meta.title) + "</button>" +
            (linksHtml ? '<span class="ref-links">' + linksHtml + "</span>" : "") +
            ((authorPart || venuePart)
              ? '<span class="ref-meta">' +
                  authorPart + metaJoiner + venuePart +
                "</span>"
              : "");
          const btn = bodyEl.querySelector(".ref-title");
          if (btn) {
            btn.addEventListener("click", function () {
              openRefModal(slug, meta);
            });
          }
        });
      });
    }

    // ---------------------------------------------------------------
    // Reference popup modal — single shared element, populated per click.
    // ESC + overlay click + close-button close it.
    // ---------------------------------------------------------------

    let _refModalEl = null;
    function ensureRefModal() {
      if (_refModalEl) return _refModalEl;
      const overlay = document.createElement("div");
      overlay.className = "ref-modal-overlay";
      overlay.setAttribute("data-open", "false");
      overlay.setAttribute("role", "presentation");
      overlay.innerHTML =
        '<div class="ref-modal" role="dialog" aria-modal="true" aria-labelledby="rm-title">' +
          '<button type="button" class="ref-modal-close" aria-label="close">×</button>' +
          '<p class="rm-eyebrow" id="rm-eyebrow">Reference</p>' +
          '<h3 class="rm-title" id="rm-title"></h3>' +
          '<p class="rm-meta" id="rm-meta"></p>' +
          '<p class="rm-tldr-label">TL;DR</p>' +
          '<div class="rm-tldr" id="rm-tldr"></div>' +
          '<div class="rm-links" id="rm-links"></div>' +
        "</div>";
      document.body.appendChild(overlay);
      overlay.addEventListener("click", function (e) {
        if (e.target === overlay) closeRefModal();
      });
      overlay.querySelector(".ref-modal-close").addEventListener("click", closeRefModal);
      document.addEventListener("keydown", function (e) {
        if (e.key === "Escape" && overlay.getAttribute("data-open") === "true") {
          closeRefModal();
        }
      });
      _refModalEl = overlay;
      return overlay;
    }

    function openRefModal(slug, meta) {
      const overlay = ensureRefModal();
      overlay.querySelector("#rm-eyebrow").textContent =
        meta.venue ? meta.venue : "Reference";
      overlay.querySelector("#rm-title").textContent = meta.title || slug;
      const metaBits = [];
      if (meta.authors) metaBits.push(meta.authors);
      if (meta.venue) metaBits.push(meta.venue);
      overlay.querySelector("#rm-meta").textContent = metaBits.join(" · ");
      const tldrEl = overlay.querySelector("#rm-tldr");
      if (meta.tldr) {
        // Lightweight inline-markdown for the TL;DR: bold + code only.
        let safe = escapeHtml(meta.tldr);
        safe = safe.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
        safe = safe.replace(/`([^`]+)`/g, "<code>$1</code>");
        tldrEl.innerHTML = safe;
      } else {
        tldrEl.innerHTML = '<em style="color:var(--muted)">No TL;DR available in the wiki entity.</em>';
      }
      const linksEl = overlay.querySelector("#rm-links");
      linksEl.innerHTML = "";
      if (meta.arxiv) {
        linksEl.insertAdjacentHTML("beforeend",
          '<a class="rm-link" target="_blank" rel="noopener" href="' +
            escapeHtml(meta.arxiv) + '">arxiv ↗</a>');
      }
      if (meta.openreview) {
        linksEl.insertAdjacentHTML("beforeend",
          '<a class="rm-link" target="_blank" rel="noopener" href="' +
            escapeHtml(meta.openreview) + '">openreview ↗</a>');
      }
      if (meta.pdf) {
        linksEl.insertAdjacentHTML("beforeend",
          '<a class="rm-link" target="_blank" rel="noopener" href="' +
            escapeHtml(meta.pdf) + '">pdf ↗</a>');
      }
      linksEl.insertAdjacentHTML("beforeend",
        '<a class="rm-link" target="_blank" rel="noopener" href="/wiki/entities/' +
          escapeHtml(slug) + '.md">wiki entry ↗</a>');
      overlay.setAttribute("data-open", "true");
      document.body.style.overflow = "hidden";
    }

    function closeRefModal() {
      if (!_refModalEl) return;
      _refModalEl.setAttribute("data-open", "false");
      document.body.style.overflow = "";
    }

    // Active-section highlight: most-recently-intersected H2 wins.
    function wireScrollSpy(sections) {
      if (!sections.length || !("IntersectionObserver" in window)) return;

      const sideToc = document.getElementById("side-toc");
      const inlineToc = document.getElementById("inline-toc");

      const refsHeading = document.getElementById("references-heading");
      const targets = sections.slice();
      if (refsHeading) {
        targets.push({ id: "references-heading", el: refsHeading });
      }

      function setActive(id) {
        if (sideToc) {
          sideToc.querySelectorAll("a.active").forEach(function (a) {
            a.classList.remove("active");
          });
          const a = sideToc.querySelector('a[data-target="' + id + '"]');
          if (a) a.classList.add("active");
        }
        if (inlineToc) {
          inlineToc.querySelectorAll("a.active").forEach(function (a) {
            a.classList.remove("active");
          });
          const a = inlineToc.querySelector('a[href="#' + id + '"]');
          if (a) a.classList.add("active");
        }
      }

      const visible = {};
      const observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          const id = entry.target.id;
          if (entry.isIntersecting) {
            visible[id] = entry.intersectionRatio;
          } else {
            delete visible[id];
          }
        });
        // Pick the visible target whose top is highest on screen (most recent).
        let bestId = null;
        let bestTop = Infinity;
        targets.forEach(function (s) {
          if (visible[s.id] !== undefined) {
            const top = s.el.getBoundingClientRect().top;
            if (top < bestTop && top > -50) {
              bestTop = top;
              bestId = s.id;
            }
          }
        });
        if (!bestId) {
          // Fall back: last target whose top is above the viewport.
          const passed = targets.filter(function (s) {
            return s.el.getBoundingClientRect().top < 120;
          });
          if (passed.length) bestId = passed[passed.length - 1].id;
        }
        if (bestId) setActive(bestId);
      }, {
        rootMargin: "-30% 0px -60% 0px",
        threshold: [0, 0.25, 0.5, 1]
      });
      targets.forEach(function (s) { observer.observe(s.el); });
      setActive(targets[0].id);
    }

    // The user's explicit refinement: side-TOC is hidden while the inline
    // TOC is in the viewport; fades+slides in once the inline TOC scrolls
    // off; fades+slides out when the inline TOC re-enters. One observer,
    // CSS handles the transition.
    function wireSideTocVisibility() {
      const inline = document.getElementById("inline-toc");
      const side = document.getElementById("side-toc");
      if (!inline || !side || !("IntersectionObserver" in window)) return;

      // Default state: hidden (CSS sets opacity 0 via data-hidden="true").
      side.setAttribute("data-hidden", "true");
      side.setAttribute("aria-hidden", "true");

      const obs = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          // intersectionRatio > 0 means at least partly in viewport.
          const inlineVisible = entry.isIntersecting && entry.intersectionRatio > 0;
          if (inlineVisible) {
            side.setAttribute("data-hidden", "true");
            side.setAttribute("aria-hidden", "true");
          } else {
            side.setAttribute("data-hidden", "false");
            side.setAttribute("aria-hidden", "false");
          }
        });
      }, { threshold: 0 });
      obs.observe(inline);
    }

    function wireSmoothScroll() {
      document.addEventListener("click", function (e) {
        const a = e.target.closest && e.target.closest('a[href^="#"]');
        if (!a) return;
        const href = a.getAttribute("href");
        if (!href || href === "#") return;
        const id = href.slice(1);
        const target = document.getElementById(id);
        if (!target) return;
        e.preventDefault();
        target.scrollIntoView({ behavior: "smooth", block: "start" });
        // Update the URL hash without jumping (already handled by scrollIntoView).
        if (history && history.pushState) {
          history.pushState(null, "", "#" + id);
        }
      });
    }

    function renderSiblings(post, all) {
      if (!post.category) return;
      const siblings = all.filter(function (p) {
        return p.category === post.category && p.slug !== post.slug;
      }).sort(function (a, b) {
        return String(b.date).localeCompare(String(a.date));
      }).slice(0, 3);
      if (siblings.length === 0) return;
      moreLabel.textContent = "more in " + post.category;
      moreList.innerHTML = "";
      for (let i = 0; i < siblings.length; i++) {
        moreList.appendChild(buildRow(siblings[i]));
      }
      moreSection.hidden = false;
    }
  }

  // ---- bootstrap ----------------------------------------------------------

  function boot() {
    if (document.getElementById("post-list")) {
      initIndex();
    } else if (document.getElementById("post-frame")) {
      initPost();
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();

> **Bootstrap protocol.** On the first session in a fresh copy of this repo,
> the LLM must interview the user and fill in this section, then delete this
> blockquote. Ask: (1) discipline & research mission, (2) 5–10 seed topics,
> (3) primary source venues/databases (conferences? journals? arXiv? PubMed?),
> (4) owner name + contact email (also set `CONTACT_EMAIL` in
> `scripts/harvest/download.py` or export `DEEPLR_CONTACT_EMAIL`), (5) site
> title if the blog/portal will be used (default "deep-lr"). Then: create
> `wiki/topics/<topic>.md` stubs for the seed topics, link them from
> `index.md`, and append a `log.md` bootstrap entry.
>
> **Direction still undecided?** Don't force answers. Run the `good-question`
> skill first; a one-sentence mission and 1–2 *tentative* topics are a valid
> bootstrap — topics are cheap to add, rename, and delete later. The minimal
> first day is: bootstrap thin → ingest the 2–3 papers you already have
> (§3 Ingest, one at a time) → look at the portal. Everything else (corpus
> harvest, deep dives) earns its complexity only after that works.

- **Discipline / mission**: _(unset)_
- **Owner**: _(unset)_
- **Bootstrapped**: _(unset)_
- **Seed topics**: _(unset — tracked as pages under `wiki/topics/`; each topic
  page is the entry point to its sub-literature, entities, and open questions)_

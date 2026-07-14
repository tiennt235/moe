---
title: "Sourcing rules"
origin: "experts/expert-builder/materials/sourcing.md"
format: markdown
source_id: cbc77422fbfa5843
sections: 4
---

# Sourcing rules
## Sourcing rules (auto-research mode)

When the user gives only a topic, you find the sources. The knowledge you generate is
committed to the repo and served as an expert's authoritative corpus, so the bar is high.

## Sourcing rules (auto-research mode) › What to prefer

- **Authoritative & widely used**: canonical textbooks, official documentation, standards
  bodies, primary sources, peer-reviewed overviews, or the recognized reference on the topic.
- **Openly licensed & freely available**: public domain (e.g. Project Gutenberg, Wikisource),
  Creative Commons, official docs you may mirror, or government/standards publications.
- **Stable URLs**: prefer permalinks and canonical document URLs over blog reposts or pages
  that change. For public-domain books, prefer the **EPUB** edition from Project Gutenberg
  (e.g. `.../cache/epub/<id>/pg<id>.epub`) over the `.txt`: the extractor sections EPUBs by
  chapter, so citations get real anchors (see the formats reference). Only use `.txt` when no
  structured edition exists.

## Sourcing rules (auto-research mode) › What to avoid

- Anything whose license forbids redistribution (most commercial books, paywalled articles,
  "all rights reserved" pages). If you cannot confirm the license permits mirroring, do not
  ingest it — ask the user.
- Low-quality, SEO, or AI-generated summaries; forum threads; unstable or mirror URLs.
- Redundant sources that cover the same ground — deduplicate to a tight, high-signal set.

## Sourcing rules (auto-research mode) › The propose-then-confirm loop

1. Search and assemble a shortlist of **3–8** sources.
2. For each, state: the title/author, the URL, **why it is authoritative**, and its
   **license / why it is freely usable**.
3. Present the shortlist and **wait for the user to approve** (they may cut or add). Build only
   from approved sources.
4. If a source turns out to be unusable at build time (fetch fails, extracts empty, wrong
   license), report it and continue with the rest rather than silently dropping it.

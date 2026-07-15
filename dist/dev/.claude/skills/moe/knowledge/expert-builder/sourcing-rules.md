---
title: "Sourcing rules"
origin: "experts/expert-builder/materials/sourcing.md"
format: markdown
source_id: 340356a2f85afb10
sections: 5
---

# Sourcing rules
## Sourcing rules (auto-research mode)

When the user gives only a topic, you find the sources. The knowledge you generate is
committed to the repo and served as an expert's authoritative corpus, so the bar is high.

## What to prefer

- **Authoritative & widely used**: canonical textbooks, official documentation, standards
  bodies, primary sources, peer-reviewed overviews, or the recognized reference on the topic.
- **Openly licensed & freely available**: public domain (e.g. Project Gutenberg, Wikisource),
  Creative Commons, official docs you may mirror, or government/standards publications.
- **Stable URLs**: prefer permalinks and canonical document URLs over blog reposts or pages
  that change. For public-domain books, prefer the **EPUB** edition from Project Gutenberg
  (e.g. `.../cache/epub/<id>/pg<id>.epub`) over the `.txt`: the extractor sections EPUBs by
  chapter, so citations get real anchors (see the formats reference). Only use `.txt` when no
  structured edition exists.

## Map vs corpus - ingest the territory, not just the map

Some sources *name* a body of knowledge without *containing* it: exam guides, syllabi, curricula, standards indexes, tables of contents, and "in-scope / out-of-scope" lists.
These are **maps** - they enumerate topics but do not explain them.
An expert built from a map alone can tell a user *what* exists but not *how* or *why*, which is almost always what the user actually asks.

Signs a source is a map, not a corpus: dense bullet lists, repeated lead-ins like "Knowledge of:" / "Skills in:", long lists of proper nouns (product, service, or standard names) with little connecting prose, and an outline-shaped structure.

So treat a map as a **plan for sourcing, not as the corpus**:

1. Use the map to enumerate the domains, tasks, and named entities (services, concepts, standards) the expert must cover.
2. For each, fetch the authoritative source that actually **explains** it - the official documentation, the reference manual, the primary text - and ingest **those** as the corpus.
3. Keep the map too if it helps with scope and routing, but never let it be the only material.

Example: a cloud certification exam guide lists domains, tasks, and dozens of service names.
Ingest the guide to fix scope, then ingest each named service's official documentation so the expert can actually answer how-to questions - not just recite the syllabus.

This rule holds in **guided ingest** too, not only auto-research.
If the user hands you a map as the material, do not silently treat it as the corpus: tell them it is a map, offer to expand it into the explanatory sources it points to, and build only after they choose.

## What to avoid

- Anything whose license forbids redistribution (most commercial books, paywalled articles,
  "all rights reserved" pages). If you cannot confirm the license permits mirroring, do not
  ingest it — ask the user.
- Low-quality, SEO, or AI-generated summaries; forum threads; unstable or mirror URLs.
- Redundant sources that cover the same ground — deduplicate to a tight, high-signal set.

## The propose-then-confirm loop

1. Search and assemble a shortlist of **3–8** sources.
   If a candidate is a map (see above), expand it: enumerate the explanatory sources needed to actually cover its topics and shortlist **those**, not just the map.
2. For each, state: the title/author, the URL, **why it is authoritative**, and its
   **license / why it is freely usable**.
3. Present the shortlist and **wait for the user to approve** (they may cut or add). Build only
   from approved sources.
4. If a source turns out to be unusable at build time (fetch fails, extracts empty, wrong
   license), report it and continue with the rest rather than silently dropping it.

---
title: "Build workflow"
origin: "experts/expert-builder/materials/workflow.md"
format: markdown
source_id: 49f664611a8b875a
sections: 3
---

# Build workflow
## Build workflow

The exact steps to add or update an expert. Run everything from the repo root via the Python
dev path.

## Build workflow › Steps

1. **Pick the name + description.** Choose a short kebab-case-able name and write the routing
   `description` (see the roster schema — this is what routing depends on).
2. **Scaffold** the expert:
   ```bash
   uv run moe scaffold <name> -d "<description>"
   ```
   This creates `experts/<slug>/` (with `EXPERT.md` and an empty `materials/`) and adds a stub
   entry to `experts.yaml`.
3. **Add materials.** For local files, copy them into `experts/<slug>/materials/` and add a
   `path:` entry. For web sources, add a `url:` entry. Set `title:`/`author:` on each. Refine
   the `description` while you are there.
4. **Build:**
   ```bash
   uv run moe build
   ```
   This extracts each source into `experts/<slug>/knowledge/<source>.md` + `INDEX.md`, then
   recompiles every host build under `dist/` (including `dist/dev`).
5. **Verify** (do not skip): confirm `experts/<slug>/knowledge/INDEX.md` lists the sources and
   at least one `<source>.md` exists with real section headings and page/section anchors. Open
   one file and confirm a section carries a citable heading. If a source fetched nothing or
   extracted empty, fix the URL/file or drop it and rebuild.
6. **Deploy reminder.** Tell the user how to install:
   - `npx github:tiennt235/moe install` — end users get the knowledge experts.
   - `npx github:tiennt235/moe install --dev` — maintainers also get builder/dev-only experts.

## Build workflow › Managing the roster

- `uv run moe list` shows the current team.
- To update an existing expert, edit its `materials` in `experts.yaml` and re-run `uv run moe
  build`.

# /moe add-expert <name>

Add a new expert to the vault. There are two ways in.

## In the dev repo — delegate to the expert-builder

If you are working inside the moe repo (with the dev build installed via `npx
github:tiennt235/moe install --dev`), delegate to the **`moe-expert-builder`** subagent. It
handles the whole flow in one of two modes:

- **Guided ingest** — you give it a topic *and* specific materials (file paths or URLs); it
  ingests exactly those.
- **Auto-research** — you give it only a topic; it searches for authoritative, openly-licensed
  sources, proposes a shortlist for you to approve, then builds from the approved set.

Either way it scaffolds the expert, patches `experts.yaml`, runs `uv run moe build`, verifies
the knowledge + citations, and reports.

## By hand (authoring/dev path, needs Python)

Scaffold, drop in material, describe it, and build:

```bash
uv run moe scaffold <name> -d "<one-line routing description>"   # or python -m moe scaffold …
#   add material into experts/<name>/materials/ (or url: entries in experts.yaml)
uv run moe build
```

Write a good one-line `description` (it drives routing) and supported material formats are
PDF/EPUB/MOBI/HTML/Markdown/text. Then deploy with `npx github:tiennt235/moe install`.

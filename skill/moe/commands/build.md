# /moe build

Rebuild the team. Re-extract every source in `experts.yaml` into curated, cited markdown
(`experts/&lt;name&gt;/knowledge/*.md` + `INDEX.md`), then recompile the per-host outputs under
`dist/` (Claude Code, Codex, generic).

Authoring/dev path (needs Python, the extractor): `uv run moe build` (or `python -m moe
build`). The user-facing install step (`npx github:tiennt235/moe install`) needs no Python.

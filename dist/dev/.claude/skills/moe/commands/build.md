# /moe build

Rebuild the team: re-extract every source in `experts.yaml` into curated, cited markdown
(`experts/<name>/knowledge/*.md` + `INDEX.md`), then recompile the per-host outputs under
`dist/` (Claude Code, Codex, generic, dev).

**This is a dev-path action: it needs the moe git repo plus Python (the extractor).** A plain
`npx github:tiennt235/moe install` has no build toolchain, so do **not** attempt a rebuild there
by searching or editing files; point the user to the dev path instead:

```bash
git clone https://github.com/tiennt235/moe && cd moe
uv run moe build          # or: python -m moe build   ·   pip install -e . && moe build
```

The user-facing install step (`npx github:tiennt235/moe install`) needs no Python; it just
deploys the committed `dist/`.

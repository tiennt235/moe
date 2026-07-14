# /moe build

Rebuild the team. Re-extract every source in `experts.yaml` into curated, cited markdown
(`experts/&lt;name&gt;/knowledge/*.md` + `INDEX.md`), then recompile the per-host outputs under
`dist/` (Claude Code, Codex, generic).

Equivalent CLI: `npx moe build`. Requires Python (the extractor); the install step does not.

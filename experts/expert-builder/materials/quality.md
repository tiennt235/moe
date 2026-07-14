# Quality checklist

Run this before declaring a new or updated expert done.

## Routing

- [ ] The `description` names the concrete sub-topics and ends with a clear "Route here for …"
      cue. A stranger could tell from it what questions belong to this expert.
- [ ] The domain is singular. If it spans two unrelated areas, split into two experts.
- [ ] The name/slug is short, lowercase-friendly, and unambiguous against existing experts
      (check `uv run moe list`).

## Knowledge

- [ ] `experts/<slug>/knowledge/INDEX.md` exists and lists every source with its sections.
- [ ] Each `<source>.md` has YAML front-matter (title, and author/page/section metadata) and
      real section headings — not one giant untitled blob.
- [ ] Page numbers are present for PDFs; section headings are present for HTML/EPUB/markdown.
- [ ] No source extracted empty or errored during `uv run moe build`.

## Licensing & sources

- [ ] Every source is redistributable (public domain / open license / cleared official page).
- [ ] Sources are authoritative and deduplicated; no filler.

## Deploy

- [ ] `uv run moe build` completed and reported the expert's source + section counts.
- [ ] The user was told the install command (`npx github:tiennt235/moe install`, or `--dev` for
      builder/dev-only experts).

## Smoke test

- [ ] Ask the finished expert one representative question and confirm it answers **only** from
      its knowledge and cites `source title · section · p.<page>`.

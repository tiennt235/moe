# expert-builder — knowledge index

_Consult this index, then grep/read the files below to answer expert-builder questions. Always cite: source title · section · page._

## Roster schema (experts.yaml)  →  `roster-schema-experts-yaml.md`
- Roster schema (experts.yaml)  ·  139 chars  ·  "The roster at the repo root drives everything. It is a YAML file with a `name…"
- Fields  ·  1.4k chars  ·  "`name` (required): the expert's display name. Its slug (kebab-case, lowercase…"
- Example entry  ·  366 chars  ·  "```yaml"

## Supported material formats  →  `supported-material-formats.md`
- Supported material formats  ·  242 chars  ·  "Each material is either a local file (`path:`) or a fetched URL (`url:`). The…"
- Formats  ·  662 chars  ·  "**PDF** (`.pdf`): text + table of contents become sections with page numbers.…"
- path vs url  ·  512 chars  ·  "`path:` — a repo-relative file. Place local sources under `experts/<slug>/mat…"
- Prefer structured formats for good citations  ·  654 chars  ·  "Citations are only as granular as the source's structure. The extractor makes…"

## Build workflow  →  `build-workflow.md`
- Build workflow  ·  102 chars  ·  "The exact steps to add or update an expert. Run everything from the repo root…"
- Steps  ·  1.4k chars  ·  "1. **Pick the name + description.** Choose a short kebab-case-able name and w…"
- Managing the roster  ·  147 chars  ·  "`uv run moe list` shows the current team."

## Sourcing rules  →  `sourcing-rules.md`
- Sourcing rules (auto-research mode)  ·  175 chars  ·  "When the user gives only a topic, you find the sources. The knowledge you gen…"
- What to prefer  ·  763 chars  ·  "**Authoritative & widely used**: canonical textbooks, official documentation,…"
- Map vs corpus - ingest the territory, not just the map  ·  1.6k chars  ·  "Some sources *name* a body of knowledge without *containing* it: exam guides,…"
- What to avoid  ·  388 chars  ·  "Anything whose license forbids redistribution (most commercial books, paywall…"
- The propose-then-confirm loop  ·  640 chars  ·  "1. Search and assemble a shortlist of **3–8** sources."

## Quality checklist  →  `quality-checklist.md`
- Quality checklist  ·  55 chars  ·  "Run this before declaring a new or updated expert done."
- Routing  ·  384 chars  ·  "[ ] The `description` names the concrete sub-topics and ends with a clear "Ro…"
- Knowledge  ·  792 chars  ·  "[ ] `experts/<slug>/knowledge/INDEX.md` exists and lists every source with it…"
- Licensing & sources  ·  154 chars  ·  "[ ] Every source is redistributable (public domain / open license / cleared o…"
- Deploy  ·  214 chars  ·  "[ ] `uv run moe build` completed and reported the expert's source + section c…"
- Smoke test  ·  161 chars  ·  "[ ] Ask the finished expert one representative question and confirm it answer…"

# moe — a team of domain experts, as agent skills

`moe` packages a **mixture of domain experts** as installable **skills + subagents** for your
coding agent (Claude Code, Codex, Pi, …). Each expert owns a curated **knowledge folder** built
from your materials (books, articles, docs); it answers by **searching that folder** (grep/read)
and **citing** it — *no RAG, no vector DB, no embeddings*. A **router skill** picks the right
expert(s) for a question and synthesizes a cited answer.

Modeled on [impeccable.style](https://impeccable.style): author once, compile per-host builds
into `dist/`, and deploy with a lightweight installer.

## Quick start

```bash
npx moe build                 # extract materials → knowledge + INDEX, compile dist/  (needs Python)
npx moe install               # detect your agent(s) and deploy the skill + experts
# then, inside your agent:
/moe ask "which valve is on the left side of the heart?"
```

`build` needs Python (the extractor); `install` is pure Node and just deploys the committed
`dist/`. Install prefers [uv](https://astral.sh/uv) for `build`; otherwise `pip install -e .`.

## How it works

- **Expert = subagent.** `experts/<name>/EXPERT.md` (optional guidance) + `experts/<name>/knowledge/`
  (built markdown + `INDEX.md`). The expert reads the index, greps the files, and cites
  `source · section · page`.
- **Router = skill.** Reads the roster (`experts.yaml`) and picks the matching expert(s) by
  reasoning over their descriptions — no embeddings. Then delegates and synthesizes.
- **Retrieval = agentic file search.** Coding agents are already great at grep/read; that *is*
  the retrieval engine. Citations come from each knowledge file's front-matter + headings.

## Install targets & delegation

| Host | Installs to | Delegation |
|---|---|---|
| **Claude Code** | `.claude/skills/moe` + `.claude/agents/moe-*` | native subagents (Agent tool) |
| **Codex** | `.agents/skills/moe` + `.codex/agents` + `AGENTS.moe.md` | native subagents; paste the snippet into `AGENTS.md` |
| **Pi / generic** | `.agents/skills/moe` | inline expert-mode (no subagent primitive) |

```bash
npx moe install --providers=claude,codex,agents --scope=project   # or --scope=global
```

Claude Code can also install via plugin marketplace (`plugin/plugin.json`), and any
Agent-Skills host via `npx skills add <repo>`.

## Manage the team

```bash
npx moe list                      # show the roster
npx moe scaffold neurology -d "Clinical neurology…"   # new expert
#   drop material into experts/neurology/materials/, then:
npx moe build && npx moe install
```

Add materials as `path:` (local) or `url:` entries under an expert in `experts.yaml`. Supported
formats: PDF (+OCR), EPUB, MOBI (via Calibre), HTML, Markdown/text.

## Portability

The repo *is* the shareable expert team — `dist/` and `knowledge/` are committed. Anyone gets
your experts with `npx moe install` (or `npx skills add <repo>`). No database, snapshot, or
re-embedding.

## Layout

```
experts.yaml            roster (drives routing)
experts/<name>/         EXPERT.md · materials/ · knowledge/ (built)
skill/moe/              router skill source (SKILL.md + commands)
templates/              shared expert-behavior template
src/moe/                Python builder (extract → knowledge → dist)
bin/moe.mjs             Node umbrella CLI (install/build/scaffold/list)
dist/{claude-code,codex,agents}/   committed per-host builds
plugin/plugin.json      Claude Code marketplace manifest
```

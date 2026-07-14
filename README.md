# moe — a team of domain experts, as agent skills

`moe` packages a **mixture of domain experts** as installable **skills + subagents** for your
coding agent (Claude Code, Codex, Pi, …). Each expert owns a curated **knowledge folder** built
from your materials (books, articles, docs); it answers by **searching that folder** (grep/read)
and **citing** it — *no RAG, no vector DB, no embeddings*. A **router skill** picks the right
expert(s) for a question and synthesizes a cited answer.

Modeled on [impeccable.style](https://impeccable.style): author once, compile per-host builds
into `dist/`, and deploy with a lightweight installer.

## Two paths

`moe` deliberately splits along the two audiences:

- **Authoring / dev (Python)** — build experts from source material. Needs Python (the
  extractor).
- **User / agent facing (`npx github:tiennt235/moe`)** — install the built experts into your
  agent. Pure Node, no Python.

```bash
# 1) authoring (dev): turn materials → knowledge + INDEX and compile per-host dist/
uv run moe build            # or: pip install -e . && moe build   ·   python -m moe build

# 2) use it (any user/agent): deploy the committed dist/ into your agent — no flags needed,
#    it auto-detects your agent(s) and scope
npx github:tiennt235/moe install

# then, inside your agent:
/moe ask "which valve is on the left side of the heart?"
```

A user who just wants the experts never needs Python — `dist/` is committed, so `npx
github:tiennt235/moe install` (or `npx skills add tiennt235/moe`) is all they run. With no
flags it detects your installed agent(s) (`~/.claude`, `~/.codex`, `.agents`/`.pi`) and scope.

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
npx github:tiennt235/moe install --providers=claude,codex,agents --scope=project   # or --scope=global
```

Claude Code can also install via plugin marketplace (`plugin/plugin.json`), and any
Agent-Skills host via `npx skills add tiennt235/moe`.

## Manage the team (authoring / dev — Python)

```bash
uv run moe list                              # show the roster
uv run moe scaffold neurology -d "Clinical neurology…"   # new expert
#   drop material into experts/neurology/materials/, then:
uv run moe build && npx github:tiennt235/moe install
```

Add materials as `path:` (local) or `url:` entries under an expert in `experts.yaml`. Supported
formats: PDF (+OCR), EPUB, MOBI (via Calibre), HTML, Markdown/text.

## Portability

The repo *is* the shareable expert team — `dist/` and `knowledge/` are committed. Anyone gets
your experts with `npx github:tiennt235/moe install` (or `npx skills add tiennt235/moe`). No
database, snapshot, or re-embedding.

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

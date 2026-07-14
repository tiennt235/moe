# moe-mcp — Mixture of Domain Experts

A locally-run **MCP server** that acts as a *mixture of domain experts*. Each expert owns a
domain knowledge base built by ingesting source material (books, articles, e-books, web
pages) into **Qdrant Cloud**. A single MCP tool **auto-routes** a question to the most
relevant expert(s), retrieves grounded passages, and always returns **traceable citations**.
Accuracy is the top priority.

Three surfaces over one shared core:

| Surface | Command | Purpose |
|---|---|---|
| Dashboard | `moe-dashboard` | Build & manage the expert team (upload material, watch ingestion, test queries) |
| CLI | `moe-ingest` | Scriptable mirror of the dashboard |
| MCP server | `moe-mcp` | Read-only querying for MCP clients (Claude Code / Desktop) |

- **Embeddings + rerank:** AWS Bedrock — Cohere Embed v4 + Cohere Rerank 3.5
- **Contextual retrieval + synthesis:** Claude on Bedrock
- **KB:** Qdrant Cloud (one collection per expert), hybrid dense + BM25 sparse + RRF fusion
- **Shared state:** a local SQLite registry (`moe.db`), rebuildable from Qdrant + `experts.yaml`

See `docs/` and the plan for the full design.

## Quick start

```bash
uv venv --python 3.11 && uv pip install -e .
cp .env.example .env            # fill in Qdrant + AWS
moe-ingest doctor               # preflight Qdrant + Bedrock
moe-ingest create-expert --name cardiology --description "Clinical cardiology."
moe-ingest add --expert cardiology --path ./braunwald.pdf
moe-dashboard                   # open http://127.0.0.1:8848
```

Wire the MCP server into Claude Code (`.mcp.json`):

```json
{ "mcpServers": { "moe": { "command": "moe-mcp" } } }
```

## Region note

Bedrock Rerank 3.5 is available only in `us-west-2`, `ca-central-1`, `eu-central-1`,
`ap-northeast-1`. Use a region that also serves Embed v4 + Claude (`us-west-2` recommended).

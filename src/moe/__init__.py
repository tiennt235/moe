"""moe — a mixture-of-domain-experts MCP server.

Three surfaces over one shared core:
  * ``moe-dashboard`` (moe.api)    — FastAPI + React SPA for authoring/managing experts
  * ``moe-ingest``    (moe.cli)    — CLI mirror of the dashboard for scripting
  * ``moe-mcp``       (moe.server) — read-only MCP server for querying the KB

The core (``moe.store``, ``moe.ingest``, ``moe.retrieval``, ``moe.clients``) does the real
work; each surface is a thin adapter.
"""

__version__ = "0.1.0"

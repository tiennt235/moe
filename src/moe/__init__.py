"""moe — a distributable team of domain experts, shipped as agent skills.

No RAG. Each expert is a subagent with a curated ``knowledge/`` folder it searches by hand
(grep/read) and cites. The router is a skill. Authored once, this package's ``moe build``
compiles per-agent outputs into ``dist/`` which ``npx github:tiennt235/moe install`` deploys
into a host (Claude Code, Codex, Pi, …).
"""

__version__ = "0.2.0"

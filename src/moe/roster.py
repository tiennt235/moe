"""The expert-team roster — the source of truth the router reasons over.

Loaded from ``experts.yaml`` at the repo root. Descriptions drive routing (the host model
picks an expert by reading them), so write them to say what each expert *knows*."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

from moe.models import slugify

DEFAULT_TOOLS = ["Read", "Grep", "Glob"]
# A builder expert *acts* (scaffolds experts, edits the roster, runs the build), so it needs
# write/exec/web tools a read-only knowledge expert never gets.
BUILDER_TOOLS = ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "WebSearch", "WebFetch"]


class MaterialSpec(BaseModel):
    path: str | None = None      # repo-root-relative file path
    url: str | None = None       # or a URL to fetch at build time
    title: str | None = None
    author: str | None = None

    @property
    def origin(self) -> str:
        origin = self.url or self.path
        if not origin:
            raise ValueError("material needs a 'path' or 'url'")
        return origin


class ExpertSpec(BaseModel):
    name: str
    description: str
    # "knowledge": answers from its corpus and cites it (default). "builder": a procedural
    # meta-expert that creates other experts — rendered from a different behavior template.
    kind: Literal["knowledge", "builder"] = "knowledge"
    # dev_only experts run only in the repo + Python dev path, so they are excluded from the
    # shipped end-user builds and the router roster (they ship only in the dist/dev build).
    dev_only: bool = False
    materials: list[MaterialSpec] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=lambda: list(DEFAULT_TOOLS))
    model: str | None = None            # optional Claude Code model hint
    proactive: bool = True              # subagent description invites proactive routing

    @property
    def slug(self) -> str:
        return slugify(self.name)

    @property
    def agent_name(self) -> str:
        return f"moe-{self.slug}"        # e.g. .claude/agents/moe-cardiology.md


class Roster(BaseModel):
    name: str = "experts"
    experts: list[ExpertSpec] = Field(default_factory=list)

    def get(self, name: str) -> ExpertSpec | None:
        slug = slugify(name)
        return next((e for e in self.experts if e.slug == slug), None)


def load_roster(path: str | Path = "experts.yaml") -> Roster:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"roster not found: {p} (run `moe scaffold <name>` to create one)")
    data = yaml.safe_load(p.read_text()) or {}
    return Roster(**data)

"""The expert-team roster — the source of truth the router reasons over.

Loaded from ``experts.yaml`` at the repo root. Descriptions drive routing (the host model
picks an expert by reading them), so write them to say what each expert *knows*."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from moe.models import slugify

DEFAULT_TOOLS = ["Read", "Grep", "Glob"]


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

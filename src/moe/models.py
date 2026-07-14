"""Canonical data models for the knowledge builder.

Only what the RAG-free build needs: the extraction models (:class:`Document` /
:class:`Section`) plus a couple of id/slug helpers. Everything vector/DB-related was
removed in the pivot to a skills-based distribution."""

from __future__ import annotations

import hashlib
from enum import StrEnum

from pydantic import BaseModel, Field


class SourceFormat(StrEnum):
    pdf = "pdf"
    epub = "epub"
    mobi = "mobi"
    html = "html"
    markdown = "markdown"
    text = "text"


class Section(BaseModel):
    """A structural unit of a document (chapter / heading region). Carries the citation
    backbone: the heading path and (for PDFs) a page range."""

    heading_path: list[str] = Field(default_factory=list)  # e.g. ["Ch. 3", "3.2 Valves"]
    text: str
    page_start: int | None = None
    page_end: int | None = None


class Document(BaseModel):
    """A parsed, normalized source, ready to be written out as curated knowledge."""

    source_id: str
    title: str | None = None
    author: str | None = None
    url: str | None = None
    fmt: SourceFormat
    sections: list[Section] = Field(default_factory=list)


# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------
def content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def make_source_id(origin: str, content_hash_hex: str) -> str:
    return hashlib.sha256(f"{origin}\x00{content_hash_hex}".encode()).hexdigest()[:16]


def slugify(name: str) -> str:
    # kebab-case: matches agent/skill/dir naming conventions (e.g. moe-expert-builder) and keeps
    # multi-word expert names readable as directories and file names.
    out = "".join(c if c.isalnum() else "-" for c in name.strip().lower())
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-")

"""Shared dataclasses for extraction and packing."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class PageRecord:
    page: int | None
    text: str
    confidence: str = "high"  # high | low | unknown
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExtractedDocument:
    source_path: str
    source_id: str
    source_sha256: str
    format: str
    title: str
    text: str
    pages: list[PageRecord]
    extraction_method: str
    warnings: list[str] = field(default_factory=list)
    removed_invisible: int = 0
    structure_degraded: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return data


@dataclass
class Chunk:
    chunk_id: str
    source_id: str
    title: str
    text: str
    page_start: int | None = None
    page_end: int | None = None
    char_start: int = 0
    char_end: int = 0
    heading_path: list[str] = field(default_factory=list)
    sha256: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

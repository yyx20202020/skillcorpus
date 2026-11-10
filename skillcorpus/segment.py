"""Split extracted documents into citable chunks."""

from __future__ import annotations

import re

from skillcorpus.hashing import sha256_text
from skillcorpus.models import Chunk, ExtractedDocument

_ATX = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_CHAPTER = re.compile(
    r"^(?:chapter|unit|lesson|第)\s*(\d+)|^第\s*[0-9一二三四五六七八九十百]+\s*[章节篇]",
    re.IGNORECASE,
)
_MAX_CHUNK_CHARS = 3500


def segment_document(doc: ExtractedDocument) -> list[Chunk]:
    """Prefer heading-based slices; fall back to sized windows."""
    sections = _split_by_headings(doc.text)
    if len(sections) <= 1 and len(doc.text) > _MAX_CHUNK_CHARS:
        sections = _window_split(doc.text)

    chunks: list[Chunk] = []
    for index, (title, body, start, end) in enumerate(sections, start=1):
        body = body.strip("\n")
        if not body.strip():
            continue
        page_start, page_end = _infer_pages(doc, start, end)
        chunk_id = f"{doc.source_id}-c{index:03d}"
        warnings = list(doc.warnings)
        if doc.structure_degraded:
            warnings.append("structure_degraded")
        chunks.append(
            Chunk(
                chunk_id=chunk_id,
                source_id=doc.source_id,
                title=title or f"Section {index}",
                text=body,
                page_start=page_start,
                page_end=page_end,
                char_start=start,
                char_end=end,
                heading_path=[title] if title else [],
                sha256=sha256_text(body),
                warnings=warnings,
            )
        )
    if not chunks:
        chunks.append(
            Chunk(
                chunk_id=f"{doc.source_id}-c001",
                source_id=doc.source_id,
                title=doc.title,
                text=doc.text,
                page_start=doc.pages[0].page if doc.pages else None,
                page_end=doc.pages[-1].page if doc.pages else None,
                char_start=0,
                char_end=len(doc.text),
                heading_path=[doc.title],
                sha256=sha256_text(doc.text),
                warnings=list(doc.warnings),
            )
        )
    return chunks


def _split_by_headings(text: str) -> list[tuple[str, str, int, int]]:
    lines = text.splitlines(keepends=True)
    markers: list[tuple[int, str]] = []
    offset = 0
    for line in lines:
        stripped = line.strip()
        atx = _ATX.match(stripped)
        if atx and len(atx.group(1)) <= 2:
            markers.append((offset, atx.group(2).strip()))
        elif _CHAPTER.match(stripped):
            markers.append((offset, stripped))
        offset += len(line)

    if not markers:
        return [("Document", text, 0, len(text))]

    # Include preamble before first heading.
    sections: list[tuple[str, str, int, int]] = []
    if markers[0][0] > 0:
        pre = text[: markers[0][0]]
        if pre.strip():
            sections.append(("Preamble", pre, 0, markers[0][0]))

    for i, (start, title) in enumerate(markers):
        end = markers[i + 1][0] if i + 1 < len(markers) else len(text)
        sections.append((title, text[start:end], start, end))
    return sections


def _window_split(text: str) -> list[tuple[str, str, int, int]]:
    sections: list[tuple[str, str, int, int]] = []
    start = 0
    index = 1
    while start < len(text):
        end = min(len(text), start + _MAX_CHUNK_CHARS)
        if end < len(text):
            # Break on paragraph boundary when possible.
            cut = text.rfind("\n\n", start + _MAX_CHUNK_CHARS // 2, end)
            if cut != -1:
                end = cut
        sections.append((f"Window {index}", text[start:end], start, end))
        index += 1
        start = end
    return sections


def _infer_pages(
    doc: ExtractedDocument, char_start: int, char_end: int
) -> tuple[int | None, int | None]:
    """Map character offsets onto page records when pages carry numbers."""
    numbered = [p for p in doc.pages if p.page is not None]
    if not numbered:
        return None, None
    # Approximate: walk cumulative page text lengths joined with \n\n.
    cursor = 0
    hit: list[int] = []
    for page in numbered:
        piece = page.text
        length = len(piece) + 2  # account for join
        page_start = cursor
        page_end = cursor + len(piece)
        if page_end >= char_start and page_start <= char_end:
            hit.append(int(page.page))
        cursor += length
    if not hit:
        return numbered[0].page, numbered[-1].page
    return hit[0], hit[-1]

"""Plain text and Markdown extraction."""

from __future__ import annotations

from pathlib import Path

from skillcorpus.hashing import sha256_file, sha256_text
from skillcorpus.models import ExtractedDocument, PageRecord
from skillcorpus.sanitize import sanitize_text
from skillcorpus.security import assert_source_readable


def extract(path: Path, *, source_id: str | None = None) -> ExtractedDocument:
    path = assert_source_readable(path)
    raw = path.read_text(encoding="utf-8", errors="replace")
    text, removed = sanitize_text(raw)
    if not text.strip():
        from skillcorpus.errors import ExtractionError

        raise ExtractionError(f"No visible text in {path.name}")
    sid = source_id or sha256_file(path)[:12]
    title = _guess_title(text, path.stem)
    return ExtractedDocument(
        source_path=str(path.resolve()),
        source_id=sid,
        source_sha256=sha256_file(path),
        format="markdown" if path.suffix.lower() in {".md", ".markdown"} else "text",
        title=title,
        text=text,
        pages=[PageRecord(page=None, text=text, confidence="high")],
        extraction_method="utf8_text",
        removed_invisible=removed,
        metadata={"text_sha256": sha256_text(text)},
    )


def _guess_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("# "):
            return s[2:].strip() or fallback
        if s:
            return s[:80]
    return fallback

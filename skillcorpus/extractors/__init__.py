"""Format adapters."""

from __future__ import annotations

from pathlib import Path

from skillcorpus.errors import UnsupportedFormatError
from skillcorpus.extractors import epub as epub_ext
from skillcorpus.extractors import html as html_ext
from skillcorpus.extractors import pdf as pdf_ext
from skillcorpus.extractors import text_md as text_ext
from skillcorpus.models import ExtractedDocument

SUPPORTED_SUFFIXES = {
    ".md": "markdown",
    ".markdown": "markdown",
    ".txt": "text",
    ".html": "html",
    ".htm": "html",
    ".pdf": "pdf",
    ".epub": "epub",
}


def extract_path(
    path: Path,
    *,
    ocr: bool = False,
    source_id: str | None = None,
) -> ExtractedDocument:
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise UnsupportedFormatError(
            f"Unsupported format {suffix!r}. Supported: "
            + ", ".join(sorted(SUPPORTED_SUFFIXES))
        )
    kind = SUPPORTED_SUFFIXES[suffix]
    if kind in {"markdown", "text"}:
        return text_ext.extract(path, source_id=source_id)
    if kind == "html":
        return html_ext.extract(path, source_id=source_id)
    if kind == "pdf":
        return pdf_ext.extract(path, ocr=ocr, source_id=source_id)
    if kind == "epub":
        return epub_ext.extract(path, source_id=source_id)
    raise UnsupportedFormatError(f"Unsupported format: {suffix}")

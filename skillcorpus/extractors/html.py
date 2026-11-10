"""HTML → text that preserves inline runs and code blocks.

Unlike BeautifulSoup.get_text(separator='\\n'), inline tags do not insert
newlines between text nodes. Block tags still create paragraph boundaries.
"""

from __future__ import annotations

import html.parser
from pathlib import Path

from skillcorpus.errors import ExtractionError
from skillcorpus.hashing import sha256_file, sha256_text
from skillcorpus.models import ExtractedDocument, PageRecord
from skillcorpus.sanitize import sanitize_text
from skillcorpus.security import assert_source_readable


class _HTMLTextExtractor(html.parser.HTMLParser):
    SKIP = frozenset({"script", "style", "head", "noscript"})
    BLOCK = frozenset({
        "address", "article", "aside", "blockquote", "br", "dd", "div", "dl",
        "dt", "fieldset", "figcaption", "figure", "footer", "form", "h1", "h2",
        "h3", "h4", "h5", "h6", "header", "hr", "li", "main", "nav", "ol", "p",
        "pre", "section", "table", "tbody", "tfoot", "thead", "tr", "ul",
    })
    CELL = frozenset({"td", "th"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip = 0
        # Do not name this `_pending` — html.parser.HTMLParser uses that name
        # internally on Python 3.12+.
        self._boundary = ""
        self._in_pre = 0

    def _mark(self, sep: str) -> None:
        if sep == "\n" or not self._boundary:
            self._boundary = sep

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        if tag in self.SKIP:
            self._skip += 1
        if tag == "pre":
            self._in_pre += 1
        if tag in self.BLOCK:
            self._mark("\n")
        elif tag in self.CELL:
            self._mark("\t")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP:
            if self._skip:
                self._skip -= 1
            return
        if tag == "pre" and self._in_pre:
            self._in_pre -= 1
        if tag in self.BLOCK:
            self._mark("\n")
        elif tag in self.CELL:
            self._mark("\t")

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        if self._boundary:
            if not data.strip() and not self._in_pre:
                return
            if self._parts:
                self._parts.append(self._boundary)
            self._boundary = ""
        self._parts.append(data)

    def get_text(self) -> str:
        return "".join(self._parts)


def html_to_text(raw_html: str) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(raw_html)
    parser.close()
    return parser.get_text()


def extract(path: Path, *, source_id: str | None = None) -> ExtractedDocument:
    path = assert_source_readable(path)
    raw = path.read_text(encoding="utf-8", errors="replace")
    text, removed = sanitize_text(html_to_text(raw))
    if not text.strip():
        raise ExtractionError(f"No visible text in HTML: {path.name}")
    sid = source_id or sha256_file(path)[:12]
    title = path.stem
    for line in text.splitlines():
        if line.strip():
            title = line.strip()[:80]
            break
    return ExtractedDocument(
        source_path=str(path.resolve()),
        source_id=sid,
        source_sha256=sha256_file(path),
        format="html",
        title=title,
        text=text,
        pages=[PageRecord(page=None, text=text, confidence="high")],
        extraction_method="stdlib_html_parser",
        removed_invisible=removed,
        metadata={"text_sha256": sha256_text(text)},
    )

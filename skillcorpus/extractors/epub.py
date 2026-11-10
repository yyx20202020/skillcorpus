"""EPUB extraction with spine order and archive safety checks."""

from __future__ import annotations

import html as html_lib
import posixpath
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from skillcorpus.errors import ExtractionError, SecurityError
from skillcorpus.extractors.html import html_to_text
from skillcorpus.hashing import sha256_file, sha256_text
from skillcorpus.models import ExtractedDocument, PageRecord
from skillcorpus.sanitize import sanitize_text
from skillcorpus.security import assert_source_readable

# Hard limits against zip bombs / oversized EPUB payloads.
MAX_EPUB_BYTES = 40 * 1024 * 1024
MAX_MEMBER_BYTES = 8 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED = 80 * 1024 * 1024
MAX_MEMBERS = 5_000
MAX_COMPRESSION_RATIO = 200.0

_OPF_ITEM = re.compile(
    r"<(?:[A-Za-z_][\w.-]*:)?item\b([^>]*)/?>",
    re.IGNORECASE,
)
_OPF_ITEMREF = re.compile(
    r"<(?:[A-Za-z_][\w.-]*:)?itemref\b([^>]*)/?>",
    re.IGNORECASE,
)
_ATTR = re.compile(
    r"""([A-Za-z_][\w:.-]*)\s*=\s*(["'])(.*?)\2""",
    re.DOTALL,
)


def extract(path: Path, *, source_id: str | None = None) -> ExtractedDocument:
    path = assert_source_readable(path, max_bytes=MAX_EPUB_BYTES)
    if path.stat().st_size > MAX_EPUB_BYTES:
        raise SecurityError(f"EPUB exceeds size limit: {path.name}")

    try:
        with zipfile.ZipFile(path) as zf:
            _validate_zip_safety(zf)
            opf_path = _find_opf(zf)
            opf_text = _read_member_text(zf, opf_path)
            manifest, spine = _parse_opf(opf_text)
            ordered_hrefs = [manifest[i] for i in spine if i in manifest]
            if not ordered_hrefs:
                # Fall back to all HTML-like manifest items in declared order.
                ordered_hrefs = [
                    href
                    for href in manifest.values()
                    if href.lower().endswith((".xhtml", ".html", ".htm", ".xml"))
                ]
            parts: list[str] = []
            for href in ordered_hrefs:
                member = _resolve_opf_href(opf_path, href)
                raw = _read_member_text(zf, member)
                # Reject DTD / entity expansion vectors in content docs.
                if _has_dangerous_xml_decl(raw):
                    raise SecurityError(
                        f"EPUB member declares DTD/entities (refused): {member}"
                    )
                parts.append(html_to_text(raw))
    except zipfile.BadZipFile as exc:
        raise ExtractionError(f"Invalid EPUB/ZIP: {path.name}") from exc

    text = "\n\n".join(p for p in parts if p.strip())
    text, removed = sanitize_text(text)
    if not text.strip():
        raise ExtractionError(f"No visible text in EPUB: {path.name}")

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
        format="epub",
        title=title,
        text=text,
        pages=[PageRecord(page=None, text=text, confidence="high")],
        extraction_method="epub_spine_stdlib",
        removed_invisible=removed,
        metadata={
            "text_sha256": sha256_text(text),
            "spine_documents": len(ordered_hrefs),
        },
    )


def _validate_zip_safety(zf: zipfile.ZipFile) -> None:
    names = zf.namelist()
    if len(names) > MAX_MEMBERS:
        raise SecurityError("EPUB has too many zip members (possible zip bomb)")
    total_uncomp = 0
    for info in zf.infolist():
        name = info.filename
        if name.startswith("/") or name.startswith("\\"):
            raise SecurityError(f"EPUB zip-slip risk (absolute path): {name}")
        # Normalize and reject parent traversal.
        norm = posixpath.normpath(name.replace("\\", "/"))
        if norm.startswith("../") or norm == ".." or norm.startswith("/"):
            raise SecurityError(f"EPUB zip-slip risk (path traversal): {name}")
        if info.file_size > MAX_MEMBER_BYTES:
            raise SecurityError(f"EPUB member too large: {name}")
        total_uncomp += info.file_size
        if total_uncomp > MAX_TOTAL_UNCOMPRESSED:
            raise SecurityError("EPUB uncompressed size exceeds limit (zip bomb)")
        if info.compress_size > 0:
            ratio = info.file_size / max(info.compress_size, 1)
            if ratio > MAX_COMPRESSION_RATIO and info.file_size > 1_000_000:
                raise SecurityError(
                    f"EPUB member compression ratio too high: {name}"
                )


def _find_opf(zf: zipfile.ZipFile) -> str:
    try:
        container = _read_member_text(zf, "META-INF/container.xml")
    except KeyError as exc:
        raise ExtractionError("EPUB missing META-INF/container.xml") from exc
    if _has_dangerous_xml_decl(container):
        raise SecurityError("container.xml declares DTD/entities (refused)")
    # Prefer regex to avoid XXE via ElementTree on hostile DOCTYPE.
    match = re.search(
        r'full-path\s*=\s*["\']([^"\']+\.opf)["\']',
        container,
        re.IGNORECASE,
    )
    if not match:
        raise ExtractionError("EPUB container.xml has no OPF full-path")
    opf = match.group(1)
    _assert_safe_member_name(opf)
    return opf


def _parse_opf(opf_text: str) -> tuple[dict[str, str], list[str]]:
    if _has_dangerous_xml_decl(opf_text):
        raise SecurityError("OPF declares DTD/entities (refused)")
    manifest: dict[str, str] = {}
    for block in _OPF_ITEM.finditer(opf_text):
        attrs = {
            k.lower().split(":")[-1]: v
            for k, _quote, v in _ATTR.findall(block.group(1))
        }
        item_id = attrs.get("id")
        href = attrs.get("href")
        if item_id and href:
            manifest[item_id] = html_lib.unescape(href)
    spine: list[str] = []
    for block in _OPF_ITEMREF.finditer(opf_text):
        attrs = {
            k.lower().split(":")[-1]: v
            for k, _quote, v in _ATTR.findall(block.group(1))
        }
        idref = attrs.get("idref")
        if idref:
            spine.append(idref)
    if not manifest:
        # Last-resort XML parse without resolving entities (defused via prior DTD ban).
        try:
            root = ET.fromstring(opf_text)
        except ET.ParseError as exc:
            raise ExtractionError("Could not parse EPUB OPF") from exc
        ns = ""
        if root.tag.startswith("{"):
            ns = root.tag.split("}")[0] + "}"
        for item in root.iter(f"{ns}item"):
            item_id = item.attrib.get("id")
            href = item.attrib.get("href")
            if item_id and href:
                manifest[item_id] = href
        for itemref in root.iter(f"{ns}itemref"):
            idref = itemref.attrib.get("idref")
            if idref:
                spine.append(idref)
    return manifest, spine


def _resolve_opf_href(opf_path: str, href: str) -> str:
    href = href.split("#", 1)[0]
    base = posixpath.dirname(opf_path)
    member = posixpath.normpath(posixpath.join(base, href)) if base else href
    _assert_safe_member_name(member)
    return member


def _assert_safe_member_name(name: str) -> None:
    norm = posixpath.normpath(name.replace("\\", "/"))
    if (
        norm.startswith("../")
        or norm == ".."
        or norm.startswith("/")
        or name.startswith("/")
        or "\\" in name
    ):
        raise SecurityError(f"Unsafe EPUB member path: {name}")


def _read_member_text(zf: zipfile.ZipFile, name: str) -> str:
    _assert_safe_member_name(name)
    try:
        info = zf.getinfo(name)
    except KeyError as exc:
        raise ExtractionError(f"EPUB missing member: {name}") from exc
    if info.file_size > MAX_MEMBER_BYTES:
        raise SecurityError(f"EPUB member too large: {name}")
    data = zf.read(name)
    if len(data) > MAX_MEMBER_BYTES:
        raise SecurityError(f"EPUB member read exceeded limit: {name}")
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16", errors="replace")
    return data.decode("utf-8", errors="replace")


def _has_dangerous_xml_decl(text: str) -> bool:
    head = text.lstrip()[:4000].lower()
    if "<!doctype" in head and "entity" in head:
        return True
    if "<!entity" in head:
        return True
    return False

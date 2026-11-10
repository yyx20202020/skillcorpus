from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from skillcorpus.errors import SecurityError
from skillcorpus.extractors.epub import extract
from skillcorpus.pipeline import build_pack
from skillcorpus.segment import segment_document

ROOT = Path(__file__).resolve().parents[1]
EPUB = ROOT / "fixtures" / "epub_synth" / "rate_notes.epub"


def test_epub_spine_order_and_inline_code(tmp_path: Path):
    doc = extract(EPUB)
    assert "EPUB_SPINE_FIRST_ANCHOR" in doc.text
    assert "EPUB_SPINE_SECOND_ANCHOR" in doc.text
    assert doc.text.index("EPUB_SPINE_FIRST_ANCHOR") < doc.text.index(
        "EPUB_SPINE_SECOND_ANCHOR"
    )
    assert 'print("epub-ok")' in doc.text or "print(\"epub-ok\")" in doc.text
    assert "Chapter\n1" not in doc.text

    chunks = segment_document(doc)
    titles = " ".join(c.title for c in chunks)
    assert "1" in titles and "2" in titles

    out = tmp_path / "skill"
    info = build_pack([EPUB], out, skill_name="EPUB Notes")
    assert info["validation"]["ok"]


def test_epub_zip_slip_rejected(tmp_path: Path):
    evil = tmp_path / "slip.epub"
    with zipfile.ZipFile(evil, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip")
        zf.writestr(
            "META-INF/container.xml",
            '<?xml version="1.0"?><container><rootfiles>'
            '<rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>'
            "</rootfiles></container>",
        )
        zf.writestr(
            "OEBPS/content.opf",
            """<?xml version="1.0"?>
            <package><manifest>
            <item id="x" href="../../tmp/evil.xhtml" media-type="application/xhtml+xml"/>
            </manifest><spine><itemref idref="x"/></spine></package>""",
        )
        # Also plant a traversal member name.
        zf.writestr("../tmp/evil.xhtml", "<html><body>nope</body></html>")
    with pytest.raises(SecurityError, match="zip-slip|Unsafe EPUB"):
        extract(evil)


def test_epub_entity_dtd_rejected(tmp_path: Path):
    evil = tmp_path / "entity.epub"
    with zipfile.ZipFile(evil, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip")
        zf.writestr(
            "META-INF/container.xml",
            '<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe "boom">]>'
            "<container><rootfiles>"
            '<rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>'
            "</rootfiles></container>",
        )
        zf.writestr(
            "OEBPS/content.opf",
            """<?xml version="1.0"?><package><manifest>
            <item id="c1" href="c1.xhtml" media-type="application/xhtml+xml"/>
            </manifest><spine><itemref idref="c1"/></spine></package>""",
        )
        zf.writestr("OEBPS/c1.xhtml", "<html><body>hi</body></html>")
    with pytest.raises(SecurityError, match="DTD|entities"):
        extract(evil)


def test_epub_zip_bomb_ratio_rejected(tmp_path: Path):
    evil = tmp_path / "bomb.epub"
    # Craft a member that claims huge size via ZipInfo trickiness is hard without
    # raw structures; instead exceed MAX_MEMBERS.
    with zipfile.ZipFile(evil, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mimetype", "application/epub+zip")
        for i in range(5001):
            zf.writestr(f"pad/{i}.txt", "x")
    with pytest.raises(SecurityError, match="too many zip members|zip bomb"):
        extract(evil)

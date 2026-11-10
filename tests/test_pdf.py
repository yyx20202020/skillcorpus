from pathlib import Path

import pytest

from skillcorpus.capabilities import detect_capabilities
from skillcorpus.errors import CapabilityError, ExtractionError
from skillcorpus.extractors.pdf import extract
from skillcorpus.pipeline import build_pack
from skillcorpus.segment import segment_document

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "fixtures" / "pdf_synth" / "queue_primer.pdf"
TWOCOL = ROOT / "fixtures" / "pdf_synth" / "twocol.pdf"
IMAGE = ROOT / "fixtures" / "pdf_synth" / "image_only_like.pdf"

pytestmark = pytest.mark.skipif(
    not detect_capabilities().pypdf and not detect_capabilities().pdftotext,
    reason="no PDF backend installed",
)


def test_pdf_text_layer_extracts_and_pages(tmp_path: Path):
    doc = extract(PDF)
    assert "backpressure" in doc.text.lower() or "有界" in doc.text
    assert doc.pages
    assert doc.pages[0].page == 1
    assert doc.pages[-1].page >= 2
    out = tmp_path / "skill"
    info = build_pack([PDF], out, skill_name="PDF Primer")
    assert info["validation"]["ok"]
    assert any(c.page_start is not None for c in segment_document(doc))


def test_image_only_pdf_fails_clearly():
    with pytest.raises(ExtractionError, match="scanned|image-only|No extractable"):
        extract(IMAGE)


def test_ocr_flag_without_ocrmypdf_is_capability_error():
    caps = detect_capabilities()
    if caps.ocrmypdf:
        pytest.skip("ocrmypdf installed; cannot assert unsupported path")
    with pytest.raises(CapabilityError, match="OCR requested"):
        extract(IMAGE, ocr=True)


def test_twocol_marks_degraded_and_avoids_layout_weld():
    """Two-column fixture: must not silently keep interleaved layout text as high confidence."""
    doc = extract(TWOCOL)
    assert "apple" in doc.text and "zebra" in doc.text
    # Welded layout signature must not remain as the chosen high-confidence body.
    assert "fruit. COLUMN" not in doc.text
    assert "fruit.COLUMN" not in doc.text
    caps = detect_capabilities()
    if caps.pdftotext:
        assert doc.structure_degraded
        assert any(
            "multicolumn" in w or "reading_order" in w or "column" in w
            for w in doc.warnings
        )
        assert all(p.confidence == "low" for p in doc.pages if p.text.strip())
    assert doc.pages[0].page == 1

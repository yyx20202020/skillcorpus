from pathlib import Path

import pytest

from skillcorpus.capabilities import detect_capabilities
from skillcorpus.errors import ExtractionError
from skillcorpus.extractors.pdf import extract
from skillcorpus.pipeline import build_pack

ROOT = Path(__file__).resolve().parents[1]
OCR_PDF = ROOT / "fixtures" / "pdf_synth" / "ocr_image_only.pdf"
MIXED = ROOT / "fixtures" / "pdf_synth" / "mixed_scan_text.pdf"

caps = detect_capabilities()
pytestmark = pytest.mark.skipif(
    not caps.ocrmypdf,
    reason="ocrmypdf not installed in this environment",
)


def test_image_only_requires_ocr_flag():
    with pytest.raises(ExtractionError, match="scanned|image-only"):
        extract(OCR_PDF)


def test_ocr_success_on_original_image_pdf(tmp_path: Path):
    doc = extract(OCR_PDF, ocr=True)
    assert "OCRSUCCESSANCHOR77" in doc.text.replace(" ", "")
    assert "ocr_via_ocrmypdf" in doc.warnings
    out = tmp_path / "skill"
    info = build_pack([OCR_PDF], out, ocr=True, skill_name="OCR Pack")
    assert info["validation"]["ok"]


def test_mixed_scan_text_with_ocr_keeps_both_pages(tmp_path: Path):
    doc = extract(MIXED, ocr=True)
    assert len(doc.pages) == 2
    assert doc.pages[0].page == 1 and doc.pages[1].page == 2
    assert "OCRSUCCESSANCHOR77" in doc.text.replace(" ", "")
    assert "MIXED_TEXT_LAYER_PAGE_TWO" in doc.text
    out = tmp_path / "skill"
    build_pack([MIXED], out, ocr=True, skill_name="Mixed Pack")

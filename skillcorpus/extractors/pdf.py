"""PDF text-layer extraction with honest OCR / multicolumn signaling."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from skillcorpus.capabilities import detect_capabilities
from skillcorpus.errors import CapabilityError, ExtractionError
from skillcorpus.hashing import sha256_file, sha256_text
from skillcorpus.models import ExtractedDocument, PageRecord
from skillcorpus.sanitize import sanitize_text
from skillcorpus.security import assert_source_readable

_WS = re.compile(r"\s+")


def extract(
    path: Path,
    *,
    ocr: bool = False,
    source_id: str | None = None,
) -> ExtractedDocument:
    path = assert_source_readable(path)
    caps = detect_capabilities()
    warnings: list[str] = []
    structure_degraded = False
    method = ""
    work_path = path

    if ocr:
        if not caps.ocrmypdf:
            raise CapabilityError(
                "OCR requested (--ocr) but ocrmypdf is not installed on this "
                "system. SkillCorpus does not fabricate OCR output. Install "
                "ocrmypdf (and tesseract) or run without --ocr."
            )
        work_path = _run_ocrmypdf(path)
        warnings.append("ocr_via_ocrmypdf")
        method = "ocrmypdf+pypdf"
    elif not caps.pypdf and not caps.pdftotext:
        raise CapabilityError(
            "No PDF text backend available. Install optional extra: "
            "pip install 'skillcorpus[pdf]' (pypdf), and/or poppler-utils "
            "(pdftotext)."
        )

    try:
        pages, method_used, page_warnings = _extract_pages(work_path, caps)
    except ExtractionError:
        if _looks_image_only(work_path, caps):
            raise ExtractionError(
                f"{path.name} looks like a scanned/image-only PDF (no extractable "
                "text layer). Re-run with --ocr after installing ocrmypdf, or OCR "
                "the file externally first. SkillCorpus will not silently succeed."
            ) from None
        raise
    method = method or method_used
    warnings.extend(page_warnings)

    if not any(p.text.strip() for p in pages):
        if _looks_image_only(work_path, caps):
            raise ExtractionError(
                f"{path.name} looks like a scanned/image-only PDF (no extractable "
                "text layer). Re-run with --ocr after installing ocrmypdf, or OCR "
                "the file externally first. SkillCorpus will not silently succeed."
            )
        raise ExtractionError(f"No extractable text in PDF: {path.name}")

    # Multicolumn / reading-order honesty: never keep silent high-confidence
    # interleaved layout text. Prefer -raw when layout diverges; still mark degraded.
    if caps.pdftotext:
        degraded, detail, raw_pages = _multicolumn_assessment(work_path)
        if degraded:
            structure_degraded = True
            warnings.append(detail)
            if raw_pages:
                pages = raw_pages
                method = f"{method}+pdftotext_raw_override"
                warnings.append("replaced_extract_with_pdftotext_raw_due_to_column_risk")
            for page in pages:
                if detail not in page.warnings:
                    page.warnings.append(detail)
                page.confidence = "low"

    full = "\n\n".join(p.text for p in pages if p.text.strip())
    # Secondary weld check on the chosen text itself.
    if _looks_interleaved_weld(full):
        structure_degraded = True
        weld = "detected_interleaved_column_weld_in_output_text"
        if weld not in warnings:
            warnings.append(weld)
        for page in pages:
            if weld not in page.warnings:
                page.warnings.append(weld)
            page.confidence = "low"

    full, removed = sanitize_text(full)
    if not full.strip():
        raise ExtractionError(f"PDF text became empty after sanitization: {path.name}")

    sid = source_id or sha256_file(path)[:12]
    title = path.stem
    return ExtractedDocument(
        source_path=str(path.resolve()),
        source_id=sid,
        source_sha256=sha256_file(path),
        format="pdf",
        title=title,
        text=full,
        pages=pages,
        extraction_method=method,
        warnings=warnings,
        removed_invisible=removed,
        structure_degraded=structure_degraded,
        metadata={
            "text_sha256": sha256_text(full),
            "page_count": len(pages),
            "ocr_requested": ocr,
        },
    )


def _run_ocrmypdf(path: Path) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="skillcorpus-ocr-"))
    out = tmp / "ocr.pdf"
    cmd = [
        "ocrmypdf",
        "--skip-text",
        "--quiet",
        str(path.resolve()),
        str(out),
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
    except OSError as exc:
        raise CapabilityError(f"Failed to launch ocrmypdf: {exc}") from exc
    if proc.returncode != 0 or not out.exists():
        raise ExtractionError(
            "ocrmypdf failed. stderr: "
            + (proc.stderr or proc.stdout or "no output")[:500]
        )
    return out


def _extract_pages(
    path: Path,
    caps,
) -> tuple[list[PageRecord], str, list[str]]:
    warnings: list[str] = []
    if caps.pypdf:
        try:
            import pypdf

            reader = pypdf.PdfReader(str(path))
            pages: list[PageRecord] = []
            for idx, page in enumerate(reader.pages, start=1):
                try:
                    raw = page.extract_text() or ""
                except Exception:
                    raw = ""
                    pages.append(
                        PageRecord(
                            page=idx,
                            text="",
                            confidence="low",
                            warnings=["page_extraction_failed"],
                        )
                    )
                    continue
                text, _ = sanitize_text(raw)
                conf = "high" if text.strip() else "low"
                w = [] if text.strip() else ["empty_page_text"]
                pages.append(
                    PageRecord(page=idx, text=text, confidence=conf, warnings=w)
                )
            if any(p.text.strip() for p in pages):
                return pages, "pypdf", warnings
            warnings.append("pypdf_empty_falling_back")
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"pypdf_failed:{type(exc).__name__}")

    if caps.pdftotext:
        # Prefer reading-order (-raw) for prose integrity; warn if layout differs.
        text = _pdftotext(path, mode="raw")
        if text and text.strip():
            pages = []
            for idx, part in enumerate(text.split("\f"), start=1):
                part = part.strip("\n")
                pages.append(
                    PageRecord(
                        page=idx,
                        text=part,
                        confidence="high" if part.strip() else "low",
                        warnings=[] if part.strip() else ["empty_page_text"],
                    )
                )
            return pages, "pdftotext_raw", warnings

    raise ExtractionError(
        "Could not extract PDF text with available backends "
        f"(pypdf={caps.pypdf}, pdftotext={caps.pdftotext})."
    )


def _pdftotext(path: Path, mode: str) -> str | None:
    if not shutil.which("pdftotext"):
        return None
    args = ["pdftotext", "-enc", "UTF-8"]
    if mode == "layout":
        args.append("-layout")
    elif mode == "raw":
        args.append("-raw")
    args.extend([str(path.resolve()), "-"])
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=120,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def _looks_image_only(path: Path, caps) -> bool:
    if caps.pdftotext:
        sample = subprocess.run(
            [
                "pdftotext",
                "-f",
                "1",
                "-l",
                "3",
                "-enc",
                "UTF-8",
                str(path.resolve()),
                "-",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if sample.returncode == 0 and not (sample.stdout or "").strip():
            return True
    if caps.pypdf:
        try:
            import pypdf

            reader = pypdf.PdfReader(str(path))
            for page in reader.pages[:3]:
                if (page.extract_text() or "").strip():
                    return False
            return len(reader.pages) > 0
        except Exception:
            return False
    return False


def _pages_from_pdftotext(text: str) -> list[PageRecord]:
    pages: list[PageRecord] = []
    for idx, part in enumerate(text.split("\f"), start=1):
        part = part.strip("\n")
        pages.append(
            PageRecord(
                page=idx,
                text=part,
                confidence="high" if part.strip() else "low",
                warnings=[] if part.strip() else ["empty_page_text"],
            )
        )
    return pages


def _looks_interleaved_weld(text: str) -> bool:
    # Classic -layout weld: end of left column jammed into right column header.
    return bool(
        re.search(r"\w\.\s+COLUMN\b", text)
        or re.search(r"fruit\.\s*COLUMN", text, re.IGNORECASE)
        or re.search(r"\w{3,}\.\s+[A-Z]{2,}\s+COLUMN\b", text)
    )


def _multicolumn_assessment(
    path: Path,
) -> tuple[bool, str, list[PageRecord] | None]:
    layout = _pdftotext(path, "layout") or ""
    raw = _pdftotext(path, "raw") or ""
    if not layout.strip() or not raw.strip():
        return False, "", None
    raw_pages = _pages_from_pdftotext(raw)
    if _looks_interleaved_weld(layout):
        return (
            True,
            "multicolumn_layout_weld_detected_in_pdftotext_layout",
            raw_pages,
        )
    lay_tokens = _WS.sub(" ", layout).split()
    raw_tokens = _WS.sub(" ", raw).split()
    if not lay_tokens or not raw_tokens:
        return False, "", None

    def bigrams(tokens: list[str]) -> set[tuple[str, str]]:
        return set(zip(tokens, tokens[1:])) if len(tokens) > 1 else set()

    a, b = bigrams(lay_tokens), bigrams(raw_tokens)
    if not a or not b:
        return False, "", None
    inter = len(a & b)
    union = len(a | b)
    jaccard = inter / union if union else 1.0
    if jaccard < 0.55:
        return (
            True,
            "possible_multicolumn_or_reading_order_mismatch:"
            f"layout_vs_raw_jaccard={jaccard:.2f}",
            raw_pages,
        )
    return False, "", None

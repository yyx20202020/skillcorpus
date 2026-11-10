"""Detect optional backends; never silently claim success without them."""

from __future__ import annotations

import importlib.util
import shutil
from dataclasses import dataclass


@dataclass(frozen=True)
class Capabilities:
    pypdf: bool
    pdftotext: bool
    pdfinfo: bool
    ocrmypdf: bool
    tesseract: bool

    def report(self) -> dict[str, bool | str]:
        ocr_status = "available" if self.ocrmypdf else "unsupported_in_this_environment"
        return {
            "pypdf": self.pypdf,
            "pdftotext": self.pdftotext,
            "pdfinfo": self.pdfinfo,
            "ocrmypdf": self.ocrmypdf,
            "tesseract": self.tesseract,
            "ocr_pipeline": ocr_status,
            "note": (
                "OCR is only attempted when --ocr is passed AND ocrmypdf is installed. "
                "If ocrmypdf is missing, SkillCorpus reports unsupported rather than faking OCR."
            ),
        }


def detect_capabilities() -> Capabilities:
    return Capabilities(
        pypdf=importlib.util.find_spec("pypdf") is not None,
        pdftotext=shutil.which("pdftotext") is not None,
        pdfinfo=shutil.which("pdfinfo") is not None,
        ocrmypdf=shutil.which("ocrmypdf") is not None,
        tesseract=shutil.which("tesseract") is not None,
    )

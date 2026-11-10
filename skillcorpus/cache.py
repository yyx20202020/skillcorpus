"""Integrity-checked extraction workspace with optional reuse (not chapter-incremental)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from skillcorpus.errors import IntegrityError
from skillcorpus.hashing import sha256_file, sha256_json, sha256_text
from skillcorpus.security import atomic_write_text, assert_safe_output_dir


class WorkCache:
    """Per-run work directory.

    Reuse is allowed only when *all* of the following hold:
    - metadata/full_text/pages/chunks exist and hashes match
    - recorded source path+sha256 list equals the current inputs (order-sensitive)
    - recorded ocr flag equals the current request

    This is **not** chapter-level incremental caching across partial source edits.
    """

    def __init__(self, root: Path) -> None:
        self.root = assert_safe_output_dir(root)
        self.extract_dir = self.root / "extract"
        self.extract_dir.mkdir(exist_ok=True)

    def clear_evidence(self) -> None:
        """Invalidate all extracted evidence before writing a new corpus."""
        for name in ("full_text.txt", "metadata.json", "pages.json", "chunks.json"):
            path = self.extract_dir / name
            if path.exists() or path.is_symlink():
                if path.is_dir() and not path.is_symlink():
                    shutil.rmtree(path)
                else:
                    path.unlink()

    def write_extraction(
        self,
        *,
        full_text: str,
        metadata: dict[str, Any],
        pages: list[dict[str, Any]],
        chunks: list[dict[str, Any]],
    ) -> dict[str, str]:
        self.clear_evidence()
        meta = dict(metadata)
        meta["full_text_sha256"] = sha256_text(full_text)
        meta["pages_sha256"] = sha256_json(pages)
        meta["chunks_sha256"] = sha256_json(chunks)
        atomic_write_text(self.extract_dir / "full_text.txt", full_text)
        atomic_write_text(
            self.extract_dir / "metadata.json",
            json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
        )
        atomic_write_text(
            self.extract_dir / "pages.json",
            json.dumps(pages, indent=2, ensure_ascii=False) + "\n",
        )
        atomic_write_text(
            self.extract_dir / "chunks.json",
            json.dumps(chunks, indent=2, ensure_ascii=False) + "\n",
        )
        return {
            "full_text_sha256": meta["full_text_sha256"],
            "pages_sha256": meta["pages_sha256"],
            "chunks_sha256": meta["chunks_sha256"],
        }

    def verify_or_raise(self) -> dict[str, Any]:
        meta_path = self.extract_dir / "metadata.json"
        text_path = self.extract_dir / "full_text.txt"
        pages_path = self.extract_dir / "pages.json"
        chunks_path = self.extract_dir / "chunks.json"
        for path in (meta_path, text_path, pages_path, chunks_path):
            if not path.is_file():
                raise IntegrityError(f"Missing extraction artifact: {path.name}")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        text = text_path.read_text(encoding="utf-8")
        if not text.strip():
            raise IntegrityError("full_text.txt is empty — refusing dirty cache reuse")
        pages = json.loads(pages_path.read_text(encoding="utf-8"))
        chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
        if meta.get("full_text_sha256") != sha256_text(text):
            raise IntegrityError("full_text.txt hash mismatch — dirty or tampered cache")
        if meta.get("pages_sha256") != sha256_json(pages):
            raise IntegrityError("pages.json hash mismatch — dirty or tampered cache")
        if meta.get("chunks_sha256") != sha256_json(chunks):
            raise IntegrityError("chunks.json hash mismatch — dirty or tampered cache")
        return {
            "metadata": meta,
            "full_text": text,
            "pages": pages,
            "chunks": chunks,
            "artifact_hashes": {
                "full_text": sha256_file(text_path),
                "metadata": sha256_file(meta_path),
                "pages": sha256_file(pages_path),
                "chunks": sha256_file(chunks_path),
            },
        }

    def try_reuse(
        self,
        *,
        source_fingerprints: list[tuple[str, str]],
        ocr: bool,
    ) -> dict[str, Any] | None:
        """Return verified cache payload if reusable for these inputs, else None.

        ``source_fingerprints`` is an ordered list of ``(resolved_path, sha256)``.
        """
        try:
            payload = self.verify_or_raise()
        except IntegrityError:
            return None
        meta = payload["metadata"]
        if bool(meta.get("ocr")) != bool(ocr):
            return None
        recorded = meta.get("sources") or []
        if len(recorded) != len(source_fingerprints):
            return None
        for rec, (path, digest) in zip(recorded, source_fingerprints, strict=True):
            if rec.get("path") != path or rec.get("sha256") != digest:
                return None
        payload["reused"] = True
        return payload

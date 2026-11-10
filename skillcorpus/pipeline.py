"""End-to-end: extract → segment → cache (reuse-or-rewrite) → transactional pack."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from skillcorpus.cache import WorkCache
from skillcorpus.extractors import extract_path
from skillcorpus.hashing import sha256_file
from skillcorpus.models import Chunk, ExtractedDocument, PageRecord
from skillcorpus.pack import pack_skill
from skillcorpus.segment import segment_document
from skillcorpus.security import assert_safe_output_dir, assert_source_readable
from skillcorpus.validate import validate_skill


def build_pack(
    sources: list[Path],
    output_dir: Path,
    *,
    work_dir: Path | None = None,
    skill_name: str | None = None,
    ocr: bool = False,
    harden: bool = False,
) -> dict[str, Any]:
    if not sources:
        from skillcorpus.errors import SkillCorpusError

        raise SkillCorpusError("No source files provided")

    out = assert_safe_output_dir(output_dir)
    # Keep work outside the pack swap surface when using default location.
    work = WorkCache(work_dir or (out / ".work"))

    resolved: list[Path] = []
    fingerprints: list[tuple[str, str]] = []
    for src in sources:
        path = assert_source_readable(src)
        resolved.append(path)
        fingerprints.append((str(path.resolve()), sha256_file(path)))

    reused = False
    cached = work.try_reuse(source_fingerprints=fingerprints, ocr=ocr)
    docs: list[ExtractedDocument]
    chunks: list[Chunk]
    warnings: list[str]
    hashes: dict[str, str]

    if cached is not None:
        reused = True
        docs, chunks, warnings = _hydrate_from_cache(cached)
        hashes = {
            "full_text_sha256": cached["metadata"]["full_text_sha256"],
            "pages_sha256": cached["metadata"]["pages_sha256"],
            "chunks_sha256": cached["metadata"]["chunks_sha256"],
        }
    else:
        docs = []
        chunks = []
        warnings = []
        for path in resolved:
            doc = extract_path(path, ocr=ocr)
            docs.append(doc)
            warnings.extend(doc.warnings)
            if doc.structure_degraded:
                warnings.append(
                    f"structure_degraded:{path.name} — pack succeeded with LOW confidence"
                )
            chunks.extend(segment_document(doc))

        meta = {
            "sources": [
                {
                    "path": d.source_path,
                    "sha256": d.source_sha256,
                    "source_id": d.source_id,
                    "format": d.format,
                    "method": d.extraction_method,
                    "title": d.title,
                    "structure_degraded": d.structure_degraded,
                    "warnings": d.warnings,
                    "removed_invisible": d.removed_invisible,
                    "page_count": len(d.pages),
                }
                for d in docs
            ],
            "source_sha256": docs[0].source_sha256 if len(docs) == 1 else None,
            "ocr": ocr,
            "warnings": warnings,
        }
        pages = []
        for d in docs:
            for p in d.pages:
                rec = p.to_dict()
                rec["source_id"] = d.source_id
                if d.structure_degraded and "structure_degraded" not in rec["warnings"]:
                    rec["warnings"].append("structure_degraded")
                    rec["confidence"] = "low"
                pages.append(rec)

        full_text = "\n\n".join(
            f"===== SOURCE {d.source_id} ({d.title}) =====\n{d.text}" for d in docs
        )
        hashes = work.write_extraction(
            full_text=full_text,
            metadata=meta,
            pages=pages,
            chunks=[c.to_dict() for c in chunks],
        )
        work.verify_or_raise()

    # Pack is transactional: failure here must not destroy a prior valid pack.
    pack_info = pack_skill(
        docs=docs,
        chunks=chunks,
        output_dir=out,
        skill_name=skill_name,
        harden=harden,
        structure_warnings=warnings,
    )
    validation = validate_skill(out)
    return {
        **pack_info,
        "extraction_hashes": hashes,
        "validation": validation,
        "work_dir": str(work.root),
        "sources": [d.source_path for d in docs],
        "structure_degraded": any(d.structure_degraded for d in docs),
        "cache_reused": reused,
        "cache_mode": "integrity_reuse_full_extract" if reused else "fresh_extract",
        "cache_note": (
            "Reuse applies only to an intact prior full extraction for identical "
            "source path+sha256+ocr. Not chapter-level incremental caching."
        ),
    }


def _hydrate_from_cache(
    cached: dict[str, Any],
) -> tuple[list[ExtractedDocument], list[Chunk], list[str]]:
    meta = cached["metadata"]
    pages_by_source: dict[str, list[PageRecord]] = {}
    for rec in cached["pages"]:
        sid = rec.get("source_id") or ""
        pages_by_source.setdefault(sid, []).append(
            PageRecord(
                page=rec.get("page"),
                text=rec.get("text") or "",
                confidence=rec.get("confidence") or "unknown",
                warnings=list(rec.get("warnings") or []),
            )
        )

    docs: list[ExtractedDocument] = []
    # Rebuild per-source text from page records when possible.
    full = cached["full_text"]
    for src in meta.get("sources") or []:
        sid = src["source_id"]
        marker = f"===== SOURCE {sid} ("
        start = full.find(marker)
        text = ""
        if start != -1:
            after = full.find("\n", start)
            end = full.find("\n===== SOURCE ", after)
            text = full[after + 1 :] if end == -1 else full[after + 1 : end]
            text = text.strip("\n")
        docs.append(
            ExtractedDocument(
                source_path=src["path"],
                source_id=sid,
                source_sha256=src["sha256"],
                format=src.get("format") or "unknown",
                title=src.get("title") or Path(src["path"]).stem,
                text=text,
                pages=pages_by_source.get(sid) or [PageRecord(page=None, text=text)],
                extraction_method=src.get("method") or "cache_reuse",
                warnings=list(src.get("warnings") or []),
                removed_invisible=int(src.get("removed_invisible") or 0),
                structure_degraded=bool(src.get("structure_degraded")),
            )
        )

    chunks = [
        Chunk(
            chunk_id=c["chunk_id"],
            source_id=c["source_id"],
            title=c.get("title") or "",
            text=c.get("text") or "",
            page_start=c.get("page_start"),
            page_end=c.get("page_end"),
            char_start=int(c.get("char_start") or 0),
            char_end=int(c.get("char_end") or 0),
            heading_path=list(c.get("heading_path") or []),
            sha256=c.get("sha256") or "",
            warnings=list(c.get("warnings") or []),
        )
        for c in cached["chunks"]
    ]
    warnings = list(meta.get("warnings") or [])
    return docs, chunks, warnings

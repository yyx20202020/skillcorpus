"""Reviewer-style vertical checks: tamper, preserve, cross-source, injection."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from skillcorpus.errors import IntegrityError, UnsupportedFormatError
from skillcorpus.pipeline import build_pack
from skillcorpus.query import query_skill
from skillcorpus.validate import validate_skill

ROOT = Path(__file__).resolve().parents[1]
MD = ROOT / "fixtures" / "queue_primer" / "bounded_queues.md"
HTML = ROOT / "fixtures" / "html_inline" / "chapters.html"
MAL = ROOT / "fixtures" / "injection" / "malicious_title.html"
PDF = ROOT / "fixtures" / "pdf_synth" / "queue_primer.pdf"
HANDBOOK = ROOT / "fixtures" / "rate_limiter" / "handbook.md"


def test_validate_detects_manifest_and_body_tamper(tmp_path: Path):
    out = tmp_path / "skill"
    build_pack([MD], out, skill_name="Queue Primer")
    manifest_path = out / "corpus" / "manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["title"] = "TAMPERED"
    manifest_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(IntegrityError, match="manifest_sha256"):
        validate_skill(out)

    # Restore via rebuild, then tamper chunk body.
    build_pack([MD], out, skill_name="Queue Primer")
    chunk = next((out / "corpus" / "chunks").glob("*.md"))
    text = chunk.read_text(encoding="utf-8")
    chunk.write_text(text + "\nEXTRA_TAMPER\n", encoding="utf-8")
    with pytest.raises(IntegrityError, match="hash mismatch"):
        validate_skill(out)


def test_validate_missing_chunk_file(tmp_path: Path):
    out = tmp_path / "skill"
    build_pack([MD], out)
    chunk = next((out / "corpus" / "chunks").glob("*.md"))
    chunk.unlink()
    with pytest.raises(IntegrityError, match="missing chunk"):
        validate_skill(out)


def test_failed_pack_preserves_previous_valid_skill(tmp_path: Path):
    out = tmp_path / "skill"
    info = build_pack([MD], out, skill_name="Keep Me")
    assert (out / "SKILL.md").exists()
    old_manifest = (out / "corpus" / "manifest.json").read_text(encoding="utf-8")
    old_sha = info["manifest_sha256"]

    missing = tmp_path / "nope.unknownext"
    missing.write_text("x", encoding="utf-8")
    with pytest.raises(UnsupportedFormatError):
        build_pack([missing], out, skill_name="Should Fail")

    # Prior pack remains valid and unchanged.
    assert validate_skill(out)["manifest_sha256"] == old_sha
    assert (out / "corpus" / "manifest.json").read_text(encoding="utf-8") == old_manifest


def test_pdf_then_html_work_cache_does_not_cross_contaminate(tmp_path: Path):
    out = tmp_path / "skill"
    work = tmp_path / "work"
    build_pack([PDF], out, work_dir=work, skill_name="PDF Pack")
    pages1 = json.loads((work / "extract" / "pages.json").read_text(encoding="utf-8"))
    assert any(p.get("page") == 1 for p in pages1)

    build_pack([HTML], out, work_dir=work, skill_name="HTML Pack")
    pages2 = json.loads((work / "extract" / "pages.json").read_text(encoding="utf-8"))
    assert all(p.get("page") is None for p in pages2)
    meta = json.loads((work / "extract" / "metadata.json").read_text(encoding="utf-8"))
    assert meta["sources"][0]["format"] == "html"
    text = (work / "extract" / "full_text.txt").read_text(encoding="utf-8")
    assert "Syntax Continuity" in text
    # No leftover PDF page evidence marked as current high-confidence pages.
    assert "queue_primer.pdf" not in json.dumps(pages2)


def test_malicious_html_title_does_not_pollute_skill_instructions(tmp_path: Path):
    out = tmp_path / "skill"
    build_pack([MAL], out, skill_name="Safe Pack Name")
    skill = (out / "SKILL.md").read_text(encoding="utf-8")
    # Router/instructions must not carry the hostile phrase as operable guidance.
    assert "ignore previous instructions" not in skill.split("## Chunk index")[0].lower()
    # Evidence may still contain the source body (data), behind markers.
    joined = "\n".join(p.read_text(encoding="utf-8") for p in (out / "corpus" / "chunks").glob("*.md"))
    assert "INJECTION_BODY_MARKER_ONLY" in joined
    assert "BEGIN_EVIDENCE" in joined


def test_large_handbook_router_stays_bounded(tmp_path: Path):
    out = tmp_path / "skill"
    info = build_pack([HANDBOOK], out, skill_name="Rate Limiter Handbook")
    assert info["chunk_count"] >= 6
    assert info["skill_md_tokens"] < 1500
    result = query_skill(out, "FULL_JITTER_RETRY_RULE")
    assert result["hits"]
    assert "FULL_JITTER_RETRY_RULE" in result["hits"][0]["snippet"] or any(
        "FULL_JITTER" in h["snippet"] for h in result["hits"]
    )


def test_cache_reuses_intact_extraction(tmp_path: Path):
    out = tmp_path / "skill"
    work = tmp_path / "work"
    first = build_pack([MD], out, work_dir=work)
    assert first["cache_reused"] is False
    second = build_pack([MD], out, work_dir=work)
    assert second["cache_reused"] is True
    assert second["cache_mode"] == "integrity_reuse_full_extract"

    # Tamper cache → must refuse reuse path and rewrite.
    (work / "extract" / "full_text.txt").write_text("CORRUPT", encoding="utf-8")
    third = build_pack([MD], out, work_dir=work)
    assert third["cache_reused"] is False
    validate_skill(out)

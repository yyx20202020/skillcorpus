from pathlib import Path

import pytest

from skillcorpus.errors import SecurityError
from skillcorpus.pipeline import build_pack
from skillcorpus.query import query_skill
from skillcorpus.validate import validate_skill

ROOT = Path(__file__).resolve().parents[1]
MD = ROOT / "fixtures" / "queue_primer" / "bounded_queues.md"
INJECT = ROOT / "fixtures" / "injection" / "ignore_previous.md"


def test_pack_validate_query_roundtrip(tmp_path: Path):
    out = tmp_path / "skill"
    info = build_pack([MD], out, skill_name="Queue Primer")
    assert info["chunk_count"] >= 5
    assert info["validation"]["ok"] is True
    validate_skill(out)

    result = query_skill(out, "backpressure bounded queue", top_k=2)
    assert result["unsupported"] is False
    assert result["hits"]
    assert "citation" in result["hits"][0]
    assert result["hits"][0]["citation"]["chunk_id"]


def test_query_unsupported(tmp_path: Path):
    out = tmp_path / "skill"
    build_pack([MD], out)
    result = query_skill(out, "quantum entanglement unicorn xerxes", top_k=3)
    assert result["unsupported"] is True


def test_harden_refuses_injection_fixture(tmp_path: Path):
    out = tmp_path / "skill"
    with pytest.raises(SecurityError):
        build_pack([INJECT], out, harden=True)

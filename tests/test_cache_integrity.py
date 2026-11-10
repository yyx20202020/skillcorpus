import json
from pathlib import Path

import pytest

from skillcorpus.cache import WorkCache
from skillcorpus.errors import IntegrityError


def test_cache_rejects_missing_and_tampered(tmp_path: Path):
    cache = WorkCache(tmp_path / "work")
    cache.write_extraction(
        full_text="hello chapter",
        metadata={"sources": []},
        pages=[{"page": 1, "text": "hello chapter"}],
        chunks=[{"chunk_id": "c1", "text": "hello chapter"}],
    )
    cache.verify_or_raise()

    # Tamper full_text without updating metadata hash.
    (cache.extract_dir / "full_text.txt").write_text("TAMPERED", encoding="utf-8")
    with pytest.raises(IntegrityError, match="full_text"):
        cache.verify_or_raise()


def test_cache_clear_removes_stale_pages_sidecar(tmp_path: Path):
    cache = WorkCache(tmp_path / "work")
    cache.write_extraction(
        full_text="pdf text",
        metadata={"sources": [{"path": "a.pdf", "sha256": "aaa"}]},
        pages=[{"page": 1, "text": "pdf text", "source_id": "pdf"}],
        chunks=[],
    )
    assert (cache.extract_dir / "pages.json").exists()

    # Second write for markdown must not leave old pages content unaccounted.
    cache.write_extraction(
        full_text="md text",
        metadata={"sources": [{"path": "a.md", "sha256": "bbb"}]},
        pages=[{"page": None, "text": "md text", "source_id": "md"}],
        chunks=[],
    )
    pages = json.loads((cache.extract_dir / "pages.json").read_text(encoding="utf-8"))
    assert pages[0]["source_id"] == "md"
    assert "pdf" not in json.dumps(pages)
    cache.verify_or_raise()

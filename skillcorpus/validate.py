"""Validate a packed skill's integrity and basic shape."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from skillcorpus.errors import IntegrityError
from skillcorpus.hashing import sha256_file, sha256_json, sha256_text


def validate_skill(skill_dir: Path) -> dict[str, Any]:
    skill_dir = skill_dir.resolve()
    skill_md = skill_dir / "SKILL.md"
    manifest_path = skill_dir / "corpus" / "manifest.json"
    if not skill_md.is_file():
        raise IntegrityError("SKILL.md missing")
    if not manifest_path.is_file():
        raise IntegrityError("corpus/manifest.json missing")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    stored = manifest.get("manifest_sha256")
    recomputed = sha256_json(
        {k: v for k, v in manifest.items() if k != "manifest_sha256"}
    )
    if stored != recomputed:
        raise IntegrityError("manifest_sha256 mismatch — pack may be tampered")

    problems: list[str] = []
    for chunk in manifest.get("chunks", []):
        rel = chunk.get("path")
        if not rel:
            problems.append(f"{chunk.get('chunk_id')}: missing path")
            continue
        path = skill_dir / "corpus" / rel
        if not path.is_file():
            problems.append(f"missing chunk file: {rel}")
            continue
        if chunk.get("file_sha256") and chunk["file_sha256"] != sha256_file(path):
            problems.append(f"file hash mismatch: {rel}")
        body = path.read_text(encoding="utf-8")
        # Evidence hash is over raw chunk text stored in manifest field sha256.
        # Re-extract between markers when present.
        evidence = _extract_evidence(body)
        if chunk.get("sha256") and sha256_text(evidence) != chunk["sha256"]:
            problems.append(f"evidence hash mismatch: {rel}")
        if "chunk_id:" not in body or "BEGIN_EVIDENCE" not in body:
            problems.append(f"chunk missing citation markers: {rel}")

    if problems:
        raise IntegrityError("validation failed:\n- " + "\n- ".join(problems))

    return {
        "ok": True,
        "skill_dir": str(skill_dir),
        "chunk_count": len(manifest.get("chunks", [])),
        "manifest_sha256": stored,
        "sources": len(manifest.get("sources", [])),
        "warnings": manifest.get("warnings", []),
    }


def _extract_evidence(body: str) -> str:
    start = body.find("<!-- BEGIN_EVIDENCE")
    end = body.find("<!-- END_EVIDENCE")
    if start == -1 or end == -1 or end <= start:
        # Fall back: strip HTML comments / heading for best-effort.
        lines = [
            ln
            for ln in body.splitlines()
            if not ln.startswith("#")
            and not ln.startswith("<!--")
            and not ln.startswith("**Citation:**")
        ]
        return "\n".join(lines).strip()
    # Skip the start comment line.
    after = body.find("\n", start)
    region = body[after + 1 : end]
    return region.strip()

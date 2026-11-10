"""Path safety, size limits, and advisory injection heuristics."""

from __future__ import annotations

import os
import re
import stat
from pathlib import Path

from skillcorpus.errors import SecurityError

# Soft defaults for local conversion of user-owned docs.
DEFAULT_MAX_SOURCE_BYTES = 40 * 1024 * 1024  # 40 MiB
DEFAULT_MAX_TOTAL_BYTES = 80 * 1024 * 1024
DEFAULT_MAX_FILES = 200

_INJECTION_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "prompt.ignore_previous",
        re.compile(
            r"\bignore\s+(?:(?:all|any|the)\s+)?(?:previous|prior)\s+"
            r"(?:instructions?|prompts?|rules?|messages?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "prompt.disregard_system",
        re.compile(r"\bdisregard\s+(?:the\s+)?(?:system|developer)\b", re.IGNORECASE),
    ),
    (
        "prompt.role_reassignment",
        re.compile(r"\byou\s+are\s+now\b", re.IGNORECASE),
    ),
    (
        "prompt.system_tag",
        re.compile(r"<\s*/?\s*system\b[^>]*>", re.IGNORECASE),
    ),
)


def resolve_under(base: Path, candidate: Path) -> Path:
    """Resolve candidate and ensure it stays under base (no traversal)."""
    base_r = base.resolve()
    cand_r = candidate.resolve()
    try:
        cand_r.relative_to(base_r)
    except ValueError as exc:
        raise SecurityError(
            f"Refusing path outside allowed root: {candidate}"
        ) from exc
    return cand_r


def assert_safe_output_dir(path: Path) -> Path:
    """Create or reuse an output directory with basic symlink/ownership checks."""
    if path.exists() and path.is_symlink():
        raise SecurityError(
            f"Refusing output path that is a symbolic link: {path}"
        )
    if path.exists() and not path.is_dir():
        raise SecurityError(f"Output path exists and is not a directory: {path}")
    if not path.exists():
        path.mkdir(parents=True, mode=0o700)
    else:
        if hasattr(os, "getuid"):
            if path.stat().st_uid != os.getuid():
                raise SecurityError(
                    f"Refusing output directory owned by another user: {path}"
                )
            os.chmod(path, 0o700)
    # Re-check after create.
    if path.is_symlink():
        raise SecurityError(f"Refusing symlinked output directory: {path}")
    return path.resolve()


def assert_source_readable(path: Path, max_bytes: int = DEFAULT_MAX_SOURCE_BYTES) -> Path:
    if not path.exists():
        raise SecurityError(f"Source not found: {path}")
    if path.is_symlink():
        # Allow reading through symlink to a regular file, but resolve first.
        resolved = path.resolve()
        if not resolved.is_file():
            raise SecurityError(f"Source symlink does not point to a file: {path}")
        path = resolved
    if not path.is_file():
        raise SecurityError(f"Source is not a regular file: {path}")
    size = path.stat().st_size
    if size > max_bytes:
        raise SecurityError(
            f"Source exceeds size limit ({size} > {max_bytes} bytes): {path.name}"
        )
    mode = path.stat().st_mode
    if not stat.S_ISREG(mode):
        raise SecurityError(f"Source is not a regular file: {path}")
    return path


def scan_injection_phrases(text: str) -> list[dict[str, str]]:
    """Advisory scan. Does not prove absence of prompt injection."""
    findings: list[dict[str, str]] = []
    for rule_id, pattern in _INJECTION_RULES:
        if pattern.search(text):
            findings.append(
                {
                    "rule": rule_id,
                    "note": "heuristic match; review manually — not a complete defense",
                }
            )
    return findings


def atomic_write_text(path: Path, text: str, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with tmp.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        os.chmod(path, mode)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def atomic_write_bytes(path: Path, data: bytes, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with tmp.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        os.chmod(path, mode)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)

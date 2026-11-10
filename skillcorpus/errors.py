"""Typed failures for the CLI and library callers."""

from __future__ import annotations


class SkillCorpusError(Exception):
    """Base error; message is safe to show to users."""


class UnsupportedFormatError(SkillCorpusError):
    pass


class ExtractionError(SkillCorpusError):
    pass


class IntegrityError(SkillCorpusError):
    pass


class SecurityError(SkillCorpusError):
    pass


class CapabilityError(SkillCorpusError):
    """Requested backend is unavailable or opted-out."""

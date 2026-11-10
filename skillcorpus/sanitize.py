"""Strip invisible / tag-block Unicode from untrusted document text.

Source documents are treated as data, never as executable instructions.
Sanitization removes common prompt-injection spacers; it does not claim to
block all injection strategies.
"""

from __future__ import annotations

import unicodedata
import re

# Zero-width / word-joiner / BOM family commonly used as injection spacers.
_INVISIBLE = {
    0x200B,
    0x200C,
    0x200D,
    0x2060,
    0xFEFF,
}

# Kangxi radicals that often appear when PDF fonts lack proper Unicode maps.
_KANGXI = re.compile("[\u2f00-\u2fdf]")


def sanitize_text(text: str) -> tuple[str, int]:
    """Return (cleaned_text, removed_invisible_count)."""
    removed = 0
    out: list[str] = []
    for ch in text:
        cp = ord(ch)
        if cp in _INVISIBLE or 0xE0000 <= cp <= 0xE007F:
            removed += 1
            continue
        if _KANGXI.match(ch):
            out.append(unicodedata.normalize("NFKC", ch))
        else:
            out.append(ch)
    cleaned = "".join(out)
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    return cleaned, removed

"""Token counting for benchmarks — measured, never a design-cap stand-in."""

from __future__ import annotations

import re

# Approximate whitespace tokenizer used ONLY when no better option exists.
# Benchmarks must label which method was used.
_WORD = re.compile(r"\S+")


def count_tokens(text: str) -> tuple[int, str]:
    """Return (count, method_label).

    Prefer tiktoken cl100k_base when installed; otherwise a documented
    whitespace heuristic. Callers must surface the method in reports.
    """
    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text)), "tiktoken_cl100k_base"
    except Exception:
        return len(_WORD.findall(text)), "whitespace_tokens_heuristic"

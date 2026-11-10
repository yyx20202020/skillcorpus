"""Explainable keyword retrieval over a packed skill."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from skillcorpus.errors import IntegrityError
from skillcorpus.tokens import count_tokens
from skillcorpus.validate import validate_skill

_LATIN = re.compile(r"[a-z0-9_]+", re.IGNORECASE)
_CJK_RUN = re.compile(r"[\u4e00-\u9fff]+")


@dataclass
class Hit:
    chunk_id: str
    title: str
    score: float
    page_start: int | None
    page_end: int | None
    snippet: str
    path: str
    matched_terms: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "title": self.title,
            "score": self.score,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "snippet": self.snippet,
            "path": self.path,
            "matched_terms": self.matched_terms,
            "citation": {
                "chunk_id": self.chunk_id,
                "page_start": self.page_start,
                "page_end": self.page_end,
            },
        }


def tokenize(text: str) -> list[str]:
    """Latin words + CJK overlapping bigrams (and unigrams for short runs)."""
    terms: list[str] = [t.lower() for t in _LATIN.findall(text)]
    for run in _CJK_RUN.findall(text):
        if len(run) == 1:
            terms.append(run)
            continue
        # Prefer bigrams for recall on space-less Chinese queries.
        for i in range(len(run) - 1):
            terms.append(run[i : i + 2])
        if len(run) <= 4:
            terms.append(run)
    return terms


def query_skill(
    skill_dir: Path,
    question: str,
    *,
    top_k: int = 3,
    validate: bool = True,
) -> dict[str, Any]:
    skill_dir = skill_dir.resolve()
    if validate:
        validate_skill(skill_dir)

    manifest = json.loads(
        (skill_dir / "corpus" / "manifest.json").read_text(encoding="utf-8")
    )
    q_terms = tokenize(question)
    if not q_terms:
        raise IntegrityError("Query has no searchable terms")

    hits: list[Hit] = []
    loaded_chars = 0
    for chunk in manifest.get("chunks", []):
        path = skill_dir / "corpus" / chunk["path"]
        text = path.read_text(encoding="utf-8")
        evidence_start = text.find("<!-- BEGIN_EVIDENCE")
        if evidence_start != -1:
            after = text.find("\n", evidence_start)
            end = text.find("<!-- END_EVIDENCE")
            evidence = text[after + 1 : end].strip() if end != -1 else text
        else:
            evidence = text
        loaded_chars += len(evidence)
        terms = tokenize(evidence)
        if not terms:
            continue
        freq: dict[str, int] = {}
        for t in terms:
            freq[t] = freq.get(t, 0) + 1
        matched = [t for t in q_terms if t in freq]
        # Substring fallback for CJK phrases longer than a bigram.
        for t in q_terms:
            if t not in matched and not t.isascii() and t in evidence:
                matched.append(t)
                freq[t] = freq.get(t, 0) + 1
        if not matched:
            continue
        score = sum(1.0 + 0.1 * freq[t] for t in matched) / len(q_terms)
        # Title hit bonus
        title_terms = set(tokenize(chunk.get("title", "")))
        score += 0.25 * sum(1 for t in matched if t in title_terms)
        snippet = _snippet(evidence, matched)
        hits.append(
            Hit(
                chunk_id=chunk["chunk_id"],
                title=chunk.get("title", ""),
                score=round(score, 4),
                page_start=chunk.get("page_start"),
                page_end=chunk.get("page_end"),
                snippet=snippet,
                path=chunk["path"],
                matched_terms=matched,
            )
        )

    hits.sort(key=lambda h: h.score, reverse=True)
    top = hits[:top_k]

    # Token accounting for "skill path": SKILL.md + selected chunks only.
    skill_md = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    selected_text = "\n\n".join(
        (skill_dir / "corpus" / h.path).read_text(encoding="utf-8") for h in top
    )
    skill_tokens, method = count_tokens(skill_md + "\n" + selected_text)
    dump_tokens, dump_method = count_tokens(
        "\n\n".join(
            (skill_dir / "corpus" / c["path"]).read_text(encoding="utf-8")
            for c in manifest.get("chunks", [])
        )
    )
    if method != dump_method:
        # Prefer labeling both if they somehow differ (should not).
        method = f"{method}+{dump_method}"

    return {
        "question": question,
        "hits": [h.to_dict() for h in top],
        "unsupported": len(top) == 0,
        "message": (
            "No supporting chunk found for the query terms."
            if not top
            else "Return answers grounded in the cited snippets only."
        ),
        "token_report": {
            "tokenizer": method,
            "skill_path_tokens": skill_tokens,
            "context_dump_all_chunks_tokens": dump_tokens,
            "comparison": (
                "skill_path = SKILL.md + top-k chunk files; "
                "context_dump = all chunk files concatenated. "
                "This is a local retrieval cost model, not a live LLM trace."
            ),
            "ratio_dump_over_skill": (
                round(dump_tokens / skill_tokens, 2) if skill_tokens else None
            ),
        },
    }


def _snippet(text: str, matched: list[str], radius: int = 110) -> str:
    lower = text.lower()
    positions = []
    for term in matched:
        idx = lower.find(term.lower())
        if idx != -1:
            positions.append(idx)
    if not positions:
        return text[: radius * 2].strip() + ("…" if len(text) > radius * 2 else "")
    at = min(positions)
    start = max(0, at - radius)
    end = min(len(text), at + radius)
    snippet = text[start:end].strip()
    if start > 0:
        snippet = "…" + snippet
    if end < len(text):
        snippet = snippet + "…"
    return snippet

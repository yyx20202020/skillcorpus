"""Reproducible local retrieval/token benchmark (no live LLM calls)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from skillcorpus.query import query_skill
from skillcorpus.tokens import count_tokens
from skillcorpus.validate import validate_skill


def run_benchmark(
    skill_dir: Path,
    questions_path: Path,
) -> dict[str, Any]:
    """Evaluate keyword retrieval + localization on an annotated fixture set.

    Metrics (honest names):
    - ``heading_hit_rate``: share of positive questions where at least one
      ``expected_headings`` substring appears in a hit title (routing signal only).
    - ``evidence_localization_rate``: share where ``evidence_must_contain`` appears
      inside a retrieved hit's evidence body (not title-only).
    - ``no_answer_correct_rate``: share of ``expect_unsupported`` questions that
      correctly return unsupported.
    - Token costs: measured tokenizer; dump = all chunks; skill_path = SKILL+top-k.

    This is **not** LLM answer quality, citation faithfulness of a model, or a
    universal N× savings claim. Presence of source_id/chunk_id alone is never
    treated as support.
    """
    validate_skill(skill_dir)
    payload = json.loads(questions_path.read_text(encoding="utf-8"))
    questions = payload["questions"]

    rows: list[dict[str, Any]] = []
    heading_hits = 0
    heading_total = 0
    evidence_hits = 0
    evidence_total = 0
    noans_ok = 0
    noans_total = 0

    for item in questions:
        qid = item["id"]
        question = item["question"]
        qtype = item.get("type") or "positive"
        expect_unsupported = bool(item.get("expect_unsupported"))
        expected_headings = list(item.get("expected_headings") or [])
        must_contain = list(item.get("evidence_must_contain") or [])
        # Legacy fields intentionally ignored for success scoring.
        legacy_title_shortcut = item.get("expected_chunk_ids_contains")

        result = query_skill(skill_dir, question, top_k=3, validate=False)
        hit_titles = [h["title"] for h in result["hits"]]
        hit_ids = [h["chunk_id"] for h in result["hits"]]
        evidence_blobs = [_hit_evidence(skill_dir, h) for h in result["hits"]]

        heading_ok = None
        if expected_headings:
            heading_total += 1
            heading_ok = any(
                any(eh.lower() in (title or "").lower() for eh in expected_headings)
                for title in hit_titles
            )
            if heading_ok:
                heading_hits += 1

        evidence_ok = None
        if must_contain:
            evidence_total += 1
            evidence_ok = any(
                any(needle in blob for needle in must_contain)
                for blob in evidence_blobs
            )
            if evidence_ok:
                evidence_hits += 1

        noans_ok_flag = None
        if expect_unsupported or qtype == "no_answer":
            noans_total += 1
            noans_ok_flag = bool(result["unsupported"])
            if noans_ok_flag:
                noans_ok += 1

        rows.append(
            {
                "id": qid,
                "type": qtype,
                "question": question,
                "expected_headings": expected_headings,
                "evidence_must_contain": must_contain,
                "expect_unsupported": expect_unsupported,
                "hit_chunk_ids": hit_ids,
                "hit_titles": hit_titles,
                "heading_hit": heading_ok,
                "evidence_localized": evidence_ok,
                "no_answer_correct": noans_ok_flag,
                "unsupported": result["unsupported"],
                "legacy_title_shortcut_ignored": legacy_title_shortcut,
                "token_report": result["token_report"],
            }
        )

    dump_vals = [r["token_report"]["context_dump_all_chunks_tokens"] for r in rows]
    skill_vals = [r["token_report"]["skill_path_tokens"] for r in rows]
    tokenizer = rows[0]["token_report"]["tokenizer"] if rows else count_tokens("")[1]
    mean_dump = sum(dump_vals) / len(dump_vals) if dump_vals else 0
    mean_skill = sum(skill_vals) / len(skill_vals) if skill_vals else 0

    return {
        "skill_dir": str(skill_dir.resolve()),
        "questions_path": str(questions_path.resolve()),
        "dataset": payload.get("dataset"),
        "question_count": len(questions),
        "heading_hit_rate": _rate(heading_hits, heading_total),
        "evidence_localization_rate": _rate(evidence_hits, evidence_total),
        "no_answer_correct_rate": _rate(noans_ok, noans_total),
        "counts": {
            "heading_hit": heading_hits,
            "heading_total": heading_total,
            "evidence_localized": evidence_hits,
            "evidence_total": evidence_total,
            "no_answer_correct": noans_ok,
            "no_answer_total": noans_total,
        },
        "tokenizer": tokenizer,
        "mean_context_dump_tokens": round(mean_dump, 1),
        "mean_skill_path_tokens": round(mean_skill, 1),
        "mean_dump_over_skill_ratio": (
            round(mean_dump / mean_skill, 2) if mean_skill else None
        ),
        "scope": {
            "compares": "all-chunk dump vs SKILL.md+top-k retrieval",
            "measures": [
                "keyword heading hit (routing)",
                "evidence substring localization in hit body",
                "no-answer unsupported correctness",
                "measured token counts",
            ],
            "does_not_claim": [
                "LLM answer quality",
                "universal 20-50x savings",
                "design-cap token sizes",
                "title-only match as citation support",
                "source_id/chunk_id presence as answer quality",
            ],
            "fixture_only": True,
            "not_representative_of_all_books": True,
        },
        "rows": rows,
    }


def _rate(num: int, den: int) -> float | None:
    if den == 0:
        return None
    return round(num / den, 3)


def _hit_evidence(skill_dir: Path, hit: dict[str, Any]) -> str:
    path = skill_dir / "corpus" / hit["path"]
    text = path.read_text(encoding="utf-8")
    start = text.find("<!-- BEGIN_EVIDENCE")
    end = text.find("<!-- END_EVIDENCE")
    if start == -1 or end == -1 or end <= start:
        return text
    after = text.find("\n", start)
    return text[after + 1 : end].strip()

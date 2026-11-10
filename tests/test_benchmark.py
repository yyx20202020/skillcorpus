from pathlib import Path

from skillcorpus.benchmark import run_benchmark
from skillcorpus.pipeline import build_pack

ROOT = Path(__file__).resolve().parents[1]
MD = ROOT / "fixtures" / "queue_primer" / "bounded_queues.md"
HANDBOOK = ROOT / "fixtures" / "rate_limiter" / "handbook.md"
Q_QUEUE = ROOT / "fixtures" / "questions" / "queue_primer.json"
Q_RATE = ROOT / "fixtures" / "questions" / "rate_limiter.json"


def test_queue_primer_evidence_localization(tmp_path: Path):
    out = tmp_path / "skill"
    build_pack([MD], out, skill_name="Queue Primer")
    report = run_benchmark(out, Q_QUEUE)
    assert report["evidence_localization_rate"] is not None
    assert report["evidence_localization_rate"] >= 0.8
    assert report["no_answer_correct_rate"] == 1.0
    assert "citation_support_rate" not in report
    assert report["scope"]["not_representative_of_all_books"] is True
    assert "title-only match as citation support" in report["scope"]["does_not_claim"]


def test_rate_limiter_multichapter_benchmark(tmp_path: Path):
    out = tmp_path / "skill"
    build_pack([HANDBOOK], out, skill_name="Rate Limiter Handbook")
    report = run_benchmark(out, Q_RATE)
    assert report["question_count"] == 12
    assert report["heading_hit_rate"] >= 0.8
    assert report["evidence_localization_rate"] >= 0.8
    assert report["no_answer_correct_rate"] == 1.0
    assert report["mean_skill_path_tokens"] > 0
    assert report["mean_context_dump_tokens"] >= report["mean_skill_path_tokens"]

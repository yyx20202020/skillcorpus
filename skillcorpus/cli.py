"""SkillCorpus command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from skillcorpus import __version__
from skillcorpus.capabilities import detect_capabilities
from skillcorpus.errors import SkillCorpusError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="skillcorpus",
        description=(
            "Evidence-first local converter: documents → citable Agent Skill packs. "
            "No network upload; source text is treated as untrusted data."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_doctor = sub.add_parser("doctor", help="Show backend capabilities")
    p_doctor.set_defaults(func=cmd_doctor)

    p_pack = sub.add_parser("pack", help="Extract sources and pack an evidence skill")
    p_pack.add_argument("sources", nargs="+", type=Path, help="Source files (.md/.txt/.html/.pdf)")
    p_pack.add_argument(
        "-o",
        "--output",
        type=Path,
        required=True,
        help="Output skill directory (created/replaced safely)",
    )
    p_pack.add_argument("--name", type=str, default=None, help="Skill title/slug seed")
    p_pack.add_argument(
        "--work-dir",
        type=Path,
        default=None,
        help="Extraction work directory (default: <output>/.work)",
    )
    p_pack.add_argument(
        "--ocr",
        action="store_true",
        help="Request OCR via ocrmypdf (fails clearly if unavailable)",
    )
    p_pack.add_argument(
        "--harden",
        action="store_true",
        help="Refuse pack when advisory injection heuristics match",
    )
    p_pack.set_defaults(func=cmd_pack)

    p_val = sub.add_parser("validate", help="Validate skill integrity hashes")
    p_val.add_argument("skill_dir", type=Path)
    p_val.set_defaults(func=cmd_validate)

    p_query = sub.add_parser("query", help="Keyword retrieval with citations")
    p_query.add_argument("--skill", type=Path, required=True)
    p_query.add_argument("question", type=str)
    p_query.add_argument("--top-k", type=int, default=3)
    p_query.add_argument("--json", action="store_true")
    p_query.set_defaults(func=cmd_query)

    p_bench = sub.add_parser(
        "benchmark",
        help="Run fixture token/citation benchmark (no live LLM)",
    )
    p_bench.add_argument("--skill", type=Path, required=True)
    p_bench.add_argument("--questions", type=Path, required=True)
    p_bench.add_argument("--json", action="store_true")
    p_bench.set_defaults(func=cmd_benchmark)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except SkillCorpusError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


def cmd_doctor(_args: argparse.Namespace) -> int:
    report = detect_capabilities().report()
    print(json.dumps(report, indent=2))
    return 0


def cmd_pack(args: argparse.Namespace) -> int:
    from skillcorpus.pipeline import build_pack

    info = build_pack(
        list(args.sources),
        args.output,
        work_dir=args.work_dir,
        skill_name=args.name,
        ocr=args.ocr,
        harden=args.harden,
    )
    print(json.dumps(info, indent=2))
    if info.get("structure_degraded"):
        print(
            "warning: structure_degraded — output marked low-confidence; "
            "do not treat as lossless.",
            file=sys.stderr,
        )
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    from skillcorpus.validate import validate_skill

    result = validate_skill(args.skill_dir)
    print(json.dumps(result, indent=2))
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    from skillcorpus.query import query_skill

    result = query_skill(args.skill, args.question, top_k=args.top_k)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    if result["unsupported"]:
        print("UNSUPPORTED: no cited evidence for that query.")
        return 1
    for hit in result["hits"]:
        cite = hit["citation"]
        pages = ""
        if cite["page_start"] is not None:
            pages = f" pages={cite['page_start']}"
            if cite["page_end"] and cite["page_end"] != cite["page_start"]:
                pages += f"-{cite['page_end']}"
        print(f"[{hit['score']}] {hit['chunk_id']}{pages} — {hit['title']}")
        print(f"  matched: {', '.join(hit['matched_terms'])}")
        print(f"  snippet: {hit['snippet']}")
        print()
    tr = result["token_report"]
    print(
        f"tokens ({tr['tokenizer']}): skill_path={tr['skill_path_tokens']} "
        f"dump={tr['context_dump_all_chunks_tokens']} "
        f"ratio={tr['ratio_dump_over_skill']}"
    )
    print(tr["comparison"])
    return 0


def cmd_benchmark(args: argparse.Namespace) -> int:
    from skillcorpus.benchmark import run_benchmark

    result = run_benchmark(args.skill, args.questions)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(
            f"heading_hit_rate={result['heading_hit_rate']} "
            f"evidence_localization_rate={result['evidence_localization_rate']} "
            f"no_answer_correct_rate={result['no_answer_correct_rate']}"
        )
        print(
            f"tokenizer={result['tokenizer']} "
            f"mean_skill_path={result['mean_skill_path_tokens']} "
            f"mean_dump={result['mean_context_dump_tokens']} "
            f"ratio={result['mean_dump_over_skill_ratio']}"
        )
        print("scope:", json.dumps(result["scope"], ensure_ascii=False))
    # Gate on evidence localization when the set defines such questions.
    loc = result.get("evidence_localization_rate")
    noans = result.get("no_answer_correct_rate")
    if loc is not None and loc < 0.8:
        return 1
    if noans is not None and noans < 1.0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

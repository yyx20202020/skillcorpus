# SkillCorpus

**Evidence-first**, local converter: documents you own → citable Agent Skill packs.

中文上手：[docs/getting-started.zh-CN.md](docs/getting-started.zh-CN.md) · [README.zh-CN.md](README.zh-CN.md)

Version **0.1.1** (publish candidate). Independent MIT implementation. No vendored upstream source. No copyrighted books.

## Install

Python **3.11+**.

```bash
python -m pip install -e ".[dev,pdf]"
skillcorpus doctor
```

Optional system tools: `poppler-utils` (pdftotext), `ocrmypdf` + `tesseract` (only for `--ocr`).

## Quick vertical flow

```bash
skillcorpus pack fixtures/rate_limiter/handbook.md \
  -o /tmp/rate-skill --name "Rate Limiter Handbook"
skillcorpus validate /tmp/rate-skill
skillcorpus query --skill /tmp/rate-skill "FULL_JITTER_RETRY_RULE"
skillcorpus benchmark --skill /tmp/rate-skill \
  --questions fixtures/questions/rate_limiter.json --json
```

## What benchmarks measure (and do not)

| Metric | Meaning |
|--------|---------|
| `heading_hit_rate` | Keyword routing hit on expected headings |
| `evidence_localization_rate` | Annotated anchor found in hit **evidence body** |
| `no_answer_correct_rate` | True-negative questions correctly unsupported |
| token ratio | Measured dump vs SKILL.md+top-k on the fixture |

**Not measured:** LLM answer quality. **Not claimed:** universal 20–50× savings.  
**Not sufficient:** mere presence of `source_id` / `chunk_id`.

There is **no** `citation_support_rate` metric — older title-substring shortcuts are not scored as citation support.

## Supported formats / limits

| Format | Status |
|--------|--------|
| `.md` / `.txt` | Yes |
| `.html` / `.htm` | Yes (inline-safe) |
| `.pdf` text layer | Yes; multi-column may be `structure_degraded` |
| `.pdf` scans | Only with `--ocr` when `ocrmypdf` is installed |
| `.epub` | Yes; zip-slip / DTD / zip-bomb guards |
| DOCX, MOBI, formulas, embeddings, LLM summaries | Not in this release |

**Cache:** full-extract integrity reuse for identical source path+sha256+ocr only. **Not** chapter-level incremental cache.

## Security / privacy

Local only; no upload; no API key for the evidence MVP. Source text is untrusted data. Heuristic injection scans / `--harden` are incomplete by design.

## License

MIT — [LICENSE](LICENSE), [NOTICE](NOTICE).

## Docs

- [docs/getting-started.zh-CN.md](docs/getting-started.zh-CN.md)
- [docs/upstream-audit.md](docs/upstream-audit.md)
- [docs/defect-matrix.md](docs/defect-matrix.md)
- [docs/product-plan.md](docs/product-plan.md)

# SkillCorpus 上手指南（发布候选 0.1.1）

## 安装

```bash
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev,pdf]"
# 可选系统依赖：
#   sudo apt install poppler-utils          # pdftotext
#   sudo apt install ocrmypdf tesseract-ocr # 仅当需要 --ocr
skillcorpus doctor
```

从源码 zip 安装：

```bash
python -m pip install skillcorpus-0.1.1-src.zip
# 或解压后：pip install .
```

## 最小纵向流程

```bash
skillcorpus pack fixtures/rate_limiter/handbook.md \
  -o /tmp/rate-skill --name "Rate Limiter Handbook"
skillcorpus validate /tmp/rate-skill
skillcorpus query --skill /tmp/rate-skill "FULL_JITTER_RETRY_RULE"
skillcorpus benchmark --skill /tmp/rate-skill \
  --questions fixtures/questions/rate_limiter.json --json
```

EPUB：

```bash
skillcorpus pack fixtures/epub_synth/rate_notes.epub -o /tmp/epub-skill
```

扫描件（需已安装 ocrmypdf）：

```bash
skillcorpus pack fixtures/pdf_synth/ocr_image_only.pdf -o /tmp/ocr-skill --ocr
```

## 读懂评测指标

- `heading_hit_rate`：路由是否命中期望章节标题（不是答题质量）
- `evidence_localization_rate`：命中 chunk **正文**是否包含标注锚点
- `no_answer_correct_rate`：无答案题是否正确 `UNSUPPORTED`
- token 比为 **fixture 上** dump vs SKILL+top-k 的实测值，**不是** LLM 端到端，也不是普适 N×

## 支持格式与边界

| 格式 | 状态 |
|------|------|
| Markdown / TXT | 支持 |
| HTML | 支持（块级边界，行内不拆字） |
| PDF 文本层 | 支持；多栏可能 `structure_degraded` |
| PDF 扫描件 | 仅 `--ocr` + ocrmypdf |
| EPUB | 支持；拒绝 zip-slip / 危险 DTD / 过成员数 |
| DOCX/MOBI/公式重建/语义检索/LLM摘要 | **未支持** |

## 安全提示

- 本地运行，默认不上传、不需要 API Key
- 源文是不可信数据；`--harden` 只是启发式
- 打包失败时会保留原先有效 skill（事务性替换）

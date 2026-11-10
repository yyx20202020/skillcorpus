# SkillCorpus

证据优先的本地转换器：自有文档 → 可引用 Agent Skill 证据包。

完整上手步骤见 [docs/getting-started.zh-CN.md](docs/getting-started.zh-CN.md)。

**0.1.1 发布候选**：独立 MIT 实现；不打包版权书；不宣称任意 PDF 无损；评测指标不含夸大的 `citation_support_rate`。

```bash
python -m pip install -e ".[dev,pdf]"
skillcorpus doctor
skillcorpus pack fixtures/rate_limiter/handbook.md -o /tmp/rate-skill --name "Rate Limiter Handbook"
skillcorpus validate /tmp/rate-skill
skillcorpus query --skill /tmp/rate-skill "令牌桶 补充"
skillcorpus benchmark --skill /tmp/rate-skill --questions fixtures/questions/rate_limiter.json
```

支持：Markdown/TXT/HTML/PDF（文本层；扫描需 `--ocr`）/EPUB。  
不支持：DOCX/MOBI、复杂公式重建、语义检索、LLM 摘要、章节级增量缓存。

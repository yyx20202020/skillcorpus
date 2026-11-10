# 上游缺陷覆盖矩阵（SkillCorpus 0.1.1 发布候选）

对照审计对象：`virgiliojr94/book-to-skill` @ `e7bb659d3261491c8b28793dcb9102fa64a46c22`（只读复现）。  
完整条目见 [upstream-audit.md](upstream-audit.md)。  
**说明：** 下表只记录本仓库独立实现中已验证的行为；合成 fixture ≠ 任意技术书。

| ID | 上游问题 | 本版状态 | 证据 / 测试 |
|----|----------|----------|-------------|
| F01 | 断点复用忽略脏 `full_text` | **已对齐** | `WorkCache.verify_or_raise` + 脏缓存拒绝复用；`tests/test_cache_integrity.py` / `test_pack_integrity_reviewer.py` |
| F02 | 复用 workdir 残留旧页证据 | **已对齐** | 换源前 `clear_evidence`；PDF→HTML 串证测试 |
| F03 | 页数 mismatch 不传导到单页 | **部分** | `structure_degraded` 下沉到 page.warnings/confidence；无独立 sidecar API |
| F04 | bs4 行内拆碎章节/代码 | **已对齐** | HTML/EPUB stdlib 块级边界；`test_html_inline` / `test_epub` |
| F05 | `pdftotext -layout` 多栏交错 | **缓解（非根治）** | layout weld 检测 → raw 覆盖 + `structure_degraded`；**不宣称多栏已解决**；`test_pdf.py` |
| F06 | 无内置 OCR | **可选且已在本环境验证** | `--ocr` + ocrmypdf；无则明确失败；`test_ocr.py`（无 ocrmypdf 时 skip） |
| F07 | 24–51× 无保质量基准 | **不照抄** | `heading_hit_rate` / `evidence_localization_rate` / `no_answer_correct_rate` + 实测 token；**禁止**用 title 命中冒充 citation_support |
| F08 | 摘要无页码/不可追溯 | **证据包路径** | chunk 引用 + query citation；摘要仍非本版范围 |
| F09 | 复杂版式/公式 | **未覆盖** | 明确限制 |
| F10 | 大书增量缓存 | **未实现** | 仅有「完整抽取完整性复用」；**不得称为增量缓存已修复** |
| F11 | 转换 SKILL / 安装过重 | **已规避** | 短路由 SKILL + library CLI |
| F12 | 注入扫描偏 advisory | **部分** | 标题消毒 + `--harden`；恶意 HTML 不污染指令区；**不宣传完备防注入** |

## 本版仍明确延后

- 章节级增量 / 跨运行 partial rebuild
- 语义向量检索、LLM 摘要视图
- Docling 级复杂版式/公式重建
- DOCX / MOBI
- 公开 GitHub 发布（父级账户确认后再做）

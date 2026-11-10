# 上游参考项目审查：virgiliojr94/book-to-skill

**审查阶段：** 第一阶段（只读审查 + 本地复现 + 设计）  
**审查记录日：** 以本仓库提交时间为准；**不**把工作区主机日期与上游 commit/issue 的日历关系当作证据。  
**锁定 commit：** [`e7bb659d3261491c8b28793dcb9102fa64a46c22`](https://github.com/virgiliojr94/book-to-skill/commit/e7bb659d3261491c8b28793dcb9102fa64a46c22)（由只读 `git clone` + `git rev-parse` 记录）  
**上游 issue 引用：** 仅当本地对同一 SHA 复现成功或与公开 issue 描述交叉核验后保留；**合成 fixture 不代表全书。**  
**本地只读 clone：** `/tmp/upstream/book-to-skill`（未改上游、未提 PR/issue、未公开发布）  
**许可证：** MIT（`LICENSE.md`）— 可参考思路与独立重写；若直接复制代码须保留版权与许可声明  
**本仓库复用边界：** **优先独立实现**；不 vendoring 上游源码，不打包任何受版权书籍；fixture 仅用原创/许可素材

---

## 1. 项目画像（证据）

| 维度 | 事实 |
|------|------|
| 形态 | 双半架构：确定性 Python **抽取器**（`book_to_skill/`）+ 由宿主 Agent 执行的 **生成器规格**（根目录 `SKILL.md`，约 55 KB / 880 行） |
| 版本 | `pyproject.toml` → `1.4.0`；Python `>=3.9` |
| 依赖 | 核心无强制运行时依赖；可选 extras：`pdf`/`epub`/`docx`/`rtf`/`html`/`technical(docling)`/`all` |
| 测试 | 本地 `pytest tests/ --collect-only`：**982** 用例；完整跑一轮约 **977 passed / 1 flaky fail / 4 skipped**（单独重跑该 fail 即过） |
| CI | `.github/workflows/ci.yml`：多版本 pytest、ruff(E9+F)、optional-deps、smoke、bandit、zizmor、validate-skill；另有 CodeQL / docs deploy |
| 可见 open issues | 检索时 **8** 个 open issue（另有大量 open PR）；本审查引用其中已核实者 |
| 安装方式 | `npx skills add …` 或把整仓 clone 到 skills 目录；抽取 CLI：`python3 scripts/extract.py` |

**数据流（简）：** 文档 → `scripts/extract.py` → `full_text.txt` + `metadata.json`（可选 `pdf_pages.json`）→ Agent 按 `SKILL.md` Steps 蒸馏 → `~/.agents/skills/<slug>/` 下的 `SKILL.md` + `chapters/*.md` + glossary/patterns/cheatsheet。

---

## 2. 值得保留的优点

1. **抽取器工程化扎实**：多格式、多工具降级链、单源失败不拖垮批次；扫描件快速失败提示 OCR（而非 silent empty）。
2. **章节启发覆盖面广**：多语言章节标题、PDF outline、结构标题启发式；CJK radical folding 对坏字体映射有针对性修复。
3. **安全意识高于同类 demo**：不可见 Unicode 清洗、DOCX DTD/实体拒绝、subprocess 路径绝对化、workdir symlink/属主检查、生成技能注入扫描（advisory）。
4. **测试与 CI 密度高**：近千测例 + 安全扫描门禁；有合成 PDF fixture，不依赖版权书。
5. **对自身评测局限有部分诚实注释**：`tools/discovery_tax.py` 写明 discovery-loop 是 *model*；研究文档承认质量评测仍是 plan。
6. **跨宿主 Agent Skills 目录约定**写得很细（Copilot/Claude/Hermes/OpenCode/OpenClaw），产品定位清晰。

---

## 3. 实证不足清单（约 12 条）

分类标签：

- **复现 bug**：本 VM 对锁定 SHA 复现成功，或与上游 open issue 的最小复现一致且代码仍存在  
- **明确缺失能力**：代码路径确认不存在 / 显式关闭  
- **设计权衡**：有意为之，但带来可论证的产品缺口  
- **未验证宣传**：营销数字缺乏“保质量”的可重复基准

优先级：P0 阻塞可信转换 / 证据链；P1 显著质量或成本风险；P2 体验与可维护性。

---

### F01 — 断点复用把“源文件未变”当成“抽取产物完整” 【复现 bug】【P0】

- **证据：** [`utils.py#L1328-L1400`](https://github.com/virgiliojr94/book-to-skill/blob/e7bb659d3261491c8b28793dcb9102fa64a46c22/book_to_skill/utils.py#L1328-L1400)；上游 [#259](https://github.com/virgiliojr94/book-to-skill/issues/259)
- **复现（本 VM，SHA e7bb659）：** `reuse_is_safe()` 在 workdir 存在、mode/sources/sha256 匹配时，对 **缺失 / 空 / 被篡改** 的 `full_text.txt` 均返回 `ok=True`（“workdir intact…”）。
- **影响：** 中断后续跑可授权 Agent 在空/脏语料上继续生成技能 → 静默错书、幻觉放大。
- **新版解法：** 复用门禁必须校验抽取产物：`full_text.txt` 存在、非空、内容指纹（及可选 `metadata` 内记录的 `full_text_sha256`）一致；失败则强制重抽。
- **验收：** 单元测试覆盖 missing/empty/tampered 三种 → `ok=False`；集成测试禁止在脏 workdir 上进入 generate。

---

### F02 — 复用 workdir 会留下过期 `pdf_pages.json` 【复现 bug】【P0】

- **证据：** [`write_pdf_page_sidecar`](https://github.com/virgiliojr94/book-to-skill/blob/e7bb659d3261491c8b28793dcb9102fa64a46c22/book_to_skill/utils.py#L1689-L1753) 只负责写入；非 PDF 二次运行不删除旧 sidecar。上游 [#326](https://github.com/virgiliojr94/book-to-skill/issues/326)
- **复现：**  
  1. `BOOK_SKILL_WORKDIR=/tmp/bts_reuse_test` + `extract.py tests/fixtures/pdf_page_provenance.pdf --pdf-page-sidecar`  
  2. 同 workdir 再抽 `/tmp/other.md`  
  3. `full_text.txt`/`metadata.json` 已换，但 **`pdf_pages.json` 仍指向旧 PDF**。
- **影响：** 页级“证据”与当前语料错配；若 Agent/用户把 sidecar 当引用依据，会产生假页码引用。
- **新版解法：** 每次写入新语料前原子失效旧证据（删除或写 `status=stale`）；sidecar 与 `full_text`/`metadata` 同事务版本号。
- **验收：** 跨格式复用 workdir 后不得残留指向旧源的可用 sidecar。

---

### F03 — 页数不一致只标在 source 级，单页仍可 `requires_manual_review=false` 【复现 bug】【P1】

- **证据：** [`utils.py#L1720-L1730`](https://github.com/virgiliojr94/book-to-skill/blob/e7bb659d3261491c8b28793dcb9102fa64a46c22/book_to_skill/utils.py#L1720-L1730)；[#330](https://github.com/virgiliojr94/book-to-skill/issues/330)
- **复现：** stub `extract_pypdf_page_records` 返回 1 页而 source `pages=2` → source 有 `page_count_mismatch`，**单页 `low_confidence_reasons=[]` 且 `requires_manual_review=False`**。
- **影响：** 只消费 per-page 记录的下游会漏掉不确定性。
- **新版解法：** 源级告警向下传播到每条 page record；引用 API 默认拒绝未审查页。
- **验收：** mismatch 时所有 page.`requires_manual_review is True`。

---

### F04 — EPUB/HTML 的 BeautifulSoup `separator="\n"` 拆碎行内节点 【复现 bug】【P0】

- **证据：** [`epub.py#L98`](https://github.com/virgiliojr94/book-to-skill/blob/e7bb659d3261491c8b28793dcb9102fa64a46c22/book_to_skill/parsers/epub.py#L98)、[`html.py#L128`](https://github.com/virgiliojr94/book-to-skill/blob/e7bb659d3261491c8b28793dcb9102fa64a46c22/book_to_skill/parsers/html.py#L128)；[#263](https://github.com/virgiliojr94/book-to-skill/issues/263)
- **复现：** `Chapter <span>1</span>` → `"Chapter \n1\n…"`；`detect_structure` → **0 chapters**；代码 `<span>print</span>("ok")` → 行被拆，`print("ok")` 不再连续。stdlib `_HTMLTextExtractor` 无此问题。
- **影响：** 带样式的 EPUB/HTML（常见）章节检测失败；技术书代码块损坏后进入蒸馏。
- **新版解法：** 块级才换行、行内标签拼接；EPUB 默认走健壮 HTML→text（可基于改进的 stdlib 路径），并加回归 fixture。
- **验收：** 带 span 的两章 HTML/EPUB fixture → `chapters_detected==2`；代码块可被 `compile()`。

---

### F05 — `pdftotext -layout` 多栏阅读序交错 【复现 bug】【P0】

- **证据：** [`pdf.py#L84-L95`](https://github.com/virgiliojr94/book-to-skill/blob/e7bb659d3261491c8b28793dcb9102fa64a46c22/book_to_skill/parsers/pdf.py#L84-L95) 无条件 `-layout`；[#128](https://github.com/virgiliojr94/book-to-skill/issues/128)
- **复现：** 本机合成双栏 PDF `/tmp/twocol.pdf`：`-layout` / 项目 `extract_with_pdftotext` 出现 `fruit. COLUMN zebra…` 类跨栏拼接；`-raw` 则按栏连续。
- **影响：** 下游章节/蒸馏会读到**原文不存在的句子**（issue 用 IRS Pub 17 亦同）。
- **新版解法：** 栏数/阅读序检测；多栏改 reading-order 或 layout 引擎（Docling 等）并标记置信度；禁止把交错文本当高置信语料。
- **验收：** 双栏 fixture 抽取后左右栏句子不交叉；交错时 `confidence=low` 且阻断“静默成功”。

---

### F06 — 无内置 OCR；Docling 显式 `do_ocr=False` 【明确缺失】【P0】

- **证据：** [`pdf.py#L267-L268`](https://github.com/virgiliojr94/book-to-skill/blob/e7bb659d3261491c8b28793dcb9102fa64a46c22/book_to_skill/parsers/pdf.py#L267-L268)；[`looks_image_only` L101-L117](https://github.com/virgiliojr94/book-to-skill/blob/e7bb659d3261491c8b28793dcb9102fa64a46c22/book_to_skill/parsers/pdf.py#L101-L117)；README 要求用户先跑 `ocrmypdf`
- **说明：** 快速失败是负责任的产品行为，但能力上 **转换管线不含 OCR**；且 `looks_image_only` 依赖 `pdftotext`，无该二进制时返回 `False`，可能拖到整链空文本才失败。
- **影响：** 扫描书/拍照书无法一站式处理；混合页（部分有文本层）易漏检。
- **新版解法：** 可选 OCR 后端（如 ocrmypdf/tesseract/docling OCR）作为显式模式；按页文本密度探测混合扫描；保留“拒绝默默产出空技能”。
- **验收：** 纯图像 PDF fixture 在 `--ocr` 下产出非空文本+页对齐；默认模式仍清晰失败。

---

### F07 — “24×–51× 更少 token”缺乏保质量的可重复基准 【未验证宣传】【P0】

- **宣传：** [README.md#L46](https://github.com/virgiliojr94/book-to-skill/blob/e7bb659d3261491c8b28793dcb9102fa64a46c22/README.md#L46)；表在 [docs/performance.md#L39-L55](https://github.com/virgiliojr94/book-to-skill/blob/e7bb659d3261491c8b28793dcb9102fa64a46c22/docs/performance.md#L39-L55)
- **工具自述：** [discovery_tax.py#L16-L24](https://github.com/virgiliojr94/book-to-skill/blob/e7bb659d3261491c8b28793dcb9102fa64a46c22/tools/discovery_tax.py#L16-L24) — discovery-loop 是 **模型不是轨迹测量**；无 `--skill-dir` 时 skill 侧用 **design cap 4000+1000**
- **本机复现：** 合成 7 章语料跑 `discovery_tax.py`：对 dump 仅 **1.4×**，且 vs discovery best 为 **0.2×（更差）**——说明倍数强烈依赖“全书很大 + skill 固定 ~5k”假设，不是普适常数。
- **质量缺口：** `docs/research/progressive-disclosure-evals.md` 状态为 **ACTIVE PLAN — planning only**；`tools/evals/run.py` **不存在**。现有 evals 是 manifest/score/replay 骨架，**未证明**“省 token 且答题质量不降”。
- **对比对象问题：** 主宣传对比的是 **context-dump 全书**，不是强导航 Agent / RAG / grep 基线；且生成技能是摘要层，与 dump 原始文本 **信息不等价**。
- **新版解法：** 发布任何倍数前必须同时报告：(a) 真实 harness 轨迹 token；(b) 固定题集上的 exact/support/citation 质量；(c) 相对 dump **与** navigation/RAG 基线；禁止用 design-cap 充当实测。
- **验收：** 公开可跑的 eval 配置 + fixture；CI 可跑 replay；倍数声明必须绑定 commit 与题集哈希。

---

### F08 — 生成物强制“永不复制原文”，页码引用未接入技能输出 【设计权衡 + 明确缺失】【P0】

- **证据：** Quality Rule #7 [SKILL.md#L879](https://github.com/virgiliojr94/book-to-skill/blob/e7bb659d3261491c8b28793dcb9102fa64a46c22/SKILL.md#L879) “Never copy raw book text”；章节模板强调框架/摘要；全文件几乎 **无** “cite physical page / 原文页码” 生成指令。
- **页证据：** `--pdf-page-sidecar` 产出的 `pdf_pages.json` **明确不是** `full_text` 的字符偏移映射（架构文档与函数 docstring），且 **不自动进入** 生成章节的引用字段。
- **影响：**  
  - 蒸馏依赖 LLM → **幻觉/丢失**结构性风险（项目口号写 “no hallucination”，但机制是摘要而非可核对引用）。  
  - 用户无法稳定追溯“技能里这句话对应原书哪一页哪一段”。
- **新版解法：** 默认 **evidence pack**：保留可检索原文切片 + 页锚点；摘要/框架为可选视图；回答路径要求 citation 或显式 `unsupported`。
- **验收：** 对 fixture 提问，答案必须带 `(source_id, page|chunk_id)`；切断原文后同一问题应失败或标 unsupported。

---

### F09 — 复杂版式/公式/表格/代码：能力声明大于默认路径 【明确缺失 / 设计权衡】【P1】

- **证据：** technical 模式依赖 Docling；失败则回退 text 链（丢失版式）。SKILL 亦承认 EPUB 等 “code, tables, and formulas may lose structure”。EPUB 图片内容直接丢弃（`images_dropped` 警告）。无 LaTeX/MathML 专用通路；去连字符 `(\w)-\n(\w)` 可能误粘合真连字符词（pdf.py 自陈）。
- **影响：** 技术书默认或回退路径下，表格/代码/公式不可信；中英混排+复杂栏式叠加 F05。
- **新版解法：** 按页结构类型路由；表格/代码/公式独立块类型与置信度；不宣称“任意 PDF 无损”。
- **验收：** 自建含 code fence、markdown table、简单公式的 PDF/EPUB fixture；technical 路径块类型召回达标；回退路径必须标 `structure_degraded`。

---

### F10 — 大书费用与增量：抽取可续跑但不完整，生成仍是重 LLM 流程 【明确缺失 / 设计权衡】【P1】

- **已有（上游）：** 源 sha256、workdir、`reuse_is_safe`、Step 2.6 大书 REPL 探测、Mode 4 fold-in。
- **缺口（上游）：** F01/F02 使续跑不安全；无章节级增量；生成仍重 LLM。
- **SkillCorpus 现状（勿夸大）：** 仅实现「完整抽取结果的完整性校验 + 同源指纹复用」；**章节级增量缓存未实现**，不得写入“已修复增量”。
- **新版后续：** 内容寻址 chunk 增量、生成解耦、真实 tokenizer 费用门禁。

---

### F11 — 转换器用 `SKILL.md` 过重，安装态整仓过重 【设计权衡】【P2】

- **证据：** 本仓 `SKILL.md` 55464 bytes / 880 lines；[#169](https://github.com/virgiliojr94/book-to-skill/issues/169) 测到大量步骤在确认成本前即已加载；[#309](https://github.com/virgiliojr94/book-to-skill/issues/309) 指出 `npx skills add`/clone 带入 docs/tests/site 等非运行时文件。
- **影响：** 宿主上下文税；技能目录污染；与“progressive disclosure”叙事不一致。
- **新版解法：** 运行时包与开发/文档包分离；生成器规程拆成按需加载的子指令；发布 artifact = 最小 runtime。
- **验收：** runtime tarball 文件白名单；主 SKILL 前置门控后才加载重步骤。

---

### F12 — 提示注入防御偏 advisory；供应链曾出现恶意重传 【设计权衡 / 已知风险】【P1】

- **证据：** `tools/scan_generated_skill.py` 为生成后扫描且 **不回显匹配文本**；不可见字符在抽取期剥离（优点）。`SECURITY-NOTICE.md` 记录第三方恶意重传（钱包枚举/外传）。
- **影响：** 文档型 prompt injection 仍可能进入摘要技能并被其他 Agent 加载；用户易装错叉。
- **新版解法：** 高危规则可配置为硬失败；生成技能默认只读工具面；发布签名/校验官方包；文档强调仅安装签名来源。
- **验收：** 含注入短语的 fixture 在 harden 模式下拒绝发布；安装说明含校验步骤。

---

## 4. 调查主题对照（避免“README 没写 = 代码没有”）

| 主题 | 代码侧结论 |
|------|------------|
| 扫描/OCR | **无内置 OCR**；Docling OCR 关闭；有扫描预检 |
| 复杂版式/代码表格公式 | technical→Docling 尽力；回退则差；EPUB 图丢弃 |
| 中英混排 | 章节多语种+CJK folding **较强**；栏式/样式节点仍可能毁结构 |
| 层次目录/切分 | outline + 多语种 + structural；无 `Chapter N` 时需人工（文档已述） |
| 原文页码引用 | sidecar 可选且弱连接；生成技能 **不强制引用** |
| 幻觉/丢失 | 摘要生成路径 **结构上允许**；无 grounded citation 闭环 |
| 大书/断点/缓存/费用 | 有雏形但不完整且有 bug；费用宣传与模型混用 |
| Agent Skill 格式/按需加载 | 目标格式清晰；转换器自身 SKILL 过重；跨宿主路径文档好 |
| 路径穿越/恶意输入/注入/隐私 | workdir/symlink/XXE/sanitize 有投入；注入扫描非硬门；本地处理、无强制上传 |
| 安装/测试/许可 | MIT；测试密；安装偏整仓 |
| 20–50× 宣传 | **未**通过“保质量”基准验证；工具本身限制已写明 |

---

## 5. 本阶段未做 / 阻塞

- 未改上游、未开 issue/PR、未公开发布。
- 未下载版权书籍做端到端蒸馏（避免版权与费用）；token 宣传验证用合成语料 + 阅读其方法论。
- 未装全量 Docling 做大书版式金标（重依赖）；版式结论基于代码路径与上游 issue + 本地双栏 PDF。
- **不承诺**下一阶段实现“任意 PDF 无损”。

---

## 6. 制品

- 本文件：`docs/upstream-audit.md`
- 导出副本：`/opt/cursor/artifacts/upstream-audit.md`
- 产品计划：`docs/product-plan.md`（及 artifacts 副本）

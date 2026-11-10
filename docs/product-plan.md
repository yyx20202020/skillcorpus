# 新产品计划：SkillCorpus（工作名）

**阶段：** 第一阶段设计（与 `docs/upstream-audit.md` 配套）  
**上游对照：** `virgiliojr94/book-to-skill` @ `e7bb659d3261491c8b28793dcb9102fa64a46c22`  
**许可证策略：** 独立实现，MIT 发布自身代码；不复制上游实质代码除非必要时并保留 MIT 归属；**永不打包受版权书籍**；测试仅用原创/公有领域/明确许可素材  
**公开 GitHub：** 本阶段不做；不提供假链接或发布承诺

---

## 1. 一句话定位

把用户自有文档转成 **可引用、可增量、可按需加载的 Agent Skill 语料包**：先保证证据链与抽取诚信，再谈摘要与省 token——并且任何省 token 声明必须带质量基准。

**明确不做的承诺：** 不保证任意 PDF 版式无损；不对扫描件默认“智能猜字”；不把摘要说成原文。

---

## 2. 与上游的差异化（MVP 必打点）

| 上游痛点（见审计） | SkillCorpus MVP |
|--------------------|-----------------|
| 摘要技能难核对，页码弱 | **Evidence-first**：chunk + 页锚点 + 强制 citation 字段 |
| 24–51× 无保质量基准 | **Eval-gated**：token×quality 矩阵，无基准不写倍数 |
| OCR/多栏/行内 HTML 损坏 | **诚实路由**：OCR 可选、栏序检测、健壮 HTML/EPUB |
| 脏 workdir 续跑 | **内容寻址缓存 + 产物完整性门禁** |
| 转换 SKILL / 安装包过重 | **runtime 最小包** + 规程分片按需加载 |
| 生成全靠宿主 Agent 规程 | **抽取/索引确定性**；LLM 蒸馏可选插件，默认可只发 evidence skill |

---

## 3. MVP 范围（下一阶段实现切片）

### 3.1 必须交付

1. **本地 CLI**（Python 3.11+）：`extract` / `pack` / `validate` / `eval-smoke`
2. **输入：** Markdown/纯文本 + 简单 PDF（文本层）+ 简单 HTML；EPUB 作为 stretch
3. **输出（Agent Skills 兼容目录）：**
   - `SKILL.md`：短路由索引（目标 &lt;1.5k tokens）
   - `corpus/chunks/*.md`：带 `source_id`、`chunk_id`、可选 `page_start/page_end` 的原文切片
   - `corpus/manifest.json`：哈希、页图、章节边界、置信度
   - 可选 `views/summary/`：LLM 摘要视图（关闭也不影响检索回答）
4. **安全：** 输出目录拒绝 symlink 逃逸；不可见 Unicode 剥离；生成物注入扫描 **可硬失败**
5. **完整性：** 中断恢复校验 `full_text`/`chunks` 指纹；禁止脏缓存
6. **评测脚手架：** 1 本原创短书 fixture + 10 问；指标含 citation_support、answer_hash_stability、token_in；可在无 API 下 replay
7. **文档：** 安装、局限、版权、如何复现评测

### 3.2 明确延后

- 全自动“框架/心智模型”高质量蒸馏（可作为插件）
- 完美公式/复杂杂志版式
- 多书库级路由与托管市场
- 官方云转换服务（保持本地优先）

---

## 4. 架构选择

```
源文件
  → adapters/ (pdf|html|md|epub)
  → normalize (encoding, sanitize, reading-order)
  → segment (outline | heading | sliding window fallback)
  → evidence store (content-addressed chunks + page map)
  → packer (Agent Skill tree)
  → optional summarizer (LLM plugin)
  → validate + eval
```

**关键决策：**

| 决策 | 选择 | 理由 |
|------|------|------|
| 语言 | Python | 文档生态与上游对照成本低；独立包名与模块，不 fork |
| 技能格式 | Agent Skills `SKILL.md` + 相对链接 | 跨宿主可发现；保持短核心 |
| 默认知识表示 | **原文 chunk + 元数据**，摘要可选 | 对抗幻觉；允许用户审计 |
| PDF | pypdf/pdfminer 基线 + 可选 docling；多栏检测 | 不绑死单一引擎 |
| OCR | 显式 `--ocr` 可选依赖 | 默认诚实失败 |
| 缓存 | 输出目录 `.work` 完整性复用 | 同源指纹全量复用；章节增量另议 |
| UI | 先 CLI；若需再薄 Web 浏览 manifest | 本阶段无 Web 亦可；有浏览器面时再上 Next 不在 MVP 强制 |

---

## 5. 路线图

### Phase A — 证据包 MVP（下一 agent 回合主目标）

- 原创 fixture 书（中英混排短文 + 代码块 + 伪表）
- 抽取→切片→打包→validate
- 完整性门禁与安全扫描硬失败开关
- replay eval 骨架

### Phase B — 难文档

- OCR 模式、混合扫描页探测
- 多栏阅读序
- EPUB 健壮 HTML；图片“有图无字”清单
- PDF page map 与 chunk 对齐（允许近似，标置信度）

### Phase C — 智能视图与省 token（有评测才宣传）

- 可选摘要/cheatsheet 视图
- 与 evidence 回答同题集对比：质量不降才报告 token 比
- 增量 fold-in

### Phase D — 开源打磨

- runtime/devtools 分包
- CI、安全政策、供应签名说明
- 公开仓库（**届时**再定名与链接；本文件不预支）

---

## 6. 验收矩阵

| ID | 场景 | 通过标准 |
|----|------|----------|
| A1 | MD 原创书打包 | 产出合法 skill 树；`validate` 退出 0 |
| A2 | 带 span 的 HTML 章节 | 章节数正确；代码块可编译 |
| A3 | 双栏 PDF | 不交叉或 `structure_degraded` 非静默成功 |
| A4 | 扫描 PDF 默认 | 非空失败信息；`--ocr` 才尝试 |
| A5 | 脏 workdir 恢复 | 拒绝复用；无错技能 |
| A6 | 引用答题（fixture） | ≥90% 答案含正确 chunk/page 引用 |
| A7 | 切断 corpus | 同题不得仍“自信作答” |
| A8 | 注入文档 | harden 模式拒绝 pack |
| A9 | Token 声明 | 无质量数字则文档禁止写“N×” |
| A10 | 版权 | 仓库无第三方书；README 含使用边界 |

---

## 7. 复用与合规边界

- **上游 MIT：** 允许学习 API 形状与测例思路；本仓库以独立实现为主。若日后有意移植个别函数，必须保留版权行并在 NOTICE 列出。
- **书籍版权：** 工具零预置正文；用户自备有权文件；生成物若含原文切片，默认视为私人语料，文档明确“勿公开分发受版权文本”。
- **恶意重传风险：** 发布时强调官方来源校验（校验和/签名），吸取上游 `SECURITY-NOTICE.md` 教训。

---

## 8. 阶段完成定义

- [x] 锁定上游 SHA 并只读审查  
- [x] 本地复现关键缺陷并写入审计  
- [x] 差异化 MVP + 架构 + 验收矩阵  
- [x] Phase A 证据包 MVP（CLI / fixtures / tests / CI / 源码 zip）— 本回合  
- [ ] Phase B+ 难文档与可选摘要视图  
- [ ] 公开 GitHub 发布（另轮；本仓库仅准备制品）

---

## 9. 制品路径

- `docs/product-plan.md`
- `/opt/cursor/artifacts/product-plan.md`
- 配套审计：`docs/upstream-audit.md`、`/opt/cursor/artifacts/upstream-audit.md`

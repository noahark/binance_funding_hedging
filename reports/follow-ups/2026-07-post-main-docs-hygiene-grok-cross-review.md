# Grok 交叉评审：三方文档卫生意见合议

Status: **cross-model review record** — not operator-approved execution, not a
Harness delivery stage, no runtime contract change.

Recorded by: Grok (author of the original hygiene packet).<br>
Date: 2026-07-12.<br>
Branch observed: `main` (HEAD `d8d77e4` at authoring; worktree may contain
uncommitted Pass B archive / follow-ups index edits).

## Inputs reviewed

| Artifact | Author |
|---|---|
| `2026-07-post-main-docs-hygiene-and-semantic-conflicts.md` | Grok (original plan) |
| `2026-07-post-main-docs-hygiene-codex-semantic-sync-plan.md` | Codex |
| `2026-07-docs-sync-method-opus4.8.md` | Claude Opus 4.8 |
| `2026-07-post-main-docs-hygiene-and-semantic-conflicts-glm52-counterproposal.md` | GLM-5.2 (`claude_glm` / `zhipu_glm`) |

Related delivery stage: `2026-07-auto-review-pipeline-v1` (`accepted`, merged to
`main`).

---

## 总裁决

| 来源 | 判定 | 一句话 |
|---|---|---|
| **Opus 4.8** | **ACCEPT_WITH_AMENDMENTS**（对原计划）— 方法层最强 | SoT 指针化 + accept ritual；A1/A2 批评成立 |
| **GLM-5.2** | **ACCEPT_WITH_AMENDMENTS**（对原计划）— 最可执行 | §0 纠错、C4 拆分、P2 lint 立项；批次最干净 |
| **Codex** | **ACCEPT_WITH_AMENDMENTS**（对执行层）— 提交卫生最严 | A1/A2 分 commit、禁止误绑 SHA；对 10/11 banner 过严 |

**对原 Grok packet 自身：** 接受三方共同的 **blocking 修订**（§1），再谈执行。

**合成推荐：**

- 导航 / SoT 哲学 → Codex + Opus + GLM 共识
- 防复发 → Opus accept ritual + GLM P2 lint（另 stage）
- 提交边界 → Codex A1/A2
- C4 拆分 → GLM
- 原计划未修订版 **S1–S9 不得原样执行**

---

## 1. 三方共同击中、原作者认账的问题

### B1 — 原 packet §0 权威顺序失真（Opus A1 / GLM 1.1 / Codex §2）

**属实，阻塞。**

- `AGENTS.md` 真序是 10 项，含 `agents/skills/*.md`、
  `agents/developer-discipline.md`，且 **`reports/agent-runs/<stage>/` 在
  `docs/*.md` 之上**。
- 原 packet 把 `docs/auto-review-pipeline.md` 提成独立第 7 级，并压低 stage
  设计壳——**违反最高权威**。
- C6 结论（用 `16-serial` / `19-model-routing` **stage 内层** supersede）仍可
  成立，但**不得靠「docs > stage design」这种假阶梯**。

**拟改：** 原 packet §0 **逐字复刻** `AGENTS.md` Authority Order；auto 合同仅
脚注：「registry / AGENTS 正文引用的 normative doc，位阶仍是 `docs/*.md`」。

### B2 — 计划与工作区不同步（Opus A2 / GLM C1）

**属实，阻塞。**

- 落档时为避免索引撒谎，已改 `reports/follow-ups/README.md`（delivered +
  注册 hygiene 包），**可能尚未 commit**。
- 原 packet 仍把 C1/S1 写成「未来步骤」→ 评审在批一件**已做一半**的事。

**拟改：** C1 标 **`applied_in_worktree, pending_commit`**；S1 降级为
**核对 + 随导航批提交**。

### B3 — C4 不可整段 resolved（GLM）

**属实。**

- §4 (a) `codex.default_model` / `gpt-5.5` → 已被 registry `gpt-5.6-sol` 收敛。
- §4 (b) Gemini future-candidate 事件记录 → **仍 open**。

原计划「整 §4 resolved」会误关 (b)。

**拟改：** 仅 model 点 resolved header；**(b) 独立 follow-up 条目**。

### B4 — C2 stage id 简称（GLM）

**接受。** 写全 `2026-07-funding-annualized-history-v1`，勿写模糊
“funding-history”。

---

## 2. 分模型深度评价

### 2.1 Opus 4.8 — 诊断层最佳

**强：**

1. **「一个事实，一个家」** — 根因比「改错字」准；导航应是指针，不是复述。
2. **M1–M6 批次** 与原 S 系列兼容，结构更清。
3. **Accept ritual 护栏**（grep 三入口）— 防 C1/C2/C3 复发，原计划缺失。
4. 实测核对 registry / 保留真文件 / 多条 C 项，可信。

**弱 / 需收：**

- Accept ritual 若写进 `AGENTS.md` 属于 **合同/纪律变更**，不宜与纯导航
  commit silently 混做；应标 **可选 bookkeeper checklist** 或并入
  mechanical-gates / docs-lint 小 stage（与 GLM P2 合流）。<br>
- 「其他文档不准写具体 model 名」对 **registry 命令模板、model-adapters
  示例命令** 不适用——SoT 是 registry，手册可展示命令，但须标注「以
  registry 字段为准」。

**对原计划：** ACCEPT with amendments（A1、A2 阻塞）——同意。

### 2.2 GLM-5.2 — 工程落地最清晰

**强：**

1. §0 **逐字引用** + 不重排（正确）。
2. **三层分类**（导航 / 证据 / 设计壳）可操作。
3. **C4 拆分** 必须采纳。
4. **P0/P1/P2 分层**：文档批 vs `scripts/` lint 批，符合 Harness
   「scripts 要走 stage」。<br>
5. C7 **直接 skip** 合理。
6. 「navigation 取原 packet，authority order 与防复发取本方案」——务实合成句。

**弱 / 需收：**

- P0「**无需走 stage review**」对已合 `main` 的卫生改动在操作上常见，但与
  仓库严格习惯可能张力；建议操作者明确 **「docs hygiene exception」或 mini
  stage**。<br>
- P2「docs/README 必须列 `docs/` 下所有 md」可能过严；宜改为：**AGENTS /
  registry 引用的合约 + 明确 canonical 列表**，或「未列出则不得声称
  canonical」。<br>
- 「Grok review 角色限定」是 **表述精确化**，不是冲突；registry 已写 auto
  primary vs manual 非 default gate。

**对原计划：** ACCEPT with amendments ——同意，且 C4/P2 优于原 S 表。

### 2.3 Codex — 提交与证据纪律最严

**强：**

1. **A1/A2 分 commit**：先 archive 字节，再绑真实 SHA——避免
   `bookkeeper_checkpoint` / 旧 SHA 错绑。<br>
2. 分类标签 `navigation-stale` vs `active-contract-conflict`——避免把导航
   过期当 runtime P0。<br>
3. **direction-draft 不迁**（F 层）— 比原「迁出 docs」更稳。
4. 验收命令清单（byte-equality、validate-stage、diff --check）可执行。
5. 明确「未提交的 Pass B ≠ 已进入项目历史」。

**弱 / 需争议：**

| Codex 主张 | Grok 态度 |
|---|---|
| **不要**给已验收 `10-design` / `11-adr` 加 supersede banner | **部分反对**：banner 是 prepend header、不改正文。折中见 §4 Batch C |
| 不改 `status.json` bootstrap reason（C7） | **同意 skip** |
| Batch B **只限三个导航入口** | **同意作为首批**；mechanical-gates header 可进 B′ |
| 不把导航不一致标 P0/P1 runtime | **同意换标签**（用 Codex taxonomy） |

**对 Codex 方案：** **ACCEPT_WITH_AMENDMENTS** — A1/A2/B 批次采用；10/11
banner 用折中，不绝对禁止。

---

## 3. 冲突矩阵：三方 vs 原计划

| 议题 | Grok 原 | Codex | Opus | GLM | 合成决议 |
|---|---|---|---|---|---|
| Authority order | 重排（错） | 逐字 10 项 | 逐字 + A1 | 逐字 | **逐字 AGENTS** |
| C1 README | S1 修 | Batch B | M2 已应用 | 降级核对 | **已 worktree；提交时核对** |
| STAGE_INDEX | 加行 | 加行 + historical-ref | M3 | 加行 + 全 id + lint | **加两行全 id；lint 另 stage** |
| docs/README | 加 bullet | 加 | M4 | 加 | **做** |
| C4 mechanical-gates | 整 §4 resolved | §4 model resolved | M6 | **拆 a/b** | **拆分** |
| 10/11 banner | 要 | **不要** | 要（stage 内） | 要 header only | **折中：C-pref 优先，C-alt 可选** |
| direction-draft 迁移 | S6 可选迁 | **不迁** | 另批 | 未强调 | **不迁** |
| C7 reason | optional | 不改 | optional | skip | **skip** |
| 防复发 | 无 | 弱（扫描） | **accept ritual** | **P2 lint stage** | **checklist 先；lint 立 stage** |
| Pass B commit | 未规范 | **A1/A2 分交** | 对账 | 文档批 | **Codex A1/A2** |
| 风险分级 | P0–P3 | 换 taxonomy | — | — | **用 Codex 标签** |

---

## 4. 合成执行计划（待操作者批准）

### Batch 0 — 修订 hygiene 指令自身（先于改仓库）

1. 原 packet 或本评审：§0 改为 AGENTS 逐字；C1/S1 状态更正；C4 拆分；C2
   全 stage id。<br>
2. 声明 Pass B：**filesystem done, git pending**（若仍未提交）。

### Batch A（Codex）— 仅 history 归档提交

- **A1：** 20 文件 → `history/raw/` + symlink + snapshots + `history/README.md`
  （**不**绑假 SHA；保留旧 `bookkeeper_checkpoint` 语义）。<br>
- **A2：** `status.json` / `70-handoff.md` 记 **真实 A1 SHA**；运行
  `validate-stage --phase checkpoint`（及操作者要求的 pre-accept 时再跑）。

### Batch B — 导航 only

- `reports/follow-ups/README.md`（确认 delivered；与 worktree 对齐后提交）
- `reports/agent-runs/STAGE_INDEX.md`（`2026-07-auto-review-pipeline-v1` +
  `2026-07-funding-annualized-history-v1` 全 id）<br>
- `docs/README.md`（`docs/auto-review-pipeline.md`）
- **可选 B′：** mechanical-gates **仅 model 点 (a)** resolved header；
  Gemini **(b)** 新 follow-up 一行

### Batch C — 设计壳可见性（二选一，勿混 A/B）

- **C-pref（推荐 / Codex 友好）：** 仅在 `STAGE_INDEX` / stage `70-handoff` /
  `history/README` 写 supersede 指针。<br>
- **C-alt：** `10-design.md` / `11-adr.md` **prepend-only** banner（Opus/GLM/
  原计划）；正文 0 改；单独小批。

### Batch D — 另 stage（非本 hygiene）

- docs-sync lint / STAGE_INDEX coverage（GLM P2 + Opus ritual 机械化）
- mechanical-gates §1–3、§5
- Claude `opus4.8` 短名（若操作者要可执行）
- dual-dev auto / goal 编排

### Explicitly out of hygiene

- 不改 auto serial-only 合同、registry 运行时语义（除非另批）
- 不 bulk 改写历史 evidence 正文
- 不 push / 不模型 dispatch

---

## 5. 对评审问题的直接回答

| 问题 | 答案 |
|---|---|
| 按职责分层 vs 统一改措辞？ | **分层**（Codex A–G + Opus SoT） |
| A1/A2 是否解决 SHA 错绑？ | **是**；应采纳 |
| Pass B 是否有文件必须真文件？ | **否**（当前 11 个真文件集合理）；`60-test-output` 保留真文件正确 |
| Batch B 三入口够吗？ | **首批够**；B′ 可选 |
| active-contract-conflict 有吗？ | **活跃合同层当前无型号/serial 互斥**；剩余是 `navigation-stale` + `historical-wording` |
| 误把冻结基线当历史？ | direction-draft **保留路径**（Codex）；原 S6 迁出 **取消** |

---

## 6. 原作者对自身的修订声明

| 原主张 | 修订后 |
|---|---|
| §0 自拟权威序 | **作废** → 逐字 AGENTS |
| S1 修 C1 | **已部分执行** → 核对 + 提交 |
| C4 整段 resolved | **拆 a/b** |
| S6 迁 direction-draft | **取消** |
| 10/11 必加 banner | **C-pref 优先，C-alt 可选** |
| P0 导航 = runtime 级 | **改为 `navigation-stale`** |
| 无防复发 | **接受 checklist + 独立 lint stage** |

---

## 7. 给操作者的一句话

> 三份意见 **互补不互斥**：<br>
> **Opus** 定哲学（SoT + 防漂移），**GLM** 定文档批与 C4 拆分，**Codex** 定
> git/证据边界。<br>
> 原计划 **导航优先、证据 verbatim** 被一致认可；**§0 与 C1 状态、C4 整段
> 关闭** 应先修订指令，再按 **Codex A1/A2 → Batch B → 可选 C** 执行。

---

## 8. Related paths

```text
reports/follow-ups/2026-07-post-main-docs-hygiene-and-semantic-conflicts.md
reports/follow-ups/2026-07-post-main-docs-hygiene-codex-semantic-sync-plan.md
reports/follow-ups/2026-07-docs-sync-method-opus4.8.md
reports/follow-ups/2026-07-post-main-docs-hygiene-and-semantic-conflicts-glm52-counterproposal.md
reports/follow-ups/2026-07-post-main-docs-hygiene-grok-cross-review.md  (this file)
reports/follow-ups/README.md
AGENTS.md  (§ Authority Order)
```

---

```text
本地北京时间: 2026-07-12 15:40:18 CST
下一步模型: human
下一步任务: 裁定 Batch 0→A→B→C；批准后授权执行（本文件不授权提交/push）
```

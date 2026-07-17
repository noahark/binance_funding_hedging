# Fable5 直修计划 v2（一次性收弧）— 已吸收五模型 review，待用户拍板

模式: 用户指定的例外流程——**Fable5 直修 + 多模型 review + 用户最终拍板**。
v1 → v2 变更依据: codex(REWORK, 5P1) / opus4.8(有条件批, F1-F8) / claude-glm(2P0+1P1) /
grok(CONDITIONAL APPROVE, M1-M4+S1-S6) / kimi 重审 session ff8b70c3(轻量 REWORK, F1-F6)。
文末附「review→处置」映射表。范围仍**不含 Stage B**。

底线不变: 不改写历史 review 原文（演进只追加 note）、不改历史指纹、不改产品行为、
AGENTS.md 与 `_template` 的本仓专有字段不被同步覆盖。

## 直修审计协议（codex-5 / grok-S1,S6 / opus-F5）

- 开工前先把 05/06/07/82 四个未跟踪文件提交入库（clean-worktree 前置，glm/kimi 均标）。
- 两仓各钉 commit range；每个 T 的原始命令与输出留档到本 stage 目录（60-/61- 序列）。
- 实现 diff 的独立评审 = **Kimi + Codex（非 Anthropic；opus4.8 与 Fable5 同厂，不担任
  独立评审）**，评审输入 = raw `git diff` + A1-A8 对抗用例输出 + bookticker pre-accept
  输出，禁止只读计划叙事。
- 用户批准前不 push；red-gate-greening-v1 补 status.json/70-handoff 终态记账；用户对
  直修模式的授权原文（拍板消息 verbatim）落专用证据文件。

## 任务列表（v2 执行序）

### T0 — Stage A 模板仓账本收口〔新增，codex-4〕
`status=stage_accepted_waiting_user` 与 `merged_back_to_main:true` 自相矛盾且无
`user_acceptance` 记录。补记用户接受原文（"接受 Stage A，执行合并 + cp"，2026-07-17）
为 user_acceptance；查无原文的部分如实登记证据缺口，**不补造**。

### T2a — Golden 基线（先于 T1，opus-F2 / kimi golden-diff / grok-M3 / codex-2）
`scripts/validate-all-stages.py`：fixture 模式 = 记录级校验（跳过 branch/worktree 上下文
断言，kimi P1-2）、per-repo root、排除两仓 `_template/`。**用现行 validator** 对两仓全部
stage 落盘 committed 基线（stage → 输出摘要）。附**薄期望迁移表**（仅列预期改变态者）：
- bookticker: known_red(chain+review_1 trail) → green_with_exception（T3 后）
- docs-truth-sync: known_red → 维持 known_red(class-2) 或 green_with_exception（视 D-i）
- funding-annualized-history-v1: chain-red → **green（登记为 v2 预期战果**，kimi 实测其
  review 指纹全量==status，缺省路标下零添加转绿；防止被误读为 validator 没跑）
- harness-flow-optimization-v1: known_red（status 值 ∉ ALLOWED_STATUSES，历史遗留）
- 4 个 legacy 字符串-task stage: known_red（task 形态，历史遗留）
总验收口径改为：**"无未登记的红、无未登记的判定翻转"**（kimi-F3）。

### T1 — D3-v2 重写〔模板仓，核心〕协议闭合版（codex-1 / glm-P1-3 / grok-M1 / kimi-F5）
- 覆盖担保 v1 版**只保留两条途径**：规则 1 = top-level review 指纹 == 重算
  `base..Wi` 前缀（全量命中 j=n ⇒ 全部段已担保，**无需 waypoints**——bookticker 走此路，
  缺省路标 `[base,head]`、零 waypoints）；规则 3 = class-1 例外按**既有 scope 语义**盖
  尾随（`review_k` = 该 review 匹配前缀之后的剩余段）。**task own-review 从覆盖担保中
  移除**（glm 方案 a + grok 推荐；`_task_own_review_covers` 按 dev 坐标重算的口子随之
  整体删除——kimi 指出的"命门 hunk"直接不存在）。**不新增 scope 语法、不新增
  assertion_id**；`task:<id>` 保留 finding-4 语义并映射为"task.head 所在路标段"，
  task.head ∉ 路标时报记录错误。`covers_through_task` 退役（kimi 实测 0/23 使用，
  零兼容成本），留一行 compat 说明。
- **T1 DoD**（grok-M2 / kimi-P1-1,F4）：合成对抗用例 **A1-A8** 实跑并留档（无担保段
  fail / dev-diff 冒充 fail / 路标首尾错 fail / 畸形与重复路标 fail / 单任务退化不变 /
  全量 review-2 命中即绿 / bookticker 真实数据带例外 PASS / 伪造路标段无担保 fail），
  输出存本 stage 测试证据文件；随后非 Anthropic raw-diff 评审。
- 文档：模板仓 harness-design D3 段改 v2；Stage A `10-design.md` §3/§5 追加订正 note；
  `_template/status.json` 加 `coverage_waypoints` 示例（merge，见 T5 规则）。

### T2b — 基线复跑比对（T1 后）
重跑 runner 与 T2a 基线 diff；仅允许迁移表内的预期变化。

### T6 — 治理规则 + known-issue 总登记〔模板仓，移到 T5 前，codex-3〕
- 三条收口规则照 v1（max_rework 硬停、文档 stage 可带 P2 收口/语义收敛默认、修复攒批），
  **明确标注从属于用户"终审以 review-2 + 用户显式验收为准"的主线之下**（opus-F8）。
- known-issue 台账（每项给登记落点，kimi-F6 / opus-F6）：身份治理 P3（未注册 provider
  串自声明）、纯 evidence 段豁免、路标祖先序 hygiene、class-2（若 D-i 不收）、
  bookkeeper 多任务顺手记路标惯例。落点 = harness-design 注记 + `reports/follow-ups/`。

### T5 — 下行同步〔改 merge-not-copy，codex-3 / kimi-F1,F2 / grok-S5〕
- 同步清单：`validate-stage.py`、schema、`validate-all-stages.py`、
  **`docs/harness-design.md`**（kimi-F2，否则本仓永留旧链式条文=新造 doc-truth 漂移）、
  T6 治理文本。
- **字段级 merge**：本仓 `_template/status.json` 只增 `coverage_waypoints` 示例，
  **保留** `session_receipts`/`reporting_preferences`（kimi 实测 update 脚本 `:110-113`
  为整文件覆盖，会静默删字段）；carve-out 校验范围 = AGENTS.md + `_template/status.json`
  + harness-design 本地 3 行注，校验用可重复 diff 命令留档；`model-adapters.md` 本弧不动。
- **分支拓扑**（glm-P0-1 / kimi-P1-2）：模板仓合 main → 本仓同步落 **main**（AGENTS 硬门）
  → T3/T4 在 **main** 上执行（`:540-544` recheck-on-main 红门所致，stage 分支上永远红）。

### T3 — bookticker 真转绿〔本仓 main 上〕
- 证据采用 **kimi 重审实证**：bookticker `status.json.user_acceptance.instruction` 与
  `70-handoff.md:35-38` 已含用户豁免授权 verbatim（已提交 blob）→ `evidence_file` 指向
  70-handoff.md + `evidence_sha256` 封印；reason 言明"该 blob 日后再编辑即破印回红，
  属设计行为"（kimi 注意点）。opus-F3 的更严读法由两点补强：digest 封印 + 用户本次拍板
  消息 verbatim 落直修协议证据文件。
- 只追加 `authorized_exceptions[]`（scope=review_1、钉 `a9218b7:dd72d6ae…`）；边界改述为
  "不动 tasks[] 坐标 / review 原文 / diff_fingerprint，仅向前追加"（glm-P2-4）。
- pre-accept 在 main 跑，PASS-with-exception 输出写**新证据文件**（不动冻结 blob，codex）。

### T4 — docs-truth-sync 账面归一〔本仓 main 上〕
- 范围缩准（kimi 实测 status.json 已归一）：仅 `70-handoff.md` 正文与终态对齐。
- **D-i（用户拍板）class-2 收不收**：glm 证实 docs-truth-sync 即首例。若收 → 白名单扩项
  并入 T1（严格条件：证据须含用户对每条残余 finding 的逐条处置 + 钉指纹）；若不收 →
  T2a 迁移表维持 known_red + T6 台账登记。
- 追加 note：bookticker 真绿依赖本直修 T1+T3，非 Stage A 单独达成（grok-S4）。

### T7 — schema/docstring prose 清欠〔本仓，独立 commit，opus-F7 / grok-M4〕
- 路径改正：`schemas/api/public-market/{symbol-snapshot,funding-history}.schema.json`、
  `backend/services/snapshot_service.py:320-322`。
- schema `:5` 按契约 mode-dependent 表述改写（**非**简单删 same-version 半句，kimi）；
  **连带删除契约 `:296-300`/`:397-410` 的 drift 披露注记与 Residual Risks 对应条**
  （opus-F1，否则合同声称一个已不存在的漂移=反向漂移）。
- 定性写明：对已批准真值（docs-truth-sync 收敛契约 + user_authorizations[2]）的同步，
  不引入新事实，故不触发 contract-amendment 样本门（codex）。
- 验收：schema diff 仅 description 行 + 按**实际**测试数跑全量（backend 全集 + 前端 80；
  v1 写的 71 是三文件子集旧数，kimi 校正）。

### 收口 — red-gate-greening-v1 终态记账 + ACTIVE 归位（grok-S6 / kimi-F6a）

**执行序**: 提交 05/06/07/82 → T0 → T2a → T1(+A1-A8+独立评审) → T2b → T6 → T5(落 main)
→ T3 → T4 → T7 → 收口。

## Review→处置映射（逐条）

- codex-1 协议未闭合 → T1 闭合（own-review 移除、scope 表、全量命中规则显式化）
- codex-2 oracle → T2a/T2b golden 基线 + 迁移表 + A1-A8 归 T1 DoD
- codex-3 同步毁字段/漏文件/顺序 → T5 merge-not-copy + 清单扩 + T6 前移
- codex-4 Stage A 账本 → 新增 T0
- codex-5 审计协议 → 专节
- opus-F1 反向漂移 → T7 范围并入；F2 基线先行 → T2a 前置；F3 证据 → T3 采 kimi 实证+
  双补强；F4 直修留痕 → 审计协议+10-design note；F5 评审身份 → 协议写死 Kimi+Codex；
  F6 残余登记 → T6 台账；F7 独立 commit → T7；F8 从属关系 → T6 标注
- glm-P0-1 recheck-on-main → T5 分支拓扑；P0-2 class-2 首例 → D-i 用户拍板；
  P1-3 own-review 段映射 → 采方案(a)整体移除；P2-4/5/6 → T3 边界改述/缺省路标/先提交
- grok-M1→T1 scope 规则；M2→A1-A8；M3→迁移表；M4→T7 路径与定位；S2→covers_through_task
  退役说明；S3→T3 证据点名；S4→T4 note；S5→T5 可检查 diff；S6→收口
- kimi-F1→T5 merge；F2→T5 清单+harness-design；F3→验收口径+预登记（含 annualized 转绿
  战果）；F4→A1-A8 留档；F5→scope 表+不新增语法；F6→T6 台账+收口+先提交

## 需用户拍板

1. **D-i：class-2 收不收**（docs-truth-sync 即首例；我倾向**收**，带严格条件，收后两仓
   再无永久红门；不收亦成立=永久 known_red）。
2. **确认本清单 v2 并授权执行**（该拍板消息 verbatim 即直修协议 + T3 补强证据的原文）。

---
模型身份: Fable 5（anthropic/claude-fable-5）
本地北京时间: 2026-07-17 23:05
下一步: 用户拍板 D-i + 授权 → Fable5 按执行序一次性执行 → Kimi/Codex 对 raw diff 独立
评审 → 用户终审

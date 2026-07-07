<!-- ============ RECEIPT（审计元数据；非任务内容） ============
status: done                # pending | running | done | escalated
reviewed_by: fable5 (bookkeeper)   # 设计评审 2026-07-07
review_verdict: ACCEPT      # 设计对齐冻结契约, 指令与真实代码/路径核验通过
review_note: 实现须注意行级 value_usdt 不能直接复用 _usdt_value(缺价返回0无法区分 null/0), 需返回 None 的变体; 顶层 total_value_usdt 逻辑不变。
stage_id: 2026-07-private-account-ui-polish-v1
stage_branch: stage/2026-07-private-account-ui-polish-v1
node: stage-design
target_model: codex        # 本 stage designer（唯一）
role: stage_designer       # design-only；依 Hard Gates 不得实现、不得任 final reviewer
role_chain: designer=Codex → implementer=Kimi → review-2=Claude/Fable5
adapter_cmd: 用户以「读此文件并执行 PROMPT BODY」一行指令发至 Codex 终端
stage_delivery_base_sha: 4549227e9f6528787fb8e69b72c0cd7c585611f4  # delivery diff 的 base（已 merge main v0.4）
current_stage_head_at_dispatch: c118ae0            # 派发时 stage HEAD（含 H_intake REWORK 修订）
outputs:
  - reports/agent-runs/2026-07-private-account-ui-polish-v1/10-design.md   # 已产出, ACCEPT
  - reports/agent-runs/2026-07-private-account-ui-polish-v1/11-adr.md      # 已产出, ACCEPT
completed_at: 2026-07-07 CST
next_dispatch: Kimi 依 10-design/11-adr 实现（前后端）→ Fable5 review-2
  # 启动文案: reports/agent-runs/2026-07-private-account-ui-polish-v1/implementation-kimi.prompt.md
======================================================================== -->

--- PROMPT BODY（不可变任务正文，自此行以下原样执行） ---

你是 stage `2026-07-private-account-ui-polish-v1` 的**唯一 stage designer**。
这是**纯设计文档任务**：产出 `10-design.md` 与 `11-adr.md`，把「怎么改」
精确到实现模型（Kimi）可直接照做。**禁止**改动任何源码 / schema / 契约文档 /
前端文件本身——你只在 `reports/agent-runs/<stage-id>/` 下写这两份设计文档，把
schema 字段形态、契约文档措辞、测试点以**文本方式**写清，交由 Kimi 落码。

## 角色红线（Hard Gates，不可越界）

- 你是 designer，**不实现、不做 final review**。Codex 因 designer 身份已被记为
  review-2 ineligible（见 status.json）。final reviewer 是独立的 Claude/Fable5。
- 只加字段、不改既有字段/枚举语义（见下「契约变更门」）。

## 背景

本 stage 承接 private-account-v1 验收后的 4 项个人账户/借币**展示打磨**。
H_intake 经 GPT 只读评审 REWORK、用户 2026-07-07 裁决后定稿。**务必先读**：

1. `reports/agent-runs/2026-07-private-account-ui-polish-v1/00-intake.md`
2. `reports/agent-runs/2026-07-private-account-ui-polish-v1/00-task.md`
   （四项 scope、Non-Goals、Acceptance 已写死，你的设计不得与之冲突）
3. `docs/api/public-market-contract.md`
   — `negative_funding_status` 结构优先级、`borrow_rate_source` / `net_daily_yield`
   语义、private_account 块定义（冻结契约，仅第 4 项允许 additive 扩展）
4. `schemas/api/public-market/snapshot.schema.json`
   — 现有 `balances_unified`(asset,total_balance) / `balances_spot`(asset,free,locked) /
   顶层 `total_value_usdt` / `valuation`
5. `backend/domain/snapshot.py` — `assemble_private_account` / `_usdt_value`
   （逐资产估值内部已算、仅未逐行吐出；`price_map` 来自 public ticker）
6. `frontend/index.html` + `frontend/self-check.js` + `frontend/fixture/public-market-snapshot.json`
7. `AGENTS.md` §契约修订（一处 frozen 契约的 amendment 须有 raw public 样本佐证，
   落 `reports/api-samples/<stage>/`）

## 四项 scope 的设计要点（须逐项在 10-design 展开）

**第 1 项 — 净收益行日借币利率（仅成本腿命中行）**
- 仅当该行 `borrow_rate_source != null`（负费率借币候选、成本腿产出费率）时,
  在净收益列旁展示 `borrow_validation.classic_margin.daily_interest_account`（账户档）;
  无账户档回落 `daily_interest_vip0` 并标注「参考」。
- 正费率行（`net_daily_yield = daily_funding_rate`，无借币腿）/ 无成本腿行 → 占位（—）。
- 设计要点：定义前端在哪一列/子行渲染、占位规则、账户档 vs 参考档的视觉区分。

**第 2 项 — `negative_funding_status` 派生文案（先结构优先级，再 borrow_validation）**
- 派生**先判结构禁用状态**并保持结构文案：`DISABLED_PERP_ONLY` / `DISABLED_BSTOCK` /
  `DISABLED_SPOT_ONLY`（优先级见契约「Priority for negative_funding_status」）。
- **仅 `PRIVATE_BORROW_VALIDATION_REQUIRED`（MARGIN_SPOT_CANDIDATE）行**才按
  `borrow_validation` 细分（已验证可借 / 杠杆对未列出 / 资产不可借 / 未探测(限速预算) /
  需私有验证），结构禁用行**不得**派生「需私有验证」。
- 设计要点：给出完整派生决策表（输入字段 → 中文文案），中文文案按 [[ui-chinese-first]]
  定稿；结构字段本身不改。

**第 3 项 — 个人账户面板上移**（纯前端布局）
- private_account 面板从页面底部移到市场表（费率行情表）之上。
- 设计要点：DOM 结构调整点、private_channel=disabled/失败时的优雅降级（不白屏）。

**第 4 项 — 个人账户余额每资产折算 USDT（★ additive 契约变更，走契约变更门）**
- 范围**仅限账户余额**：`balances_unified[]` / `balances_spot[]`。`um_positions[]` 是
  **exposure view，其名义价值 NEVER 计入 total_value_usdt**（见 `assemble_private_account`
  anti-double-count 硬规则），故 **`um_positions[]` 不加 `value_usdt`、不参与资产折算**,
  维持现有持仓敞口展示。若将来要展示 UM 名义价值，另开需求，勿与账户资产估值混淆。
- 已确认 payload 只吐聚合 `total_value_usdt`、不暴露单资产价格，**无法纯前端计算**。
  用户裁决允许 additive 契约变更。
- **你必须在 11-adr 明确二选一并给理由**：
  - 方案 A：后端在 `balances_unified[]` / `balances_spot[]` 各行新增 `value_usdt`
    （复用 `_usdt_value`，与 `total_value_usdt` 同源，单一真相源）。
  - 方案 B：payload 暴露 `price_map`（或逐资产 price），前端相乘。
  - 倾向 A（避免前后端重算漂移、与总估值一致），但由你裁定并说明取舍。
- 明确定义：新字段名 / 类型（8 位字符串 or null）/ **无价格时 null vs 0**（注意
  `_usdt_value` 现将缺价视作 0 + warning，逐资产展示须区分「0 价值」与「无价格」）/
  在 schema 的确切位置 / 契约文档 v0.x additive amendment 的**逐字措辞**。
- **契约变更门证据**：新字段的估值源是 public ticker 价格。判定现有
  `reports/api-samples/` 样本是否已覆盖该 public 端点足以佐证；若不足，记为本 stage
  需补的 raw public 样本（落 `reports/api-samples/2026-07-private-account-ui-polish-v1/`）
  与对应 follow-up。**不得**仅凭合成 fixture 落契约变更。

## 交付物（严格按模板章节）

`10-design.md`（模板：Summary / Assumptions / Design Decisions / Task Breakdown /
Test Strategy / Risks / Raw Artifact Requirements For Review）
- Task Breakdown 要能直接映射为 Kimi 的实现清单，标注每项前端/后端边界。
- Test Strategy 明确：后端 `backend/tests/test_snapshot.py` /
  `test_private_account_v1.py` 增补的断言（尤其第 4 项 additive 字段的估值与
  null/0 边界、anti-double-count 不回归）；前端 `frontend/self-check.js` 覆盖
  4 项展示分支（含各占位/降级路径）；契约变更门 schema 校验。

`11-adr.md`（模板：Context / Decision / Alternatives / Tradeoffs / Edge Cases /
Links / Reviewer Notes）
- 重点记第 4 项方案 A/B 抉择、null vs 0 语义、契约 amendment 边界与样本证据要求。
- Reviewer Notes 给 Fable5 review-2 列出「看起来可疑但故意为之」的点。

## 完成判据

- 两份文档产出，四项 scope 各有可落码的设计与测试点。
- 第 4 项契约变更门路径写清（字段形态 + 契约措辞 + 样本证据）。
- 设计不与 00-task.md 的 Non-Goals/Acceptance 冲突；不改任何源码/schema/契约文档本身。
- 交回后由 Fable5（bookkeeper）审阅并派发 Kimi 实现。

（完成后交回 Fable5：**RECEIPT 由 bookkeeper 更新**（status/outputs），你不改本 prompt 文件。
若遇阻塞无法在不违反红线/契约下推进，写明阻塞点退回 Fable5 由其 escalate。）

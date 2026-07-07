<!-- ============ RECEIPT（审计元数据；非任务内容） ============
status: pending             # pending | running | done | escalated
stage_id: 2026-07-private-account-ui-polish-v1
stage_branch: stage/2026-07-private-account-ui-polish-v1
node: implementation
target_model: kimi          # 本 stage 唯一 implementer（前后端）
role: implementer           # 依 Hard Gates 不得任本 task 的 reviewer/fix-author 之外角色；final review 归 Fable5
role_chain: designer=Codex → implementer=Kimi → review-2=Claude/Fable5
design_verdict: ACCEPT (Fable5, 2026-07-07)
stage_delivery_base_sha: 4549227e9f6528787fb8e69b72c0cd7c585611f4   # delivery diff 的 base
adapter_cmd: 用户以「读此文件并执行 PROMPT BODY」一行指令发至 Kimi 终端
outputs（实现产出，交回后由 bookkeeper 收敛）:
  - 源码/schema/契约/测试改动（提交到 stage 分支）
  - reports/agent-runs/2026-07-private-account-ui-polish-v1/20-implementation.md
  - reports/agent-runs/2026-07-private-account-ui-polish-v1/60-test-output.txt
  - reports/api-samples/2026-07-private-account-ui-polish-v1/<timestamp>/{api-v3-ticker-price.json,evidence-index.md}
next_dispatch: Fable5 组织 review-1 / review-2（终审 Fable5，Codex/Kimi 均 ineligible）
======================================================================== -->

--- PROMPT BODY（不可变任务正文，自此行以下原样执行） ---

你是 stage `2026-07-private-account-ui-polish-v1` 的**唯一 implementer（Kimi）**，
承接**前后端全部实现**。设计已由 Codex 产出、Fable5 评审 ACCEPT。你**照设计落码**，
不重开设计决策；如发现设计与契约/代码有实质冲突无法照做，**停下写明冲突退回 Fable5**，
不要自行改设计口径。

## 角色红线

- 你是 implementer，**不做本 task 的 final review**（终审 Fable5，无 override）。
- 在 stage 分支 `stage/2026-07-private-account-ui-polish-v1` 上工作并提交；**不得合并到 main**。
- 契约只做 **additive**：只加 nullable 字段，不改既有字段/枚举语义，`schema_version`
  保持 `public-market-snapshot/v1`。

## 权威输入（务必先读，按此实现）

1. `reports/agent-runs/2026-07-private-account-ui-polish-v1/00-task.md`（scope/Non-Goals/Acceptance）
2. `reports/agent-runs/2026-07-private-account-ui-polish-v1/10-design.md`（★ 实现蓝本，Task A/B 清单）
3. `reports/agent-runs/2026-07-private-account-ui-polish-v1/11-adr.md`（决策与边界，尤其 null vs 0）
4. `docs/api/public-market-contract.md` / `schemas/api/public-market/snapshot.schema.json`
5. `backend/domain/snapshot.py`（`assemble_private_account` / `_usdt_value`）
6. `frontend/index.html`（`renderPrivatePanel` L1105 / `badgeForNegativeFundingStatus` L878 /
   `formatFundingRate` L790 / `private-panel` section L640）+ `frontend/self-check.js`

## ★ 实现红线（评审时点明，务必遵守）

**行级 `value_usdt` 不得直接复用 `_usdt_value`。** 现有 `_usdt_value` 缺价/坏价/坏数量
一律返回 `Decimal(0)`，会把「无价格」和「合法零值」混为 0。本 stage 要求：
- 缺价格 / 坏价格 / 坏数量 / 空数量 → 行 `value_usdt = null`（并保留/补 warning）
- 合法零值或合法计算为 0 → `value_usdt = "0.00000000"`
- **顶层 `total_value_usdt` 仍走原 `_usdt_value`（缺价计 0 + warning）逻辑不变**，
  anti-double-count 硬规则不回归。
因此请新增一个能返回 `Optional[Decimal]`（缺价→None）的行级估值变体，供逐资产用；
总额继续用原函数。

## Task A：后端 / schema / 契约 / 测试（10-design §Task A）

Allowed files：`backend/domain/snapshot.py`、`backend/services/snapshot_service.py`(仅在
需要透传既有 price_map、无语义变更时)、`schemas/api/public-market/snapshot.schema.json`、
`docs/api/public-market-contract.md`、`backend/tests/test_private_account_v1.py`、
`backend/tests/test_snapshot.py`、`backend/tests/fixtures/*`、
`reports/api-samples/2026-07-private-account-ui-polish-v1/**`

- `balances_unified[].value_usdt = total_balance * price(asset)`；
  `balances_spot[].value_usdt = (free + locked) * price(asset)`；USDT/USDC 稳定币计 1。
- `um_positions[]` **不加** `value_usdt`，形态保持不变。
- schema：在 unified/spot item 加 `value_usdt`（decimal_string | null），**不进 `required`**；
  但后端新 producer 必须由测试断言输出该字段（防「可选」变「漏吐」）。
- 契约文档：按 10-design §4 的 v0.4 additive amendment 措辞追加到
  `docs/api/public-market-contract.md`。
- **契约变更门证据**：在 `reports/api-samples/2026-07-private-account-ui-polish-v1/<timestamp>/`
  落 raw public `GET /api/v3/ticker/price`（no-key）样本 + `evidence-index.md`。网络不可用时
  可复制既有样本（`reports/api-samples/2026-07-private-account-v1/*/api-v3-ticker-price.json`）
  并在 index 写明来源路径与 sha；**不得仅用合成 fixture**。

## Task B：前端展示（10-design §Task B）

Allowed files：`frontend/index.html`、`frontend/self-check.js`、`frontend/fixture/public-market-snapshot.json`

1. 净收益列补借币日息子行：仅 `row.borrow_rate_source != null` 行展示
   `borrow_validation.classic_margin.daily_interest_account`，缺账户档回落 `daily_interest_vip0`
   并标「参考」，两者皆缺显示占位；正费率/无成本腿行不展示。用现有 `formatFundingRate`。
2. `negative_funding_status` 改为 **row-aware 结构优先级派生**（把
   `badgeForNegativeFundingStatus(ns)` 升级为接收整行 row，同步调用点）：先判
   DISABLED_PERP_ONLY / DISABLED_BSTOCK / DISABLED_SPOT_ONLY 结构文案；仅
   PRIVATE_BORROW_VALIDATION_REQUIRED 行按 `borrow_validation` 细分五文案。原始枚举可留 `title`。
3. 把 `#private-panel` 移到市场表 panel **之前**；`renderPrivatePanel()` 逻辑不变；
   缺失/`verified=false` 降级不白屏。
4. unified/spot 余额卡片每行加「折算: <value_usdt> USDT」；null/缺失显示「折算: -」；
   隐私开关同时遮蔽余额与折算值。
- 保持 UI 中文优先、前端零排序、不在前端反算 total。

## 测试与证据（须捕获原始输出）

按 10-design §Test Strategy 补断言并运行，**把原始输出写入
`reports/agent-runs/2026-07-private-account-ui-polish-v1/60-test-output.txt`**：
- `python3 -m pytest backend/tests/test_private_account_v1.py -q`
- `python3 -m pytest backend/tests/test_snapshot.py -q`
- `python3 -m pytest backend/tests -q`
- `node frontend/self-check.js`
- 用 schema 校验更新后的 `frontend/fixture/public-market-snapshot.json`
关键断言：value_usdt 的 null vs "0.00000000" 区分、稳定币计 1、缺价 warning、
um_positions 无 value_usdt、anti-double-count 不回归；前端四项展示分支 + 各降级路径。

## 交付

- 源码/schema/契约/测试/样本改动，提交到 stage 分支（清晰 commit message，勿动 main）。
- `20-implementation.md`：改了哪些文件、关键实现点（尤其行级估值变体与 null/0）、如何验证。
- `60-test-output.txt`：上述命令的原始输出。
- 完成后退回 Fable5：由 bookkeeper 校验 checkpoint、算 diff fingerprint、组织 review-1/review-2。

（RECEIPT 由 bookkeeper 更新，你不改本 prompt 文件。若遇契约/设计冲突无法照做，
status 相关阻塞写明后退回 Fable5，由其裁决或 escalate。）

# Intake — 2026-07-phase2-borrow-sort-v1

## Direction baseline (frozen prerequisite)

`docs/phase2-direction-draft.md` = **FROZEN Phase 2 方向基线**（commit
`11dec26`，Codex MILESTONE 合成 ACCEPT-FREEZE，verdict 原文
`reports/agent-runs/phase2-direction-v1/codex-synthesis.raw-output.md`）。
用户已批准进入 stage design（2026-07-04）。本阶段一切设计冲突以该基线为准。

## Stage goal

- **Task A（后端，claude_glm）**：私有只读签名通道（`private_client`）+
  借币可借性/利率数据 → `borrow_validation` 契约块；公开 fundingInfo
  接入 → `funding_interval_hours`/`daily_funding_rate` 字段 + rows 后端
  排序（abs(日费率) 降序）；契约 bump v0.2。
- **Task B（前端，kimi）**：费率/时间拆列；新增日费率列 + 结算间隔标注；
  渲染后端顺序，零排序逻辑；不消费 borrow_validation。
- 非目标：交易/划转能力（永久禁止）、私有数据前端展示（下一阶段）、
  净收益模型、开仓规划。

## Complexity & process

**MILESTONE**。方向 panel 等效履行已由 Codex 裁定接受（仅限本 milestone）。
实施按 `docs/parallel-development-mode.md`（ADOPTED-TRIAL）**首次试运行**：
GLM(Task A) ‖ Kimi(Task B) 并行 + 任务内嵌交叉预审（checkpoint，非评审门）+
bookkeeper 串行落盘 + 正式 review-1 对 committed 指纹确认 + 单轮 review-2。
红线突破即回退串行（mode doc §7）。

## Security red-line (Phase 2 amendment, per frozen baseline §3)

- 允许：只读 HMAC-SHA256 签名 GET，仅限 status.json 端点白名单。
- 永久禁止（跨阶段 invariant）：order、borrow 执行、repay、transfer、
  withdraw、listenKey/user data stream、websocket、任何 POST/PUT/DELETE
  及交易语义端点。
- key/secret 仅经环境变量 `BINANCE_API_KEY`/`BINANCE_API_SECRET` 注入；
  不落 repo/日志/报告/对话。用户决定保留全权限 key（IP 白名单已绑定）→
  **代码层白名单为主防线**，§3.3 技术门全部为 review 必查项。
- 证据脱敏：落档 URL 整体剥离 query string；账户级响应去账户标识；
  脱敏脚本入库可复核。

## H_intake hard gate（Task A 实现的前置门）

controller 持用户 key 对白名单端点各做一次只读 **discovery 实抓**，脱敏
落档至 `reports/api-samples/2026-07-phase2-borrow-sort-v1/<ts>/`（含
evidence-index.md + sha256），据实抓冻结 10-design 端点矩阵的字段列。
`/papi/v1/margin/maxBorrowable` 若实抓失败（账户形态与文档不符）→
BLOCKED，升级用户决策，禁止静默 fallback 到 /sapi。
Task B 不受此门约束（其契约依赖已在 10-design 设计期冻结）。

## Frozen inputs

- 方向基线: `docs/phase2-direction-draft.md` @ `11dec26`
- fundingInfo 方向论据样本: `reports/api-samples/phase2-direction-v1/
  20260704T2030Z/fapi-v1-fundingInfo.json`（sha256 `33f61539…`；实现期
  须由 H_intake 重新实抓的新样本替代作为契约证据）
- 现行契约: `docs/api/public-market-contract.md` v0.1 + 冻结修正案
- Phase 1 已验收基线: head `ee9296c`（ui-cn-v1 accepted @ `d91a6cf`）

## Roles

| 角色 | 承担者 | 备注 |
|---|---|---|
| designer / breakdown / prompt author | Fable5 | 本文件及全套 dispatch packet；review-2 默认避让 |
| bookkeeper（单一本地执行会话） | claude_glm controller 会话 | 与 Task A 实现同模型：dual-hat 已披露，评估同 impl-v1/ui-cn-v1 的 evidence_policy 缓解 |
| Task A implementer | claude_glm | review-2 hard-ban |
| Task B implementer | kimi | review-2 hard-ban |
| embedded pre-review A | kimi（fresh 只读会话） | checkpoint，非评审门 |
| embedded pre-review B | claude_glm（fresh 只读会话） | checkpoint，非评审门 |
| review-1（正式，committed 指纹） | A→kimi fresh；B→glm fresh | 与预审同向但必须新会话 |
| review-2（final gate） | Codex/GPT | `reviewer_prior_involvement=direction_synthesis`，disclosure override 同前三阶段 |
| 最终验收 | 用户（Fable5 外部复核辅助） | controller `can_accept_final=false` |

本地北京时间: 2026-07-04 21:05 CST（Fable5 预写）

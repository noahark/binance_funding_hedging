# 00-task — 2026-07-private-account-v1

## 任务索引

| 任务 | 实现者 | scope | 预审者 |
|---|---|---|---|
| A 后端：验证链/契约 v0.3/净收益/探测扩围/资产聚合/预算落地 | claude_glm（实现会话） | `backend/**`、`schemas/**`、`docs/api/**`、`backend/tests/**` | fresh Kimi |
| B 前端：私有面板/综合资产视图/净收益列/sort_basis 标注/隐私开关 | kimi | `frontend/index.html`、`frontend/self-check.js` | fresh claude-glm |

两任务并行启动（H_intake 完成后）；耦合面在设计期冻结，任何变更需求
→ R3 停手升级 bookkeeper，禁止本地自决。

## 冻结耦合面（Task B 消费的全部 Task A 产出）

1. rows[].`net_daily_yield`（string|null）
2. rows[].`borrow_rate_source`（enum|null）
3. 顶层 `sort_basis`（enum）与 **rows 有序性**（后端排好，前端零排序）
4. 顶层 `private_account` 块（10-design §1.4 字段）
5. `borrow_validation.classic_margin.daily_interest_account`（string|null）
6. `borrow_validation` coverage/warnings 语义（10-design §1.5）
7. 既有字段全部不变（funding_interval_hours / daily_funding_rate /
   枚举三列 等 Phase 2 契约）

## 硬红线（沿用 + 本轮新增）

- `classify.py` / `normalize.py` **零改动**；枚举与优先级零改动。
- key 片段零出现；单一 HMAC 出口；deny-by-default；GET-only。
- 进 git 的样本/报告/fixture 数值脱敏（运行时页面真实展示不受限）。
- 实现终端不 commit、不碰 status.json；R10 收尾段必须机械执行。
- 端点清单以 status.json endpoint_whitelist 为准，**开发中途加端点 =
  R3 升级**。
- ADR：本 stage `11-adr.md` 必须记录 ADR-3 修订（排序基准）、一阶近似
  假设、防重复计算规则、脱敏映射、预算表冻结。

本地北京时间: 2026-07-06 00:22 CST（Fable5 起草）

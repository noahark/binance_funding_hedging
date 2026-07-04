# Task Split — 2026-07-phase2-borrow-sort-v1

详细边界见 `10-design.md`（唯一权威）；本文件为任务索引。

## Task A — backend: private channel + borrow_validation + fundingInfo sort

- Owner: `claude_glm`（review-2 hard-ban）
- Scope: `10-design.md` §1/§2/§3
- Dispatch: `task-a-glm-backend.prompt.md`
- Embedded pre-review: fresh Kimi 只读会话，`pre-review-task-a-by-kimi.prompt.md`
- 验收要点：安全门负向单测全绿；daily rate 测试向量全过；排序全序断言；
  三态语义 schema 测试；契约 v0.2 + discovery 证据；classify/normalize
  零改动；既有 54 测试保持通过。

## Task B — frontend: column split + daily-rate visibility, zero sort logic

- Owner: `kimi`（review-2 hard-ban）
- Scope: `10-design.md` §4
- Dispatch: `task-b-kimi-frontend.prompt.md`
- Embedded pre-review: fresh Claude-GLM 只读会话，`pre-review-task-b-by-glm.prompt.md`
- 验收要点：拆列 + 日费率列 + 间隔标注；零排序逻辑（无控件、payload 顺序
  渲染）；新字段缺失优雅降级；formatFundingRate/formatBeijing* 零改动；
  self-check 全绿；不消费 borrow_validation。

## 耦合面（仅此三项，H_intake 冻结）

`funding_interval_hours`（int|缺失）、`daily_funding_rate`（string|null|缺失）、
rows 有序性（abs 日费率降序，null 末尾，symbol 升序 tie-break）。
实现期任何一方需要变更耦合面 → 停手上报 bookkeeper（mode R3），
禁止本地 fix。

## 无 ADR 例外

本阶段有架构决策（私有通道引入），`11-adr.md` 必须实质记录：单一签名
出口、deny-by-default 白名单、borrow_validation 独立块（枚举零改动）、
后端排序职责、全权限 key 残余风险（用户决定）与代码层主防线。

本地北京时间: 2026-07-04 21:05 CST（Fable5 预写）

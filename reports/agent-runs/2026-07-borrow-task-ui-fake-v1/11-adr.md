# Stage ADR

## Context

用户要先查看借币自动任务的前端效果，随后才决定是否接入后端。现有产品明确定义为只读快照工作台，当前没有借币执行面。行情表行本身已经是可点击的详情入口，任何新增控件都不得破坏它。

## Decision

创建纯前端、仅内存的任务原型。任务由行的 `base_asset` 标识，固定显示未来的“每 30 秒重试直到成功 N 次”策略，但不执行该策略。任务页作为第二个视图展示创建结果；`HOME` 通过同一条资产路径获得支持。

## Alternatives Considered

- Alternative: 直接对 Binance 私有 API 发起借币并在浏览器定时重试。
  - Why rejected: 超出用户限定的 fake 范围，会引入真实资金、风险、凭据和后台可靠性问题。
- Alternative: 在 fixture 中插入 `HOMEUSDT` 假行情行。
  - Why rejected: 将展示层需求错误地写入市场数据契约，容易被误当成真实市场数据。
- Alternative: 只添加静态借币任务菜单，没有可创建流程。
  - Why rejected: 不能验证两个输入框、确认和参数到任务列表的用户路径。

## Tradeoffs

- Tradeoff: 内存任务在刷新后消失。
  - Benefit: 清楚隔离 fake UI 与未来后端任务系统，不增加持久化或风险。
  - Cost: 无法模拟跨刷新恢复或真实成功进度；这些属于下一阶段设计。
- Tradeoff: 重试间隔固定为 30 秒。
  - Benefit: 视觉可验证且不增加未要求的第三个参数/配置。
  - Cost: 最终后端仍需决定可配置的间隔、限速和退避策略。

## Edge Cases Or Constraints

- `amount` 只能接受大于零的有限数值；`successTarget` 只能接受大于零的整数。
- 控件事件必须不会打开行详情抽屉。
- 页面必须明确标记“前端演示；未发起真实借币请求”。
- 只移除额度子行的“已借完”，不改变已确认耗尽状态的“可借 0(已借完)”徽标。

## Links To Prior Direction

- Direction synthesis: none; user explicitly approved a low-complexity frontend-fake route.
- Product or architecture docs: `AGENTS.md` Project State (read-only product baseline).

## Reviewer Notes

不要把固定 30 秒或 `0/N` 前端展示误判为后台调度实现。若 diff 中出现 `/api/` 借币请求、私有签名、`setInterval` 任务重试、后端文件或 fixture 市场行，则属于越界。

## Amendment v2: Explicit UI State Machine

The user requested lifecycle controls and a deleted-status filter. A physical removal would make “已删除” impossible to inspect, so the stage adopts soft deletion as a UI-only state. The state machine is deliberately small:

```text
new task → borrowing ↔ paused
borrowing | paused | completed → deleted
```

There is no completion transition in this fake because no scheduler or success event exists. `completed` is nevertheless a first-class display/filter state so the UI contract does not need restructuring when a later backend supplies progress.

Task configuration edits are presentation-only local mutations, not an instruction to an external scheduler. Allowing edits while borrowing is intentional for this fake preview; later backend design must decide whether active-task edits require a pause/restart, optimistic concurrency, and audit records.

当前 Session ID: unavailable (current runtime does not expose provider-native session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-borrow-task-ui-fake-v1/11-adr.md
本地北京时间: 2026-07-18 18:26:49 CST
下一步模型: Kimi
下一步任务: 实现前端 fake 借币任务 UI

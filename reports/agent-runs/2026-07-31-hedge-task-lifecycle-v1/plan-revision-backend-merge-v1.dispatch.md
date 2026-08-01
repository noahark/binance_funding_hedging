# Dispatch —— plan-revision-backend-merge-v1

```text
Identity:
  task_id:         plan-revision-backend-merge-v1
  target_role:     Planner
  target_model:    claude_glm
  provider:        zhipu_glm
  status_revision: 6
  required_skill:  agents/skills/software-architect.md
```

## Goal

按 Human 的两条新决策**修订**你上一轮交付的方案（`b370401`）。这不是返工惩罚 —— 你的 ADR-001 有一处前提被 Bookkeeper 核查推翻，Human 据此改了选型；计划评审阶段的修订按 `AGENTS.md` §8 **不计入 `rework_count`**（当前仍为 `0`）。

### 被推翻的前提（先读，这是本次修订的起点）

ADR-001 判定「后端合并被事实堵死，须扩冻结白名单或新增读路径 = 新增限频权重」。**前半句成立（hedge 服务这个类确实够不到 `private_account`），结论不成立**：

| # | 事实 | 位置 | 内容 |
|---|---|---|---|
| F-A | 服务器层同时持有两个服务 | `server.py:632-642` | `build_server` 把 `service`（`SnapshotService`，产出 `private_account`）与 `hedge_open_service` 注入**同一个 `_Handler`**；处理 `/api/hedge-open-positions` 的 `_hedge_open_positions`（`server.py:607-608`）两者皆在手。 |
| F-B | 取账户数据零上游请求 | `snapshot_service.py:237-257` | `get_snapshot()` 在 live 是**纯读已发布状态**，docstring 原文 `live: zero-upstream pure read of the published state`。**零新增交易所请求、零新增限频权重。** |
| F-C | 未就绪路径 | 同上 | 首次发布前 live 读抛 `SnapshotNotReady`（server 映射 503）；offline 是同步 fixture 构建 + 60s 缓存。 |
| F-D | 账户数据不可用时的形状 | `snapshot.py:1097-1116` | `verified: false`、`balances_unified`/`balances_spot`/`um_positions` 三数组为空、金额字段 `null`、`error` 带原因（如 `private_channel_disabled`）。 |

即：**后端合并可在服务器层完成，无需扩白名单，也不产生任何新的交易所请求。** ADR-001 所述代价不存在。

### Human 的两条决定（已定，不得推翻、不得重新论证选型）

- **D14｜合并改为后端做。** Human 在获知 F-A/F-B 后直接拍板。你的任务是把它设计好，**不是**重新比较前后端优劣。
- **D15｜保留被删除任务的成本基。** 修改 `aggregate_positions` 的 `WHERE t.status != DELETED`（`store.py:1950` 与 `:1960` 两条查询），让已删除任务的已成交腿仍计入。你原方案的**非目标 #7「本轮不改后端 `WHERE`」作废**，该项移入本轮范围。

D15 的依据：`PROJECT_STATE.md` 的 `[OPEN][MONEY-VISIBILITY]` 条目原文写着该问题「becomes routine if auto-pause ever turns into auto-delete」并标注「**Blocks that change**」，而本 stage 的 ② 正是执行该转换。你原方案以 `um_positions` 骨架为由不改 `WHERE`，只覆盖了**敞口可见性**，未覆盖**成本基** —— 被自动删除任务的 `spot_avg`/`perp_avg` 仍会消失，合并表该行退化为「无任务记录」，用户看得到持仓、看不到入场价，且 ② 落地后成为常态。

## 修订范围

**只改受 D14/D15 直接影响的部分，其余保持不动。** 你上一轮 P2-P8 的裁定（除受影响处外）、六条红线确认、风险清单等，Bookkeeper 核验通过，不要重写。

必须修订：

1. **`10-design.md` 的 P1** —— 重裁为后端合并，给出具体做法。
2. **`11-adr.md` 的 ADR-001** —— 重写。Context 须如实记录前提被推翻这件事（不粉饰）；Decision 为后端合并；Consequences 重估。顺带修掉引用错误：原文引 `index.html:2106` 指向无关代码，`directionForPosition` 实际在 `:2198`。
3. **`10-design.md` 非目标 #7** —— 删除该条（已移入范围），并在正文补 D15 的做法与影响。
4. **`12-development-breakdown.md` 的 Task 1** —— 文件边界从纯前端变为后端 + 前端，验收标准、风险等级、测试策略相应重估。
5. **`10-design.md` §5（与 fake 的一致性）** —— fake 用的是前端 join，数据源一节需按 D14 更新。
6. 任何因上述改动而失效的交叉引用（如 §6 证据表中「前端合并 join」一行）。

### 你必须在修订中裁定的五个新决策点

- **N1｜改既有接口还是新开接口。** `GET /api/hedge-open-positions` 现有返回是 §3.4 冻结的 Position JSON，前端逐字渲染（`index.html:4500`）。合并后的形状与它不同。是就地改这个端点，还是新开一个（旧的保留）？给出结论与代价。
- **N2｜降级路径。** F-C（`SnapshotNotReady`）与 F-D（`verified: false`）两种情况下，合并端点返回什么？**不得让持仓接口因账户数据未就绪而整个 503** —— 本地记账部分本来就能返回。请给出明确的降级契约。
- **N3｜D15 的契约影响。** 去掉 `WHERE != DELETED` 后，`GET /api/hedge-open-positions` 的语义变化（已删除任务的腿开始计入）对既有消费者的影响；是否需要在返回里标出「该行来自已删除任务」；`hedge_open_fill` 与 `hedge_open_leg` 两条查询是否都改。
- **N4｜前端还剩什么。** 后端出合并结果后，前端的工作缩到什么范围；`63f5007` 预览确定的展示形状如何保持；既有「UM 持仓」表与 `renderHedgePositionsSection` 如何被取代。
- **N5｜测试策略。** 合并逻辑移到 Python 后可测性提升，请给出具体的测试切面（哪些用 `backend/tests/` 覆盖、哪些仍需 `self-check.js`），特别是六个场景（normal / no_task / no_um / single_leg / missing / empty）与符号对齐（1000x 六币）的测试归属。

## Allowed Files

**只可修改你上一轮交付的这三份文档，不得修改任何代码文件：**

- `reports/agent-runs/2026-07-31-hedge-task-lifecycle-v1/10-design.md`
- `reports/agent-runs/2026-07-31-hedge-task-lifecycle-v1/11-adr.md`
- `reports/agent-runs/2026-07-31-hedge-task-lifecycle-v1/12-development-breakdown.md`

按 `agents/roles.md` Shared Rules 的勘误规则：这是**你自己的**已交付文档，可就地更正，但须在每份文件顶部附一行修订说明（日期 + 改了什么 + 为什么）。

`backend/`、`frontend/`、`status.json` 及其他任何文件**一律不得改动**。边界不足即为阻塞项，报告并停止。

## Inputs

| 文件 | 字节数 | 读什么 |
|---|---|---|
| 本 dispatch | —（当前文件） | 全部 |
| `04-backend-merge-decision.md` | 6308 | 全部 —— D14/D15 与被推翻前提的完整记录 |
| 你自己的 `10-design.md` / `11-adr.md` / `12-development-breakdown.md` | 28648 / 9510 / 11453 | 你已有上下文，按需回看，勿整读 |
| `plan-hedge-task-lifecycle-v1.dispatch.md` | 12766 | 六条红线与原始约束（**仍然全部有效**） |
| `02-scope-decisions.md` | 7647 | D1-D8 |
| `PROJECT_STATE.md` | 5197 | Live Risks 与 Open Follow-ups |

新增代码锚点（除下列外，沿用上一轮 dispatch 的锚点表）：

| 位置 | 是什么 |
|---|---|
| `server.py:632-642` | `build_server`：两个服务注入同一 `_Handler` |
| `server.py:607-608` | `_hedge_open_positions` 处理函数 |
| `snapshot_service.py:237-257` | `get_snapshot()`：live 零上游纯读 / offline 同步构建 + 60s 缓存 / `SnapshotNotReady` |
| `snapshot.py:1097-1116` | `private_account` 不可用时的降级形状 |
| `store.py:1950` / `:1960` | `aggregate_positions` 两条查询的 `WHERE t.status != ?`（D15 的目标） |
| `index.html:2198` | `directionForPosition`（更正 ADR-001 的错误引用） |

### 红线

上一轮 dispatch 的**六条红线全部继续有效**（51169 逐字冻结、不得放宽 A-1、不得新增状态枚举、不得用账户级数值冒充每币、不得自动交易动作、不得无证据抽象）。新增一条：

7. **不得重新论证 P1 的选型。** D14 是 Human 已定决策。你可以指出后端做法的风险与代价（应该指出），但不得建议改回前端，也不得设计「可切换前后端」的兼容层（红线 #6 明禁）。

## Acceptance Checks

每项按 `AGENTS.md` §7 标注 `pass` / `fail` / `contested`。

1. **N1-N5 五个新决策点全部有明确裁定**，各含结论、理由、放弃了什么。
2. **ADR-001 已重写**，Context 如实记录前提被推翻（不粉饰、不改写历史），Decision 为后端合并，Consequences 重估；`index.html` 引用已更正为 `:2198`。
3. **非目标 #7 已删除**，D15 的做法（改哪两条查询、语义变化、是否标记来源）已写入正文。
4. **Task 1 已重估**：文件边界含后端与前端、验收标准可判定、风险等级与理由更新、测试策略明确。
5. **N2 降级契约明确**：账户数据未就绪或不可用时，持仓接口**不整体失败**，返回什么有明确定义。
6. **未受影响部分未被改动**：P2-P8（除受 D14/D15 直接影响处）、六红线确认、风险清单保持原判；改动处逐条列出。
7. **三份文档各有顶部修订说明**（日期 + 改了什么 + 为什么），符合勘误规则。
8. **七条红线逐条确认**，其中新增的第 7 条须明确声明未重新论证选型。
9. **不引入无证据支撑的抽象**：后端合并的每个新增点指出它解决的已观察问题。
10. **新增风险**：后端合并相对前端合并新引入的风险逐条列出（至少覆盖接口契约、降级、snapshot 耦合三方面）。

## Stop

- 完成后按 `AGENTS.md` §7 输出 `[TASK_RESULT v2]`，然后**停止**。
- **不要改动 `status.json`** —— 本任务状态由 Bookkeeper 更新。
- 不得写代码、不得改 `backend/` 或 `frontend/`、不得合并、不得推送、不得接触凭证或实盘路径。
- 不得启动、调用、转交或冒充任何其他模型会话（§3 #2）。
- 若发现 F-A 至 F-D 任一事实与实际代码不符：**停止并报告**，不要将错就错地设计。
- 若阅读量将显著超出锚点范围，按 `agents/developer-discipline.md` §5 停止并报告。

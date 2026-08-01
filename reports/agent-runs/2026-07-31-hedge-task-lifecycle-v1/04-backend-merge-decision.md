# 04-backend-merge-decision —— P1 重裁与成本基保留

- stage: `2026-07-31-hedge-task-lifecycle-v1`
- 记录人：opus5（bookkeeper），2026-07-31
- 触发：Human 询问后端数据存储方式并提出「按标的存 map、现货合约同存、再与交易所持仓匹配」的思路（其 FMZ 策略的做法）。核查过程中发现 `11-adr.md` ADR-001 的核心前提不成立。
- 上游：`02-scope-decisions.md`（D1-D8）、`03-fake-ui-outcome-and-plan-scope.md`（D9-D13）。本文件记 D14-D15。

## 1. 被推翻的前提

`11-adr.md` ADR-001 判定「后端合并被事实堵死」，理由是 hedge 服务够不到 `private_account`，白名单冻结不可扩，后端合并须扩白名单或新增读路径 = **新增限频权重**。

**前半句成立，结论不成立。** 已核实：

| 事实 | 位置 | 内容 |
|---|---|---|
| F-A | `server.py:632-642` | `build_server` 把 `service`（`SnapshotService`，产出 `private_account`）与 `hedge_open_service` **注入同一个 `_Handler` 类**。处理 `/api/hedge-open-positions` 的 `_hedge_open_positions`（`server.py:607-608`）**两者皆在手**。 |
| F-B | `snapshot_service.py:237-257` | `get_snapshot()` 在 live 模式是**纯读已发布状态**，docstring 原文 `live: zero-upstream pure read of the published state`。**零上游请求、零新增限频权重**。 |
| F-C | 同上 | 首次发布前 live 读抛 `SnapshotNotReady`（server 映射 503）；offline 模式是同步 fixture 构建 + 60s 缓存。 |
| F-D | `snapshot.py:1097-1116` | `private_account` 不可用时形状已定义：`verified: false`、三个数组为空、`total_value_usdt` 等为 `null`、`error` 带原因（如 `private_channel_disabled`）。 |

即：**后端合并可在服务器层完成，不需要扩任何白名单，也不产生任何新的交易所请求**。ADR-001 所述的代价不存在。

真实取舍因此变为：后端做则合并逻辑在 Python（**可测**，ADR-001 自己承认 JS 侧「比 SQL 难测」）、口径唯一；代价是须处理 F-C / F-D 的降级，且要决定是改既有接口还是新开接口。前端做则零后端改动、fake 已验证、可逆；代价是逻辑在 JS 难测，且接口与界面两套数字。

## 2. Human 的决定

| # | 决策点 | Human 的选择 |
|---|---|---|
| **D14** | 合并放哪一层 | **改为后端做**（推翻 ADR-001 的 P1 裁定）。Human 在获知 F-A/F-B 后直接拍板，与其原有心智模型（策略层持有合并后的每标的记录）一致。 |
| **D15** | 被删除任务的成本基是否保留 | **保留**。修改 `aggregate_positions` 的 `WHERE t.status != DELETED`，让已删除任务的已成交腿仍计入。原 `10-design.md` 非目标 #7「本轮不改后端 `WHERE`」**作废**，该项移入本轮范围。 |

### D15 的依据

`PROJECT_STATE.md` 的 `[OPEN][MONEY-VISIBILITY]` 条目原文记着该问题「**becomes routine if auto-pause ever turns into auto-delete**」并标注「**Blocks that change**」。本 stage 的 ② 正是执行该转换。

原方案以「合并表以 `um_positions` 为骨架」为由不改后端 `WHERE`，只覆盖了**敞口可见性**，未覆盖**成本基**：被自动删除任务的 `spot_avg` / `perp_avg` 仍从 `aggregate_positions` 消失，合并表该行退化为「无任务记录」—— 用户看得到持仓、看不到入场价，且 ② 落地后成为常态。

Human 采纳保留。这同时正面回应了 `PROJECT_STATE.md` 中被标为阻塞的那条记录。

## 3. Human 原提问的答复（存档，供后续参考）

Human 问：能否改成 FMZ 策略那样「按标的存 map、现货与合约开单信息同存一条、再与交易所持仓匹配」。

**后端当前存法**（四层）：

| 表 | 一行代表 | 关键字段 |
|---|---|---|
| `hedge_open_task` | 一张任务卡 | `coin`（全称如 `BTCUSDT`）、`direction`、`target_n`、各计数器、`status`、`pause_reason` |
| `hedge_open_attempt` | 一组下单（一对腿） | `task_id`、`attempt_seq`、`pair_outcome`、错误、`rate_limited` |
| `hedge_open_leg` | 一条腿 | `client_order_id`、`exchange_status`、`cumulative_base_qty`、`cumulative_quote_amt`、`avg_price`、`fee_*`、`terminal` |
| `hedge_open_fill` | 一组的汇总（**遗留**） | `spot_*` 与 `perp_*` 两套字段**同行** |

`hedge_open_fill` 即 Human 描述的存法，是项目早期设计，现作为遗留数据继续读取。演进为 attempt + leg 两层的原因：**两条腿生命周期不同步**（各自可能多次查询才终态、可能部分成交、可能单腿成功），同行存储导致无法各自推进。

**结论**：不改存储结构。理由三条 ——

1. 「就地累加改写」丢失原始记录：任一次写失败或崩溃即造成永久且不可追溯的错误。现行设计保留每条腿原始成交、读时现算，重启后重算仍正确。此为上一 stage「未知不得当零」教训（币安返回 `"0.00000"`）的直接产物。
2. FMZ 脚本是「一币一策略实例」，本项目是「任务清单」模型，允许同币多卡；塞回单条记录需先解决多卡合并，即已被 D13 移出的同币双向问题。
3. 匹配真实持仓这一步与存储形状无关，改存储不会简化匹配。

**但 Human 直觉中正确的一半**：其 map 独立于任务生命周期，卡没了记录还在。该好处不需重构存储即可获得 —— 即 D15（改 `WHERE`）。Human 已采纳。

## 4. 对已备产物的影响

- `plan-hedge-task-lifecycle-v1` 的交付 `b370401` **不作废**，但其 P1、ADR-001、非目标 #7、以及 `12-development-breakdown.md` 的 Task 1 需按 D14/D15 重写 → 新任务 `plan-revision-backend-merge-v1`。
- `plan-review-deepseek-v1.dispatch.md` **已备但未交付**，其评审对象 `b370401` 将被修订版取代 → 该 packet 作废，修订完成后按新 `delivery_sha` 重新签发。
- 计划评审的返工按 `AGENTS.md` §8 **不触碰 `rework_count`**；本次修订源于 Human 决策变更与 packet 事实更正，同样不计。当前 `rework_count` 保持 `0`。
- 顺带修掉：`11-adr.md` ADR-001 引用 `index.html:2106` 有误（`directionForPosition` 实际在 `:2198`）—— ADR-001 本就要重写，该错误随之消失。

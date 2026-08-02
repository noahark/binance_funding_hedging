# 35-review-1-gpt-task3-r3 —— review-1 复审（GPT）

## 评审元数据

- 任务：`review-1-gpt-task3-r3`
- 角色：Reviewer / review-1，REWORK 后第 3 轮穷举复审
- provider：openai
- 固定区间：`9faa716396cbbe67ebeec272ad6b3dd443bba583..d2ac353caf22a68c6ff59a45167280365ace5a95`
- 受审交付：`d2ac353caf22a68c6ff59a45167280365ace5a95`
- 当前 `HEAD`：`80a763a7361936864d9f850a809215e7425bcfff`；评审未移动 `HEAD`，结论只基于固定区间和只读检查。
- 风险：`HIGH_RISK`（订单状态、暂停/删除粘性、实盘发布门）。

## 总结

评审结论为 `ACCEPT`。

本轮对 F2-P1 家族的 1a/1b/1c/1e/1f 逐站点复核通过。`pause_task` 的条件写覆盖了 drain 429、insufficient/collateral、order-state-unknown 以及共享的 dispatch 暂停路径；其返回值从单个 task 改为 `(updated_task, applied)` 后，唯一生产调用方已正确解包。条件未命中时不改状态、不刷新旧快照，但仍记录事件。`stop_task_fatal` 的返回形状未改变，fatal preflight 也使用了同样的状态条件。

`suppress_done` 只关闭暂停类终态结算中的“达到计划数即兜底置 done”分支，不是全局禁止 done；正常成功、正常失败/单腿、重试收口和非暂停类结算仍保留既有 done 逻辑。F1-P1 未被本轮触碰，Human 已接受的事实基础经本轮独立扫描仍成立。未发现本轮修复新增接缝。

## F1-F5 逐条结论

| 项 | 结论 | 复审判断 |
|---|---|---|
| F1 | 已按既定范围成立；F1-P1 为已接受限制 | 每腿重试计数、上限收口、重启清零和不重发路径未被本轮改动；下文独立核验 F1-P1 的接受前提。 |
| F2 | **真正修复** | 1a/1b/1c/1e 条件写及 1f 结算顺序均闭合，见逐站点表。 |
| F3 | 无回归 | 本区间未改 entries 投影语义；既有 `task_paused` 映射证据保持有效。 |
| F4 | 无回归 | `verdict is None`、畸形 2xx 和人工核对事件路径均保留。 |
| F5 | 无回归 | 间隔迁移、有效间隔和展示形状未被本区间生产改动影响。 |

## F2-P1 逐站点判定

| 站点 | 范围分类 | 判定 | 证据与边界 |
|---|---|---|---|
| 1a drain 429 | `pre-existing-release-critical`；base 上 `pause_task` 旧实现由 `ab3126d7` 引入 | **pass** | `_worker_round` → `_pause_task_local` → 条件 `pause_task`；并发删除回归确认最终仍为 `deleted`，未重发，`rate_limited` 事件仍在。 |
| 1b drain insufficient / collateral_cap | `pre-existing-release-critical`；同一旧 `pause_task` 站点，base blame 为 `ab3126d7` | **pass** | 与 1a 共用根修；insufficient 并发回归确认不复活为 `paused`，事件仍可见。真实查询接口只返回订单状态/明确不存在，暂停分类主要来自下单返回；测试注入的 drain 分类也走同一条件写。 |
| 1c drain order_state_unknown | `in-range` | **pass** | service 层先看权威状态，store 层再用 `WHERE status IN (running, paused)` 条件写；并发删除回归确认 `deleted` 粘性、腿保持非终态、无重发、人工核对事件保留。 |
| 1e fatal preflight | `pre-existing-release-critical`；base 上无条件 `stop_task_fatal` 由 `8af3f22d` 引入 | **pass** | preflight 无锁读取期间删除任务，条件 `stop_task_fatal` 不再写回 `stopped`；`task_stopped` 事件仍记录，任何 POST 均未发生。 |
| 1f pause-class settlement → done | `in-range`；由本轮条件写与既有 done 规则交互确认 | **pass** | `_dispatch_live` 的无 querying 暂停类终态结算传 `suppress_done=True`，先保留暂停落点；随后条件 pause 可以命中。破坏该参数会使既有 4 条暂停回归失败。 |

共享路径 1d（dispatch 阶段 429/insufficient）复用 `_pause_task_local`，因此与 1a/1b 同一条件写覆盖；没有另造第二个状态写点。`set_task_status` 仍只由人工 API 入口调用，入口先读权威状态并做状态校验，不属于旧 worker 快照写族。

## 四项重点

### 1. 条件写是否覆盖全族，含返回值形状变化

结论：覆盖。

- `pause_task` 的 SQL 现在只允许当前状态为 `running` 或 `paused`；未命中返回 `(None, False)`，命中返回 `(task, True)`。
- `_pause_task_local` 是唯一生产调用方，已按新形状解包；只有 `applied=True` 且 task 非空时才更新本地快照。
- 429、insufficient、collateral、order-state-unknown 和共享 dispatch 暂停路径均汇入该调用方；条件未命中后仍统一写 task event，因此不会静默丢失闭环证据。
- `stop_task_fatal` 仍返回 `dict | None`，调用方保持原有单值接收；其 SQL 同样限制在 `running/paused`。
- store 条件测试覆盖 running 命中、paused 幂等命中、deleted/done/stopped 未命中；四条真线程回归覆盖查询/预检网络调用期间的外部删除交错。

### 2. `suppress_done` 是否误伤既有 done 收口

结论：没有误伤。

`suppress_done` 只参与 `_apply_task_counters` 的独立兜底分支：`pair_outcome != None`、当前仍为 `running`、且 `scheduled_attempt_count >= target_n` 时把任务置为 `done`。它不抑制：

- 成功 pair 通过 `resolve_status_after_attempt` 到达目标后的正常 `done`；
- 非暂停类失败/单腿在最后计划尝试后的既有 `done`；
- `finalize_attempt` 的普通查询收口；
- 默认不传该参数的正常 dispatch、模拟和恢复路径。

暂停类下单结果需要例外：若先按计划数自动置 `done`，之后的条件 pause 会因 `done` 不在允许集而落空。因此只在 `_dispatch_live` “两腿已终态、已有暂停类事实”的分支传 `True`。计数和 attempt 结算仍发生，只抑制这一次与暂停冲突的兜底 done。正常 done 测试、暂停测试以及全套回归均通过；破坏 `suppress_done` 会使 `test_4[-2019]`、`test_4[-3041]`、`test_4c`、`test_4g` 转红，说明该参数是必要接线而非冗余开关。

### 3. F1-P1 Human 接受的事实基础

结论：接受前提在当前交付中仍为真，且本轮没有触碰该限制。

独立扫描结果：

- `ensure_worker` 的生产触发点是人工 `post_start`、`post_fill_once`、`post_fill_all`，以及服务启动时的一次 `_recover_workers`；后者是旧进程结束后的启动恢复。
- live `tick()` 明确是安全空操作，不扫描任务、不启动 worker、不做自动重试。
- 前端自动刷新只 GET 快照、任务列表、持仓和设置；暂停、启动、删除、成交一次、成交全部都由按钮动作触发。`mutateHedgeTask` 没有自动重试下单；前端的 drawer retry 也是只读查询。
- 未发现定时器、后台恢复循环、API 组合调用或前端自动 retry 会在人工动作之外调用 `ensure_worker`。

因此 Human 记录的接受条件——当前仅人工触发，若未来加入自动重启、自动补单、定时重试等非人工 `ensure_worker` 路径则重新评估——仍可核验。该限制不是本轮 F2-P1 的返工项。

### 4. 本轮修复是否引入新接缝

结论：未发现新的阻塞接缝。

本轮新增的主要交互正是 1f：条件 pause 写入后，原先的自动 done 规则会抢先结束任务；实现用局部 `suppress_done` 修复，并保留默认行为。除此之外：

- 返回值形状只在一个生产消费者处改变，测试消费者同步更新；
- 条件未命中不更新本地旧快照，事件仍记录，下一轮重新读权威状态；
- fatal preflight 使用独立条件写，不改变正常下单、查询、429 分类或 51169 语义；
- diff 未触碰 `frontend/`、`backend/services/live_hedge_executor.py` 或 `data/`，没有新增 worker、状态枚举或数据库列。

## 验收与边界检查

| 检查 | 结论 | 证据 |
|---|---|---|
| 固定 SHA | pass | 已核验 `9faa716..d2ac353`；未移动 HEAD。 |
| F2-P1 关键回归 | pass | 条件写、1a/1b/1c/1e、暂停类和正常 done 组合共 `16 passed in 6.37s`。 |
| 项目测试 | pass | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider backend/tests -q` → `1158 passed in 69.57s`。 |
| 调用方/边界扫描 | pass | `pause_task` 仅一个生产调用方且已解包；1d 复用；无 frontend、live executor、data 区间改动。 |
| F1-P1 触发路径 | pass | `ensure_worker` 生产调用点与前端/调度器扫描符合 Human 接受条件。 |
| diff hygiene | pass（范围外例外） | `git diff --check` 仅命中早期控制报告 `23-cadence-implementation.md:82` 尾随空格，不是本轮受审生产交付。 |

根目录直接运行 pytest 会额外收集历史 archive 中不属于本阶段的旧测试并在导入阶段失败；正式项目测试按 dispatch 口径限定为 `backend/tests`，结果如上，不把 archive 失败归因于本交付。

## 已知限制与发布门

- F1-P1 的计数清理/同任务 worker 交接限制仍存在，但已由 Human 按事实、影响、接受理由、观察方式和复看条件明确接受；未来出现非人工 `ensure_worker` 路径时必须重新复审。
- BK-T3-002 的历史 live DB 写入事故仍是独立发布门。本轮没有新增 `data/` 写入，也没有消除历史事故；合并、部署或实盘启用仍须 Human 单独授权。

## 评审闭环

评审结论: ACCEPT（接受）
问题记录: reports/agent-runs/2026-07-31-hedge-task-lifecycle-v1/35-review-1-gpt-task3-r3.md#已知限制与发布门
修复要求: none

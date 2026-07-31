# 09-delivery：2026-07-31-hedge-task-inline-log-v1

> 实现者 claude_glm，交付时间 2026-07-31 16:37 CST。
> base_sha `42de1aff`。计划评审 r4 已 ACCEPT（revision 9）。本报告为实现 + 自测证据。

## 实现摘要（对照 Goal）

1. **任务卡内嵌日志（真实数据）**：`renderHedgeTaskCard` 在控件行新增「展开日志 ↔ 收起
   日志」toggle，展开后伸出该任务的尝试日志表格。列固定为进展 / 状态 / 成交时间 /
   合约订单号 / 现货订单号 / 合约均价 / 现货均价 / 合约数量 / 现货数量 / 错误原因，
   倒序（最新在上）。数据来自 `GET /api/hedge-open-logs?task_id=…` 的 `attempts`。
   - 「进展」= `attempt_seq / target_n`（`target_n` 取自任务卡；未用 `scheduled_attempt_count`）。
   - 展开状态记入 `state.hedgeLogExpanded`（既有 `Set`），跨自动刷新保持。
2. **`#task-id`**：回归确认既有实现仍生效（`index.html:4216` 真卡卡头 `#${idAttr}`）。
3. **移除 fake**：删除 `renderHedgeTaskCardFake` / `HEDGE_FAKE_TASK_ID` / `showFakePreview`
   分支，全量搜索零残留。

### 展示口径决策（Human 可推翻，均为局部改动）

- **成交时间门控**：仅当至少一腿已受理（`order_id` 存在）时展示 `attempt.ts`（北京时间，
  复用 `hedgeLogEntryTimeTime`）；否则 `—`。理由：列名为「成交时间」，对未成交行（进行中/
  确认失败）挂时间会被读成「已成交」，触碰「钱的展示」硬约束。`attempt` 投影里只有创建时间，
  没有成交时间，故以创建时间为最接近代理（与既有 attempt 时间线卡同源）。**与 fake 原型的
  差异**：fake 的进行中/失败行时间为 `—`，此处对「无 fill 的失败行」也保持 `—`、对「有 fill
  的单腿/已受理」展示时间——与 fake 一致。
- **`accepted_pair` 文案「已受理」**：既有常量已是「已受理」（保守文案，非 fake 的「已成交」）。
- **`single_leg` badge `warning`→`warn`**：`index.html:3567` 一行修复。CSS 只定义了
  `.badge.warn`（`:229`），`.badge.warning` 是失效样式（既有 `HEDGE_PAIR_OUTCOME_BADGE`
  里写错）。本表格正确展示的必要条件，顺带使既有 attempt 时间线卡的 `single_leg` 徽标也生效。
- **错误原因回退链**：`error_reason_zh` → 机器字段 `error_category / error_code`（原样）→
  失败/单腿行固定占位「原因未记录」；`accepted`/进行中无错误数据为 `—`。前端不编造中文业务句。
  （`error_reason_zh` 经常是 `NULL`——`store.py:1088`，非 fatal rollup——这是既有事实，不改写入。）
- **`task_id` 读语义**：无 `task_id` 响应契约不变；有 `task_id` 时 `attempts` = 该任务全部
  attempt + 两腿一次返回，`logs`/`entries` 为空、游标 `None`（内嵌表只消费 `attempts`，
  避免与全局/entries 游标混用——amendment 17 已证共用会重演 R4 缺陷）。
- **刷新策略**：随既有 60s 快照 tick 重取已展开任务的日志（在 `loadHedgeTasks` 内，刷新前
  重取 → 再渲染，故展开表在 tick 后保持新鲜），**未新增任何轮询定时器**（self-check「零新任务
  定时器」断言仍过）；展开时即拉取（toggle 打开触发 `loadHedgeTaskLogs`）。

## 改动文件（全部在 Allowed Files 内）

```
 backend/app/server.py               |   5 +-    # _hedge_open_logs 解析可选 task_id 并透传（仅读路径）
 backend/hedge_open_tasks/service.py |  28 ++-    # get_logs 加 task_id 早返回；attempt_to_doc 投影 3 个 error 字段
 backend/tests/test_hedge_service.py |  60 ++-    # 新增 task_id 全量取数 + attempt_to_doc error 投影 测试
 frontend/index.html                 | 205 ++--    # 真卡内嵌日志表 + helpers + 移除 fake
 frontend/self-check.js              | 160 ++-    # AC1-AC9 自检 + mock task_id 槽
```

**未触碰 `store.py`**：`list_attempts_for_task`（`:1403`）与 `list_legs_for_attempt`
（`:1394`）已存在，直接只读组装，无需改 store。

## 后端只动读路径（AC10）

- `server.py`：仅 `_hedge_open_logs` 多解析一个 `task_id` query 参数并透传 `get_logs`。
- `service.py`：`get_logs` 在 `task_id is not None` 时早返回该任务 attempt 组装结果（
  `list_attempts_for_task` + `list_legs_for_attempt` + `attempt_to_doc`，全部既有只读方法）；
  `attempt_to_doc` 投影新增 `error_category`/`error_code`/`error_reason_zh`（取自 `_row_to_attempt`
  既有列）。未触碰状态机、调度、结算、计数器、暂停/删除、worker 生命周期。

## 验收逐项（Acceptance Checks）

| # | 项 | 结果 | 证据 |
|---|---|---|---|
| 1 | 四状态渲染（进行中/info、已受理/success、已确认失败/danger、单腿成交/warn） | pass | self-check 86a |
| 2 | 钱原样透传（均价 `120.70000000`/`120.70300000` 含尾零，未经 formatHedgeDecimal） | pass | self-check 86a |
| 3 | 未受理腿门控（`order_id` 缺失 → 订单号/均价/数量三格 `—`，无裸 `<td>0</td>`） | pass | self-check 86a |
| 4 | 错误回退链（zh 原文 / 机器字段原样 / 「原因未记录」） | pass | self-check 86a |
| 5 | task_id 全量取数（51>50，一次返回，不混 entries_cursor） | pass | self-check 86b + pytest task_id |
| 6 | 进展 = `attempt_seq/target_n`，各行序号各异 | pass | self-check 86a |
| 7 | 展开状态跨刷新保持 + 无新定时器 + 真卡 toggle 已绑定 | pass | self-check 86a/86b + 零定时器断言 |
| 8 | `#task-id` 可见（既有实现） | pass | `index.html:4216` |
| 9 | fake 已清干净（全量搜索 0 残留） | pass | `grep -c` = 0 |
| 10 | 后端只动读路径 | pass | 见上节 + diff --stat |
| 11 | 回归：self-check 全过；pytest backend/tests 全过 | pass | 原始输出见下 |

## 原始测试输出

```
$ python3 -m pytest backend/tests -q
........................................................................ [ 91%]
........................................................................ [ 97%]
........................                                                 [100%]
1104 passed in 57.84s

$ node frontend/self-check.js | tail -3
[PASS] fetch 同源白名单（含开单 §3 路由）、零 Binance/外域、零新任务定时器、localStorage 白名单（仅隐私键）
全部自检通过
```

新增后端用例：`test_attempt_to_doc_projects_error_fields`、
`test_get_logs_task_id_returns_all_attempts_unpaged`（均 pass）。
新增前端用例：86a（AC1/AC2/AC3/AC4/AC6/AC7/AC9）、86b（AC5/AC7）（均 pass）。

## 未做 / 边界

- 未触碰 Stop 列出的任何项：未写 live DB、未下真实单、未碰凭据/闸门/部署；未做任何「任务卡
  卡住」相关修复；未改状态机/PAUSE_REASON/aggregate_positions/计数器/结算。
- 未改 `_leg_to_doc` 的 `"0"` 投影；未改 `error_reason_zh` 写入语义；门控/回退链均在前端读侧。
- 未新增 API 路由（`task_id` 是既有 `/api/hedge-open-logs` 上的可选参数）。
- 自测完成，停下回报；未启动评审终端、未合并、未推送。

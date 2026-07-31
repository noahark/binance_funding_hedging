# 07：计划评审 round 3 verdict（新范围首评，grok / xai，2026-07-31 15:43:37 CST）

> 落盘说明：本文件由 Human 授权将 grok 计划评审终端原文归档，供 Bookkeeper（opus5）核验。
> 计划评审终端本身只读；**是否封存、是否改 `00-task.md` / `status.json` 由 Bookkeeper 裁定**。
> 本文件不计入 `rework_count`（计划评审 verdict，`AGENTS.md` §8）。

`评审结论: REWORK`。受审对象：`00-task.md`（`status_revision: 6`，范围收窄后的新 packet）。
dispatch：`02-plan-review.dispatch.md`（task_id `…-plan-review-r3`）。
基线：`base_sha = 42de1aff364e7c979d2fbb5dc56f1dec65287cc7`。

**披露（按 dispatch 原样要求）**：计划评审与 review-1 同为 grok / xai，本轮已参与计划批准。
跨 provider 满足（xai ≠ 实现作者 zhipu_glm）；终审 review-2（codex / openai）未参与设计。

---

## 总判

收窄后的 packet **方向正确**：只做任务卡内嵌真实日志 + 可选 `task_id` 读过滤，HIGH_RISK 与
文件边界成立，后端「只动读路径」可执行。

但有 **三条阻塞** 会在实现或验收时卡死（进展列字段误指、错误原因硬约束与数据现实冲突、
未受理腿 API 的 `"0"` 未钉前端门控）。须修订 packet 后再实现；**不要**把这些塞进实现时
「自行理解」。

---

## 三条阻塞发现

### R3-F1 —— 进展列字段误指 `scheduled_attempt_count`（阻塞）

**事实**

- packet Goal 1 / AC6 写：进展 = `scheduled_attempt_count / target_n`。
- fake 原型（`frontend/index.html:4240-4249`）每行是不同的 `n/10`（4/10、3/10、2/10、1/10），
  对应的是**该次 attempt 序号**，即 `attempt_seq / target_n`。
- `scheduled_attempt_count` 是任务级计数器，用它填进展列则**每一行数字相同**（例如全是
  `4/10`），与 fake 语义和用户预期都不符。

**修订要求**

- Goal 1 与 AC6 全文改为：进展列 = `attempt_seq / target_n`（每行该次序号 / 该任务计划次数）。
- 删除「用 `scheduled_attempt_count` 填进展列」的表述。`scheduled_attempt_count` 仍可在
  任务卡摘要行展示（现有 `countersLine` 已展示），但不是日志表「进展」列。

---

### R3-F2 —— 错误原因硬约束与数据/投影现实冲突（阻塞）

**事实**

1. 硬约束与 AC4 要求：失败与单腿成交行**必须**有错误原因，不得留空或 `—`。
2. `attempt_to_doc`（`backend/hedge_open_tasks/service.py:239-265`）**不投影**
   `error_reason_zh` / `error_code` / `error_category`。若前端只用 `attempts` 数组，
   错误列根本没有字段来源。
3. `entries` 路径的 `_attempt_to_entry`（同文件 `:817-819`）有 `error_reason_zh`，但：
4. 写入侧（`store.py:1085-1095`）对非 fatal 的 leg rollup 常写
   `error_reason_zh = None`（单腿、普通确认失败亦然）。fatal 才写
   `stop_reason_zh`；dry-run 仅 offline constraint 等少数路径带中文原因。
5. 因此 AC4「凡失败/单腿行必有非空中文原因」在**只读范围**内经常无法满足；前端编造
   中文又违反既有「字段缺失逐项降级，绝不补造」（`index.html:4396` 一带约定）。

**修订要求（只读范围可落地）**

1. 钉死错误列主字段：`error_reason_zh`（须在读投影中带上——扩展 `attempt_to_doc` 加算
   字段，或明确内嵌表改用 `entries` 同源字段；二者皆为读路径）。
2. 钉死回退链（**禁止前端编造中文业务句**）：
   `error_reason_zh` → 否则展示 `error_code` / `error_category`（机器字段原样）→
   仍无则固定占位「原因未记录」（或 packet 明确允许此时显示 `—`）。
3. AC4 改为可构造：夹具使用**后端已写入** `error_reason_zh` 的失败/单腿行，断言展示该
   字符串；另测回退链。
4. Stop 增补：禁止为填满错误列去改结算/写路径 / `error_reason_zh` 写入语义。

---

### R3-F3 —— 未受理腿 API 已是 `"0"`，未钉前端门控；AC3 断言过宽（阻塞）

**事实**

- 硬约束与 AC3：未受理腿显示 `—`，绝不显示 `0`（踩过 51061→0 的坑）。
- `_leg_to_doc`（`service.py:214-229`）：
  `base = Decimal(leg.get("cumulative_base_qty") or "0")`，
  再 `cumulative_base_qty: fmt_decimal(base)` → 未成交/未受理腿在线上常为 **`"0"`**，
  不是 `null`。
- `hedgeText("0")`（`index.html:3602-3605`）只把 null/undefined/'' 降为 `—`，**会显示 `0`**。
- AC3 写「页面上不出现 `0`」过宽：任务卡计数器等合法 `0` 会被误伤。

**修订要求**

1. 钉死门控：该腿 `order_id` 缺失/null → 订单号、均价、数量单元格一律 `—`，即使
   `cumulative_base_qty === "0"` 或 `avg_price` 缺失。
2. AC3 断言范围改为「该日志行、该未受理腿的金额/订单号单元格」，勿写整页无 `0`。
3. 日志金额列渲染钉 `hedgeText` 原样透传；禁用 `formatHedgeDecimal` / `hedgeNum` 做金额格
   （`formatHedgeDecimal` 会去尾 0，与「数值原样透传」冲突）。

---

## 建议修改（不单独阻塞，但应写入 packet 以免实现分叉）

### R3-F4 —— `task_id` 过滤与「全部尝试」语义未钉死

**事实**

- 可选 `task_id` 正确且必要（r1/r2 已确认）；禁止只滤全局当前页。
- `list_attempts_for_task`（`store.py:1403-1410`）**只返回 attempt 行，不带 legs**；
  `list_attempts_page` / `list_attempts_entries_page` 才附 spot/perp。
- `list_legs_for_attempt`（`store.py:1394-1401`）已存在，可只读组装。
- 双游标：legacy `cursor/limit` 与 `entries_cursor/entries_limit` 独立（amendment 17 /
  R4 修复）。`task_id` 模式如何与之共存未写。
- `LIMIT_DEFAULT=50`，`LIMIT_MAX=200`（`domain.py:518-520`）；`target_n` 仅校验 `>=1`，
  无上限。AC5 要求 attempts 超过默认页大小时仍「全部可见」。

**建议钉死**

1. 无 `task_id`：响应契约不变。
2. 有 `task_id`：`attempts` = 该任务**全部** attempt + 两腿（`list_attempts_for_task` +
   每 attempt `list_legs_for_attempt`，或等价只读 join）；**不**与 `entries_cursor` 混用
   分页；一次返回全量以满足 AC5。
3. `logs` / `entries` 是否同滤：建议写明「以内嵌表消费的 `attempts` 为准；其余流可原样
   或同滤，但不得用共享游标重蹈 R4」。
4. AC5：夹具 attempts 数 > 50，一次 `task_id` 响应含全部。

### R3-F5 —— 状态中文/徽标与既有映射冲突

| pair_outcome | fake 文案 | 既有 `HEDGE_PAIR_OUTCOME_LABELS` | 建议 |
|---|---|---|---|
| null / querying | 进行中 | 查询中 | 二选一写死 |
| accepted_pair | 已成交 | 已受理 | **钱相关**：域语义是双腿有 orderId（受理），非必「完全成交」；建议用「已受理」或明确产品接受「已成交」的误读风险 |
| confirmed_failed | 失败 | 已确认失败 | 二选一写死 |
| single_leg | 单腿成交 | 单腿成交 | 一致 |
| badge | fake 用 `warn` | 既有用 `warning` | CSS 仅有 `.badge.warn`（`index.html:229`）→ 钉 `warn` |

须在 packet 给一张冻结映射表（文案 + badge class）。

---

## Goal 八项逐条（对照 dispatch）

| # | 项 | 判断 | 依据摘要 |
|---|---|---|---|
| 1 | 收窄是否干净 | **pass** | `00-task.md` r6 无 Goal3/4/F10/暂停→删除/持仓/51169 残留；Stop 明确禁止。`PROJECT_STATE.md` Next Priority 仍写 F10 属状态文档滞后，不阻塞本 packet。 |
| 2 | 【钱】四条硬约束是否够 | **fail（阻塞）** | 方向对；R3-F1/F2/F3 未堵住误读/不可验收。第五种误读见下「观察」。 |
| 3 | 按任务过滤设计 | **pass-with-gaps** | 可选 `task_id` 正确；R3-F4 补 legs 组装与全量语义。 |
| 4 | 后端只动读路径 | **pass** | AC10+AC11+看 diff 可执行；加算 `error_*` 投影仍属读路径；禁止为错误列改正文写路径。 |
| 5 | 验收可执行 | **fail（随 F1/F2/F3）** | AC6 字段错；AC4 与数据冲突；AC3 过宽；AC1 缺映射表。AC7–11 大体可执行。 |
| 6 | HIGH_RISK | **pass** | 展示价量单号=账务信息；新功能+读 API 参数变更，非 §8 纯文档机械改动。 |
| 7 | 文件边界 | **pass** | 前端两文件 + server/service/store 读路径 + tests + stage 证据；`domain.py` 不改合理。 |
| 8 | 未识别风险 | **pass（已列）** | 见下。 |

### 第五种误读 / 实现必撞（观察，非独立阻塞）

- 进行中行：空值显示 `—`（fake 已示）。
- 部分成交：已受理且 `PARTIALLY_FILLED` 应显示真实 qty/均价，勿因未终态整行清空。
- 时区：API 为 UTC ISO；fake 为 `07-31 12:40:15`；建议钉「原样 ISO 或统一本地化」。
- 真卡 `#task-id` 已在 `index.html:4207`（Goal 2 可能已满足，AC8 作回归）。
- `bindHedgeTaskLogToggles` 现仅在 `showFakePreview` 时绑定（`:4159`）；真卡必须改绑定。
- 展开后刷新策略：随现有 tick 重取 vs 仅首次展开；**禁止新增轮询定时器**。

---

## Packet 修订清单（Bookkeeper 可直接照此改 `00-task.md`）

1. **进展列**：`attempt_seq / target_n`；改 Goal 1 + AC6。
2. **错误原因列**：主字段 + 只读回退链 + 收窄 AC4 + Stop 禁写路径。
3. **未受理腿门控**：`order_id` 缺失 → 订单号/均价/数量 `—`；AC3 收窄断言范围；金额用 `hedgeText`。
4. **`task_id` 读语义**：全量 attempts+legs；不与 entries 游标混用；AC5 夹具 >50。
5. **状态映射表**：pair_outcome → 中文 + `warn`/`success`/`danger`/`info`。
6. **日志金额**：禁用 `formatHedgeDecimal`/`hedgeNum` 渲染金额格。

---

## 原始 `[TASK_RESULT v2]`（终端回执，未改措辞意图）

```text
[TASK_RESULT v2]
任务 ID: 2026-07-31-hedge-task-inline-log-v1-plan-review-r3
执行结果: completed（完成）
结果摘要: 收窄干净、HIGH_RISK与文件边界成立；阻塞=进展列字段误指、错误原因硬约束与NULL现实冲突、未受理腿API"0"未钉门控。建议补task_id全量/legs组装与状态映射。REWORK不计入rework_count。披露：计划评审与review-1同为grok/xai，本轮已参与计划批准。
产物: [reports/agent-runs/2026-07-31-hedge-task-inline-log-v1/00-task.md, reports/agent-runs/2026-07-31-hedge-task-inline-log-v1/06-scope-reduction.md, backend/hedge_open_tasks/service.py, backend/hedge_open_tasks/store.py, frontend/index.html]
检查结果: [Goal1-收窄干净: pass; Goal2-钱展示四约束: fail(R3-F1/F2/F3阻塞); Goal3-task_id过滤: pass-with-gaps(R3-F4建议); Goal4-只读边界: pass; Goal5-AC可执行: fail(随F1/F2/F3); Goal6-HIGH_RISK: pass; Goal7-文件边界: pass; Goal8-未识别风险: pass(已列)]
阻塞项: [R3-F1 进展列须改 attempt_seq/target_n; R3-F2 错误原因源字段+只读回退链+收窄AC4; R3-F3 未受理腿 order_id 门控与 AC3 断言范围]
评审结论: REWORK（返工）
问题记录: inline-full-text（见本文件 R3-F1..F5 与 Goal 逐条）
修复要求: inline-full-text（见本文件「Packet 修订清单」1-6）
本地北京时间: 2026-07-31 15:43:37 CST
下一步模型: opus5（Bookkeeper）
下一步任务: Bookkeeper 核验本 verdict；按修订清单 1-6 改 00-task.md 并升 revision；封存本计划评审；再决定重派 plan-review 或派 claude_glm 实现（plan REWORK 不计入 rework_count）
[/TASK_RESULT]
```

---

---

## Bookkeeper 核验与处置（opus5，2026-07-31）

**已封存。** 本轮回执携带完整正文、发现清单（R3-F1..F5）与可执行修订清单（1-6），
符合 `AGENTS.md` §7。不计入 `rework_count`。

### 代码引用逐条复核：**六处全部属实**

| 引用 | 复核结果 |
|---|---|
| `attempt_seq` 存在且已投影 | 属实。`_row_to_attempt`（`store.py:243`）与 `attempt_to_doc`（`service.py:256`）都有；表索引 `store.py:137-138` 按 `(task_id, attempt_seq)` 建。**R3-F1 成立**——用 `scheduled_attempt_count` 填每行会让所有行同号。 |
| `attempt_to_doc` 不投影 `error_*` | 属实。`service.py:246-265` 只投 `task_id`/`attempt_id`/`attempt_seq`/`direction`/`q_common`/`pair_outcome`/`spot`/`perp`/`residual`/`ts`。**R3-F2 前半成立**。 |
| `error_reason_zh` 常为 `NULL` | 属实。`store.py:1088` 与 `:1093` 在非 fatal 时写 `None`。**R3-F2 后半成立**——原「必有非空中文原因」约束在只读范围内做不到。 |
| 未受理腿是 `"0"` 不是 `null` | 属实。`_leg_to_doc`（`service.py:214`）`base = Decimal(... or "0")` → `cumulative_base_qty: fmt_decimal(base)`；`hedgeText`（`index.html:3602`）只降 null/undefined/`''`。**R3-F3 成立**。（补注：`avg_price` 与 `cumulative_quote_amt` 在 quote 为 NULL 时确实是 `null`，只有数量列会显示 `0`——门控仍需按 `order_id` 做，判据不变。） |
| `list_attempts_for_task` 不带 legs | 属实。`store.py:1403-1410` 只 `SELECT * FROM hedge_open_attempt`；`list_legs_for_attempt`（`:1394`）存在可组装。**R3-F4 成立**。 |
| badge class 冲突 | 属实且更严重：`HEDGE_PAIR_OUTCOME_BADGE`（`index.html:3567`）把 `single_leg` 写成 `'warning'`，而 CSS 只有 `.badge.warn`（`:229`）——**既有的单腿徽标样式现在就是失效的**。**R3-F5 成立**。 |

### Bookkeeper 独立追加的两项

1. **Goal 2 已实现**：`#task-id` 在真卡卡头已存在（`index.html:4207`）。grok 标为
   「可能已满足」，经确认属实。Goal 2 已降级为回归验收，不再作为新工作。
2. **时间格式化有现成函数**：`hedgeLogEntryTimeText`（`index.html:4516`，北京时间）
   与 `renderHedgeLogEntryLeg`（`:4524`，已在用 `hedgeText` 逐字展示腿数据）可直接复用，
   已写入 packet，避免实现方自创格式。

### 修订清单 1-6 落实情况（`00-task.md` 升 `status_revision: 7`）

| # | 修订要求 | 落实 |
|---|---|---|
| 1 | 进展列改 `attempt_seq / target_n` | Goal 1 + AC6 已改，并显式禁用 `scheduled_attempt_count` |
| 2 | 错误原因主字段 + 回退链 + 收窄 AC4 + Stop 禁写路径 | 硬约束段重写（含读投影须补、`NULL` 现实、三级回退链）；AC4 改为三个用例；Stop 增禁令 |
| 3 | 未受理腿 `order_id` 门控 + AC3 收窄 + 金额用 `hedgeText` | 门控判据钉死；AC3 断言范围限定到三个单元格；禁用 `formatHedgeDecimal`/`hedgeNum` 入硬约束与 AC2 |
| 4 | `task_id` 全量 attempts+legs、不混游标、AC5 夹具 >50 | Inputs 增「读语义（钉死）」四条；AC5 改为 >50 且断言未共用游标 |
| 5 | 状态映射冻结表 | 已加冻结表（含 `accepted_pair` 取「已受理」的理由与 `warn` class 决定） |
| 6 | 日志金额禁用 `formatHedgeDecimal`/`hedgeNum` | 同 #3 |

另落实「第五种误读/实现必撞」观察项：时间格式复用、进行中行 `—`、**部分成交不得整行
清空**、渲染参照、展开刷新策略二选一且禁新增定时器、真卡 toggle 绑定须改。

### 上交 Human 的一个产品文案选择

`accepted_pair` 的中文，fake 原型写「已成交」，既有代码写「已受理」。packet 定稿取
**「已受理」**——域语义是两条腿都拿到 `orderId`（被交易所受理），不等于完全成交，可能
部分成交或仍在挂单。写「已成交」是更强的断言，用户会以为钱已经落定。Human 可推翻，
改动是一行。

---

## Bookkeeper 待办提示（grok 原文保留，非授权，仅导航）

1. 逐条复核 R3-F1 / F2 / F3 代码引用是否属实（建议点开 `service.py:214-265`、
   `store.py:1085-1095`、`store.py:1403-1410`、`index.html:3602-3651`、`:4240-4249`、
   `:4159`）。
2. 属实则修订 `00-task.md` → 升 `status_revision`，本文件标记封存。
3. 计划评审 REWORK **不**递增 `rework_count`。
4. 是否对修订后 packet 再跑一轮 plan-review，或 Human 认可后直接派实现：由 Bookkeeper
   + Human 决定（修订若仅消歧义、无新风险面，可论证直接实现；若改验收语义建议至少
   Bookkeeper 自核一遍修订落盘）。
5. **本归档未改** `status.json`（仍应由 Bookkeeper 写）。

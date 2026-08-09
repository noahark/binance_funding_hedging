# 平仓任务“两段式建卡 + 预检瘦身”整改方案（v2，待 Opus 5 复评）

- **日期**：2026-08-09
- **状态**：仅整改计划，未实现、未授权修改实盘资金路径
- **触发现象**：平仓任务卡 `a93405ae-2874-4e77-84eb-c0204e42cc7c` 点击创建后等待，卡片不能快速回显
- **v1 计划**：`docs/planning/close-task-preflight-simplification-2026-08-09.review-request-opus5.md`
- **v1 评审**：`docs/planning/close-task-preflight-simplification-2026-08-09.review-opus5-result.md`，结论 `REWORK`
- **源码基线**：`dc356cd7f6acdc8502cd6caa44a48f6e3c760cac`
- **风险路由**：`HIGH_RISK`，实施前必须取得独立跨 provider 计划评审 `ACCEPT`
- **计划作者**：Codex / OpenAI
- **复评模型**：Opus 5 / Anthropic，由 Human 启动独立只读终端

---

## 1. v2 结论

平仓改为两个明确阶段：

1. **创建卡片**：只做本地轻量校验，以现有 `paused` 状态和“待人工启动”原因入库，立即返回并在页面显示任务卡；不创建 worker、不读取交易所、不可能下单。
2. **Human 点击任务卡“启动”**：接口立即把卡片切为 `running` 并异步启动 worker；完整预检在 worker 内执行，启动按钮不等待。预检通过才持久化 attempt 并并发发送两腿，失败则在任何订单 POST 前暂停。

dispatch 不再采用 v1 的“只准缓存、禁止实时回退”。现有 exchangeInfo、price、balances、base free 继续保持“**缓存优先，缓存不可用时实时兜底**”。只删除 close 路径四项无效或可固化的读取：

- position mode 实时查询；
- PAPI order rate-limit 预读；
- Spot order rate-limit 预读；
- 普通现货账户 USDT 读取。

这样真正缩短的是用户等待卡片出现的 create 路径；启动后的正常缓存命中路径仍然零额外网络，缓存源异常时也不会永久失去平仓能力。

## 2. Human 新确认的运行前提

1. `.env` 中展示只读通道和 hedge 下单通道配置的是**同一把 Binance key，权限相同**；v1 评审所说的“两把不同权限密钥”在当前生产环境不成立。
2. 但两个配置变量仍走不同的代码入口，且 `private_channel_enabled` 可以关闭或刷新失败。因此，“key 相同”不代表 SnapshotService 缓存一定存在，dispatch 仍必须保留 hedge client 的实时兜底。
3. Human 不在建卡到启动、以及任务运行期间手工修改 position mode；账户维持一向仓 `BOTH`。
4. Human 的体验要求是：点击平仓确认后先快速看到任务卡；只有再次点击任务卡“启动”，系统才允许进入交易所预检和真实订单路径。

本方案不读取、不输出、不修改任何 `.env` 内容；上述内容作为 Human 给定的运行事实进入复评。

## 3. v1 REWORK 逐条整改

| Finding | v1 问题 | v2 整改 |
|---|---|---|
| F1 | close 禁止实时回退，SnapshotService 私有通道关闭时永久无法平仓 | 完全撤回 cache-only；所有现有市场/私有资金读取保持缓存优先 + hedge client 实时兜底；新增私有通道关闭仍能启动平仓的测试 |
| F2 | 删除每轮 snapshot base 门、只留首笔 helper，导致第 2..N 笔无余额保护 | forward base 门改为每个 attempt 前执行，计量为 `q_common × remaining_attempts`，落在 `prepare_attempt` 之前；不再使用 `single_amount × target_n` 代替 |
| F3 | 只看可空的 `symbol_match_type`，历史 NULL 可放行 1000x | 创建时纯查表轻量拒绝；dispatch 再做“固化值 OR `resolve_spot_identity(coin)`”双判，覆盖存量任务 |
| F4 | UM 持仓只比绝对值，符号相反或无行可能放行 | forward 必须是负持仓、reverse 必须是正持仓；数量需覆盖剩余计划量；无行、零、反号、解析失败均暂停；缓存 miss 时用 hedge client 实时兜底 |
| F5 | 没证明 open 实时回退不变 | 增加 open create + dispatch 逐项回归断言；本轮所有新增分支均限定 `task_type == close` |
| F6 | close 建卡不算 `q_common` 会改变 dry-run 数量 | 明确接受：dry-run close 使用原始 `single_amount` 记录、零 POST；实盘启动后必须用 fresh preflight 的 `q_common` |
| F7 | close snapshot 的 position mode 来源未写死 | 创建时继承 origin `position_side_mode`；为 NULL 时按 Human 固定前提填 `BOTH`；dispatch 只读任务固化值，不调用 position-mode API |

## 4. 阶段一：轻量创建并立即显示任务卡

### 4.1 创建时允许做的事

按顺序：

1. 后端信任边界校验：JSON、字段白名单、coin、direction、mode、task_type、正数 `single_amount`、整数 `target_n >= 1`；
2. SQLite 查询 `(coin, direction)` 活跃周期；无周期继续返回 `no_active_cycle`；
3. 读取周期首个开仓任务，继承 `spot_symbol`、`spot_base_asset`、`symbol_match_type`、`position_side_mode`；
4. 对 coin 调用纯本地 `resolve_spot_identity`：若固化值或当前映射任一判为 `multiplier_strip_alias`，快速拒绝创建并提示 1000x 自动平仓未支持；
5. 创建 close 任务：
   - `status = paused`；
   - `pause_reason = awaiting_manual_start`；
   - 中文显示“平仓任务已创建，点击启动后才会校验并发送订单”；
   - `q_common = NULL`、`preflight_snapshot = no_preflight_snapshot`；
   - `position_side_mode = origin.position_side_mode or BOTH`；
6. 返回 `201`。前端把返回任务立即放入 `state.hedgeTasks`，显示卡片并启用“启动”。

### 4.2 创建时明确禁止的事

- 不调用 `check_symbol_legs`；
- 不调用 `get_snapshot` / `compute_preflight`；
- 不读取 exchangeInfo、ticker、余额、UM position、position mode、rate limit；
- 不划转资产；
- 不创建 attempt；
- 不启动 worker；
- 不发送订单。

创建路径的性能验收以“外部读取调用数为 0”为准，不制定依赖机器负载的毫秒阈值。

### 4.3 不新增状态词汇

复用现有 `paused` 状态，因为当前页面已经：

- 对 `paused` 卡启用“启动”按钮；
- 对非 `running` 卡禁用“暂停”按钮；
- 展示后端 `pause_reason_zh`；
- `post_start` 已经是“改为 running、启动 worker、立即返回”的异步入口。

只新增一个 pause reason，不新增 schema、任务状态或恢复协议。`post_start` 成功后，现有 `set_task_status` 清空初始 pause reason。

### 4.4 防止绕过“先启动”

当前 live `fill-once` / `fill-all` 也能把 paused 卡切到 running。对于 `pause_reason == awaiting_manual_start` 的 close 卡：

- 前端禁用“成交1次 / 立即成交所有”；
- 后端 `_require_fillable` 同样拒绝，不能靠直接 API 绕过；
- 只有 `/start` 可以完成第一次人工启动；
- 已经启动过、后来因普通原因 paused 的任务，恢复和 fill 行为保持现状。

## 5. 阶段二：点击启动后的异步预检与发单

### 5.1 启动接口

`POST /api/hedge-open-tasks/<id>/start`：

1. 沿用现有 deleted/done 状态规则；本轮不改变 open 或其它 paused/stopped 任务的 start 语义；
2. 将任务改为 `running` 并清除 `awaiting_manual_start`；
3. 调用既有 `ensure_worker(task_id)`；
4. 立即返回任务文档，不同步等待任何交易所 GET/POST。

worker 随后执行预检。预检失败时任务从 running 变回 paused，卡片显示具体中文原因；Human 修复原因后可再次启动。

### 5.2 每个 attempt 的固定顺序

1. **1000x 双判**：固化 `symbol_match_type` 或当前静态映射任一为 multiplier → 暂停、零 attempt、零 POST；
2. **fresh snapshot**：读取两腿 filters、交易状态、价格和方向性余额；所有既有源保持缓存优先 + 实时兜底；
3. **position mode**：close snapshot 使用任务固化值，NULL 才填 `BOTH`，不发 position-mode GET；
4. **无用读取跳过**：close 不读取 PAPI rate limit、Spot rate limit、普通现货 USDT；
5. **计算数量**：Decimal 计算 `q_common`，校验两腿 step、min/max qty、minNotional；
6. **UM 持仓门**：先读 SnapshotService `um_positions`；缺失/过期时调用 hedge executor 的 `query_symbol_um_qty` 实时兜底；
7. **forward base 门**：仅 forward close 执行，所需量为 `q_common × (target_n - scheduled_attempt_count)`；
8. 所有门通过后才 `prepare_attempt`，持久化 attempt、两腿 client order ID 和 preflight fingerprint；
9. 并发发送两腿；交易所拒单、限频、状态未知继续沿用现有 reconcile/暂停。

任何启动后校验失败都必须发生在 `prepare_attempt` 之前，保证 attempt 不增加、两腿 POST 都为 0。

### 5.3 保留“缓存优先 + 实时兜底”的源

以下不再引入 close 专用 cache-only 模式：

| 数据 | 缓存命中 | 缓存 miss/坏形状/过期 |
|---|---|---|
| Spot/UM exchangeInfo | 直接使用，零网络 | 沿用公开 API 实时兜底 |
| `price_map` | 直接使用，零网络 | ticker 实时兜底 |
| `unified_balances` | 直接使用，零网络 | hedge client `/papi/v1/balance` 实时兜底 |
| `spot_balances` base free | 直接使用，零网络 | hedge client `/api/v3/account` 实时兜底 |
| `um_positions` | 方向和数量满足时直接使用 | hedge executor 实时查该 symbol UM qty |

Human 给定的“两处 env 使用同一 key/权限”降低了凭证差异风险；保留兜底解决的是缓存生产通道关闭/失败，不是 key 权限差异。

### 5.4 close 路径删除的四项读取

| 读取 | 替代事实 |
|---|---|
| position mode API | origin task 固化值；NULL → Human 固定前提 `BOTH` |
| PAPI rate-limit API | 不参与任何 preflight 计算；真实 429/418 后处理 |
| Spot rate-limit API | 同上 |
| Spot account USDT | forward close 卖 base 不需要；reverse close 走统一账户 USDT |

本轮只让 close 跳过；open 行为和实时回退保持不变。暂不顺手删除 live client 方法、store 字段和 open 侧调用，避免扩大高风险 diff。

### 5.5 UM 持仓门的可执行判据

计算 `remaining_qty = q_common × (target_n - scheduled_attempt_count)`：

- forward close：必须 `positionAmt < 0` 且 `abs(positionAmt) >= remaining_qty`；
- reverse close：必须 `positionAmt > 0` 且 `positionAmt >= remaining_qty`；
- symbol 无行、返回空、数量为 0、符号相反、数值不可解析、缓存与实时查询都失败：暂停，零 attempt、零 POST。

这道门只降低当前任务的明显超平风险，不声称解决多张 close 卡并存造成的额度竞争；本轮不新增全局仓位预留系统。

### 5.6 forward base 余额/划转门

v1 的“只在首笔执行”撤回。每一对 forward close 订单前：

1. 使用 fresh preflight 已算出的 `q_common`；
2. `remaining_base = q_common × (target_n - scheduled_attempt_count)`；
3. 普通现货缓存 free 足够 remaining：直接放行，零网络；
4. 缓存不足/未知：实时确认普通现货 free；
5. 实时仍不足：检查统一账户同币可划转量，只划差额；
6. 查询或划转失败：暂停，零 attempt、零订单；
7. 该门位于 `prepare_attempt` 之前。

实现需把现有 helper 从 worker 首笔前重排到 fresh `q_common` 产生之后；不允许用原始 `single_amount × target_n` 代替。现有划转端点、方向、无重试和审计日志保持不变。

### 5.7 最终平仓核实不变

次数用完后 `_verify_close_flat` 仍实时查询 UM 持仓，决定 flat/open/failed 和周期是否关闭。这是不可逆结算事实，不读缓存，不属于性能瘦身范围。

## 6. 前端改动

1. 创建成功后立即显示后端返回的 paused close 卡；
2. `awaiting_manual_start` 显示“待启动：点击启动后才会校验并发送真实订单”；
3. “启动”按钮保持启用；
4. 首次启动前禁用 fill-once/fill-all；
5. 现有 amount/count、活跃周期状态、约 60 秒余额/持仓提前提示保持，不新增前端请求；
6. 修正旧注释中“后端未实现/stub”和“create_task 实时兜底”的过时描述；
7. 启动后的实际失败原因继续直接展示后端 `pause_reason_zh`。

前端缓存只用于用户体验，不替代后端启动后的安全门。

## 7. 最小实现文件边界

| 文件 | 最小职责 |
|---|---|
| `backend/hedge_open_tasks/service.py` | close 轻量建卡；初始 paused；position mode 继承；启动后 1000x/UM/forward base 门；阻止 fill 绕过；重排到 prepare_attempt 前 |
| `backend/hedge_open_tasks/store.py` | `create_task` 支持可选初始 status/pause reason，默认仍为 running，open 零变化 |
| `backend/services/hedge_preflight_provider.py` | close 跳过四项读取；接受固化 position mode；其余缓存优先+实时兜底不变 |
| `backend/hedge_open_tasks/domain.py` | `awaiting_manual_start` 原因/中文；支持 forward close 余额由 service 门负责，过滤器与 reverse 余额逻辑复用现有实现 |
| `frontend/index.html` | 待启动文案与 fill 按钮约束；保留现有提前提示 |
| `backend/tests/test_hedge_service.py` | 两段式状态/启动异步/绕过防护/open 不变 |
| `backend/tests/test_hedge_preflight_provider.py` | 四项跳过、五源缓存优先+兜底、open 回归 |
| `backend/tests/test_hedge_cycle_close.py` | F2/F3/F4、dry-run、final flat 回归 |
| `frontend/self-check.js` | close 卡待启动按钮/文案/禁用行为 |

明确不改：schema、API 路径和响应字段、open 初始 running 行为、scheduler、两腿并发、client order ID、自动补腿、1000x 换算、final flat、gate、凭据、env、服务和 live DB。

## 8. 验收标准

### 8.1 创建与首次启动体验

1. 所有交易所读取 mock 设置为“调用即失败”，合法 close create 仍返回 `201`；
2. 返回任务 `status=paused`、`pause_reason=awaiting_manual_start`、attempt=0、worker 未启动；
3. 页面立即出现任务卡，“启动”可点，首次 fill 按钮不可点；
4. `/start` 不同步执行 preflight，立即返回 `running` 并只提交 worker；
5. worker 预检失败后任务变 paused、中文原因可见、attempt=0、POST=0；
6. 非法参数/无活跃周期仍拒绝；1000x 纯本地拒绝且零卡片、零 POST。

### 8.2 dispatch 正常与兜底

1. 五项缓存充足时，预检零实时 GET；通过后仅出现两腿订单 POST；
2. 逐项缓存 miss/坏形状时仍走现有实时兜底；
3. `private_channel_enabled=false`、hedge 凭证可用时，forward/reverse close 仍可完成预检；
4. close 不调用 position-mode、PAPI rate-limit、Spot rate-limit、Spot USDT；
5. open create 和 open dispatch 在同样 cache miss 下仍走原实时读取及 `_degrade_note`，行为逐字不变。

### 8.3 F2：多次 forward close

`target_n=3`：

1. 第 1 笔前按 `q_common × 3` 校验/备位；
2. 第 2 笔前按 `q_common × 2`；
3. 第 3 笔前按 `q_common × 1`；
4. 任一轮缓存不足时实时确认，仍不足才划差额；
5. 第 2 笔前确认不足或划转失败：暂停、attempt 不增、两腿 POST=0。

### 8.4 F3：1000x

以下两例均须零 POST：

1. 新建 close 的纯查表 match 为 multiplier；
2. 存量任务 `symbol_match_type=NULL`，但 `resolve_spot_identity(coin)` 为 multiplier。

### 8.5 F4：UM 持仓

1. forward `positionAmt=-300`、remaining=300 → 通过；`+300` / `-299` / 0 / 无行 → 暂停；
2. reverse `positionAmt=+300`、remaining=300 → 通过；`-300` / `+299` / 0 / 无行 → 暂停；
3. cache miss 时实时查询一次；实时失败暂停；
4. 所有失败形状 attempt 不增、两腿 POST=0。

### 8.6 position mode、dry-run、最终核实

1. origin `position_side_mode=BOTH` 被继承；origin 为 NULL 时 close 卡固化 `BOTH`，不得 fatal stop；
2. close 启动/派发不调用 position-mode API；
3. dry-run close 接受使用原始 `single_amount` 记录，永远零 POST；测试不得把它误当 live `q_common`；
4. target 用完后的 UM flat 实时核实仍只执行一次，flat/open/failed 语义不变。

### 8.7 回归命令

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests -q -p no:cacheprovider
node frontend/self-check.js
git diff --check
```

网络性能用可计数 fake client 证明：create 外部调用数为 0、start handler 同步外部调用数为 0、缓存命中 dispatch 的 preflight GET 为 0；不使用脆弱的毫秒阈值代替调用计数。

## 9. 剩余风险与 reopen trigger

1. 缓存通过后，交易所状态仍可能变化；两腿并发使一腿拒单、另一腿成交无法原子回滚，继续由任务暂停 + Human 交易所核对兜底。
2. Human 若修改 position mode，必须恢复实时 position-mode 校验并重新评审。
3. 两个 env 变量若未来不再使用相同 key/权限，必须重新评审私有读取与下单权限差异。
4. 多张同 `(coin,direction)` close 卡并存会竞争同一仓位/余额；本轮不加预留系统。若出现此类实际使用，再单独设计。
5. 1000x 在完整换算、独立高风险评审和最小额度实盘验证前只允许人工交易所平仓。
6. dispatch 的缓存 miss 仍可能产生一次实时等待；这是可恢复性兜底。用户体验目标只保证卡片立即出现和 start 接口不阻塞，不承诺交易所读取永不等待。

## 10. Opus 5 v2 复评任务

请作为独立、只读的 `HIGH_RISK` 计划 Reviewer，重点复核：

1. `paused + awaiting_manual_start` 是否能复用现有状态机，且没有 worker/startup handoff/fill endpoint 绕过；
2. close create 全部跳过 preflight 后，nullable `q_common/snapshot` 是否只影响已明确接受的 dry-run 记录量；
3. F1 是否已彻底修正：private channel 关闭时仍可通过 hedge client 兜底，且 open 不变；
4. F2 的 helper 重排是否在 fresh `q_common` 之后、`prepare_attempt` 之前、每轮按 remaining 执行；
5. F3 双判是否覆盖新任务与历史 NULL；
6. F4 的方向符号、无行、数量和实时兜底是否完整；
7. 四项删除是否真的没有 close 生产消费者，并且没有误改 open；
8. 文件范围、验收和活文档同步是否是最小充分集合。

可实施时返回明确 `ACCEPT（接受）`；仍存在错误订单、单腿敞口、绕过人工启动、不可恢复暂停或必要证据缺失时返回 `REWORK（返工）`，附源码锚点和最小修复要求。

复评完成后只允许**新建**：

`docs/planning/close-task-preflight-simplification-2026-08-09.v2.review-opus5-result.md`

不得覆盖 v1 计划、v1 结果或本文。结果需包含 provider 隔离披露、八项逐条结论、F1—F7 closure、明确 verdict 和最小修复要求。计划复评不授权实现、提交、推送、部署、服务控制或任何实盘操作。

# GLM 排查结果存档 + 交叉复核

## 元信息

- stage_id: `2026-08-06-hedge-order-close-validation`
- 文档类型: **他模型排查结果存档（Part 1，原文不改）+ 交叉复核意见（Part 2）**
- Part 1 作者模型: **glm**
- Part 2 作者模型: **claude-opus-5（Claude Opus 5，Claude Code CLI）**
- 作成时间: `2026-08-06 CST`
- base_sha: `f153cdc`（工作树含 stage 未提交改动）
- 同源文档: `2026-08-06-hedge-order-close-validation-the-single-leg-dryrun-diagnosis.md`
  （claude-opus-5 独立排查报告，下称「Opus 报告」）
- 一句话结论: **两份排查在 A / B 的机理与定性上完全一致**；GLM 多发现一处真实缺陷
  （`_error_leg` 丢弃异常），Opus 报告漏了；**C 的严重性判断两边相反**，实测证据支持
  Opus 侧（worker 退出、任务停摆等人工，而非自动重试）；另有 **B 的危害面被 GLM 漏判**
  （dry-run 假成交已污染持仓口径，被误当作「另一条线」）。

---

# Part 1 — GLM 排查结果（原文存档）

排查完成。基于 DB 实测取证（`data/hedge-open-tasks.sqlite3` 任务 7eeab9c3），三个问题已全部定性。交接材料里对问题 A 的两个核心推断与实际相反，下面用证据说话。

> 时间换算：DB 的 `created_at_us` 存 UTC 微秒。下文同时标注 UTC / 北京（UTC+8）。交接的 08:41/09:16 即 UTC（= 北京 16:41/17:16）。DB 里 `attempt_seq=1` 对应「attempt 6」，`attempt_seq=2` 对应「attempt 7」。

## 问题 A（核心谜团 -2013）—— 交接推断反转，按设计正确工作

### 交接的两个错误推断

| 交接推断 | DB 实测 | 结论 |
|---|---|---|
| 「合约腿静默成 UNKNOWN」 | perp 腿走了正常分类路径，order_post raw 完整落库 | ❌ 没有静默 |
| 「raw_response 空，无法取证」 | perp order_post raw 存在：`transport_error=connection_error`、`decisive=1` | ❌ raw 没空 |

### 真实链路（attempt 1，UTC 08:41:59 / 北京 16:41:59）

1. 双腿并发（`live_hedge_executor.py:904` 两个 Thread）。两条腿走不同物理 host：
   - 现货腿（THE 被强制 regular_spot）→ POST `https://api.binance.com/api/v3/order` ✅ FILL 834390514
   - 合约腿 → POST `https://papi.binance.com/papi/v1/um/order` ❌
2. 合约腿 POST 时 `urlopen` 抛 `urllib.error.URLError` → `_send`（`hedge_open_live_client.py:224`）包成 `HedgeHttpResponse(transport_error="connection_error")`，请求在传输层失败，交易所根本没收到。
3. `classify_leg_response`（`live_hedge_executor.py:359`：`transport_error is not None`）→ `LEG_UNKNOWN_QUERYING`，raw 经 `_persist_leg_raw` 落库（`service.py:2456`，`decisive=1`）。
4. POST 后即时 best-effort query（`_send_one_leg:756`）也未当场定论 → `_dispatch_live:2558` → `_mark_legs_querying` → 交给 worker drain。
5. 47 秒后（16:42:46）worker `_reconcile_own_legs`（`service.py:1642`）→ `query_leg` → 交易所返回 `-2013 Order does not exist` → 确认合约单从未到达交易所（`error_category=absent`）→ 腿置 `TERMINAL_RECORDED`。
6. `pair_outcome=single_leg`（现货成交+合约无单）→ 单腿暴露记录。

### DB 证据（`hedge_open_raw_response`，attempt_seq=1）

```
perp  order_post   /papi/v1/um/order  http=(空) transport_error=connection_error  decisive=1  16:41:59
perp  order_query  /papi/v1/um/order  http=400  business_code=-2013  body={"Order does not exist."}  decisive=1  16:42:46
spot  order_post   /api/v3/order      http=200  orderId=834390514 (FILLED)  16:41:59
spot  order_query  /api/v3/order      http=200  orderId=834390514 (FILLED)  16:42:46
```

### 定性

这不是 bug，而是一次被正确保守处理的瞬时网络层连接失败（PAPI host 的 TCP 连接建立失败）。整个「UNKNOWN → 不重发 → drain query → 确认 absent」链路完全符合 ADR-2（写单永不重发）设计。-2013 是真实 absent（订单从未到交易所），不是最终一致性噪声——因为连接错误意味着请求很可能压根没发出去。

## 遗留盲区（真实，但本次未触发）—— `_error_leg` 丢弃证据

排查中发现一个潜在取证缺口，与 attempt 6 无关但值得修：

`live_hedge_executor.py:958` 的 `_error_leg(leg, exc)`：

- 签名接收 `exc` 参数，函数体完全没用它 → 异常 type/message/堆栈被彻底丢弃；
- 构造的 `LegDispatch` 不设 `raw_response` → 默认 None → `_persist_leg_raw`（`service.py:2644`：`if raw is None: return`）直接跳过；
- `_dispatch` 的 `_run` except（`:901`）只把异常存进 `errors[leg]`，无任何 stderr log。

本次合约腿没走这条路（`URLError` 已被 `_send` 包成 response，带了 raw），所以 raw 不空。但若 `_post_signed` 的签名 / `urllib.request.Request` 构造 / 白名单等环节抛出 Python 异常，就会走 `_error_leg` → 那时 raw 确实会空、异常静默。这正是交接描述的现象，只是 attempt 6 的实际成因不是它。

建议（可选，等确认后再改）：`_error_leg` 把 exc 的 `type(exc).__name__` + `str(exc)[:200]` 写进一个 `transport_error` 风格的 raw（或单独 task event），`_run` 的 except 加一行 stderr log。

## 问题 B（dry-run → live 切换）—— 交接推断正确，已确认

| 任务 | 时间(北京) | record_transport | legs 订单号 |
|---|---|---|---|
| e22ce275 | 16:38:06 | `"transport":"dry_run_record","posted":false` | `dryperp-*` / `dryspot-*`（假单） |
| 7eeab9c3 | 16:41:59 | `"transport":"live","posted":true` | 真单 834390514 / 2031628184 |

机制（`config.py:213`）：`APP_HEDGE_EXECUTOR` 只接受 `disabled`/`live`。

- `disabled`（默认）→ `server.py:990` mode≠"live" → 不注入 live executor → `service.py:481` 用默认 `RecordTransportExecutor`（dry-run 假成交）。
- `live` → `server.py:992-1013` 注入 `LiveHedgeExecutor` + `HedgePreflightProvider`。

切换 = 改 `APP_HEDGE_EXECUTOR`（disabled→live）+ 重启进程，无热切换。16:38→16:41 的 3 分钟即重启窗口。交接「不是按钮问题，是当时服务模式」的判断完全正确。

## 问题 C（preflight 未就绪窗口）—— 根因 + 改进方向

证据：THE 任务 attempt 6（16:41 single_leg）后，worker 下一轮在 16:43:14 踩到 `preflight_incomplete`（任务因 single_leg 在阈值内属 advisory，未暂停，继续 running）。

根因（`hedge_preflight_provider.py:482` `get_snapshot`）：每次发单前实时串行读 6–8 个独立端点，任何一个返回 None → 整盘 snapshot=None → fail-closed（`:523-530`）：

- 公开：perp exchangeInfo、spot exchangeInfo+isMarginTradingAllowed、est_price、（forward）collateral-cap 列表
- 签名：balance、positionSide/dual、rateLimit/order、（regular_spot）spot account + rateLimit

每个 `_read_*` 对任何异常都 swallow 成 None（如 `:194`、`:228`），无 TTL 缓存、无预热。所以重启后首个 tick 或任一端点瞬时抖动 → incomplete → 该 tick 不发单、下一 tick 重试。

这其实已经是「排队等待」的语义（不 fatal、下一轮重试，非永久卡死），只是事件噪声大 + 每次都重读全部端点放大了抖动面。

改进方向（呼应交接建议）：

1. 对变化慢的公开读取（exchangeInfo 过滤器、restricted-asset cap 列表）加 TTL 缓存，把每次实时端点数从 6–8 降到 3–4，显著缩小抖动面；
2. 签名读取（balance/positionMode/rateLimit）可考虑加短 TTL（如 1–2 秒）摊平同一 tick 内多任务的重复读；
3. 噪声治理：连续 N 次 incomplete 汇总成一条事件，而非每 tick 一条。

## 需要你决策的下一步

1. `_error_leg` 取证盲区：要不要修（把异常信息落进 raw/event + `_run` 加 stderr log）？这是唯一真实的代码缺陷，但与 attempt 6 无关——属防御性加固。
2. 问题 C 缓存改进：是否要加公开读取的 TTL 缓存？这会改 `HedgePreflightProvider`，影响面需要单独评估。
3. A 无需改代码：链路按设计正确工作，attempt 7 已双腿成交补回。现货 `spot_qty=800` vs `spot_bal=400` 的本地/真实差额是另一条线（本地记账口径），需要的话我可以单独查 `hedge_open_fill` / ledger 对账。

---

# Part 2 — 交叉复核（claude-opus-5）

两份排查独立进行，未共享中间结论。下面逐项对照。

## 2.1 完全一致的部分（可视为双模型互证，置信度高）

| 项 | 两边结论 |
|---|---|
| A 机理链条 | 双线程并发 → papi 腿 `URLError` → `connection_error` → `UNKNOWN_QUERYING`（ADR-2 禁重发）→ 47s 后 drain query → `-2013` → `absent` → `single_leg` |
| A 定性 | **不是 bug**，是被正确保守处理的瞬时传输失败；absent 判定与交易所实况（`um_amt=-200` 仅来自 attempt 7）一致 |
| A 对交接的证伪 | 「raw_response 空」「静默成 UNKNOWN」两个推断均错——raw 有 `order_post` + `order_query` 两条 `decisive=1` 记录 |
| B 根因 | `APP_HEDGE_EXECUTOR` 缺省 `disabled` → `service.py:481` 默认 `RecordTransportExecutor` → 假成交；无热切换，16:38→16:41 是重启窗口 |
| C 机理 | 每次派发实时串行读 6–8 个端点、零缓存、`_read_*` 吞掉一切异常成 None、任一 None → 整盘 fail-closed |
| C 改进方向 | 对慢变公开读（exchangeInfo / cap 列表）加 TTL 缓存 |

关键代码坐标两边也一致：`live_hedge_executor.py:904 / :359`、`hedge_open_live_client.py:224`、
`service.py:481 / :2154`、`config.py:213`、`hedge_preflight_provider.py:482 / :523-530`。

## 2.2 GLM 发现而 Opus 报告漏掉的（采纳）

**`_error_leg` 丢弃异常证据** —— GLM 的发现成立，已复核确认：

```python
# live_hedge_executor.py:958
def _error_leg(leg: str, exc: Optional[BaseException]) -> LegDispatch:
    """A leg whose send/thread raised maps to UNKNOWN_QUERYING (query, not fail)."""
    return LegDispatch(
        leg=leg, dispatch_state=LEG_UNKNOWN_QUERYING, order_id=None,
        exchange_status=None, executed_qty="0", cumulative_quote=None,
        avg_price=None, rate_limited=False,      # ← 无 raw_response，exc 从未被使用
    )
```

`exc` 形参接收后完全未使用，且 `raw_response` 缺省 None → `_persist_leg_raw` 的
`if raw is None: return` 直接跳过 → **该路径下 raw 确实会空且异常完全静默**。
GLM 对边界的界定也准确：本次 attempt 6 **没有**走这条路（`URLError` 在 `_send`
内部就被包成了带 raw 的 response），所以它是潜在缺陷而非本次成因。

这与 Opus 报告 P1-1（`_send` 的 `except URLError` 丢弃 `exc.reason`）是**两个不同位置的
同类缺陷**，应合并成一个「传输层异常证据保全」修复项：

| 位置 | 现状 | 触发条件 |
|---|---|---|
| `hedge_open_live_client.py:224-226` | `exc` 丢弃，只留 `"connection_error"` 字符串 | **本次已触发** |
| `live_hedge_executor.py:958-969` | `exc` 丢弃，且完全无 raw 落库 | 未触发（签名/Request 构造/白名单抛错时） |

## 2.3 判断相反的部分（实测证据支持 Opus 侧）

### 分歧 1（重要）：C 的严重性——「自动重试」还是「停摆等人工」

GLM 原文：

> 任务因 single_leg 在阈值内属 advisory，**未暂停，继续 running**
> …… 该 tick 不发单、**下一 tick 重试**
> …… 这其实已经是「排队等待」的语义（不 fatal、**下一轮重试，非永久卡死**）

**这一判断与实现和实测行为均不符。**

代码实证（`service.py:1450-1451`）：

```python
if signal == D.SIGNAL_PREFLIGHT_INCOMPLETE:
    return self._worker_exit(task_id, D.WORKER_EXIT_PREFLIGHT_INCOMPLETE)
```

`preflight_incomplete` 让 **task-local worker 直接退出**，不是继续下一轮。

行为实证：

- `hedge_open_log` 中 16:43:14 之后 **33 分钟零事件**，直到 17:16:08 用户手动点「成交 1 次」
  才产生下一个 attempt。若真是「下一 tick 重试」，`interval_seconds=0.5`，33 分钟应产生
  数千条 incomplete 事件——实际只有 **1 条**。
- 字段名本身即结论：`hedge_open_task.last_worker_exit_reason`，任务 `e22ce275` 该字段值
  就是 `preflight_incomplete`。它是**退出原因**，不是等待状态。
- 架构层佐证（Amendment 21）：live 模式下 `start()` 只做一次 `_recover_workers()`
  （`service.py:554`），**没有全局 guardian/scanner**；worker 退出后只有 HTTP
  Start/recover 能重新拉起。所以没有任何东西会自动重试。

**这个分歧直接改变优先级**：按 GLM 的判断，C 只是噪声问题，做缓存和事件聚合即可；
按实测，C 会让任务**静默停摆直到人工干预**——这正是用户会来排查的原因，也是本次
`e22ce275`（16:06 incomplete → 停到 16:38）和 `7eeab9c3`（16:43 incomplete → 停到 17:16）
两次停摆的直接机制。

顺带发现一处**契约不一致**（两份报告都未提，本次复核新增）：
`_dispatch_one_for_task` 的 docstring 写的是

> an incomplete read is **fail-closed retry** (no attempt/POST/count)

而 worker 层实现是 `_worker_exit`。文档说 retry，实现是 exit，中间没有任何重试者。
这是 C 该修的真正落点——要么补有限重试（带退避、带上限），要么修正文档并让 UI
明确暴露「任务已因预检不完整停摆，需人工恢复」。

### 分歧 2（重要）：B 的危害面被漏判为「另一条线」

GLM 决策项 3 写：

> 现货 `spot_qty=800` vs `spot_bal=400` 的本地/真实差额是**另一条线**（本地记账口径），
> 需要的话我可以单独查 `hedge_open_fill` / ledger 对账

**这不是另一条线，它就是 B 的直接后果。** 复核证据：

- `hedge_open_fill` 表**为空**——查它得不到任何东西；持仓口径实际来自
  `hedge_open_leg`（`store.py:2487-2530` 遍历 `leg_rows`）。
- 该聚合对 leg 行**无差别累加** `cumulative_base_qty`，dry-run 写入的
  `dryspot-`/`dryperp-` 行同样计入：

| 口径 | 真实（交易所） | dry 虚增 | 本地显示 |
|---|---|---|---|
| spot_qty | 400 | **+400**（attempt 4/5 各 200） | 800 |
| perp_qty | 200 | **+400** | 600 → position_qty −600 |

数字与用户观测逐位吻合（`spot_bal=400` vs `spot_qty=800`；`um_amt=-200` vs
`position_qty=-600`）。此外 `success_count=2` 被计入、周期 `096232b7` 成本基被污染。

补充一条两份报告都未覆盖的事实：**软删除救不了**——`store.py:2500-2502` 中
`STATUS_DELETED` 只置 `includes_deleted` 标志，leg 行**仍然参与累加**。必须物理清理
或在聚合层按 `dry*` 前缀排除。

因此 B 的优先级应从 GLM 隐含的「已确认，无需动作」提升为 **P0（数据清理 + 防复发）**。

## 2.4 不建议采纳的建议

**GLM 改进方向 2：签名读取（balance/positionMode/rateLimit）加 1–2 秒 TTL 缓存。**

建议**否决**。`_dispatch_one_for_task` 的核心冻结契约是
**fresh preflight immediately before send（A-2）**——`balance` 是决定 `q_common`
和「是否够钱下单」的事实基础。给它加缓存意味着可能在**过时余额**上授权真实下单，
这与整个 fail-closed 设计的立意直接冲突，用「摊平重复读」的性能收益换下单安全性
不划算。

分层立场应当是：

| 读类型 | 可否缓存 | 理由 |
|---|---|---|
| `fapi/exchangeInfo`（1.06 MB）、spot exchangeInfo、cap 列表 | ✅ 可加 TTL | 分钟级不变，且是 preflight 中最重、最易超时的一环 |
| `balance` / `positionSide/dual` / `rateLimit` | ❌ 不缓存 | 账户事实，缓存即违反 fresh-preflight 契约 |

GLM 改进方向 1（公开读加 TTL）与 Opus 报告 P1-3 一致，采纳。
改进方向 3（事件聚合）在修掉分歧 1 之后才有意义——当前只有 1 条事件，噪声不是问题，
**停摆才是**。

## 2.5 次要差异（不影响结论）

- GLM 未追查环境层根因。Opus 报告实测本机
  `HTTP_PROXY/HTTPS_PROXY/ALL_PROXY = 127.0.0.1:6152` + 系统代理同指 6152（Surge），
  全部币安流量经本地代理；现货与合约是两个 host、两条独立代理连接，可精确解释
  「同一毫秒一腿成、一腿断」。GLM 止步于「PAPI host TCP 连接建立失败」，方向正确但未到底。
- GLM 保留了交接的「重启后首个 tick」表述。实际上 `HedgePreflightProvider`
  **无任何进程级状态或缓存**，重启后第一次与第一万次走完全相同的代码路径，
  不存在「未就绪窗口」这一概念。硬反证：16:41:59 派发前 preflight 刚成功，
  **同一进程 75 秒后**的 16:43:14 即 incomplete。
- GLM 说「串行读 6–8 个端点」，Opus 报告实测计为 7 个（forward open 路径），
  口径差异来自 regular_spot 分支是否额外读 spot account + rateLimit。两边不冲突。
- GLM 未提 `leverage -2015` 已在工作树修复（`/fapi/v1/leverage` → `/papi/v1/um/leverage`），
  该修复正是 16:35 重启的起因，也是 B 时间线的关键一环。

## 2.6 合并后的建议清单

| 优先级 | 项 | 来源 | 位置 |
|---|---|---|---|
| **P0-1** | 清理 attempt 4/5 假 leg 行 | Opus | `hedge_open_leg`（破坏性，需 Human 点头 + 备份） |
| **P0-2** | 持仓聚合 / success_count 排除 `dry*` 前缀 | Opus | `store.py:2487-2530` |
| **P0-3** | 前端常驻显示 executor_mode；修正陈旧的 `executor_mode_snapshot` | Opus | 前端 + settings |
| **P1-0** | preflight_incomplete 的 exit-vs-retry 契约不一致：补有限重试或明确暴露停摆 | 本次复核新增 | `service.py:1450` + 文档 + UI |
| P1-1 | 传输层异常证据保全（合并两处） | Opus + **GLM** | `hedge_open_live_client.py:224` + `live_hedge_executor.py:958` |
| P1-2 | `preflight_incomplete` payload 记录失败的读名 | Opus | `service.py:2241` |
| P1-3 | 公开读（exchangeInfo / cap 列表）加 TTL 缓存 | Opus + GLM | `hedge_preflight_provider.py:242` |
| ~~—~~ | ~~签名读加 1–2s TTL~~ | GLM（**否决**） | 违反 fresh-preflight 契约 |

## 2.7 复核边界声明

- 本次复核为 **read-only**：未改源码、未执行 DDL/DML、未发交易请求。
- 分歧 1 的判定依据为 `service.py:1450-1451` 代码实证 + `hedge_open_log` 事件间隔实测，
  非推断。
- 行号基于 base_sha `f153cdc` + stage 未提交工作树，后续改动会漂移。

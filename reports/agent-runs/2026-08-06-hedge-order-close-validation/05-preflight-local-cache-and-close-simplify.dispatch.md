# 实施任务：preflight 改读本地缓存 + 平仓校验简化 + 预检失败改为可见暂停

阶段：`2026-08-06-hedge-order-close-validation`（验证下单/平仓核心链路 + 修复小 bug）
status.json：`reports/agent-runs/2026-08-06-hedge-order-close-validation/status.json`

> **本文件取代未派发的 `04-preflight-local-cache-and-incomplete-retry.dispatch.md`。**
> 该草稿从未进入 `status.json`（04 编号已由 review-1 占用），且其 §4/§5 已被 Human
> 三项决定改写。以本文件为准。

背景：2026-08-06 THE 实盘出现「任务静默停摆 33 分钟」（问题 C）。claude-opus-5 完成
只读实测（仅 GET，未下单、未划转），三组数据：

**① 耗时构成（实测，串行）**

| 环节 | 耗时 | 频率 |
|---|---|---|
| 建卡 `check_symbol_legs` | 2.79s | 每次建卡 |
| 建卡 `get_snapshot` | 9.95s | 每次建卡 |
| **建卡合计** | **12.74s** | ← 用户可感知的「回显要等十几秒」 |
| 开单 `get_snapshot` | 6.64s | **每个 attempt** |
| 平仓 `get_snapshot` + 专属读 | ~8.9s | **每个 attempt** |

单项：`fapi exchangeInfo` 2.88s（**1.06 MB**，占 43%）、`positionSide/dual` 1.11s、
`balance` 0.83s、`rateLimit/order` 0.62s、`restricted-asset` 0.46s、
`spot exchangeInfo` 0.45s、`ticker/price` 0.38s；平仓额外
`/api/v3/account` 1.40s + `/api/v3/rateLimit/order` 0.80s；
`_ensure_close_spot_balance` 首轮 1.77s；`_verify_close_flat` 每轮 0.44s。
**建卡时 `fapi exchangeInfo` 被拉了两次**（`check_symbol_legs` 一次 + `get_snapshot`
一次），纯浪费 ~2.9s。

**② 问题 C 的直接根因（实证）**

`fapi exchangeInfo` 连测 5 次：`15.68s / 6.13s / 6.29s / 3.74s / 4.07s`——抖动
3.7~15.7 秒，而 `DEFAULT_TIMEOUT_SECONDS = 10.0`。**最大的那个请求经常击穿超时** →
`_read_public_json` 吞掉异常返回 None → `get_snapshot` 整盘 None →
`SIGNAL_PREFLIGHT_INCOMPLETE` → `service.py:1450` **worker 静默退出**（任务状态仍
`running`，卡片无任何提示）→ 停摆到人工干预。交接曾假设「重启后首次快照未就绪」，
已证伪：16:41:59 preflight 刚成功，**同一进程 75 秒后**即 incomplete。

**③ 本地已有缓存**

`SnapshotService._global_source_cache` 已缓存 preflight 所需的绝大部分数据，
**所有私有源均为 60s TTL**：

| preflight 的读 | 本地缓存 source_id | 刷新周期 |
|---|---|---|
| fapi exchangeInfo | `group_b_public.futures_exchange_info` | 1800s |
| spot exchangeInfo | `group_b_public.spot_exchange_info` | 1800s |
| ticker/price | `price_map` | 60s |
| restricted-asset cap | `restricted_asset`（带 `checked_at`） | 按 due |
| papi balance | `unified_balances`（`/papi/v1/balance`） | **60s** |
| 平仓 `/api/v3/account` | `spot_balances`（同一端点） | **60s** |
| positionSide/dual | ❌ 无 | — |
| spot / papi rateLimit | ❌ 无 | — |

**Human 三项决定（2026-08-06，本 dispatch 的直接依据）**

1. **实时查询换本地缓存**，且**保留每轮校验**——换缓存后每轮成本≈0，而
   「建卡一次性校验」会让久置任务拿几小时前的快照下单，更不安全。
2. **平完判定不再每轮做**，只在平仓任务 `running → 非 running` 时做一次。
   Human 风险判断（评审者已核实其技术前提）：平仓合约腿带 `reduceOnly=true`
   （`executor.py:125-126`，注释 "so a close order never over-closes"），无仓可平会被
   **交易所拒绝**；且现货腿数量与合约腿一致，多卖场景不成立。
3. **划转不再做后置余额复检**：只认划转返回结果（拿到 `tranId` 即成功），
   加 `sleep(100ms)` 让余额同步，并**补充可区分的细节日志**。
4. **预检失败的 exit-vs-retry 契约不一致**：以代码实现为准改文档（**退出**，不重试），
   但**静默是缺陷必须修**——退出前须暂停任务并在卡片上显示中文原因。

## Identity

- task_id: `2026-08-06-hedge-order-close-validation-preflight-local-cache`
- target_role: `Implementer`
- target_model: `deepseek`（Human 指定）
- provider: 按 `agents/roles.md` 模型映射
- status_revision: 6
- required_skill: `agents/skills/senior-developer.md`
- 基线：`ee7ec4f`（stage 任务 01/02/03 已交付并经 review-1 `ACCEPT`）之后的工作树。

## Goal

1. preflight 的可缓存读改走 **SnapshotService 本地缓存**，带**陈旧上限**；
   缓存不可用时**降级实时读**（不比现状更差）。
2. 本地无缓存的两项账户级配置**进程内读一次 + 长 TTL**。
3. **平仓简化**：平完判定只在 `running → 非 running` 时做一次（仍实时）；
   划转去掉后置复检，改为认返回结果 + `sleep(100ms)` + 细节日志。
4. **预检失败改为可见暂停**：`_worker_exit` → `_pause_task_local`，
   中文原因含**失败的读名**；同步修正 docstring 的 retry/exit 措辞。
5. **前端执行模式徽标醒目化（Human 2026-08-06 决定并入本任务）**：徽标**已有**
   （`frontend/index.html:4493` `renderHedgeExecutionStatus`），数据源是进程实时
   `self._mode`（`service.py:856`），非陈旧 DB 字段。**不做新增提示、不改数据源**，
   只把它**做醒目**：dry-run 时状态栏变警示色 + 「成交 1 次」按钮标注演习模式。
   实现后须跑 `node frontend/self-check.js` 全绿。

目标数字：

| | 现在 | 改后 |
|---|---|---|
| 建卡回显 | 12.74s | ~0.1s |
| 开单每轮 | 6.64s | ~0ms |
| 平仓每轮 | ~8.9s | **~0ms** |
| 平仓收尾（状态转换那一次） | — | ~0.44s（实时平完判定，不可省） |

---

## 实现要求

### 1. 只读注入 seam（两服务保持解耦）

`HedgeOpenTaskService` 与 `SnapshotService` 现为**刻意解耦**（`service.py:591-595`
注释：「SnapshotService stays uninjected here」），**禁止直接 import**。照抄既有先例
`configure_cache_refresh`（`service.py:588`，`server.py:1064` 注入）：

1. **`backend/services/snapshot_service.py`**：新增**公开只读**方法
   `get_cached_source(source_id) -> tuple[float, Any] | None`，返回
   `(monotonic_ts, value)`，缺失返回 `None`。内部复用 `_global_source_cache`
   （`:1213-1215`）。**只读，不得触发任何刷新**（不得调用 `_refresh_due_sources`）。
2. **`backend/services/hedge_preflight_provider.py`**：构造函数新增可选参数
   `snapshot_reader: Optional[Callable[[str], tuple[float, Any] | None]] = None`。
   **`None` 时行为逐字不变**（走现有实时读路径）——保证既有 provider 测试零改动。
3. **`backend/app/server.py`**：与 `configure_cache_refresh` 同处注入
   `snapshot_reader`（绑定到 SnapshotService 实例的新方法）。

### 2. 缓存映射 + 陈旧上限

改造以下方法：**先查缓存 → 命中且未超陈旧上限则用；否则降级走原有实时读**。

| 方法 | source_id | 取值路径 | 陈旧上限 | 超限行为 |
|---|---|---|---|---|
| `_read_perp_filters` (:241) | `group_b_public` | `["futures_exchange_info"]["symbols"]` | **2h** | 降级实时读 |
| `_read_spot_record`/`_read_spot_leg` (:251) | `group_b_public` | `["spot_exchange_info"]["symbols"]` | **2h** | 降级实时读 |
| `_read_est_price` (:313) | `price_map` | 按 symbol 取价 | **5min** | 降级实时读 |
| `_read_balances` (:327) | `unified_balances` | `[{asset, crossMarginFree}]` | **5min** | 降级实时读 |
| `_read_spot_account_usdt` (:423) | `spot_balances` | `[{asset, free}]` 取 USDT | **5min** | 降级实时读 |
| `_read_collateral_cap_hit` (:392) | `restricted_asset` | `value["exceeded"]` | **10min** | **fail-closed（返回 None）** |
| `check_symbol_legs` (:598) | `group_b_public` | 两个 exchangeInfo | **2h** | 降级实时读 |

要点：

- **`restricted_asset` 是唯一 fail-closed 项**：它是 51169 抵押额度打满导致
  「合约腿成交 / 现货腿被拒 → 裸空」的**唯一预警**，陈旧时绝不许猜。其 value 自带
  `checked_at`，优先用该字段判陈旧。
- **按实际结构解析，不得假设**：`unified_balances` 来自 `/papi/v1/balance`
  （字段 `crossMarginFree`）、`spot_balances` 来自 `/api/v3/account` 的 `balances`
  （字段 `free`）——与现有 `_read_balances` / `_read_spot_account_usdt` 的解析一致。
- **降级实时读必须留痕**（stderr + 计入 §4 的失败读名机制），否则「缓存长期不可用而
  在偷偷走慢路径」不可见。
- `check_symbol_legs` 与 `get_snapshot` 命中同一份 `group_b_public`，
  **建卡那次重复的 1.06MB 读自然消除**，无需额外去重逻辑。

### 3. 账户级配置：进程内读一次 + 长 TTL

`positionSide/dual`（1.11s）、`rateLimit/order`（0.62s）、`spot rateLimit/order`
（0.80s，平仓 regular_spot 路由用）本地无缓存，但均为**账户级设置，不主动更改则不变**。
在 `HedgePreflightProvider` 内加进程级缓存：

- `_read_position_mode`（:351）、`_read_rate_limit_order`（:373）、
  `_read_spot_rate_limit_order` 三者各自缓存，**TTL 600s**；
- **失败不缓存**（只缓存成功值），失败仍按现有 fail-closed 返回 `None`；
- `dualSidePosition` 语义不变：只有字面 `false` 确认单向，缺失/歧义仍 fail-closed。

### 4. 平仓简化（Human 决定 2 / 3）

#### 4.1 平完判定：从「每轮」改为「状态转换时一次」

现状 `service.py:1404-1426`：worker 每轮开头调 `_verify_close_flat`（每轮 0.44s），
四个分支 `flat / failed / open+次数用完 / open+还有次数`。

改为：**只在平仓任务将从 `running` 变为其他状态时调用一次**，即以下两个时点，
其余每轮**不再调用**：

1. `scheduled_attempt_count >= target_n`（次数用完，准备收尾）→ 调一次：
   - `flat` → `_finalize_close_task`（关周期 + 写结算日志），
   - `open` → 现有「部分平完成」路径（done、周期不关、`close_partial_done` 日志），
   - `failed` → 现有 `PAUSE_REASON_CLOSE_VERIFY_FAILED` 暂停（fail-closed 不变）。
2. 任务因其他原因即将离开 `running`（暂停/停止/软删除路径中已有的 close 收尾点）→
   保持既有语义，**不新增**调用点。

**保持实时**：该判定决定「关闭周期 + 写结算日志」这一**不可逆**动作，
**禁止读缓存**（`um_positions` 缓存 60s，会以过期持仓关错周期）。它是本任务里
唯一保留的实时签名读。

**安全依据（Human 已拍板，实现者不得据此扩大改动）**：合约腿 `reduceOnly=true`
使「无仓可平仍下单」被交易所拒绝；现货腿数量与合约腿一致，多卖场景不成立。
因此去掉每轮的「提前发现已平完」保护是可接受的。

#### 4.2 划转：去掉后置复检 + `sleep(100ms)` + 细节日志

`_ensure_close_spot_balance`（`service.py:1497`）改动三处：

1. **删除**划转后的 `recheck = q_spot(base_asset)` 及其两个失败分支
   （`:1546-1552`）。`universal_transfer` 内部已在缺 `tranId` 时抛错
   （`live_hedge_executor.py:699-700`），响应丢失/失败仍走既有异常 → 暂停路径，
   语义不变。
2. 划转成功后 `time.sleep(0.1)` 让普通现货账户余额同步（**经验值，非保证**——
   正因如此才必须有第 3 条）。
3. **新增可区分的细节日志（Human 决定 3 的重点）**：本任务首轮划转过之后，
   若后续下单因余额不足失败/暂停，其中文原因必须能区分「真没钱」与「钱还在路上」。
   实现：在划转成功时记录本任务已划转的事实（`_log_close_transfer` 的 `ok` 事件已
   存在，复用即可），并在 forward close 的余额不足暂停文案中追加提示，形如
   「本轮已完成划转 <数量> <资产>，若仍报余额不足，可能是划转尚未到账，
   请稍后手动恢复重试」。

3. **划转触发仍走「缓存放行、实时确认才动手」**（保留）：
   `:1517` 首次余额判断可用 `spot_balances` 缓存——
   - 缓存显示**充足** → 直接放行（0 网络请求，覆盖绝大多数情况）；
   - 缓存显示**不足** → **必须再实时读确认一次**，实时读仍不足才发起
     `universal_transfer`。
   理由：划转是**有副作用的真实资金动作**，缓存误判会白划一笔。原则：
   **缓存只用于「放行」，不用于触发有副作用的动作。**
   `query_unified_free`（可划转量，`:1525`）属放行类，可用 `unified_balances` 缓存。

### 5. 预检失败：静默退出 → 可见暂停（Human 决定 4）

现状 `service.py:1450-1451`：

```python
if signal == D.SIGNAL_PREFLIGHT_INCOMPLETE:
    return self._worker_exit(task_id, D.WORKER_EXIT_PREFLIGHT_INCOMPLETE)
```

worker 退出但任务状态仍 `running`，卡片零提示；live 模式无全局 scanner
（Amendment 21），只有 HTTP Start/recover 能重新拉起。实测后果：一条事件后
**33 分钟零活动**直到人工点按钮。

改为（**保留「退出、不重试」策略，只修可见性**）：

1. 用 `_pause_task_local` 替代 `_worker_exit`：任务置 `paused` +
   新增 `D.PAUSE_REASON_PREFLIGHT_INCOMPLETE` + 中文文案 +
   `kind="preflight_incomplete"` 事件；worker 随后退出本轮（`return False`，
   与既有 `SIGNAL_TASK_LOCAL_PAUSE` 分支一致）。
2. 中文原因**必须含失败的读名**，形如「预检数据不完整（<失败的读名>），任务已暂停
   （fail-closed，未发单）；请检查网络后手动恢复」。
3. `_record_preflight_incomplete`（`:2241-2250`）的 payload 增加**失败的读名**字段
   （当前仅 `{reason, coin, direction}`，无法回溯是哪个读挂了——这是问题 C 排查时的
   第二个取证盲区）。`get_snapshot` 需把「第一个失败的读」回传给调用方
   （新增返回通道，或 provider 侧记录最近一次失败读名，二选一），
   **不得为此改 `PreflightSnapshot` 的冻结形状**。
4. **同步修正措辞（Human 决定 4 的文档侧）**：`_dispatch_one_for_task` docstring
   中「an incomplete read is fail-closed **retry**」等 retry 表述，一律改为
   **exit/pause**，与实现一致。搜索范围限本任务 Allowed Files 内的
   docstring/注释，不改其他模块。

**不变**：fail-closed 语义本身（残缺事实上永不授权下单）、
`SIGNAL_PREFLIGHT_FATAL` 的既有停机路径、**不引入重试**。

---

## 不在本次范围

- 不改 `_dispatch_live` / `classify_*` / ADR-2 不重发语义；
- 不改 SnapshotService 的**刷新策略/周期/due 规则**——本任务对它**只读**，
  一行刷新逻辑都不许动；不得从 preflight 触发 `force_account_panels`；
- 不改 `DEFAULT_TIMEOUT_SECONDS`（换缓存后 1.06MB 的超时面自然消失，改超时是治标）；
- 不新增「本地累计已平量核对」（Human 已判定 reduceOnly + 双腿等量足够，
  不需要该保护）；
- 不动周期表 `hedge_open_cycle`（`096232b7` 的 `first/last_task_id` 指向已删任务
  是既有待办）；

## Allowed Files

可修改：

- `backend/services/hedge_preflight_provider.py`（缓存映射 + 陈旧上限 + 账户配置 TTL
  + 失败读名回传）
- `backend/services/snapshot_service.py`（**仅新增只读 `get_cached_source`**）
- `backend/app/server.py`（注入 `snapshot_reader`）
- `backend/hedge_open_tasks/service.py`（平完判定调用点收敛、划转改造、
  预检失败改暂停、`_record_preflight_incomplete` 失败读名、docstring 措辞）
- `backend/hedge_open_tasks/domain.py`（`PAUSE_REASON_PREFLIGHT_INCOMPLETE` + 中文文案）
- `frontend/index.html`（仅执行模式徽标醒目化：dry-run 警示色 + 成交按钮演习标注，
  不改数据源、不新增提示）
- **相关测试文件**（本条为兜底授权，覆盖下列已知文件及为本任务新增行为所必需的
  其他测试文件）：`backend/tests/test_hedge_preflight_provider.py`、
  `test_hedge_task_local.py`、`test_hedge_cycle_close.py`、`test_snapshot_service.py`、
  `test_hedge_service.py`
  > 兜底授权的由来：本 stage 任务 03 的 Allowed Files 逐个列举测试文件却漏列两个，
  > review-1 已将其记为 **packet 缺陷 R-1**（起草方疏漏，非交付缺陷）。本 dispatch
  > 据此改为兜底授权，避免同类边界不足重演。新增/改动的测试文件须在交接件列明。

只读：

- `reports/agent-runs/2026-08-06-hedge-order-close-validation/status.json`
- `evidence/` 下 diagnosis / crosscheck / review-1 三份报告
- `backend/services/private_client.py`（各 fetcher 的字段形状与 60s TTL）
- `backend/hedge_open_tasks/executor.py`（`build_perp_order_params` 的 reduceOnly 事实）

禁止：

- 在 `hedge_open_tasks/` 或 `hedge_preflight_provider` 中 `import` SnapshotService；
- 让 preflight 触发任何缓存刷新（只读）；
- 对 §4.1 的平完判定使用缓存；
- 为预检失败引入重试（Human 已决定「退出」）；
- 未授权提交、移动 HEAD、对实盘发单/划转/设杠杆、记录凭证。

交接件：`reports/agent-runs/2026-08-06-hedge-order-close-validation/evidence/
2026-08-06-hedge-order-close-validation-preflight-local-cache.handoff.md`

## Inputs

按 `AGENTS.md` §4 顺序读取：

1. `AGENTS.md`
2. 本 dispatch
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-06-hedge-order-close-validation/status.json`
6. `agents/roles.md` 的 `Implementer` 段 + `Task Handoff Evidence Contract` 段
7. `agents/developer-discipline.md`
8. `agents/skills/senior-developer.md`
9. `reports/agent-runs/2026-08-06-hedge-order-close-validation/evidence/2026-08-06-hedge-order-close-validation-the-single-leg-dryrun-diagnosis.md`（§4 问题 C 机理）
10. `reports/agent-runs/2026-08-06-hedge-order-close-validation/evidence/2026-08-06-hedge-order-close-validation-glm-diagnosis-crosscheck.md`（§2.3 exit-vs-retry 实证）
11. 按需：`snapshot_service.py:1213 / :1233 / :1288-1340`、
    `hedge_preflight_provider.py:188-196 / :241-441 / :482-596`、
    `service.py:588-597（注入先例）/ :1395-1460 / :1497-1560 / :2241 / :2278-2310`

## Acceptance Checks

1. **注入解耦**：`hedge_open_tasks/` 与 `hedge_preflight_provider.py` grep 不到
   `SnapshotService`；`snapshot_reader=None` 时 provider 行为**逐字不变**
   （既有 provider 测试零修改通过）。
2. **缓存命中**：注入伪 reader 后 `get_snapshot` 的 7 个读**零网络请求**
   （spy 断言 `_public_urlopen` / client 方法调用次数为 0）。
3. **陈旧降级**：每个缓存项超上限 → 走实时读（spy 断言）；`restricted_asset`
   超 10min → **返回 None（fail-closed）**，不降级、不猜。
4. **账户配置 TTL**：三项在 600s 内各只读一次；读失败不写缓存。
5. **平完判定收敛**：普通轮次（`scheduled_attempt_count < target_n`）**不调用**
   `query_symbol_um_qty`（spy 计数为 0）；次数用完那一轮调用**恰好一次**且为
   **实时**；`flat / open / failed` 三分支语义与改动前逐字一致
   （关周期 / 部分平完成 / fail-closed 暂停）。
6. **划转**：后置复检已删除；划转成功后 `sleep(100ms)`；缺 `tranId` / 异常仍暂停；
   缓存显示不足时**先实时确认**、实时充足则**不发起划转**；划转后余额不足的暂停
   文案含「可能是划转尚未到账」提示。
7. **预检失败可见**：incomplete → 任务 `paused` +
   `pause_reason=PREFLIGHT_INCOMPLETE` + 中文原因**含失败的读名** + 事件落库；
   worker 退出本轮；**无重试**；`SIGNAL_PREFLIGHT_FATAL` 路径不变。
8. **措辞一致**：Allowed Files 内不再有把 incomplete 描述为 retry 的 docstring/注释。
9. **性能证据**（写进交接件）：注入缓存前后各测一次 `get_snapshot`（开单 + 平仓），
   附耗时对比；建卡路径断言 `fapi exchangeInfo` 读 0 次（命中）或 1 次（冷启动降级），
   不再是 2 次。
10. **回归**：`python3 -m pytest backend/tests -q` 全绿 + `node frontend/self-check.js`
    全绿；`git status --short` 仅列 Allowed Files；SnapshotService 的 `git diff`
    **只有新增只读方法**。
11. **前端徽标醒目**：dry-run/disabled 模式状态栏徽标为警示色（与 live 可区分），
    「成交 1 次」按钮带演习/disabled 标注；live 模式外观不变；数据源仍为进程实时
    `self._mode`，未新增前端提示通道。

## Stop

按 `AGENTS.md` §7 返回完整中文 `[TASK_RESULT v2]`（含三行中文交接），`下一步任务` 用
可执行形式 `读取：<路径或 none>；执行：<立即动作>；关卡：<下一验证>`。

下一关卡：Human 用 `scripts/run-server.sh` 重启服务实盘复测——
(a) 建卡回显是否从十几秒降到秒内；
(b) 连续开单/平仓每轮是否不再有数秒预检等待；
(c) 平仓任务收尾时仍以**实时**持仓判定是否全平（周期关闭正确）；
(d) 断网或拔代理制造预检失败，确认任务**暂停并在卡片上显示中文原因（含失败的读名）**，
    而不是静默消失。

**评审状态**：本 stage 为验证 + 小 bug 修复（Human 拍板）。本任务触及平仓完成判定
与划转（资金动作），属 `HIGH_RISK`；§4.1 与 §4.2 的行为变更须在交接件逐条给出测试证据。

---

## 附：待决与待办（不属本任务范围）

1. ~~前端执行模式徽标醒目化~~：**已并入本任务 Goal 5**（Human 2026-08-06 决定），
   不再另开。
2. `hedge_open_settings.executor_mode_snapshot`（停在 2026-07-27 的 `disabled`）
   为死字段，前端未使用——清理与否另议。
3. review-1 记录的不阻塞后续项 S-1 / S-2 / S-3 与 N-1..N-5（见
   `evidence/2026-08-06-hedge-order-close-validation-review1-transport-evidence-drop-dryrun.handoff.md`），
   由 Bookkeeper 排期。
4. 本 dispatch 由 claude-opus-5 起草（实测 + 范围界定），**未改 `status.json`**；
   派发前需 bookkeeper（deepseek）更新 `current_task` 与 `status_revision` 至 6，
   并按 Task Handoff Evidence Contract 预检交接件路径 `test ! -e`。

# 实施任务：preflight 改读本地缓存（开单 + 平仓）+ preflight_incomplete 有限重试后暂停

阶段：`2026-08-06-hedge-order-close-validation`（验证下单/平仓核心链路 + 修复小 bug）
status.json：`reports/agent-runs/2026-08-06-hedge-order-close-validation/status.json`

背景：2026-08-06 THE 实盘出现「任务静默停摆 33 分钟」，取证定位为 **问题 C**。
claude-opus-5 完成只读实测（仅 GET，未下单），三组数据：

**① 耗时构成（实测，串行）**

| 环节 | 耗时 | 频率 |
|---|---|---|
| 建卡 `check_symbol_legs` | 2.79s | 每次建卡 |
| 建卡 `get_snapshot` | 9.95s | 每次建卡 |
| **建卡合计** | **12.74s** | ← 用户可感知的「回显要等十几秒」 |
| 开单 `get_snapshot` | 6.64s | **每个 attempt** |
| 平仓 `get_snapshot` + 专属读 | ~8.9s | **每个 attempt** |

单项分解：`fapi exchangeInfo` 2.88s（**1.06 MB**，占 43%）、`positionSide/dual` 1.11s、
`balance` 0.83s、`rateLimit/order` 0.62s、`restricted-asset` 0.46s、
`spot exchangeInfo` 0.45s、`ticker/price` 0.38s；平仓额外
`/api/v3/account` 1.40s + `/api/v3/rateLimit/order` 0.80s。
**建卡时 `fapi exchangeInfo` 被拉了两次**（探针一次 + 快照一次），纯浪费 ~2.9s。

**② C 的直接根因（实证）**

`fapi exchangeInfo` 连测 5 次：`15.68s / 6.13s / 6.29s / 3.74s / 4.07s`——
抖动 3.7~15.7 秒，而 `DEFAULT_TIMEOUT_SECONDS = 10.0`。**最大的那个请求经常击穿超时**
→ `_read_public_json` 吞掉异常返回 None → `get_snapshot` 整盘 None →
`SIGNAL_PREFLIGHT_INCOMPLETE` → `service.py:1450` **worker 直接退出** → 任务静默停摆到人工干预。
（交接曾假设「重启后首次快照未就绪」，已被证伪：16:41:59 preflight 刚成功，
**同一进程 75 秒后**即 incomplete；provider 无任何进程级状态。）

**③ 本地已有缓存（关键）**

`SnapshotService._global_source_cache` 已缓存 preflight 所需的绝大部分数据，
且**所有私有源均为 60s TTL**：

| preflight 的读 | 本地缓存 source_id | 刷新周期 |
|---|---|---|
| fapi exchangeInfo | `group_b_public.futures_exchange_info` | 1800s |
| spot exchangeInfo | `group_b_public.spot_exchange_info` | 1800s |
| ticker/price | `price_map` | 60s |
| restricted-asset cap | `restricted_asset`（带 `checked_at`） | 按 due |
| papi balance | `unified_balances`（`/papi/v1/balance`） | **60s** |
| 平仓 `/api/v3/account` | `spot_balances`（同一端点） | **60s** |
| positionSide/dual | ❌ 无 | — |
| spot rateLimit / papi rateLimit | ❌ 无 | — |

Human 拍板：**把实时查询换成本地缓存**；**保留每轮校验**（不降级为「建卡一次性校验」——
换缓存后每轮成本≈0，而一次性校验会让久置任务拿几小时前的快照下单，更不安全）。

## Identity

- task_id: `2026-08-06-hedge-order-close-validation-preflight-local-cache`
- target_role: `Implementer`
- target_model: `deepseek`（Human 指定）
- provider: 按 `agents/roles.md` 模型映射
- status_revision: 4
- required_skill: `agents/skills/senior-developer.md`
- 前置：本任务与 `03-transport-evidence-and-drop-dryrun.dispatch.md` **无代码冲突**，
  但若 03 已交付，以其交付后的工作树为基线。

## Goal

1. `HedgePreflightProvider` 的慢变/可缓存读改走 **SnapshotService 本地缓存**，
   带**陈旧上限**保护；缓存不可用时**降级实时读**（不比现状更差）。
2. 两个本地没有的账户级配置（`positionSide/dual`、`rateLimit/order`）**进程内读一次 + 长 TTL**。
3. 平仓路径同样受益，但**两条硬边界保持实时**（见 §3，写错会导致重复平仓/错误关闭周期）。
4. `preflight_incomplete` 从「静默退出」改为**有限重试后暂停 + 卡片显示中文原因**。

目标数字：

| | 现在 | 改后 |
|---|---|---|
| 建卡回显 | 12.74s | ~0.1s |
| 开单每轮 preflight | 6.64s | ~0ms |
| 平仓首轮 | ~10.7s | ~1.6s |
| 平仓每轮 | ~8.9s | ~0.44s（仅保留平完判定） |

---

## 实现要求

### 1. 只读注入 seam（两服务保持解耦）

`HedgeOpenTaskService` 与 `SnapshotService` 现为**刻意解耦**
（`service.py:591-595` 注释：「SnapshotService stays uninjected here」），
**禁止直接 import**。照抄既有先例 `configure_cache_refresh`
（`service.py:588`，`server.py:1064` 注入）：

1. **`backend/services/snapshot_service.py`**：新增**公开只读**方法
   `get_cached_source(source_id) -> tuple[float, Any] | None`
   （返回 `(monotonic_ts, value)`，缺失返回 None）。内部复用既有
   `_cached_source_value`/`_global_source_cache`（`:1213-1215`）。
   **只读，不得触发任何刷新**（不得调用 `_refresh_due_sources`）。
2. **`backend/services/hedge_preflight_provider.py`**：构造函数新增可选参数
   `snapshot_reader: Optional[Callable[[str], tuple[float, Any] | None]] = None`。
   **`None` 时行为逐字不变**（走现有实时读路径）——这保证既有测试零改动。
3. **`backend/app/server.py`**：`_build_hedge_service` 之后、
   与 `configure_cache_refresh` 同处注入 `snapshot_reader`
   （绑定到 SnapshotService 实例的新方法）。

### 2. 缓存映射 + 陈旧上限（核心）

改造 `hedge_preflight_provider.py` 的以下方法：**先查缓存 → 命中且未超陈旧上限则用；
否则降级走原有实时读**。

| 方法 | source_id | 取值路径 | 陈旧上限 | 超限行为 |
|---|---|---|---|---|
| `_read_perp_filters` (:241) | `group_b_public` | `["futures_exchange_info"]["symbols"]` | **2h** | 降级实时读 |
| `_read_spot_record` / `_read_spot_leg` (:251) | `group_b_public` | `["spot_exchange_info"]["symbols"]` | **2h** | 降级实时读 |
| `_read_est_price` (:313) | `price_map` | 按 symbol 取价 | **5min** | 降级实时读 |
| `_read_balances` (:327) | `unified_balances` | `[{asset, crossMarginFree}]` | **5min** | 降级实时读 |
| `_read_spot_account_usdt` (:423) | `spot_balances` | `[{asset, free}]` 取 USDT | **5min** | 降级实时读 |
| `_read_collateral_cap_hit` (:392) | `restricted_asset` | `value["exceeded"]` 集合 | **10min** | **fail-closed（返回 None）** |
| `check_symbol_legs` (:598) | `group_b_public` | 两个 exchangeInfo | **2h** | 降级实时读 |

**要点**：

- **`restricted_asset` 是唯一 fail-closed 项**：它是 51169 抵押额度打满导致
  「合约腿成交 / 现货腿被拒 → 裸空」的**唯一预警**，陈旧时绝不许猜。
  它的 value 自带 `checked_at`，优先用该字段判陈旧（比 monotonic 更准）。
- **缓存的字段形状必须按实际结构解析**，不得假设：
  `unified_balances` 来自 `/papi/v1/balance`（字段 `crossMarginFree`）、
  `spot_balances` 来自 `/api/v3/account` 的 `balances`（字段 `free`）——
  与 `_read_balances` / `_read_spot_account_usdt` 现有解析逻辑保持一致。
- **降级实时读时必须记录**（stderr + 后续 §4 的失败读名），否则「缓存一直不可用而在偷偷
  走慢路径」不可见。
- `check_symbol_legs` 与 `get_snapshot` 命中同一份 `group_b_public`，
  **建卡时那次重复的 1.06MB 读自然消除**——不需要额外去重逻辑。

### 3. 账户级配置：进程内读一次 + 长 TTL

`positionSide/dual`（1.11s）与 `rateLimit/order`（0.62s）本地无缓存，但是**账户级设置，
不主动更改则不变**。在 `HedgePreflightProvider` 内加进程级缓存：

- `_read_position_mode`（:351）、`_read_rate_limit_order`（:373）、
  `_read_spot_rate_limit_order`（平仓路由用）三者各自缓存，**TTL 600s**；
- **失败不缓存**（只缓存成功值），失败仍按现有 fail-closed 返回 None；
- `dualSidePosition` 的语义不变：只有字面 `false` 确认单向，缺失/歧义仍 fail-closed。

### 4. 平仓路径：两条硬边界**必须保持实时**

平仓受益于以上全部改造，**但下列两处禁止使用缓存**，实现者若改为读缓存判不合格：

**① `_verify_close_flat`（`service.py:1465`，每轮调用于 `:1405`）→ `query_symbol_um_qty`**

必须保持实时签名读。理由（**比误判更严重的方向**）：该判定的分支是
`flat → 关闭周期+写结算日志` / `open + 有次数 → 继续下一条 attempt`。
`um_positions` 缓存 TTL 60s，**平仓单刚成交后缓存仍是平仓前的持仓** →
判定 `open` → **继续下一轮 → 重复平仓 → 超卖**。这是不可逆的资金后果。

**② `_ensure_close_spot_balance`（`service.py:1497`）的划转后复检**

`xfer(...)` 之后的 `recheck = q_spot(base_asset)`（`:1546`）必须实时。
其存在意义就是防「响应丢失但划转其实成功」的误判，缓存必然读到划转前旧值。

**③ 划转触发改为「缓存放行、实时确认才动手」**

`_ensure_close_spot_balance` 的首次余额判断（`:1517` `free = q_spot(base_asset)`）：

- 缓存显示**充足** → 直接放行（0 网络请求，覆盖绝大多数情况）；
- 缓存显示**不足** → **必须再做一次实时读确认**，实时读仍不足才发起
  `universal_transfer`。
- 理由：划转是**有副作用的真实资金动作**，缓存误判会白划一次。
  统一原则：**缓存只用于「放行」，不用于触发有副作用的动作**。

`query_unified_free`（可划转量，`:1525`）属放行类，可用 `unified_balances` 缓存。

### 5. `preflight_incomplete`：有限重试后暂停（替代静默退出）

现状（`service.py:1450-1451`）：

```python
if signal == D.SIGNAL_PREFLIGHT_INCOMPLETE:
    return self._worker_exit(task_id, D.WORKER_EXIT_PREFLIGHT_INCOMPLETE)
```

worker 直接退出，卡片上无任何提示，只有 HTTP Start/recover 能重新拉起
（Amendment 21：live 模式无全局 scanner）。实测后果：16:43:14 一条事件后
**33 分钟零活动**直到人工点按钮。

改为：

1. **同一任务内有限重试**：连续 incomplete **最多 2 次重试**，间隔 **2 秒**
   （复用 worker 既有的 stop-event 等待，不新增定时器/线程）；
2. 重试仍失败 → `_pause_task_local`，新增
   `D.PAUSE_REASON_PREFLIGHT_INCOMPLETE` + 中文文案
   （形如「预检数据不完整（<失败的读名>），任务已暂停（fail-closed，未发单）；
   请检查网络后手动恢复」）——**卡片可见**，不再静默；
3. 重试计数**进程内即可**（不新增 DB 列），任务成功派发一次即清零；
4. `_record_preflight_incomplete`（`:2241-2250`）的 payload 增加
   **失败的读名**字段（当前仅 `{reason, coin, direction}`，无法回溯是哪个读挂了——
   这是 C 排查时的第二个取证盲区）。`get_snapshot` 需把「第一个失败的读」
   回传给调用方（新增返回通道或 provider 侧记录最近一次失败读名，二选一，
   不得为此改 `PreflightSnapshot` 的冻结形状）。

**不变**：fail-closed 语义本身（残缺事实上永不授权下单）、
`SIGNAL_PREFLIGHT_FATAL` 的既有停机路径。

---

## 不在本次范围

- 不改 `_dispatch_live` / `classify_*` / ADR-2 不重发语义；
- 不改 SnapshotService 的**刷新策略/周期/due 规则**——本任务对它**只读**，
  一行刷新逻辑都不许动；
- 不给 `balance` 之外的账户读加「新鲜度强制刷新」（不得从 preflight 触发
  `force_account_panels` 刷新，那是状态面板的路径）；
- 不做 dry-run 相关改造（属 dispatch 03）；
- 不动前端（执行模式徽标的醒目化另议，见附注）；
- 不改 `DEFAULT_TIMEOUT_SECONDS`（换缓存后 1.06MB 的超时面自然消失，
  改超时值是治标）。

## Allowed Files

可修改：

- `backend/services/hedge_preflight_provider.py`（主体：缓存映射 + 陈旧上限 + 账户配置 TTL）
- `backend/services/snapshot_service.py`（**仅新增只读 `get_cached_source`**，不改刷新逻辑）
- `backend/app/server.py`（注入 `snapshot_reader`）
- `backend/hedge_open_tasks/service.py`（incomplete 重试/暂停、
  `_record_preflight_incomplete` 失败读名、`_ensure_close_spot_balance` 划转实时确认）
- `backend/hedge_open_tasks/domain.py`（`PAUSE_REASON_PREFLIGHT_INCOMPLETE` + 中文文案 + 重试常量）
- `backend/tests/test_hedge_preflight_provider.py`、`test_hedge_task_local.py`、
  `test_hedge_cycle_close.py`、`test_snapshot_service.py`（新增用例）

只读：

- `reports/agent-runs/2026-08-06-hedge-order-close-validation/status.json`
- `evidence/` 下三份取证文档（diagnosis / crosscheck / 本 dispatch 背景数据来源）
- `backend/services/private_client.py`（各 fetcher 的字段形状与 60s TTL）

禁止：

- 直接在 `hedge_open_tasks/` 或 `hedge_preflight_provider` 中 `import` SnapshotService；
- 让 preflight 触发任何缓存刷新（只读）；
- 对 §4 两条硬边界使用缓存；
- 未授权提交、移动 HEAD、对实盘发单/划转。

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
9. `evidence/2026-08-06-hedge-order-close-validation-the-single-leg-dryrun-diagnosis.md`
   §4（问题 C 机理）与 `*-crosscheck.md` §2.3（exit-vs-retry 实证）——**必读**
10. 按需：`snapshot_service.py:1213 / :1233 / :1288-1340`、
    `hedge_preflight_provider.py:188-196 / :241-441 / :482-596`、
    `service.py:588-597（注入先例）/ :1395-1460 / :1497-1560 / :2241 / :2278-2310`

## Acceptance Checks

1. **注入解耦**：`hedge_open_tasks/` 与 `hedge_preflight_provider.py` grep 不到
   `SnapshotService`；`snapshot_reader=None` 时 provider 行为**逐字不变**
   （既有 provider 测试零修改通过）。
2. **缓存命中**：注入伪 reader 后，`get_snapshot` 的 7 个读**零网络请求**
   （用 spy 断言 `_public_urlopen` / client 方法调用次数为 0）。
3. **陈旧降级**：每个缓存项超陈旧上限 → 走实时读（spy 断言发生了实时调用）；
   `restricted_asset` 超 10min → **返回 None（fail-closed）**，不降级、不猜。
4. **账户配置 TTL**：`positionSide/dual` 等三项在 600s 内只读一次；读失败不写缓存。
5. **平仓硬边界（重点）**：
   - 注入伪 reader 后，`_verify_close_flat` 仍发生**实时** `query_symbol_um_qty` 调用；
   - 构造「缓存显示 open、实盘已 flat」与「缓存显示 flat、实盘仍 open」两种场景，
     断言判定以**实时**结果为准；
   - 划转后复检为实时读；
   - 缓存显示不足 → 断言**先做实时确认**、实时充足则**不发起划转**。
6. **incomplete 重试/暂停**：连续 incomplete → 重试 2 次（间隔 2s）→ 暂停，
   `pause_reason=PREFLIGHT_INCOMPLETE` + 中文原因**含失败的读名**；
   成功派发一次后重试计数清零；worker 不再静默退出。
7. **性能证据**（写进交接件）：注入缓存前后各测一次 `get_snapshot`
   （开单 + 平仓各一），附耗时对比；建卡路径断言 `fapi exchangeInfo`
   **只读 0 次**（缓存命中）或 1 次（冷启动降级），不再是 2 次。
8. **回归**：`python3 -m pytest backend/tests -q` 全绿 + `node frontend/self-check.js` 全绿。
9. **范围核对**：`git status --short` 仅列 Allowed Files；SnapshotService 的
   `git diff` **只有新增只读方法**，无刷新逻辑改动。

## Stop

按 `AGENTS.md` §7 返回完整中文 `[TASK_RESULT v2]`（含三行中文交接），`下一步任务` 用可执行形式
`读取：<路径或 none>；执行：<立即动作>；关卡：<下一验证>`。

下一关卡：Human 用 `scripts/run-server.sh` 重启服务实盘复测——
(a) 建卡回显是否从十几秒降到秒内；
(b) 连续开单每轮是否不再有 6~7 秒预检等待；
(c) 平仓任务的「平完判定」仍以实时为准（不出现重复平仓）；
(d) 断网/拔代理制造 preflight 失败，确认任务**暂停并在卡片上显示中文原因**，
    而不是静默消失。

**评审状态**：本 stage 为验证 + 小 bug 修复（Human 拍板）。§4 的两条硬边界涉及
**不可逆资金后果**（重复平仓 / 错误关闭周期），交接件须逐条给出测试证据。

---

## 附：待决与待办（不属本任务范围）

1. **dispatch 03 的 B-4 需修订**：起草 03 时判断「运行期无执行模式提示」有误——
   前端**已有**徽标（`frontend/index.html:4493` `renderHedgeExecutionStatus`），
   且数据源是进程实时 `self._mode`（`service.py:856`），非陈旧 DB 字段。
   B-4 应从「加 stderr 警告」改为「**把徽标做醒目**：dry-run 时状态栏变警示色 +
   『成交1次』按钮标注演习模式」。**待 Human 确认后由 bookkeeper 修订 03**。
2. `hedge_open_settings.executor_mode_snapshot`（停在 2026-07-27 的 `disabled`）
   确为死字段，但前端未使用——清理与否另议。
3. 本 dispatch 由 claude-opus-5 起草（实测 + 范围界定），**未改 `status.json`**；
   派发前需 bookkeeper（deepseek）更新 `current_task` 与 `status_revision` 至 4。

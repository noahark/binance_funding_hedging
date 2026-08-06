# Diagnosis: THE 单腿裸露 / dry-run 假成交 / preflight_incomplete 三问题取证

## 元信息

- stage_id: `2026-08-06-hedge-order-close-validation`
- 文档类型: **诊断报告（read-only 取证）**——未改任何代码、未动任何数据、未发任何单
- 作者模型: **claude-opus-5（Claude Opus 5，Claude Code CLI）**
- 作成时间: `2026-08-06 CST`
- base_sha: `f153cdc`（工作树含 stage 未提交改动）
- 取证对象: `data/hedge-open-tasks.sqlite3`、`backend/**`、本机网络/代理环境
- 结论摘要: 三个问题**根因各自明确**；交接文档中的 **A「raw_response 空无法取证」与
  C「重启后首次快照未就绪」两个假设均被证伪**；B 的根因不是时点巧合而是**启动方式漏加载
  `.env`**，且其危害远大于原判断（假执行 + 真记账，已污染持仓口径）。

---

## 0. 时间口径

数据库存 epoch us，报告统一用 **CST 本地时间**。用户观察窗口用的是 UTC，二者差 8 小时：
UTC 08:38 = CST 16:38，UTC 08:41 = CST 16:41，UTC 09:16 = CST 17:16。下文全部为 CST。

---

## 1. 事实基线（DB 实测）

### 1.1 任务

| task_id | coin | created | updated | success/fail | status | exit_reason |
|---|---|---|---|---|---|---|
| `7eeab9c3` | THEUSDT | 16:41:56 | 17:16:30 | 1 / 1 | done | task_not_running |
| `97b0f068` | THEUSDT | 16:15:47 | 16:16:12 | 0 / 0 | paused | leverage_set_failed |
| `e22ce275` | THEUSDT | 16:06:13 | 16:38:06 | **2 / 0** | done | preflight_incomplete |
| `56e7ded9` | THEUSDT | 12:26:14 | 16:15:57 | 0 / 2 | deleted | task_not_running |

### 1.2 attempt / leg（`hedge_open_attempt` + `hedge_open_leg`）

| attempt | task | 时间 | pair_outcome | spot order_id | perp order_id |
|---|---|---|---|---|---|
| 4 | e22ce275 | 16:38:06 | accepted_pair | `dryspot-af62e4df…` | `dryperp-af62e4df…` |
| 5 | e22ce275 | 16:38:06 | accepted_pair | `dryspot-59cd4c77…` | `dryperp-59cd4c77…` |
| 6 | 7eeab9c3 | 16:41:59 | **single_leg**（absent / -2013） | `834390514` FILLED 200 | 空 / UNKNOWN |
| 7 | 7eeab9c3 | 17:16:08 | accepted_pair | `834392365` FILLED 200 | `2031628184` FILLED 200 |

`hedge_open_fill` 表**为空**——持仓口径实际来自 `hedge_open_leg`（见 §3.2）。

### 1.3 事件日志（`hedge_open_log`，16:00 后全量）

```
16:00:48  89a2937f  leverage_set_failed    set_leverage http=401 {'code': -2015, ...}
16:06:16  e22ce275  preflight_incomplete
16:16:05  97b0f068  leverage_set_failed    set_leverage http=401 {'code': -2015, ...}
16:38:06  e22ce275  record_transport       {"transport": "dry_run_record", "posted": false, ...}
16:38:06  e22ce275  record_transport       {"transport": "dry_run_record", "posted": false, ...}
16:43:14  7eeab9c3  preflight_incomplete
17:16:08  7eeab9c3  record_transport       {"transport": "live", "posted": true, ...}
```

attempt 6 **没有** `record_transport` 事件——原因见 §2.3（不是丢日志，是写入点在结算侧）。

---

## 2. 问题 A：attempt 6 合约腿 -2013（现货成交、合约无单）

### 2.1 决定性证据（`hedge_open_raw_response`，交接文档称"空"，实为有）

```
id=9   attempt=6  leg=perp  source=order_post   16:41:59
       http_status=NULL   transport_error=connection_error   body=（空）

id=11  attempt=6  leg=perp  source=order_query  16:42:46
       http_status=400    business_code=-2013   body={"code":-2013,"msg":"Order does not exist."}
```

对照现货腿 `id=8` 同一秒 `http_status=200` + `orderId 834390514` FILLED。

### 2.2 机理链条（全部为设计内行为）

1. `live_hedge_executor.py:904-911` — `dispatch()` 双腿**并发两线程**（frozen §6.3.4），
   互不等待。现货打 `api.binance.com`，合约打 `papi.binance.com`。
2. `hedge_open_live_client.py:224-226` — 合约腿 POST 抛 `urllib.error.URLError`
   → 返回 `transport_error="connection_error"`，无 HTTP 响应。
3. `live_hedge_executor.py:359-360` — `classify_leg_response`：`transport_error is not None`
   → `LEG_UNKNOWN_QUERYING`。**这是强制要求**：传输失败不能断定订单未到达，
   绝不重发写 POST（ADR-2）。
4. `live_hedge_executor.py:456-461` — 47 秒后（16:42:46）drain 查询拿到 400/-2013
   → `LEG_REJECTED` + `error_category=absent`（Amendment row 5：只有显式 404/-2013
   才是权威 absent 信号）。
5. 结算为 `single_leg` → fail_count=1 → 任务留下裸现货多头 200。

### 2.3 为什么没有 `record_transport` 日志

`service.py:2557-2559`：存在 UNKNOWN 腿时 `_mark_legs_querying` 后**提前 return**，
不进入结算路径，而 `record_transport` 事件写在结算侧。attempt 7 双腿一次性终态，
故有该日志。**取证缺口已被 `hedge_open_raw_response` 的 `order_post` 行覆盖**。

### 2.4 判定正确性

交易所实况 `um_amt=-200`（仅 attempt 7 的 200 空单），与 absent 判定一致。
**该腿确实从未到达交易所，系统处理正确，非 bug。**

### 2.5 真正的取证盲区（可修）

`hedge_open_live_client.py:224-226`：

```python
except urllib.error.URLError as exc:
    # connection loss / DNS / refused — no HTTP response was received
    return HedgeHttpResponse(None, None, "", "connection_error", None)
```

**`exc` 被整个丢弃**，只留分类字符串。无法区分 connection refused / reset by peer /
TLS handshake failure / DNS / 代理断开。这是"无法进一步定位"的唯一原因。

### 2.6 环境根因指向

本机全局代理（实测）：

```
HTTP_PROXY / HTTPS_PROXY / ALL_PROXY = http://127.0.0.1:6152
scutil --proxy: HTTPEnable=1 HTTPPort=6152 / HTTPSEnable=1 HTTPSPort=6152
```

`urllib` 默认走 `getproxies()`，**所有币安流量经本地代理 6152（Surge）**。现货
`api.binance.com` 与合约 `papi.binance.com` 是两个 host、两条独立代理连接——
代理侧节点切换/连接池重建会让其中一条瞬断，精确解释"同一毫秒一腿成、一腿断"。

本次诊断时探测（无凭证，只读）：

```
fapi/exchangeInfo        3/3 ok   1,056,180 bytes   1.48s / 1.91s / 2.67s
spot/exchangeInfo?THE    3/3 ok       5,301 bytes   0.59s / 0.70s / 0.81s
spot/ticker?THE          3/3 ok          41 bytes   0.49s / 0.32s / 0.37s
papi/balance (no-auth)   5/5 HTTP 401                0.52s ~ 0.82s
```

papi 5/5 可达 → **瞬时故障，非持续不可达**，与 §2.4 结论互证。

---

## 3. 问题 B：dry-run 假成交（e22ce275）

### 3.1 根因：进程启动时未加载 `.env`，不是按钮、不是时点巧合

- `service.py:2154-2156` — `_live_dispatch_capable() = self._live_mode and
  hasattr(self._executor, "dispatch")`，**进程级常量，运行中不可能改变**。
  故 16:38 走 `_dispatch_simulated` 只能意味着该进程 `mode != "live"`。
- `server.py:988-991` — `mode = config.hedge_executor`；非 live 时
  `HedgeOpenTaskService(db_path, mode=mode)`，executor 为 None →
  `service.py:481` 默认 `RecordTransportExecutor()`。
- `config.py:213-222` — `APP_HEDGE_EXECUTOR` 缺省 `"disabled"`。
- `scripts/run-server.sh:16-24` — **只有该脚本**会 `set -a; source .env; set +a`。
  直接 `python -m backend.app.server` → 缺省 disabled。
  （`scripts/service-control.py:220-223` 走 launchd 调 run-server.sh，是安全路径。）

### 3.2 时间线闭环（三次进程更替）

```
16:00:48  live 进程   leverage -2015（端点错：/fapi/v1/leverage 用在 PM 账户）
16:06:16  live 进程   preflight_incomplete   ← 只在 live 分支产生（service.py:2299-2304）
16:16:05  live 进程   leverage -2015
   ~16:35            hedge_open_live_client.py mtime：端点改为 /papi/v1/um/leverage
                     → 重启（漏 .env）→ mode=disabled
16:38:06  dry 进程    e22ce275 两笔假成交（dryspot-/dryperp-）
   16:38~16:41       再次重启（带 .env）→ mode=live
16:41:59  live 进程   attempt 6 真单；leverage 不再报错（端点修复生效）
17:16:08  live 进程   attempt 7 双腿真成交
```

`16:06:16` 的 `preflight_incomplete` 是关键反证：它只在 `if live:` 分支内产生，
证明 16:06 时进程为 live，而 16:38 为 simulated → **中间必然换过进程**。

### 3.3 危害（本问题真正的严重性）

`disabled` 不是"不执行"，而是**假执行 + 真记账**：`RecordTransportExecutor`
（`executor.py:253-347`）写入 `dryspot-`/`dryperp-` 前缀的 leg 行，
`cumulative_base_qty=200`；而持仓聚合 `store.py:2487-2530` 遍历 `leg_rows`
**无差别累加**：

| 口径 | 真实（交易所） | dry 虚增 | 本地显示 |
|---|---|---|---|
| spot_qty | 400 | +400 | **800** |
| perp_qty | 200 | +400 | **600** → position_qty **−600**（forward 取负） |

与用户观测完全一致（`spot_bal=400` 真实余额 vs `spot_qty=800` 本地记账；
`um_amt=-200` vs `position_qty=-600`）。此外 `success_count=2` 被计入，
周期 `096232b7` 的成本基同样被污染。

**软删除无法修复**：`store.py:2500-2502` 中 deleted 状态只置 `includes_deleted`
标志，leg 行**仍然累加**。必须物理清理或在聚合层排除。

### 3.4 附带发现：模式可见性缺失

`hedge_open_settings.executor_mode_snapshot` 当前值 `"disabled"`，
`updated_at_us` 停留在 **2026-07-27 22:14**——是个陈旧死字段，与实际运行模式无关，
**反而误导**。运行期没有任何前端常驻标识能让人区分 live / dry-run。

---

## 4. 问题 C：preflight_incomplete（交接假设被证伪）

### 4.1 原假设"服务重启后首次快照未就绪窗口"不成立

硬反证：**16:41:59 派发前 preflight 刚成功**（否则不会创建 attempt 6 并发出真单），
**同一进程 75 秒后**的 16:43:14 即 `preflight_incomplete`。与重启无关。

### 4.2 实际机理：每次派发实时拉 7 个 HTTP，零缓存，任一失败即 fail-closed

`hedge_preflight_provider.py:508-530` + `:554-557`，`DEFAULT_TIMEOUT_SECONDS = 10.0`：

| 读 | 端点 | 实测体量/耗时 |
|---|---|---|
| perp filters | `fapi/v1/exchangeInfo`（**全量**） | **1.06 MB / 1.5–2.7s** |
| spot leg | `api/v3/exchangeInfo?symbol=` | 5 KB / 0.6–0.8s |
| est price | `api/v3/ticker/price?symbol=` | 41 B / 0.3–0.5s |
| balances | `papi/v1/balance` | 签名 |
| position mode | `papi/v1/um/positionSide/dual` | 签名 |
| rate limit | `papi/v1/rateLimit/order` | 签名 |
| collateral cap | `sapi/v1/margin/restricted-asset` | forward open 才读 |

`_read_public_json:188-195` 对**任何异常一律 `return None`**（连异常类型都不留），
任一读失败 → `get_snapshot` 返回 None → `service.py:2299-2304` fail-closed 重试。

### 4.3 与问题 A 同源

16:41:59 的 perp `connection_error` 与 16:43:14 的 `preflight_incomplete` 相隔 75 秒，
指向**同一时间窗的代理/网络抖动**（§2.6）。二者不是两个独立故障。

### 4.4 第二个取证盲区

`service.py:2241-2250` — `_record_preflight_incomplete` 的 payload 仅
`{reason, coin, direction}`，**不记录是哪一个读失败**。C 的具体失败点在现有数据下
**不可回溯**，必须先补字段再等复现。

### 4.5 关于"改为排队等待而非 fail-closed"的立场

**不建议改**。在残缺事实上授权真实下单的风险，远大于任务停摆的成本；fail-closed 是正确的。
应做的是（a）记录失败的那个读，(b) 给 1.06 MB 的 `fapi/v1/exchangeInfo` 加进程内短 TTL
缓存——它是 preflight 中最重、最易超时的一环，且 exchangeInfo 分钟级不变。

---

## 5. 建议动作（未执行，待 Human 决策）

| 优先级 | 项 | 位置 | 备注 |
|---|---|---|---|
| **P0-1** | 清理 attempt 4/5 的假 leg 行（dry 前缀） | `hedge_open_leg` / `hedge_open_attempt` | **破坏性，需 Human 点头 + 先备份 DB** |
| **P0-2** | 持仓聚合 / success_count 排除 `dry*` 订单前缀 | `store.py:2487-2530` | 防复发第一道 |
| **P0-3** | 前端常驻显示当前 executor_mode；废弃或修正陈旧的 `executor_mode_snapshot` | 前端 + settings | 让 dry-run 不可能被误当真单 |
| P1-1 | `URLError` 保留 `exc.reason` 写入 transport_error | `hedge_open_live_client.py:224-226` | 约 3 行 |
| P1-2 | `preflight_incomplete` payload 记录失败的读名 | `service.py:2241-2250` + provider | 小 |
| P1-3 | `fapi/v1/exchangeInfo` 进程内 TTL 缓存 | `hedge_preflight_provider.py:242` | 小；显著降低 C 复发面 |

### 附注（非本次三问题）

- 周期 `096232b7` 的 `first_task_id` / `last_task_id` 仍指向已删除的 `56e7ded9`，
  `last_task_id` 未随成功腿更新。
- `leverage -2015` 根因已在工作树修复（`/fapi/v1/leverage` → `/papi/v1/um/leverage`，
  PM 账户必须用 PAPI 端点），16:41 后未再复现；对应改动尚未提交。

---

## 6. 本次诊断的边界声明

- 全程 **read-only**：未修改任何源码、未执行任何 DDL/DML、未发出任何交易请求。
- 对外网络仅发起**无凭证只读探测**（公共 exchangeInfo / ticker，以及 papi 未授权
  401 探活），用于验证 §2.6 连通性假设。
- 所列代码行号基于 base_sha `f153cdc` + stage 未提交工作树，后续改动会漂移。

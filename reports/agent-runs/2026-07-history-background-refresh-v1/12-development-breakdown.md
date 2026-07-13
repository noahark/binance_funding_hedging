# Development Breakdown — `2026-07-history-background-refresh-v1`

> 开发细化（development breakdown）。把 `10-design.md` / `11-adr.md` 的冻结设计
> 转成一个 bounded 实现者无需再做产品或架构判断即可执行的任务包。

## Author Identity（作者身份，review-2 设计涉入披露用）

- provider: **Anthropic**
- model: **Opus 4.8**（本节点由操作者显式指定，覆盖 workflow 的 Fable5-first 默认）
- skill: `task_planner`
- mode: `read_write_docs`
- 设计涉入声明（disclosure）：本文件属 design involvement。加上 Codex 为 designer、
  Claude Opus 4.8 曾做 design review，**review-2 最终评审的 provider 隔离必须由
  bookkeeper 在 dispatch 前重新评估**（见 `status.json.review_2`），这不是本
  breakdown 的 blocker。

## 冻结的上游裁定（本 breakdown 不再重开）

- 冷启动（cold-start）：`brief_503_before_immediate_base_publication`——首次 base
  发布前，snapshot / symbol 读接口短暂返回 503；任何请求都**不**等待 deep-history
  扫描。来源：`status.json.human_gates.cold_start`（`approved_in_design_discussion`）。
- kill switch：`present_and_default_enabled`，offline 强制不启动 worker。来源：
  `status.json.human_gates.background_kill_switch`。
- 复杂度 `MEDIUM`，`parallel_mode=false`，`auto_review_pipeline=false`。不得引入
  R1–R10 并行机制。

---

## 1. 冻结的产品语义（Frozen Product Semantics）

实现者按下列语义编码，不得自行更改：

1. **全量 snapshot 端点是 canonical `PublishedState` 的纯读**：
   `GET /api/public-market/snapshot` 在 live 后台模式下**零上游抓取**，只返回一份
   完整的旧版或新版已发布状态。
2. **默认预热集 = 有效费率子集**（valid-rate subset）：
   `route_class != "PERP_ONLY_EXCLUDED"` **且**
   `abs(Decimal(daily_funding_rate)) > Decimal("0.00030000")`。
3. **null/非法费率行可见但有意不预热**：前端 `absDailyRateAtOrBelowThreshold`
   对 null/空/非法返回 `false`（`frontend/index.html:1187-1204`），即这些行默认
   首页可见；后端预热选择器**排除**它们（因为 `Decimal(None)` 无意义）。它们保留
   一次性 click 刷新能力。此不一致是**有意**的，必须有 null 边界向量证明。
4. **一次点击 = 一条 `RefreshSymbolCommand`**，不是订阅 / watched set / 优先级
   记录 / 独立 interest TTL。
5. **点击刷新的四项**：选中 symbol 的公开市场字段、完整 30 天 settled 历史、
   选中 base asset 的**实际借币利率**、选中 base asset 的**实际 max-borrowable**。
6. **点击绝不抓取**：余额（balances）、持仓（positions）、账户估值（account
   valuation）、无关资产（unrelated assets）、整宇宙公开 snapshot（full
   `fetch_raw()`）。
7. **后台发布完整 canonical 状态；点击响应只含一行**，且该行投影自
   **同一个 `published_version`**。
8. **前端只补丁该行 + 抽屉**：1 秒防连点、in-flight 期间忽略再次激活、依赖
   ≤60s 全量轮询做全局排序/汇总对账。

---

## 2. Ownership 与任务形态（Ownership And Task Shape）

**结论：一个 backend-dominant 的 bounded 实现，单 owner = `claude_glm`，review-1 =
`kimi`。** 与 `status.json.model_routing` / `00-task.md` 一致。

论据（按 `AGENTS.md` dominance 规则）：

- 工作量绝大多数在后端：worker 生命周期、命令队列、不可变发布、`build_snapshot`
  拆分、force-TTL 私有 API、新端点 + schema、失败矩阵、raw/signed 证据、后端测试。
- 前端仅轻量集成：`frontend/index.html` 改一处 fetch URL + 目标行补丁 + 1 秒防连点；
  `frontend/self-check.js` 加一条契约校验。属「light integration or display wiring」，
  按 dominance 规则可并入 backend-dominant 的整体 bounded task 交给 `claude_glm`。
- 无「both substantial and separable」情形，故**不拆双 owner**。

以下 T1–T9 是**同一个 dispatch 内的内部工作项顺序**（不是并行 owner 拆分）。

---

## 3. 精确的 allowed / forbidden 文件（Exact Allowed And Forbidden Files）

在 `00-task.md` 边界上进一步收窄。**Allowed（每条附理由）：**

生产代码：
- `backend/services/snapshot_service.py` — worker、命令队列、发布、`get_snapshot`
  改为读、`get_funding_history` 改为纯投影、`build_snapshot` 拆分为 base 刷新 +
  纯组装 + 选中行组装。
- `backend/services/private_client.py` — 新增 force-TTL exact-key bypass（**必须**
  在此文件，因 `test_single_hmac_exit_in_product_code` 禁止其它模块触碰
  hmac/hashlib/signature）。
- `backend/adapters/binance_public.py` — 新增 per-symbol premium-index 抓取
  `fetch_premium_index_for(symbol)`（点击不得调用整宇宙 `fetch_raw()`）。
- `backend/app/server.py` — 新增 `symbol-snapshot` 路由、worker start/stop 生命
  周期挂到服务启动/关闭、not-ready → 503 映射。
- `backend/config.py` — 新增 kill switch / tick / batch / timeout 配置及 env。
- `backend/domain/snapshot.py` — **仅当**需要一个窄范围纯函数 helper（如「从
  candidate 列表按选择器过滤」或「单行投影」）时才改；不得改动既有排序/组装语义。
- `schemas/api/public-market/symbol-snapshot.schema.json` — 新契约 schema。
- `frontend/index.html` — 点击流切换到 symbol-snapshot + 目标行补丁 + 1 秒防连点。

测试与证据：
- `backend/tests/` — 新增/扩展下列测试文件（见 §12）。
- `frontend/self-check.js` — 加 symbol-snapshot 契约校验。
- `reports/api-samples/2026-07-history-background-refresh-v1/` — raw 公开样本 +
  脱敏 signed 审计（该目录当前不存在，实现期创建）。
- `reports/agent-runs/2026-07-history-background-refresh-v1/` — 实现报告/测试输出。

**Forbidden（明确禁止）：**
- 任何交易执行/下单/借/还/划转/平仓等 mutating Binance 端点。
- `schemas/api/public-market/snapshot.schema.json`（主 snapshot schema **不改**，
  见 §9 的 same-version 证明方式）。
- 凭证值、展开的 alias/环境、签名、请求头、完整 signed query、余额、持仓、估值证据。
- `AGENTS.md`、`workflows/`、`agents/registry.yaml`、Harness 脚本/schemas。
- 用户批准前把内容写入 canonical `docs/`。
- 无关的前端布局/样式/过滤器/账户面板行为。
- `00-intake.md` / `00-task.md` / `10-design.md` / `11-adr.md` / `status.json` /
  `70-handoff.md`（bookkeeper 单写）。

---

## 4. 数据与并发模型（Data And Concurrency Model）

### 4.1 `PublishedState`（不可变，一次引用替换）

建议实现为 `@dataclass(frozen=True)` 或「构造后不再原地改」的对象，字段：
- `snapshot: dict` — 与今天 `assemble_snapshot()` 输出同形的完整 payload（含
  `rows`、`summary`、`warnings`、`private_account` 等，**不改主 schema**）。
- `data_time_ms: int` — settled-window 结束边界（annualization 与历史窗口共用）。
- `generated_at: str`
- `published_version: int` — **单调递增**（monotonic）；每次成功发布 +1。
- `rows_by_symbol: dict[str, dict]` — 由 `snapshot["rows"]` 派生的索引，供 O(1)
  单行投影；派生自同一对象，保证行/全量同版本。

发布：`self._published_state = next_state`（一次原子引用替换）。请求线程只读该引用，
因此永远看到**完整的旧版或新版**，绝不跨版本混字段。

### 4.2 worker 独占的可变状态（仅 worker 线程写）

- `_base_raw: dict | None` + `_base_raw_ts: float(monotonic)` — 上次成功
  `fetch_raw()` 结果与时间戳，驱动 60s base 节奏；点击复用它（不再抓整宇宙）。
- `_funding_history_cache: dict[str, tuple[float, list]]` — 既有结构，**改为
  worker-only 写**（`get_funding_history` 不再写它，见 §8）。
- `_history_cursor: int` — 稳定 candidate 列表上的滚动游标。
- `_last_private_inputs` — 上次发布时用于私有组装的输入束：`classic_ref`、
  `cost_leg`、`portfolio_by_asset`、`price_map`、以及已组装的 `private_account`
  块。点击 republish 复用非选中资产的这些输入，**只**覆盖选中 base asset 的
  `portfolio_by_asset[asset]`（maxBorrowable）与其 rate。
- `_published_state: PublishedState | None`。

**关键不变式**：worker 是**唯一** domain-cache 写者与唯一 full-state 发布者。因此
组装时可无锁 copy/read 缓存（这正是 D5 的前提）。请求线程**只**提交命令并等待，
从不改缓存或发布。

### 4.3 命令队列与合并（bounded in-flight coalescing）

- `_command_queue: queue.Queue[RefreshSymbolCommand]`。
- `RefreshSymbolCommand`：`symbol: str`、`done: threading.Event`、`result: dict|None`、
  `error: str|None`、**`deadline_monotonic: float`**。
- **共享 deadline（截止时间）**：命令创建时记录一个共享的单调时钟截止时间
  `deadline_monotonic = time.monotonic() + symbol_refresh_timeout_seconds`（默认创建
  后 30s）。同 `symbol` 的并发 waiter **共享同一 command 与同一 deadline**（合并即
  共享），不引入 per-waiter 独立取消、通用取消框架或新线程。该 deadline 是**发布闸门**
  （publication gate），语义见 §10。
- `_inflight: dict[str, RefreshSymbolCommand]` + `_inflight_lock: threading.Lock`
  （**只**护 `_inflight` 字典，不护缓存/发布）。
- 提交 `submit_refresh(symbol)`：加锁查 `_inflight`；若同 `symbol` 已在飞行/排队，
  返回**同一** command（合并，防重复签名，共享 deadline）；否则新建、入队、放入
  `_inflight`。请求线程 `cmd.done.wait(max(0, cmd.deadline_monotonic - now))`。
- 合并键 = **`symbol`**（非 base asset）。理由：公开字段与历史是 symbol 维度；两个
  同 base 不同 symbol（如 `BTCUSDT` vs `BTCUSDC`）的点击必须各自刷新自己的公开/
  历史，故按 symbol 合并；它们对同一 base 的两次 maxBorrowable force 调用是有界且
  正确的，可接受。

### 4.4 worker 主循环（单串行 worker）

```
worker_loop():
    立即执行一次 base 刷新 + 发布（无 sleep）      # bootstrap
    while not stop_event.is_set():
        try:
            cmd = queue.get(timeout=background_tick_seconds)   # 30s
        except Empty:
            cmd = None
        if stop_event.is_set(): break
        if cmd is not None:
            _handle_refresh_command(cmd)     # 选中行路径 + 发布 + 完成 command
        else:
            _scheduled_tick()                # base(≥60s 才刷) + ≤10 历史扫描 + 发布
```

- `_scheduled_tick()`：若 `now - _base_raw_ts >= cache_ttl_seconds(60)` 则刷 base；
  然后从游标处理**至多 `history_sweep_batch_size`(10)** 个「缺失或过期」的默认集
  历史；然后组装 + 校验 + 发布。candidate 列表在每 tick 从最新 base rows **重算**
  为一个**稳定快照 list**，游标在该 list 上推进，故成员变化不会破坏正在进行的
  cursor 周期。
- `_handle_refresh_command(cmd)`：见 §6 / §7 / §10；完成后 `cmd.result = 单行投影`，
  `cmd.done.set()`。

### 4.5 原子发布与 last-good 保留

- 组装/校验全部在 worker 本地未发布变量中完成；**只有校验通过**才引用替换。
- 任一环节失败 → **不发布**：上一份 `_published_state` 继续对外服务。
- 字段级 last-good：一次 republish 产出的 `PublishedState` **永远是完整的**（所有
  行都在）；某来源失败时该字段回退到 `_last_private_inputs` 中的上次成功值。
  **区分**「schema-complete 发布 + per-source last-good 回退」（允许）与「发布半
  拼装对象」（禁止）。

### 4.6 offline / kill-switch 模式（严格区分两种「不起 worker」）

`start_worker()` 在 `config.offline=True` **或** `background_refresh_enabled=False`
时都是 **no-op**（不起线程），但 `get_snapshot()` 的行为**必须按 offline 与 live 分开**：

- **`config.offline=True`（测试/离线兼容例外）**：`get_snapshot()` 保留既有**同步
  build + 60s 缓存**路径。此路径读**冻结 fixtures，零网络、零上游**（`fetch_raw` 走
  `_fetch_offline`，私有通道离线恒 disabled）。这是唯一允许同步 build 的分支，仅为让
  `backend/tests` 离线单线程用例继续通过。单写者不变式是 **live 后台模式**属性；
  offline 无并发风险。
- **`config.offline=False`（live 在线服务）且 `background_refresh_enabled=False`
  （kill switch 关闭）**：**绝不**回退到请求路径同步上游抓取。`get_snapshot()`：
  - 若已有 `_published_state`（开关关闭前曾发布过）→ 返回该 **last-good** 已发布状态；
  - 若无 `_published_state`（从启动即关闭）→ 抛 `SnapshotNotReady` → server 映射
    **503**。
- **`config.offline=False` 且 `background_refresh_enabled=True`**：worker 正常运行，
  `get_snapshot()` 只读 `_published_state`。

此严格区分保证 `00-task.md` 的「在线 full snapshot 零上游请求」验收：**live 服务在任何
开关状态下都不做请求路径同步上游抓取**。

**禁止**：通用调度器、线程池、watched set、优先级队列/账本、业务级大锁、磁盘持久化、
delta 合并。

---

## 5. Bootstrap 与 timeout 契约（Bootstrap And Timeout Contract）

冻结默认：
- **构造无副作用**：`SnapshotService.__init__` 不起线程（今天已如此，保持）。
- **显式生命周期**：`server.run()` 在 `serve_forever()` 前调用
  `service.start_worker()`；`finally` 里 `service.stop_worker()`。
- `start_worker()` **幂等**；重复调用不起第二个线程。
- `offline` 与 kill-switch 关闭 → 不起 worker（两种「不起」的读行为按 §4.6 严格区分）。
- worker 起来后**立即无 sleep** 做一次 base 发布。
- 首次 base 发布前，`get_snapshot()` / `symbol-snapshot` 抛
  `SnapshotNotReady` → server 映射 **503**（brief 503）。
- **live 服务 kill switch 关闭**：有已发布状态 → 返回 last-good；无 → 503。**绝不**
  回退请求路径同步上游抓取（§4.6）。
- **任何请求都不等待 deep-history 扫描**。
- `stop_worker()`：置 `stop_event`，入队 sentinel 唤醒，`thread.join(timeout=...)`，
  及时终止。
- **symbol refresh 超时可配置，默认 30s**（`symbol_refresh_timeout_seconds`）。
  请求线程 `cmd.done.wait(timeout)`；超时**绝不**替换/清空已发布状态（见 §10）。

### 配置新增（`backend/config.py`，跟随既有 `_env_*` 模式）

| 字段 | 默认 | env（主，及 `FUNDING_HEDGING_` 别名） |
|---|---|---|
| `background_refresh_enabled: bool` | `True` | `APP_BACKGROUND_REFRESH_ENABLED` |
| `background_tick_seconds: int` | `30` | `APP_BACKGROUND_TICK_SECONDS` |
| `history_sweep_batch_size: int` | `10` | `APP_HISTORY_SWEEP_BATCH_SIZE` |
| `symbol_refresh_timeout_seconds: float` | `30` | `APP_SYMBOL_REFRESH_TIMEOUT_SECONDS` |

base 公开刷新节奏**复用**既有 `cache_ttl_seconds`(60)，不新增冗余旋钮。

---

## 6. 公开适配器契约（Public Adapter Contract）

点击刷新选中行**只做每-symbol 公开调用**，复用 worker 持有的
`_base_raw`（exchangeInfo / spot / funding_interval 元数据），**不得**为一行调用整
宇宙 `fetch_raw()`。

新增 `backend/adapters/binance_public.py`：

```python
def fetch_premium_index_for(self, symbol: str) -> dict:
    """GET /fapi/v1/premiumIndex?symbol=SYMBOL —— 单 symbol premium/mark。
    live-only；offline 返回 {}（点击流在 offline 不触发）。"""
```

- 请求参数：`{"symbol": symbol}`，经 `urllib.parse.urlencode` 编码（symbol 从不
  裸插值）；`_bump("GET /fapi/v1/premiumIndex?symbol")` 记账。
- 30 天历史：复用既有 `fetch_funding_rate(symbol, start_time_ms, end_time_ms,
  limit=1000)`，窗口 `[t_end - 30d, t_end]`，`t_end = _base_raw` 派生的
  `data_time_ms`（复用 base 边界，保证与全量行的 annualization 边界一致、结果确定）。
- 组装：worker 用 `_base_raw` 的 `premium_index` 副本，**仅**用
  `fetch_premium_index_for` 结果覆盖选中 symbol 的 premium 条目；`build_rows` 对全
  集重算（纯函数、无 HTTP），仅选中行的公开字段变化。
- 错误降级：per-symbol premium/history 失败 → 该来源不更新，保留 last-good；不抛
  snapshot-wide 503。history 失败沿用既有「不缓存失败」语义。
- 缓存更新：成功 30 天历史写入 `_funding_history_cache[symbol]`（worker 写）。
- 若某契约断言依赖当前 Binance 公开行为，需在
  `reports/api-samples/2026-07-history-background-refresh-v1/` 落**原始公开样本**
  （`/fapi/v1/premiumIndex?symbol=` 与 `/fapi/v1/fundingRate` 各一份）。
- 测试/mock：以 fake client 注入固定 premium/funding，断言点击只触发 per-symbol
  两个公开调用、**从不**触发 `fetch_raw()`（用 `request_log` 计数断言）。

---

## 7. 私有 force-TTL 契约（Private Force-TTL Contract）

在 `backend/services/private_client.py`（单 HMAC 出口）实现**最小**的 exact-key
一次性绕过：

```python
def _evict(self, method, path, params=None) -> None:
    key = (method, path, tuple(sorted((params or {}).items())))
    self._cache.pop(key, None)         # 只删这一个精确键；绝不 _cache.clear()

def fetch_max_borrowable(self, asset, *, force=False):   # 加 force 关键字
    ...
    if force:
        self._evict("GET", "/papi/v1/margin/maxBorrowable", {"asset": asset})
    data = self._cached_get("GET", "/papi/v1/margin/maxBorrowable", {"asset": asset})
    ...

def fetch_cost_leg_chain(self, assets, *, force=False):  # 加 force 关键字
    # 点击路径调用 fetch_cost_leg_chain([asset], force=True)（单资产列表）。
    # force=True 时，仅 evict 本次单资产的两个 rate 精确键：
    #   E2  ("GET","/sapi/v1/margin/next-hourly-interest-rate",
    #        {"assets": asset, "isIsolated": "false"})   # 单资产 → assets=asset
    #   E2b ("GET","/sapi/v1/margin/interestRateHistory", {"asset": asset})
    # 然后照常走 _cached_get（各触发一次新签名调用）。
    # 内部的 account/info(E5)、crossMarginData(W3) 仍走普通 _cached_get 复用 1h
    # 缓存（不 evict、不强刷）。
```

**force 精确键清单（点击路径只 evict 这 3 个单资产键）：**
- `("GET","/papi/v1/margin/maxBorrowable", (("asset", asset),))`
- `("GET","/sapi/v1/margin/next-hourly-interest-rate", (("assets", asset),("isIsolated","false")))`
- `("GET","/sapi/v1/margin/interestRateHistory", (("asset", asset),))`

**不得触碰：**
- scheduled refresh（定时刷新）形成的**多资产 batch 键**——如
  `{"assets": "BTC,ETH,SOL,...", "isIsolated": "false"}` 是**不同**的缓存键，evict
  单资产键天然不影响它；实现/测试必须固化「单资产键刷新、多资产批次键仍保留」。
- 共享 1h 引用：`crossMarginData`(W3)、`account/info`(E5/VIP)、classic
  (`allPairs`/`allAssets`)——**绝不**强刷、**绝不** `_cache.clear()`。

冻结规则：
- 点击强制**只**刷选中 asset 的 maxBorrowable 与 actual-rate，各**一次**新签名调用。
- 复用有效的 classic / VIP / account-tier / 共享引用（1h TTL 未过期即复用）。
- **绝不** `_cache.clear()`；**绝不**从点击路径调用 `fetch_unified_balances` /
  `fetch_um_positions` / `fetch_spot_balances`（余额/持仓/估值）。
- 点击 republish **复用**上次发布的 `private_account` 面板与**非选中行**的
  borrow 字段（来自 `_last_private_inputs`）。
- 保留：单 HMAC 出口、精确 GET 白名单（`_require_whitelisted` 先于签名）、脱敏
  audit（`audit_log` 只含 `logical_endpoint/method/http_status/error/latency_ms`）、
  rate-limit 回退（`_is_rate_limited` 一次重试）、timeout、last-good 降级。
- **缓存/合并键**：force 走 `_cached_get` 的 `(method, path, sorted(params))` 精确
  键，其中 maxBorrowable 的 params 是 `{"asset": <base asset>}`（**base asset 维度**，
  因为借币是资产维度）；而**命令合并键是 `symbol`**（§4.3，公开/历史是 symbol
  维度）。二者维度不同是有意的，需在测试中固化。
- **signed 证据**：`reports/api-samples/.../` 落**脱敏** audit 片段，**不得**含
  key/secret/signature/full query/headers/balances/positions。

---

## 8. 兼容端点（Compatibility Endpoint）

`GET /api/public-market/funding-history?symbol=X` 降级为**纯 `PublishedState`
投影**：

- **零上游抓取、零缓存写**（`get_funding_history` 不再调 `_fetch_history_for`）。
  这消除了「第二个 cache 写者」并发风险（架构评审 F2）。
- 语义：
  - 400 `invalid_symbol`：`symbol` 缺失/畸形（沿用 `_SYMBOL_RE`）。
  - 404 `symbol_not_found`：合法但不在当前已发布 snapshot 的 eligible rows。
  - 503：worker 未就绪（首次发布前）。
  - 200：从已发布行投影 `funding_history` + `annualized_funding_7d/30d`，
    `history_status = "available"`（列表非空）或 `"empty"`（present 但空）。
- 前端点击流**不再**用此端点（改用 §9 symbol-snapshot）；保留仅为契约兼容。
- 测试（扩展 `test_funding_history_endpoint.py`）：断言调用后 `request_log` 无新增
  公开调用、`_funding_history_cache` 无新增/变更键、available/empty/404/503 语义。

---

## 9. 新行-快照契约（New Row-Snapshot Contract）

**路由**：`GET /api/public-market/symbol-snapshot?symbol=SYMBOL`
**schema**：`schemas/api/public-market/symbol-snapshot.schema.json`，
`schema_version = "public-market-symbol-snapshot/v1"`。

**成功响应形状（恰好一行，无 full `rows` 数组）：**

```json
{
  "schema_version": "public-market-symbol-snapshot/v1",
  "symbol": "BTCUSDT",
  "published_version": 42,
  "data_time": "2026-07-12T....Z",
  "generated_at": "2026-07-12T....Z",
  "refresh_status": "ok",
  "warnings": [],
  "row": { "...": "单行投影，与 snapshot.rows[] 元素同形" }
}
```

- `refresh_status ∈ {"ok","partial","timeout"}`：`ok` 全部成功；`partial` 公开/历史
  成功但 borrow 失败（字段 last-good）；`timeout` 命令超时（返回上次已发布该行投影）。
- **无 `rows` 数组**（schema `additionalProperties:false` 且不定义 `rows`）。

**HTTP 语义：**
- 400 `invalid_symbol`（畸形，先于命令提交，复用 `_SYMBOL_RE`）。
- 404 `symbol_not_found`（合法但当前已发布 snapshot 无此 eligible 行）。
- 503 `snapshot_not_ready`（首次 base 发布前）。
- 200 + `refresh_status:"timeout"`（命令 30s 超时）：返回**上次已发布**该行投影 +
  warning；**不**替换/清空已发布状态。前端呈现「刷新超时，显示上次数据」。
- 200 + `refresh_status:"partial"`（borrow 失败）：见 §10。

**same-version 证明方式**（主 snapshot schema 不改）：`row` 与 `published_version`
均取自 worker `_handle_refresh_command` 里**刚发布的同一个 `PublishedState` 对象**
（`state.rows_by_symbol[symbol]` + `state.published_version`）。证明靠**构造 + 测试**：
测试断言「点击返回的 row 恒等于同一 `published_version` 的全量 snapshot 中该 symbol
行」。因主 snapshot schema 无 `published_version` 字段（不改 schema），全量端点不带
版本号；同版本一致性由单发布者 + 单调版本 + 测试保证。

**契约修订证据**（`AGENTS.md` 硬门）：该 schema 是 contract amendment，正式 review
前必须在 `reports/api-samples/2026-07-history-background-refresh-v1/` 落**原始公开
样本** + **脱敏 signed 证据**。

---

## 10. 失败矩阵（Failure Matrix → 实现与测试规则）

把 `10-design.md` 真值表落成精确规则。每行都产出**schema-complete** 发布，禁止半
拼装对象。

| # | 场景 | 行为 | HTTP / refresh_status |
|---|---|---|---|
| 1 | public+history+borrow 全成 | 全部更新选中行；发布新版 | 200 `ok` |
| 2 | history 成、borrow 败 | history/public 更新；borrow 字段回退 `_last_private_inputs` last-good | 200 `partial` + warning |
| 3 | borrow 成、history 败 | borrow 更新；history 保留 last-good（失败不缓存）；public 若成则更新 | 200 `partial` + warning |
| 4 | public 刷新失败但有 eligible last-good base | 复用 `_base_raw` 该行旧公开字段；其它来源按上表 | 200 `partial` + warning |
| 5 | 无 eligible last-good 行（该 symbol 从未在任何已发布版本） | 不发布伪行 | 404 `symbol_not_found` |
| 6 | 所有选中来源全败 | 不发布新版；返回上次该行投影 | 200 `timeout`/`partial`（视是否超时），或 404 若从无该行 |
| 7 | 命令 deadline 已过（共享 30s 截止） | worker 可完成已开始的上游 I/O，但**不提交** history/domain-cache 变更、**不发布**新版本；见下方 deadline 闸门 | 200 `timeout` + 上次已发布行投影 |
| 8 | rate-limit / auth / service 失败 | `PrivateClient` 一次回退重试后降级；last-good；single-exit 语义不变 | 200 `partial` + warning |

**Deadline 发布闸门（消除超时后的发布竞态）：**

- worker 处理命令时**允许完成**已经开始的上游 I/O（不做 per-waiter 取消），但必须把
  选中行结果**先暂存在本地变量**中。
- 在**写 domain cache（`_funding_history_cache` / `_last_private_inputs`）之前、以及
  替换 `PublishedState` 之前**，worker 必须**再次检查** `cmd.deadline_monotonic`
  （单调时钟）。
- 若 `time.monotonic() > cmd.deadline_monotonic`（第 31 秒才完成的场景）：**不得**提交
  本次 history/domain-cache 变更、**不得**发布新版本；只 `cmd.done.set()` 完成命令，
  端点返回**上次已发布**该行投影 + `refresh_status:"timeout"`。
- 若在 deadline 前完成：正常提交并**只发布一次**新版本，端点返回新行 `refresh_status`
  按来源结果（`ok`/`partial`）。
- **区分**：`PrivateClient` transport cache（`_cache`）可能已被本次签名请求**自身**更新
  ——这属**传输层缓存**，不构成 domain publication（不改 `_funding_history_cache`、
  不换 `PublishedState`），因此不违反「超时不替换已发布状态」；实现与注释须写清该区别。
- **区分**：schema-complete + per-source last-good（允许）vs 发布 half-assembled
  对象（禁止）——测试用「校验失败则 `_published_state` 不变」断言。
- worker 内部对单个来源异常必须 catch 并转 warning，不得让一次点击把整份发布置空。

---

## 11. 前端集成（Frontend Integration，`frontend/index.html` + `self-check.js`）

精确状态/DOM 变更：

1. **每次行点击（含 preloaded 行）调用 symbol-snapshot**：`openDrawer(symbol)` 的
   历史加载分支，把 `fetch('/api/public-market/funding-history?symbol=...')`
   （`index.html:1399`）改为 `fetch('/api/public-market/symbol-snapshot?symbol=...')`；
   即便 `hasPreloaded` 也发一次刷新（覆盖公开/历史/borrow）。
2. **1 秒防连点**：点击后把该行 + 抽屉刷新入口置为 non-clickable 1 秒
   （`setTimeout` 解禁）；防误双击。
3. **in-flight 忽略再次激活**：同 symbol 命令在飞行时，忽略新的点击激活；沿用既有
   `drawerRequestId` / `isActive()` stale-guard 处理迟到响应。
4. **stale 响应身份校验**：校验 `data.schema_version === 'public-market-symbol-
   snapshot/v1'` 且 `data.symbol === symbol` 且 `isActive()`，否则丢弃。
5. **只替换选中行的前端状态**：用 `data.row` 替换 `state.snapshot.rows` 中该 symbol
   条目（按 symbol 定位）；不动其它行。
6. **只补丁该 DOM 行 + 抽屉**：实现 `patchRow(symbol, row)` 只更新对应 `<tr>` 与
   抽屉内容；**移除**点击路径里的 `renderTable()` 全表重渲染（`index.html:1438`）。
7. **本地应用选中行可见性变化**：若刷新后该行跨越 `hideLowDailyRate` 阈值/路由过滤，
   仅对该行做本地显示/隐藏；**不**在点击时重算 summary。
8. **点击不做整 snapshot 抓取/整表渲染**。
9. **接受 ≤60s 全局排序/汇总临时陈旧**：全局排序位次与 summary 计数由既有 60s
   全量轮询（`AUTO_REFRESH_MS = 60000`）对账。
10. **完成后再次刻意点击 = 新命令**（无保留状态）。

`self-check.js`：新增校验——symbol-snapshot 响应含 `schema_version` /
`published_version` / 恰好一个 `row` / **无** `rows` 数组，且 `row` 满足
`REQUIRED_ROW_FIELDS`。

---

## 12. 精确测试与证据（Exact Tests And Evidence）

**命令（照 `docs/development/DEVELOPMENT_GUIDE.md`）：**
- 后端：`PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests -q -p no:cacheprovider`
- 前端：`node frontend/self-check.js`
- 新 schema 校验：symbol-snapshot 样本 `jsonschema.validate` 用例（含在 pytest）。
- HMAC/安全 grep：既有 `backend/tests/test_private_client.py`
  `test_single_hmac_exit_in_product_code`（force-TTL 加在 private_client 内，须仍通过）。
- 阶段校验：`python3 scripts/validate-stage.py 2026-07-history-background-refresh-v1 --phase pre-review`

**新增/扩展测试文件：**
- `backend/tests/test_background_worker.py`：生命周期（构造无线程；start 幂等；stop
  及时；offline/disabled 不启动）；节奏（base ≥60s 才刷、tick ≤10、cursor 在成员
  变化下稳定不跳漏）；**选择器 parity 向量**：`0.00029999`/`0.00030000`/
  `-0.00030000` 不预热，`0.00030001`/`-0.00030001` 预热（route 未排除时），
  `PERP_ONLY_EXCLUDED` 任意费率不预热，**null/非法费率不预热**；all-valid-cache
  合并；per-symbol 失败不毒化缓存/不删已发布值。
- `backend/tests/test_symbol_snapshot_endpoint.py`：恰好一行、无 `rows` 数组；行与
  同 `published_version` 全量行恒等；400/404/503/timeout/partial；点击触发**恰好一条**
  命令；点击 audit **绝无** balance/position/valuation 端点；force-TTL 精确键绕过；
  同 symbol 并发点击合并为一条命令。
  - **deadline 发布闸门测试**（修订 1）：注入可控 monotonic clock（如 fake
    `time.monotonic`）。用例 A——上游在 deadline 后（模拟第 31 秒）完成：断言
    `_published_state` **不变**、`_funding_history_cache` 无该 symbol 提交、端点返回
    上次行投影 + `refresh_status:"timeout"`。用例 B——deadline 前完成：断言**只发布
    一次**（`published_version` +1）、行更新。
- `backend/tests/test_private_client.py`（扩展）：`force=True` 只 evict §7 的 3 个
  单资产精确键、不 `clear()`、force 路径不触发账户面板调用（无
  balance/position/valuation）；**多资产 batch 键仍保留**——预置一个多资产
  `{"assets":"BTC,ETH,...","isIsolated":"false"}` 批次缓存键，对单资产
  `fetch_cost_leg_chain([asset], force=True)` 后断言该批次键仍在
  `_cache`、`crossMarginData`/`account/info` 键未被 evict。
- `backend/tests/test_funding_history_endpoint.py`（扩展）：纯投影、零上游抓取、
  零缓存写、available/empty/404/503。
- 请求路径测试：live 模式 `get_snapshot()` 不触发网络（worker 注入 fake）；
  **live + kill switch 关闭**：有已发布状态 → 返回 last-good 且**零上游**；无状态 →
  503 且**零上游**（断言 `request_log`/audit 无新增）。**offline 是唯一同步 build 分支**，
  读 fixtures 零网络。

**验收 → 证据映射（每条 `00-task.md` 验收对一件证据）：**
- 零上游全量读 / 完整旧或新状态 → `test_background_worker` + `test_symbol_snapshot`。
- 显式生命周期 / offline·disabled 不启动 → `test_background_worker` 生命周期用例。
- brief 503 → server 层用例（未就绪 → 503）。
- base 60s / tick ≤10 → `test_background_worker` 节奏用例。
- null 行不预热 → 选择器 null 向量。
- 点击一条命令、无 watched set → `test_symbol_snapshot` 命令用例。
- 点击不调 `fetch_raw()` → `request_log` 计数断言。
- force exact-key、复用面板 → `test_private_client` + `test_symbol_snapshot` audit。
- worker 唯一写者 → 请求路径无写断言 + `test_funding_history_endpoint` 零写。
- symbol-snapshot 一行/版本 → schema 校验 + same-version 恒等断言。
- 前端只补丁 → `self-check.js` 契约 + 无整表渲染（代码审查点）。
- 失败矩阵 → `test_symbol_snapshot` 8 场景。
- 30s 超时保留 → timeout 用例。
- raw/signed 证据 → `reports/api-samples/2026-07-history-background-refresh-v1/`。

**扫描时限观测**：记录默认集大小 `N`（intake 实测约 50–56）。约束
`ceil(N/10) * background_tick_seconds < funding_history_cache_ttl_seconds`，即
`ceil(N/10)*30s < 1800s` → `N < 600`。实现报告须记录实测 `N` 与单次全扫时间，并注明
若 `N` 逼近 600 的限制（当前有充裕余量）。

---

## 13. 风险与评审焦点（Risk And Review Focus）

最高风险实现缝隙（review-1 重点核对）：
1. **意外的第二个 cache 写者**：`get_funding_history` 必须彻底停止写
   `_funding_history_cache`（§8）——架构评审 F2 的落地点。
2. **点击路径重入整账户面板**：账户面板 60s TTL 过期后，若点击 republish 误调
   `fetch_unified_balances/um_positions/spot_balances` 即违规；必须复用
   `_last_private_inputs`（§7）——架构评审 F3。
3. **过宽私有缓存失效**：force 必须精确键 evict，禁止 `_cache.clear()`（§7）。
4. **点击触发整宇宙 `fetch_raw()`**：必须走 `fetch_premium_index_for` 单 symbol（§6）。
5. **行/全量版本错配**：投影必须来自刚发布的同一 `PublishedState`（§9）。
6. **部分失败擦除 last-good**：校验失败不发布、字段回退（§4.5/§10）。
7. **线程生命周期/测试非确定性**：offline·disabled no-op、start 幂等、stop 及时
   join；测试单线程（§4.6/§5）。
8. **前端整表重渲染回归**：点击路径移除 `renderTable()` 全表调用（§11.6）。
9. **raw/signed 证据泄漏**：audit 仅脱敏字段，样本不得含凭证/签名/余额/持仓（§7/§9）。
10. **顺序重复点击的签名压力**（架构评审 F4）：**v1 必须实现**前端「点击后该行 1 秒
    不可点击」+「同 symbol 命令 in-flight 时忽略再次激活」（§11.2/§11.3，操作者已裁定，
    非待决）。in-flight 合并覆盖并发；1 秒防连点覆盖误连点。完成后再次刻意点击**仍**
    触发一条新命令。**仅** worker 侧「完成后的额外 cooldown/结果复用」（对该 symbol
    上次强刷 < 短窗口的重复命令复用结果而非再 force）留 v1.1，须在实现报告记录为优化位。
    **不得**新增 watched set、interest TTL 或优先级状态。

---

## 14. 实现分发就绪（Implementation Dispatch Readiness）

**Ready 判定：`READY`（可分发实现，无 BLOCKED）。**

- 全部人机门已由操作者裁定并记录（`status.json.human_gates`）：冷启动 brief-503、
  kill switch default-on。
- 架构评审 F2/F3/F4 已在本 breakdown 落成具体规则（§8/§7/§13.10），非 blocker。
- 无 `10-design.md`/`11-adr.md` 内部真实冲突阻碍安全拆分。

就绪清单：
- [x] owner 路由确定（`claude_glm` 单 owner，`kimi` review-1）。
- [x] allowed/forbidden 文件收窄（§3），主 snapshot schema 明确不改。
- [x] 数据/并发模型（`PublishedState` + 单 worker + 命令队列 + 合并键 §4）。
- [x] bootstrap/timeout + 配置旋钮（§5）。
- [x] 公开 per-symbol 适配器契约（§6）。
- [x] 私有 force-TTL exact-key + 复用面板（§7）。
- [x] 兼容端点降级为纯投影（§8）。
- [x] symbol-snapshot 路由/schema/HTTP/same-version（§9）。
- [x] 失败矩阵 8 场景（§10）。
- [x] 前端目标补丁 + 1s 防连点 + self-check（§11）。
- [x] 精确测试命令与验收→证据映射（§12）。
- [x] 契约样本证据路径（`reports/api-samples/2026-07-history-background-refresh-v1/`）。

**剩余人类决策（不阻塞实现，交 bookkeeper/操作者）：**
1. review-2 最终评审 provider 隔离：Codex 设计、Opus 评审+breakdown → 需 bookkeeper
   在 dispatch 前按 `AGENTS.md` strong-reviewer 规则重估（`status.json.review_2`）。

> 注：前端 1 秒防连点 + in-flight 忽略已由操作者裁定为 **v1 必做**（§11/§13.10），
> **不再是待决项**；仅 worker 侧额外 cooldown/结果复用为已决的 v1.1 优化位。

---

本地北京时间: 2026-07-12 23:49:49 CST
下一步模型: Codex bookkeeper
下一步任务: 验收 12-development-breakdown.md（含 amendment 四项修订），更新 status/handoff，并准备 claude_glm 实现分发包

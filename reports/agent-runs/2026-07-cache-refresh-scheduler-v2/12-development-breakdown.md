# 开发分解（Development Breakdown）：三节奏缓存刷新调度器

> v2 manual-delivery note: the product boundaries, contracts, tests, and risk
> analysis in this document are preserved from the user-approved v1 breakdown.
> The retired auto-review instructions in §8 and scattered references to a
> runner, seal, authorization artifact, or Grok-primary review are historical
> only. `13-manual-delivery-amendment.md` is authoritative for v2 dispatch and
> review routing when those passages conflict.

- Stage: `2026-07-cache-refresh-scheduler-v2`
- Branch: `stage/2026-07-cache-refresh-scheduler-v2`
- Approved design baseline commit（批准设计基线提交）:
  `b5ead37ba868bb7c461ae4d85a97bfa55e4530bf`
- Execution baseline（执行基线）: `main@8aac137` 创建的
  `stage/2026-07-cache-refresh-scheduler-v2`；实现 task base 由派发准备
  提交后的 `status.json.tasks[0].base_sha` 绑定。
- Breakdown author（分解作者）: Anthropic `claude-opus-4-8`，skill `task_planner`。
  这是 review-2 披露意义上的 design involvement（设计参与）。
- Complexity: `MEDIUM`；单串行实现任务，backend-dominant（后端主导）。
- 本文件为设计文档，不含产品补丁、不写产品代码。

> 阅读者约定：本文中的确切标识符、文件路径、命令、API 路由、schema 键、状态
> 字面量（如 `claude_glm`、`zhipu_glm`、`grok-4.5`、`private_channel_ttl_seconds`、
> `daily_funding_rate < -0.00030000`、`chain_hit_tier`）均
> 不翻译、不改写。

---

## 1. 基线与需求可追溯性（Baseline and requirement traceability）

### 1.1 固定基线

- 批准设计基线提交：`b5ead37ba868bb7c461ae4d85a97bfa55e4530bf`。
- 权威设计证据：本 stage 的 `10-design.md`、`11-adr.md`（在上述基线处批准），
  以及 `status.json.approved_design_amendments`（human 于
  `2026-07-14T09:31:19Z` 批准的三条 P1 决议）。
- 产品文档：`docs/product/PRD.md`（read-only funding 工作站，无节奏/刷新约束）、
  `docs/architecture/ARCHITECTURE.md`（确认 `GET /api/public-market/snapshot`
  历史路由、additive 私有字段、serial single-writer、无交易副作用）。本 stage
  不改这两份 canonical 文档。

### 1.2 冻结需求（Frozen requirements，必须保留）

来源：`00-task.md` Acceptance Criteria + `10-design.md` + prompt 的 "Frozen
product decisions" 与 "Mandatory contract clarifications"。

- FR-1 三个独立节奏组：Group A ≈60s、Group B 固定 1800s、Group C 每 30s 检查
  至多 10 个主页 symbol。三组共享发布但**不**共享 freshness gate。
- FR-2 slow scheduled private transport TTL 从 3600 改为 1800；这些 scheduled
  key 的 effective 值必须 `<=1800`。business timestamp 只在**成功 source 结果**后
  推进；age-due 的 scheduled 调用必须做真实 upstream I/O，不得复用旧 transport
  条目冒充成功刷新。
- FR-3 scheduled source fetching/updating 与 cache-only snapshot assembly 分离。
  scheduled assembly **不得**调用当前的 all-row
  `fetch_cost_leg_chain(rate_probe_assets)`，也不得重建 global top-50
  max-borrowable 探针。
- FR-4 scheduled borrow 工作是 homepage-only，冻结谓词：
  `daily_funding_rate < -0.00030000 AND route_class == MARGIN_SPOT_CANDIDATE
  AND asset_tag in {CRYPTO, METAL} AND 只读私有通道可用`。低于主页阈值的行
  （`abs(daily_funding_rate) <= 0.00030000`）不接受任何 scheduled history /
  borrow-rate / max-borrowable / coverage 工作；现有手动选中行刷新不变。
- FR-5 历史 global `borrow_check_max_calls` top-50 上限**不**适用于 scheduled
  Group C；at-most-10-symbol cursor 是唯一压力边界。
- FR-6 `interestRateHistory` 仅为 selected-due-asset fallback（在 next-hourly
  失败或不可用后），不是 homepage-wide 常规轮询。
- FR-7 history / borrow-rate / max-borrowable freshness 相互独立；批量 next-hourly
  结果按 `base_asset` 拆包并各自打时间戳。
- FR-8 保留当前 wire schema、前端行为、serial single-writer 发布、手动点击语义，
  以及被显式 deferred 的 failure/empty/partial-response 策略。

### 1.3 强制契约澄清（Mandatory contract clarifications，直接采用，不选相反解释）

- CC-1 Group B **不**用一个共享成功时间戳覆盖不相关 source。Public Group B、
  classic-reference、account/VIP-reference 三类 source state 各自保留独立
  due/success 状态：一个 source 成功不得压制另一个失败 source 的 retry；一个
  source 失败不得逼迫已成功 source 每 30s 重取。
- CC-2 Group B business cadence 固定 1800s。**不**提供 `reference_refresh_seconds`
  这类环境覆盖。slow scheduled private transport 可配更低，但 effective 值必须
  `<=1800`，且不得把固定的 Group B business cadence 放大。
- CC-3 homepage coverage `attempted` = 资产进入当前 universe 后**实际发起过**一次
  scheduled max-borrowable endpoint 尝试。cursor 仅路过而 max-borrowable 组件仍
  fresh，**不**算 attempt。失败的实际调用**算** attempt；离开 universe 从账本移除；
  重新进入以 unattempted 起算。
- CC-4 冻结 borrow-rate 缓存单位。若 next-hourly 数据在存储前被 normalize，则把缓存
  值标记为 daily 并禁止 assembly 再乘一次 `*24`；否则存 raw hourly 并在 resolution
  处**恰好一次** normalize。选一种表示并显式测试。**本分解选择：存 raw + source，
  在 resolution 处恰好一次 normalize**（详见 §5.3）。
- CC-5 区分 adapter/owner identity 与 provider identity：
  `implementation_adapter = claude_glm`，provider identity 为 `zhipu_glm`；
  人工 review 仍按 provider identity 做实现者/评审者隔离。
- CC-6 **不**把 `backend/domain/snapshot.py` 这类仅条件性产品文件放入初始
  `allowed_pathspecs`。若当前代码证明必须改它，实现者需描述证据并停下，
  等待 human 批准最小 scope expansion 后才可加入。本分解已论证**无需**改
  `backend/domain/snapshot.py`（见 §4.3）。
- CC-7 v2 的 review-2 路由在 review-1 后按 provider isolation 决定：
  OpenAI/Codex 有继承设计参与，Anthropic/Claude 有继承 breakdown 参与。
  这些是 design-involvement disclosure，不是 v2 交付代码作者身份。

### 1.4 Non-goals（非目标，不实现）

来自 `00-task.md`：无 25 分钟 refresh-ahead 窗口；不保证恰好 1800s 刷新（队列位置
可使正常成功路径 age 达到约 30–35 分钟）；无新的 last-good 失败保留策略；不防护
成功的 empty/partial 响应覆盖旧缓存；无 endpoint 响应完整性审计；无前端/API/schema
变更；不改 one-shot 行点击刷新语义；不跨进程持久化；无任何交易/借贷/划转动作。

### 1.5 Deferred behavior（延后，不在本 stage 引入）

failure-path、empty/partial-success overwrite 保护、response completeness 匹配、
last-good 保留——均由 operator 显式 defer（`11-adr.md` Alternatives），本 stage 只
保证 operator 要求的**正常成功刷新路径**。

---

## 2. 当前 call-graph 诊断（Current call-graph diagnosis）

以下均来自当前工作树源码，引用真实函数/类名与文件，不虚构 API。

### 2.1 live worker：调度 → 抓取 → 缓存写 → 装配 → 校验 → 原子发布

- `backend/services/snapshot_service.py:SnapshotService.start_worker` 启动单线程
  `_worker_loop`（`background_refresh_enabled=True` 且非 offline 时）。
- `_worker_loop`（`snapshot_service.py:733`）：先 bootstrap 调一次 `_scheduled_tick`；
  之后 `self._command_queue.get(timeout=self.config.background_tick_seconds)`
  （默认 `background_tick_seconds=30`）。取到 `RefreshSymbolCommand` 走
  `_handle_refresh_command`（手动点击路径），超时/无命令走 `_scheduled_tick`。
- `_scheduled_tick`（`snapshot_service.py:761`）：
  1. base 刷新条件 `self._base_raw is None or (now - self._base_raw_ts) >=
     self.config.cache_ttl_seconds`（60s），满足则 `self.client.fetch_raw()`；
  2. `_eligible_rows(base_raw)` → rows_preview + data_time_ms；
  3. `default_view_history_symbols(rows_preview)` 选主页候选；
  4. `_sweep_history(candidates, data_time_ms)`（≤ `history_sweep_batch_size=10`）；
  5. `_all_valid_history()` 组 overlay；
  6. `_assemble(base_raw, funding_history_overlay=..., history_warnings=...)`；
  7. `_validate(snapshot)` → `_publish_validated(...)`（单引用交换发布）。
- `backend/adapters/binance_public.py:BinancePublicClient.fetch_raw` →
  `_fetch_live`（`binance_public.py:93`）在**同一次调用**里 bump 并抓取：
  `GET /fapi/v1/exchangeInfo`、`GET /fapi/v1/premiumIndex`、
  `GET /api/v3/exchangeInfo`、`GET /fapi/v1/fundingInfo`（后者 best-effort 降级）。
- 私有输入在 `_assemble` → `_gather_private_inputs(rows, forced_overrides=None)`
  （scheduled 分支，`snapshot_service.py:543`）里每 tick 组装：
  - `self._private.fetch_classic_reference()`（W1 allPairs / W2 allAssets /
    W3 crossMarginData）；
  - `select_borrow_candidates(rows, self.config.borrow_check_max_calls)`（=50）→
    `rate_probe_assets`（全量去重负资金池）、`borrowability_probe_assets`（前 50）、
    `borrowability_unprobed_assets`（其余）、`coverage`；
  - `self._private.fetch_cost_leg_chain(rate_probe_assets)`（**all-row**：E5
    `/sapi/v1/account/info`、E2 `next-hourly-interest-rate` 分批、E2b
    `interestRateHistory` 单资产、crossMarginData）；
  - `self.client.fetch_ticker_price_map()`（`/api/v3/ticker/price`）；
  - `fetch_unified_balances`/`fetch_um_positions`/`fetch_spot_balances`
    （`/papi/v1/balance`、`/papi/v1/um/positionRisk`、`/api/v3/account`，60s
    fast TTL）；
  - `for asset in borrowability_probe_assets: self._private.fetch_max_borrowable(asset)`
    （top-50 全局探针循环）。
- 行装配（`_assemble`，`snapshot_service.py:473`）：每行按 `resolve_cost_leg_rate(base,
  cost_leg)` 取日借币率、`compute_net_daily_yield`、`assemble_borrow_validation(...)`；
  `sort_rows`；`assemble_snapshot(...)` 产出 wire payload。
- 校验/发布：`_validate` 用 `snapshot.schema.json`，`_publish_validated` 递增
  `_published_version` 并原子替换 `_published_state`，同时把 `pi` 存入
  `_last_private_inputs`（供点击 republish 复用）。

### 2.2 Group A/B 节奏当前在哪里耦合

- **公有耦合**：`_base_raw_ts` 是**单一** 60s 时间戳，门控 `fetch_raw()` 整包。
  于是 Group B 的 `/fapi/v1/exchangeInfo`、`/api/v3/exchangeInfo`、
  `/fapi/v1/fundingInfo` 与 Group A 的 `/fapi/v1/premiumIndex` 被绑在同一个 60s
  刷新里——exchangeInfo/fundingInfo 本应 1800s。
- **私有耦合**：`_gather_private_inputs` scheduled 分支**每 tick**都调
  `fetch_classic_reference`（Group B）与账户面板（Group A），二者当前只靠
  `PrivateClient._cache` 的 transport TTL（1h vs 60s）区分，而**没有** business-level
  due 状态；`updated_monotonic` 语义完全不存在于私有侧。

### 2.3 all-row cost-leg / top-50 行为在哪里进入 assembly

- `_gather_private_inputs` scheduled 分支每 tick 调
  `fetch_cost_leg_chain(rate_probe_assets)`，其中 `rate_probe_assets` 是
  `select_borrow_candidates` 产出的**全量未截断**负资金去重池（见
  `backend/domain/snapshot.py:select_borrow_candidates` 注释：rate_probe 不 cap）。
- max-borrowable 通过 `borrowability_probe_assets = rate_probe[:cap]`（cap=50）循环
  `fetch_max_borrowable`——即历史 global top-50 探针。
- 二者当前只被 `PrivateClient._cache` 1h transport TTL 抑制实际网络量，但**调用图**
  每 tick 都会重新进入（命中缓存），正是 FR-3 要求 scheduled assembly 不得再有的
  隐藏路径。

### 2.4 手动点击刷新如何绕过 transport key

- `submit_refresh(symbol)` → 入队 `RefreshSymbolCommand` →
  `_handle_refresh_command`（`snapshot_service.py:812`）：分阶段做 `fetch_premium_index_for`
  、`fetch_funding_rate`、`fetch_cost_leg_chain([base_asset], force=True)`、
  `fetch_max_borrowable(base_asset, force=True)`，最后 `_assemble(...,
  forced_overrides=..., private_reuse=self._last_private_inputs or None)`。
- `force=True` 经 `PrivateClient._evict(method, path, params)` 单键淘汰
  （`private_client.py:221`）：只删该资产的单资产 E2/E2b/maxBorrowable transport
  key，**不**动多资产 scheduled-batch key 与共享 1h 引用；从不 `_cache.clear()`。
- 共享的 deadline gate（`deadline_monotonic`）在 I/O 后、domain-commit/publish 前
  多次复核，超时则不 commit 任何 domain 缓存、不 publish。**此路径整体保持不变。**

---

## 3. 一个串行实现任务（One serial implementation task）

- Task id：`task`（与 `status.json.tasks[0].id` 一致）。
- Owner：`claude_glm`（implementation_adapter；backend-dominant，无并行子任务）。
- Review-1：人工派发的全新只读 Kimi Session（与 `zhipu_glm` 实现者 provider 隔离）。
- **不**创建并行实现任务；`parallel_mode.enabled=false` 保持不变。

有序变更序列（每步 bounded 且可测；依赖自上而下）：

- **S1 config 与 slow-TTL 契约**（依赖：无）
  - `backend/config.py`：`private_channel_ttl_seconds` 默认 `3600 → 1800`。
  - 增加 effective slow scheduled TTL 校验：`private_channel_ttl_seconds > 1800`
    时拒绝（`ValueError`，与 `_env_int` 现有拒绝风格一致）。`fast` 60s TTL 不变。
  - verify：`python3 -m pytest backend/tests/test_config.py`。
- **S2 公有抓取拆分（Group A / Group B 独立时间戳）**（依赖：S1）
  - `backend/adapters/binance_public.py`：把 `_fetch_live` 拆成两个可独立调用的
    seam——Group A 公有（`/fapi/v1/premiumIndex`）与 Group B 公有
    （`/fapi/v1/exchangeInfo`、`/api/v3/exchangeInfo`、`/fapi/v1/fundingInfo`，
    保留 fundingInfo best-effort 降级 + warning）。`fetch_raw()` 作为 offline 唯一
    同步路径与向后兼容入口须保留（offline 与既有 offline 测试仍走 `fetch_raw`）。
  - `snapshot_service.py`：worker 维护 `_global_source_cache[source_id] =
    (updated_monotonic, value)`（见 §5.1）。Group A 公有 due=60s，Group B 公有
    due=1800s，各 source_id 独立时间戳（CC-1）。装配时从缓存组合出与
    `_eligible_rows` 期望完全一致的 base_raw dict（键：`futures_exchange_info`、
    `premium_index`、`spot_exchange_info`、`funding_history_by_sym`、
    `funding_interval_by_sym`、`warnings`）。
  - verify：`test_background_worker.py` 中 base 刷新节奏相关用例（新增/改写，见 §7）。
- **S3 私有 source 业务缓存与独立 due（Group A 账户面板 / Group B 引用）**（依赖：S2）
  - `snapshot_service.py`：把 `_gather_private_inputs` scheduled 分支拆为
    **fetch/update** 与 **cache-only 组装** 两阶段：
    - Group B 私有（due=1800s，各 source 独立时间戳，CC-1）：`fetch_classic_reference`
      （classic-reference）、`fetch_account_info` + crossMarginData VIP 表
      （account/VIP-reference）。crossMarginData 只抓一次并同时供 classic 引用与
      VIP 表（共享 transport key，业务侧各自记 due）。
    - Group A 私有（due=60s）：`fetch_unified_balances`、`fetch_um_positions`、
      `fetch_spot_balances`、`fetch_ticker_price_map`。
  - 缓存命中即复用，不命中/age-due 才真实 I/O；business timestamp 仅在成功结果后
    推进（FR-2）。
- **S3b 冻结两个 scheduled-only 窄接口**（依赖：S1；被 S4/S6 使用）
  - `backend/services/private_client.py` 新增两个**只做单端点**的 scheduled 接口。
    两个接口各自只允许调用其明确指定的单一 endpoint；除该接口指定 endpoint 外，
    不得调用任何其他 endpoint。特别地，`fetch_next_hourly_rates` 不得调用
    `account/info`、`crossMarginData` 或 `interestRateHistory`。二者也**不得**返回
    单一命中 tier：
    - `fetch_next_hourly_rates(assets: List[str]) -> Dict[str, Optional[str]]`：
      只调用 `GET /sapi/v1/margin/next-hourly-interest-rate?assets=..&isIsolated=false`；
      沿用 `NEXT_HOURLY_BATCH_SIZE=15` 分批与单请求硬顶 20；保留现有 partial-batch
      成功语义（失败批只跳过该批、不整 tier 降级、不 `_cache.clear()`）；返回按
      `base_asset` 拆开的 **raw hourly** 值 `{asset: nextHourlyInterestRate}`；
      **禁止**调用 account info、crossMarginData 或 interestRateHistory。
    - `fetch_interest_rate_history_latest(asset: str) -> Optional[str]`：只调用该
      资产的 `GET /sapi/v1/margin/interestRateHistory?asset=..`，返回 latest 的
      **daily** 值（取 `timestamp` 最大点的 `dailyInterestRate`）；仅由 selected due
      asset 在 next-hourly 失败或无可用值后调用。
  - 上述签名若最终采用等价命名，必须保持**完全相同的窄行为**（同端点、同上限、同
    partial-batch 语义、同返回单位）。分解**不**保留“可复用整个
    `fetch_cost_leg_chain` 由实现者决定”的选择空间。
  - `fetch_cost_leg_chain` 保持**仅供手动点击路径**使用（`_handle_refresh_command`），
    scheduled Group C 的 fetch/update 与 cache-only assembly **都不得**调用它。
  - verify：`python3 -m pytest backend/tests/test_private_client.py`。
- **S4 Group C 组件化 symbol sweep**（依赖：S2, S3, S3b）
  - `snapshot_service.py`：把现有 `_sweep_history` 扩展为 component-aware sweep：
    对本 tick cursor 选中的 ≤10 个主页 symbol，分别独立检查 history / borrow-rate /
    max-borrowable 三个组件的 due（missing 或 age `>=1800s`）。
  - borrow 组件仅对满足 §1.2 FR-4 谓词的行发起；history 组件对所有主页候选发起
    （谓词见 §2.1 第 3 步的 `default_view_history_symbols`，不变）。
  - next-hourly 对本批 due 资产**去重后一次批量**请求，调用 **S3b 的
    `fetch_next_hourly_rates(due_assets)`**（**不是** `fetch_cost_leg_chain`），响应已
    按 `base_asset` 拆开，写入 `borrow_rate_cache`（source `next_hourly`，raw hourly，
    §5.3）。
  - max-borrowable 对本批 due 的唯一 base asset 逐个 `fetch_max_borrowable(asset)`，
    写入 `max_borrowable_cache[base_asset]`。**无 top-50 截断**（FR-5）。
- **S5 borrow-rate per-asset resolution 与单位冻结**（依赖：S4）
  - assembly 端逐 asset 按优先级解析日借币率（不联网）：
    ① `borrow_rate_cache[asset]` source `next_hourly`（raw hourly）→ 用
    `compute_daily_from_hourly`（×24，**恰好一次**）；
    ② `borrow_rate_cache[asset]` source `rate_history`（已 daily）→ 仅 `_quantize`；
    ③ 否则查 Group B `cross_margin_daily_by_vip[account VIP level][asset]`
    （source `cross_margin_tier`，已 daily，`_quantize`）；
    ④ 否则查 `cross_margin_daily_by_vip["0"][asset]`（source `vip0_reference`）。
  - tier③/④ **不**存入 `borrow_rate_cache`，而是 assembly 时从 Group B 缓存
    （`classic_reference` 的 cross 表 + `account_info` 的 VIP level）派生（见 §5.2/§6.2），
    Group C **不**为此重取任何 Group B 端点。
  - 实现方式：逐 asset 用单资产合成 `{"daily_by_asset": {asset: value},
    "chain_hit_source": source}` 调**公有** `resolve_cost_leg_rate`（其内部对
    `next_hourly` 做 `compute_daily_from_hourly` ×24、其余仅 quantize），无需 import
    私有函数、不改 `backend.domain.snapshot`（§4.3）。
- **S6 fallback-only interestRateHistory**（依赖：S4, S5）
  - 仅当某 selected due 主页 borrow 资产的 next-hourly 请求失败或无可用值时，才对
    该资产单独调 **S3b 的 `fetch_interest_rate_history_latest(asset)`**（**不是**
    `fetch_cost_leg_chain`，FR-6），成功后写 `borrow_rate_cache[asset]`（source
    `rate_history`，daily 值）；不新增 logical symbol slot，不扩为 homepage-wide
    轮询。
- **S7 coverage 重定义为 cursor-attempt 语义**（依赖：S4）
  - `snapshot_service.py`：worker 维护 `_coverage_attempted: set[base_asset]` 与
    当前 homepage borrow universe（§1.2 FR-4 谓词的去重 base_asset 集）。coverage
    `{probed, skipped, reason}` wire 形状不变，但计数域改为当前 universe 的 cursor-
    attempt（CC-3）：`probed` = universe 内已发起过 ≥1 次实际 max-borrowable 尝试
    的资产数（失败尝试算数）；`skipped` = universe 内 cursor 尚未到达、未尝试的资产
    数；`reason = "rate_limit_budget"` 当且仅当 `skipped > 0`，否则 `null`。离开
    universe 从账本移除并停止 scheduled borrow 刷新；重新进入时 cursor 下次检查该
    symbol 使 missing/expired 组件 due 且重置为 unattempted。
- **S8 cache-only scheduled assembly**（依赖：S2–S7）
  - `snapshot_service.py`：scheduled assembly 只读 `_global_source_cache` +
    `_funding_history_cache` + `borrow_rate_cache` + `max_borrowable_cache` +
    coverage 账本，组装快照；**绝不**调用 `fetch_cost_leg_chain(rate_probe_assets)`
    或 top-50 max-borrowable 循环，或任何隐藏网络工作（FR-3）。
  - top-level `chain_hit_tier`/`chain_hit_source` 仍作为兼容诊断：反映当前至少一行
    borrow 行使用的最高优先级 source（§5.4）。
  - 保留 `_validate` → `_publish_validated` 的 validate-before-commit 原子发布。
- **S9 手动点击路径回归确认**（依赖：S3, S8）
  - 保持 `_handle_refresh_command` + `_gather_private_inputs(forced_overrides,
    reuse=_last_private_inputs)` + `force=True` 单键 evict 语义不变；确认拆分后
    click 仍复用 `_last_private_inputs` 且不触发全宇宙 `fetch_raw()`、不重取
    balances/positions/valuation。

依赖图：S1 → S2 → S3；S1 → S3b；{S3, S3b} → S4 → {S5 → S6, S7} → S8 → S9。

---

## 4. 精确文件边界（Exact file boundaries）

### 4.1 允许改动的产品/测试文件（product/test scope）

| 文件 | 为什么 |
|---|---|
| `backend/config.py` | S1：slow TTL 默认 3600→1800 + `<=1800` 校验 |
| `backend/adapters/binance_public.py` | S2：拆分 Group A / Group B 公有抓取 seam；保留 `fetch_raw` |
| `backend/services/private_client.py` | S3b：新增两个 scheduled-only 窄接口 `fetch_next_hourly_rates` / `fetch_interest_rate_history_latest`；S3：Group A/B 私有 fetch seam 复用。`fetch_cost_leg_chain` 仅留给手动点击路径 |
| `backend/services/snapshot_service.py` | S2–S9：worker 节奏拆分、source/borrow/max-borrowable 业务缓存、component sweep、cache-only assembly、coverage 账本 |
| `backend/tests/test_config.py` | S1：slow TTL 默认/校验用例 |
| `backend/tests/test_background_worker.py` | S2/S4/S7/S8：节奏分离、组件独立、去重、coverage、无 top-50、无隐藏网络 |
| `backend/tests/test_private_client.py` | S3：1799/1800 transport 边界、slow-TTL 复用/真实 I/O、next-hourly 拆包 |

> `private_client.py` 说明：scheduled Group C **不得**复用 `fetch_cost_leg_chain`
> ——该函数除 next-hourly 外还调用 `fetch_account_info`、`interestRateHistory`、
> `crossMarginData` 并经 `_select_chain_tier` 返回单一命中 tier，会把 Group B/
> fallback 工作混入 Group C，破坏 selected-due-asset、fallback-only、per-asset
> source/timestamp 与 cache-only assembly 契约。因此 S3b 冻结两个只做单端点的窄接口
> （`fetch_next_hourly_rates` 只做 next-hourly 批量并返回按 `base_asset` 拆开的
> `{asset: raw_hourly}`；`fetch_interest_rate_history_latest` 只做单资产
> interestRateHistory latest daily）。二者作为该文件内**最小新增**，复用现有
> `_cached_get`/`_evict`/whitelist，**不得**破坏现有 whitelist / 单-HMAC-exit /
> 审计日志不变量（`test_private_client.py` 的 §1 grep 级断言）；`fetch_cost_leg_chain`
> 原样保留给手动点击路径。

### 4.2 可能需要的额外 backend 文件（须证据 + 最小）

- 无预期额外产品文件。若实现证明必须新增 backend 文件，须显式命名 + 附证据 + 保持
  最小，并按 CC-6 走 human 授权。

### 4.3 明确论证：**不需要**改 `backend/domain/snapshot.py`（CC-6）

- borrow-rate per-asset resolution 复用现成**公有**纯函数
  `resolve_cost_leg_rate`（已被 `snapshot_service.py` import）：assembly 逐 asset 用
  单资产合成的 `{"daily_by_asset": {asset: value}, "chain_hit_source": source}` 调它
  即可（`next_hourly` 内部 ×24 一次，其余 source 仅 quantize），无需 import 任何
  私有函数、无需改 `snapshot.py`。（`compute_daily_from_hourly` 亦为公有，如需直接
  用只在 `snapshot_service.py` import 行追加。）
- borrow universe 谓词（FR-4）与 coverage cursor-attempt 账本在 `snapshot_service.py`
  的 worker 内计算（rows 上的 `daily_funding_rate`/`route_class`/`asset_tag`
  字段已具备），不依赖 `select_borrow_candidates` 的 top-50 语义。
- `assemble_borrow_validation` 的 `borrowability_truncated=True` 参数即产出
  `error="borrowability_not_probed"`，可直接复用于「in-universe 但 cursor 未到/无
  max_borrowable 缓存」的行，无需改该函数。
- 因此 `backend/domain/snapshot.py` **不进入初始 `allowed_pathspecs`**。若 review-1
  或实现证明确需改它（例如新增拆包/normalize helper 无法在 service 层完成），
  实现者必须**停下**并要求 human 批准最小 scope expansion（CC-6）。

### 4.4 禁止/超范围（forbidden，硬边界）

- `frontend/**`、`schemas/api/**`、canonical `docs/**`（未经 user 批准的 promote）。
- 交易/mutation surface、下单/借/还/划转/平仓、credential 文件与环境 dump。
- 无关重构、依赖升级、通用 scheduler 框架。
- `backend/domain/snapshot.py`（见 §4.3，初始禁改）。
- `reports/agent-runs/2026-07-cache-refresh-scheduler-v2/**` 为 evidence 路径；
  实现者仅可更新 `20-implementation.md`。`status.json`、`70-handoff.md`、
  `60-test-output.txt` 与 formal review 文件仍由 bookkeeper 维护。

---

## 5. 内部契约与状态归属（Internal contracts and state ownership）

所有 domain-cache 写仍是 **worker-only**（serial single-writer 不变）。

### 5.1 Group A/B source state（`_global_source_cache`）

```text
SourceCacheEntry = (updated_monotonic, value)
_global_source_cache[source_id] = SourceCacheEntry
```

source_id 与 due（各 id 独立时间戳，CC-1）：

| source_id | endpoint | group | due |
|---|---|---|---|
| `premium_index` | `GET /fapi/v1/premiumIndex` | A | 60s |
| `unified_balances` | `GET /papi/v1/balance` | A | 60s |
| `um_positions` | `GET /papi/v1/um/positionRisk` | A | 60s |
| `spot_balances` | `GET /api/v3/account?omitZeroBalances=true` | A | 60s |
| `price_map` | `GET /api/v3/ticker/price` | A | 60s |
| `futures_exchange_info` | `GET /fapi/v1/exchangeInfo` | B | 1800s |
| `spot_exchange_info` | `GET /api/v3/exchangeInfo` | B | 1800s |
| `funding_info` | `GET /fapi/v1/fundingInfo` | B | 1800s |
| `classic_reference` | `allPairs`+`allAssets`+`crossMarginData` | B | 1800s |
| `account_info` | `GET /sapi/v1/account/info` | B | 1800s |

- Group B 三类独立 due（CC-1）：public exchange/funding info、classic-reference、
  account/VIP-reference。一个失败不拖累另一个已成功者进入 30s 重取；一个成功不压制
  另一个失败者的 retry。
- Group B 引用数据最小兼容方式（改自 correction 点 3）：`fetch_classic_reference`
  **加性**返回完整 `cross_margin_daily_by_vip`（`{vip_level: {coin: dailyInterest}}`）
  表，**同时保留**现有 `pair_listed_by_symbol` / `asset_borrowable_by_name` /
  `daily_interest_vip0_by_coin` 三键（保持既有含义）。注意
  `test_private_client.py::test_classic_reference_maps_raw_fields` 是精确 dict 相等
  断言，新增该键须**同步更新该测试**（`test_private_client.py` 在允许文件内，§7.1）。
  `fetch_account_info` 维持独立
  source/timestamp（`account_info`）。assembly 用当前 classic/cross 表 + account VIP
  level 组合 tier③/④，**不**在 Group C 重取这些 Group B 端点。
- Group B business cadence 固定 1800s，是**模块常量**（如
  `GROUP_B_REFRESH_SECONDS = 1800`），**非**环境可配（CC-2）；Group A due 复用
  `cache_ttl_seconds`（60）。

### 5.2 Group C cursor 与 per-symbol/per-asset 缓存

```text
_funding_history_cache[symbol]  = (updated_monotonic, raw entries)   # 现有，保留
borrow_rate_cache[base_asset]   = (updated_monotonic, value, source) # 新增
max_borrowable_cache[base_asset]= (updated_monotonic, value)         # 新增
```

- cursor：复用 `_history_cursor`（在候选 snapshot 列表上滚动，mod-n，稳定不跳过；
  当所有组件 fresh、无请求时仍前进——`11-adr.md` Edge Cases）。每 tick 至多检查 10
  个 symbol（logical work unit，非 HTTP 硬上限）。
- 去重：一批选中 symbol 中重复 base_asset 只查一次 next-hourly / max-borrowable。
- success-only 时间戳（FR-2）：三个缓存均只在成功结果后写/推进 `updated_monotonic`；
  失败**不**写缓存（沿用现有 `_fetch_history_for` 「失败不缓存」不变量）。
- source selection（每 asset）：next-hourly（tier①）→ 失败/不可用时
  interestRateHistory fallback（tier②，FR-6）→ Group B VIP/reference 表
  （tier③/④）。

### 5.3 borrow-rate 缓存单位冻结（CC-4，显式测试）

- **选定表示**：`borrow_rate_cache[base_asset] = (ts, value, source)`，只承载
  **Group C 抓取的两种 source**：`next_hourly`（`value` = `fetch_next_hourly_rates`
  返回的 **raw hourly 字符串**）或 `rate_history`（`value` =
  `fetch_interest_rate_history_latest` 返回的 **daily 字符串**）。
- tier③`cross_margin_tier` / tier④`vip0_reference` **不进** `borrow_rate_cache`，
  在 assembly 时从 Group B 缓存（`cross_margin_daily_by_vip` + account VIP level）
  按 §5 S5 优先级派生。
- **恰好一次 normalize**：在 resolution（装配行时）对 `next_hourly` 用
  `compute_daily_from_hourly(value)`（×24），其它 source 已是 daily 仅 `_quantize`
  （经公有 `resolve_cost_leg_rate` 逻辑，不二次 ×24）。
- 因此 assembly **禁止**对已 normalize 值再乘 `*24`；此不变量由 §7 的
  `test_borrow_rate_hourly_normalized_exactly_once` 显式钉死。

### 5.4 发布边界与 wire 兼容（`chain_hit_tier` / `chain_hit_source`）

- wire response 形状不变；source 时间戳是内部调度元数据，不入 public schema。
- top-level `borrow_validation.chain_hit_tier`/`chain_hit_source`（由
  `_assemble` 组入 `borrow_validation_summary`）保持含义：**当前至少一行 borrow 行**
  使用的最高优先级 source 的 tier/source。cache-only assembly 从 per-asset
  `borrow_rate_cache` 的 source 推导该聚合诊断，不再来自单一 all-row
  `fetch_cost_leg_chain` 结果；它**不**断言每行同源（`10-design.md` §6）。
- `sort_basis`：`net_daily_yield`（有可用 cost leg 时）/`abs_daily_funding_rate`；
  判定条件保持「classic_ref 非空 且 存在可用 borrow rate」的等价语义。

### 5.5 slow transport TTL `<=1800` 校验与 1799/1800 边界

- `PrivateClient._cached_get` 用绝对到期 `cached[0] > now`（`private_client.py:215`）：
  设 slow TTL=1800，条目在 `t0` 写入，`t0+1800` 到期。`now = t0+1799` → 复用；
  `now = t0+1800` → 严格 `>` 为假 → 真实 signed GET（真实 upstream I/O）。
- business due age `>=1800s` 与 transport 到期同点触发（1800）：因 business timestamp
  在成功抓取（写 transport 条目）之后捕获，`transport_ts <= business_ts` →
  `transport_age >= business_age`，故 business age 到 1800 时 transport 必已到期，
  age-due 调用必做真实 I/O，旧 transport 条目不会被当成 30 分钟成功刷新、也不推进
  business `updated_monotonic`（FR-2 保证成立）。
- 校验：`private_channel_ttl_seconds > 1800` 在 `config.from_env` 拒绝（`ValueError`）。

---

## 6. Endpoint-to-function 归属矩阵（Ownership matrix）

fetching seam / cache key / due rule / assembly consumer。**cache-only assembly 发起
的任何隐藏网络调用都是显式失败**（由 §7 的 stub 计数断言钉死）。

### 6.1 Group A（60s；无 10-symbol 预算）

| endpoint | fetching seam | cache key | due | assembly consumer |
|---|---|---|---|---|
| `GET /fapi/v1/premiumIndex` | binance_public Group A seam | `premium_index` | 60s | `_eligible_rows` premium_by_sym |
| `GET /api/v3/ticker/price` | `fetch_ticker_price_map` | `price_map` | 60s | private_account 估值 / value_usdt |
| `GET /papi/v1/balance` | `fetch_unified_balances` | `unified_balances` | 60s | `assemble_private_account` |
| `GET /papi/v1/um/positionRisk` | `fetch_um_positions` | `um_positions` | 60s | `assemble_private_account` |
| `GET /api/v3/account?omitZeroBalances=true` | `fetch_spot_balances` | `spot_balances` | 60s | `assemble_private_account` |

### 6.2 Group B（固定 1800s；无 cursor / 10-symbol 预算）

| endpoint | fetching seam | cache key | due | assembly consumer |
|---|---|---|---|---|
| `GET /fapi/v1/exchangeInfo` | Group B 公有 seam | `futures_exchange_info` | 1800s | `_eligible_rows` 合格性 |
| `GET /api/v3/exchangeInfo` | Group B 公有 seam | `spot_exchange_info` | 1800s | spot-leg 匹配 |
| `GET /fapi/v1/fundingInfo` | Group B 公有 seam（best-effort 降级+warning） | `funding_info` | 1800s | funding_interval_by_sym |
| `GET /sapi/v1/margin/allPairs` | `fetch_classic_reference` | `classic_reference` | 1800s | `assemble_borrow_validation` pair_listed |
| `GET /sapi/v1/margin/allAssets` | `fetch_classic_reference` | `classic_reference` | 1800s | asset_borrowable |
| `GET /sapi/v1/margin/crossMarginData` | `fetch_classic_reference`（共享） | `classic_reference` + VIP 表 | 1800s | vip0/VIP reference borrow-rate |
| `GET /sapi/v1/account/info` | `fetch_account_info` | `account_info` | 1800s | VIP level + tier③ 选择 |

### 6.3 Group C（每 30s，≤10 主页 symbol）

| endpoint | fetching seam | cache key | due | eligibility |
|---|---|---|---|---|
| `GET /fapi/v1/fundingRate?symbol=..&startTime=..&endTime=..&limit=1000` | `_fetch_history_for`（每 symbol 一请求） | `symbol` | missing 或 `>=1800s` | 每个主页候选（`default_view_history_symbols`） |
| `GET /sapi/v1/margin/next-hourly-interest-rate?assets=..&isIsolated=false` | `fetch_next_hourly_rates`（S3b 窄接口，上限 15/硬顶 20，只做此端点） | 响应拆包 per `base_asset` → `borrow_rate_cache`（source `next_hourly`） | missing 或 `>=1800s` | FR-4 谓词 |
| `GET /papi/v1/margin/maxBorrowable?asset=..` | `fetch_max_borrowable`（每 due 唯一 base asset） | `base_asset` → `max_borrowable_cache` | missing 或 `>=1800s` | FR-4 谓词；**无 top-50** |

### 6.4 fallback / manual / discovery-only（非常规组成员）

| endpoint | 分类 | 规则 |
|---|---|---|
| `GET /sapi/v1/margin/interestRateHistory?asset=..` | fallback-only（seam `fetch_interest_rate_history_latest`，S3b 单资产窄接口） | 仅 selected due 主页 borrow 资产 next-hourly 失败/无可用值后（FR-6）；不加 slot；scheduled 侧**不**经 `fetch_cost_leg_chain` |
| `GET /fapi/v1/premiumIndex?symbol=..`、选中行 history、单资产 next-hourly、`interestRateHistory`、`maxBorrowable` | manual | 属 `_handle_refresh_command` 行点击命令，不占 scheduled slot；`force=True` 单键 evict |
| `GET /papi/v1/margin/marginInterestHistory`、`GET /papi/v1/portfolio/interest-history` | discovery-only | whitelist 内注册但**不**被任何 assembly 调用 |

---

## 7. 确定性测试与精确 blocking 命令（Deterministic tests & blocking commands）

测试沿用现有约定：offline / stub 客户端注入（`test_background_worker.py` 的
`_StubPublic`/`_StubPrivate`/`_service`）、`monkeypatch` `snapshot_service.time.monotonic`
或 `private_client.time`、直接调 `_scheduled_tick()` 驱动（不起线程、不联网）。

### 7.1 单元用例（必须新增/覆盖）

- **节奏分离**：Group A 60s、Group B 1800s 各自独立 due；推进时钟验证 Group B 未到
  1800s 时不重取 exchangeInfo/fundingInfo，而 premium_index 每 60s 更新。
- **Group B 不占 Group C 槽**：Group B 刷新不消耗 10-symbol cursor 预算。
- **组件独立**（FR-7）：某选中 symbol history fresh 但 borrow-rate 过期 → 只刷
  borrow-rate；max-borrowable missing 且其它 fresh → 只调 `maxBorrowable`。
- **CC-1 独立源状态**：classic-reference 失败不使已成功的 public Group B 或
  account/VIP-reference 进入 30s 重取；反之亦然（用 stub 计数断言）。
- **per-asset batch 时间戳**（FR-7）：批量 next-hourly 结果按 asset 各自打时间戳，
  而非按 batch 字符串；批量成员变化不改变单资产 freshness identity。
- **去重**：一批选中 symbol 中重复 base_asset 只查一次。
- **borrow-rate 单位**（CC-4）：`test_borrow_rate_hourly_normalized_exactly_once`——
  `next_hourly` 值 `"0.00000500"` resolution 得 `"0.00012000"`（恰好 ×24 一次），
  且 assembly 不二次 ×24。
- **阈值边界**（FR-4）：`daily_funding_rate` 为 `-0.00030000` 的负行**不**进入
  scheduled borrow universe/coverage；越过至 `-0.00030001` 后在后续 cursor 检查
  变为 eligible。正资金/非 MARGIN_SPOT_CANDIDATE/非 CRYPTO·METAL 选中 symbol 不触发
  borrow 调用。
- **无 top-50 截断**（FR-5）：>50 个主页 borrow 候选可在连续 cursor 周期内全部获得
  max-borrowable 工作；无 global top-50 残留。
- **coverage entry/exit/re-entry**（CC-3）：`probed` 只随当前 universe 的 cursor
  实际尝试递增（失败尝试算数）；越界低费率资产不计入 `skipped`；离开 universe 移出
  账本；重新进入以 unattempted 起算；`reason == "rate_limit_budget"` iff `skipped>0`。
- **失败时间戳行为**（FR-2）：endpoint 失败不推进成功 business timestamp、不写缓存；
  age-due 调用做真实 upstream I/O。
- **1799/1800 边界**：slow transport 在 1799s 复用、1800s 真实 signed GET；运行时
  slow TTL >1800 被拒。
- **cache-only assembly 无隐藏网络**：scheduled assembly **不**发起 all-row
  cost-leg 或 top-50 max-borrowable 网络调用；`interestRateHistory` 只在 selected-
  asset next-hourly 失败/缺失后运行（stub 计数断言）。
- **scheduled Group C 窄接口隔离**（correction 点 5，必须显式）：
  - next-hourly 成功时，scheduled 路径对 `account/info`、`crossMarginData`、
    `interestRateHistory` 的调用计数**均为 0**（Group C 只调
    `fetch_next_hourly_rates` + `fetch_max_borrowable`）；
  - 部分资产 next-hourly 缺失/失败时，只对**这些 selected due assets** 调
    `fetch_interest_rate_history_latest`，不对其它资产触发 fallback；
  - 手动点击路径**仍**调用原 `fetch_cost_leg_chain`（`_handle_refresh_command`
    的既有 stub 断言保持）。
- **classic_reference 加性键**：更新
  `test_private_client.py::test_classic_reference_maps_raw_fields`，在精确 dict 断言中
  加入新 `cross_margin_daily_by_vip` 键并保留原三键值不变。
- **手动刷新不变**（FR-8）：`_handle_refresh_command` 仍单键 evict、复用
  `_last_private_inputs`、不触发全宇宙 `fetch_raw()`、不重取 balances/positions/
  valuation；既有 `test_symbol_snapshot_endpoint.py` 用例保持通过。

### 7.2 集成用例

- 冷启动 Group A/B 发布 + Group C 增量 warm 均 schema-valid。
- 现有全快照 `GET /api/public-market/snapshot` 与行点击端点契约不变。
- 现有前端 fixtures/self-checks 不变。

### 7.3 精确 blocking 命令（implementer 运行，bookkeeper 独立复核）

- 根目录**无** `pyproject.toml`/`pytest.ini`/`setup.cfg`/`tox.ini`/`Makefile`；测试
  运行方式由当前源码/测试判定：所有测试用 `from backend...` 绝对导入，`pytest`
  8.4.2 可从仓库根收集（已核实收集到 301 项）。
- **聚焦命令**（开发中迭代用，非最终 gate）：
  - `python3 -m pytest backend/tests/test_config.py`
  - `python3 -m pytest backend/tests/test_background_worker.py`
  - `python3 -m pytest backend/tests/test_private_client.py`
- **最终 blocking 命令集**（implementer 完成前运行，bookkeeper 复核）：
  - `python3 -m pytest backend/tests`
- **lint/type 命令**：当前仓库根**无** ruff/mypy/flake8/type 配置证据。故本 stage
  的唯一 evidence-based blocking 命令是上面的 pytest。**不**凭空发明 lint/type 命令；
  若未来需要 lint/type gate，须由 human 追加配置证据后再定义（此处报告不确定性，
  而非查历史 stage 推断）。

---

## 8. Manual delivery handoff

- Human dispatches a fresh `claude_glm` implementation Session from
  `implementation-claude-glm.prompt.md`.
- Write scope is the seven files in §4.1 plus `20-implementation.md` only.
- `status.json`, `70-handoff.md`, test evidence, commits and review dispatch stay
  under bookkeeper control.
- Review-1 is a fresh read-only Kimi Session; it must not share provider,
  transcript or tool state with `zhipu_glm` implementation.
- Review-2 routing is selected after review-1 and records inherited design
  involvement without treating it as v2 delivery-code authorship.
- The complete process override is `13-manual-delivery-amendment.md`.

---

## 9. 风险与 review focus（Risk and review focus）

### 9.1 命名风险

- race / single-writer：拆分抓取阶段后仍须只有 worker 写 domain 缓存；
  `_publish_validated` 单引用交换与 validate-before-commit 原子性不得破坏。
- false freshness：business timestamp 仅成功后推进；slow transport `<=1800` 防止旧
  transport 条目冒充 30 分钟成功刷新（FR-2 / §5.5）。
- cursor starvation：cursor 必须在多数组件 fresh、无请求时仍前进，避免某些 symbol
  永不被检查（`11-adr.md` Edge Cases）。
- duplicate assets：一批内重复 base_asset 去重，避免重复 next-hourly/maxBorrowable。
- mixed-source 兼容：`chain_hit_tier`/`chain_hit_source` 仅为聚合诊断，不得被误当成
  每行同源断言（§5.4）。
- transport/business TTL 失配：3600 运行时覆盖会重造 false 30 分钟刷新——校验须把
  slow scheduled transport TTL 钉在 `<=1800`（`11-adr.md` Risks）。
- failure 语义：本 stage 只保证正常成功路径；失败/empty/partial 沿用既有行为，不得
  悄悄引入新 last-good/overwrite 策略。
- request-pressure 回归：scheduled assembly 若仍留 all-row `fetch_cost_leg_chain` 或
  top-50 探针，会绕过 10-symbol 压力模型（即便 transport 缓存掩盖部分调用）。
- manual-path 回归：click 路径的 deadline gate、单键 evict、`_last_private_inputs`
  复用、不重取 balances 均须保持。

### 9.2 给 Kimi `review-1` 的 invariants 与 adversarial cases

- INV-1 cache-only scheduled assembly 零 upstream 网络（stub 计数为 0 的 all-row
  cost-leg 与 top-50 maxBorrowable）。
- INV-1b scheduled Group C 只用窄接口：`fetch_next_hourly_rates` /
  `fetch_interest_rate_history_latest`（仅 fallback）/ `fetch_max_borrowable`；
  next-hourly 成功时 `account/info`、`crossMarginData`、`interestRateHistory` 计数为 0；
  `fetch_cost_leg_chain` **仅**出现在手动点击路径。
- INV-2 borrow-rate hourly 恰好 ×24 一次；无二次归一化（CC-4）。
- INV-3 三组 freshness gate 互不压制（组件独立 + CC-1 源独立）。
- INV-4 coverage 是 cursor-attempt 语义：失败尝试算 attempt；越界低费率不计 skipped；
  exit 移除、re-entry unattempted（CC-3）。
- INV-5 slow transport 1799 复用 / 1800 真实 I/O；运行时 >1800 被拒。
- 对抗案例：universe 成员在两 tick 间抖动（穿越 `-0.00030000` 阈值）；同 base_asset
  多 symbol；next-hourly 部分 batch 失败（既有 partial-batch 语义不得回退为整 tier
  降级）；Group B 单源失败时其余源不被拖入 30s 重取；cursor 在 candidate 集缩小时
  mod-n 不跳过（对照现有 `test_cursor_wraps_around_on_a_shrinking_candidate_set`）。

---

## 10. 验收清单与 stop 条件（Acceptance checklist & stop conditions）

对照 `00-task.md` Acceptance Criteria，逐条可客观检查：

- [ ] AC-1 每个 scheduled upstream endpoint 恰好归入一个常规节奏组，或显式记为
  fallback/manual/discovery-only（§6 矩阵覆盖全部端点）。
- [ ] AC-2 60s 组独立刷新 all-market 与 account 输入，与两个慢组解耦（§7.1 节奏分离）。
- [ ] AC-3 固定 1800s 组刷新冻结的 shared/unified 端点，不消耗 symbol-sweep 槽。
- [ ] AC-4 每 30s 主页 sweep 至多检查 10 个 eligible symbol。
- [ ] AC-5 history / borrow-rate / max-borrowable freshness 独立检查；一个 fresh 组件
  不压制另一个 missing/expired 组件的刷新。
- [ ] AC-6 批量 borrow-rate 响应拆包为 per-base-asset 业务缓存条目，各自独立时间戳。
- [ ] AC-7 当前 API 响应字段与前端行为不变（wire schema、`chain_hit_tier`/
  `chain_hit_source`、coverage 形状保持）。
- [ ] AC-8 现有手动选中 symbol 刷新行为不变。
- [ ] AC-9 确定性测试钉死节奏分离、组件级 skip/update、per-asset batch-cache 时间戳。
- [ ] slow transport TTL 默认 1800 且 effective `<=1800`；1799/1800 边界测试通过。
- [ ] scheduled borrow universe 严格用 `daily_funding_rate < -0.00030000` 组合谓词，
  无 global top-50。
- [ ] `python3 -m pytest backend/tests` 全绿（含新增用例）。

### stop 条件 / 需 human 解决的产品歧义

- **无**当前必须由 human 解决的产品歧义：三条 P1 已在
  `approved_design_amendments` 冻结，谓词、TTL、coverage 语义均已确定。
- 唯一 hard stop 触发点：若实现证明**必须**改 `backend/domain/snapshot.py`（CC-6）
  或新增 backend 产品文件（§4.2），实现者须停下取得 human 的最小
  scope expansion 批准——这是设计边界 stop，不是普通实现细节。
- scheduled Group C 的取数**不是**实现者自决项：已冻结为 S3b 的窄接口
  `fetch_next_hourly_rates` / `fetch_interest_rate_history_latest`（+
  `fetch_max_borrowable`），**禁止**在 scheduled 侧复用 `fetch_cost_leg_chain`。
- 常规实现细节（如缓存 dict 的具体字段命名、循环/批量的内部组织）**不**是 blocker，
  由实现者在 §4 边界内决定。

---

本地北京时间: 2026-07-14 22:41:45 CST
下一步模型: human → claude_glm
下一步任务: 人工执行 `implementation-claude-glm.prompt.md`，实现者在七文件边界内写代码与测试，然后交回 bookkeeper 复核

# 平滑开单 V1 开发清单（单 Implementer 活动方案）

状态：**Planner 定向返修完成，等待定向计划复核。本文不授权实现、创建 worktree/分支、安装依赖、连接网络、启动服务、下单、修改状态、提交、合并或部署。**

- 产品与资金语义唯一权威：`docs/planning/smooth-open-orders-v1.md`（本文不复制 gate 契约，只在必要处引用条目号）。
- P0 证据唯一权威：`docs/planning/ccxt-bookticker-recon-2026-08-13.md`。
- 已冻结的实现不变量：`reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/01-advisory-design-reviews.md` §4。
- 上一轮正式计划评审（`REWORK`）：`reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-formal-plan-review-deepseek-v4-pro.handoff.md`。
- 本文引用的行号按 `base_sha = 2e5902347c5f0ac81638c67dc7a1bf20a9141ac9` 核对；该 base 与上一轮受审树相比 `backend/`、`frontend/` 零改动。实现前仍应重新 `grep` 确认。

## 0. 本轮修订说明

### 0.1 Human 最新开发路由决定（本轮改稿的起因）

**不再拆成 A/B/C/D 多终端并行任务。** 由**一个** `gpt-5.6-sol`、reasoning `xhigh`、provider `openai` 的 Implementer，在**一个**独立 worktree/分支内完成平滑开单 V1 的 provider、gate/store、worker/API 与前端真实接线，形成**一个** dispatch、一个 `status.json.current_task`、一个 handoff、一个交付区间。

### 0.2 DeepSeek 计划评审发现的关闭方式

| 发现 | 关闭方式 | 本文位置 |
|---|---|---|
| R1：§5.4 以 handoff 替代在途 `current_task`，违反单活动 packet 规则 | **随并行拓扑一起消失**。只有一个 implementation task，`current_task` 全程指向它，三态闭环（`dispatched → reported → verified`）在 `status.json` 里完整可表达。不新增状态数组、并行 ledger 或新 schema，也不再用 handoff 承担在途状态 | §3.6、§11 |
| R2：§3.2 断言 `set_task_status` 是唯一状态迁移收口，与代码事实矛盾，系统 pause/stop 会残留 gate | **按真实代码改正**。该错误结论已删除。全仓穷举出**四条** `running → 非 running` 写路径（比评审指出的三条多一条），逐条给出处理方式与证据；三条需在各自事务内、仅在写命中时清 gate，第四条给出不需清理的不变量并配断言型回归 | §4.2.3、§4.2.4 |
| R3：§8.1 让 Bookkeeper 建集成分支并 cherry-pick，越记账职责且与「C 是唯一集成者」矛盾 | **随跨分支集成一起消失**。单 Implementer 直接在唯一实现分支上形成 delivery commit；Bookkeeper 只核验 handoff/commit/测试、`git rev-parse` 固定 `base_sha..delivery_sha`、准备评审 dispatch，不建分支、不 cherry-pick、不合出交付 | §7.1 |
| O1：`latest` 返回语义留了「二选一」分叉 | 钉死一种，见 §4.1 第 2 条 | §4.1 |
| O2：provider 放 `services/` 的纯度依据引用不准确 | 按 `test_hedge_purity.py` 的真实正则改写理由 | §4.1 |
| O3：生产 provider 缺失与测试注入 fake provider 的区别未写清 | 明确两种形态与各自期望 | §4.3 第 6 条、§5 |

### 0.3 已作废的旧方案（历史说明，不得再被选用）

前一版细拆中的 **A/B/C/D 四任务包、四个 worktree/分支、分阶段 cherry-pick 集成流程、三份多终端启动文稿、以及为跨任务协作而设的 owner/consumer 接口冻结与冲突检查**，已由 Human 于 2026-08-13 决定作废。后续模型不得在新旧两套方案之间选择：**本文 §3 是唯一活动实施方案**。跨层最小契约（§4）、P0→P1 验收（§5）、依赖清单（§6）与资金安全门保留，只删掉纯粹为并行协作而存在的部分。

## 1. 已取得的开发输入（不变）

- Human 已冻结：`bookTicker` 一档、严格 `spread > threshold`、两腿各 `>=80%`、每轮 5 分钟、`成交1次` 只放行当前 gate、两腿下单继续复用立即开单。
- P0 已验证 `ccxt==4.5.64` 的 Binance spot/USDⓈ-M `watchBidsAsks`、双 watcher cancel 隔离、普通合约单位和 raw/normalized 差异。
- 必须取 `info.b/B/a/A` 原始字符串；spot 无交易所时间戳；1000x 封禁不能靠 `contractSize` 解除。
- P0 未证明重连 generation、引用归零、close 无残留、多 symbol 共享；这些必须在本交付中 fail-closed 验收（见 §5）。
- 前端 fake 只用于观察布局，不能当最终 API 或后端字段证据。

## 2. 哪些是 Human 已冻结、哪些是本文的实现选择

复核只对第二类提意见；第一类除非有当前代码/契约反证并说明实际影响，否则不重开。

| 类别 | 内容 |
|---|---|
| Human 已冻结（不重开） | `bookTicker`/`watchBidsAsks` 一档；方向开单率严格 `>` signed threshold；两腿各 `>=80%` 覆盖；每轮 5 分钟；超时回退既有立即链；`成交1次` 只放行当前 gate；两腿异步提交并同步等返回；单腿/查单/结算复用立即链；CCXT Pro 作为公共盘口来源（`ccxt==4.5.64`）；不做 `立即成交所有`、私有 WS、完整 order book、动态阈值；**单 Implementer 实施路由** |
| 本文的实现选择（可复核） | provider 模块路径与最小接口；`latest` 返回语义；`domain.L1Quote` / `evaluate_smooth_gate` 的纯函数边界；四条状态写路径的 gate 清理方式与第四条的豁免论证；`prepare_attempt` 增加两个可选关键字参数；provider 缺失时的 fail-closed 形态；worktree/分支命名；内部实现顺序；回归矩阵；依赖清单文件名 |

## 3. 活动实施方案：单 Implementer 任务包

### 3.1 任务身份

| 项 | 值 |
|---|---|
| task_id | `smooth-open-v1-fullstack-gpt56sol-xhigh` |
| target_role | Implementer |
| target_model / reasoning / provider | `gpt-5.6-sol` / `xhigh` / `openai` |
| worktree | `<<WORKTREE>>`（占位符，建议 `/Users/ark/Desktop/ai code/funding_hedging-smooth-v1`） |
| branch | `<<BRANCH>>`（占位符，建议 `smooth/v1-fullstack`） |
| 输入提交 | `<<BASE_SHA>>`（唯一 committed input，由 Bookkeeper 在 ACCEPT 后 `git rev-parse` 填入） |
| status revision | `<<REVISION>>` |
| handoff（唯一） | `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-fullstack-gpt56sol-xhigh.handoff.md` |
| 交付 | 该分支上**一个**本地 delivery commit，不 push、不合并 |

worktree 放在 `~/Desktop/ai code/` 之下是刻意的：`PROJECT_STATE.md` 记录的 macOS TCC 限制已确认该目录对当前终端可读写（同级已有 `funding_hedging-kimi-smooth-ui` 先例），换到别处会重演 launchd 那类权限故障。

### 3.2 Allowed Files（唯一所有权，联集）

生产代码：

- `backend/services/best_bid_ask_provider.py`（新建）
- `backend/hedge_open_tasks/domain.py`
- `backend/hedge_open_tasks/store.py`
- `backend/hedge_open_tasks/service.py`
- `backend/app/server.py`
- `frontend/index.html`
- `requirements.txt`（新建，见 §6）

测试：

- `backend/tests/test_best_bid_ask_provider.py`（新建）
- `backend/tests/test_smooth_gate_store.py`（新建）
- `backend/tests/test_smooth_gate_worker.py`（新建）
- `backend/tests/test_smooth_api.py`（新建）
- `backend/tests/test_hedge_domain.py`、`backend/tests/test_hedge_store.py`、`backend/tests/test_hedge_service.py`、`backend/tests/test_hedge_api.py`、`backend/tests/test_frontend_field_binding.py`
- `frontend/self-check.js`

交接件：

- `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-fullstack-gpt56sol-xhigh.handoff.md`（新建，create-only）

### 3.3 明确禁止改动的文件

- `backend/services/live_hedge_executor.py`、`backend/services/hedge_open_live_client.py`、`backend/services/hedge_preflight_provider.py`、`backend/hedge_open_tasks/executor.py` —— **实盘两腿提交、查单、结算行为一行不得改**。平滑只决定「何时调用」，不改「如何调用」。
- `backend/hedge_open_tasks/scheduler.py` —— 平滑链路完全走 task-local worker，1 秒 tick 只驱动 dry-run 路径，本轮不需要改。
- `backend/domain/snapshot.py` —— 开单率必须**复用**其 `compute_opening_spread_pct`，不得修改也不得复制公式。
- `backend/tests/test_hedge_purity.py`、`test_hedge_cycle_core.py`、`test_hedge_cycle_close.py`、`test_hedge_task_local.py`、`test_hedge_review2_regressions.py`、`test_live_hedge_executor.py`、`test_hedge_executor.py`、`test_book_ticker.py` —— 只跑不改；需要改它们才能变绿，说明本交付破坏了既有契约，停下报告。
- `reports/agent-runs/**/status.json`、`reports/agent-runs/ACTIVE.json`、`PROJECT_STATE.md`、其他 stage 的任何文件、`.venv/`。

### 3.4 内部实现顺序（同一任务内的 checkpoint，不是独立 dispatch）

四个 checkpoint 只表达**技术依赖顺序**，不构成独立 dispatch、stage、owner 或并行工作流，也不各自产生 commit：

1. **CP1 provider + 依赖清单**：`best_bid_ask_provider.py` 与 `requirements.txt`；跑 `test_best_bid_ask_provider.py` 与 `test_hedge_purity.py`。
2. **CP2 gate 域与持久化**：`domain.py`（阈值规范化、`L1Quote`、`evaluate_smooth_gate`）与 `store.py`（迁移、三个 gate 事务方法、`prepare_attempt` 扩参、§4.2.3 的四条状态路径）；跑 `test_smooth_gate_store.py`、`test_hedge_domain.py`、`test_hedge_store.py`、`test_hedge_cycle_core.py`。
3. **CP3 worker/API 接线**：`service.py`、`server.py`；跑 `test_smooth_gate_worker.py`、`test_smooth_api.py` 与既有 hedge 回归组。
4. **CP4 前端真实接线**：`index.html`、`self-check.js`、`test_frontend_field_binding.py`。

CP2 依赖 CP1 的快照类型，CP3 依赖 CP1+CP2 的接口，CP4 依赖 CP3 冻结的返回形状。任一 checkpoint 未绿不得进入下一个。全部完成后跑 §7.2 全量回归，再做**唯一**一个 delivery commit。

### 3.5 全量验收命令

```bash
.venv/bin/python -m pytest backend/tests/test_best_bid_ask_provider.py \
    backend/tests/test_smooth_gate_store.py backend/tests/test_smooth_gate_worker.py \
    backend/tests/test_smooth_api.py -q
.venv/bin/python -m pytest backend/tests/test_hedge_domain.py backend/tests/test_hedge_store.py \
    backend/tests/test_hedge_service.py backend/tests/test_hedge_api.py \
    backend/tests/test_hedge_cycle_core.py backend/tests/test_hedge_cycle_close.py \
    backend/tests/test_hedge_task_local.py backend/tests/test_hedge_review2_regressions.py \
    backend/tests/test_hedge_leverage.py backend/tests/test_hedge_purity.py -q
.venv/bin/python -m pytest backend/tests -q
node frontend/self-check.js
git diff --check
```

全部命令必须在**未安装 ccxt** 的当前 `.venv` 下通过（依据见 §4.1 第 4 条与 §6）。

### 3.6 记账与边界

- `status.json` 全程只有这一个 `current_task`。实现者按 Harness 只能把**自己的**任务从 `dispatched` 改为 `reported`；不得写 `verified`、不得选择后继模型、不得改 `ACTIVE.json` / `PROJECT_STATE.md` / 其他 stage 文件。
- 唯一 handoff 按 `agents/roles.md` 的 Task Handoff Evidence Contract 写在 §3.1 的确定路径（create-only，路径由 Bookkeeper 在 dispatch 前 `test ! -e` 预检并记录）。
- 一个本地 delivery commit，**不 push、不合并**。
- 禁止：安装依赖（含 `pip install ccxt`）、连接任何网络/WebSocket/HTTP 行情或订单接口、读取凭证、启动或重启服务、真实下单、部署。
- 范围不足是 blocker，不是自行扩权的理由（`AGENTS.md` §3.3）。验收命令红灯时不得改既有测试断言、不得 `-k` 跳过、不得扩大文件范围绕过——停下报 blocked。

## 4. 最小跨层契约

单 owner 之后不再需要「owner/consumer 接口冻结」，以下保留的是**实现必须满足的语义**（资金安全门与可测试性），不是协作协议。

### 4.1 公共盘口 Provider

模块路径固定：`backend/services/best_bid_ask_provider.py`。

**为什么放在 `backend/services/` 而不是 `hedge_open_tasks/`（O2 已按真实正则改正）**：`backend/tests/test_hedge_purity.py` 的 `_FORBIDDEN_IMPORT_RE` 实际只禁 `urllib|socket|requests|http.client|hmac|hashlib`，**不含 `aiohttp` 或 `ccxt`**；真正约束方向的是同文件的 `_LIVE_MODULE_RE`——`hedge_open_tasks/**` 不得 import services 层的实盘模块（`hedge_open_live_client`/`live_hedge_executor`/`hedge_preflight_provider`），实盘能力一律经注入进入任务包。provider 因此与这三个模块同层、同样靠注入接入，既符合既有 seam，也不让任务包新增任何传输依赖。

```python
MarketKey = tuple[str, str, str]          # (exchange_id, market_type, symbol)
                                          # 例：("binance", "spot", "BTCUSDT") / ("binance", "swap", "BTCUSDT")

@dataclass(frozen=True)
class BookTickerSnapshot:
    key: MarketKey
    bid_price: Decimal
    bid_qty: Decimal
    ask_price: Decimal
    ask_qty: Decimal
    exchange_ts_ms: int | None            # perp 取 raw E；spot 恒为 None
    received_at_us: int                   # 最后一次合法 tick 的本地墙钟
    generation: int                       # 每次订阅建立或重连递增
    status: str                           # "connecting" | "live" | "disconnected"
    error_zh: str | None                  # 安全中文摘要，禁含凭证/完整请求

class BestBidAskProvider:
    def __init__(self, *, on_change: Callable[[MarketKey], None] | None = None,
                 source_factory: Callable[[MarketKey], "L1Source"] | None = None) -> None: ...
    def start(self) -> None: ...
    def subscribe(self, key: MarketKey) -> None: ...
    def release(self, key: MarketKey) -> None: ...
    def latest(self, key: MarketKey) -> BookTickerSnapshot | None: ...
    def close(self, timeout: float = 5.0) -> None: ...
```

1. **Decimal 即原始字符串**：四个价量字段由 `Decimal(raw_str)` 从 `info` 的 `b/B/a/A` 直接构造。`Decimal` 保留尾零（`format(Decimal("7.48647000"), 'f')` 原样回读），因此**不再单独保存 raw 字符串字段**。CCXT normalized 的 `bid/ask/bidVolume/askVolume`（float）在任何路径上都不得出现。
2. **`latest` 的唯一返回语义（O1 已钉死，不留二选一）**：
   - 返回 `None` **当且仅当**该 key 未被订阅，或当前 generation 从未收到过一条合法 tick（四字段均可解析且 `> 0`）。
   - 其余情况**恒返回快照对象**，`status` 是唯一有效性判据。watcher 抛错/断开/重连中时，返回的是「最后一次合法 tick 的值 + `status="disconnected"`（或 `"connecting"`）+ 该 tick 的 `received_at_us`」。
   - **gate 只在 `status == "live"` 且四值 `> 0` 时使用该快照**；其余一律按该侧无效处理。
   - **读模型在 `status != "live"` 时价格与数量一律输出 `—`**，只展示 `status` 与 `received_at_us`；保留值仅供「最后接收时间」定位，绝不得被涂成当前盘口（设计 §8.4）。
3. **contractSize**：仅用于断言普通可达 symbol `== 1`；不等于 1 或读不到 → 该 key 永不产出 `live` 快照。**禁止**用 contractSize 做任何乘法换算，也不得用它识别 1000x（P0 实测 1000PEPE 同报 `1.0`）。
4. **ccxt 惰性 import**：`import ccxt.pro` 只能出现在 source_factory 的函数体内部。模块本身必须在**未安装 ccxt** 的环境里可 import、可被全部测试驱动。这是本轮能在「依赖尚未获批安装」的前提下完成实现与评审的唯一办法。
5. **线程边界**：进程级专用 event-loop 线程独占 CCXT clients 与 watcher；`latest` 由同步 worker 线程调用，必须在锁内返回不可变对象；`subscribe`/`release`/`close` 从同步线程线程安全地提交到 event loop，调用方不得 `await`；`close` 先 cancel watcher、再 close clients、最后 join 线程，且幂等。
6. **`on_change` 回调**：每次快照更新、失效、重连时调用一次，参数为 MarketKey；在 event-loop 线程上执行，实现必须是「只置位并 notify，不做阻塞工作」。

### 4.2 Gate 领域与持久化

#### 4.2.1 `backend/hedge_open_tasks/domain.py`（纯函数，零 I/O，不 import 任何 services 层模块）

```python
SMOOTH_GATE_WINDOW_US = 5 * 60 * 1_000_000
SMOOTH_COVERAGE_MIN   = Decimal("0.80")
PASS_REASON_MARKET  = "market"
PASS_REASON_TIMEOUT = "timeout"
PASS_REASON_MANUAL  = "manual"

def validate_slippage_threshold_pct(value) -> str: ...
# 接受 "-12" / "0" / "0.05" / ".05"（归一 "0.05"）；最多两位小数；
# 拒绝空、None、非字符串、NaN、Infinity、科学记数、含 "%"、超两位小数。
# 返回规范化的两位小数十进制字符串（"0.05"、"-0.10"、"0.00"）。

class L1Quote(NamedTuple):        # 一侧的一档，四个 Decimal，均 > 0
    bid: Decimal; bid_qty: Decimal; ask: Decimal; ask_qty: Decimal

class SmoothGateEval(NamedTuple):
    spread_pct: Decimal | None
    spread_pass: bool
    spot_coverage: Decimal | None
    perp_coverage: Decimal | None
    coverage_pass: bool
    market_pass: bool             # spread_pass and coverage_pass
    wait_reason: str              # 中文等待原因，UI 直显

def evaluate_smooth_gate(direction: str, threshold_pct: Decimal, q_common: Decimal,
                         spot: L1Quote | None, perp: L1Quote | None) -> SmoothGateEval: ...
```

开单率**必须直接调用** `backend/domain/snapshot.py::compute_opening_spread_pct`（`snapshot.py:613`，已含 Decimal、`ROUND_HALF_UP`、两位量化、负零归一、分母 `<= 0` 返回 `None`），禁止复制公式。forward 取 `compute_opening_spread_pct(perp.bid, spot.ask)`，reverse 取 `compute_opening_spread_pct(spot.bid, perp.ask)`；返回字符串解析回 `Decimal` 后与 `threshold_pct` 严格 `>`。覆盖率分母恒为 `task.q_common`，forward 用 `spot.ask_qty`/`perp.bid_qty`，reverse 用 `spot.bid_qty`/`perp.ask_qty`。任一侧为 `None` → `market_pass = False`。

`service.py` 负责把 `BookTickerSnapshot`（`status == "live"` 且四值 `> 0`）映射成 `L1Quote`，其余映射为 `None`；`domain.py` 因此不 import provider，任务包的零传输依赖边界不变。

#### 4.2.2 `backend/hedge_open_tasks/store.py` 的 schema 与事务方法

```python
# 迁移（_migrate，store.py:413 的 additions 元组内追加）
hedge_open_task    += slippage_threshold_pct TEXT
                      smooth_gate_seq INTEGER
                      smooth_gate_started_at_us INTEGER
                      smooth_gate_force_requested INTEGER NOT NULL DEFAULT 0
hedge_open_attempt += smooth_pass_reason TEXT

def open_smooth_gate(task_id, gate_seq, started_at_us) -> dict | None
def force_smooth_gate(task_id, gate_seq, now_us) -> dict | None
def clear_smooth_gate(task_id, now_us) -> None
def prepare_attempt(..., *, expected_gate_seq: int | None = None,
                    smooth_pass_reason: str | None = None) -> dict | None
```

1. `open_smooth_gate` 在一个事务内复核：task 存在、`task_type == open`、`mode == smooth`、`status == running`、`scheduled_attempt_count < target_n`、无 `pair_outcome IS NULL` 的 attempt、且（无活动 gate 或活动 gate 的 seq 等于入参）。不满足返回 `None`。幂等：同 seq 重复调用不重置 `started_at_us`，也不清 force flag。
2. `force_smooth_gate` 在一个事务内复核同一组条件 + `smooth_gate_seq == gate_seq`，置 `smooth_gate_force_requested = 1`。不满足返回 `None`（service 映射为 409）。重复调用幂等，不累计次数。
3. `prepare_attempt` **最小扩参，不新增并行原子方法**：在其现有事务（`store.py:888`）内追加复核——若 `task.mode == smooth`，则 `expected_gate_seq` 必须非空且等于当前 `smooth_gate_seq`，否则返回 `None`；成功时在同一事务里写 `attempt.smooth_pass_reason`、递增 `scheduled_attempt_count`、清空三个 gate 列。
   - 判定理由：设计 §6.1 要求 gate 复核与 attempt 写入同事务，而周期分配、client id、请求指纹已在该事务内；另起方法会复制这段事务或引入两段式提交。若实现中发现该判断与代码事实冲突，停下报告，不得自行改成新方法。
   - **fail-closed 兜底**：`mode == smooth` 且 `expected_gate_seq is None` → 返回 `None`。这一条把 dry-run tick（`service.py:2438` `list_eligible_tasks` → `_dispatch_one_for_task`）、非 live 的 `post_fill_once`（`service.py:1054`）等所有旁路入口一次性关死。
   - immediate 任务两参数均为 `None` → 行为与今天逐字节一致，现有测试不需改。
4. 不存在独立的 `consumed` 状态；不在 task 上保存「最近一次 pass_reason」（冻结不变量 §4.1/§4.2）。

#### 4.2.3 `running → 非 running` 的全部写路径（R2 的正式修正）

**上一版「`set_task_status` 是全仓状态迁移唯一收口」的结论是错的，已删除。** 以下是对 `backend/hedge_open_tasks/store.py` 的穷举扫描结果（`grep -n "SET status\|status = ?"`，四处 `UPDATE hedge_open_task ... status`，无第五处；任务行的初始 status 由 `create_task` 的 INSERT 写入，不是状态迁移）：

| # | 写路径 | UPDATE 行 | 写入形态 | 触发者 | gate 处理 |
|---|---|---|---|---|---|
| 1 | `set_task_status`（`store.py:774`） | `789`（→running）/ `796`（其余） | **无条件** UPDATE，`rowcount == 0` 表示任务不存在 | Human start/pause/delete（`service.py:1010/1027/1039`）、fill-once/fill-all 置 running（`1051/1064`）、worker 判 done（`1676/1914`） | 新状态**不是** `running` 且 `rowcount > 0` 时，在**同一事务**内清空三列 |
| 2 | `pause_task`（`store.py:1964`） | `1991` | **条件** UPDATE：`WHERE id = ? AND status IN (running, paused)`；未命中返回 `(None, False)` | worker 确认 429/Retry-After 或余额/保证金不足（`service.py:2293`，经 `_pause_task_local`@`2274`） | **仅在 `rowcount > 0` 时**于同一事务内清空三列 |
| 3 | `stop_task_fatal`（`store.py:1928`） | `1950` | **条件** UPDATE：同上 `WHERE`；未命中返回 `None` | fatal preflight 事实（`service.py:2608`，经 `_stop_task_fatal_preflight`@`2601`） | **仅在 `rowcount > 0` 时**于同一事务内清空三列 |
| 4 | `_apply_task_counters`（`store.py:1046`，UPDATE 在 `1192`） | `1192` | 结算写：`status` 可被 `resolve_status_after_attempt` 置为 `paused`（连续提交失败达阈值）或 `done`（R2-F1：计划次数用尽） | `resolve_attempt`（`1264`）、`finalize_attempt`（`1416`）、`settle_attempt_no_counters`（`1483`） | **不清理**，理由与回归见下 |

**路径 2、3 是真实缺口**（评审 R2 成立）：二者由 `_dispatch_one_for_task` 在 `prepare_attempt`（`service.py:2889`）**之前**调用（`service.py:2745` 的 `_stop_task_fatal_preflight`，`2769/2785/2812/2834` 等 `_pause_task_local`），此时 gate 尚未被消费，三列仍在。若不清，Human 之后 Start 恢复时 `open_smooth_gate` 会因同 seq 而幂等复用旧 gate、沿用已过期的 deadline，立刻形成 `timeout` 候选，跳过本应重开的完整 5 分钟窗口——违反设计 §6.1 与验收矩阵第 11 条。

**为什么条件写必须「仅在命中时清」**：路径 2、3 的 `WHERE` 带状态条件，正是为了防止并发 `post_delete` / target-`done` 期间被过期的 worker 快照复活（代码注释里的 `fix-runtime-seam-scan` 家族）。若在未命中时仍清 gate，就会去动一个本轮并未迁移状态的任务——既可能误清他人正在等待的 gate，也把「未命中即完全不写」的既有语义破坏掉。

**为什么路径 4 不需要清理（不变量论证 + 断言型回归）**：`_apply_task_counters` 只在 attempt 结算时运行，而此时三列必然已为 `NULL`——`prepare_attempt` 在同一事务里创建 attempt 的同时清空了它们（§4.2.2 第 3 条），且在该 attempt 的 `pair_outcome` 落定前，`open_smooth_gate` 的「无未决 pair」条件与 `force_smooth_gate` 的「`smooth_gate_seq == gate_seq`」条件都不可能成立（`NULL` 永不匹配），因此结算前无法重新出现活动 gate。在这里加清理是无法触发的死代码；改为用一条断言型回归钉住该不变量（见 §4.2.4 第 4 条）。**若将来放宽「同一 task 有未决 pair 时不得开新 gate」这一 A-9 顺序性约束，本条豁免立即失效，必须重新评估路径 4。**

`clear_smooth_gate` 的保留用途**仅剩一种**：任务仍是 `running` 但 Start gate 被关闭（`service.py:1644` 的 `_worker_round` 退出分支）。此时没有任何状态迁移发生，四条路径都不会触发，必须由 worker 显式调用。除此之外不得再有第二个调用点。

#### 4.2.4 R2 的确定性回归（必须全部可跑，禁止依赖真实网络/时钟）

1. **系统 pause 清 gate + resume 重开完整窗口**：smooth task 有活动 gate（`seq=N`，`force_requested=1`）→ `pause_task` 命中 → 三列全部为 `NULL`；Human `post_start` 后 worker 为**同一未调度 seq N** 调 `open_smooth_gate`，断言 `started_at_us` 是新值、`deadline` 是新的完整 5 分钟、`force_requested == False`。
2. **fatal stop 清 gate**：同上初态 → `stop_task_fatal` 命中 → 三列全部为 `NULL`。
3. **`set_task_status(非 running)` 清 gate**：分别对 `paused`、`deleted`、`done` 各断言一次三列清空；`set_task_status(running)` **不得**清空（进程重启续原 gate 依赖这一点）。
4. **结算路径不误清、不复活**：smooth pair 走完 `prepare_attempt` → executor → `resolve_attempt`，断言结算前后三列恒为 `NULL`（路径 4 的不变量守卫）。
5. **条件 UPDATE 未命中时不误清（必须用非空 sentinel，禁止空断言）**：先把 task 置为 `deleted` / `done` / `stopped` 终态，再由 test fixture 在**同一个隔离 test DB** 中对该 task 行**直接写入三个明确非空 sentinel**（`smooth_gate_seq = 777`、`smooth_gate_started_at_us = 123456789`、`smooth_gate_force_requested = 1`）；随后分别调用 `pause_task` 与 `stop_task_fatal`，断言：条件 UPDATE 未命中（`pause_task` 返回 `(None, False)`、`stop_task_fatal` 返回 `None`）、`status` 未被改写、且三个 sentinel **逐值保持**（`777` / `123456789` / `1`）。
   - 这里的直接 SQL 只用于构造一个正常 API 不会产生的观察态（终态任务 + 非空 gate 列），目的是让「miss 分支完全不写 gate 列」成为可观测事实：若实现把清理写在条件 UPDATE 之外（无条件清），sentinel 会变成 `NULL`，用例立刻红。
   - **不得以三列本来就是 `NULL` 来构造断言**：走 `set_task_status` 进入终态会按 §4.2.3 路径 1 先清空三列，此时「保持调用前的值」等于断言 `NULL` 仍是 `NULL`，无条件清的错误实现也照样通过，抓不到任何回归。
6. **immediate 零行为变化**：immediate task 走 pause/stop/settle 全部路径，断言与本次改动前逐字段一致，且三列恒为 `NULL`/默认值。

### 4.3 Service / API 读写模型

```text
POST /api/hedge-open-tasks
  body += slippage_threshold_pct: string   # mode=smooth 必填，其余模式禁止出现
  mode=smooth 仅允许 task_type=open；close+smooth 一律 400
  provider 不可用时 mode=smooth 返回 400 smooth_market_unavailable（中文原因）

GET  /api/hedge-open-tasks（task_to_doc，service.py:161）
  += slippage_threshold_pct: string | null
     smooth_gate_seq: int | null
     smooth_gate_started_at_us: int | null
     smooth_gate_deadline_at_us: int | null      # started_at + 5min 派生，不落库
     smooth_gate_force_requested: bool
     smooth_gate_state: "none" | "waiting" | "forced"

POST /api/hedge-open-tasks/{id}/fill-once
  smooth：body { "gate_seq": <int> } 必填 → force_smooth_gate → ensure_worker → 唤醒
          gate 不活动/seq 不符/非 running/已达目标/有在途 pair → 409，不改 task
  immediate 及其他模式：行为一字不改（不带 body 亦可）

POST /api/hedge-open-tasks/{id}/fill-all
  smooth → 409 smooth_fill_all_unsupported；其他模式不变

GET  /api/hedge-open-logs?task_id=...（service.py:1103 的 task_id 分支）
  += smooth_market: {
       spot / perp: {status, received_at_us, bid, bid_qty, ask, ask_qty} | null,
       forward_spread_pct / reverse_spread_pct: string | null,
       spot_coverage_pct / perp_coverage_pct: string | null,
       spread_pass / coverage_pass / gate_pass: bool,
       wait_reason: string
     }
```

`server.py` 的唯一改动：`_hedge_open_action`（`server.py:1271`）当前对全部动作 `_drain_hedge_body()` 后只传 `task_id`。改为**仅 `fill-once`** 读取可选 JSON body 并透传（沿用既有 `_read_hedge_body(required=False)` 与 `BODY_MAX_BYTES` 上限），其余动作保持 drain 语义不变。

实现要点（每条对应设计条目，不得自行扩展）：

1. **等待与唤醒**（设计 §6.2）：每 task 一个 `threading.Condition` + 单调 `wake_version`。worker 在锁内记录版本号，锁外重读 task/gate/Start gate/两侧快照，未通过则 `wait_for(版本已变, timeout=剩余秒数)`。**不得复用 `_stop_events`**——它只在 `stop()`（`service.py:588`）被 set，而 `post_pause`/`post_delete` 明确不打断 worker（`service.py:1023-1027` 的 Review-1 r3 P1-2 结论），复用会破坏既有 drain 语义。
2. **唤醒源恰好六个**：provider `on_change`、`force_smooth_gate` 成功、pause/delete、Start gate 变化、`service.stop()`、deadline 到期。
3. **绝不忙循环**：`_run_task_worker`（`service.py:1513`）只在有未终态 legs 时 pace，gate 等待发生在无 legs 时，必须由 condition 阻塞承担。
4. **`post_fill_once` 的 mode 分流发生在 live/offline 分支之前**；smooth 分支持久化 force 后幂等 `ensure_worker` 并 notify，永不直接 dispatch。
5. **Start gate 关闭**：`_worker_round` 的该退出分支显式调用 `clear_smooth_gate`（§4.2.3 的唯一保留用途）。
6. **provider 缺失的两种形态必须分清（O3）**：
   - **生产/dry-run**：`server.py` 组合根构造 provider；`import ccxt.pro` 失败时注入 `None` 并打印中文告警。此时 `mode=smooth` 创建返回 400 `smooth_market_unavailable`；已存在的 smooth task 市场条件恒不通过，**timeout 与 manual 放行仍可用**（fail-closed，不是功能关停）。
   - **测试**：注入 fake provider，smooth task 可正常创建并驱动 gate 全部分支。因此「dry-run 下 smooth 建不出来」是**预期行为**，不得被当成回归失败，也不得为此在生产路径放宽校验。
7. **解除冻结必须与 gate 同一交付**：`service.py:761` 的 `mode != immediate` 拒绝只能在本交付内解除，不得先开入口后补门。

### 4.4 前端真实接线

- 市场页平滑按钮解除 disabled（`index.html:5622`）+ signed threshold 输入与 `%`；移除 `smooth_next_round` 短路（`index.html:5777`/`5846`）。
- 任务卡显示 threshold 与动态盘口块：复用现有百分比 formatter 与正负颜色规则，**不新增任何 timer**（搭载 `EXECUTION_POLL_MS = 2000` 的既有展开日志读链）。
- `成交1次`：点击时先走同源日志 GET 取当前 `smooth_gate_seq` 再 POST；无活动 seq 或非 running 时按钮禁用。
- `showFillAll`（`index.html:6018`）对 smooth 关闭。
- `status != "live"` 的一侧价格与数量显示 `—` 并标明连接状态，不得把保留值涂成当前盘口。

## 5. P0 未证事项 → 可执行验收（全部用 fake async source，禁止连真实 WS）

真实 CCXT 连通性已由 P0 覆盖，重复连接不产生新证据且超出授权。fake source 必须能按脚本抛异常、延迟、断流、重放。

| # | P0 未证事项 | 可执行验收（用例语义） |
|---|---|---|
| 1 | watcher 异常/重连的 generation 失效 | fake source 抛异常 → 该 key 立即不再产出 `live`；source 恢复后首条合法消息前仍不可用；恢复后 `generation` 严格递增，旧 generation 的值不被复用 |
| 2 | 延迟消费者隔离 | spot source 阻塞 N 秒不产出，perp source 持续更新 → perp 的更新计数持续增长、`latest(perp)` 持续刷新；spot 阻塞不阻塞 provider 任何公共方法 |
| 3 | 同 symbol 共享与引用计数 | 同一 key `subscribe` 两次 → source_factory 只被调用一次；`release` 一次后仍 `live` |
| 4 | 最后一个引用释放才 cancel | 上例再 `release` → watcher 被 cancel、不再 `live`；再次 `subscribe` 新建 watcher 且 generation 递增 |
| 5 | 多 symbol 行为 | 三个不同 key（spot A、swap A、spot B）并存，各自独立更新与失效，互不串扰 |
| 6 | close/join 后零残留 | `close()` 后 event-loop 线程已 join、`asyncio.all_tasks` 中无 provider 创建的 task、重复 `close()` 幂等不抛、`latest` 返回 `None` |
| 7 | raw 字段缺失/畸形 | `info` 缺 `b`/`B`/`a`/`A` 任一，或值为 `""`/`"0"`/`"abc"`/负数 → 该侧不产出 `live`，不抛异常，不产生半填充快照 |
| 8 | normalized float 不得进入 | 断言快照四字段类型为 `Decimal`；用带尾零的 raw（`"7.48647000"`）驱动，断言 `format(snap.bid_qty, 'f') == "7.48647000"`（float 路径会退化为 `7.48647`，该断言即 float 探测器） |
| 9 | spot 本地时间 | spot 源无 `E/T` → `exchange_ts_ms is None` 且 `received_at_us > 0`；perp 源有 `E` → `exchange_ts_ms == raw E` |
| 10 | contractSize 非 1 / 未知 | `contractSize` 为 `2`、`None`、缺失三种 → 该 key 永不产出 `live`，且不做任何乘法换算 |
| 11 | 1000x fail-closed | `create_task(open, mode=smooth)` 对乘数币仍返回 `multiplier_contract_unsupported`；provider 的 `contractSize == 1` 断言不构成任何解除路径 |

## 6. 唯一运行时依赖清单

| 项 | 决定 |
|---|---|
| 文件名 | `requirements.txt`（仓库根，新建） |
| 内容 | 仅 `ccxt==4.5.64` 一行 + 一句中文注释说明「运行时依赖；开发工具（pytest/mypy/ruff）不在此清单」 |
| 维护者 | 本交付由当前获 dispatch 的 Implementer 创建；此后任何依赖变更也只能由获专门 dispatch 的 Implementer 在该交付中修改。Bookkeeper 只核验和记账，**绝不修改 `requirements.txt`**。生产安装仍须 Human 单独授权 |
| 事实依据 | 仓库当前**没有任何依赖清单**（无 `requirements*.txt` / `pyproject.toml` / `setup.py`），生产代码全部 stdlib（`backend/adapters/binance_public.py:13` 用 `urllib.request`）；`.venv` 内只有 pytest/mypy/ruff/jsonschema 等开发校验工具。CCXT 将是本仓第一个运行时依赖 |
| 安装边界 | **本交付不得执行 `pip install`**。全部测试必须在未安装 ccxt 的当前 `.venv` 下全绿（靠 §4.1 第 4 条的惰性 import 与 fake source 实现） |
| 生产安装 | 只有在 Review-1 + Review-2 ACCEPT 且 Human 明确授权后，才允许装入正在跑真钱的 `.venv`；安装属于 `AGENTS.md` §3 的外部副作用类动作，需单独授权，不被任何 ACCEPT 隐含 |
| 回滚 | 安装前 `.venv/bin/pip freeze > /tmp/venv-before-ccxt.txt`；回滚为 `pip uninstall ccxt` + 比对 freeze 差异。因为对 ccxt 是惰性 import 且缺失时 fail-closed，卸载后服务仍可启动，只是 smooth 创建被拒——回滚不需要回退代码 |

## 7. 交付、固定 SHA 与回归矩阵

### 7.1 交付流程（无跨分支集成，R3 随之关闭）

1. Implementer 在唯一 worktree/分支上完成 §3.4 的四个 checkpoint，跑完 §3.5 全部命令，写唯一 handoff，做**一个**本地 delivery commit（不 push、不合并）。
2. Bookkeeper 只做记账与核验：核对 handoff（源区块 SHA-256、task/stage/model/revision）、`git rev-parse` 取得 `delivery_sha`、复跑验收命令、把 `current_task.state` 推进到 `verified`、准备 Review-1 dispatch。
   **Bookkeeper 不建分支、不 cherry-pick、不 merge、不合出交付**——本轮不存在需要集成的第二条分支。
3. 评审区间固定为 `base_sha..delivery_sha`（`base_sha` 即 §3.1 的唯一输入提交），Review-1 与 Review-2 只看这一个区间。
4. 合并到 `main`、装依赖、重启服务、实盘验证，均需 Human 逐项单独授权。

### 7.2 全量确定性回归矩阵（封存前必须全部有输出留档）

| # | 命令 | 期望 |
|---|---|---|
| R1 | `.venv/bin/python -m pytest backend/tests -q` | 全绿；基线约 1601 项，新增用例只增不减 |
| R2 | `.venv/bin/python -m pytest backend/tests/test_hedge_purity.py -q` | 绿（provider 未污染任务包的注入边界与零网络证明） |
| R3 | `.venv/bin/python -m pytest backend/tests/test_hedge_cycle_core.py backend/tests/test_hedge_cycle_close.py -q` | 绿且这两个文件零 diff（`prepare_attempt` 扩参未撞坏周期分配/平仓链） |
| R4 | `.venv/bin/python -m pytest backend/tests/test_hedge_task_local.py backend/tests/test_hedge_review2_regressions.py -q` | 绿且零 diff（worker 生命周期与既有 review-2 回归） |
| R5 | `.venv/bin/python -m pytest backend/tests/test_live_hedge_executor.py backend/tests/test_hedge_executor.py -q` | 绿且**这两个文件零 diff**（实盘两腿提交/查单/结算未被触碰） |
| R6 | `node frontend/self-check.js` | 末行「全部自检通过」、退出码 0、无新增 timer |
| R7 | `.venv/bin/python -m pytest backend/tests/test_frontend_field_binding.py -q` | 绿 |
| R8 | `git diff --check` | 无输出 |
| R9 | `git diff --stat <base_sha>..<delivery_sha>` | 变更文件集 ⊆ §3.2 的 Allowed Files，无 §3.3 中的任何文件 |
| R10 | 全流程在**未安装 ccxt** 的 `.venv` 下执行 | R1–R8 仍全绿 |

设计 §13 的 15 条验收矩阵落到用例：1/2/3 → `domain` + 前端输入；4 → `evaluate_smooth_gate` + 1000x 建卡拒绝；5/6/14 → provider（§5 的 1–10）；7/8/9/10/11/12/15 → worker/API（含 §4.2.4 全部六条）；13 → 前端。

## 8. Human 启动文稿草案（单终端，INACTIVE）

> **现在不可用。** `<<...>>` 占位符必须由 Bookkeeper 在**定向计划复核 ACCEPT 且 Human 授权实现之后**，用真实 worktree 路径、分支、`git rev-parse` 的 base SHA、status revision 与 dispatch 路径替换，并在同一轮创建对应 dispatch 文件。未替换前粘贴到终端即为无效启动。

```text
你现在执行平滑开单 V1 的全栈实现任务（provider + gate/store + worker/API + 前端真实接线）。
模型要求：gpt-5.6-sol，reasoning xhigh，provider openai。
工作目录：<<WORKTREE>>（git 分支 <<BRANCH>>，从 <<BASE_SHA>> 起）。
按 AGENTS.md 顺序启动并核对：stage_id=2026-08-12-smooth-open-orders-v1，
task_id=smooth-open-v1-fullstack-gpt56sol-xhigh，target_model=gpt-5.6-sol，provider=openai，
status revision=<<REVISION>>，base_sha=<<BASE_SHA>>。
严格执行 <<DISPATCH_PATH>>；产品与资金语义以 docs/planning/smooth-open-orders-v1.md 为准，
开发边界与契约以 docs/planning/smooth-open-orders-v1-development-checklist.md 为准。

只允许修改该 dispatch 的 Allowed Files。禁止改动：live_hedge_executor.py、
hedge_open_live_client.py、hedge_preflight_provider.py、hedge_open_tasks/executor.py、
scheduler.py、backend/domain/snapshot.py，以及 status.json、ACTIVE.json、PROJECT_STATE.md。
禁止：安装依赖（包括 pip install ccxt）、连接任何 WebSocket 或 HTTP 行情/账户/订单接口、
读取凭证、启动或重启服务、真实下单、push、merge、部署。

实现顺序（同一任务内的 checkpoint，不是四个任务）：先 provider 与依赖清单，再 gate 域与持久化，
再 worker/API 接线，最后前端真实接线；每个 checkpoint 跑对应测试，未绿不得进入下一个。
gate 等待必须用独立 Condition + wake_version，禁止忙循环，禁止复用 _stop_events。
全部回归使用 fake provider、fake clock、record executor，零真实订单、零网络，
且必须在未安装 ccxt 的 .venv 下通过。

完成后跑清单 §3.5 的全部验收命令、node frontend/self-check.js 与 git diff --check，
写唯一 handoff（reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/
smooth-open-v1-fullstack-gpt56sol-xhigh.handoff.md），
做一个本地 delivery commit（不 push），可把自己的 status 从 dispatched 改为 reported
（不得写 verified、不得选择后继模型），返回 [TASK_RESULT v2] 后停止。
```

## 9. 定向计划复核请求（copy-ready）

> 这是**针对本轮改动的定向复核**，不是重做一轮大而全设计评审。因 `AGENTS.md` §8 对 HIGH_RISK 的实现前计划评审门仍生效，结论仍须 `ACCEPT | REWORK`。建议仍由 `deepseek-v4-pro`（provider `deepseek`，持有 R1/R2/R3 上下文）执行；任何 provider ≠ `anthropic` 的只读评审者均可。

```text
你现在执行平滑开单 V1 计划返修的定向只读复核。这不是 Review-1/Review-2，也不是重做一轮
完整设计评审。不授权实现、依赖安装、服务控制、下单或部署。你必须只读：除自己的 handoff 外
不改任何文件，不改 status.json/ACTIVE.json/PROJECT_STATE.md，不创建 worktree/分支，
不装依赖，不连接任何行情/账户/订单接口，不启动服务。

按 AGENTS.md 顺序启动，核对 stage_id=2026-08-12-smooth-open-orders-v1 与 status.json 的
revision 与固定 base_sha..delivery_sha。
必读，按此顺序：
  1. reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-formal-plan-review-deepseek-v4-pro.handoff.md（上一轮 REWORK 的 R1/R2/R3 与 O1-O3）
  2. docs/planning/smooth-open-orders-v1-development-checklist.md（本轮受审的返修稿）
  3. docs/planning/smooth-open-orders-v1.md（Human 冻结的产品与资金语义）
  4. 需要核实事实时只读：backend/hedge_open_tasks/store.py（set_task_status、pause_task、
     stop_task_fatal、_apply_task_counters、prepare_attempt）、backend/hedge_open_tasks/service.py
     （_pause_task_local、_stop_task_fatal_preflight、_dispatch_one_for_task、_worker_round）、
     backend/tests/test_hedge_purity.py

只回答以下三组问题，不要扩展到已被上一轮接受的部分：

 一、R1/R2/R3 是否真的关闭？
   R1：改成单 Implementer、单 worktree、单 dispatch、单 current_task、单 handoff 之后，
       是否还存在任何「用 handoff 替代在途状态」或「同时存在两个在途 implementation task」的残留？
       是否新增了状态数组、并行 ledger 或新 schema？
   R2：§4.2.3 的四条 running → 非 running 写路径枚举是否完整、行号与函数是否与固定基线一致？
       「三条在命中时于同一事务清 gate、第四条以不变量豁免并配断言回归」是否成立？
       条件 UPDATE 未命中时不清 gate 的理由是否正确？§4.2.4 的六条回归是否覆盖了 R2 的实际影响？
   R3：取消跨分支集成后，Bookkeeper 是否已被限制为只核验/记账/固定 SHA/备 dispatch，
       不再出现建分支、cherry-pick 或合出交付？是否还存在双 owner 表述？

 二、新的单任务方案本身是否有缺口？
   Allowed Files 联集是否覆盖了 provider、gate/store、worker/API、前端与依赖清单的完整必要范围？
   禁止文件清单是否足以保证实盘下单/查单/结算行为零改动？
   §3.5 与 §7.2 的验收命令是否足以证明交付，且不依赖真实网络、真实时钟或已安装的 ccxt？
   四个内部 checkpoint 的依赖顺序是否与真实调用链一致？

 三、Human 冻结语义是否有回归？
   bookTicker 一档、signed threshold 严格 >、两腿各 80%、每轮 5 分钟、timeout 回退既有立即链、
   成交1次 仅放行当前 gate、两腿异步提交并同步等返回、单腿/查单/结算复用立即链——
   是否在返修中被削弱、改写或悄悄放宽？O1/O2/O3 是否已按事实关闭？

评审若提出新假设场景，必须满足 AGENTS.md §1 Scenario Admission：给出当前代码路径、
官方契约或具体并发/单位证据，说明对本交付的实际影响，以及为何必须本轮处理。
只对偏好不同、Human 已明确接受的市场风险或未来扩展，不判阻塞。

返回 [TASK_RESULT v2]，并给出
  评审结论: ACCEPT（接受） | REWORK（返工）
  问题记录: <path | none>
  修复要求: <path | none>
REWORK 必须逐条给出可执行的修复要求。ACCEPT 不授权启动服务、安装依赖或实盘下单。
```

## 10. 角色路由与记账（供 Bookkeeper 使用，不在本任务内执行）

- 实现者：`gpt-5.6-sol` / `xhigh` / provider `openai`（唯一）。
- 定向计划复核：provider ≠ `anthropic`（本返修稿作者）；建议 `deepseek`（持有上一轮发现上下文）。
- Review-1：provider 必须 ≠ 实现者 provider（`openai`）；候选 `moonshot`（kimi）、`xai`（grok）、`deepseek`、`anthropic`，与计划复核者错开更佳。
- Review-2：必须 ≠ 交付区间内全部实现/修复作者的 provider；`sonnet5`（anthropic）符合默认规则（`agents/roles.md` Review-2，DEC-2026-08-04-001）。本细拆与返修由 anthropic 的 Opus 5 完成，属设计参与而非实现，须在评审记录中披露。
- `rework_count`：本轮为实现前计划评审 `REWORK` 后的 Planner 改稿，按 `AGENTS.md` §8 **不递增**（`status.json` 当前为 `0`）。实现开始后，任何因评审发现而返工的再交付才递增。
- 风险等级：HIGH_RISK（订单触发时机 + 次数硬上限 + 实盘资金路径），Review-1 + Review-2 双轮不可省。

## 11. 当前停止线

在定向计划复核 ACCEPT 且 Human 授权实现前：不创建 worktree/分支/stage 目录，不安装 CCXT 到任何环境（P0 已完成，无需重复），不解除 `mode=smooth` 后端拒绝或前端 disabled，不接 worker/executor，不改 `status.json`。

ACCEPT 之后仍需 Human 单独授权的动作：把 `ccxt==4.5.64` 装入生产 `.venv`、重启服务、任何真实公共 WS 连通验证、合并到 `main`、部署、任何实盘下单。

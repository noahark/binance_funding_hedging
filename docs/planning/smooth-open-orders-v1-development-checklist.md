# 平滑开单 V1 开发清单（单 Implementer 活动方案）

状态：**上一轮 F1 修复已过 Review-1，Human 页面验收现已提出 D17–D19。本文 §15 是当前唯一活动的窄返修草案；先做跨 provider 计划复核，ACCEPT 后才准备原 Implementer 的实现 dispatch。Human 已允许继续返修且不受旧次数上限阻止，`rework_count` 当前保持 4；本次属于 Human 验收后的需求修订，不因写计划或计划复核自行递增。当前服务仍运行旧交付，本计划不授权改源码、重启、创建任务、下单、push、merge、部署或实盘。**

- 产品与资金语义唯一权威：`docs/planning/smooth-open-orders-v1.md`（本文不复制 gate 契约，只在必要处引用条目号）。三项接受风险与五项必修根因的权威描述在该文件 §16；本文只写怎么修和怎么验。
- P0 证据唯一权威：`docs/planning/ccxt-bookticker-recon-2026-08-13.md`。
- 已冻结的实现不变量：`reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/01-advisory-design-reviews.md` §4。
- 第一轮正式计划评审（`REWORK`）：`.../evidence/smooth-open-formal-plan-review-deepseek-v4-pro.handoff.md`；定向复核：`.../evidence/smooth-open-targeted-plan-rereview-deepseek-v4-pro.handoff.md`。
- 第一轮交付后的 Review-2 与 Bookkeeper 非接受核验（本轮返修的唯一事实来源）：`reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-review-2-sonnet5.handoff.md`（以 `Bookkeeper Verification` 的 `rejection_basis`、`reproducible_evidence`、`requirement_change` 为准）。
- §1–§14 保留第一轮、第二轮的规划与返修历史；**Human 页面验收后的当前活动草案只看 §15，计划复核边界只看 §16**。旧任务身份、旧停止线与旧行号不得覆盖 §15。
- 第一轮的行号基线为 `2e59023`，第二轮为 `bfb6337`；它们只服务历史证据。§15 以当前已提交计划范围为准，正式实现 dispatch 前由 Bookkeeper 重新固定 base 并要求 Implementer 按函数名核对。

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

> **仅适用于第一轮实现（已于 `24074b1` 交付完成）。** 第二轮返修的任务边界见 §12，其 dispatch 由 Bookkeeper 在窄复核 `ACCEPT` 后另行编写；本节保留为历史记录，不再作为启动依据。

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

## 10. 角色路由与记账（第一轮历史记录，不是当前记账权威）

- 实现者：`gpt-5.6-sol` / `xhigh` / provider `openai`（唯一）。
- 定向计划复核：provider ≠ `anthropic`（本返修稿作者）；建议 `deepseek`（持有上一轮发现上下文）。
- Review-1：provider 必须 ≠ 实现者 provider（`openai`）；候选 `moonshot`（kimi）、`xai`（grok）、`deepseek`、`anthropic`，与计划复核者错开更佳。
- Review-2：必须 ≠ 交付区间内全部实现/修复作者的 provider；`sonnet5`（anthropic）符合默认规则（`agents/roles.md` Review-2，DEC-2026-08-04-001）。本细拆与返修由 anthropic 的 Opus 5 完成，属设计参与而非实现，须在评审记录中披露。
- `rework_count`（第一轮历史事实）：当时属于实现前计划评审 `REWORK` 后的 Planner 改稿，按当时状态未递增（当时 `status.json` 为 `0`）。当前活动记账只看 §15.1 与 `status.json`，不得沿用本行。
- 风险等级：HIGH_RISK（订单触发时机 + 次数硬上限 + 实盘资金路径），Review-1 + Review-2 双轮不可省。

## 11. 当前停止线

（第一轮口径，已由 §14 取代；保留为历史记录。）在定向计划复核 ACCEPT 且 Human 授权实现前：不创建 worktree/分支/stage 目录，不安装 CCXT 到任何环境（P0 已完成，无需重复），不解除 `mode=smooth` 后端拒绝或前端 disabled，不接 worker/executor，不改 `status.json`。

ACCEPT 之后仍需 Human 单独授权的动作：把 `ccxt==4.5.64` 装入生产 `.venv`、重启服务、任何真实公共 WS 连通验证、合并到 `main`、部署、任何实盘下单。

---

## 12. 第二轮：单 Implementer 返修任务包（活动方案）

### 12.1 任务身份

| 项 | 值 |
|---|---|
| task_id | `smooth-open-v1-fix-gpt56sol-xhigh`（最终名以 Bookkeeper dispatch 为准） |
| target_model / reasoning / provider | `gpt-5.6-sol` / `xhigh` / `openai`（**与第一轮同一实现作者**，属修复而非新交付） |
| worktree / branch | 沿用第一轮的 `/Users/ark/Desktop/ai code/funding_hedging-smooth-v1` 与 `smooth/v1-fullstack`，**不新建** |
| 输入提交 | `<<BASE_SHA>>`（窄复核 ACCEPT 且 Human 完成返修上限选择后，由 Bookkeeper 用 `git rev-parse` 填入） |
| `rework_count` | **3**（两轮计划修复均发生在首轮交付之后；本轮已达 `AGENTS.md` §8 上限，未经 Human 选择不得再派发实现） |
| 交付 | 该分支上**一个**本地 fix commit，不 push、不合并 |
| handoff（唯一） | `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/<fix-task-id>.handoff.md` |

### 12.2 Allowed Files（只含根因所需）

- `backend/services/best_bid_ask_provider.py`（必修 1、4）
- `backend/hedge_open_tasks/domain.py`（必修 3）
- `backend/hedge_open_tasks/service.py`（必修 1 的订阅回滚、D15/D16）
- `backend/app/server.py`（必修 2）
- `frontend/index.html`、`frontend/self-check.js`（必修 5）
- 测试（逐项完整仓库相对路径，无占位式范围）：`backend/tests/test_best_bid_ask_provider.py`、`backend/tests/test_smooth_gate_worker.py`、`backend/tests/test_smooth_api.py`、`backend/tests/test_hedge_domain.py`、`backend/tests/test_frontend_field_binding.py`、`backend/tests/test_service_health.py`（必修 2 的组合根离线断言唯一落点：`_build_hedge_service` 的既有用例在该文件，见其 `test_disabled_hedge_mode_warns_on_stderr`）
- 唯一 fix handoff

**明确禁止改动**：`backend/hedge_open_tasks/store.py`、`executor.py`、`scheduler.py`、`backend/services/live_hedge_executor.py`、`hedge_open_live_client.py`、`hedge_preflight_provider.py`、`backend/domain/snapshot.py`、`requirements.txt`，以及 `status.json` / `ACTIVE.json` / `PROJECT_STATE.md` / 其他 stage 文件 / `.venv`。**本轮不动 store**：D15/D16 不需要新的持久化列或新状态机；若实现认为必须改 store，说明方案偏了，停下报告。

### 12.3 五项必修：根因、修复要求与确定性验收

行号基线 `bfb6337`，实现前重新 `grep` 确认。

**必修 1 — provider 并发冷启动僵尸订阅**

- 证据锚点：`best_bid_ask_provider.py::start`（对已 alive 线程直接 `return`，不等待 `_ready`）与 `service.py::_ensure_smooth_subscriptions`（先把 task_id 写进 `_smooth_subscriptions`，再逐个 `subscribe` 并 `except Exception: pass`）。
- 根因：两处各自把「登记」与「就绪」解耦——并发首次订阅可以在 loop 尚未 ready 时登记出一个没有 watcher 的可见状态，且单侧订阅异常被吞掉后不会回滚已登记的另一侧。
- 修复要求：① 所有并发 `start`/`subscribe` 调用者等待**同一个** ready 结果；loop 未 ready 或启动失败时不得登记任何可见 state（宁可抛出，让调用方按失败处理）；② 订阅两侧必须「**全部成功才记 task subscriptions**」，部分成功要 `release` 回滚，失败后允许下一轮重试。**不得**新增第二个 event loop、manager 或后台监督器。
- 确定性验收：多线程并发 `subscribe` 同一 key，断言只创建一个 watcher、无「已登记但无 watcher」中间态；构造单侧 `subscribe` 抛错，断言另一侧被 release 回滚、`_smooth_subscriptions` 无该 task、再次调用可成功。

**必修 2 — `APP_OFFLINE=true` 仍构造真实公共 WebSocket provider**

- 证据锚点：`server.py::_build_hedge_service` 只按 `default_source_available()` 决定是否构造 `BestBidAskProvider()`，未读 `config.offline`（`backend/config.py:40` / `APP_OFFLINE`）。
- 修复要求：`config.offline` 为真时组合根固定注入 `market_provider=None`，**即使已安装 ccxt** 也不得构造 provider、不得启动线程、不得 subscribe。非 offline 且 ccxt 缺失时的既有 400 行为**不变**。
- 确定性验收：组合根测试在 `offline=True` 下断言零构造、零线程、零订阅（例如以「未安装 ccxt 也能跑」的方式断言 `market_provider is None`），并保留一条非 offline + 无 ccxt 仍 400 的既有断言。

**必修 3 — 超长 signed 整数 threshold 逃逸为 500**

- 证据锚点：`domain.py::validate_slippage_threshold_pct` 的 `format(threshold.quantize(Decimal("0.01")), "f")`；`validate_slippage_threshold_pct("123456789012345678901234567890")` 抛 `decimal.InvalidOperation`（未被 `HedgeError` 包裹）。
- 修复要求：保持既有产品契约不变——**无产品最大值**、最多两位小数、拒绝科学记数/NaN/Infinity/`%`。用**最小字符串规范化**取代对任意长度输入的默认 context `quantize`（例如按正则捕获符号/整数/小数部分后补足两位并归一 `-0`），错误一律 400 而非 500。
- 确定性验收：domain 层与 API 层各一组回归，覆盖正负超长整数（如 30 位、100 位）、`-0`、`.05`、`0.055`、`1e-2`、`5%`、空值。断言分两类，不得混淆——
  - **合法但超长**（正负 30 位、100 位整数）：domain 正常规范化为两位小数字符串（如 `"-" + "9"*100` → `-999…9.00`，整数位逐字保留），且在注入 fake provider 的 API 创建路径上**被正常接受**（`201`），**不得**因长度返回 `400` 或 `500`；`-0` → `0.00`、`.05` → `0.05` 同属此类。
  - **格式非法**（`0.055` 超两位小数、`1e-2` 科学记数、`5%` 含百分号、空值/非字符串）：domain 与 API 均返回 `400`。
  - 这与 D5「不设置人为最小值或最大值」一致：本项修的是异常逃逸成 500，不是给阈值加长度上限。

**必修 4 — provider 持续异常/无效快照零等待热循环**

- 证据锚点：`best_bid_ask_provider.py::_watch` 的 `except` 分支与 `snapshot is None` 分支在重试前无任何 `await`；零网络 always-fail 假源实测 0.1 秒约 15 万次回调。
- 修复要求：两条失败分支在重试前都要有一个**简单固定最小等待**。**不得**发明指数退避、重试状态机或新配置项。等待必须可被 `close()` 立即打断（不得让 close 等满一个等待周期）。
- 确定性验收：用假源在短窗口内断言 `watch` 调用次数与 `on_change` 回调次数**有界**（例如 0.2 秒内不超过个位数），并断言等待期间调用 `close()` 能立即返回、线程 join 成功。

**必修 5 — 暂停/删除后仍在 drain/settle 时前端停止刷新展开日志**

- 证据锚点：`service.py::post_pause` / `post_delete` 明确不打断 worker（在途订单继续 drain/settle）；`frontend/index.html` 的展开日志刷新条件为 `task.status === 'running'`；`frontend/self-check.js:5615-5621` 目前**断言**「任务停止执行后须停止自动刷新日志」——这条把缺陷写成了预期。
- 修复要求：只要任务仍存在且日志已展开，就继续用共享 2 秒 tick / 既有 `loadHedgeTasks` 链取日志，使 paused/deleted/done/stopped 在 drain/settle 期间新增的 attempt 与腿状态最终可见。**不得新增 timer**；「收起后停止刷新」的既有断言保留；同步把上述 self-check 断言改成正确方向（非 running 且展开时**应当**继续请求）。
- 确定性验收：self-check 中构造 paused + 展开态，断言仍发出 `hedge-open-logs?task_id=` 请求；收起态仍断言不发。

### 12.4 新需求实现规格（设计 D15 / D16 / §6.5）

**D16 杠杆前移**

- 现状锚点：`service.py:3170-3185` 在 `_dispatch_one_for_task` 内、`live and task_type == OPEN and scheduled_attempt_count == 0` 时调用 `_set_leverage_before_open`（定义在 `service.py:3007`）。
- 修改：对 **live smooth** 任务，把这一次设置移到 `_worker_round` 的 smooth 分支（`service.py:1995` 调用 `_wait_for_smooth_gate` 之前），且必须早于 `_ensure_smooth_subscriptions`、`open_smooth_gate`（含已有 gate 恢复）与第一次 `_smooth_eval`。失败沿用现有 `PAUSE_REASON_LEVERAGE_SET_FAILED` 暂停与中文原因，此时零订阅、零 gate、零 attempt、零订单。
- `_dispatch_one_for_task` 对 smooth **不得**再设置杠杆；immediate 的位置与条件逐字不变。
- 首轮尚未产生 attempt 就因失败或进程重启重新进入执行入口时，可幂等重试，但仍必须在任何订阅/gate 之前；**不新增持久化列或新状态机**（`scheduled_attempt_count == 0` 已是判据）。

**D15 smooth-only 删除每轮 fresh preflight**

- 现状锚点：`_dispatch_one_for_task` 的 `if live:` 分支（`service.py:3083`）调用 `_resolve_fresh_preflight` 并据此得到 `q_common` / `position_side_mode` / `snapshot_record`；`else:` 分支（`service.py:3141`）已经在用 task 固化值。
- 修改：让 live **smooth** 走与 `else` 分支同源的固化值路径（`task["q_common"]` / `task["position_side_mode"]` / `task["preflight_snapshot"]`，route 取固化 snapshot 里的 `spot_route`），不调用 `HedgePreflightProvider.get_snapshot`。immediate 与 close 的 live 分支逐字不变。
- `service.py:3152-3165` 的 frozen/fresh route 一致性检查：对 smooth 两者同源、恒相等，等价于空转；实现可让它对 smooth 不参与（或保留为恒真），**但不得**改变 immediate 的该检查语义。
- 随后仍由既有 `prepare_attempt` 原子复核（task 状态、target、无在途 pair、当前 gate seq、pass reason）→ 既有 `_dispatch_live` 两腿异步提交 → 同步等返回 → 查单 → 结算 → 单腿/429/余额拒绝按既有原因暂停。**不复制 executor，不新建 smooth 下单实现。**
- 保留不动：create-task 的首次完整 preflight、固化数据、`regular_spot` forward 预划转、缺腿与 1000x 乘数合约拒绝。
- **明确接受的代价（不得包装成 fail-closed）**：等待期间余额/保证金、交易规则、position mode、下单限频、现货路由的变化不再被每轮预检拦截，可能双腿被拒或单腿成交；单腿由现有任务卡告警、任务暂停与 Human 人工核对收口。

**顺序型回归（必须有）**

用 spy 记录调用序列，断言：

```text
set_leverage → subscribe/open gate → market evaluation → prepare_attempt → dispatch
```

并断言 **market pass 之后** `set_leverage` 与 `HedgePreflightProvider.get_snapshot` 的调用计数**均不再增加**；`market` / `manual` / `timeout` 三种放行原因各覆盖一次。另需一条断言：gate 判定通过到 `_dispatch_live` 之间没有任何联网读取、交易所设置或 sleep（以 spy 计数 + 无 fake 网络桩被触达表达）。

### 12.5 三项接受风险：本轮不得修、不得重新纳入验收

设计 §16.1 的 L1（Start OFF/stop 与 reserve→dispatch 竞态）、L2（新 gate 可能少于完整 5 分钟）、L3（行情表重绘复位未提交的 threshold 输入）——**本轮既不修，也不作为验收失败项**。实现不得为它们新增准入锁、`stopping` 状态、store 侧 gate 复核、时钟获取点改动或前端 capture selector 扩展；复核者不得据此判 `REWORK`。

### 12.6 验收命令

```bash
.venv/bin/python -m pytest backend/tests/test_best_bid_ask_provider.py \
    backend/tests/test_smooth_gate_store.py backend/tests/test_smooth_gate_worker.py \
    backend/tests/test_smooth_api.py backend/tests/test_hedge_domain.py -q
.venv/bin/python -m pytest backend/tests/test_hedge_store.py backend/tests/test_hedge_service.py \
    backend/tests/test_hedge_api.py backend/tests/test_hedge_cycle_core.py \
    backend/tests/test_hedge_cycle_close.py backend/tests/test_hedge_task_local.py \
    backend/tests/test_hedge_review2_regressions.py backend/tests/test_hedge_leverage.py \
    backend/tests/test_hedge_purity.py -q
.venv/bin/python -m pytest backend/tests -q
node frontend/self-check.js
.venv/bin/python -m pytest backend/tests/test_frontend_field_binding.py -q
git diff --check
git diff --stat <base_sha>..<delivery_sha>
```

- 全后端仍以「不得出现相对固定 base 的**新增**失败」为准；已知唯一基线失败 `test_private_client.py::test_urlopen_only_in_designated_http_clients`（触发文件 `backend/services/public_ip_service.py`，引入提交早于 base、零 diff）保持同一测试、同一触发文件即为通过，**不得**修改这两个文件去「修绿」。
- 全部命令必须在**未安装 ccxt** 的 `.venv` 下通过。
- `git diff --stat` 的变更文件集必须 ⊆ §12.2 Allowed Files，且不含任何禁止文件；`backend/hedge_open_tasks/store.py`、executor、live client、preflight provider、`snapshot.py`、`requirements.txt` 必须零 diff。
- `test_hedge_leverage.py` 与 `test_hedge_cycle_*.py` 必须**不改一行**地通过——它们是 immediate 杠杆时机与结算链未被 D15/D16 波及的直接证据。

### 12.7 失败停止条件

- 任何一项要求改动 §12.2 禁止文件（尤其 `store.py`）才能通过 → 停，报 blocked。
- 顺序型回归无法在不接真实网络的前提下建立 → 停（说明 spy/fake 接缝设计错了）。
- 发现 L1/L2/L3 之外的新缺陷 → 记录在 handoff，**不顺手修**（`agents/developer-discipline.md` §2：验收通过即停止扩张）。

## 13. 窄范围计划复核请求（copy-ready）

> 只查本轮增量，不重做整体设计评审。目标 reviewer provider 必须 **非 `anthropic`**（本增量作者为 Opus 5）；建议 `deepseek`（持有前两轮上下文）或 `moonshot`。结论仍为 `ACCEPT | REWORK`。

```text
你现在执行平滑开单 V1 计划增量的窄范围只读复核。这不是 Review-1/Review-2，也不是重做整体设计
评审。不授权实现、依赖安装、联网、服务控制、下单、push、merge、部署或实盘。你必须只读：除自己的
handoff 外不改任何文件，不改 status.json/ACTIVE.json/PROJECT_STATE.md，不装依赖，不连接任何
行情/账户/订单接口，不启动服务。

按 AGENTS.md 顺序启动，核对 stage_id=2026-08-12-smooth-open-orders-v1 与 status.json。
必读，按此顺序：
  1. reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-review-2-sonnet5.handoff.md
     （以 Bookkeeper Verification 的 rejection_basis / reproducible_evidence / requirement_change 为准）
  2. docs/planning/smooth-open-orders-v1.md（重点：状态行、D8 更正、D15、D16、§6.4 更正、§6.5、§9、§13、§16）
  3. docs/planning/smooth-open-orders-v1-development-checklist.md（重点：§0 头部、§12、§13、§14）
  4. 需要核实事实时只读：backend/services/best_bid_ask_provider.py（start/subscribe/_watch）、
     backend/hedge_open_tasks/domain.py::validate_slippage_threshold_pct、
     backend/hedge_open_tasks/service.py（_ensure_smooth_subscriptions / _wait_for_smooth_gate /
     _worker_round 的 smooth 分支 / _dispatch_one_for_task 的 live 与 else 分支 / _set_leverage_before_open /
     post_pause / post_delete）、backend/app/server.py::_build_hedge_service、
     frontend/index.html 的展开日志刷新条件、frontend/self-check.js 现有相关断言

只回答以下四组问题：

 一、三项 Human 接受风险是否被错误地重新纳入？
     L1（Start OFF/stop 与 reserve→dispatch 竞态）、L2（新 gate 可能不足完整 5 分钟）、
     L3（行情表重绘复位未提交 threshold）——计划是否把它们写成了具名已知限制（含实际影响、临时
     操作方式、重开条件），而不是待修项或验收失败项？是否出现了为它们新增准入锁、stopping 状态、
     store 侧复核、时钟改动或前端 capture selector 扩展的要求？

 二、五项必修是否覆盖真实根因？
     provider 并发冷启动僵尸订阅、APP_OFFLINE 仍构造 provider、超长 signed 整数 threshold 逃逸、
     provider 持续失败零等待热循环、非 running 展开日志停止刷新——每项的证据锚点是否与固定基线的
     真实代码一致？修复要求是否解决根因而非表征？是否出现了被明确禁止的东西（第二个 event loop /
     manager / 监督器、指数退避、重试状态机、新配置项、新 timer）？确定性验收是否真的能在实现错误
     时变红（尤其：热循环的有界断言、离线零构造断言、合法超长整数被 API 接受为 201 / 格式非法值返回 400 的分组断言、paused
     展开仍刷新的断言）？

 三、smooth-only 删除每轮 fresh preflight 是否准确保留了必须保留的东西？
     create-task 首次完整 preflight、固化数据、regular_spot 预划转、缺腿/1000x 拒绝是否明确保留？
     immediate 的每轮 fresh preflight 与杠杆时机是否逐字不变？prepare_attempt 的原子复核（状态、
     target、无在途 pair、gate seq、pass reason）与两腿异步提交/查单/结算/单腿暂停链是否原样复用？
     被放弃的每轮拦截（余额、交易规则、position mode、限频、路由变化）是否被如实写成 Human 接受
     的代价，而**没有**被包装成 fail-closed？是否存在要求改 store / executor / live client /
     preflight provider 的隐含前提？

 四、smooth 杠杆是否严格前移、放行后是否再无联网？
     计划是否要求：live smooth 且 scheduled_attempt_count == 0 时，唯一一次杠杆设置发生在任何
     订阅、gate 建立/恢复与第一次滑点计算之前，失败时零订阅/零 gate/零 attempt/零订单？是否明确
     禁止把杠杆提前到建卡时、禁止在 _dispatch_one_for_task 内对 smooth 再设置？顺序型回归
     （set_leverage → subscribe/open gate → market evaluation → prepare → dispatch，且 market
     pass 后 leverage/preflight 调用计数不再增加）是否足以证明「gate 通过到两腿提交之间无任何
     联网读取、交易所设置或 sleep」？

评审若提出新假设场景，必须满足 AGENTS.md §1 Scenario Admission：给出当前代码路径、官方契约或
具体并发/单位证据，说明对本增量的实际影响，以及为何必须本轮处理。偏好、未来扩展、以及上述三项
Human 已明确接受的风险，不得判为阻塞。

返回 [TASK_RESULT v2]，并给出
  评审结论: ACCEPT（接受） | REWORK（返工）
  问题记录: <path | none>
  修复要求: <path | none>
REWORK 必须逐条给出可执行的修复要求。ACCEPT 不授权实现、安装依赖、服务控制或实盘下单。
```

## 14. 历史停止线（第二轮；已由 §15–§16 取代）

在本增量通过跨 provider 窄范围计划复核 `ACCEPT`，且 Human 已针对 `rework_count=3` 上限明确选择缩窄、重设计、接受限制或停止之前：不改任何源码或测试、不创建新 worktree/分支、不安装 CCXT 到任何环境、不改 `status.json`、不准备或启动返修实现终端。只有 Human 的选择明确允许继续时，Bookkeeper 才能另备实现 dispatch。

`ACCEPT` 之后仍需 Human 单独授权的动作：把 `ccxt==4.5.64` 装入生产 `.venv`、重启服务、任何真实公共 WS 连通验证、合并到 `main`、`push`、部署、任何真实平滑任务或实盘下单。

## 15. Human 页面验收返修：D17–D19（当前活动草案）

### 15.1 任务身份与范围

| 项 | 值 |
|---|---|
| task_id | `smooth-open-v1-human-validation-fix-gpt56sol-xhigh`（计划复核 ACCEPT 后由 Bookkeeper 固化） |
| target_model / reasoning / provider | `gpt-5.6-sol` / `xhigh` / `openai`（沿用原 Implementer） |
| worktree / branch | `/Users/ark/Desktop/ai code/funding_hedging-smooth-v1` / `smooth/v1-fullstack` |
| 输入提交 | 计划复核 ACCEPT 后，由 Bookkeeper 以当时 committed HEAD 固化 |
| rework_count | `4`；Human 已明确允许继续修复，不受旧上限阻止；本次 Human 需求修订不自行加一 |
| 交付 | 一个本地 fix commit；不 push、不合并、不重启 |
| handoff | `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-human-validation-fix-gpt56sol-xhigh.handoff.md`（create-only） |

Allowed Files：

- `backend/hedge_open_tasks/domain.py`（把 `awaiting_manual_start` 中文改为任务通用措辞）
- `backend/hedge_open_tasks/executor.py`（AttemptContext 只新增可选的 smooth 审计载体）
- `backend/hedge_open_tasks/store.py`（仅增加按 task+kind 读取既有 append-only 日志的窄查询；不改 schema、gate 或状态迁移）
- `backend/hedge_open_tasks/service.py`（D17 创建状态、首次启动门、同次 gate 快照、服务层时间点、审计落库与读模型）
- `backend/services/live_hedge_executor.py`（executor / 双腿线程 / 每腿订单客户端调用边界时间点）
- `frontend/index.html`、`frontend/self-check.js`（D18）
- `backend/tests/test_smooth_api.py`、`backend/tests/test_smooth_gate_worker.py`、`backend/tests/test_live_hedge_executor.py`、`backend/tests/test_hedge_service.py`、`backend/tests/test_frontend_field_binding.py`
- `docs/api/public-market-contract.md`（新增 paused-create 与 additive audit 读字段）
- 唯一实现 handoff

明确禁止：`backend/app/server.py`、provider、scheduler、live client、preflight provider、`requirements.txt`、数据库 schema、新端点、新 timer、新 watcher、新重试/锁/状态机，以及其他产品/测试/阶段文件。实现若证明必须超出 Allowed Files，停下交回 Bookkeeper，不自行扩张。

### 15.2 D17：创建后暂停，Human 首次启动

现有证据锚点：`service.py::create_task` 的普通 open INSERT 未传 `initial_status`，随后 smooth + Start gate on 直接 `ensure_worker`；`post_start` 已具备 `paused → running → ensure_worker` 的目标路径；close 已有 atomic paused-create 先例。

最小修复：

1. 只对 `mode=smooth && task_type=open` 的现有 INSERT 传 `initial_status=paused`、`initial_pause_reason=awaiting_manual_start` 及通用中文；删除 create 末尾的 smooth auto-`ensure_worker`。不得改 immediate。
2. 保持建卡首次 preflight、缺腿/1000x 拒绝、固化身份/数量/route、regular-spot forward 预划转的发生位置和结果不变；不得把它们迁到 Start。
3. `_require_fillable` 对 `pause_reason=awaiting_manual_start` 的 smooth 也返回 `409 start_required`，确保未首次启动时 `成交1次` 不能绕过 Human；错误中文改为“任务首次执行必须点击启动”。
4. `post_start`、D16 杠杆、F1 订阅、gate/worker 的既有路径保持单一，不复制启动逻辑。

必须变红的回归：smooth create 返回 paused 且 Start 可用；create 后零 worker、零 provider refs、零 gate、零 attempt、零 dispatch；recovery/startup 不领取该 paused 卡；fill-once 409；post_start 后顺序仍为 `set_leverage → subscribe/open gate → evaluate → prepare → dispatch` 且只有一个 worker。immediate create/status/worker 基线逐值不变。另断言 regular-spot 预划转仍只在 create 发生一次，不在 Start 重做。

### 15.3 D18：只有 running 卡显示动态盘口

现有证据锚点：`renderHedgeTaskCard` 当前以 `task.mode === 'smooth'` 无条件调用 `renderSmoothTaskExtras`；启动成功已把 task 加入 `hedgeLogExpanded`、立即加载日志并重绘。

最小修复：卡片基础区为所有 smooth 状态单独显示“滑点阈值”；动态 `smoothExtras` 只在 `task.mode === 'smooth' && task.status === 'running'` 生成。paused/done/stopped/deleted DOM 不得出现 `hedge-smooth-market-*`、连接状态、正/反向价格/数量/覆盖率/轮次/倒计时。启动成功仍沿用现有自动展开和日志 GET；running 卡显示原完整动态块。不得把 D12 的“非 running 且已展开时继续刷新 attempt/腿日志”改回去，也不得新增 timer。

必须变红的 self-check / Python 绑定断言：paused smooth 有 threshold、启动按钮可点、动态块不存在；running smooth 动态块完整；running→paused 后动态块消失但已展开日志仍被共享 tick 拉取；immediate 卡不受影响。

### 15.4 D19：同次 gate 快照与无侵入延迟审计

现有证据锚点：`_wait_for_smooth_gate` 只返回 `(task, gate_seq, reason, now_us)`；`attempt` 只存 `smooth_pass_reason`；`LiveHedgeExecutor.dispatch` 在两个 thread 中进入 `_send_one_leg`，而真实订单客户端调用发生在 `_send_one_leg` 的 `post_spot_order/post_margin_order/post_um_order`；task_id 日志 GET 当前固定 `logs=[]`，未返回 task 的 append-only log。

最小数据流：

1. `_wait_for_smooth_gate` 的一次评估同时产出放行审计：gate/reason/direction/threshold、spot/perp raw Decimal 一档+`received_at_us`、当前 spread/coverage/pass、放行 wall/monotonic 时刻。为此可增加一个 service 内部 helper，但不得在放行后再次 `latest()`。
2. `_worker_round → _dispatch_one_for_task → AttemptContext → LiveHedgeExecutor` 传同一个仅本轮使用的可变 audit dict；`AttemptContext` 字段必须 optional，immediate/close/既有测试构造点不传时行为不变。
3. service 记录：dispatch 入口、参数组装完成、prepare 开始/提交完成、executor 调用前/返回后。executor 记录：入口、两线程各自启动、每腿订单客户端调用前/返回后、线程完成、join/返回。每腿用独立局部时间字典，join 后合并，禁止用两个线程同时改同一嵌套对象。
4. 所有相对耗时只用 monotonic 微秒，wall clock 只标放行时刻；输出既保留事件 offset，也计算相邻阶段和 `gate→每腿 order_client_call_started` 总耗时。负值或时间倒序属于测试失败，不在生产静默修正。
5. 订单客户端边界必须在凭证检查和 route 选择之后、调用 `post_*_order` 之前打点；字段名写 `order_client_call_started`，不得写“网络已发送”。client 返回后立即打点，后续 UM confirm GET/UNKNOWN query 不混入“放行到下单开始”的数值。
6. `executor.dispatch` 返回后，service 立即 best-effort `append_log(kind='smooth_dispatch_audit', attempt_id=attempt_uuid)`，然后才继续既有 raw persistence/resolve/query/settlement。写日志异常完全吞掉且不得改变 `dispatch` 结果。放行→每腿订单客户端调用前不允许新增 SQL/网络/sleep/print/锁。
7. store 只增加 `list_logs_for_task_kind(task_id, kind)` 的只读查询；task_id 日志 GET additive 返回 `smooth_dispatch_audits=[log_to_doc(...)]`。禁止 schema migration、把 audit 变成 gate、或把每个 WS tick 写库。

必须变红的确定性回归：

- fake provider 在第一次通过后改变盘口，审计仍等于产生 pass 的旧快照且 `latest()` 读取次数不增加；market/manual/timeout 三因均有一条。
- fake monotonic 序列逐值断言事件顺序、阶段差值和两腿总耗时；人为给 prepare/store、线程启动、某腿 client 各注入可控延迟，只有相应分段增长。
- spy store 断言第一笔额外 audit SQL 严格晚于两腿 `order_client_call_started` 和 executor return；审计 append 抛错时两腿 verdict、resolve、次数与任务状态完全相同。
- 两腿仍并发：阻塞 spot client 不妨碍 perp 进入自己的 order client；审计不引入串行等待。
- immediate/close 不创建 `smooth_dispatch_audit`；smooth 审计不含 API key、signature、完整 URL、私有响应。
- task_id API 对新旧 task 均返回数组：旧 task/未放行 task 为 `[]`；已有审计按时间/ID 稳定排序并保持 Decimal 为字符串。

### 15.5 回归与停止线

实现至少执行：

```bash
.venv/bin/python -m pytest backend/tests/test_smooth_api.py \
  backend/tests/test_smooth_gate_worker.py backend/tests/test_live_hedge_executor.py \
  backend/tests/test_hedge_service.py backend/tests/test_frontend_field_binding.py -q
.venv/bin/python -m pytest backend/tests/test_hedge_store.py backend/tests/test_hedge_api.py \
  backend/tests/test_hedge_task_local.py backend/tests/test_hedge_review2_regressions.py \
  backend/tests/test_hedge_leverage.py backend/tests/test_hedge_cycle_core.py \
  backend/tests/test_hedge_cycle_close.py backend/tests/test_hedge_purity.py -q
.venv/bin/python -m pytest backend/tests -q
node frontend/self-check.js
git diff --check
```

全后端仍只允许固定基线前的 `public_ip_service.py` 白名单单一既存失败。不得修改该测试或触发文件。实现不联网、不读凭证、不控制当前服务、不创建任务、不下单、不安装/卸载依赖。当前运行服务不会自动加载 worktree 新代码；修复交付后先走 fresh 跨 provider Review-1，Human 再决定何时重启继续页面验收，最后仍须 fresh Review-2。

## 16. D17–D19 窄范围计划复核请求

只检查四点：① paused-create 是否真正零 worker/订阅/gate/attempt/order，且没有把既有 preflight/预划转挪到 Start、没有改 immediate；② running-only 盘口是否与 non-running 展开日志继续刷新相容；③同次 gate 快照是否禁止二次读盘口，分段是否准确覆盖到两腿各自订单客户端调用开始；④审计是否在 executor 返回后才落既有 log、失败不影响订单、Allowed Files 足够且没有隐含 schema/端点/锁/二次复核。任何要求恢复 fresh preflight 或滑点二次复核、改变两腿/单腿链、修改当前运行服务，均超出本计划。

计划复核必须是 fresh、只读、provider 非 openai 的 Reviewer，只能创建自己的 handoff，给出 `ACCEPT | REWORK`。ACCEPT 后由 Bookkeeper 固化实现 base 并准备 §15 的唯一 Implementer dispatch；不得由 Reviewer 改代码、状态、服务或环境。

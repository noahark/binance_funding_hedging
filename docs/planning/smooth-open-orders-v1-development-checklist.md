# 平滑开单 V1 开发清单（Opus 5 实施细拆结果）

状态：**Planner 细拆完成，等待跨 provider 正式计划评审。本文不授权实现、创建 worktree、安装依赖、修改 status、提交、推送、启动服务或连接任何行情/账户/订单接口。**

- 产品与资金语义唯一权威：`docs/planning/smooth-open-orders-v1.md`（本文不复制 gate 契约，只在必要处引用条目号）。
- P0 证据唯一权威：`docs/planning/ccxt-bookticker-recon-2026-08-13.md`。
- 冻结的实现不变量：`reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/01-advisory-design-reviews.md` §4。
- 细拆依据的代码基线：`base_sha = 0f19beae98b6909c2a5f0a9764f81f71b474a226`。本文引用的行号按该基线核对，实现前请重新 `grep` 确认（行号会漂）。

## 0. 本文中哪些是 Human 已冻结、哪些是本文的实现选择

评审只对第二类提意见；第一类除非有当前代码/契约反证并说明实际影响，否则不重开。

| 类别 | 内容 |
|---|---|
| Human 已冻结（不重开） | `bookTicker` 一档；方向开单率严格 `>` signed threshold；两腿各 `>=80%` 覆盖；每轮 5 分钟；超时回退立即开单；`成交1次` 只放行当前 gate；两腿下单/查单/结算复用立即链；CCXT Pro 作为公共盘口来源（`ccxt==4.5.64`）；不做 `立即成交所有`、私有 WS、完整 order book、动态阈值 |
| 本文的实现选择（可评审） | 三赛道拓扑与依赖顺序；文件所有权划分；provider 模块路径与最小接口；`domain.L1Quote` / `evaluate_smooth_gate` 的纯函数边界；gate 列清理折叠进 `set_task_status`；`prepare_attempt` 增加两个可选关键字参数；smooth 任务在 provider 不可用时 fail-closed 的具体形态；worktree/分支命名；集成顺序与回归矩阵；依赖清单文件名 |

## 1. 已取得的开发输入（不变）

- Human 已冻结：`bookTicker` 一档、严格 `spread > threshold`、两腿各 `>=80%`、每轮 5 分钟、`成交1次` 只放行当前 gate、两腿下单继续复用立即开单。
- P0 已验证 `ccxt==4.5.64` 的 Binance spot/USDⓈ-M `watchBidsAsks`、双 watcher cancel 隔离、普通合约单位和 raw/normalized 差异。
- 必须取 `info.b/B/a/A` 原始字符串；spot 无交易所时间戳；1000x 封禁不能靠 `contractSize` 解除。
- P0 未证明重连 generation、引用归零、close 无残留、多 symbol 共享；这些必须在 provider 交付中 fail-closed 验收（见 §6）。
- 前端 fake 只用于观察布局，不能当最终 API 或后端字段证据。

## 2. 拓扑判定：两路真并行 + 一路依赖后置 + 一路前端后置

**结论：不能三路真并行。** 采用

```text
阶段 1（并行）  A：Claude-GLM  公共盘口 Provider      ┐
                B：GPT-5.6-sol high ①  Gate 域与持久化 ┘→ 合并为集成基线
阶段 2（依赖）  C：GPT-5.6-sol high ②  Worker/API 接线与安全回归（同时是唯一集成者）
阶段 3（依赖）  D：Claude-GLM  前端真实接线（C 冻结 API 之后）
```

### 2.1 为什么 A 与 B 是真并行

两者文件集完全不相交，且都不改对方任何一行：

- A 只新增文件（`backend/services/best_bid_ask_provider.py`、`backend/tests/test_best_bid_ask_provider.py`、`requirements.txt`）。它**不允许**接线到 `service.py`/`server.py`，因此不碰任何现有生产文件。
- B 只改 `backend/hedge_open_tasks/domain.py`、`backend/hedge_open_tasks/store.py` 及其两个现有测试文件。
- A 与 B 之间没有类型、函数或测试夹具依赖：`domain.py` 不 import provider（见 §3.2 的 `L1Quote` 设计），provider 不 import `hedge_open_tasks`。

### 2.2 为什么 C 必须后置（真实调用链证据）

C 的每一个入口都要调用 B 在 base 上还不存在的函数，而这些函数的**事务边界本身**就是被评审的资金安全点：

| C 要改的位置（base 行号） | 必须调用的 B 侧新接口 | 为什么不能自造本地替身 |
|---|---|---|
| `service.py:741` `_CREATE_BODY_KEYS` + `service.py:761` 解除 `mode != immediate` 拒绝 | `domain.validate_slippage_threshold_pct` | 阈值规范化是 D5/D6 的判断值来源，两份实现会产生两种舍入 |
| `service.py:1592` `_worker_round`（gate 建立/等待/候选原因） | `store.open_smooth_gate` / `domain.evaluate_smooth_gate` | gate 建立条件与 `list_eligible_tasks`（`store.py:848`）同源，必须由 store 事务判定 |
| `service.py:2888` `prepare_attempt(...)` 调用点 | `store.prepare_attempt(..., expected_gate_seq, smooth_pass_reason)` | 设计 §6.1 要求 gate 复核、attempt 写入、计数递增、gate 清空在**同一事务**内；替身必然是第二套 gate 实现 |
| `service.py:1043` `post_fill_once` 分流 | `store.force_smooth_gate` | force flag 的原子性与 409 判定同属该事务 |

`AGENTS.md` §1 与本文 §4.3 都禁止为并行造兼容层/双实现，因此 C 的正确形态是**依赖任务**，不是并行任务。

C 对 A 的依赖是**结构性**的（模块路径 + 方法名 + 快照字段），已由 §3.1 冻结；但 `server.py` 组合根要 import A 的模块，所以 C 的默认起点仍是 A+B 的集成提交。

### 2.3 为什么 D（前端）必须最后

`frontend/index.html` 要消费的 `smooth_gate_seq`、`smooth_market` 字段全部由 C 定义（`task_to_doc` 和 `get_logs` 都在 `service.py`，见 `service.py:161` 与 `service.py:1103`）。在 C 冻结返回形状之前接线，等于让前端对着猜测的字段名写代码。

### 2.4 Human 三终端的实际占用

| 终端 | 阶段 1 | 阶段 2 | 阶段 3 |
|---|---|---|---|
| Claude-GLM | A（provider） | 空闲 | D（前端） |
| GPT-5.6-sol ① | B（gate 域/存储） | 空闲 | 空闲 |
| GPT-5.6-sol ② | 空闲 | C（worker/API/集成） | 空闲 |

阶段 1 有一个终端空闲。**本文不为填满终端发明任务**：能与 A/B 并行且无共享文件的工作在当前范围内不存在，硬凑只会制造需要后置返工的接口猜测。

### 2.5 一个可选的加速分支（Human 决定，非默认）

若 A 因 CCXT 生命周期验收返工而滞后，Human 可让 C 从 **B-only** 的集成提交起步。代价必须明说：C 的 `test_smooth_provider_wiring.py`（断言真实 provider 模块可 import 且满足协议）在 A 落地前必然失败，C 不得因此删除或跳过该用例，且封存 delivery 前必须在 A 落地后重跑全绿。默认路径仍是 A+B 都落地后再启动 C。

## 3. 冻结的最小跨任务契约（每个字段恰好一个 owner）

以下签名与字段是三个终端之间**唯一**的约定。任何一方想改，必须回到 Planner/Bookkeeper 走一次修订，不得在自己的分支里私自扩展。

### 3.1 契约一：公共盘口 Provider（owner = A；consumer = C）

模块路径固定：`backend/services/best_bid_ask_provider.py`。

**为什么必须放在 `backend/services/` 而不是 `hedge_open_tasks/`**：`backend/tests/test_hedge_purity.py` 用静态正则守住 `hedge_open_tasks/**` 不得出现 `import urllib|socket|requests|http.client|hmac|hashlib`，并禁止该包 import services 层的实盘模块。CCXT 走 aiohttp，放进该包会直接打破这条已存在的零网络证明。provider 因此与 `hedge_open_live_client.py`、`live_hedge_executor.py` 同层，靠注入进入任务层——与现有实盘执行器完全同构。

```python
MarketKey = tuple[str, str, str]          # (exchange_id, market_type, symbol)
                                          # 例：("binance", "spot", "BTCUSDT")
                                          #     ("binance", "swap", "BTCUSDT")

@dataclass(frozen=True)
class BookTickerSnapshot:
    key: MarketKey
    bid_price: Decimal
    bid_qty: Decimal
    ask_price: Decimal
    ask_qty: Decimal
    exchange_ts_ms: int | None            # perp 取 raw E；spot 恒为 None
    received_at_us: int                   # 本地墙钟，两侧都必填
    generation: int                       # 每次订阅建立或重连递增
    status: str                           # "connecting" | "live" | "disconnected"
    error_zh: str | None                  # 安全中文摘要，禁含凭证/完整请求

class BestBidAskProvider:
    def __init__(self, *, on_change: Callable[[MarketKey], None] | None = None,
                 source_factory: Callable[[MarketKey], "L1Source"] | None = None) -> None: ...
    def start(self) -> None: ...                      # 启动专用 event-loop 线程，幂等
    def subscribe(self, key: MarketKey) -> None: ...   # 引用计数 +1；首次订阅才建 watcher
    def release(self, key: MarketKey) -> None: ...     # 引用计数 -1；归零才 cancel watcher
    def latest(self, key: MarketKey) -> BookTickerSnapshot | None: ...
    def close(self, timeout: float = 5.0) -> None: ... # cancel watcher → close clients → join 线程，幂等
```

冻结的语义（每条都对应 §6 的一个可执行验收）：

1. **Decimal 即原始字符串**：四个价量字段由 `Decimal(raw_str)` 从 `info` 的 `b/B/a/A` 直接构造。`Decimal` 保留尾零（`Decimal("7.48647000")` 的 `format(..., 'f')` 原样回读），因此**不再单独保存 raw 字符串字段**。CCXT normalized 的 `bid/ask/bidVolume/askVolume`（float）在任何路径上都不得出现。
2. **`latest` 的有效性**：只有当前 generation 收到过一条四字段均可解析且 `> 0` 的消息，才返回快照；watcher 抛错/断开/重连中一律返回 `None`（或 `status != "live"` 的快照——二选一由 A 决定并在测试里钉死，C 只判 `status == "live"` 且四值 `> 0`）。
3. **contractSize**：仅用于断言普通可达 symbol `== 1`；不等于 1 或读不到 → 该 key 永不产出 `live` 快照。**禁止**用 contractSize 做任何乘法换算，也不得用它识别 1000x（P0 实测 1000PEPE 同报 `1.0`）。
4. **ccxt 惰性 import**：`import ccxt.pro` 只能出现在 source_factory 的函数体内部。模块本身必须在**未安装 ccxt** 的环境里可 import、可被 A/C 的全部测试驱动。这是本轮能在「依赖尚未获批安装」的前提下完成实现与评审的唯一办法。
5. **线程边界**：`latest` 由同步 worker 线程调用，必须在锁内返回不可变对象；`subscribe`/`release`/`close` 从同步线程线程安全地提交到 event loop，调用方不得 `await`。
6. **`on_change` 回调**：provider 在每次快照更新、失效、重连时调用一次，参数为 MarketKey。回调在 event-loop 线程上执行，C 侧的实现必须是「只置位并 notify，不做阻塞工作」。

### 3.2 契约二：Gate 领域与持久化（owner = B；consumer = C）

**`backend/hedge_open_tasks/domain.py`**（纯函数，零 I/O，不 import 任何 services 层模块）：

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
    spread_pct: Decimal | None    # 该方向开单率（已两位量化）
    spread_pass: bool
    spot_coverage: Decimal | None
    perp_coverage: Decimal | None
    coverage_pass: bool
    market_pass: bool             # spread_pass and coverage_pass
    wait_reason: str              # 中文等待原因，UI 直显

def evaluate_smooth_gate(direction: str, threshold_pct: Decimal, q_common: Decimal,
                         spot: L1Quote | None, perp: L1Quote | None) -> SmoothGateEval: ...
```

`evaluate_smooth_gate` 的实现约束：开单率**必须直接调用** `backend/domain/snapshot.py::compute_opening_spread_pct`（`snapshot.py:613`，已含 Decimal、`ROUND_HALF_UP`、两位量化、负零归一、分母 `<= 0` 返回 None），禁止复制公式。forward 取 `compute_opening_spread_pct(perp.bid, spot.ask)`，reverse 取 `compute_opening_spread_pct(spot.bid, perp.ask)`；返回的字符串解析回 `Decimal` 后与 `threshold_pct` 做严格 `>`。覆盖率分母恒为 `task.q_common`，forward 用 `spot.ask_qty`/`perp.bid_qty`，reverse 用 `spot.bid_qty`/`perp.ask_qty`。任一侧为 `None` → `market_pass = False`。

**`backend/hedge_open_tasks/store.py`**：

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

冻结的事务语义：

1. `open_smooth_gate` 在一个事务内复核：task 存在、`task_type == open`、`mode == smooth`、`status == running`、`scheduled_attempt_count < target_n`、无 `pair_outcome IS NULL` 的 attempt、且（无活动 gate 或活动 gate 的 seq 等于入参）。不满足返回 `None`。幂等：同 seq 重复调用不重置 `started_at_us`，也不清 force flag。
2. `force_smooth_gate` 在一个事务内复核同一组条件 + `smooth_gate_seq == gate_seq`，置 `smooth_gate_force_requested = 1`。不满足返回 `None`（C 映射为 409）。重复调用幂等，不累计次数。
3. `prepare_attempt` **扩参而非新增并行方法**：在其现有事务（`store.py:888`）内追加复核——若 `task.mode == smooth`，则 `expected_gate_seq` 必须非空且等于当前 `smooth_gate_seq`，否则返回 `None`；成功时在同一事务里写 `attempt.smooth_pass_reason`、递增 `scheduled_attempt_count`、清空三个 gate 列。
   - **fail-closed 兜底（重要）**：`mode == smooth` 且 `expected_gate_seq is None` → 返回 `None`。这一条把 dry-run tick（`service.py:2438` `list_eligible_tasks` → `_dispatch_one_for_task`）、非 live 的 `post_fill_once`（`service.py:1054`）等所有旁路入口一次性关死，不必在每个调用点各加一道判断。
   - immediate 任务两个参数均为 `None` → 行为与今天逐字节一致，现有测试不需改。
4. `set_task_status`（`store.py:774`）是全仓状态迁移的唯一收口：**新状态不是 `running` 时，同一事务内清空三个 gate 列**。pause/delete/done/stopped 由此自动清 gate，C 不需要在各分支散落 `clear_smooth_gate` 调用。`clear_smooth_gate` 只保留给「任务仍 running 但 Start gate 关闭」这一种情况。
5. 不存在独立的 `consumed` 状态；不在 task 上保存「最近一次 pass_reason」（冻结不变量 §4.1/§4.2）。

### 3.3 契约三：Service / API 读写模型（owner = C）

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
       spot: {status, received_at_us, bid, bid_qty, ask, ask_qty} | null,
       perp: {同上} | null,
       forward_spread_pct: string | null,
       reverse_spread_pct: string | null,
       spot_coverage_pct / perp_coverage_pct: string | null,
       spread_pass / coverage_pass / gate_pass: bool,
       wait_reason: string
     }
```

`server.py` 的唯一改动：`_hedge_open_action`（`server.py:1271`）当前对全部动作 `_drain_hedge_body()` 后只传 `task_id`。改为 **仅 `fill-once`** 读取可选 JSON body 并透传（沿用既有 `_read_hedge_body(required=False)` 与 `BODY_MAX_BYTES` 上限），其余动作保持 drain 语义不变。

`scheduler.py` **不属于任何人的 Allowed Files**：平滑链路完全走 task-local worker，1 秒 tick 只驱动 dry-run 路径，本轮不需要改动。

## 4. 四个任务包

通用条款（四包都适用）：

- 只改自己的 Allowed Files；范围不足是 blocker，不是自行扩权的理由（`AGENTS.md` §3.3）。
- 不得启动服务、读取凭证、连接私有流、调用订单/账户/资产接口、安装依赖到 `.venv`、推送、合并、改 `status.json` / `ACTIVE.json` / `PROJECT_STATE.md`。
- **公共 WebSocket 也不连**：A 的全部验收用 fake async source 完成；真实 CCXT 连通性已由 P0 覆盖，重复连接不产生新证据且超出授权。
- 一个本地 delivery commit，不 push。按 `agents/roles.md` Task Handoff Evidence Contract 在 `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/<task-id>.handoff.md` 写唯一交接件（create-only，路径已由 Bookkeeper 预检不存在）。
- **不写 `status.json`**：三个终端并行时该文件只有一个 `current_task`，任何终端写它都会与另一条赛道抢同一行。本轮由 Bookkeeper 独占状态迁移，各赛道的事实以自己的 handoff 文件与分支为准（比 `AGENTS.md` §7 给实现者的权限更严，方向安全）。
- 失败即停：验收命令红灯时不得改测试断言、不得 `-k` 跳过、不得扩大文件范围绕过；停下来报 blocked。

### 4.1 任务 A — 公共盘口 Provider（`claude-glm` / provider `zhipu_glm`）

- task_id：`smooth-open-p1-provider-claude-glm`
- 目标：交付 §3.1 契约的 `BestBidAskProvider`，含专用 event-loop 线程、两个独立 watcher、共享 key 引用计数、generation 失效与恢复、不可变 Decimal 快照、close/join；用 fake async source 完成全部验收。**不接任何任务/订单代码。**
- 输入提交：`base_sha`（正式计划评审 ACCEPT 后由 Bookkeeper 填入）。
- Allowed Files（唯一所有权）：
  - `backend/services/best_bid_ask_provider.py`（新建）
  - `backend/tests/test_best_bid_ask_provider.py`（新建）
  - `requirements.txt`（新建，见 §7）
  - `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-p1-provider-claude-glm.handoff.md`（新建）
- 明确禁止触碰：`backend/hedge_open_tasks/**`、`backend/app/server.py`、`backend/domain/**`、`frontend/**`、任何现有测试文件、`.venv/`。
- 验收命令（全绿才算完成）：
  ```bash
  .venv/bin/python -m pytest backend/tests/test_best_bid_ask_provider.py -q
  .venv/bin/python -m pytest backend/tests -q
  .venv/bin/python -m pytest backend/tests/test_hedge_purity.py -q
  git diff --check
  ```
  第二条证明零回归；第三条单独列出是因为它是本模块选址的直接约束（新模块若被误放进 `hedge_open_tasks/` 会红）。全部测试必须在**未安装 ccxt** 的当前 `.venv` 下通过。
- 失败停止条件：CCXT 的重连/close 语义无法在 fake source 下形成确定性验收（§6 的 P1-1/P1-6 做不出来）→ 停，报 blocked，交由 Human 决定是否切 Binance 原生 public bookTicker fallback；不得先合入一个「靠库应该会自动重连」的实现。

### 4.2 任务 B — Gate 领域与持久化原子性（`gpt-5.6-sol` reasoning high / provider `openai`）

- task_id：`smooth-open-p2-gate-store-gpt56sol`
- 目标：交付 §3.2 的全部契约——阈值规范化、`L1Quote`/`evaluate_smooth_gate` 纯函数、四列 + 一列迁移、三个 gate 事务方法、`prepare_attempt` 扩参与同事务复核、`set_task_status` 的 gate 清理。**不接 CCXT、不调 executor、不启服务、不改 worker。**
- 输入提交：同 A（两者从同一 base 起步）。
- Allowed Files（唯一所有权）：
  - `backend/hedge_open_tasks/domain.py`
  - `backend/hedge_open_tasks/store.py`
  - `backend/tests/test_hedge_domain.py`
  - `backend/tests/test_hedge_store.py`
  - `backend/tests/test_smooth_gate_store.py`（新建，放竞态/崩溃缝用例）
  - `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-p2-gate-store-gpt56sol.handoff.md`（新建）
- 明确禁止触碰：`service.py`、`server.py`、`scheduler.py`、`executor.py`、`backend/services/**`、`frontend/**`、`backend/tests/test_hedge_cycle_core.py`（只跑不改，见下）。
- 验收命令：
  ```bash
  .venv/bin/python -m pytest backend/tests/test_smooth_gate_store.py \
      backend/tests/test_hedge_store.py backend/tests/test_hedge_domain.py -q
  .venv/bin/python -m pytest backend/tests/test_hedge_cycle_core.py -q
  .venv/bin/python -m pytest backend/tests -q
  git diff --check
  ```
  `test_hedge_cycle_core.py` 覆盖 `prepare_attempt` 事务内的持仓周期分配，是本次扩参最容易被撞坏的现有契约；它必须**不改一行**地通过——若必须改它才能通过，说明扩参方式不是加法式的，停下来报告。
- 必答的设计确认（写进 handoff）：`prepare_attempt` 最小扩参 vs 新增专用原子方法 —— 本文已判定为**最小扩参**，理由是设计 §6.1 要求 gate 复核与 attempt 写入同事务，而周期分配、client id、请求指纹已在该事务内；另起方法会复制这段事务或引入两段式提交。B 若在实现中发现该判断与代码事实冲突，必须停下报告，不得自行改成新方法。
- 失败停止条件：无法在不改现有测试的前提下让 immediate 路径逐字节不变 → 停，报 blocked。

### 4.3 任务 C — Worker/API 接线、安全回归与集成（`gpt-5.6-sol` reasoning high / provider `openai`）

- task_id：`smooth-open-p3-worker-api-gpt56sol`
- 目标：把 A 的 provider 与 B 的 gate 事务接进任务链——smooth 创建、读模型、`fill-once(gate_seq)` 分流、`fill-all` 拒绝、`smooth_market` 读模型、gate 建立/等待/唤醒、候选 pass_reason 透传到 `prepare_attempt`、provider 生命周期挂到组合根。**它同时是唯一集成者**：不需要第五个「集成任务」。
- 输入提交：A、B 的集成基线（Bookkeeper 合并后 `git rev-parse` 的确切值）。
- Allowed Files（唯一所有权）：
  - `backend/hedge_open_tasks/service.py`
  - `backend/app/server.py`
  - `backend/tests/test_hedge_service.py`
  - `backend/tests/test_hedge_api.py`
  - `backend/tests/test_smooth_gate_worker.py`（新建，gate 建立/等待/唤醒/三方竞态/重启缝）
  - `backend/tests/test_smooth_api.py`（新建，创建、读模型、fill-once/fill-all 分流与 409）
  - `backend/tests/test_smooth_provider_wiring.py`（新建，见 §2.5）
  - `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-p3-worker-api-gpt56sol.handoff.md`（新建）
- 明确禁止触碰：`domain.py`、`store.py`（B 的文件——需要改动说明契约有误，停下报告）、`backend/services/best_bid_ask_provider.py`（A 的文件）、`backend/services/live_hedge_executor.py` 与 `hedge_open_live_client.py` 与 `hedge_preflight_provider.py`（**任何分支都不得改动实盘下单/查单/结算行为**）、`scheduler.py`、`frontend/**`。
- 实现要点（每条都对应设计条目，不得自行扩展）：
  1. 等待与唤醒（设计 §6.2）：每 task 一个 `threading.Condition` + 单调 `wake_version`。worker 在锁内记录版本号，锁外重读 task/gate/Start gate/两侧快照，未通过则 `wait_for(版本已变, timeout=剩余秒数)`。**不得复用 `_stop_events`**——它只在 `stop()`（`service.py:588`）被 set，而 `post_pause`/`post_delete` 明确不打断 worker（`service.py:1023-1027` 的 Review-1 r3 P1-2 结论），复用会破坏既有 drain 语义。
  2. 唤醒源恰好六个：provider `on_change`、`force_smooth_gate` 成功、pause/delete、Start gate 变化、`service.stop()`、deadline 到期。
  3. 绝不忙循环：`_run_task_worker`（`service.py:1513`）只在有未终态 legs 时 pace，gate 等待发生在无 legs 时，必须由 condition 阻塞承担。
  4. `post_fill_once` 的 mode 分流发生在 live/offline 分支**之前**；smooth 分支持久化 force 后幂等 `ensure_worker` 并 notify，永不直接 dispatch。
  5. provider 生命周期在 `server.py` 组合根构造与 `close()`；ccxt 缺失时注入 `None`，此时 smooth 创建 400、market pass 恒 False、timeout/manual 仍可用（fail-closed）。
  6. 解除冻结必须与 gate 同一交付：`service.py:761` 的 `mode != immediate` 拒绝只能在本任务内解除。
- 验收命令：
  ```bash
  .venv/bin/python -m pytest backend/tests/test_smooth_gate_worker.py \
      backend/tests/test_smooth_provider_wiring.py backend/tests/test_smooth_api.py -q
  .venv/bin/python -m pytest backend/tests/test_hedge_service.py backend/tests/test_hedge_api.py \
      backend/tests/test_hedge_task_local.py backend/tests/test_hedge_review2_regressions.py \
      backend/tests/test_hedge_cycle_close.py backend/tests/test_hedge_leverage.py -q
  .venv/bin/python -m pytest backend/tests -q
  node frontend/self-check.js
  git diff --check
  ```
- 失败停止条件：任何一条要求改 B 或 A 的文件才能通过 → 停，报 blocked（契约缺陷由 Planner/Bookkeeper 修订，不在实现分支里私改）。测试若需要真实 CCXT 或真实网络才能绿 → 停（说明 fake seam 设计错了）。

### 4.4 任务 D — 前端真实接线（`claude-glm`，C 的 API 冻结之后）

- task_id：`smooth-open-p4-frontend-claude-glm`
- Allowed Files：`frontend/index.html`、`frontend/self-check.js`、`backend/tests/test_frontend_field_binding.py`、自己的 handoff。
- 范围：市场页平滑按钮解除 disabled（`index.html:5622`）+ signed threshold 输入与 `%`；移除 `smooth_next_round` 短路（`index.html:5777`/`5846`）；任务卡 threshold 与动态盘口块（复用现有百分比 formatter/颜色，不新建 timer）；`成交1次` 先 GET 取当前 `smooth_gate_seq` 再 POST，无活动 seq 或非 running 时禁用；`showFillAll`（`index.html:6018`）对 smooth 关闭。
- 验收：`node frontend/self-check.js`（含零新增 timer 断言）+ `.venv/bin/python -m pytest backend/tests/test_frontend_field_binding.py -q` + `git diff --check`。

## 5. worktree / 分支 / 状态隔离

**本文不创建任何 worktree、分支或 stage 目录**；以下是 ACCEPT 之后 Bookkeeper 执行的方案。

沿用仓库已有的同级目录惯例（当前已存在 `/Users/ark/Desktop/ai code/funding_hedging-kimi-smooth-ui`，分支 `fast/kimi-smooth-ui-refine-20260813`）：

| 赛道 | worktree 路径 | 分支 |
|---|---|---|
| A | `/Users/ark/Desktop/ai code/funding_hedging-smooth-p1` | `smooth/p1-provider` |
| B | `/Users/ark/Desktop/ai code/funding_hedging-smooth-p2` | `smooth/p2-gate-store` |
| C | `/Users/ark/Desktop/ai code/funding_hedging-smooth-p3` | `smooth/p3-worker-api` |
| D | `/Users/ark/Desktop/ai code/funding_hedging-smooth-p4` | `smooth/p4-frontend` |

放在 `~/Desktop/ai code/` 之下是刻意的：`PROJECT_STATE.md` 记录的 macOS TCC 限制已经确认该目录对当前终端可读写，换到别处会重演 launchd 那类权限故障。

隔离规则：

1. 每个终端只在自己的 worktree 工作，`git worktree` 天然各有独立 index 与 HEAD，不共享暂存区。
2. `reports/agent-runs/ACTIVE.json` 与 `.../status.json` 只由 Bookkeeper 在主 worktree 写。实现者一行都不碰（§4 通用条款）。
3. 每个赛道的 handoff 文件路径按 task_id 唯一，四条分支各自新增不同文件名，合并时不可能冲突。
4. **`status.json` 只有一个 `current_task` 的现实**：schema（`agents/roles.md` Minimal State And Dispatch Shape）不含并行任务表示，本文**不发明字段**。Bookkeeper 的最小做法是：先备好 A 的 dispatch → revision N 指向 A → Human 启动 A；再备好 B 的 dispatch → revision N+1 指向 B → Human 启动 B。此时 `current_task` 指 B，A 的事实以 `smooth-open-p1-provider-claude-glm.handoff.md` 为准，Bookkeeper 按文件而非按 `current_task` 逐条核验。若 Bookkeeper 认为该做法与自身记账规则冲突，应在计划评审阶段提出，由 Human 裁定，不由实现者临场决定。
5. 阶段 1 两个终端都不得 `git fetch`/`rebase`/`merge` 对方分支。

## 6. P0 未证事项 → P1 可执行验收（全部由任务 A 承担，除标注外）

每一项都必须是一个能跑的用例，不接受「CCXT 应该会自动重连/close」这种论证。fake async source 必须能按脚本抛异常、延迟、断流、重放。

| # | P0 未证事项 | P1 可执行验收（用例语义） |
|---|---|---|
| 1 | watcher 异常/重连的 generation 失效 | fake source 抛异常 → 该 key 立即不再产出 `live` 快照；source 恢复后首条合法消息前仍不可用；恢复后 `generation` 严格递增，且旧 generation 的值不被复用 |
| 2 | 延迟消费者隔离 | spot source 阻塞 N 秒不产出，perp source 持续更新 → perp 的更新计数持续增长、`latest(perp)` 持续刷新；spot 的阻塞不阻塞 provider 任何公共方法 |
| 3 | 同 symbol 共享与引用计数 | 同一 key `subscribe` 两次 → 只创建一个 watcher（source_factory 被调用恰好一次）；`release` 一次后仍 `live` |
| 4 | 最后一个引用释放才 cancel | 上例再 `release` 一次 → watcher 被 cancel，`latest` 返回 `None`/非 live；再次 `subscribe` 会新建 watcher 且 generation 递增 |
| 5 | 多 symbol 行为 | 三个不同 key（spot A、swap A、spot B）并存，各自独立更新与失效，互不串扰；`latest` 不会跨 key 返回错值 |
| 6 | close/join 后零残留 | `close()` 后：event-loop 线程已 join、`asyncio.all_tasks` 中不存在 provider 创建的 task、重复 `close()` 幂等不抛；被 close 后 `latest` 返回 `None` |
| 7 | raw 字段缺失/畸形 | `info` 缺 `b`/`B`/`a`/`A` 任一、值为 `""`/`"0"`/`"abc"`/负数 → 该侧不产出 `live` 快照，不抛异常，不产生半填充快照 |
| 8 | normalized float 不得进入 | 断言快照四字段类型为 `Decimal`；用带尾零的 raw（如 `"7.48647000"`）驱动，断言 `format(snap.bid_qty, 'f') == "7.48647000"`（float 路径会退化成 `7.48647`，因此该断言即 float 探测器） |
| 9 | spot 本地时间 | spot 源无 `E/T` → `exchange_ts_ms is None` 且 `received_at_us > 0`；perp 源有 `E` → `exchange_ts_ms == raw E` |
| 10 | contractSize 非 1 / 未知 | market 元数据 `contractSize` 为 `2`、`None`、缺失三种 → 该 key 永不产出 `live` 快照，且不做任何乘法换算 |
| 11 | 1000x fail-closed（owner = C，非 A） | `create_task(open, mode=smooth)` 对乘数币仍返回 `multiplier_contract_unsupported`；provider 的 `contractSize == 1` 断言不构成任何解除路径 |

## 7. 唯一运行时依赖清单

| 项 | 决定 |
|---|---|
| 文件名 | `requirements.txt`（仓库根，新建） |
| 内容 | 仅 `ccxt==4.5.64` 一行 + 一句中文注释说明「运行时依赖；开发工具（pytest/mypy/ruff）不在此清单」 |
| 维护者 | 任务 A 创建；此后由 Bookkeeper 在依赖变更交付中维护 |
| 事实依据 | 仓库当前**没有任何依赖清单**（无 `requirements*.txt` / `pyproject.toml` / `setup.py`），生产代码全部 stdlib（`backend/adapters/binance_public.py:13` 用 `urllib.request`）；`.venv` 内只有 pytest/mypy/ruff/jsonschema 等开发校验工具。CCXT 将是本仓第一个运行时依赖 |
| 安装边界 | **本轮任何任务都不得执行 `pip install`**。规划期不装、实现期不装、评审期不装。A/B/C/D 的全部测试必须在未安装 ccxt 的当前 `.venv` 下全绿（靠 §3.1 的惰性 import 与 fake source 实现） |
| 生产安装 | 只有在 Review-1 + Review-2 ACCEPT 且 Human 明确授权后，才允许装入正在跑真钱的 `.venv`；安装属于 `AGENTS.md` §3 的外部副作用类动作，需要单独授权，不被任何 ACCEPT 隐含 |
| 回滚 | 安装前记录 `.venv/bin/pip freeze > /tmp/venv-before-ccxt.txt`；回滚为 `pip uninstall ccxt` + 比对 freeze 差异。因为代码对 ccxt 是惰性 import 且 provider 缺失时 fail-closed，卸载后服务仍可启动，只是 smooth 创建被拒——回滚不需要回退代码 |

## 8. 集成、固定 SHA 与回归矩阵

### 8.1 合入顺序（唯一集成者 = 任务 C）

1. A、B 各自在自己的 worktree 完成、自测全绿、各产出**一个**本地 commit（不 push）。
2. Bookkeeper 在主 worktree 建集成分支 `smooth/integration`，从 `base_sha` 起，先 `cherry-pick` A 的 commit，再 `cherry-pick` B 的 commit（顺序固定：A 在前，因为 A 只增文件，冲突面为零）。
3. 冲突检查（预期为零冲突，因为文件集不相交）：
   ```bash
   git diff --name-only <A_commit>^..<A_commit> > /tmp/a.txt
   git diff --name-only <B_commit>^..<B_commit> > /tmp/b.txt
   comm -12 <(sort /tmp/a.txt) <(sort /tmp/b.txt)      # 必须为空
   git diff --check
   .venv/bin/python -m pytest backend/tests -q          # 合并基线必须全绿
   ```
   `comm` 输出非空 = 文件所有权被破坏，停止集成并回到 Planner 修订，不得手工调和。
4. Bookkeeper `git rev-parse` 集成提交，作为 C 的输入基线写进 C 的 dispatch。
5. C 在 `smooth/p3-worker-api`（从集成提交起）完成接线，产出一个本地 commit。
6. D 从 C 的提交起完成前端，产出一个本地 commit。
7. Bookkeeper 合出最终交付分支，`delivery_sha = git rev-parse` 该分支 tip；`base_sha` 仍为 `0f19bea…`（阶段基线，`agents/roles.md` SHA Discipline 不因分阶段而改）。Review-1 / Review-2 只看这一个固定区间。

### 8.2 全量确定性回归矩阵（封存前必须全部有输出留档）

| # | 命令 | 期望 |
|---|---|---|
| R1 | `.venv/bin/python -m pytest backend/tests -q` | 全绿；基线约 1601 项，新增用例只增不减 |
| R2 | `.venv/bin/python -m pytest backend/tests/test_hedge_purity.py -q` | 绿（provider 未污染任务包的零网络证明） |
| R3 | `.venv/bin/python -m pytest backend/tests/test_hedge_cycle_core.py backend/tests/test_hedge_cycle_close.py -q` | 绿（`prepare_attempt` 扩参未撞坏周期分配/平仓链） |
| R4 | `.venv/bin/python -m pytest backend/tests/test_hedge_task_local.py backend/tests/test_hedge_review2_regressions.py -q` | 绿（worker 生命周期与既有 review-2 回归） |
| R5 | `.venv/bin/python -m pytest backend/tests/test_live_hedge_executor.py backend/tests/test_hedge_executor.py -q` | 绿且**这两个文件零 diff**（实盘两腿提交/查单/结算不得被本轮触碰） |
| R6 | `node frontend/self-check.js` | 末行「全部自检通过」、退出码 0、无新增 timer |
| R7 | `.venv/bin/python -m pytest backend/tests/test_frontend_field_binding.py -q` | 绿 |
| R8 | `git diff --check` | 无输出 |
| R9 | `git diff --stat <base_sha>..<delivery_sha>` | 变更文件集 = A∪B∪C∪D 的 Allowed Files，无第五方文件 |
| R10 | 全流程在**未安装 ccxt** 的 `.venv` 下执行 | R1–R8 仍全绿 |

设计 §13 的 15 条验收矩阵按 owner 落到用例：1/2/3 → B（域）+ D（前端输入）；4 → B（`evaluate_smooth_gate`）+ C（1000x 建卡拒绝）；5/6/14 → A（§6 的 1–10）；7/8/9/10/11/12/15 → C；13 → D。

## 9. 三份 Human 启动文稿草案（INACTIVE）

> **这三段现在不可用。** 占位符 `<<...>>` 必须由 Bookkeeper 在**正式计划评审 ACCEPT 之后**，用真实的 worktree 路径、分支、`git rev-parse` 的 base SHA、status revision 与 dispatch 路径替换，并在替换的同一轮里创建对应 dispatch 文件。未替换前粘贴到终端即为无效启动。

### 9.1 终端一（Claude-GLM，任务 A）

```text
你现在执行 smooth-open V1 的 P1 公共盘口 Provider 实现任务。
工作目录：<<WORKTREE_A>>（git 分支 <<BRANCH_A>>，从 <<BASE_SHA>> 起）。
按 AGENTS.md 顺序启动并核对：stage_id=2026-08-12-smooth-open-orders-v1，
task_id=smooth-open-p1-provider-claude-glm，target_model=claude-glm，provider=zhipu_glm，
status revision=<<REVISION>>，base_sha=<<BASE_SHA>>。
严格执行 <<DISPATCH_A>>。
只允许修改该 dispatch 的 Allowed Files。禁止：安装依赖（包括 pip install ccxt）、
连接任何 WebSocket 或 HTTP 行情/账户/订单接口、读取凭证、启动或重启服务、
修改 status.json / ACTIVE.json / PROJECT_STATE.md、改动 backend/hedge_open_tasks/** 与
backend/app/server.py、push、merge。
全部验收用 fake async source 完成，且必须在未安装 ccxt 的 .venv 下通过。
完成后跑 dispatch 列出的验收命令与 git diff --check，写 handoff，做一个本地 commit（不 push），
返回 [TASK_RESULT v2] 后停止。
```

### 9.2 终端二（GPT-5.6-sol high，任务 B）

```text
你现在执行 smooth-open V1 的 gate 领域与持久化原子性实现任务。
工作目录：<<WORKTREE_B>>（git 分支 <<BRANCH_B>>，从 <<BASE_SHA>> 起）。
按 AGENTS.md 顺序启动并核对：stage_id=2026-08-12-smooth-open-orders-v1，
task_id=smooth-open-p2-gate-store-gpt56sol，target_model=gpt-5.6-sol（reasoning high），
provider=openai，status revision=<<REVISION>>，base_sha=<<BASE_SHA>>。
严格执行 <<DISPATCH_B>>。
只允许修改该 dispatch 的 Allowed Files（domain.py / store.py / 两个现有 hedge 测试 /
新建 test_smooth_gate_store.py / 自己的 handoff）。禁止改 service.py、server.py、
scheduler.py、executor.py、backend/services/**、frontend/**、test_hedge_cycle_core.py。
immediate 路径必须逐字节不变；test_hedge_cycle_core.py 必须不改一行地通过。
禁止：装依赖、连网、读凭证、启服务、改 status.json / ACTIVE.json、push、merge。
完成后跑 dispatch 列出的验收命令与 git diff --check，写 handoff，做一个本地 commit（不 push），
返回 [TASK_RESULT v2] 后停止。
```

### 9.3 终端三（GPT-5.6-sol high，任务 C —— 阶段 1 全部核验通过后才启动）

```text
你现在执行 smooth-open V1 的 worker/API 接线与安全回归任务，并且是本阶段唯一集成者。
工作目录：<<WORKTREE_C>>（git 分支 <<BRANCH_C>>，从集成提交 <<INTEGRATION_SHA>> 起，
该提交已包含 P1 provider 与 P2 gate 存储）。
按 AGENTS.md 顺序启动并核对：stage_id=2026-08-12-smooth-open-orders-v1，
task_id=smooth-open-p3-worker-api-gpt56sol，target_model=gpt-5.6-sol（reasoning high），
provider=openai，status revision=<<REVISION>>，base_sha=<<BASE_SHA>>。
严格执行 <<DISPATCH_C>>。
只允许修改该 dispatch 的 Allowed Files（service.py / server.py / test_hedge_service.py /
test_hedge_api.py / 三个新建测试 / 自己的 handoff）。禁止改 domain.py、store.py、
best_bid_ask_provider.py、live_hedge_executor.py、hedge_open_live_client.py、
hedge_preflight_provider.py、scheduler.py、frontend/**——需要改它们说明契约有误，停下报告。
gate 等待必须用独立 Condition + wake_version，禁止忙循环，禁止复用 _stop_events。
全部回归使用 fake clock、fake provider、record executor，零真实订单、零网络。
禁止：装依赖、连网、读凭证、启服务、改 status.json / ACTIVE.json、push、merge。
完成后跑 dispatch 列出的验收命令、node frontend/self-check.js 与 git diff --check，
写 handoff，做一个本地 commit（不 push），返回 [TASK_RESULT v2] 后停止。
```

（任务 D 的启动文稿在 C 的 API 冻结后由 Bookkeeper 另出，形状同上。）

## 10. 正式跨 provider 计划评审请求（copy-ready）

> 用法：Bookkeeper 备好 dispatch 后由 Human 启动一个**只读**评审终端。评审对象是「设计 + 本细拆」，不是尚不存在的实现。评审者 provider 必须 ≠ `anthropic`（本细拆的作者）；建议 `kimi`（moonshot）或 `grok`（xai），因为 `openai` 与 `zhipu_glm` 都将是本轮实现者。

```text
你现在执行 smooth-open V1 的正式跨 provider 只读计划评审。这不是 Review-1/Review-2，
不授权实现、依赖安装、服务控制、下单或部署。你必须只读：不改任何文件、不改 status.json、
不创建 worktree、不装依赖、不连接任何行情/账户/订单接口。

按 AGENTS.md 顺序启动，核对 stage_id=2026-08-12-smooth-open-orders-v1 与 status.json。
必读，按此顺序：
  1. docs/planning/smooth-open-orders-v1.md（Human 冻结的产品与资金语义）
  2. docs/planning/smooth-open-orders-v1-development-checklist.md（本次受审的实施细拆）
  3. docs/planning/ccxt-bookticker-recon-2026-08-13.md（P0 证据）
  4. reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/01-advisory-design-reviews.md（已冻结不变量）
  5. 需要核实事实时只读：backend/hedge_open_tasks/{service,store,domain}.py、
     backend/app/server.py、backend/domain/snapshot.py、backend/tests/test_hedge_purity.py、
     frontend/index.html

请逐项裁定并给出结论：
 A. 并行拓扑：细拆判定「A/B 真并行 + C 依赖后置 + D 前端后置」。依据当前调用链与文件所有权，
    这个判定是否成立？是否存在被忽略的共享文件、共享测试夹具或隐藏契约耦合？
    是否存在一个不需要兼容层/双实现/猜测接口的、更快的诚实拆法？
 B. 单位与精度：覆盖率分母固定为建卡 task.q_common、两腿同量纲、contractSize 只做 ==1 断言、
    1000x 继续由 SPOT_SYMBOL_MAP 封禁——这套口径能否形成可执行契约？
    开单率复用 compute_opening_spread_pct 的两位量化 + 严格 > 是否会产生判断/展示不一致或资金侧偏差？
 C. Provider 生命周期：专用 event-loop 线程 + 引用计数 + generation 失效 + close/join，
    以及「ccxt 惰性 import、未安装即 fail-closed」的边界，是否足以在不连真实 WS 的前提下被验收？
    §6 的 11 条 P1 验收是否覆盖了 P0 明确未证的全部事项？
 D. gate 原子性：把 gate 复核、attempt 写入、计数递增、gate 清空放进 prepare_attempt 的同一事务，
    并在 mode=smooth 且 expected_gate_seq 为空时 fail-closed，能否真正封住
    自然通过 / 人工 force / timeout 三方竞态与 10/10 第 11 单？
    把 gate 列清理折叠进 set_task_status 是否遗漏了任何状态迁移路径？
 E. 停机与恢复缝：进程停机计入 5 分钟窗口、恢复后可立即形成 timeout 候选但仍过全部现有安全门；
    Human pause/resume 清 gate 重开完整窗口而进程重启续原 gate——这两种语义是否在文档与拆分中一致，
    是否存在能绕过 Start gate / preflight / prepare_attempt 硬门的路径？
 F. 模式隔离：immediate 创建、现有 fill-once、fill-all、close 任务、dry-run tick 与市场页 REST
    开单率是否被证明零回归？smooth 的旁路入口是否全部关死？
 G. 证据充分性：本细拆是否有任何结论依赖「库应该会自动重连/close」这类推断而非可执行证据？

评审若提出新假设场景，必须满足 AGENTS.md §1 Scenario Admission：给出当前代码路径、
官方契约或具体并发/单位证据，说明对本交付的实际影响，以及为何必须本轮处理。
只对偏好不同、Human 已明确接受的市场风险或未来扩展，不判阻塞。

返回 [TASK_RESULT v2]，并给出明确的
  评审结论: ACCEPT（接受） | REWORK（返工）
  问题记录: <path | none>
  修复要求: <path | none>
REWORK 必须逐条给出可执行的修复要求。ACCEPT 不授权启动服务、安装依赖或实盘下单。
```

## 11. 角色路由与记账（供 Bookkeeper 使用，不在本任务内执行）

- 实现者 provider：A、D = `zhipu_glm`；B、C = `openai`。
- 计划评审：provider ≠ `anthropic`（Planner），建议 `moonshot`/`xai`。
- Review-1：provider 必须 ≠ 受审部分作者的 provider；本轮作者覆盖 `openai` + `zhipu_glm`，故 Review-1 取 `moonshot`（kimi）或 `xai`（grok），与计划评审者错开更佳。
- Review-2：必须 ≠ 交付区间内全部实现/修复作者的 provider；`sonnet5`（anthropic）符合默认规则（`agents/roles.md` Review-2，DEC-2026-08-04-001）。本细拆由 anthropic 的 Opus 5 完成，属设计参与而非实现，按规则须在评审记录中披露。
- `rework_count`：绑定交付物。四条赛道构成同一交付物，任一赛道因评审发现返工即递增一次；改名或拆分不清零。计划评审的 verdict 不触碰 `rework_count`（`AGENTS.md` §8）。
- 风险等级：HIGH_RISK（订单触发时机 + 次数硬上限 + 实盘资金路径），Review-1 + Review-2 双轮不可省。

## 12. 当前停止线（不变，且加严）

在正式计划评审 ACCEPT 前：不创建 worktree/分支/stage 目录，不安装 CCXT 到任何环境（含隔离 venv——P0 已完成，无需重复），不解除 `mode=smooth` 后端拒绝或前端 disabled，不接 worker/executor，不改 `status.json`。

ACCEPT 之后仍需 Human 单独授权的动作：把 `ccxt==4.5.64` 装入生产 `.venv`、重启服务、任何真实公共 WS 连通验证、合并到 `main`、部署、任何实盘下单。

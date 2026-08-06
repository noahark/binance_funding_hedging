# Task Handoff: 2026-08-06-hedge-order-close-validation-close-forward-regular-spot-balance-fix

## Source Report (author-only; immutable after task end)

- task_id: `2026-08-06-hedge-order-close-validation-close-forward-regular-spot-balance-fix`
- role: `Implementer`（bounded finding repair；target_model: deepseek）
- stage_id: `2026-08-06-hedge-order-close-validation`
- created_at: `2026-08-06 20:54 CST`
- base_sha: `e4d5464`（`git rev-parse e4d5464` = `e4d546435cb4684ec3f0b88a7c40a9b69567ba56`）
- delivery_sha: `pending`（本任务未获提交授权，改动保留在工作树，由 Bookkeeper 处理交付提交）
- rework_count: 1（本任务为响应 Human 实盘复测缺陷的修复交付，dispatch 注明按 §8 递增）

### 背景与根因

Human 实盘复测暴露：THE 普通现货账户持有 600 THE（`/api/v3/account`），统一账户
（`/papi/v1/balance`）无 THE；开 forward close（卖现货平仓）单次 200×2 被前端误拦
「卖回现货需要现货持仓：需要约 200 THE，当前可用 0」。

根因：`compute_preflight` 的 `DIR_REVERSE` 分支（卖现货方向）用
`snapshot.balances`（**统一账户** `crossMarginFree`）判断可用量，但 close+forward 固定
走 **普通现货账户**（`decide_spot_route` close+forward → `(regular_spot,
close_sell_regular_spot)`）。FORWARD 分支在 `regular_spot` 路由下早已路由感知
（`spot_account_usdt`），REVERSE 分支漏了对称的路由感知——2026-08-05 COOKIE 修复链
遗留的对称缺陷（引入提交 `04ab07b`，pre-existing，阻塞实盘平仓）。

### 实际修改范围

**`backend/hedge_open_tasks/domain.py`**：

1. `PreflightSnapshot` 新增字段
   `spot_account_base_free: Decimal | None = None`（对齐 `spot_account_usdt`：仅
   regular_spot 路由读取，注释写明普通现货账户 vs 统一账户两个钱包的区别）。
2. `compute_preflight` REVERSE 分支补路由感知（与 FORWARD 对称）：

   ```python
   else:  # direction == DIR_REVERSE（卖现货方向）
       required = q_common * target_n
       if snapshot.spot_route == SPOT_ROUTE_REGULAR_SPOT:
           available = snapshot.spot_account_base_free or Decimal(0)
       else:
           available = snapshot.balances.get(base, Decimal(0))
   ```

   - `regular_spot`（唯一入口：close+forward 卖现货）→ 普通现货账户该币可用量；
   - 其余（reverse 开仓 / close+reverse 买现货，均 papi_margin）→ `balances` 逐字不变；
   - 语义与 FORWARD 一致：可用量缺失但账户读取成功 = 真 0（不足事实）；读取失败 =
     `None`（fail-closed，快照不组装）。
3. balance gate 注释段补 REVERSE 侧路由感知说明（与 FORWARD 段对称）。

**`backend/services/hedge_preflight_provider.py`**：

1. 新增 `_read_spot_account_base_free(base_asset)`：形状照抄 `_read_spot_account_usdt`
   （asset 参数化），复用 `spot_balances` 缓存（60s TTL、5min 上限）→ 实时降级 +
   stderr 留痕；读失败返回 None（调用方 fail-closed）。
2. `get_snapshot` 的 `regular_spot` 分支补读该币 base 可用量，组装进
   `PreflightSnapshot.spot_account_base_free`；任一读失败（usdt / rate_limit /
   base_free）→ snapshot 不组装（fail-closed）。
3. `_read_spot_account_usdt` 既有行为**逐字不变**（git diff 不含其函数体改动——
   仅新方法 docstring 提及 + get_snapshot 分支 if 条件重组）；FORWARD 分支未改。

**未改**（dispatch 禁止）：`decide_spot_route`、close+forward 固定 regular_spot 路由、
`_ensure_close_spot_balance`（发单前划转与创建时余额检查是两层，后者修前者不动）、
DB schema、前端。

### 测试变动说明（新增 6 个，无既有测试适配——负向回归零适配通过）

全部在 `backend/tests/test_hedge_preflight_provider.py`（dispatch Allowed Files）：

1. `test_close_forward_reads_standard_spot_base_free_the_scenario`：**THE 实盘场景
   全链**——普通现货 free=600、统一账户无 THE、close+forward（direction=REVERSE +
   task_type=close）单次 200×2 → `spot_route=regular_spot`、
   `spot_account_base_free=600`、`compute_preflight` → `balance_ok=True`、
   `available=600`、`required=400`（不再误拦）。
2. `test_compute_preflight_reverse_regular_spot_uses_standard_spot_base`：纯 domain——
   REVERSE + regular_spot → available 取 `spot_account_base_free`（统一账户 balances
   为空仍通过）。
3. `test_compute_preflight_reverse_regular_spot_missing_base_is_zero`：语义与 FORWARD
   一致——可用量缺失但读取成功 = 真 0（`available=0`、`balance_ok=False`、
   `REJECT_INSUFFICIENT_BALANCE`），不是 None / 不是读取失败。
4. `test_compute_preflight_reverse_papi_margin_keeps_balances_verbatim`：**负向回归**——
   REVERSE + papi_margin → available 仍取统一账户 `balances` 逐字不变。
5. `test_non_regular_spot_never_reads_standard_spot_base`：provider 侧 close+reverse
   （papi_margin）→ `spot_account_base_free=None`、不触发额外普通现货账户读取。
6. （沿用既有 `test_routing_close_forward_spot_only_keeps_close_sell_regular` 的
   close+forward 路由回归，未改。）

无既有测试需要适配（验收 4：reverse 开仓 / close+reverse 余额语义与改动前逐字一致，
`test_hedge_domain.py` 的 `test_preflight_reverse_accept` /
`test_preflight_reverse_insufficient_base` 等零修改通过）。

### 命令与结果

- `.venv/bin/python3 -m pytest backend/tests -q` → **1467 passed**（基线 1462 +
  本任务净增 5；无失败）。
- `node frontend/self-check.js` → 全部自检通过（本任务未改前端）。
- `git status --short` → 仅 3 个 Allowed Files（domain.py / hedge_preflight_provider.py /
  test_hedge_preflight_provider.py）；`.reasonix/` 与 `macos_input_outage_playbook.md`
  为宿主/其他会话产物，非本任务文件。
- 数据面核验：`git diff` 确认 `_read_spot_account_usdt` 函数体零改动（验收 2）；
  `compute_preflight` FORWARD 分支零改动；REVERSE 非 regular_spot 分支仅缩进变化。

### 未完成事项 / 不能假设的事实

- 本任务未提交（无提交授权）。
- 修复经核验后按 §8（HIGH_RISK：平仓余额门）走 review-1 + review-2；`rework_count`
  递增一次（响应缺陷的修复交付）。
- `spot_account_base_free` 读取失败 → 整盘 fail-closed（比 task 05 前多一个
  regular_spot 分支的必需读；但与 USDT 同源 `/api/v3/account` 响应，实际影响极小）。
- 服务当前停止；下一步由 Human 重启实盘复测。

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-06-hedge-order-close-validation/evidence/2026-08-06-hedge-order-close-validation-close-forward-regular-spot-balance-fix.handoff.md`
  2. `reports/agent-runs/2026-08-06-hedge-order-close-validation/06-close-forward-regular-spot-balance-fix.dispatch.md`
  3. `backend/hedge_open_tasks/domain.py`（`PreflightSnapshot.spot_account_base_free`、`compute_preflight` REVERSE 分支）
  4. `backend/services/hedge_preflight_provider.py`（`_read_spot_account_base_free`、`get_snapshot` regular_spot 分支）
  5. `backend/tests/test_hedge_preflight_provider.py`（6 个新测试）
- 执行：Human 重启服务（加载新代码）后实盘复测——THE 普通现货 600 / 合约空 400，
  开 forward close 200×2：**不再被误拦**，面板与交易所一致。
- 关卡：修复经核验后按 §8 走 review-1 + review-2（HIGH_RISK：平仓余额门）。
- 不能假设的事实：服务未运行；`rework_count` 已按 dispatch 递增为 1（本修复交付）。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

```text
[TASK_RESULT v2]
任务 ID: 2026-08-06-hedge-order-close-validation-close-forward-regular-spot-balance-fix
执行结果: completed
结果摘要: compute_preflight REVERSE 分支补 regular_spot 路由感知（close+forward 卖现货改用普通现货账户该币可用量，THE 600 不再误报可用 0）；PreflightSnapshot 新增 spot_account_base_free；provider 新增同源读取；1467 测试 + self-check 全绿
产物: [backend/hedge_open_tasks/domain.py, backend/services/hedge_preflight_provider.py, backend/tests/test_hedge_preflight_provider.py, reports/agent-runs/2026-08-06-hedge-order-close-validation/evidence/2026-08-06-hedge-order-close-validation-close-forward-regular-spot-balance-fix.handoff.md]
检查结果: [REVERSE 路由感知：regular_spot 用 spot_account_base_free/缺失→0、非 regular_spot 用 balances 逐字不变、FORWARD 零改动 通过(pass), 数据面：新字段默认 None、仅 regular_spot 读、_read_spot_account_usdt 函数体零改动、读失败 fail-closed 通过(pass), THE 场景：free=600/统一无 THE/200×2 → balance_ok=True、available=600 通过(pass), 负向回归：reverse 开仓/close+reverse 既有测试零适配通过 通过(pass), 回归 pytest 1467 passed+self-check 全绿 通过(pass), 范围：不改路由/划转/前端/DB，git status 仅 3 个 Allowed Files 通过(pass)]
阻塞项: [none]
本地北京时间: 2026-08-06 20:54:24 CST
下一步模型: deepseek（Bookkeeper；本任务回执的直接接收者）
下一步任务: 读取：reports/agent-runs/2026-08-06-hedge-order-close-validation/evidence/2026-08-06-hedge-order-close-validation-close-forward-regular-spot-balance-fix.handoff.md；执行：核验交接件与工作树改动范围后封存 delivered/reported，并按 §8（HIGH_RISK 平仓余额门）准备 review-1/review-2；关卡：Human 重启服务实盘复测（THE forward close 200×2 不再误拦、面板与交易所一致）
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- verified_at: `2026-08-06 21:04:43 CST`
- source_sha256: `4ee1ea5425056d0a02440c46f58531e8fe07df2356a1d2822c2798d393628be2`
- status_revision: 8（核验时 `status.json` 指向本任务，state `dispatched`）
- base_sha / delivery_sha: `e4d546435cb4684ec3f0b88a7c40a9b69567ba56` .. 见下文交付提交
- verdict: **verified（通过）**；`rework_count` 1（响应实盘缺陷的修复交付，dispatch 已注明）
- 依据（可复现）：
  - `python3 -m pytest backend/tests -q` → **1467 passed**（本 Bookkeeper 实测，91.22s）
  - `node frontend/self-check.js` → 全部自检通过（本 Bookkeeper 实测）
  - `domain.py:1219-1225` REVERSE 分支：`regular_spot` → `spot_account_base_free or Decimal(0)`、否则 `balances.get(base)` 逐字不变；FORWARD 分支零改动（:1216-1218 原样）
  - `domain.py:914` 新字段 `spot_account_base_free: Decimal | None = None`
  - `hedge_preflight_provider.py:693` 新方法 `_read_spot_account_base_free`（形状照抄 `_read_spot_account_usdt`，asset 参数化；`git diff` 确认 `_read_spot_account_usdt` 函数体零改动）
  - `:886-901` get_snapshot regular_spot 分支补读 + 任一失败 fail-closed（`_mark_failed_read("spot_account_base_free")`）
- 观察点（不阻塞）：`spot_account_base_free` 与 USDT 同源 `/api/v3/account` 响应，regular_spot 分支多一个必需读，失败即整盘 fail-closed——比 task 05 前多一个失败点，但同源响应实际影响极小（handoff 已如实说明）
- 后续状态：06 `dispatched` → `verified`；本修复属 HIGH_RISK（平仓余额门），按 §8 需 review-1 + review-2；Human 重启服务实盘复测（THE forward close 200×2 不再误拦）

## Errata (append-only)

# 修复任务：close+forward 平仓余额检查读错钱包（unified → 普通现货账户）

阶段：`2026-08-06-hedge-order-close-validation`（验证下单/平仓核心链路 + 修复小 bug）
status.json：`reports/agent-runs/2026-08-06-hedge-order-close-validation/status.json`

背景（Human 实盘复测暴露，Bookkeeper 定位）：
THE 普通现货账户持有 600 THE（`/api/v3/account` `balances_spot` free=600），统一账户
（`/papi/v1/balance` `balances_unified`）无 THE。开 forward close（卖现货平仓）单次
200 × 2 次 → 前端弹「卖回现货需要现货持仓：需要约 200 THE，当前可用 0」——**误拦**。

根因：`compute_preflight`（`backend/hedge_open_tasks/domain.py:1204-1206`）的
`DIR_REVERSE` 分支（卖现货方向）用 `snapshot.balances`（**统一账户** `crossMarginFree`）
判断可用量，但 close+forward（卖现货）固定走 **普通现货账户**（`decide_spot_route`
close+forward → `(regular_spot, close_sell_regular_spot)`，`domain.py:1043-1045`）。
FORWARD 分支在 `regular_spot` 路由下早已路由感知（`domain.py:1200-1201` 用
`spot_account_usdt`），**REVERSE 分支漏了对称的路由感知**——2026-08-05 COOKIE 修复链
遗留的对称缺陷（引入提交 `04ab07b`，pre-existing，早于本 stage base，但阻塞实盘平仓）。

## Identity

- task_id: `2026-08-06-hedge-order-close-validation-close-forward-regular-spot-balance-fix`
- target_role: `Implementer`（bounded finding repair）
- target_model: `deepseek`（Human 指定）
- provider: 按 `agents/roles.md` 模型映射
- status_revision: 8
- required_skill: `agents/skills/minimal-change-engineer.md`

## Goal

### 核心修复（最小，与 FORWARD 分支对称）

`compute_preflight` 的 `DIR_REVERSE` 分支（`domain.py:1204-1206`）补路由感知：

```python
else:  # direction == DIR_REVERSE（卖现货方向）
    required = q_common * target_n
    if snapshot.spot_route == SPOT_ROUTE_REGULAR_SPOT:
        available = snapshot.spot_account_base_free or Decimal(0)   # 普通现货账户该币
    else:
        available = snapshot.balances.get(base, Decimal(0))          # 统一账户（现状）
```

- `spot_route == regular_spot`（当前唯一入口：close+forward 卖现货）→ 用**普通现货账户
  该币可用量**；其余（reverse 开仓 / close+reverse 买现货，均 papi_margin）→ 维持
  `snapshot.balances` 逐字不变。
- 语义必须与 FORWARD 分支一致：**可用量缺失但账户读取成功 = 真 0（不足事实）**；
  读取失败 = `None`（fail-closed，快照不组装）。

### 数据面

1. **`backend/hedge_open_tasks/domain.py`**：
   - `PreflightSnapshot` 新增字段 `spot_account_base_free: Decimal | None = None`
     （对齐 `spot_account_usdt`：仅 regular_spot 路由读取，注释写明两个钱包的区别）；
   - `compute_preflight` REVERSE 分支按上述逻辑改；docstring 的 balance gate 段落
     同步补一句 REVERSE 侧路由感知说明（与 FORWARD 段对称）。
2. **`backend/services/hedge_preflight_provider.py`**：
   - 新增读取普通现货账户**指定 base 资产**可用量（`free`）的方法，复用
     `spot_balances` 缓存（60s TTL，5min 上限）→ 实时降级，形状照抄
     `_read_spot_account_usdt`（`asset` 参数化；缓存结构不符降级 + stderr 留痕；
     读失败返回 None 由调用方 fail-closed）；
   - `get_snapshot` 的 `regular_spot` 分支（`:826-829` 附近）补读该币 base 可用量，
     组装进 `PreflightSnapshot.spot_account_base_free`；
   - **不改** `_read_spot_account_usdt` 的既有行为（USDT 侧逐字不变），不得破坏
     FORWARD 分支的 `spot_account_usdt` 读取。
3. **禁止**：不改 `decide_spot_route`、不改 close+forward 固定 regular_spot 的路由、
   不改 `_ensure_close_spot_balance`（发单前划转逻辑与创建时余额检查是两层，后者修
   前者不动）、不改 DB schema、不改前端。

### 测试（验收 3-6）

- **新增**：provider 侧——close+forward（direction=REVERSE + task_type=close）→
  regular_spot 路由 → `spot_account_base_free` 被读取（对照既有
  `test_routing_close_forward_spot_only_keeps_close_sell_regular`，
  `test_hedge_preflight_provider.py:505-516`）；
  纯 `compute_preflight` 侧——REVERSE + regular_spot → available 取普通现货账户值；
  REVERSE + papi_margin → 仍用 `balances`（负向回归，逐字断言现状语义）。
- **THE 场景回归**（模拟）：普通现货 free=600、统一无 THE、close+forward 单次 200×2
  → `balance_ok=True`（不再误拦）；统一账户缺该币时 `available=600`。
- 全量回归：`python3 -m pytest backend/tests -q` 全绿 +
  `node frontend/self-check.js` 全绿。

## 不在本次范围

- 不改前端（弹框文案/来源正确，payload 由后端给）；
- 不改 `_ensure_close_spot_balance` 的划转/复检语义（另一层，已有 task 05 改造）；
- 不改 `decide_spot_route` / ADR / close+forward 固定 regular_spot 路由本身；
- 不动 `hedge_open_settings`、周期表、`executor_mode_snapshot`；
- 不新增「普通现货账户其余资产」读取——只读 close+forward 卖的那个 base。

## Allowed Files

可修改：

- `backend/hedge_open_tasks/domain.py`（`PreflightSnapshot` 字段 + `compute_preflight`
  REVERSE 分支 + docstring）
- `backend/services/hedge_preflight_provider.py`（新增 base 可用量读取 + `get_snapshot`
  regular_spot 分支接线；`_read_spot_account_usdt` 行为不变）
- `backend/tests/test_hedge_preflight_provider.py`（新增/适配测试）

只读：

- `reports/agent-runs/2026-08-06-hedge-order-close-validation/status.json`
- `backend/hedge_open_tasks/service.py`（:792-809 close 创建反转方向 + 余额检查调用点，
  只读理解，不改）

禁止：

- 未授权提交、移动 HEAD、访问凭证、对实盘发单/划转/设杠杆；
- 改 `_read_spot_account_usdt` 既有行为、改 FORWARD 分支、改路由决策；
- 为省事删减测试覆盖。

交接件：`reports/agent-runs/2026-08-06-hedge-order-close-validation/evidence/
2026-08-06-hedge-order-close-validation-close-forward-regular-spot-balance-fix.handoff.md`
（Bookkeeper 预检 `test ! -e` 通过，路径不存在；已存在则任务失败）

## Inputs

按 `AGENTS.md` §4 顺序读取：

1. `AGENTS.md`
2. 本 dispatch
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-06-hedge-order-close-validation/status.json`
6. `agents/roles.md` 的 `Implementer` 段 + `Task Handoff Evidence Contract` 段
7. `agents/developer-discipline.md`
8. `agents/skills/minimal-change-engineer.md`
9. `backend/hedge_open_tasks/domain.py`（`:869-906` PreflightSnapshot、`:970-1045`
   decide_spot_route、`:1183-1216` compute_preflight 余额门）
10. `backend/services/hedge_preflight_provider.py`（`:637-691` `_read_spot_account_usdt`
    （形状模板）、`:719-860` get_snapshot 组装）
11. `backend/tests/test_hedge_preflight_provider.py`（`:505-516` close+forward 路由测试）
12. `backend/hedge_open_tasks/service.py`（`:790-809` close 创建反转方向——只读）

## Acceptance Checks

1. **REVERSE 路由感知**：`compute_preflight` REVERSE 分支在 `regular_spot` 路由下用
   `spot_account_base_free`（缺失 → 0），非 regular_spot 用 `balances` 逐字不变；
   FORWARD 分支逐字不变。
2. **数据面**：`PreflightSnapshot.spot_account_base_free` 字段存在且默认 None；
   provider 仅 regular_spot 分支读取；`_read_spot_account_usdt` 行为不变（git diff
   不含其逻辑改动）；读失败 → snapshot 不组装（fail-closed）。
3. **THE 场景**：普通现货 free=600 / 统一无 THE / close+forward 200×2 →
   `balance_ok=True`、`available=600`；统一账户缺币不再误报「当前可用 0」。
4. **负向回归**：reverse 开仓 / close+reverse（papi_margin）余额语义与改动前
   逐字一致（既有测试零适配通过，若有适配须在交接件逐条说明）。
5. **回归**：`python3 -m pytest backend/tests -q` 全绿 + `node frontend/self-check.js`
   全绿；`git status --short` 仅列 Allowed Files。
6. **范围**：不改路由决策、不改 `_ensure_close_spot_balance`、不改前端、不改 DB。

## Stop

按 `AGENTS.md` §7 返回完整中文 `[TASK_RESULT v2]`（含三行中文交接），`下一步任务` 用
可执行形式 `读取：<路径或 none>；执行：<立即动作>；关卡：<下一验证>`。

下一关卡：Human 重启服务（加载新代码）后实盘复测——THE 普通现货 600 / 合约空 400，
开 forward close 200×2：**不再被误拦**，面板与交易所一致。修复经核验后按 §8
（HIGH_RISK：平仓余额门）走 review-1 + review-2；`rework_count` 递增一次
（响应缺陷的修复交付）。

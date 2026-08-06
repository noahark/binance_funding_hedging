# Task Handoff: 2026-08-06-hedge-order-close-validation-spot-only-route-fix

## Source Report (author-only; immutable after task end)

- task_id: `2026-08-06-hedge-order-close-validation-spot-only-route-fix`
- role: Implementer（target_role 按 dispatch）
- target_model: deepseek（Human 指定，provider 按 `agents/roles.md` 映射）
- stage_id: `2026-08-06-hedge-order-close-validation`
- created_at: `2026-08-06 13:05:53 CST`
- base_sha: `f153cdc38469a3fde80d7d2f79682d4d7aa23df8`
- delivery_sha: `pending`（本任务未授权提交——dispatch 禁止未授权提交；改动在工作树，Bookkeeper 核验后定交付 SHA）

### 任务背景

THEUSDT forward 开仓实测：现货腿被发到 `/papi/v1/margin/order`（全仓杠杆）→ 交易所
`-51023 Trading pair does not exist.`（THEUSDT 在 PAPI margin 不存在）→ fail-closed 拒绝。
THE 的 `route_class = SPOT_ONLY_CANDIDATE`（公开现货 `isMarginTradingAllowed=False`）——
`decide_spot_route` 输入缺「仅现货」状态，漏判为可走全仓。

### 实际修改范围

1. `backend/hedge_open_tasks/domain.py`（Allowed）：
   - 新增 reason 常量 `ROUTE_REASON_SPOT_ONLY_REGULAR = "spot_only_regular_spot"`，
     附注释说明它是 provider 层前置强制、不是 `decide_spot_route` 的新规则分支。
   - `decide_spot_route` / `spot_route_endpoint` 本体逐字未改。
2. `backend/services/hedge_preflight_provider.py`（Allowed）：
   - `_read_spot_leg` 返回元组从 `(filters, tradable, symbol, base_asset)` 追加为
     `(filters, tradable, symbol, base_asset, is_margin_trading_allowed)`，字段来自现货
     原始记录 `isMarginTradingAllowed`，缺失/不可读按 `False` 保守处理；两条 return 路径
     （tradable 与 non-tradable）都透传，docstring 同步更新。
   - `get_snapshot` 解包追加第 5 元素 `spot_margin_allowed`；在调 `decide_spot_route`
     之前插入前置强制：`not spot_margin_allowed and direction==DIR_FORWARD and
     task_type != TASK_TYPE_CLOSE` → `(regular_spot, spot_only_regular_spot)`，强制后
     `regular_spot` 特有的标准现货账户/现货 rate-limit 读取照常执行；其余情况（含全部
     close 路径与 reverse）仍走 `decide_spot_route` 既有规则，逐字不变。
3. `backend/tests/test_hedge_preflight_provider.py`（Allowed）：
   - `_spot_sym` 增加 `margin_allowed=True` 默认参数（写入 `isMarginTradingAllowed`），
     既有测试语义（MARGIN_SPOT）不变；`_BstockUrlopen._spot_symbol` 补
     `isMarginTradingAllowed: True`（TSLABUSDT bStock 是 MARGIN_SPOT 语义，TRADIFI 规则不变）。
   - 新增 5 条测试：
     - `test_routing_forward_spot_only_selects_regular_spot`：THEUSDT
       `isMarginTradingAllowed=False` forward 开仓 → `regular_spot` +
       `spot_only_regular_spot` + `/api/v3/order`，并断言 regular_spot 特有读取发生。
     - `test_routing_forward_margin_spot_stays_papi_when_no_cap_hit`：MARGIN_SPOT 回归 →
       仍 `papi_margin`（dispatch 验收 2）。
     - `test_routing_close_forward_spot_only_keeps_close_sell_regular`：仅现货
       close+forward（卖现货）→ 仍 `regular_spot` + `close_sell_regular_spot`（不被强制劫持）。
     - `test_routing_close_reverse_spot_only_keeps_papi`：仅现货 close+reverse → 仍
       `papi_margin`。
     - `test_routing_reverse_spot_only_keeps_papi`：仅现货 reverse 开仓 → 仍 `papi_margin`
       （决策 §E-1 保留，cap 列表不读）。

### 结论

- 修复完成：仅现货标的 forward 开仓的现货腿强制走普通现货端点 `/api/v3/order`
  （regular_spot），不再发到全仓杠杆；MARGIN_SPOT/正常标的行为与 close/reverse 路径
  逐字不变（回归断言覆盖）。
- **-2027 排查结论（只排查，未改代码）**：
  - `-2027` 是 Binance UM（USDT-M 合约）错误码：`Exceeded the maximum allowable
    position at current leverage.`（超出当前杠杆下的最大允许仓位）。仓库内无该码任何
    代码/证据记录（不在 `FATAL_EXCHANGE_CODES`、`AUTH_AMBIGUOUS_EXCHANGE_CODES`、
    `INSUFFICIENT_FUNDS_CODES`、业务码表），`classify_exchange_code` 对它会落到
    `ERROR_CATEGORY_UNCLASSIFIED`（known non-fatal rejection 处理路径）。
  - 依据（为什么倾向「事实」而非本地数量计算 bug）：
    1. 该上限由交易所按（symbol 分档 `maxNotional`、当前杠杆倍数、已有持仓）**实时**
       计算，本地 preflight 不读取杠杆/档位信息，也无法预知；
    2. preflight 数量路径（`compute_preflight`：`floor_to_grid` + `_check_common_quantity`
       的 LOT_SIZE/MIN_NOTIONAL 检查 + 余额门槛）不存在本地把名义价值算虚高的路径；
    3. 最可能事实：THE 合约当时已有仓位 + 当前杠杆档位下新开仓超限（或该币杠杆档位
       上限低）。
  - 未完全定论原因：数据已清理（库记录清空）、交易所 THE 仓位已由 Human 手工平仓，
    复测当时日志不可得；**需要 Human 复测 SPOT_ONLY 开仓时带上核实点**：请求的合约
    quantity/名义价值、当时 THE 合约已有持仓、当前杠杆倍数（`/fapi/v1/positionRisk`）、
    该 symbol 分档 `maxNotional`。若复测仍现 -2027 且持仓为 0、数量远低于档位上限，
    才构成数量超限 bug 的可疑信号。
  - 附带发现（不改）：`-2027` 目前分类为 unclassified，若确认是常态事实可后续考虑
    明确分类；不在本次范围。

### 命令与结果

- `.venv/bin/python3 -m pytest backend/tests/test_hedge_preflight_provider.py -q` → `27 passed`
- `.venv/bin/python3 -m pytest backend/tests/test_hedge_cycle_close.py backend/tests/test_hedge_cycle_core.py backend/tests/test_hedge_cycle_backfill.py -q` → `61 passed`
- `.venv/bin/python3 -m pytest backend/tests -q` → `1426 passed`（全量后端回归全绿）
- `node frontend/self-check.js` → 全部自检通过
- `git status --short`：`M backend/hedge_open_tasks/domain.py`、`M backend/services/hedge_preflight_provider.py`、`M backend/tests/test_hedge_preflight_provider.py`（本次交付）；`M reports/agent-runs/ACTIVE.json`（stage 打开时既有的控制文件改动，非本任务引入）；`?? reports/agent-runs/2026-08-06-hedge-order-close-validation/`（stage 目录）。无前端/ledger/白名单/实盘写。

### 未完成事项 / 不能假设

- 未提交（dispatch 禁止未授权提交）；未实盘复测（需 Human 重启服务 + 授权）。
- 仅现货强制只覆盖 **open+forward**；仅现货 **open+reverse** 目前仍走 `papi_margin`
  （决策 §E-1 逐字保留）——若 SPOT_ONLY 标的 reverse 开仓也被实测拒绝（同 -51023 家族），
  属另一处需单独决策的范围，本任务未改。
- close+reverse 对仅现货标的仍走 `papi_margin`（与 open+reverse 同族），未改。

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-06-hedge-order-close-validation/status.json`
  2. `backend/services/hedge_preflight_provider.py`（`_read_spot_leg` 约 250 行、`get_snapshot` 约 467 行）
  3. `backend/hedge_open_tasks/domain.py`（`ROUTE_REASON_*` 约 447 行、`decide_spot_route` 约 950 行）
  4. `backend/tests/test_hedge_preflight_provider.py`（`test_routing_forward_spot_only_*` 等新增用例）
- 执行：Bookkeeper 核验工作树改动 + 回归记录，定 `delivery_sha`；Human 重启服务实盘复测
  SPOT_ONLY 标的（THE）forward 开仓是否走 `/api/v3/order` 并成功，同时按本报告 -2027 核实点
  记录 THE 合约腿错误上下文。
- 关卡：Human 实盘复测 + 本 stage 下一验证任务。
- 不能假设的事实：数据已清理、应用服务当前停止（`PROJECT_STATE.md` Current Status）；
  THE 现货 `isMarginTradingAllowed` 实测为 False（旧 archive 中 2026-07-03 记录为 True，
  以实时 exchangeInfo 为准）；`-2027` 无历史证据，须复测取证。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

[TASK_RESULT v2]
任务 ID: 2026-08-06-hedge-order-close-validation-spot-only-route-fix
执行结果: completed
结果摘要: SPOT_ONLY 现货路由修复完成：仅现货 forward 开仓强制 regular_spot（/api/v3/order），
decide 规则与 close/reverse 不变；新增 5 条路由回归，全量 1426 passed、self-check 全绿；
-2027 排查结论为大概率账户事实（THE 合约杠杆档位上限），缺复测日志待 Human 实盘核实。
产物: [reports/agent-runs/2026-08-06-hedge-order-close-validation/evidence/2026-08-06-hedge-order-close-validation-spot-only-route-fix.handoff.md]
检查结果: [透传 is_margin_trading_allowed pass；仅现货强制 regular_spot pass；MARGIN_SPOT 回归 papi_margin pass；close/reverse 回归 pass；全量回归 1426 passed + self-check 全绿 pass；范围核对仅 provider/domain/测试文件 pass；-2027 排查结论记录 pass]
阻塞项: [none]
本地北京时间: 2026-08-06 13:05:53 CST
下一步模型: deepseek（Bookkeeper，按 status.json bookkeeper 字段；Human 启动其终端核验并封存本任务）
下一步任务: 读取：reports/agent-runs/2026-08-06-hedge-order-close-validation/status.json + evidence/2026-08-06-hedge-order-close-validation-spot-only-route-fix.handoff.md；执行：核验工作树改动与回归记录、定 delivery_sha；关卡：Human 重启服务实盘复测 SPOT_ONLY 标的开仓（THE /api/v3/order）+ 下一验证任务
[/TASK_RESULT]

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- verified_at: `2026-08-06 18:40:28 CST`
- source_sha256: `5be867b8140073253e5fe37c7977d76e18b001cdae17a2ffc8984c0106657612`
- status_revision: 1（本任务 reported 时状态；封存时随 03 一次性提交，status.json 现指向 03）
- base_sha / delivery_sha: `f153cdc38469a3fde80d7d2f79682d4d7aa23df8` .. `ee7ec4f3a41db8d896652101fcd1821972b381bc`（Human 授权一次性提交 stage 全部工作树改动）
- verdict: **verified（通过）**
- 依据（可复现）：
  - `python3 -m pytest backend/tests -q` → **1446 passed**（本 Bookkeeper 实测；含 5 条新增 SPOT_ONLY 路由测试）
  - `hedge_preflight_provider.py:264/532/560`：`is_margin_trading_allowed` 透传 + `not spot_margin_allowed and direction==forward and task_type!=close` 前置强制；`domain.py` `ROUTE_REASON_SPOT_ONLY_REGULAR`
- 后续状态：01 `reported` → `verified`；Human 实盘复测时带上 -2027 核实点

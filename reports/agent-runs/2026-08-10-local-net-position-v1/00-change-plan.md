# 本地剩余净持仓口径改造文稿

状态：待独立计划评审；本文不授权实现、实盘操作、数据库写入、服务重启或部署。

## 1. Human 已决定

- stage：`2026-08-10-local-net-position-v1`。
- 实现模型：`claude_glm`（Zhipu GLM provider）。
- 目标：修正部分平仓后持仓表把累计开仓量误当剩余持仓量的问题。
- 方案：不向 `hedge_open_cycle` 增加数量列；以现有成交腿记录为唯一数量账本，按活跃周期逐腿计算“开仓实际成交量减平仓实际成交量”。
- 本 stage 一次性评审例外：实现后只做 review-1；review-1 `ACCEPT` 且 Bookkeeper 核验通过后，Human 已授权把 stage 分支合并到 `main`。本例外不推广到其他 HIGH_RISK 任务，不授权部署、服务重启、开关调整或实盘操作。
- HIGH_RISK 实施前独立跨 provider 计划评审仍保留。

## 2. 已观察问题与证据

XVGUSDT 活跃周期最初双腿各成交 `50000`，之后两个 close attempt 双腿各成交 `10000`。交易所当前现货与 UM 空仓均为 `30000`，但 `aggregate_positions()` 只读取 `task_type=open`，所以本地 `spot_qty/perp_qty` 仍为 `50000`，`drift` 被误触发。

代码锚点：

- `backend/hedge_open_tasks/store.py:2444-2484`：持仓聚合只查询 open 腿。
- `backend/hedge_open_tasks/store.py:2590-2635`：任何正的实际成交量都会进入数量聚合，价格未知不影响数量真值。
- `backend/hedge_open_tasks/domain.py:1983-2022`：`single_leg_exposure` 与 `drift` 直接消费本地 `spot_qty/perp_qty`。
- `backend/tests/test_hedge_cycle_close.py:106-129`：当前测试明确冻结了“close 后数量不减”的旧行为。

## 3. 唯一数量语义

对每个未关闭 `cycle_id`、每条腿独立计算：

```text
spot_remaining_qty = Σ(open spot cumulative_base_qty) - Σ(close spot cumulative_base_qty)
perp_remaining_qty = Σ(open perp cumulative_base_qty) - Σ(close perp cumulative_base_qty)
position_qty = direction_sign × perp_remaining_qty
direction_sign: forward=-1, reverse=+1
```

“实际成交量”只认 `hedge_open_leg.cumulative_base_qty > 0`，不以 task `done`、pair `success`、order literal status 或两腿同时成功为前提。这样必须覆盖：

- `FILLED`；
- `CANCELED/PARTIALLY_FILLED/EXPIRED` 但累计成交量大于零；
- 单腿成交；
- 先 UNKNOWN/QUERYING，后由 reconcile 写入的最终累计成交量；
- 已删除任务中不可抹除的真实成交。

没有实际成交量的失败腿贡献零。不得从计划数量、`success_count`、`accepted_pair_count` 或目标数量推导持仓。

## 4. 必须保持不变的语义

1. `spot_avg/perp_avg` 仍是开仓成本基，只统计 open 腿的已知成交额和对应 priced quantity；close 腿不得进入开仓均价分子或分母。
2. `hedge_open_cycle` 仍只负责周期身份与开启/关闭状态，不新增剩余数量字段，不做 schema migration、历史回填或双写缓存。
3. 已关闭周期继续从持仓表根查询排除；历史页继续读取 `hedge_open_cycle_close_log`。
4. API 字段集合不变；只修正既有 `spot_qty`、`perp_qty`、`position_qty` 的值语义为“本地账本剩余量”。
5. `merge_positions` 的账户可读性、账户求和、1% 两腿差容差、现货身份解析和 unavailable-source 行为不变；它自然消费修正后的本地净量。
6. 不改下单数量、方向、路由、预检、闸门、周期关闭、借还款、划转、交易所查询或前端交互。
7. legacy `hedge_open_fill` 空壳与其现有异常告警策略保持不变，不为无 `cycle_id` 的历史路径发明平仓语义。
8. 1000x 乘数合约继续维持现有 fail-closed/已知限制，本 stage 不恢复、不换算。

## 5. 最小实现边界

预计只需修改中央聚合：

- `backend/hedge_open_tasks/store.py`
  - SQL-B 同时读取 open/close，带出 `t.task_type`；仍只保留未关闭周期。
  - 数量聚合对 open 使用 `+q`、close 使用 `-q`，每条腿独立。
  - 成本与均价聚合只让 open 腿贡献。
- 测试：优先修改/补充现有 close、store、merge 与 API 测试，不新建测试框架。
- `docs/api/public-market-contract.md`：追加既有三个本地数量字段的剩余净量语义；不复制实现流程。

若实现者发现必须修改上述边界外的生产文件，应停止并报告 blocker，不得自行扩域。

## 6. 验收检查

1. XVG 回归形状：open `50000`，两次双腿 close 各 `10000`，输出 spot/perp `30000`、forward `position_qty=-30000`，开仓均价保持原值。
2. 双腿部分平仓：open `0.5`、close `0.2` 后两腿剩 `0.3`，`single_leg_exposure=false`；实际账户也为 `0.3` 时 `drift=false`。
3. 单腿 close：只减真实成交的一腿，剩余两腿不等并触发既有 `single_leg_exposure`；不能按 pair 失败而忽略成交腿。
4. 部分成交终态：literal status 非 `FILLED` 但 `cumulative_base_qty>0` 时仍减对应腿。
5. 零成交失败：不改变剩余量。
6. reverse：两腿数量同样按 open-close 得到剩余绝对量，`position_qty` 保持正号。
7. 部分平仓后再加仓：同一 cycle 内所有 open 加总、所有 close 扣减，起始时间与 cycle_id 不变。
8. 已删除但有真实成交的 open/close 任务仍参与；既有 `includes_deleted_task` 语义保留。
9. 周期关闭后该行仍不出现在持仓表；API 固定字段集合不变。
10. 现有开仓成本基、价格未知标志、周期拆桶、身份冲突告警、账户不可读降级测试全部通过。

建议最小测试命令：

```bash
.venv/bin/python -m pytest \
  backend/tests/test_hedge_cycle_close.py \
  backend/tests/test_hedge_cycle_core.py \
  backend/tests/test_hedge_store.py \
  backend/tests/test_positions_merge.py \
  backend/tests/test_hedge_api.py
```

实现者还应对自己实际触碰的模块运行已有相邻测试；不得启动服务或触碰 live DB。

## 7. 计划评审重点

独立计划评审必须确认：

- 上述逐腿净额能覆盖 immediate resolve、UNKNOWN reconcile、rate-limited settlement 与单腿/部分成交，而无需给每条写路径增加数量双写；
- 成本基与当前剩余数量已经彻底拆开，不会用净量作开仓均价分母；
- 不改 `domain.py` 是否足够，若不足必须给出当前代码链证据和最小文件扩域；
- 测试可证明“部分平仓误报修复”且不会把真实单腿平仓掩盖；
- 本 stage 的 review-2 豁免与合并授权只是一条 Human 流程决定，不改变产品代码验收口径。


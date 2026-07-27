# Fix — Review-2 REWORK (S5 filter wiring) — Hedge Open Live Hardening v1

执行角色：后端修复实现者（写权限 Claude-GLM / `glm-5.2[1m]` 会话）。本会话仅在本仓库
的本地源码与测试中完成限定修复；未调用、启动或转派任何其他模型会话；未访问凭据、未发起
任何 Binance 请求、未启动服务、未改动实盘闸门、未下单、未提交 git。修复范围严格遵守
`60-fix-review-2-s5.dispatch.md` 内 VERBATIM 的 `fix_start_prompt` 与
`11-adr.md` ADR-H4。

## P2 finding（必须修，已修）

`RecordTransportExecutor.execute` 对两腿调用 `validate_order_params(...)` 时未传
`step_size` / `min_qty` / `max_qty`（原 `executor.py:303-304`）。校验器
`wire_constraints.py:102-119` 已实现这三个可选检查，因此 `q_common=0.0005` 与两腿
`step_size=min_qty=0.001` 仍被 record transport 模拟为 `success`；同一 params 带过滤
条件直接校验会被拒绝。影响是 S5 承诺的“离线传输拒绝已加载 symbol filters 的 quantity
precision/bounds”在默认 dry-run record transport 中没有兑现。

### 根因

`compute_preflight` 产出的 `snapshot_record` 此前只含 `spot_step` / `perp_step`
（`effective_market_step` 解析后的有效步长），不含 `min_qty` / `max_qty`；且 record
transport 从不消费 snapshot 里的步长——这些字段对它而言是死数据。要让校验器真正生效，
必须把每腿的有效 step/min/max 一路送达 record transport 的 `validate_order_params`。

## 修改的文件与行

### 1. `backend/hedge_open_tasks/domain.py`（`compute_preflight`，约 760–771 行）

在 `snapshot_record` 构建处，用**现有私有** `_qty_bounds(filters)`（与
`effective_market_step` 同一套 MARKET_LOT_SIZE 优先、LOT_SIZE 回退语义；`min`/`max`
各自独立回退）为 spot/perp 计算有效 min/max，并 **additive** 写入 `snapshot_record`：

```python
spot_min, spot_max = _qty_bounds(snapshot.spot_filters)
perp_min, perp_max = _qty_bounds(snapshot.perp_filters)
snapshot_record = {
    "available": True,
    "spot_step": str(spot_step),
    "perp_step": str(perp_step),
    "spot_min_qty": str(spot_min) if spot_min is not None else None,
    "spot_max_qty": str(spot_max) if spot_max is not None else None,
    "perp_min_qty": str(perp_min) if perp_min is not None else None,
    "perp_max_qty": str(perp_max) if perp_max is not None else None,
    "grid": str(grid),
    "est_price": ...,
    "position_mode": snapshot.position_mode,
}
```

- 不重复实现过滤选择规则：`step` 仍由 `effective_market_step` 解析、`min/max` 仍由
  `_qty_bounds` 解析，只在 `compute_preflight` 执行一次，record transport 只消费结果。
- `None` 表示该 bound 在本 symbol 上被禁用（与 `_qty_bounds` 语义一致），下游据此跳过。
- snapshot 其余分支（`no_preflight_snapshot` / `symbol_not_trading` /
  `position_mode_not_one_way` / `step_unreadable`）的 record 不含这些字段，保持原样。
- 这是 additive 字段：`snapshot_record` 存为 JSON TEXT（`store.py` 既不校验字段集合，
  也无任何测试对其键集合做精确断言——已 grep 确认唯一字段访问是 `["available"]`），
  因此无 schema 迁移、无契约修订、不破坏既有持久化或测试。

### 2. `backend/hedge_open_tasks/executor.py`

**(a) `RecordTransportExecutor.execute`（约 297–310 行）** — 两腿
`validate_order_params` 调用改为传入每腿的有效 grid/bounds；同步把上方注释从“格式类
缺陷”扩展为“格式类缺陷**或**违反本 symbol 已加载 grid/bounds 的 quantity”：

```python
violations = [f"spot: {v}" for v in validate_order_params(
    spot_params, **_leg_qty_filters(ctx.preflight_snapshot, "spot")
)]
violations += [f"perp: {v}" for v in validate_order_params(
    perp_params, **_leg_qty_filters(ctx.preflight_snapshot, "perp")
)]
```

**(b) 新增 `_leg_qty_filters(preflight_snapshot, leg)`（约 367–389 行）** — 从
`ctx.preflight_snapshot` 读取 `{leg}_step` / `{leg}_min_qty` / `{leg}_max_qty`，组装成
`validate_order_params` 的关键字参数；字段缺失（dry-run 无已加载 filter，或某 bound 在本
symbol 禁用）则省略，校验器按 disabled 处理——与 `compute_preflight` 语义一致。源与既有
`_snapshot_price`（同从 `preflight_snapshot` 读 `est_price`）一致，单一来源，不再读
`filter_versions`。

### 3. `backend/tests/test_hedge_wire_constraints.py`（约 216–310 行，末尾追加）

不动既有 `_ctx`；新增模块级 helper `_ctx_with_qty_filters(spot, perp, *, q_common)`，
其 `preflight_snapshot` 携带 `{leg}_step`/`{leg}_min_qty`/`{leg}_max_qty`，精确模拟
`compute_preflight` 的真实产出。新增三个端到端行为测试（**不是**只直接测
`validate_order_params`）：

| 测试 | 断言 |
| --- | --- |
| `test_record_transport_rejects_quantity_violating_loaded_filters`（parametrize 两例：`0.0005` 同时违反 step+min；`200` 违反 max） | 两腿 `REJECTED` + `offline_constraint` + `constraint_violations` 含对应违规 + `filled_qty=="0"`（不模拟 fill）+ `posted is False` |
| `test_record_transport_accepts_grid_aligned_quantity_with_loaded_filters`（`q_common=0.003`） | `success`、无 `constraint_violations`、`filled_qty=="0.003"`（合法 grid 仍模拟成交） |
| `test_record_transport_applies_per_leg_filters_independently`（spot step `0.001`、perp step `0.01`、`q_common=0.005`） | 仅 `perp:` 前缀违规、无 `spot:` 违规 —— 证明每腿独立采用自己的 filter，而非单一共享 filter |

第三个测试同时满足“覆盖 spot/perp 过滤条件可不同的情形”这一要求。

## 逐项命令结果

按 `60-fix-review-2-s5.dispatch.md` 指定的精确测试命令逐项执行：

```text
.venv/bin/python -m pytest backend/tests/test_hedge_wire_constraints.py backend/tests/test_hedge_executor.py backend/tests/test_live_hedge_executor.py backend/tests/test_hedge_service.py backend/tests/test_hedge_api.py backend/tests/test_hedge_store.py backend/tests/test_hedge_preflight_provider.py -q
→ 176 passed in 18.50s   （PASS；相对 review-2 基线 172 +4：reject×2 + accept + per-leg）

node frontend/self-check.js
→ 122 [PASS]，全部自检通过   （PASS；与 review-2 实测一致，本修复未触碰 frontend）

git diff --check
→ EXIT=0   （PASS；无空白/冲突标记）
```

`git status --short` 显示改动仅在允许范围内：

```text
 M backend/hedge_open_tasks/domain.py
 M backend/hedge_open_tasks/executor.py
 M backend/tests/test_hedge_wire_constraints.py
```

### 生产路径完整性验证（额外，无网络）

用 `test_hedge_service._spot_filters/_perp_filters`（与 live provider 同型 filter 结构）
驱动 `compute_preflight`，确认每腿有效 min/max 正确落进 `snapshot_record`，且
`_qty_bounds` 的 per-constraint 回退生效：

```json
{
  "available": true,
  "spot_step": "0.00001",     "perp_step": "0.001",
  "spot_min_qty": "0.00001",  "spot_max_qty": "9000",
  "perp_min_qty": "0.001",    "perp_max_qty": "120",
  "grid": "0.00100", "est_price": "50000", "position_mode": "BOTH"
}
```

- `spot_min_qty=0.00001`：spot MARKET_LOT_SIZE `min_qty=0`（禁用）→ 回退 LOT_SIZE `0.00001`。
- `perp_max_qty=120`：取 MARKET_LOT_SIZE `120`，而非 LOT_SIZE `1000`（per-constraint 回退，
  不会因选了一种 filter 就丢掉另一边的 bound）。

## 安全/约束自检

- **ADR-H4 保持**：`wire_constraints` 仅被 record transport（与测试假件）消费；**未**导入
  或挂接到 `backend/services/live_hedge_executor.py`、`hedge_open_live_client.py` 或任何
  真实发送路径；`live_hedge_executor.py` 一行未改。
- **冻结词表不变**：状态枚举、`entries` 的 `overall_result`/`next_action` 词表、settings
  doc、`create_task` 错误码、`clientOrderId` 推导（`hg{attempt_id}{s|p}`）、`fmt_decimal`、
  S1–S4、S3 CAS 全部未动；`snapshot_record` 的四个新字段是 additive。
- **既有测试为何仍绿**：`compute_preflight` 保证 `q_common=floor_to_grid(single_amount,
  lcm(spot_step,perp_step))` 必然是两腿 step 的整数倍，`_check_common_quantity` 已校验
  min/max/notional——故任何合法创建的 task 在 record transport 的新 grid 校验下仍通过；
  `test_hedge_review2_regressions.py` 走 live dispatch（不经该校验）；现有 record-transport
  端到端测试的 `preflight_snapshot` 不含 step/min/max → 读不到 → 跳过（行为不变）。
- **未触碰禁止面**：`frontend/**`、`backend/services/live_hedge_executor.py`、
  `hedge_open_live_client.py`、`backend/app/server.py`、DB schema/迁移、实盘配置/数据、
  既有 review 原始证据、`status.json`、`70-handoff.md` 均未改；无网络、无凭据、无真实 POST。
- **未 commit**；未更新 `status.json` / `70-handoff.md`。

## Footer

```
当前 Session ID: unavailable (Claude Code 会话未向执行体暴露 provider-native session id；与 60-fix-review-2-s5.dispatch.md 自身 footer 的判定一致)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-live-hardening-v1/40-fix-review-2-s5.md
本地北京时间: 2026-07-28 00:00:59 CST
下一步模型: bookkeeper
下一步任务: R4 对账 → 合并态重跑 → 证据 commit → 新 base..head 与指纹 → 后端 review-1（与新代码 provider 隔离）→ review-2 重开；rework_count 现为 1/3
```

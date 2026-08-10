# Plan Review F-1 Counter-Evidence

- captured_at: `2026-08-10 12:19:28 CST`
- branch_head: `38a384045382a10352d80e0546ec47277c460a60`
- purpose: Planner 对首轮计划评审 F-1 的只读裁定证据；不授权实现。

## 1. Live 顺序

`backend/hedge_open_tasks/service.py:2738-2795` 的 live close 顺序是：fresh preflight → `_close_um_position_error` → forward 现货余额门 → `prepare_attempt`。`_close_um_position_error` 在 `service.py:1830-1879` 明确把 UM 零仓、方向不匹配、可平数量不足和读取失败全部变成错误；调用方在错误时暂停并返回，`prepare_attempt` 不会执行。

周期正常关闭路径 `service.py:1907-1919` 在交易所 flat 核实后调用 `close_cycle`。2026-08-10 的 XLM `manual_verify` 也在 UM 已确认归零、Human 完成人工收口后补录，不支持“周期已合法关闭但 UM 仍有可平仓位”的前提。

## 2. 当前本机数据

查询一：按 `cycle_id` 汇总正的 `cumulative_base_qty`，筛选 close 有成交且 open spot/perp 均为 0。结果：`0 rows`。

查询二：筛选 `task_type=close AND status IN ('paused','running')`，并检查相同 symbol/direction 是否仍有 active cycle。结果：`0 rows`。

这两项是 2026-08-10 12:19 CST 的只读快照，只证明当前不存在该形状，不宣称未来永远不可达。

## 3. 已有可执行检查

```text
.venv/bin/python -m pytest backend/tests/test_hedge_cycle_close.py \
  -k 'close_um_gate_requires_matching_sign_and_remaining_qty or close_um_guard_failure_pauses_before_attempt_or_post' -q

..........                                                               [100%]
10 passed, 56 deselected in 0.27s
```

这些测试覆盖 UM 零仓、方向不匹配、数量不足、不可解析，以及 guard 失败时 attempt 列表为空。

## 4. 裁定

首轮 F-1 缺少能同时满足“周期已关闭”与“live UM 门仍放行”的当前证据；其 R2 还要求在 UM flat 后 reduce-only 合约腿成交，与 live 交易语义冲突。该 finding 不满足用当前交付阻塞的证据门。

如果以后取得 stale cache 或其他路径越过 UM 门并产生实际 close-only fill 的 raw trace，应以该 trace 重开；届时优先修派发门或增加明确异常标记，不静默隐藏成交桶。


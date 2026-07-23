# Fix-3 — hedge-be（stage 2026-07-hedge-open-live-v1）

执行者：Claude-GLM（zhipu_glm，经 Claude Code）。
任务 prompt：`reports/agent-runs/2026-07-hedge-open-live-v1/task-hedge-be-fix-3.prompt.md`。

## 根因（用户产品语义澄清，非 review REWORK）

用户 2026-07-23 明确：**每次双腿成交暂时不做成交数量校验**。原因是正反向下单方式
不同——现货市价买只能传 `quoteOrderQty`（总 USDT 金额），合约买卖与现货卖传
`quantity`——双腿成交的基础币数量本就无法预先对齐（详见
`reports/agent-runs/2026-07-hedge-open-live-v1/design-inputs.md` DI-6）。因此 fix-2 中
`classify_attempt` 在双腿都 FILLED 时还要求 `spot_qty == perp_qty`、量不等就判
`single_leg_exposure` 的逻辑与真实下单方式不符，需移除该成交数量校验。

下单参数模型本身（现货市价买用 `quoteOrderQty`、正反向下单方式差异、共同网格取整在
正向不适用）属真实 API 轮重构范围，DI-6 已记录，**本轮不改**。

## 改动位置（文件边界内）

允许文件：`backend/hedge_open_tasks/domain.py`、`backend/tests/test_hedge_*.py`。实际
仅触及 `domain.py`、`test_hedge_domain.py`、`test_hedge_executor.py`（外加验收要求
追加的 `60-test-output.txt`）。

1. `backend/hedge_open_tasks/domain.py` — `classify_attempt`
   - 双腿都 FILLED → `ATTEMPT_SUCCESS`（**删除** `Decimal` 比较 filled_qty 与
     量不等→exposure 的分支）。
   - 恰好一腿 FILLED → `ATTEMPT_SINGLE_LEG_EXPOSURE`（不变）。
   - 都未 FILLED → `ATTEMPT_FAILED`（不变）。
   - docstring 更新：去掉“qty 必须相等”措辞，注明暂不做成交数量校验、见 DI-6、下单
     参数模型留真实 API 轮。

2. `backend/hedge_open_tasks/domain.py` — 常量注释 / `build_leg_exposure` docstring
   - `ATTEMPT_SUCCESS` 行注释：`both legs FILLED at aligned qty` →
     `both legs FILLED (no executed-qty check, see DI-6)`。
   - `build_leg_exposure`：**函数逻辑与 both→None 防御分支不动**（task 注：不用改、可
     保留无害）；仅顺带清理因本次改动而失真的 docstring 尾段——去掉“双腿量不等→
     escalated / 经由 exposure_alert 暂停”的旧表述，改为说明 both-filled 现走 success、
     不再路由到此处，both→None 为防御性 guard（task 给予的“顺带清理，不强制”路径）。

3. `backend/tests/test_hedge_domain.py`
   - `test_classify_qty_mismatch_is_exposure` → 重命名为
     `test_classify_both_filled_mismatched_qty_is_success`，断言由
     `ATTEMPT_SINGLE_LEG_EXPOSURE` 改为 `ATTEMPT_SUCCESS`（锁住新语义：双腿 FILLED 但
     filled_qty 不等 → success）。
   - `test_build_leg_exposure_none_when_both_filled_mismatched`：断言（`is None`）不变
     （`build_leg_exposure` 未改），仅修正其失真注释。
   - 单腿失败 → exposure、累计 >3 → 暂停、双腿量相等 → success 等断言**保持不变**。

4. `backend/tests/test_hedge_executor.py`
   - `test_seed_qty_mismatch_is_single_leg_exposure` → 重命名为
     `test_seed_qty_mismatch_is_success`；`out.category` 断言由
     `ATTEMPT_SINGLE_LEG_EXPOSURE` 改为 `ATTEMPT_SUCCESS`（`OutcomeSpec.qty_mismatch`
     为双腿 FILLED 量不等，新语义下走 success）；`out.exposure is None` 保持（success
     不建 leg_exposure）。修正注释。

`Decimal` 仍被 `compute_preflight`/`floor_to_grid` 等广泛使用，无 orphan import。

## 测试结果

`python -m pytest backend/tests -q`（`.venv/bin/python`，Python 3.11.15，
pytest-8.3.5）：

```text
790 passed in 45.35s
exit_code=0
```

基线 790（fix-2 段）。本轮无增删测试（改名 2 个、改断言），总数仍为 790，全绿。完整
输出已追加到 `reports/agent-runs/2026-07-hedge-open-live-v1/60-test-output.txt`，新起
`===== hedge-be fix-3 (Claude-GLM) 自测：python -m pytest backend/tests -q =====` 段，
既有段保留。

锁定语义的测试单独复核通过（`-v`）：`test_classify_both_filled_mismatched_qty_is_success`、
`test_seed_qty_mismatch_is_success`、`test_classify_both_filled_aligned_is_success`、
`test_classify_one_filled_one_rejected_is_exposure`、`test_classify_neither_filled_is_failed`。

## 非目标（本轮不做，留真实 API 轮）

- 下单参数模型（现货市价买 `quoteOrderQty`、正反向下单方式差异、共同网格取整在正向
  不适用）——DI-6 记录为真实 API 轮重构，本轮不改。
- 不动共同网格取整逻辑、preflight、executor、scheduler、server.py、frontend、borrow、
  docs、status.json。无新依赖、无真实网络。

## R10 / 收尾

- 未 commit、未改 `status.json`、未转派任何其他模型会话或 adapter 命令；写完即停，
  交 bookkeeper。
- 当前分支 `stage/2026-07-hedge-open-live-v1`，HEAD `f4f8ea0`（未提交）；working tree
  仅 `domain.py`、`test_hedge_domain.py`、`test_hedge_executor.py`、`60-test-output.txt`
  四处变更。

```text
当前 Session ID: 214355bb-da09-42c0-8cba-f62159824220 (Claude Code runtime；GLM provider-native id 模型自身不可见)
Session ID 来源: runtime_env (CLAUDE_CODE_SESSION_ID)
原始输出路径: reports/agent-runs/2026-07-hedge-open-live-v1/60-test-output.txt
本地北京时间: 2026-07-23 09:33:47 CST
下一步模型: bookkeeper（人工）
下一步任务: bookkeeper 收集 fix-3 证据、重算 diff fingerprint、按 routing 派发 review-2 round-2（Codex/GPT 优先）
```

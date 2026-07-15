# Kimi Formal Review-1 结论：ACCEPT（含一条非阻塞 P3 观察）

## 评审摘要

我按 `review-1-kimi.prompt.md` 的绑定范围审查了提交
`8aac137..60c91f7`，独立核对了 `diff_fingerprint`、源码、测试与 stage
校验器。实现仅触及冻结的 7 个产品/测试文件 +
`20-implementation.md`，未越界。

## 关键契约验证

1. 三组节奏独立
   - Group A（`premium_index`、`price_map`、`unified_balances`、
     `um_positions`、`spot_balances`）使用 `cache_ttl_seconds`（默认 60s）。
   - Group B（`group_b_public`、`classic_reference`、`account_info`）使用
     固定模块常量 `GROUP_B_REFRESH_SECONDS = 1800`。
   - Group C 在 `_sweep_group_c` 中每 tick 最多检查
     `history_sweep_batch_size`（默认 10）个主页 symbol，
     history/borrow-rate/max-borrowable 三个组件独立判断 due。

2. 成功时间戳与慢 transport TTL
   - 新引入的 `_global_source_cache`、`_borrow_rate_cache`、
     `_max_borrowable_cache` 均在 fetch 返回后用 `time.monotonic()` 打完成
     时间戳（INV-5）。
   - `config.py` 将 `private_channel_ttl_seconds` 默认值改为 1800，并拒绝
     `>1800` 的运行时覆盖。
   - `test_inv5_completion_time_transport_le_business_and_real_get_at_1800`
     验证了 `transport_write_time <= business_ts`、1799s 复用、1800s 真实
     signed GET、失败不推进时间戳。

3. scheduled assembly 无隐藏网络
   - `_gather_private_inputs_scheduled` 只读业务缓存，不调用
     `fetch_cost_leg_chain`、不做 top-50 探针。
     `test_scheduled_borrow_uses_narrow_seam_only` 断言
     `cost_leg_calls == []`。

4. 严格 FR-4 借贷谓词
   - `_is_scheduled_borrow_candidate` 使用
     `Decimal(str(rate)) >= Decimal("-0.00030000")` 的严格 `<` 判断，并校验
     `MARGIN_SPOT_CANDIDATE`、`asset_tag in {CRYPTO, METAL}`、classic_ref
     可用。

5. coverage 游标尝试语义
   - `_coverage_attempted` 在 `_refresh_max_borrowable` 中无论成败都 add；
     `_gather_private_inputs_scheduled` 每 tick 用 `&= universe_set` 剪枝；
     `reason == "rate_limit_budget"` iff `skipped > 0`。测试
     `test_coverage_ledger_prunes_on_universe_exit`、
     `test_coverage_reentry_starts_unattempted`、
     `test_coverage_reason_rate_limit_budget_iff_skipped` 覆盖。

6. borrow-rate 单位与 ×24 一次
   - `fetch_next_hourly_rates` 返回 raw hourly；`_borrow_rate_cache` 存 raw；
     `_resolve_borrow_rate_for_asset` 通过 `resolve_cost_leg_rate` 恰好一次归一
     化为 daily。`test_next_hourly_normalized_x24_exactly_once` 验证。

## 测试与校验证据

```text
python3 -m pytest backend/tests/test_background_worker.py backend/tests/test_private_client.py -q => 68 passed
python3 -m pytest backend/tests -q => 330 passed
python3 -m py_compile backend/config.py backend/adapters/binance_public.py backend/services/private_client.py backend/services/snapshot_service.py => OK
git diff --check => OK
python3 scripts/validate-stage.py 2026-07-cache-refresh-scheduler-v2 --phase pre-review => PASSED
diff_fingerprint 复核 => 60c91f7b32ab0f0a51f719a094915adfbec87c83:f970f6be1afa92b55b3ef79f1135753647fa9d8693b5e83fa80aa6a27bdfbfb0
```

## 非阻塞 P3 观察

`_fetch_history_for`（`backend/services/snapshot_service.py:841`）仍使用函数
入口处的 `now = time.monotonic()` 作为 `_funding_history_cache` 的时间戳，
而非 fetch 返回后的完成时间。这是上一 stage 遗留行为，本 stage 未修改；
public funding history 没有独立 transport cache，因此不会导致慢 transport
过期冒充刷新的风险，仅使时间戳比实际完成略早。建议后续统一语义，但本
stage 不阻塞。

本地北京时间: 2026-07-15 08:42:33 CST
下一步模型: human → codex (review-2 primary) / claude (fallback)
下一步任务: 在 fresh read-only session 中执行 review-2 最终评审
{"schema_version":1,"stage_id":"2026-07-cache-refresh-scheduler-v2","role":"first_reviewer","model":"kimi-code/kimi-for-coding","verdict":"ACCEPT","diff_fingerprint":"60c91f7b32ab0f0a51f719a094915adfbec87c83:f970f6be1afa92b55b3ef79f1135753647fa9d8693b5e83fa80aa6a27bdfbfb0","reviewer_prior_involvement":"none","reviewed_artifacts":["AGENTS.md","workflows/templates/stage-delivery.yaml","agents/skills/code-reviewer.md","schemas/review-verdict.schema.json","reports/agent-runs/2026-07-cache-refresh-scheduler-v2/00-task.md","reports/agent-runs/2026-07-cache-refresh-scheduler-v2/06-direction-synthesis.md","reports/agent-runs/2026-07-cache-refresh-scheduler-v2/10-design.md","reports/agent-runs/2026-07-cache-refresh-scheduler-v2/11-adr.md","reports/agent-runs/2026-07-cache-refresh-scheduler-v2/12-development-breakdown.md","reports/agent-runs/2026-07-cache-refresh-scheduler-v2/13-manual-delivery-amendment.md","reports/agent-runs/2026-07-cache-refresh-scheduler-v2/20-implementation.md","reports/agent-runs/2026-07-cache-refresh-scheduler-v2/60-test-output.txt","backend/config.py","backend/adapters/binance_public.py","backend/services/private_client.py","backend/services/snapshot_service.py","backend/tests/test_config.py","backend/tests/test_background_worker.py","backend/tests/test_private_client.py","git diff 8aac137a46d228f2d68b2036a15575eda0e235a3..60c91f7b32ab0f0a51f719a094915adfbec87c83"],"findings":[{"severity":"P3","title":"funding_history_cache 仍使用 fetch 前时间戳（非完成时间戳）","file":"backend/services/snapshot_service.py","line":841,"evidence":"_fetch_history_for 在函数入口用 now = time.monotonic() 取得时间戳，成功返回后在第 841 行写入 _funding_history_cache[symbol] = (now, entries)；该时间戳在 HTTP 调用之前捕获，而非 fetch 返回之后。","impact":"这是历史行为，本 stage 未修改该函数。public funding history 没有独立的 transport cache，因此不会产生慢私有 transport 那种过期条目冒充 30 分钟刷新的风险；仅使业务时间戳比实际完成时间早一个可忽略的同步调用耗时。","recommendation":"后续若统一所有业务缓存的完成时间戳语义，可将 _fetch_history_for 改为 fetch 返回后再读取 time.monotonic()；本 stage 可保持现状，不阻塞验收。"}],"required_fixes":[],"residual_risks":["P3: Group A panel business cadence 使用 cache_ttl_seconds，transport 使用 private_channel_fast_ttl_seconds；默认均为 60，env 发散时存在可配置 divergence，与 stage 记录一致，非阻塞。"],"next_action":"continue"}

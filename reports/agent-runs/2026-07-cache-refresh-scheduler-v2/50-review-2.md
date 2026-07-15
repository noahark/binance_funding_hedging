已独立核算 diff_fingerprint 完全一致，全部证据核对完毕。以下是最终评审结论。

---

# Review-2 最终评审结论：ACCEPT（含三条非阻塞 P3 观察）

## 先前参与披露与隔离

我是 Claude（模型 `opus4.8`，provider `anthropic`），角色 `final_reviewer`，先前参与度为 `breakdown`——Anthropic 撰写了继承的 `12-development-breakdown.md`，但**未**编写任何实现或修复代码。本次为全新只读会话，不共享 breakdown 会话（`bcb07380-…`）的 transcript 或工具状态。实现者为 `claude_glm`/`glm-5.2`（provider `zhipu_glm`），review-1 为 kimi，与我 provider 隔离成立。override 证据 `review-2-unrelated-reviewer-unavailable.md` 与 fallback 原因 `design_conflict_ineligibility_no_unrelated_registered_decision_model` 已核实；人工显式选定 `opus4.8`，未声称 Fable5 被探针/配额耗尽。本次未编辑/创建/提交任何文件，未联网、未调用 Binance、未起服务、未调用其他模型。

## 绑定核验

- base `8aac137` → head `60c91f7` 存在；当前分支 `stage/2026-07-cache-refresh-scheduler-v2`。
- 独立重算 `diff_fingerprint` = `60c91f7b…:f970f6be1afa92b55b3ef79f1135753647fa9d8693b5e83fa80aa6a27bdfbfb0`，与 prompt **完全一致**。
- 门禁：`test_background_worker + test_private_client` 68 passed；`backend/tests` **330 passed**（与 `60-test-output.txt` 一致）；四文件 `py_compile` OK；`git diff --check` OK；`git status --short` 干净。

## 关键契约独立核验

1. **三节奏独立（item 1）**：`_refresh_due_sources` 每 `source_id` 各持完成时间戳、各自判 due（CC-1）。Group A `premium_index`/`price_map`/账户面板走 `cache_ttl_seconds`(60)，Group B `group_b_public`/`classic_reference`/`account_info` 走模块常量 `GROUP_B_REFRESH_SECONDS=1800`，Group C `_sweep_group_c` 每 tick 最多检查 `history_sweep_batch_size` 个主页 symbol、三组件各自判 due。`test_split_seams_refresh_on_independent_cadences`、`test_one_public_source_failure_does_not_suppress_the_other` 佐证。

2. **完成时间戳 + 慢 transport 不冒充（item 2）**：所有业务缓存写入均在 fetch 返回后取 `time.monotonic()`（INV-5）；失败/None 不写入、不推进（FR-2）。核心不变式成立：`config.py` 默认 `private_channel_ttl_seconds` 改为 1800 且对 `>1800` 的 env 覆盖 `raise ValueError`。由于 transport_ts ≤ business_ts 且 transport_TTL ≤ 业务节奏(1800)，在 age≥1800 的业务 due 时刻 transport 条目必然同样过期→触发真实 signed GET，慢 transport 无法冒充 30 分钟刷新。

3. **assembly 无隐藏网络（item 3）**：`_gather_private_inputs_scheduled` 仅读业务缓存，不调用 `fetch_cost_leg_chain`、不做 top-50 探针（FR-3）。`test_scheduled_borrow_uses_narrow_seam_only` 断言 `cost_leg_calls==[]`。

4. **严格借贷谓词（item 4）**：`_is_scheduled_borrow_candidate` 用 `Decimal(str(rate)) >= Decimal("-0.00030000")→False` 实现严格 `< -0.00030000`，并校验 `MARGIN_SPOT_CANDIDATE`、`asset_tag∈{CRYPTO,METAL}`、classic_ref 可用。`test_fr4_predicate_strict_threshold` 覆盖边界两侧与 route/tag/disabled。

5. **coverage 语义（item 5）**：`_refresh_max_borrowable` 无论成败均 `add` 进 `_coverage_attempted`（仅成功推进缓存时间戳）；`_gather_private_inputs_scheduled` 每 tick `&= universe_set` **剪枝**（退出即移除，重入从未尝试起算）；`reason=="rate_limit_budget"` iff `skipped>0`。`test_coverage_ledger_prunes_on_universe_exit`（实测账本+已发布 coverage 双验）、`test_coverage_reentry_starts_unattempted`（cursor-only fresh pass 不算新尝试）、`test_coverage_reason_rate_limit_budget_iff_skipped` 覆盖。

6. **组件独立/批处理/去重（item 6/7）**：history / borrow-rate / max-borrowable 各自 TTL 独立（FR-7，`test_history_and_borrow_components_tracked_independently`）。`fetch_next_hourly_rates` 按 `NEXT_HOURLY_BATCH_SIZE=15` 批处理、逐 `base_asset` 解包并各带自身时间戳；`borrow_due/max_due` 去重。`next_hourly` 存**原始 hourly**、`_resolve_borrow_rate_for_asset` 经 `resolve_cost_leg_rate`（`chain_hit_source=="next_hourly"`→`compute_daily_from_hourly`）归一化 **×24 恰好一次**（`test_next_hourly_normalized_x24_exactly_once` 验实值 `0.00012000`）；`interestRateHistory` 存 daily、不 ×24，仅在某资产 next_hourly 缺失/失败时对该资产回退（FR-6）。

7. **无回归（item 8）**：click 路径 `_gather_private_inputs_click` 复用 bundle 并同步复用 `resolved_rates`，不重取 balances/positions。**重点核验**"已尝试但失败"资产渲染：失败资产在 `_coverage_attempted`（故 `borrowability_truncated=False`）且不在 `_max_borrowable_cache`（故不在 `portfolio_by_asset`）；`assemble_borrow_validation` 走 `portfolio_by_asset.get(base,{})` → 与**旧代码显式写 `{null,null,null}`** 的渲染逐字段一致（verified=True、amounts/error_code 全 null），无 wire 回归。51061 池耗尽经 `fetch_max_borrowable` 返回非 None 的 `{"0",None,"51061"}`，被缓存并保留 error_code，borrowability-error-zero-mapping 契约保留。offline/disabled 走 `private_channel_disabled` sentinel 分支保留旧契约。330 全绿。

8. **测试非同义反复（item 9）**：新增 `test_background_worker.py` 用 fake stub 驱动真实 `_scheduled_tick()`，断言具体行为（节奏计数、×24 实值、覆盖 prune≠mask、完成时间排序、no cost_leg_chain、no top-50 60 次尝试），覆盖冻结边界。

9. **遗留 P3（item 10）**：`_fetch_history_for`（`snapshot_service.py:841`）仍用函数入口的 pre-fetch `now` 打 `_funding_history_cache` 时间戳。该函数本 stage **未修改**（不在 diff 内），且 public funding history **无独立 transport cache**，pre-fetch 时间戳只会让业务缓存**略早**过期（保守方向，永不使陈旧数据冒充新鲜）——与 FR-2 masquerade 方向相反。同意 review-1 的 P3 非阻塞定性。

10. **可配置 TTL 发散（item 11）**：Group A 面板业务节奏用 `cache_ttl_seconds`，私有 transport 用 `private_channel_fast_ttl_seconds`（默认均 60，无发散）。与慢路径不同，快路径**未**设 `fast_ttl<=cache_ttl` 的 config 守卫；若 env 设 `fast_ttl>cache_ttl`，面板可能返回至多 `fast_ttl` 秒旧数据并被打新 `checked_at`。但影响限于 60s 量级的账户面板、默认对齐、且 ADR 已显式 defer 通用守卫。判为非阻塞 P3。

11. **main 基线（item 12）**：`413aa94` 仅改 `.env.example` `3600→1800`（单文件单行），内容核实无误；合并须保留。**注意**：prompt 与 `14-amendment` 记录的完整 SHA 为 `413aa94c74e356d2a99595f11cc0b91b8448fece`，而实际对象为 `413aa94c3bc4d89088b77eca07d89f59d2285d4d`——短前缀 `413aa94` 与内容均正确，属传播的记录笔误。我的 verdict 使用 stage fingerprint（非该 SHA），不受影响；建议簿记订正。

## 结论

需求保真、正确性、无回归、测试充分、安全（只读私有通道、assembly 无网络 I/O）、披露真实、隔离成立，无任何须修正项。判 **ACCEPT**。三条 P3 均为非阻塞观察，不构成 required_fix。此 ACCEPT 为本 gate 终局，不请求 Codex/Fable5 二次意见；ACCEPT 不授权合并到 `main`，须等待用户处置（合并须同时保留已落地的 `413aa94` 基线修正）。

```text
本地北京时间: 2026-07-15 09:25:52 CST
下一步模型: human
下一步任务: 用户处置 ACCEPT——授权将 stage 分支合并入 main 并保留 413aa94(.env.example=1800) 基线修正；簿记可顺带订正 413aa94 完整 SHA 笔误
```

{"schema_version":1,"stage_id":"2026-07-cache-refresh-scheduler-v2","role":"final_reviewer","model":"opus4.8","verdict":"ACCEPT","diff_fingerprint":"60c91f7b32ab0f0a51f719a094915adfbec87c83:f970f6be1afa92b55b3ef79f1135753647fa9d8693b5e83fa80aa6a27bdfbfb0","reviewer_prior_involvement":"breakdown","reviewer_prior_involvement_notes":"Anthropic(opus4.8) authored the inherited 12-development-breakdown.md only; no implementation or fix authorship. This is a fresh Anthropic-authenticated read-only session with no shared transcript/tool state from the prior breakdown session bcb07380-a298-4208-a461-e47fd629c85e. Strong-reviewer override evidence: reports/agent-runs/2026-07-cache-refresh-scheduler-v2/review-2-unrelated-reviewer-unavailable.md; fallback reason: design_conflict_ineligibility_no_unrelated_registered_decision_model. Human explicitly selected opus4.8 (not a Fable5 quota-exhaustion claim). Provider isolation from implementer zhipu_glm and reviewer-1 kimi preserved.","reviewed_artifacts":["AGENTS.md","workflows/templates/stage-delivery.yaml","docs/product/PRD.md","docs/architecture/ARCHITECTURE.md","reports/agent-runs/2026-07-cache-refresh-scheduler-v2/06-direction-synthesis.md","agents/skills/reality-checker.md","schemas/review-verdict.schema.json","reports/agent-runs/2026-07-cache-refresh-scheduler-v2/00-task.md","reports/agent-runs/2026-07-cache-refresh-scheduler-v2/10-design.md","reports/agent-runs/2026-07-cache-refresh-scheduler-v2/11-adr.md","reports/agent-runs/2026-07-cache-refresh-scheduler-v2/12-development-breakdown.md","reports/agent-runs/2026-07-cache-refresh-scheduler-v2/13-manual-delivery-amendment.md","reports/agent-runs/2026-07-cache-refresh-scheduler-v2/14-main-env-example-amendment.md","reports/agent-runs/2026-07-cache-refresh-scheduler-v2/20-implementation.md","reports/agent-runs/2026-07-cache-refresh-scheduler-v2/30-review-1.md","reports/agent-runs/2026-07-cache-refresh-scheduler-v2/40-fix-report.md","reports/agent-runs/2026-07-cache-refresh-scheduler-v2/50-review-2.md","reports/agent-runs/2026-07-cache-refresh-scheduler-v2/60-test-output.txt","reports/agent-runs/2026-07-cache-refresh-scheduler-v2/status.json","reports/agent-runs/2026-07-cache-refresh-scheduler-v2/review-2-unrelated-reviewer-unavailable.md","backend/config.py","backend/adapters/binance_public.py","backend/services/private_client.py","backend/services/snapshot_service.py","backend/domain/snapshot.py","backend/tests/test_config.py","backend/tests/test_background_worker.py","backend/tests/test_private_client.py","main commit 413aa94c3bc4d89088b77eca07d89f59d2285d4d (.env.example)","git diff 8aac137a46d228f2d68b2036a15575eda0e235a3..60c91f7b32ab0f0a51f719a094915adfbec87c83"],"findings":[{"severity":"P3","title":"funding_history 缓存仍用 fetch 前时间戳（继承，非本 stage 改动）","file":"backend/services/snapshot_service.py","line":841,"evidence":"_fetch_history_for 在函数入口(第826行)取 now=time.monotonic()，成功返回后在第841行写 _funding_history_cache[symbol]=(now, entries)，时间戳捕获于 HTTP 调用之前。该函数不在 8aac137..60c91f7 的 diff 内。","impact":"public funding history 无独立 transport cache，pre-fetch 时间戳只会使业务缓存略早于实际完成时间过期（保守方向），绝不会让陈旧数据冒充新鲜，与 FR-2 masquerade 方向相反。非阻塞。","recommendation":"后续若统一所有业务缓存的完成时间戳语义，可改为 fetch 返回后再读 time.monotonic()；本 stage 保持现状不阻塞验收。"},{"severity":"P3","title":"Group A 快速 TTL 可配置发散无 config 守卫","file":"backend/services/snapshot_service.py","line":457,"evidence":"账户面板业务节奏用 cache_ttl_seconds，私有 transport 用 private_channel_fast_ttl_seconds；与慢路径 <=1800 的 config 守卫不同，快路径未强制 fast_ttl<=cache_ttl。默认均为 60，无发散。","impact":"若操作者将 BINANCE_PRIVATE_CHANNEL_FAST_TTL_SECONDS 设为大于 cache_ttl_seconds，业务 due tick 可能返回至多 fast_ttl 秒旧的面板数据并打新 checked_at。影响限于 ~60s 量级的账户面板、默认对齐、ADR 已显式 defer 通用 last-good/empty 守卫。非阻塞。","recommendation":"后续可为快路径补一条 fast_ttl<=cache_ttl 的对称 config 校验；本 stage 不阻塞。"},{"severity":"P3","title":"main 基线 413aa94 完整 SHA 在 prompt 与 14-amendment 中记录笔误","file":"reports/agent-runs/2026-07-cache-refresh-scheduler-v2/14-main-env-example-amendment.md","line":null,"evidence":"记录的完整 SHA 为 413aa94c74e356d2a99595f11cc0b91b8448fece，git rev-parse 413aa94 实际解析为 413aa94c3bc4d89088b77eca07d89f59d2285d4d；短前缀 413aa94 与提交内容(.env.example 3600->1800，单文件单行)均正确。","impact":"仅记录字符串笔误，不影响交付物；review verdict 使用 stage fingerprint 而非该 SHA，不受影响。非阻塞。","recommendation":"簿记订正两处完整 SHA 为 413aa94c3bc4d89088b77eca07d89f59d2285d4d。"}],"required_fixes":[],"residual_risks":["P3(继承): _fetch_history_for 使用 pre-fetch 时间戳，方向安全、非阻塞。","P3: Group A fast_ttl 与 cache_ttl 可配置发散无对称 config 守卫，默认对齐、非阻塞。","P3: 413aa94 完整 SHA 记录笔误，内容正确、非阻塞。","合并须知: ACCEPT 不授权合并到 main；后续合并 stage 分支时须保留已落地的 413aa94(.env.example=1800) 基线修正。"],"next_action":"stage_accepted_waiting_user"}

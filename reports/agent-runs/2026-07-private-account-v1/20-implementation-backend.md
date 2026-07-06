# 20-implementation-backend — Task A（后端）实现报告

- stage: `2026-07-private-account-v1`
- 角色: implementer-A（claude_glm 实现会话，独立于 bookkeeper）
- base_sha: `fce1452cbc1db652477f517c4017a13f3ffb5449`（H_intake PASS）
- 权威规格: `10-design.md` §1/§2/§3（冲突时 10-design 赢）
- 本地起草时间: 2026-07-06（CST）；测试基线 96 → round1 **145 passed** → round2 **147 passed**（零回归 + 51 新增断言组；round2 +2 回归见 §7）

## 1. 改动清单（严格落在 §3.1 允许文件内）

| 文件 | 性质 | 摘要 |
|---|---|---|
| `backend/config.py` | 改 | 加 `borrow_check_max_calls=50`（§1.5，取代 Phase 2 N=10）、`private_channel_fast_ttl_seconds=60`（§1.6 双 TTL）；移除孤立的 `borrow_check_top_n`（其唯一读取者已替换）。 |
| `backend/services/private_client.py` | 改 | `WHITELIST` 4→12（base_url 按 §2.A.1：sapi/api→api.binance.com，papi→papi.binance.com）；`_cached_get` 加 `ttl` 选 §1.6 组；新增 `fetch_account_info`/`fetch_cost_leg_chain`/`fetch_unified_balances`/`fetch_um_positions`/`fetch_spot_balances` + 纯函数 `_select_chain_tier`。单一 HMAC 出口不变。E1/E1b 登记但不被任何 fetcher 调用。 |
| `backend/adapters/binance_public.py` | 改 | 新增 `fetch_ticker_price_map`（P5 `/api/v3/ticker/price` 公开全量一次，§1.4 估值）。offline 返回 `{}`。 |
| `backend/domain/snapshot.py` | 改 | 新增 `compute_net_daily_yield`/`compute_daily_from_hourly`/`_quantize_rate`/`select_borrow_candidates`/`resolve_cost_leg_rate`/`assemble_private_account`/`_infer_position_side`；`sort_rows(rows, basis)` 加 §1.2 双基准；`assemble_borrow_validation` 加 `daily_interest_account`+`truncated`；`assemble_snapshot` 加 `sort_basis`/`private_account`/顶层 `borrow_validation` 聚合块。 |
| `backend/services/snapshot_service.py` | 改 | `build_snapshot` 新流水线：候选集(§1.5)→chain(§1.3)→price map+E3/E4/E6(60s)→maxBorrowable→逐行 net/source/borrow_validation→sort_basis 排序→assemble。所有签名 HTTP 在行循环之前，行循环纯装配（§3.2）。 |
| `schemas/api/public-market/snapshot.schema.json` | 改 | additive：顶层 `sort_basis`/`private_account`/`borrow_validation`(聚合)；行 `net_daily_yield`/`borrow_rate_source`；`classic_margin.daily_interest_account`(required)；新 `$defs`：`private_account`/`um_position`/`borrow_validation_summary`。wire `schema_version` 不变。 |
| `docs/api/public-market-contract.md` | 改 | 头部 Status 升 v0.3；追加「Private Account v1 Amendment (v0.3)」段，引 H_intake 证据路径。 |
| `backend/tests/test_private_account_v1.py` | 新 | §3.3-§3.5 全覆盖（见 §4）。 |
| `backend/tests/test_private_client.py` | 改 | 白名单断言 4→12、加 base_url §2.A 断言、status.json 路径更新到本 stage、构造器加 `fast_ttl_seconds`、disabled 态加 v0.3 fetcher 降级断言。 |
| `backend/tests/test_phase2_borrow_sort.py` | 改 | `classic_margin` 字段集 4→5 键、disabled 态加 `daily_interest_account` 断言。 |
| `backend/tests/test_snapshot.py` | 改 | `_StubClient` 加 `fetch_ticker_price_map`。 |

**未触碰**：`classify.py`、`normalize.py`、`frontend/**`、`scripts/**`（工作树中 `frontend/*` 与 `embedded-review-b-*`/`60-test-output.txt` 的改动属并行 Task B，非本任务，且已被 R10 diff 路径 `git diff -- backend schemas docs/api` 正确排除）。

## 2. 关键设计决策（规格字面 vs 设计 fixture 张力处，供 review-1 核查）

1. **成本腿链 = 快照级单一命中 tier**（严格依 §1.3「链判定在快照级做一次」字面 + §3.2「不逐行探测利率端点」）。逐资产从命中 tier 的查表取利率；命中 tier 表内缺失该资产 → 该行 borrow rate=null、net=null、source=null。设计 fixture 的逐行混合 source（AUSDT=next_hourly / BUSDT=cross_margin_tier）是「design-time synthetic」字段形状示例（其自身 note 声明 ALL values fabricated），非运行时语义。我的 §3.5 排序测试断言**顺序**（AUSDT 排 BUSDT 前），不断言 source 取值。
2. **tier② E2b 单资产探针**（A1 假设）：冻结 discovery 仅验证 `asset=BTC` 单数参数（E2 用复数 `assets`，E2b 用单数 `asset`，参数名差异印证），预算表 E2b 调一次。故 `fetch_cost_leg_chain` 仅对 `probed_assets[0]` 探一次 E2b；tier② 覆盖受限。tier①（E2，`assets=` 逗号拼接，`isIsolated=false`）一次调用覆盖全部候选，是现实主路径；tier②/③/④ 仅在 E2 失败/缺漏时回退。若需 tier② 全候选覆盖，须 bookkeeper 实测确认 E2b 是否接受逗号 `asset`（R3 升级口）。
3. **`daily_interest_account` 不门控 `asset_borrowable`**：§1.5 探测范围只含 `neg ∧ MARGIN_SPOT_CANDIDATE ∧ CRYPTO`，不含 asset_borrowable。chain 对所有 probed 候选给利率；asset_borrowable 是独立信号。fixture DUSDT(not borrowable→null) 是合成示例，运行时按 §1.5 解耦（net 仍按 §1.1 公式计算）。
4. **顶层 `borrow_validation` 聚合块**（`coverage`+`chain_hit_tier`/`chain_hit_source`/`classic_margin_daily_interest_account_available`）：依 §1.5 coverage 是快照级聚合（probed/skipped），配合 fixture 顶层形状（Task B 共享契约）。与 `rows[].borrow_validation`（逐行，5 键）同名不同路径不同 schema（`$defs/borrow_validation` vs `$defs/borrow_validation_summary`）。
5. **schema 全 additive**：`sort_basis`/`private_account`/顶层 `borrow_validation`/`net_daily_yield`/`borrow_rate_source` 均 optional；v0.1 frozen fixture + v0.2 offline 快照均仍通过（已测）。`classic_margin.daily_interest_account` 恒供给故设为 required（producer 原子更新，v0.1 无 borrow_validation 不受影响）。
6. **`sort_basis` 门槛**：`net_daily_yield` 当 `classic_ref ≠ None 且 cost_leg.chain_hit_tier ∈ {1..4}`（成本腿可用，含 vip0_reference）；否则 `abs_daily_funding_rate`（Phase 2 全序回归）。chain 全断（tier None，极罕见，需 crossMarginData 无 vip0）→ abs。
7. **`private_account` 三态块恒输出**：disabled（env 缺失或 unified+spot 双失败）→ verified=false、三数组空、total null、error 填原因；单源失败 → 该数组空、块仍 verified=true。块始终在（§1.4「公开快照照常渲染」）。
8. **设计 fixture 未改**：含 `_design_fixture_*` 元键（bookkeeper 设计期注释），非 wire 输出；后端测试验证真实输出，不 schema-validate 该 fixture（其 note 自声明 synthetic）。Task B 渲染该 fixture 不做 schema 校验。若 review 要求去元键使其过 schema，trivial。
9. **R10 diff 含未跟踪新文件**：`git diff` 默认不含未跟踪文件，故对 `backend/tests/test_private_account_v1.py` 先 `git add -N`（intent-to-add，**非 commit**、不碰 status.json）使预审 patch 完整。bookkeeper R4 对账后清理。

## 3. 测试原始输出（R10 step 1 原文）

```
$ python3 -m pytest backend/tests/ -q 2>&1 | tail -20
........................................................................ [ 49%]
........................................................................ [ 99%]
.                                                                        [100%]
145 passed in 4.13s
```

基线 96（H_intake 前）→ round1 145（零回归 + 新增）。round2 修复后：

```
$ python3 -m pytest backend/tests/ -q 2>&1 | tail -5
........................................................................ [ 48%]
........................................................................ [ 97%]
...                                                                      [100%]
147 passed in 4.87s
```

`git diff --stat -- backend schemas docs/api`（round2）= 11 文件 +1991/-44（含 round2 +2 回归测试与两处修复；9 处 `reports/` 字符串引用为证据路径/STAGE_DIR/契约文档引用，非 frontend 文件 diff）。

## 4. 自查表（§3.3 / 预审必查清单逐项）

| # | 必查项 | 状态 | 证据 |
|---|---|---|---|
| 1 | 白名单 12 项与 status.json 完全一致；越界/非 GET 签名前 raise；负向单测齐 | ✅ | `test_whitelist_accepts_exactly_twelve_get_endpoints`/`_matches_status_json_endpoint_whitelist`/`_base_urls_match_2A_appendix`/`_rejects_unknown_papi_path`/`_rejects_post_on_new_endpoint`；`_require_whitelisted` 在 `_signed_get` 首行（签名构造前）。 |
| 2 | 单一 HMAC 出口仍唯一（grep 断言更新且过） | ✅ | `test_single_hmac_exit_in_product_code` + `test_single_hmac_exit_unchased_after_v03`；`test_urlopen_only_in_designated_http_clients`（仅 private_client/binance_public）。 |
| 3 | 成本腿四级链：命中判定/顺序/hourly×24 归一化正确；source 合规；E1/E1b 未进装配 | ✅ | `test_chain_tier1..4`/`_broken`/`_resolve_cost_leg_rate_applies_x24`/`_passes_through_daily`/`_fetch_cost_leg_chain_next_hourly_and_isisolated`（断言 `isIsolated=false`）/`_degrades_to_vip0`；`test_e1_e1b_whitelisted_but_no_fetcher_calls_them`。 |
| 4 | net_daily_yield：§3.4 六向量逐一在测；Decimal 禁 float；负零归一 | ✅ | `test_compute_net_daily_yield_vectors`（7 例含 §3.4 #1/2/3/5/6 + 负零 + 零费率）+`_no_float_no_scientific`；`test_compute_daily_from_hourly_vector`（#4 ×24）。 |
| 5 | 排序：§3.5 两组向量在测；sort_basis 快照级单一 | ✅ | `test_sort_net_reversal_core_assertion`（AUSDT 排 BUSDT 前）+`_net_signed_desc_nulls_last_symbol_tiebreak`+`_abs_basis_is_phase2_regression`+`_default_basis_is_abs`。 |
| 6 | coverage/warnings：上限 50 可配、截断标 not_probed、禁静默 verified | ✅（round2 补强） | round1 仅覆盖 per-row 截断标记（`test_select_borrow_candidates_caps_and_marks_truncation`/`_borrow_validation_truncated_state`），**漏了 §1.5「顶层 warnings 追加条目」**——Kimi 预审据 §1.5 line 78 指出。round2 已修：`assemble_snapshot` 由 `borrow_validation_summary.coverage.skipped>0` 驱动追加 `borrow_validation: N candidate(s) truncated by rate_limit_budget (not_probed_this_round)`；回归 `test_truncation_appends_top_level_warning`。offline（skipped=0）不触发，`test_three_contract_warnings_preserved`（len==3）不受影响。 |
| 7 | private_account：防重复计算两条硬规则有测试断言；价格 map 全量一次；三态降级 schema PASS | ✅（round2 补强） | 防重复计算与 P5 全量一次 round1 已测（`test_assemble_private_account_anti_double_count` 等）。**漏了 §1.4 heading「三态语义同 borrow_validation」的门控耦合**——round1 `assemble_private_account` disabled 判定用 `unified is None and spot is None`，未挂 `classic_ref`；当 classic_ref 失败但 E3/E4/E6 成功时会 verified=true（与逐行 borrow_validation verified=false 不一致）。Kimi 据 §1.4 heading 指出。round2 已修：`build_snapshot` 在 `classic_ref is None` 时跳过 E3/E4/E6 + price_map，令 private_account 进入 disabled 三态；回归 `test_private_account_disabled_when_classic_ref_none_even_if_accounts_return`。 |
| 8 | key/数值卫生：diff 与新 fixture 无 key 片段、无真实账户数值（§2.A 脱敏表抽查） | ✅ | `test_redaction_scan_design_fixture`（账户路径值均 `<AMOUNT>`/`<ID>`/null）+`_redaction_scan_captured_samples`（账户级样本脱敏；公开 allPairs/allAssets/crossMarginData/ticker-price 按 evidence-index account-level=False 排除）。 |
| 9 | 越界检查：diff 只触碰 §3.1；classify/normalize 零改动；无 commit、无 status.json 改动；无 websocket/listenKey 铺垫 | ✅ | `git diff --name-only` 仅 §3.1 文件 + 本报告；classify.py/normalize.py 未现；`test_no_websocket_listenkey_scaffolding`；未 commit、未碰 status.json（工作树改动）。 |
| 10 | 降级矩阵：env 缺失 / E3 失败 / E6 失败 / 链全断 四态快照均 schema PASS | ✅ | `test_degradation_env_missing_schema_pass`/`_e3_fail_schema_pass`/`_e6_fail_schema_pass`/`_chain_all_broken_schema_pass` + `test_enabled_chain_hit_sort_basis_net_and_net_yield_computed`（正路径 net=0.00048000）+ `test_offline_snapshot_v03_fields_validate`。 |

## 5. 已知限制 / R3 升级口

- **tier② E2b 全候选覆盖**：见决策 2（A1 假设）。需 bookkeeper 实测 E2b 是否接受逗号 `asset`。
- **E4 `position_side`**：papi positionRisk 无直接字段，按 `positionAmt` 符号推断 LONG/SHORT（§2.A.3 待确认）；本账户空仓 `um_positions=[]`，真实持仓出现时需实测复核。
- **设计 fixture 元键**：见决策 8。

## 6. R10 收尾段执行结果（round1）

- step 1 自测：`145 passed`（见 §3）。
- step 2 预审 diff：`embedded-review-a-round1.diff.patch`（11 文件 +1853/-43，含 `git add -N` 后的新测试文件）。
- step 3 Kimi fresh 只读预审原文：`embedded-review-a-round1.raw-output.md`。
- step 4 分支处理结论：**BLOCKER（scope 内）→ 已修复 + 修复笔记 + round2**（见 §7）。Kimi 逐项 PASS/FAIL：#1-5/8/9 PASS；#6/7 FAIL（两处规格偏离，均落在 `backend/services/snapshot_service.py` + `backend/domain/snapshot.py`，属 §3.1 允许文件）。

## 7. round2 修复（embedded-review-a-round1 BLOCKER）

两项修复均经规格字面复核确认（非盲从预审）：§1.5 line 78 明文「顶层 warnings 追加条目 + coverage 块」二者并列；§1.4 heading 明文「private_account 块（顶层，三态语义同 borrow_validation）」。

| # | 文件 | 缺陷（round1） | 修法（round2） | 回归测试 |
|---|---|---|---|---|
| A | `backend/domain/snapshot.py`（`assemble_snapshot`） | `coverage.skipped>0` 时未向顶层 `warnings` 追加条目（§1.5）。 | `assemble_snapshot` 由 `borrow_validation_summary.coverage.skipped>0` 驱动追加 `borrow_validation: N candidate(s) truncated by rate_limit_budget (not_probed_this_round)`。**分层选择**：放纯函数 `assemble_snapshot`（summary 已入参）而非 kimi 建议的 `build_snapshot:235`——同一可观测行为，更干净、可单测、零 raw-fixture 依赖。 | `test_truncation_appends_top_level_warning` |
| B | `backend/services/snapshot_service.py`（`build_snapshot`） | `private_account` disabled 判定用 `unified is None and spot is None`，未挂 `classic_ref`；classic_ref 失败但 E3/E4/E6 成功 → verified=true，违反 §1.4「三态语义同 borrow_validation」。 | `classic_ref is None` 时跳过 E3/E4/E6 + price_map（`unified=um=spot=None, price_map={}`），令 `assemble_private_account` 进入 disabled 三态（verified=false、三数组空、total null、error 沿用 `private_error`）。 | `test_private_account_disabled_when_classic_ref_none_even_if_accounts_return`（服务级桩：classic_ref=None 但 unified/spot 有数据 → 仍 verified=false） |

**安全性核查**：
- 截断 warning 仅 `skipped>0` 触发；offline（probed=0→skipped=0）不触发 → `test_three_contract_warnings_preserved`（len==3）与 `test_offline_snapshot_v03_fields_validate`（probed==0）不受影响。
- Fix B 的 classic_ref=None 分支与 offline 既 disabled 语义一致（offline E3/E4/E6 经 `enabled=False` 本就返回 None）→ offline 全部 degradation 测试无回归。
- 单源失败（classic_ref ok，E3 或 E6 单败）仍走 `assemble_private_account` 的 partial-failure 分支（verified=true、该数组空）——Fix B 只补「整通道 down → disabled」语义，不改单源降级。`test_degradation_e3_fail_schema_pass`/`_e6_fail_` 经 `_assemble_with_private`（assembly 层）不受影响。
- 全量 **147 passed**（145 + 2 round2 回归），零回归。

## 8. R10 收尾段执行结果（round2）

- step 1 自测：`147 passed`（round1 145 + 2 round2 回归，零回归）。
- step 2 预审 diff：`embedded-review-a-round2.diff.patch`（11 文件 +1991/-44）。
- step 3 Kimi fresh 只读 round2 预审原文：`embedded-review-a-round2.raw-output.md`。
- step 4 分支处理结论：**PASS（可落盘）→ 移交 bookkeeper**。Kimi round2 逐项 10/10 PASS：round1 blocker A/B 均确认修干净且有回归覆盖；#3-10 沿用 round1 PASS。Kimi 唯一非 blocker 观察：`docs/architecture/ADR/11-adr.md` 不在本任务 §3.1 允许文件内、本轮 diff 未改动，建议 bookkeeper 阶段落盘前按 `00-task.md` 硬约束补录（scope 外 follow-up，非本任务 blocker）。移交文档：`embedded-review-a-round2.dispatch.md`。

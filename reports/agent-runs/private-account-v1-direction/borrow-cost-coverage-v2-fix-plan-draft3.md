# Borrow Cost Coverage v2 Fix Plan DRAFT-3

模型：GPT/Codex  
状态：DRAFT-3，吸收 Claude/Fable5 第二轮 REWORK  
范围：后端数据源覆盖率修复方案，不修改业务代码，不提交 git  

历史链路：

- DRAFT-1: `reports/agent-runs/private-account-v1-direction/borrow-cost-coverage-v2-fix-plan.md`
- Claude review 1: `reports/agent-runs/private-account-v1-direction/borrow-cost-coverage-v2-fix-plan-review-claude.md`
- DRAFT-2: `reports/agent-runs/private-account-v1-direction/borrow-cost-coverage-v2-fix-plan-draft2.md`
- Claude review 2: 用户转述，核心阻塞为 `assemble_borrow_validation()` 的 `truncated` 分支会二次清空利率。

关键代码证据：

- `backend/services/snapshot_service.py:195-211`
- `backend/domain/snapshot.py:333-357`
- `backend/domain/snapshot.py:713-730`
- `backend/services/private_client.py:424`
- `reports/agent-runs/private-account-v1-direction/endpoint-recon-kimi-borrow-rate-v2.md`
- `reports/api-samples/private-account-v1-direction/borrow-rate-endpoint-survey-20260707T120945Z/`

---

## 1. DRAFT-3 裁定

DRAFT-2 的方向是对的：`next-hourly-interest-rate` 应作为开仓前借币利率主源，且利率覆盖不应被 `maxBorrowable` 的 top-N 预算截断。

但 DRAFT-2 仍漏了一个阻塞级落地陷阱：

```text
assemble_borrow_validation(row, ..., truncated=True)
  -> daily_interest_account = None
  -> verified = False
  -> error = "not_probed_this_round"
```

也就是说，即便 `snapshot_service.py` 行循环已经通过解耦算出了 `daily_borrow_rate`，只要继续把同一个 `truncated` 传给 `assemble_borrow_validation()`，最终输出里的 `borrow_validation.classic_margin.daily_interest_account` 仍会被清空。

因此真正的 immediate fix 不是只拆两个 asset set，而是必须同时拆开两个概念：

```text
rate_coverage_truncated      # 利率是否未覆盖
borrowability_truncated      # 可借额度是否未探测
```

当前 `truncated` 同时表达了这两个含义，这是症状反复出现的根因。

---

## 2. 当前事实链

### 2.1 当前候选选择

`select_borrow_candidates(rows, max_calls)` 只返回一个 capped 集合：

```text
probed_assets
truncated_assets
coverage
```

该集合同时用于：

1. `fetch_cost_leg_chain(probed_assets)`：借币利率链路。
2. `fetch_max_borrowable(asset)`：统一账户可借额度链路。
3. `assemble_borrow_validation(..., truncated=base in truncated_assets)`：最终输出状态。

### 2.2 当前利率链路

`fetch_cost_leg_chain()` 已经实现 `next-hourly` 批量请求：

```text
GET /sapi/v1/margin/next-hourly-interest-rate
params: assets=<comma-joined>, isIsolated=false
```

`_select_chain_tier()` 是快照级单 tier：

```text
if any(next_hourly.values()):
    chain_hit_source = "next_hourly"
    daily_by_asset = next_hourly table
```

所以稳态下，`interestRateHistory` 不参与。DRAFT-1 说“fallback 只查第一个资产导致大量 -”是错误根因；这只在 next-hourly 全空时才可能影响降级表现。

### 2.3 当前输出清空点

`snapshot_service.py` 行循环当前只对非截断资产计算利率：

```text
if base in probed_assets and base not in truncated_assets and cost_leg:
    daily_borrow_rate = resolve_cost_leg_rate(base, cost_leg)
```

即便这一步改成对更大的 rate asset set 计算，后续仍会调用：

```text
assemble_borrow_validation(..., daily_interest_account=daily_borrow_rate, truncated=base in truncated_assets)
```

而 `assemble_borrow_validation()` 的 `truncated=True` 分支会强制返回：

```text
daily_interest_account = None
checked_at = None
error = "not_probed_this_round"
```

因此 DRAFT-3 必须把这个函数列入编辑地图。

---

## 3. 开发前决策门

### 3.1 Gate A: 实盘候选数是否超过 `borrow_check_max_calls`

根因 A 只有在实盘负费率候选数超过 50 时才成立。

开发前必须用当前 live snapshot 或只读脚本记录：

```text
negative_margin_spot_crypto_candidate_count
borrow_check_max_calls
would_truncate = count > borrow_check_max_calls
```

判定：

- 如果 `count > 50`：执行本 DRAFT-3 immediate fix。
- 如果 `count <= 50`：大面积 `-` 不是由 top-N 截断造成，应改查 next-hourly 子集覆盖、classic reference、private channel failure 或 UI 映射问题；本 fix 不应贸然进入实现。

该 gate 必须落档到阶段 `60-test-output.txt` 或实现报告，不能只写在聊天里。

### 3.2 Gate B: next-hourly 单次资产上限

Kimi 只测了 9 个资产。实现前必须测试当前全量候选：

```text
GET /sapi/v1/margin/next-hourly-interest-rate
assets=<all negative MARGIN_SPOT_CANDIDATE + CRYPTO base assets>
isIsolated=false
```

记录：

- request asset count
- returned asset count
- missing assets
- HTTP status / Binance code
- response headers weight
- 是否有 URL 长度或参数数量限制

判定：

- 单次成功：`rate_probe_assets` 可一次请求。
- 单次失败：实现分批合并，分批合并必须发生在 `_select_chain_tier()` 之前。

---

## 4. Immediate Fix 设计

### 4.1 拆分候选集

新增或重构候选选择，返回两个集合：

```text
rate_probe_assets:
  全量或独立上限的负费率 MARGIN_SPOT_CANDIDATE + CRYPTO assets
  用于 next-hourly 借币利率

borrowability_probe_assets:
  受 borrow_check_max_calls 限制的同类 assets
  用于 maxBorrowable 可借额度

borrowability_unprobed_assets:
  rate_probe_assets - borrowability_probe_assets
  表示“有机会拿利率，但可借额度未探测”
```

不要再用单个 `truncated_assets` 同时控制利率和可借性。

### 4.2 行循环逻辑

推荐伪代码：

```text
if base in rate_probe_assets and cost_leg:
    rate = resolve_cost_leg_rate(base, cost_leg)
    if rate is not None:
        daily_borrow_rate = rate
        borrow_rate_source = cost_leg.get("chain_hit_source")

borrowability_truncated = base in borrowability_unprobed_assets

row["net_daily_yield"] = compute_net_daily_yield(row["daily_funding_rate"], daily_borrow_rate)
row["borrow_rate_source"] = borrow_rate_source
row["borrow_validation"] = assemble_borrow_validation(
    ...,
    daily_interest_account=daily_borrow_rate,
    borrowability_truncated=borrowability_truncated,
)
```

核心要求：

- `borrowability_truncated=True` 不得清空 `daily_interest_account`。
- `borrowability_truncated=True` 只影响 `portfolio_account` 与可借性状态。
- 如果 rate 真的没有覆盖，才让 `daily_interest_account=None`。

### 4.3 修改 `assemble_borrow_validation()`

该函数必须从单个 `truncated` 语义改为更明确的语义。

可选实现 A：新增参数。

```text
assemble_borrow_validation(
    ...,
    daily_interest_account=daily_borrow_rate,
    borrowability_truncated=base in borrowability_unprobed_assets,
)
```

行为：

- `classic_ref is None`：仍整体 `verified=False`，利率为空。
- `borrowability_truncated=True`：
  - `verified` 可继续为 `False` 或新增更细状态，取决于现有契约；
  - `classic_margin.pair_listed` / `asset_borrowable` / `daily_interest_vip0` 仍可按 `classic_ref` 填；
  - `classic_margin.daily_interest_account` 必须保留传入值；
  - `portfolio_account.max_borrowable = None`；
  - `portfolio_account.borrow_limit = None`；
  - `error = "not_probed_this_round"` 或更明确的 `"borrowability_not_probed"`。

可选实现 B：保留参数名但改变语义。  
不推荐，因为 `truncated` 历史含义已经混乱，容易再次误用。

推荐实现 A。

### 4.4 分批合并位置

如果 Gate B 发现 next-hourly 单次资产数有限制，分批合并必须在 `_select_chain_tier()` 之前完成：

```text
batch_1_next_hourly + batch_2_next_hourly + ...
  -> merged_next_hourly_by_asset
  -> _select_chain_tier(merged_next_hourly_by_asset, ...)
```

不要对每批分别调用 `_select_chain_tier()` 后再合并 tier 结果，否则会制造多套快照级 tier，语义会变得不可校验。

---

## 5. 暂不做的事

本阶段不做：

- per-asset tier synthesis；
- `interestRateHistory` 对缺失资产逐个补洞；
- maxBorrowable rotating queue；
- WebSocket；
- 下单、借币、还币、划转；
- bStock 负费率借币套利；
- 大规模 UI 重构。

如果 immediate fix 后仍有大量非 bStock 资产没有利率，再单独开 `per-asset-cost-leg-v1`，届时再讨论：

```text
asset A -> source next_hourly
asset B -> source rate_history
asset C -> source cross_margin_tier
```

---

## 6. 测试策略

### 6.1 阻塞回归测试：borrowability 截断不得清空利率

构造：

- `borrow_check_max_calls=2`
- 4 个负费率 `MARGIN_SPOT_CANDIDATE + CRYPTO` 资产
- next-hourly 返回 4 个资产利率
- maxBorrowable 只探测前 2 个资产

断言：

- 第 3/4 个资产：
  - `borrow_rate_source == "next_hourly"`
  - `borrow_validation.classic_margin.daily_interest_account` 非空
  - `net_daily_yield` 非空
  - `borrow_validation.portfolio_account.max_borrowable is None`
  - `borrow_validation.error` 表达可借性未探测

这是本阶段最重要的测试。没有这个测试，DRAFT-3 不得进入实现验收。

### 6.2 Gate A 测试 / 证据

live read-only 或 fixture 输出：

```text
negative_margin_spot_crypto_candidate_count = N
borrow_check_max_calls = 50
would_truncate = true|false
```

如果 `would_truncate=false`，本阶段应停止并重新诊断，不应继续实现。

### 6.3 Gate B 测试 / 证据

live read-only 或脱敏样本输出：

```text
next_hourly_request_asset_count = N
next_hourly_returned_asset_count = M
missing_assets = [...]
status = 200 or error code
weight_headers = ...
```

如果需要分批，增加分批合并测试：

- batch 1 返回 A/B；
- batch 2 返回 C/D；
- 合并后 `_select_chain_tier()` 收到 A/B/C/D。

### 6.4 现有行为回归

保留：

- next-hourly hourly × 24 正确；
- bStock 无利率且不可借；
- private channel disabled 时不触发私有请求；
- 所有只读红线仍成立。

回归命令：

```text
python3 -m pytest backend/tests/test_private_account_v1.py -q
python3 -m pytest backend/tests/test_phase2_borrow_sort.py -q
python3 -m pytest backend/tests/test_snapshot.py -q
python3 -m pytest backend/tests -q
```

---

## 7. 验收标准

必须满足：

1. 若 Gate A 显示候选数 `> borrow_check_max_calls`，top-N 外资产只要 next-hourly 命中，就必须保留日借币利率。
2. `borrow_check_max_calls` 只限制 `maxBorrowable`，不得限制 next-hourly 利率覆盖。
3. `assemble_borrow_validation()` 不得因为可借额度未探测而清空 `daily_interest_account`。
4. 可借性未探测和利率未覆盖必须能区分。
5. next-hourly 未返回的资产不得伪造利率。
6. bStock 负费率借币套利仍禁用。
7. 所有测试通过。
8. live smoke test 只读，不触发交易、借币、还币、划转。

建议在实现报告输出：

```text
rate_probe_assets_count
borrowability_probe_assets_count
borrowability_unprobed_assets_count
next_hourly_returned_assets_count
rows_with_rate_count
rows_with_rate_but_borrowability_unprobed_count
```

---

## 8. 建议阶段

```text
stage-id: 2026-07-borrow-cost-coverage-v2
complexity: MEDIUM
owner: claude_glm
review-1: kimi
review-2: codex 或 claude/fable5，按 Harness 规则
```

任务：

1. Task A：Gate A/Gate B 只读证据落档。
2. Task B：拆分 rate coverage 与 borrowability probe。
3. Task C：修 `assemble_borrow_validation()` 的截断语义。
4. Task D：测试与只读 live smoke。

---

## 9. 给 Claude/Fable5 的 DRAFT-3 Review 启动文案

```text
请只读 review 以下 DRAFT-3 fix 方案，不修改文件：

reports/agent-runs/private-account-v1-direction/borrow-cost-coverage-v2-fix-plan-draft3.md

背景：
- DRAFT-1: reports/agent-runs/private-account-v1-direction/borrow-cost-coverage-v2-fix-plan.md
- DRAFT-2: reports/agent-runs/private-account-v1-direction/borrow-cost-coverage-v2-fix-plan-draft2.md
- Claude review 1: reports/agent-runs/private-account-v1-direction/borrow-cost-coverage-v2-fix-plan-review-claude.md
- Kimi endpoint survey: reports/agent-runs/private-account-v1-direction/endpoint-recon-kimi-borrow-rate-v2.md

请重点判断：
1. DRAFT-3 是否正确吸收 assemble_borrow_validation 的 truncated 分支问题。
2. 将 rate coverage truncated 与 borrowability truncated 拆开是否是最小正确修法。
3. Gate A（实盘候选数 > 50）作为开发前决策门是否必要且充分。
4. Gate B（next-hourly 单次资产上限）是否表达清楚。
5. 测试 6.1 是否足以防止“行循环算出利率但最终输出又被清空”的回归。

输出 ACCEPT / REWORK，并列出必须修正项。
```

---

本地北京时间: 2026-07-07 20:48:24 CST  
下一步模型: Claude/Fable5  
下一步任务: review borrow-cost coverage v2 fix plan DRAFT-3

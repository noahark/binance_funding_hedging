# Borrow Cost Coverage v2 Fix Plan DRAFT-2

模型：GPT/Codex  
状态：DRAFT-2，已吸收 Claude/Fable5 REWORK review  
范围：后端数据源覆盖率修复方案，不修改业务代码，不提交 git  
上一版：

- `reports/agent-runs/private-account-v1-direction/borrow-cost-coverage-v2-fix-plan.md`

已吸收 review：

- `reports/agent-runs/private-account-v1-direction/borrow-cost-coverage-v2-fix-plan-review-claude.md`

关键证据：

- `reports/agent-runs/private-account-v1-direction/endpoint-recon-kimi-borrow-rate-v2.md`
- `reports/api-samples/private-account-v1-direction/borrow-rate-endpoint-survey-20260707T120945Z/`
- `backend/services/private_client.py`
- `backend/services/snapshot_service.py`
- `backend/domain/snapshot.py`

---

## 1. GPT 复核结论

Claude 的 REWORK 结论成立。上一版方案的主方向正确，但根因诊断错误。

上一版把“大量 `日借币利率 = -`”主要归因为：

```text
interestRateHistory fallback 只查 borrow_assets[0]
```

这个归因不符合当前代码主路径。

当前代码事实：

1. `PrivateClient.fetch_cost_leg_chain()` 已经用 `next-hourly-interest-rate` 做 comma-joined 批量请求。
2. `_select_chain_tier()` 是快照级单 tier 选择。
3. 只要 `next_hourly` 返回任意非空值，整张 `next_hourly` 表成为本快照唯一 cost leg。
4. `interestRateHistory` 只有在 `next_hourly` 整体全空时才参与，不会在 next-hourly 局部缺失时逐资产补洞。
5. `snapshot_service.py` 把 `borrow_check_max_calls` 产出的 `probed_assets` 同时用于：
   - `next-hourly` 利率输入集；
   - `maxBorrowable` 可借额度探测集。
6. `snapshot_service.py` 行装配时，截断资产不进入 `resolve_cost_leg_rate()`，所以既没有可借性，也没有利率。

因此真实问题是：

```text
rate source input set 与 maxBorrowable budget 被错误绑在一起。
```

`borrow_check_max_calls=50` 本来是为了限制逐资产 `maxBorrowable` 成本，但现在也限制了低成本批量 `next-hourly` 的覆盖范围。

---

## 2. 真实根因

### 2.1 根因 A：共享候选集导致利率被预算截断

当前链路：

```text
select_borrow_candidates(rows, borrow_check_max_calls)
  -> probed_assets               # capped at 50
  -> fetch_cost_leg_chain(probed_assets)
  -> next-hourly only receives those 50 assets
  -> fetch_max_borrowable(asset) for those 50 assets
```

问题：

- `next-hourly-interest-rate` 是批量端点，Kimi 实测 9 个资产单次成功，权重为 `200 IP / call`。
- `maxBorrowable` 是逐资产端点，Kimi 实测 `5 / asset`。
- 两者成本结构不同，不应该共享同一个 `borrow_check_max_calls` 上限。

结果：

- 第 51 个之后的负费率候选被 `truncated_assets` 标记。
- 这些资产即使 Binance 能返回 next-hourly 利率，也不会被请求。
- UI 显示 `日借币利率 = -` / `未探测(限速预算)`。

### 2.2 根因 B：next-hourly 子集覆盖没有逐资产 fallback

即使某资产进入 `next-hourly` 请求，响应也可能不包含该资产。例如 Kimi 实测中 `TSLAB` 没有 next-hourly 利率。

当前 `_select_chain_tier()` 是快照级单 tier：

```text
如果 next_hourly 任意命中 -> 本快照全部使用 next_hourly 表
如果 next_hourly 全空 -> 才使用 rate_history
```

这意味着：

- next-hourly 命中的资产可正常获得利率；
- next-hourly 未返回的资产不会逐资产 fallback 到 `interestRateHistory`；
- 这不是“修一行 fallback”能解决的，而是要把 cost leg 从“快照级单 tier”改为“per-asset tier synthesis”。

DRAFT-2 的建议是：**immediate fix 不做 per-asset tier synthesis**，先解决根因 A。根因 B 作为可选后续，只有当 next-hourly 对非 bStock 候选仍大量缺失时再做。

---

## 3. Immediate Fix: 解耦利率覆盖与可借额度预算

### 3.1 修复目标

把负费率候选拆成两个集合：

```text
rate_probe_assets:
  所有 daily_funding_rate < 0
  且 route_class == MARGIN_SPOT_CANDIDATE
  且 asset_tag == CRYPTO
  的去重 base_asset
  不受 borrow_check_max_calls 限制，或使用独立更高上限

borrowability_probe_assets:
  同样的候选池
  但受 borrow_check_max_calls 限制
  只用于 maxBorrowable
```

主链路：

```text
cost_leg = fetch_cost_leg_chain(rate_probe_assets)
portfolio_by_asset = fetch_max_borrowable(asset) for asset in borrowability_probe_assets
```

行装配：

```text
if base in rate_probe_assets and cost_leg:
    daily_borrow_rate = resolve_cost_leg_rate(base, cost_leg)

if base in borrowability_probe_assets:
    portfolio_account = maxBorrowable result
else:
    portfolio_account = not_probed_this_round
```

这样：

- 利率覆盖不再被 maxBorrowable 预算连累。
- `not_probed_this_round` 只表示“可借额度未探测”，不再表示“利率未探测”。
- UI 可以显示“有利率 / 净收益，但可借额度未探测”。

### 3.2 上手前阻塞验证：next-hourly 单次资产上限

Kimi 目前只实测了 9 个资产。开发前必须补一个只读探测：

```text
使用当前负费率 MARGIN_SPOT_CANDIDATE + CRYPTO 全量 asset set，
调用 /sapi/v1/margin/next-hourly-interest-rate，
记录：
- 请求 asset 数量
- 返回 asset 数量
- HTTP status / Binance code
- 是否存在 URL 长度或参数数量限制
- X-SAPI-USED-IP-WEIGHT-1M
```

如果全量单次成功：

- `rate_probe_assets` 一次请求。

如果全量单次失败：

- 增加 `next_hourly_asset_batch_size` 配置；
- 分批调用并合并 `daily_by_asset`；
- 每批仍只读；
- 记录 coverage。

### 3.3 建议新增配置

```text
BINANCE_BORROW_RATE_MAX_ASSETS
  默认 0 或空 = 不限制，由 next-hourly 实测上限决定

BINANCE_NEXT_HOURLY_ASSET_BATCH_SIZE
  默认 0 = 单次请求
  如果实测发现有上限，再设为 50/100 等安全值
```

如果不想增加配置，最小实现可以先：

- 全量单次 next-hourly；
- 失败时回退到当前 top-50 行为；
- 把失败原因写入 warnings。

---

## 4. Fallback 策略裁剪

### 4.1 本阶段不建议重构 per-asset tier synthesis

上一版方案提出：

```text
next-hourly 缺失某资产 -> 对缺失资产查 interestRateHistory
```

这在现有架构中不是小修，因为当前 cost leg 是快照级单 tier。要支持该行为，需要改成：

```text
daily_by_asset = {
  assetA: {"source": "next_hourly", "daily": "..."},
  assetB: {"source": "rate_history", "daily": "..."},
  assetC: {"source": "cross_margin_tier", "daily": "..."}
}
```

同时 `borrow_rate_source` 不能再取快照级 `cost_leg.chain_hit_source`，必须逐资产返回 source。

这是一个更大的契约变更，建议不放进 immediate fix。

### 4.2 本阶段保留的 fallback 行为

本阶段只保留当前快照级 fallback：

1. next-hourly 全空或请求失败；
2. fallback 到现有 `interestRateHistory(borrow_assets[0])` / crossMarginData；
3. 记录 coverage 和 warning；
4. 不承诺逐资产补洞。

如果 immediate fix 后仍有大量非 bStock 资产缺 next-hourly 利率，再单独开 `per-asset-cost-leg-v1` 阶段。

---

## 5. UI 与数据语义

修复后，负费率资产可能出现以下状态：

| 状态 | 利率 | 可借额度 | UI 含义 |
|---|---|---|---|
| `rate_available_borrowable` | 有 | 已探测且可借 | 可以用于负费率套利候选 |
| `rate_available_not_borrowable` | 有 | 已探测但不可借/51061/0 | 有成本估算，但当前不能借 |
| `rate_available_borrow_unprobed` | 有 | 未探测 | 有成本估算，但可借性待确认 |
| `rate_unavailable` | 无 | 任意 | 无法计算净收益 |
| `bstock_borrow_disabled` | 无 | 0 或不支持 | bStock 负费率借币套利禁用 |

本阶段最小 UI 变更可以不新增枚举，只保证：

- `daily_interest_account` 有值时不显示 `-`；
- `borrow_rate_source = next_hourly`；
- `borrow_validation.error = not_probed_this_round` 只影响可借性，不清空利率；
- bStock 仍保持禁用。

---

## 6. 代码边界建议

允许修改：

- `backend/domain/snapshot.py`
  - 拆分候选选择，或新增 `select_borrow_rate_assets()` / `select_borrowability_candidates()`。
- `backend/services/snapshot_service.py`
  - 用 rate asset set 调用 `fetch_cost_leg_chain()`；
  - 用 borrowability asset set 调用 `fetch_max_borrowable()`；
  - 行装配时利率解析不再依赖 `truncated_assets`。
- `backend/services/private_client.py`
  - 仅在需要支持 next-hourly 分批时修改；
  - 本阶段不要求 per-asset tier synthesis。
- `backend/config.py`
  - 可选新增 next-hourly 批量上限配置。
- 后端测试。

谨慎修改：

- `schemas/api/public-market/snapshot.schema.json`
- `docs/api/public-market-contract.md`
- `frontend/*`

如果只改变已有字段填充，不改变字段形状，可以不改 schema。若新增 coverage 字段或 UI 状态枚举，必须做 additive schema update。

禁止修改：

- `.env` / API key；
- 交易、借币、还币、划转接口；
- WebSocket；
- 手动开仓；
- bStock 负费率借币套利规则。

---

## 7. 测试策略

### 7.1 必须新增/调整的测试

1. **截断解耦测试**
   - 构造负费率候选 > `borrow_check_max_calls`。
   - `borrow_check_max_calls=2`。
   - next-hourly fixture 覆盖 4 个资产。
   - 断言第 3/4 个资产虽然 `maxBorrowable` 未探测，但仍有 `daily_interest_account` 和 `borrow_rate_source=next_hourly`。

2. **maxBorrowable 预算只影响可借性**
   - top-2 资产有 `portfolio_account`。
   - top-2 外资产 `borrow_validation.error=not_probed_this_round` 或等价状态。
   - 但 top-2 外资产的利率不为空。

3. **next-hourly 子集缺失**
   - 请求资产包含 `TSLAB` 或某个缺失资产。
   - next-hourly 返回不含该资产。
   - 断言该资产 `daily_interest_account=null`，且不伪造 `rate_history`。
   - bStock 仍禁用。

4. **现有 next-hourly 命中路径回归**
   - 命中资产 daily = hourly * 24。
   - `borrow_rate_source=next_hourly`。

5. **全量 next-hourly 上限 smoke 证据**
   - 只读 live smoke 或脱敏样本证明当前候选资产数量下请求可行；
   - 若不可行，测试分批合并逻辑。

### 7.2 回归命令

```text
python3 -m pytest backend/tests/test_private_account_v1.py -q
python3 -m pytest backend/tests/test_phase2_borrow_sort.py -q
python3 -m pytest backend/tests/test_snapshot.py -q
python3 -m pytest backend/tests -q
```

---

## 8. 验收标准

修复完成后必须满足：

1. 负费率 `MARGIN_SPOT_CANDIDATE + CRYPTO` 候选中，凡 next-hourly 返回的资产，100% 填充日借币利率。
2. `borrow_check_max_calls` 只限制 `maxBorrowable` 可借额度探测，不限制 next-hourly 利率请求。
3. top-N 外资产可以显示“有利率 / 净收益，但可借额度未探测”。
4. next-hourly 未返回的资产必须明确保持 `daily_interest_account=null`，不得伪造。
5. bStock 负费率借币套利仍禁用。
6. 所有测试通过。
7. live smoke test 只读，不触发交易、借币、还币、划转。

量化验收：

```text
rate_probe_assets_count >= borrowability_probe_assets_count
next_hourly_returned_assets_count > current_top50_returned_assets_count
rate_missing_reason distinguishes:
  - next_hourly_missing
  - borrowability_not_probed
  - private_channel_disabled
```

如果不新增字段，至少在 `60-test-output.txt` 或 implementation report 中输出上述统计。

---

## 9. 建议阶段拆分

推荐新开后端 fix stage：

```text
stage-id: 2026-07-borrow-cost-coverage-v2
complexity: MEDIUM
owner: claude_glm
review-1: kimi
review-2: codex 或 claude/fable5，按 Harness 规则
```

任务：

1. Task A: 补 full-candidate next-hourly 只读上限探测并落样本。
2. Task B: 解耦 rate asset set 与 maxBorrowable budget。
3. Task C: 测试与只读 live smoke。

不纳入本阶段：

- maxBorrowable rotating queue。
- per-asset tier synthesis。
- WebSocket。
- 开仓相关逻辑。

这些后续阶段应在本阶段确认 UI 利率覆盖恢复后再做。

---

## 10. 给 Claude/Fable5 的 DRAFT-2 Review 启动文案

```text
请只读 review 以下 DRAFT-2 fix 方案，不修改文件：

reports/agent-runs/private-account-v1-direction/borrow-cost-coverage-v2-fix-plan-draft2.md

背景：
- DRAFT-1: reports/agent-runs/private-account-v1-direction/borrow-cost-coverage-v2-fix-plan.md
- Claude REWORK: reports/agent-runs/private-account-v1-direction/borrow-cost-coverage-v2-fix-plan-review-claude.md
- Kimi endpoint survey: reports/agent-runs/private-account-v1-direction/endpoint-recon-kimi-borrow-rate-v2.md
- Evidence samples: reports/api-samples/private-account-v1-direction/borrow-rate-endpoint-survey-20260707T120945Z/

请重点判断：
1. DRAFT-2 是否正确吸收了“真实根因是 rate input set 与 maxBorrowable budget 被绑在一起”。
2. immediate fix 是否应聚焦“解耦 next-hourly 全量利率覆盖与 maxBorrowable top-N 可借性探测”。
3. 暂不做 per-asset tier synthesis 是否合理。
4. next-hourly 单次资产上限是否已被列为开发前阻塞验证。
5. 测试和验收标准是否能防止再次把可借性未探测误显示为利率缺失。

输出 ACCEPT / REWORK，并列出必须修正项。
```

---

本地北京时间: 2026-07-07 20:40:55 CST  
下一步模型: Claude/Fable5  
下一步任务: review borrow-cost coverage v2 fix plan DRAFT-2

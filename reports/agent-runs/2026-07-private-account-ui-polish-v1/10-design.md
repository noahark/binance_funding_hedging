# Design: Private Account UI Polish V1

## Summary

本 stage 在 `2026-07-private-account-v1` 已冻结契约之上做四项展示打磨：

1. 净收益列补展示实际借币日利率，但只在 `borrow_rate_source != null` 的成本腿命中行展示。
2. `negative_funding_status` 的 UI 文案先遵守结构优先级，再对 `PRIVATE_BORROW_VALIDATION_REQUIRED` 行按 `borrow_validation` 细分。
3. `private_account` 面板上移到市场表之上，保持关闭/失败态不白屏。
4. 账户余额每资产展示 USDT 折算值。该项需要 additive 契约变更：后端在 `balances_unified[]` / `balances_spot[]` 行上补 `value_usdt`，前端只展示。

本设计不新增 Binance 端点、不新增交易/借币/划转/websocket 行为、不改变净收益算法、成本腿链、排序语义或私有通道开关。第 4 项只加 nullable 字段，不改变既有字段/枚举含义，wire `schema_version` 继续保持 `public-market-snapshot/v1`。

## Assumptions

- `designer=Codex`，`implementer=Kimi`，`review-2=Claude/Fable5`。Codex 不实现、不做终审。
- `00-task.md` 中“持仓每资产折算 USDT”的旧措辞按本次派发 prompt 裁决解释为“个人账户余额每资产折算 USDT”。范围只包括 `private_account.balances_unified[]` 和 `private_account.balances_spot[]`。
- `private_account.um_positions[]` 是合约持仓敞口视图，不是账户余额；其名义价值仍不得计入 `total_value_usdt`，本 stage 不给 `um_positions[]` 增加 `value_usdt`。
- 现有 `reports/api-samples/2026-07-private-account-v1/*/api-v3-ticker-price.json` 已证明 `/api/v3/ticker/price` 是可用公开价格源，但本 stage 仍需在当前 stage 路径下携带 raw public sample，满足 frozen contract amendment 证据门。
- 前端继续遵守中文优先，不引入客户端排序，不在前端重新计算净收益或总资产。

## Design Decisions

### 1. 净收益列补借币日利率

前端在现有净收益列内增加第二行小字，格式：

```text
<净收益百分比> <成本来源徽标>
日借币: <借币日利率百分比>[参考]
```

渲染规则：

| 条件 | 借币日利率来源 | 展示 |
| --- | --- | --- |
| `row.borrow_rate_source == null` | N/A | 不展示借币成本子行，或展示 `日借币: -`，由实现按空间选择一种并在 self-check 固定 |
| `row.borrow_rate_source != null` 且 `classic_margin.daily_interest_account != null` | `row.borrow_validation.classic_margin.daily_interest_account` | `日借币: +0.01%` |
| `row.borrow_rate_source != null` 且账户档为空、`daily_interest_vip0 != null` | `row.borrow_validation.classic_margin.daily_interest_vip0` | `日借币: +0.01%` + `参考` 徽标 |
| `row.borrow_rate_source != null` 但两者都为空 | N/A | `日借币: -` |

实现约束：

- 日借币利率使用现有 `formatFundingRate` 格式化，保留当前“省略小数末尾 0”的 UI 规则。
- 正费率行不展示借币成本，因为契约定义正费率 `net_daily_yield = daily_funding_rate`，没有借币腿。
- `vip0_reference` 必须继续保留显著参考标识，避免把 VIP0 参考费率误读为账户真实费率。

### 2. `negative_funding_status` UI 文案派生

新增前端纯函数，例如 `negativeFundingDisplay(row)`，输入整行 row，而不是只传 `row.negative_funding_status`。

决策表：

| 优先级 | 输入 | 中文文案 | 样式建议 |
| --- | --- | --- | --- |
| 1 | `negative_funding_status == "DISABLED_PERP_ONLY"` | `仅合约: 无现货腿` | muted |
| 2 | `negative_funding_status == "DISABLED_BSTOCK"` | `bStock: 负费率不可借` | danger |
| 3 | `negative_funding_status == "DISABLED_SPOT_ONLY"` | `仅现货: 无杠杆借币` | warn |
| 4.1 | `PRIVATE_BORROW_VALIDATION_REQUIRED` + `borrow_validation.verified == true` + `pair_listed == true` + `asset_borrowable == true` | `已验证可借` | success |
| 4.2 | `PRIVATE_BORROW_VALIDATION_REQUIRED` + `borrow_validation.verified == true` + `pair_listed == false` | `杠杆交易对未列出` | warn |
| 4.3 | `PRIVATE_BORROW_VALIDATION_REQUIRED` + `borrow_validation.verified == true` + `asset_borrowable == false` | `资产不可借` | danger |
| 4.4 | `PRIVATE_BORROW_VALIDATION_REQUIRED` + `borrow_validation.verified == false` + `error == "not_probed_this_round"` | `未探测(限速预算)` | muted |
| 4.5 | `PRIVATE_BORROW_VALIDATION_REQUIRED` + private channel disabled/failed/缺字段 | `需私有验证` | warn |

实现约束：

- 结构禁用状态不得被 `borrow_validation` 覆盖。
- 原始枚举可以放入 `title` 供审计，例如 `title="PRIVATE_BORROW_VALIDATION_REQUIRED"`，但可见主文案以中文为主。
- `badgeForNegativeFundingStatus(ns)` 可以替换为 `badgeForNegativeFundingStatus(row)`；调用点必须同步。

### 3. 个人账户面板上移

DOM 顺序调整为：

```text
topbar
warnings-panel
private-panel
market-panel
footer
```

当前 `private-panel` 在市场表之后；实现只移动 `<section class="panel" id="private-panel">...</section>` 到市场表 `<section class="panel">` 之前。`renderPrivatePanel()` 的逻辑不需要因为 DOM 移动而改写。

降级规则：

- `private_account` 缺失：面板隐藏，不占位，不影响市场表渲染。
- `private_account.verified != true`：面板显示关闭/失败占位，继续展示错误原因，不白屏。
- 隐私开关行为保持不变，金额默认隐藏。

### 4. 账户余额每资产 USDT 折算

选择方案 A：后端直接在余额行输出 `value_usdt`。

字段形态：

```json
"private_account": {
  "balances_unified": [
    {
      "asset": "BTC",
      "total_balance": "0.01000000",
      "value_usdt": "600.00000000"
    }
  ],
  "balances_spot": [
    {
      "asset": "ETH",
      "free": "0.10000000",
      "locked": "0.02000000",
      "value_usdt": "360.00000000"
    }
  ]
}
```

Schema 变更：

- `schemas/api/public-market/snapshot.schema.json`
- 在 `$defs.private_account.properties.balances_unified.items.properties` 添加 `value_usdt`：
  - `anyOf: decimal_string | null`
  - 不加入 `required`，保持 additive/backward compatible；但后端新输出必须由测试断言存在。
- 在 `$defs.private_account.properties.balances_spot.items.properties` 添加同形态 `value_usdt`。
- `um_positions` 不变。

后端口径：

- `balances_unified[].value_usdt = total_balance * price(asset)`
- `balances_spot[].value_usdt = (free + locked) * price(asset)`
- `USDT` / `USDC` 等稳定美元资产价格按 1。
- 缺价格、坏价格、坏数量、空数量时：该行 `value_usdt = null`，同时沿用/补充 warning。
- 合法零余额或合法计算结果为 0 时：`value_usdt = "0.00000000"`。
- `total_value_usdt` 仍是顶层权威聚合；缺价格资产按现有规则计 0 + warning。前端不得用行 `value_usdt` 反算总资产。

契约文档建议追加到 `docs/api/public-market-contract.md` 的 v0.3 amendment 后，作为 v0.4 additive amendment：

```markdown
## Private Account UI Polish Amendment (v0.4, stage `2026-07-private-account-ui-polish-v1`)

Wire `schema_version` stays `public-market-snapshot/v1`. This amendment only adds
nullable per-balance valuation fields to `private_account`.

- `private_account.balances_unified[].value_usdt`: 8-place decimal string | null.
  Backend-computed USDT value of `total_balance` using the same P5
  `/api/v3/ticker/price` map as `total_value_usdt`. Stable USD assets use price
  1. `null` means valuation is unavailable because amount or price is missing or
  invalid; `"0.00000000"` means a valid priced zero value.
- `private_account.balances_spot[].value_usdt`: 8-place decimal string | null.
  Backend-computed USDT value of `free + locked` using the same valuation rules.
- `private_account.um_positions[]` remains an exposure view. It does not carry
  `value_usdt` and its notional value is never included in `total_value_usdt`.

The frontend renders `value_usdt` as display-only data and must not recompute
`total_value_usdt` or derive trading decisions from per-row values.
```

样本证据要求：

- 在 `reports/api-samples/2026-07-private-account-ui-polish-v1/<timestamp>/` 落当前 stage 的 raw public sample：
  - `api-v3-ticker-price.json`
  - `evidence-index.md`
- 可复用既有 capture 脚本或以 no-key `GET /api/v3/ticker/price` 重新抓取。若网络临时不可用，可复制既有 raw sample 到当前 stage 路径并在 `evidence-index.md` 写明来源 sha/provenance；但不能只引用合成 fixture。

前端展示：

- 统一账户余额卡片新增一行：`折算: <value_usdt> USDT`。
- 现货账户余额卡片新增一行：`折算: <value_usdt> USDT`。
- `value_usdt == null` 或字段缺失：显示 `折算: -`。
- 隐私开关同时遮蔽余额和折算值；隐藏态均显示 `****`。

## Task Breakdown

### Task A: backend/schema/contract additive valuation fields

Owner: Kimi

Allowed files:

- `backend/domain/snapshot.py`
- `backend/services/snapshot_service.py` only if wiring requires no semantic change beyond passing existing price map
- `schemas/api/public-market/snapshot.schema.json`
- `docs/api/public-market-contract.md`
- `backend/tests/test_private_account_v1.py`
- `backend/tests/test_snapshot.py`
- `backend/tests/fixtures/private-account-v1-design.json`
- `reports/api-samples/2026-07-private-account-ui-polish-v1/**`

Implementation checklist:

- Extend `assemble_private_account()` output rows with optional `value_usdt`.
- Keep top-level `total_value_usdt` unchanged and keep anti-double-count behavior.
- Preserve `um_positions` shape exactly.
- Add schema properties for `value_usdt` on unified/spot balance rows.
- Add v0.4 contract amendment text.
- Add raw public ticker sample evidence under current stage path.

### Task B: frontend display polish

Owner: Kimi

Allowed files:

- `frontend/index.html`
- `frontend/self-check.js`
- `frontend/fixture/public-market-snapshot.json`

Implementation checklist:

- Add borrow-rate subline in the net-yield column using the rules above.
- Replace negative funding status badge logic with row-aware structural-priority function.
- Move `private-panel` before the market table panel.
- Render `value_usdt` in unified/spot balance cards, with privacy masking and `-` fallback.
- Keep UI Chinese-first.
- Keep frontend zero-sort.

### Task C: stage evidence and handoff

Owner: bookkeeper after implementation

Required evidence:

- `20-implementation.md`
- `60-test-output.txt`
- `70-handoff.md`
- raw sample evidence index for `/api/v3/ticker/price`
- updated `status.json` with task owner, changed files, tests, and checkpoint output

## Test Strategy

Backend:

- `python3 -m pytest backend/tests/test_private_account_v1.py -q`
- `python3 -m pytest backend/tests/test_snapshot.py -q`
- `python3 -m pytest backend/tests -q`

Backend assertions to add:

- `assemble_private_account()` emits `balances_unified[].value_usdt` from `totalWalletBalance * price`.
- `assemble_private_account()` emits `balances_spot[].value_usdt` from `(free + locked) * price`.
- `USDT`/`USDC` stable assets value at 1.
- Missing price produces row `value_usdt is None`, warning exists, and `total_value_usdt` remains consistent with existing zero-count behavior.
- Legit zero balance produces `"0.00000000"`, not null.
- `um_positions[]` has no `value_usdt`.
- Schema validates updated fixture.
- Anti-double-count tests still pass.

Frontend:

- `node frontend/self-check.js`

Frontend assertions to add:

- Rows with `borrow_rate_source != null` show `日借币` value.
- Rows with `borrow_rate_source == null` do not show a borrow-cost value.
- VIP0 fallback shows `参考`.
- Structural `negative_funding_status` values keep structural Chinese labels.
- `PRIVATE_BORROW_VALIDATION_REQUIRED` rows map through `borrow_validation` to all five detailed labels.
- `private-panel` appears before the market table in DOM.
- `private_account` disabled/error states still do not white-screen.
- Unified and spot balance cards show `折算` value; missing/null value shows `-`.
- Privacy hidden state masks both raw balances and `value_usdt`.

Schema/contract evidence:

- Validate updated `frontend/fixture/public-market-snapshot.json` against `schemas/api/public-market/snapshot.schema.json`.
- Preserve a raw public `/api/v3/ticker/price` sample under `reports/api-samples/2026-07-private-account-ui-polish-v1/`.

## Risks

- The old `00-task.md` wording says “持仓每资产”，which can be misread as UM position notional. This design narrows it to account balance valuation and explicitly excludes `um_positions`.
- Row-level `value_usdt=null` while top-level total counts missing price as 0 may look inconsistent. UI copy should treat null as “无法折算”，not as zero.
- Adding `value_usdt` as optional schema fields preserves backward compatibility, but backend tests must still require the new producer output.
- Moving the private panel can increase vertical height before the market table. The panel already supports disabled/hide states; review should check mobile layout for no overlap.

## Raw Artifact Requirements For Review

Reviewers must inspect:

- `00-intake.md`, `00-task.md`, this `10-design.md`, and `11-adr.md`.
- Diff for schema, backend, frontend, fixture, contract, and tests.
- `60-test-output.txt` with backend pytest and frontend self-check outputs.
- Raw public sample under `reports/api-samples/2026-07-private-account-ui-polish-v1/`.
- Updated `frontend/fixture/public-market-snapshot.json`.
- `status.json` task routing and final diff fingerprint.

模型身份: GPT-5 / Codex
本地北京时间: 2026-07-07 CST
下一步模型: Kimi
下一步任务: 按本设计实现 Task A/B，并在完成后交由 Fable5/bookkeeper 组织 review-1/review-2。

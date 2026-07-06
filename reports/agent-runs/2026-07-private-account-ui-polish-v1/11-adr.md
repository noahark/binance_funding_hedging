# ADR: Private Account UI Polish V1

## Context

`2026-07-private-account-v1` 已冻结 private account、borrow validation、net yield、sort basis 等契约。用户验收后提出四项展示打磨：

- 净收益列需要看见被扣掉的借币日利率。
- `negative_funding_status` 的结构字段不能继续直接显示为“需私有验证”。
- 个人账户面板应上移到市场表之前。
- 账户余额需要按资产展示 USDT 折算值。

前三项可纯前端完成。第四项当前 payload 只给顶层 `private_account.total_value_usdt`，不暴露单资产价格或单资产折算值；前端无法在不新增数据的情况下准确计算。因此本 stage 允许一处 additive 契约变更。

## Decision

### ADR-1: 借币日利率只在成本腿命中行展示

净收益列补展示借币日利率，但门控条件是 `row.borrow_rate_source != null`。

原因：

- 正费率行没有借币腿，`net_daily_yield = daily_funding_rate`。
- 无成本腿行的 `net_daily_yield` 为 null 或不含成本扣减，展示借币利率会误导。
- `borrow_rate_source` 是最直接的“该行净收益扣过借币成本”的 UI 依据。

显示来源优先级：

1. `row.borrow_validation.classic_margin.daily_interest_account`
2. `row.borrow_validation.classic_margin.daily_interest_vip0`，并标注“参考”
3. 两者都缺失则显示占位

### ADR-2: 负费率状态文案先结构优先，再私有验证细分

`negative_funding_status` 的结构优先级保持不变：

1. `DISABLED_PERP_ONLY`
2. `DISABLED_BSTOCK`
3. `DISABLED_SPOT_ONLY`
4. `PRIVATE_BORROW_VALIDATION_REQUIRED`

只有第 4 类才按 `borrow_validation` 细分为“已验证可借 / 杠杆交易对未列出 / 资产不可借 / 未探测(限速预算) / 需私有验证”。结构禁用行不允许派生为“需私有验证”。

### ADR-3: 个人账户面板移动到市场表之前

DOM 顺序改为 warnings -> private account -> market table。`renderPrivatePanel()` 的状态机不变：

- 缺 `private_account`：隐藏。
- `verified=false`：显示关闭/失败占位。
- `verified=true`：显示资产总览、余额、UM 持仓敞口。

### ADR-4: 选择方案 A，后端输出每个余额行的 `value_usdt`

在 `private_account.balances_unified[]` 和 `private_account.balances_spot[]` 上新增 optional nullable 字段 `value_usdt`。

不暴露 `price_map`，不让前端重新相乘。后端继续是估值单一真相源。

字段定义：

- `balances_unified[].value_usdt`: 8-place decimal string | null
- `balances_spot[].value_usdt`: 8-place decimal string | null
- `um_positions[]`: 不新增 `value_usdt`

计算规则：

- unified: `total_balance * price(asset)`
- spot: `(free + locked) * price(asset)`
- `USDT` / `USDC` 稳定美元资产价格为 1
- 合法零值输出 `"0.00000000"`
- 缺价格、坏价格、坏数量、空数量输出 `null`

顶层 `total_value_usdt` 仍保持现有行为和权威性。前端不得从行级 `value_usdt` 反推总资产。

### ADR-5: Schema optional，producer test required

`value_usdt` 加入 schema properties，但不加入 item `required`。

理由：

- 这是 additive/backward-compatible 字段。
- 前端应能优雅处理旧 payload 或字段缺失。
- 但后端新 producer 必须由测试断言输出 `value_usdt`，避免“schema 可选”变成“实现漏吐”。

### ADR-6: Contract evidence requires current-stage raw public sample

虽然 `reports/api-samples/2026-07-private-account-v1/` 已有 `/api/v3/ticker/price` raw sample，本 stage 是新的 frozen contract amendment。为满足 Harness hard gate，当前 stage 必须在：

```text
reports/api-samples/2026-07-private-account-ui-polish-v1/
```

携带 raw public sample 和 evidence index。可以 fresh no-key capture；如网络不可用，可复制既有 raw sample 并在 index 写明原始路径和 sha，但不能只用 synthetic fixture。

## Alternatives

### Alternative A: 后端输出 `value_usdt`（采纳）

优点：

- 与顶层 `total_value_usdt` 共用同一估值源。
- 前端无需暴露或处理完整价格 map。
- 避免前后端在 Decimal、稳定币、缺价格、坏价格语义上漂移。
- payload 增量小。

缺点：

- 需要 schema 和契约文档 additive amendment。
- 需要后端测试覆盖 null vs zero。

### Alternative B: 暴露 `price_map` 或逐资产 price（拒绝）

优点：

- 前端可以自行计算展示。
- 后端行结构少改。

拒绝原因：

- 前端会复制估值算法，容易和 `total_value_usdt` 漂移。
- `price_map` 全量暴露会扩大 payload，且多数价格对 UI 没用。
- null/0/缺价格语义会分散到前端。

### Alternative C: 只展示顶层总资产，不做每资产折算（拒绝）

拒绝原因：

- 不满足用户本 stage 的展示诉求。
- 当前后端已经具备 price map 和逐资产估值能力，只是未吐出行级值。

### Alternative D: 给 `um_positions[]` 增加名义价值（拒绝）

拒绝原因：

- `um_positions[]` 是 exposure view，不是账户余额。
- 合约名义价值不得计入 `total_value_usdt`，这是 private-account-v1 anti-double-count 硬规则。
- 如果未来要展示持仓名义价值，应另开需求并单独命名，例如 `notional_usdt`，不能混入本 stage 的余额折算。

## Tradeoffs

- `value_usdt` optional 能兼容旧 payload，但需要 producer tests 保证新实现输出。
- 行级 `value_usdt=null` 与顶层 missing-price-counted-at-0 的聚合规则会让“行求和”和总值不完全等价；文案必须把 null 表示为“无法折算”，而不是 0。
- 私有面板上移会让市场表下移，但该页面是工作台而非营销页，账户状态对后续人工判断更重要。
- 负费率文案中文化会降低枚举直读性；用 `title` 保留原始枚举即可。

## Edge Cases

- `borrow_rate_source != null` 但 `borrow_validation` 缺失：净收益仍展示，借币日息显示 `-`，不白屏。
- `daily_interest_account == null` 且 `daily_interest_vip0 != null`：显示 VIP0 参考利率并标“参考”。
- `daily_interest_account == "0.00000000"`：显示 `0%`，不是占位。
- `DISABLED_BSTOCK` 行即使带 `borrow_validation`，也保持 `bStock: 负费率不可借`。
- `private_account` 缺失：面板隐藏，市场表正常。
- `private_account.verified=false`：面板显示占位和错误原因，市场表正常。
- `balances_unified[].value_usdt == null`：显示 `折算: -`。
- `balances_unified[].value_usdt == "0.00000000"`：显示 `折算: 0 USDT` 或等价格式。
- 隐私隐藏态：`total_value_usdt`、余额数量、`value_usdt` 全部遮蔽。
- 旧 fixture/旧后端没有 `value_usdt`：前端优雅显示 `-`。

## Links

- `reports/agent-runs/2026-07-private-account-ui-polish-v1/00-intake.md`
- `reports/agent-runs/2026-07-private-account-ui-polish-v1/00-task.md`
- `docs/api/public-market-contract.md`
- `schemas/api/public-market/snapshot.schema.json`
- `backend/domain/snapshot.py`
- `frontend/index.html`
- `frontend/self-check.js`
- Existing public ticker evidence:
  - `reports/api-samples/2026-07-private-account-v1/20260705T162920Z/api-v3-ticker-price.json`
  - `reports/api-samples/2026-07-private-account-v1/20260705T232800Z/api-v3-ticker-price.json`

## Reviewer Notes

- `um_positions[]` intentionally does not get `value_usdt`. This is not an omission; it preserves the existing exposure-view vs account-balance separation.
- `value_usdt` is optional in schema but required by backend producer tests. This is deliberate backward compatibility.
- Missing price row value is `null`, not `"0.00000000"`. Legit zero value remains `"0.00000000"`.
- Contract amendment can reuse the established `/api/v3/ticker/price` evidence only if the raw sample is carried into the current stage evidence path or a provenance index is created there.
- `negative_funding_status` visible text becomes Chinese-first, but raw enum should remain available in `title` or raw JSON for audit.
- Codex designed this stage and is ineligible for final review. Fable5/Claude should review the implementation against this ADR, not ask Codex for a second opinion.

模型身份: GPT-5 / Codex
本地北京时间: 2026-07-07 CST
下一步模型: Kimi
下一步任务: 实现 `value_usdt` additive 字段、前端展示打磨、测试与 raw public sample 证据。

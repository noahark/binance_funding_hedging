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

## v1.1-ui-polish-2 Design Addendum

本增量覆盖 `00-task.md` Scope 增补 item 5-10。它复用 round-1 已落地的
`balances_unified[].value_usdt` / `balances_spot[].value_usdt` 字段，只补展示规则、余额排序、
卡片删减、时间合并和审计文案。Codex 本轮仍只做设计，不改实现代码、schema 或契约正文。

### Contract Change Gate Conclusion

- 不触发契约字段或枚举变更：`value_usdt` 已在 v0.4 additive amendment 中存在，`valuation.priced_at`
  与 `checked_at` 也已存在。
- `private_account.balances_unified[]` / `private_account.balances_spot[]` 的排序是数组顺序行为变更，
  不是字段、枚举或 `schema_version` 变更。
- 市场 `rows` 的冻结顺序绝不变更。`docs/api/public-market-contract.md` 的
  `Row order (frozen)` 仍是 `abs(Decimal(daily_funding_rate))` DESC、null last、`symbol` ASC，
  且后续 v0.3 `sort_basis` 行为也不受本增量影响。
- 建议实现阶段只在 `docs/api/public-market-contract.md` v0.4 amendment 追加一句展示约定：
  `private_account.balances_unified[]` and `private_account.balances_spot[]` are emitted by
  `value_usdt` DESC, null last, `asset` ASC. 这是 additive-only 说明，`schema_version` 仍为
  `public-market-snapshot/v1`，不修改 frozen market `rows` 语义。

### Item 5: 余额行内折算

HOW:

- 前端把统一账户和现货账户余额卡片的折算值从独立 `折算:` 行改为金额行内追加：
  `金额 【: 123.45 USDT】`。
- 源字段只用 `b.value_usdt`。前端不得用余额数量和价格自行重算，也不得用行级值反推
  `private_account.total_value_usdt`。
- `value_usdt` 可见格式固定为 2 位小数，舍入方式为 `ROUND_HALF_UP`。实现应优先使用
  decimal-string helper 处理 8 位字符串，避免 `Number(...).toFixed(2)` 的二进制舍入漂移。
  规则是对绝对值做 half-up 到 cents 后再恢复符号。
- `value_usdt == null`、字段缺失或空字符串：显示 `【: — USDT】`。
- 合法零值 `"0.00000000"`：显示 `【: 0.00 USDT】`，不是缺失占位。
- 隐私开关开启时，余额数量与折算值同时遮蔽。建议统一账户显示
  `**** 【: ****】`，现货账户的 `free`、`locked` 和折算值也都使用 `****`。

涉及文件/函数:

- `frontend/index.html`: `renderPrivatePanel()` 内 unified/spot balance card 渲染；
  新增/替换 `formatUsdt2(valueUsdt)` 或等价 decimal-string helper；复用 `maskAmount` 的隐私状态但不要复用
  `formatPrice` 作为 2 位 USDT 格式化器。
- `frontend/self-check.js`: 增加 2 位显示、null 占位、合法零、隐私遮蔽断言。

边界与降级:

- `private_account` 缺失或 `verified=false` 的面板降级逻辑不变。
- 旧 payload 缺少 `value_usdt` 时不白屏，按 `【: — USDT】` 展示。

### Item 6: 后端排序 `balances_*`

HOW:

- 在 `backend/domain/snapshot.py` 的 `assemble_private_account()` 内排序最终输出的
  `unified_out` 和 `spot_out`。
- 排序范围只限 `private_account.balances_unified` 与 `private_account.balances_spot`。
  不调用、不修改 `sort_rows()`，不触碰市场 `rows`。
- 主键：`value_usdt` 降序。
- null / 缺失 / 防御性非法值：一律排最后。
- 确定性 tie-break：`asset` ASC；如同 asset 重复，保留原输入顺序作为最终稳定 tie-break。

排序伪码:

```python
from decimal import Decimal, InvalidOperation

def _balance_sort_key(row_with_index):
    idx, row = row_with_index
    raw = row.get("value_usdt")
    asset = str(row.get("asset") or "")
    try:
        value = Decimal(str(raw)) if raw not in (None, "") else None
    except (InvalidOperation, ValueError, TypeError):
        value = None
    if value is None:
        return (1, Decimal("0"), asset, idx)
    return (0, -value, asset, idx)

unified_out = [row for _, row in sorted(enumerate(unified_out), key=_balance_sort_key)]
spot_out = [row for _, row in sorted(enumerate(spot_out), key=_balance_sort_key)]
```

涉及文件/函数:

- `backend/domain/snapshot.py`: `assemble_private_account()` only。
- `backend/tests/test_private_account_v1.py`: 新增 pytest，覆盖 unified 与 spot 的 value 降序、
  null last、同值按 asset ASC、市场 `rows` 排序不受影响。

契约边界:

- 这是 private account balance array order 变更，非契约字段/枚举变更。
- 必须显式保护 frozen market rows：`sort_rows()` 和 `docs/api/public-market-contract.md`
  `Row order (frozen)` 不改。

### Item 7: 删除「估值来源」overview 卡

HOW:

- 前端 `renderPrivatePanel()` 中删除 overview 的「估值来源」卡。
- payload 继续保留 `private_account.valuation.price_source`，schema 与后端输出不变。
- 变量 `priceSource` 如只服务被删卡片，应移除以免死代码；如用于 raw audit 或 title，可保留但不可见展示。

涉及文件/函数:

- `frontend/index.html`: `renderPrivatePanel()` overview markup。
- `frontend/self-check.js`: 断言私有面板不再出现可见文本 `估值来源`，同时 fixture/payload 中
  `price_source` 仍存在。

### Item 8: 删除矛盾运行约束

HOW:

- 删除侧栏页脚中 `公开行情 · 只读展示 · 不连接 Binance` 这一运行约束文案；推荐删除整个
  `.sidebar-footer` block，避免留下与私有 HMAC 通道矛盾的概括。
- 不新增任何暗示“无需 key”“不连接 Binance”的替代说法。

涉及文件/函数:

- `frontend/index.html`: 侧栏 534-537 附近静态 DOM。
- `frontend/self-check.js`: 断言页面文本不含 `不连接 Binance`。

### Item 9: 时点合一

HOW:

- 仅前端合并展示。后端 `assemble_private_account()` 继续输出
  `valuation.priced_at = checked_at` 和顶层 `checked_at`，保持契约稳定。
- verified=true 时，私有面板副标题从 `只读资产视图` 改为
  `资产更新时间 <时间>`。时间取 `pa.checked_at`，缺失时 fallback 到 `pa.valuation.priced_at`，
  都缺失时展示 `资产更新时间 —`。
- overview 删除「估值时点」「检查时点」两张卡。
- verified=false 时可继续显示状态副标题，但建议用 item 10 的 `私有账户未读取` 口径。

涉及文件/函数:

- `frontend/index.html`: `renderPrivatePanel()` 中 `privatePanelSubtitle`、overview markup。
- `frontend/self-check.js`: 断言副标题包含 `资产更新时间`，且可见 overview 不再出现
  `估值时点` / `检查时点`。

契约边界:

- 后端字段保持不变。`priced_at` 和 `checked_at` 的现有同值事实继续由后端保证。
- 不需要 schema 或 contract 字段更新。

### Item 10: 审计文案校准

backend 事实:

- `_private.fetch_*` 私有通道是真实 signed HMAC 连接 Binance。
- deny-by-default：无 key、配置关闭或请求失败时 `classic_ref=None`，`private_account.verified=false`，
  公开行情 snapshot 仍渲染。
- 本产品仍只读：不下单、不借币、不还币、不划转。

精确替换表:

| 位置 | 原文 | 新文 |
| --- | --- | --- |
| 侧栏 brand subtitle | `公开数据 · 只读` | `行情公开 · 账户私有只读` |
| 侧栏运行约束 strong | `公开行情 · 只读展示 · 不连接 Binance` | 删除该侧栏页脚，不展示替换文案 |
| 顶栏 subtitle | `公开数据 · 只读` | `行情公开 · 账户需 key 私有只读` |
| 顶栏 badge | `公开数据` | `行情公开` |
| 顶栏 badge | `只读` | `账户只读` |
| 数据说明 subtitle | `来自后端快照服务的公开验证限制与展示约定` | `来自后端快照服务的行情公开数据与账户私有只读验证说明` |
| `WARNING_CHINESE[0]` | `杠杆交易对官方清单需 API key（当前无 key 阶段），杠杆可借性未经私有验证；候选判断使用公开现货 isMarginTradingAllowed 字段。` | `杠杆交易对与可借性通过私有只读 API key 验证；未配置或请求失败时标为需私有验证，候选初筛仍使用公开现货 isMarginTradingAllowed 字段。` |
| `marginPublicNote` span | `杠杆可借性未经私有验证（当前为公开数据阶段）` | `账户与借币验证通过私有只读 API key 读取；未配置或失败时降级为需私有验证，公开行情仍可展示。` |
| verified=true 私有面板 subtitle | `只读资产视图` | `资产更新时间 <YYYY-MM-DD HH:mm:ss>`；无时间为 `资产更新时间 —` |
| verified=false 私有面板 subtitle | `私有通道未启用` | `私有账户未读取` |
| verified=false empty-state strong | `私有通道未启用` | `私有账户未读取` |
| verified=false empty-state body | `当前未获取到账户资产数据` | `未配置 API key 或私有只读请求失败，未获取到账户资产数据` |
| verified=false help text | `请检查 API key 权限或后端私有通道配置` | `请检查 API key 权限、IP 白名单或后端私有通道配置；系统不会下单或划转` |

文案边界:

- 可以保留 `行情公开`，但不要再把账户数据称为 `公开数据`。
- 必须保留 `只读`，并明确只读含义是“不下单、不划转”；不应写“当前无 key 阶段”。
- 不要写“不连接 Binance”。真实行为是在有 key 时通过 signed HMAC 读取私有账户。

### Incremental Implementation Boundaries

Allowed implementation files for Kimi:

- `backend/domain/snapshot.py`
- `backend/tests/test_private_account_v1.py`
- `backend/tests/test_snapshot.py` only if needed to pin market row order
- `docs/api/public-market-contract.md` only for additive balance-order note
- `frontend/index.html`
- `frontend/self-check.js`
- `frontend/fixture/public-market-snapshot.json` only if self-check fixture needs text/value updates

Forbidden in this increment:

- No schema field/enum change.
- No changes to `rows` ordering, `sort_rows()`, `sort_basis`, classifier/normalizer enums, private HMAC whitelist,
  order/borrow/repay/transfer behavior, or deployment.
- No frontend sorting of balances; the frontend renders backend payload order.

### Incremental Test Strategy

Backend:

- `python3 -m pytest backend/tests/test_private_account_v1.py -q`
- `python3 -m pytest backend/tests/test_snapshot.py -q`
- `python3 -m pytest backend/tests -q`

Required backend assertions:

- `assemble_private_account()` sorts unified and spot balances by `value_usdt` DESC.
- `value_usdt is None` rows sort after all valued rows.
- Equal `value_usdt` ties sort by `asset` ASC.
- Existing market `rows` order tests remain green; add a regression assertion if existing coverage does not explicitly guard it.

Frontend:

- `node frontend/self-check.js`

Required frontend assertions:

- Balance cards render `金额 【: 123.45 USDT】` with 2-place `ROUND_HALF_UP` display.
- `value_usdt == null` renders `【: — USDT】`; `"0.00000000"` renders `【: 0.00 USDT】`.
- Privacy hidden state masks both raw amount and row valuation.
- `估值来源`、`估值时点`、`检查时点` are no longer visible in the private overview.
- `price_source` remains in fixture/payload.
- Private subtitle displays `资产更新时间 <time>`.
- Page text no longer contains `不连接 Binance`、`当前无 key 阶段` or account data described as `公开数据`.

模型身份: GPT-5 / Codex
本地北京时间: 2026-07-07 15:31:49 CST
下一步模型: Fable5
下一步任务: design_review 本增量设计；若 ACCEPT，则派 Kimi 实现 item 5-10。

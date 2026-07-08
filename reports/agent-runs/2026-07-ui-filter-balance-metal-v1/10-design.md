# 10-design：UI 过滤 / 余额格式 / 金属标签

## 设计状态

已吸收 Kimi/GLM 预实现 review 和用户裁定。未进入实现。

## 1. 前端低日费率过滤

### 当前实现

- 筛选状态在 `frontend/index.html` 的 `state.filters`：
  - `search`
  - `assetTag`
  - `routeClass`
  - `showPerpOnly`
- `filteredRows()` 当前依次应用搜索、资产标签、路由分类、PERP_ONLY 显示开关。

### 目标设计

新增：

```js
const LOW_DAILY_RATE_THRESHOLD = '0.00030000'; // 0.03%
state.filters.hideLowDailyRate = true;
```

UI 控件放在 `filter-show-perp-only` 后：

```html
<input id="filter-hide-low-daily-rate" type="checkbox" checked />
隐藏 |日费率| ≤ 0.03%
```

过滤逻辑：

- 需要避免 `Number`/float 参与契约判断；前端已有 `formatFundingRate` 用 string-shift。实现可用字符串 Decimal helper 或保守转为整数基点比较。
- 建议实现 `absDailyRateAtOrBelowThreshold(rateStr)`：
  - 接收 decimal string。
  - 解析为符号、整数、小数；补齐到 8 位小数。
  - 比较 `abs(rate) <= 0.00030000`。
  - 无法解析 / null → false（不隐藏）。

测试策略：

- 不直接改变 self-check 默认 6 行基线的断言。为低费率过滤使用独立 fixture/deep-copy 场景，避免 `backend/tests/fixtures/private-account-v1-design.json` 中现有边界行使所有默认行数断言连锁变化。
- 增加行 `daily_funding_rate="0.00030000"`，默认隐藏。
- 增加行 `daily_funding_rate="-0.00030000"`，默认隐藏。
- 增加行 `daily_funding_rate="0.00030001"` 或 `"-0.00030001"`，默认保留。
- 取消 checkbox 后隐藏行恢复。

## 2. 账户余额卡片格式

### 当前实现

`renderPrivatePanel()` 使用 `inlineUsdtSuffix(value_usdt)` 把折算值拼进数量行：

```html
<div class="amount">${maskAmount(b.total_balance)}${inlineUsdtSuffix(b.value_usdt)}</div>
```

### 目标设计

替换为独立 helper：

```js
function formatBalanceAmount(value) { ... }     // 整数千分位 + 小数原样保留
function approximateUsdtLine(valueUsdt) { ... } // ≈ 100.09 USDT / ≈ — USDT / ≈ **** USDT
```

统一账户卡片：

```html
<div class="balance-card">
  <div class="asset">USDT</div>
  <div class="amount">100.0861659</div>
  <div class="amount value-usdt">≈ 100.09 USDT</div>
</div>
```

现货账户卡片：

```html
<div class="balance-card">
  <div class="asset">USDT</div>
  <div class="amount">100.0861659</div>
  <div class="amount locked">冻结: 0</div>
  <div class="amount value-usdt">≈ 100.09 USDT</div>
</div>
```

现货账户的数量主行显示 `free`；`locked` 继续保留单独 `冻结:` 行。统一账户继续显示 `total_balance`。

隐私隐藏态：

- 数量行：`****`
- locked 行：`冻结: ****`
- 折算行：`≈ **** USDT`

保留现有 `formatUsdt2` 的 2 位 ROUND_HALF_UP 逻辑。

## 3. 金属资产标签

### 当前实现

`backend/domain/normalize.py::asset_tag_for(contract_type)` 只看 `contractType`：

- `TRADIFI_PERPETUAL` → `BSTOCK`
- `PERPETUAL` → `CRYPTO`
- otherwise → `UNKNOWN`

`build_rows()` 调用时只传 `contract_type`，没有 `base_asset` 上下文。

### 目标设计

改为：

```python
REAL_METAL_BASE_ASSETS = {"XAU", "XAG", "COPPER", "XPT", "XPD"}

def asset_tag_for(contract_type: str, base_asset: str = "") -> tuple:
    if base_asset.upper() in REAL_METAL_BASE_ASSETS:
        return ("METAL", "base_asset_metal_symbol", "HIGH")
    ...
```

`build_rows()` 调用改为传 `obj.get("baseAsset", "")`。

`asset_tag_for` 保留 `base_asset=""` 默认值，兼容既有单参数调用和测试。

### Borrow validation 语义

用户裁定：`METAL` 只是金属产品性质标签，不等同于禁止借币；部分金属可能可借，具体以私有只读接口返回为准。

实现要求：

- 不新增 `DISABLED_METAL`，不改变 `negative_funding_status` enum。
- `negative_funding_status("MARGIN_SPOT_CANDIDATE", "METAL")` 仍为 `PRIVATE_BORROW_VALIDATION_REQUIRED`。
- `select_borrow_candidates()` 的候选资产标签从仅 `CRYPTO` 扩展为 `CRYPTO` 和 `METAL`；其它条件仍保持 `daily_funding_rate < 0`、`route_class == MARGIN_SPOT_CANDIDATE`、按 `base_asset` 去重、按绝对日费率排序。
- 真实可借性、可借额度和借币成本仍由现有私有只读 API / borrow validation 链返回；接口返回不可借或预算外未探测时沿用既有 `borrow_validation` 状态，不伪造收益率。

契约同步：

- `schemas/api/public-market/snapshot.schema.json` 的 `asset_tag` enum 增加 `METAL`。
- `docs/api/public-market-contract.md` 增加说明。
- `frontend/index.html`：
  - 资产标签筛选下拉增加 `METAL(金属)`。
  - `badgeForAssetTag` 增加 `METAL`，建议样式 `info` 或 `warn`，不复用 bStock danger/accent。
- `frontend/fixture/public-market-snapshot.json` 增加至少一行金属样本或修改现有 fixture 中一行以覆盖 UI；需要保证 summary counts 同步。

测试：

- backend normalize 测试：`asset_tag_for("PERPETUAL", "XAU") == ("METAL", ...)`。
- backend snapshot 测试：`XAUUSDT` / `COPPERUSDT` 行输出 `asset_tag=METAL`。
- backend borrow selection 测试：`METAL` + `MARGIN_SPOT_CANDIDATE` + 负日费率进入 `rate_probe_assets` / `borrowability_probe_assets`；bStock 仍不进入。
- schema 测试：含 METAL 行的 snapshot 通过 schema。
- frontend self-check：资产标签下拉与徽章显示 `METAL(金属)`。
- 若能只读采集真实公开样本，放入 `reports/api-samples/2026-07-ui-filter-balance-metal-v1/`；若不能采集，记录为 follow-up，不用合成样本伪装事实证据。

## 4. 风险

- `COPPER` 可能与交易所实际 baseAsset 命名不同；初版只按用户列出的 baseAsset 精确匹配，不做模糊匹配。
- METAL 进入 borrow validation 会增加少量候选资产；仍受既有预算上限和分批逻辑约束。
- 低日费率隐藏默认开启会改变首屏行数；self-check 需要显式断言默认行数变化，避免误判。

本地北京时间: 2026-07-08 09:28:44 CST
下一步模型: codex
下一步任务: 生成实现 prompt 并进入开发。

# 10-design：UI 过滤 / 余额格式 / 贵金属标签

## 设计状态

草稿，等待用户确认。未进入实现。

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
隐藏 ≤0.03% 日费率
```

过滤逻辑：

- 需要避免 `Number`/float 参与契约判断；前端已有 `formatFundingRate` 用 string-shift。实现可用字符串 Decimal helper 或保守转为整数基点比较。
- 建议实现 `absDailyRateAtOrBelowThreshold(rateStr)`：
  - 接收 decimal string。
  - 解析为符号、整数、小数；补齐到 8 位小数。
  - 比较 `abs(rate) <= 0.00030000`。
  - 无法解析 / null → false（不隐藏）。

测试：

- self-check fixture 增加一行 `daily_funding_rate="0.00030000"`，默认隐藏。
- 增加一行 `daily_funding_rate="-0.00030000"`，默认隐藏。
- 增加一行 `daily_funding_rate="0.00030001"` 或 `"-0.00030001"`，默认保留。
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
function formatBalanceAmount(value) { ... }     // 原始精度 + 千分位
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

隐私隐藏态：

- 数量行：`****`
- locked 行：`冻结: ****`
- 折算行：`≈ **** USDT`

保留现有 `formatUsdt2` 的 2 位 ROUND_HALF_UP 逻辑。

## 3. 贵金属资产标签

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
        return ("METAL", "base_asset_precious_metal_symbol", "HIGH")
    ...
```

`build_rows()` 调用改为传 `obj.get("baseAsset", "")`。

契约同步：

- `schemas/api/public-market/snapshot.schema.json` 的 `asset_tag` enum 增加 `METAL`。
- `docs/api/public-market-contract.md` 增加说明。
- `frontend/index.html`：
  - 资产标签筛选下拉增加 `METAL(贵金属)`。
  - `badgeForAssetTag` 增加 `METAL`，建议样式 `info` 或 `warn`，不复用 bStock danger/accent。
- `frontend/fixture/public-market-snapshot.json` 增加至少一行金属样本或修改现有 fixture 中一行以覆盖 UI；需要保证 summary counts 同步。

测试：

- backend normalize 测试：`asset_tag_for("PERPETUAL", "XAU") == ("METAL", ...)`。
- backend snapshot 测试：`XAUUSDT` / `COPPERUSDT` 行输出 `asset_tag=METAL`。
- schema 测试：含 METAL 行的 snapshot 通过 schema。
- frontend self-check：资产标签下拉与徽章显示 `METAL(贵金属)`。

## 4. 风险

- `COPPER` 可能与交易所实际 baseAsset 命名不同；初版只按用户列出的 baseAsset 精确匹配，不做模糊匹配。
- 如果贵金属应该像 bStock 一样禁用负费率借币，当前草稿未做，需要用户确认后扩展 `negative_funding_status` enum 与优先级。
- 低日费率隐藏默认开启会改变首屏行数；self-check 需要显式断言默认行数变化，避免误判。

本地北京时间: 2026-07-08 02:23:15 CST
下一步模型: human
下一步任务: 确认设计草稿；确认后生成实现 prompt 并进入开发。

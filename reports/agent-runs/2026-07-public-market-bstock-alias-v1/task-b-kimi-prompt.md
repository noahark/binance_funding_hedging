# Task B dispatch — Frontend bStock B-suffix alias display

你是 Kimi（minimal_change_engineer），在仓库 `/Users/ark/Desktop/ai code/funding_hedging` 中完成
阶段 `2026-07-public-market-bstock-alias-v1` 的 **Task B（前端显示）**。Task A（契约修订 + 后端）
已由 Claude-GLM 完成并冻结：`spot.match_type` 字段已加入 schema 与后端。

## 背景（一句话）

Binance 的 TRADIFI 期货 symbol（如 `TSLAUSDT`）与对应的 bStock 现货/保证金 symbol（如 `TSLABUSDT`，
带 `B` 后缀）不同。后端现在通过 `baseAsset + "B" + quoteAsset` 别名把它们 join 起来，并在每行的
`spot.match_type` 标注匹配方式。前端需要把"期货 symbol ≠ 实际现货 symbol"这件事显示清楚。

## 契约（已冻结，仅供参考，不要改）

`spot` 对象现在有一个可选字段 `match_type`（schema：`docs/api/public-market/snapshot.schema.json`
与 `schemas/api/public-market/snapshot.schema.json`）：

- `"exact_symbol"` —— 普通 crypto，期货 symbol == 现货 symbol（如 BTCUSDT→BTCUSDT）。
- `"bstock_b_suffix_alias"` —— TRADIFI/BSTOCK 经 B 后缀别名匹配（如 TSLAUSDT→TSLABUSDT）。
- `null` —— 无现货腿（`spot.exists === false`）。

行结构其它字段不变。`route_class` 取值仍是 `MARGIN_SPOT_CANDIDATE / SPOT_ONLY_CANDIDATE /
PERP_ONLY_EXCLUDED`；`asset_tag` 仍是 `CRYPTO / BSTOCK / UNKNOWN`。

## 写入边界（硬约束）

**只允许写：**
- `frontend/index.html`
- `frontend/self-check.js`
- `frontend/fixture/public-market-snapshot.json`
- `reports/agent-runs/2026-07-public-market-bstock-alias-v1/20-implementation-frontend.md`（你的实现报告）

**禁止碰：** `backend/**`、`schemas/**`、`docs/**`、`reports/api-samples/**`、`agents/**`、
`workflows/**`、`scripts/**`、以及任何其它阶段目录文件。可以**只读** `snapshot.schema.json` 和
`docs/api/public-market-contract.md` 作参考。

越界 = 返工，无论代码质量。

## 具体改动（按这个做，不要自由发挥设计）

### 1. `frontend/index.html` — 标的列显示实际现货腿

当前"标的"列（`renderTable` 里第一个 `<td>`）只显示 `row.symbol`（= 期货 symbol）和
`base_asset/quote_asset`。

改成：**仅当 `row.spot.match_type === "bstock_b_suffix_alias"` 且 `row.spot.symbol` 存在
且 `row.spot.symbol !== row.symbol` 时**，在该 `<td>` 内额外显示实际现货 symbol + 一个来源徽章，
例如：

```
TSLAUSDT
TSLA/USDT
现货腿: TSLABUSDT（B 后缀别名）
```

- 用现有 `.badge` / `.badge.compact` / `.muted.small` 等已有样式，**不要新增 CSS 变量或大改样式**。
- exact_symbol 匹配（BTC 等）**不要**额外显示现货腿（保持现状简洁）。
- 无现货腿（match_type=null）也不要显示现货腿行。
- 文案用中文，风格与现有页面一致（参考已有 badge 文案如 "PM 现货候选"）。

可选（不强制）：如果你认为清晰，可在"UI 标记"列对 alias 行追加一个 compact badge，例如
`现货别名`。如果加了，self-check 要相应断言；不加也行。**二选一，保持简洁**。

### 2. `frontend/fixture/public-market-snapshot.json` — 演示一个 alias 行

这个 fixture 是前端的**静态演示 + 自检数据**（不是 frozen 证据，frozen 证据在
`reports/api-samples/`，不要碰）。为了让前端能演示 alias 渲染，按以下精确改法修改：

**(a) 给每个 `spot` 块加 `match_type` 字段**（紧跟 `exists` 之后）：
- BTCUSDT、ETHUSDT、XVGUSDT：`"match_type": "exact_symbol"`
- XMRUSDT、MSTRUSDT：`"match_type": null`（exists=false）

**(b) 把 `TSLAUSDT` 行从"无 alias 的 PERP_ONLY"改成"经 alias 接通的 candidate"**，精确如下：
- `route_class`: `"PERP_ONLY_EXCLUDED"` → `"MARGIN_SPOT_CANDIDATE"`
- `positive_funding_enabled`: `false` → `true`
- `negative_funding_status`: `"DISABLED_PERP_ONLY"` → `"DISABLED_BSTOCK"`
  （BSTOCK 即使进了 candidate route，负费率仍因不可借币而禁用 —— 这是契约语义，保留 asset_tag=BSTOCK）
- `last_funding_rate`: `"0.00000000"` → `"0.00010000"`（正费率，演示候选路径）
- `spot` 块改成：
  ```json
  "spot": {
    "symbol": "TSLABUSDT",
    "status": "TRADING",
    "exists": true,
    "match_type": "bstock_b_suffix_alias",
    "min_notional": "5.00000000",
    "step_size": "0.00010000"
  }
  ```
- `ui_flags`: 去掉 `"PERP_ONLY_NO_SPOT_LEG"`，保留 `"MARGIN_PUBLIC_UNVERIFIED"` 和
  `"TRADIFI_BSTOCK"`。

**(c) `MSTRUSDT` 保持不变**（仍 PERP_ONLY、无 alias、match_type=null）—— 作为"无 alias 的 BSTOCK"
对照行。

**(d) 同步更新 `summary` 计数**以匹配改后的 6 行：
- `route_counts`: `MARGIN_SPOT_CANDIDATE` 现在 3（BTC/ETH/TSLA），`SPOT_ONLY_CANDIDATE` 1（XVG），
  `PERP_ONLY_EXCLUDED` 2（XMR/MSTR）。
- `asset_tag_counts`: `CRYPTO` 4，`BSTOCK` 2（不变）。
- `negative_funding_status_counts`: `PRIVATE_BORROW_VALIDATION_REQUIRED` 2（BTC/ETH），
  `DISABLED_SPOT_ONLY` 1（XVG），`DISABLED_BSTOCK` 1（TSLA），`DISABLED_PERP_ONLY` 2（XMR/MSTR）。
  （不再有 3 个 DISABLED_PERP_ONLY；TSLA 移到 DISABLED_BSTOCK。）

**(e) `warnings[2]`（第 3 条）文案同步**为后端新的 `CONTRACT_WARNINGS[2]`：
```text
TRADIFI_PERPETUAL (bStock) spot legs are joined via the baseAsset+B+quoteAsset alias (e.g. futures TSLAUSDT -> spot TSLABUSDT); bStock collateral ratio is dynamic/unknown and is not hard-coded; asset_tag is independent of route_class.
```
（warnings[0] 和 warnings[1] 不变。）

### 3. `frontend/self-check.js` — 更新断言

改 TSLA 变 candidate 后：
- **默认（隐藏 PERP_ONLY）渲染行数：3 → 4**（BTC/ETH/XVG/TSLA）。
- 显示 PERP_ONLY 后仍是 **6 行**。
- **BSTOCK 行数仍是 2**（TSLA + MSTR）。
- **新增断言**：渲染输出包含实际现货 symbol `TSLABUSDT` 和"B 后缀别名"标识文案（与你 index.html
  里用的文案一致）。
- 保留所有现有断言：默认请求 `/api/public-market/snapshot`、数据源标签、warnings 含
  `TRADIFI_PERPETUAL`、北京时间转换、列名"最近更新的资金费率"、不含"已结算/预测"、无交易按钮/开仓。

### 4. `reports/agent-runs/2026-07-public-market-bstock-alias-v1/20-implementation-frontend.md`

写一份简洁实现报告：交付文件清单、改动摘要（标的列 alias 显示、fixture 的 TSLA alias 行、
self-check 断言更新）、边界合规声明（只写 frontend/**）、`node frontend/self-check.js` 的原始输出。

## 验证（必须通过）

在仓库根目录运行：

```bash
node frontend/self-check.js
```

必须输出"全部自检通过"并 exit 0。

不要跑 backend 测试、不要跑 pytest、不要启动服务器。

## 风格 / 约束（沿用 impl-v1）

- 中文工作台风格不变；不新增交易/开仓/账户 UI。
- 同源默认：页面默认 `fetch('/api/public-market/snapshot')`，离线 fixture 按钮不变。
- 最小改动：不重构现有渲染逻辑，只加 alias 显示分支 + fixture 字段 + 断言。
- 完成后，在你的实现报告里贴 `node frontend/self-check.js` 的原始输出作为证据。

开始。完成后只输出一句确认 + self-check 的原始输出尾部。

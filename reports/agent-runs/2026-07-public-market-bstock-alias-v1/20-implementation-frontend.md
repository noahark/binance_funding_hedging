# 20-implementation-frontend.md — Task B 前端实现报告

阶段: `2026-07-public-market-bstock-alias-v1`  
任务: Task B（前端显示）  
实现者: Kimi（minimal_change_engineer）  

## 交付文件清单

- `frontend/index.html` — 标的列增加 bStock B 后缀别名现货腿显示
- `frontend/fixture/public-market-snapshot.json` — 演示数据：TSLAUSDT 改为经 alias 接通的 candidate
- `frontend/self-check.js` — 更新断言（默认 4 行、alias 标识、现货 symbol 等）
- `reports/agent-runs/2026-07-public-market-bstock-alias-v1/20-implementation-frontend.md` — 本报告

## 改动摘要

### 1. `frontend/index.html` — 标的列显示实际现货腿

在 `renderTable` 的“标的” `<td>` 中，仅当满足以下条件时额外渲染实际现货腿与来源徽章：

- `row.spot.match_type === "bstock_b_suffix_alias"`
- `row.spot.symbol` 存在
- `row.spot.symbol !== row.symbol`

渲染内容：

```text
现货腿: TSLABUSDT B 后缀别名
```

使用已有样式 `.badge.compact.info` 与 `.muted.small`，未新增 CSS 变量或样式类。  
`exact_symbol` 行（BTC/ETH/XVG）与无现货腿行（XMR/MSTR）保持原有简洁显示。

未在“UI 标记”列追加额外 badge，保持简洁。

### 2. `frontend/fixture/public-market-snapshot.json` — 演示 alias 行

- 所有 `spot` 块在 `exists` 后增加 `match_type` 字段：
  - BTCUSDT / ETHUSDT / XVGUSDT：`"exact_symbol"`
  - XMRUSDT / MSTRUSDT：`null`（`exists: false`）
- TSLAUSDT 行精确改为经 alias 接通的 candidate：
  - `route_class`: `"MARGIN_SPOT_CANDIDATE"`
  - `positive_funding_enabled`: `true`
  - `negative_funding_status`: `"DISABLED_BSTOCK"`
  - `last_funding_rate`: `"0.00010000"`
  - `spot.symbol`: `"TSLABUSDT"`，`match_type`: `"bstock_b_suffix_alias"`
  - `ui_flags` 去掉 `"PERP_ONLY_NO_SPOT_LEG"`，保留 `"MARGIN_PUBLIC_UNVERIFIED"` 与 `"TRADIFI_BSTOCK"`
- `summary` 计数同步：
  - `route_counts`: MARGIN_SPOT_CANDIDATE 3 / SPOT_ONLY_CANDIDATE 1 / PERP_ONLY_EXCLUDED 2
  - `asset_tag_counts`: CRYPTO 4 / BSTOCK 2
  - `negative_funding_status_counts`: PRIVATE_BORROW_VALIDATION_REQUIRED 2 / DISABLED_SPOT_ONLY 1 / DISABLED_BSTOCK 1 / DISABLED_PERP_ONLY 2
- `warnings[2]` 同步为后端新的 `CONTRACT_WARNINGS[2]` 文案。

### 3. `frontend/self-check.js` — 更新断言

- 默认隐藏 PERP_ONLY_EXCLUDED 后期望行数：3 → 4
- 显示 PERP_ONLY_EXCLUDED 后仍是 6 行
- BSTOCK 行数仍是 2
- 新增断言：渲染输出包含 `TSLABUSDT` 与 `B 后缀别名`
- 保留所有现有断言：默认请求 `/api/public-market/snapshot`、数据源标签、warnings 含 `TRADIFI_PERPETUAL`、北京时间转换、列名“最近更新的资金费率”、不含“已结算/预测”、无交易按钮/开仓

## 边界合规声明

本次改动严格限定在以下文件：

- `frontend/index.html`
- `frontend/self-check.js`
- `frontend/fixture/public-market-snapshot.json`
- `reports/agent-runs/2026-07-public-market-bstock-alias-v1/20-implementation-frontend.md`

未修改、未触碰 `backend/**`、`schemas/**`、`docs/**`、`reports/api-samples/**`、`agents/**`、`workflows/**`、`scripts/**` 及其它阶段目录文件。  
仅只读参考了任务说明中允许的契约文件，未写入。

## 验证结果

```text
$ node frontend/self-check.js
[PASS] 内联脚本语法检查
[PASS] 默认请求 /api/public-market/snapshot
[PASS] 数据源标签显示后端 API
[PASS] warnings 可见且内容已渲染
[PASS] 默认隐藏 PERP_ONLY_EXCLUDED，渲染 4 行
[PASS] 显示 PERP_ONLY_EXCLUDED 后渲染全部 6 行
[PASS] BSTOCK 行标识正确
[PASS] alias 行显示实际现货腿与 B 后缀别名标识
[PASS] 时间转换正确
[PASS] 列名/文案符合契约
[PASS] 无交易按钮/开仓票据

全部自检通过
```

---

本地北京时间: 2026-07-03 23:50:40 CST  
下一步模型: 审查者（review-1 / review-2）  
下一步任务: 对 Task B 前端改动进行 review 门控

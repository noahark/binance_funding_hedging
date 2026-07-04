# 前端实现报告 — Task B rework round 1

阶段：`2026-07-public-market-ui-cn-v1`  
任务：Task B — 前端中文工作台 rework round 1  
实现者：Kimi (kimi-2.7)  
基线 commit：`0fd0d17`（上轮 review-1/review-2 双 ACCEPT）  
本轮改动范围：仅 `frontend/**` + 本报告

## 改动清单

### 1. 路由分类 / 资产标签 / 负费率状态三列及筛选下拉改为「英文枚举(中文解释)」格式

文件：`frontend/index.html`

- 市场表渲染函数 `badgeForRouteClass`、`badgeForAssetTag`、`badgeForNegativeFundingStatus` 改为查表返回 `ENGLISH(中文)` 文案，保持原有 badge 颜色语义。
- 筛选下拉 `<option>` 文本同步更新，`value` 保持原枚举不变。
- 提示标记列维持原样（无现货腿 / bStock，原始枚举在 `title`），符合任务书约束。

映射表（与 fix-start-prompt-ui-round1.md 一致）：

| 枚举 | 展示文案 |
|---|---|
| MARGIN_SPOT_CANDIDATE | `MARGIN_SPOT_CANDIDATE(杠杆现货候选)` |
| SPOT_ONLY_CANDIDATE | `SPOT_ONLY_CANDIDATE(仅现货候选)` |
| PERP_ONLY_EXCLUDED | `PERP_ONLY_EXCLUDED(仅合约，排除)` |
| CRYPTO | `CRYPTO(加密货币)` |
| BSTOCK | `BSTOCK(美股代币)` |
| UNKNOWN | `UNKNOWN(未知)` |
| PRIVATE_BORROW_VALIDATION_REQUIRED | `PRIVATE_BORROW_VALIDATION_REQUIRED(需私有借币验证)` |
| DISABLED_BSTOCK | `DISABLED_BSTOCK(禁用:bStock 不可借)` |
| DISABLED_SPOT_ONLY | `DISABLED_SPOT_ONLY(禁用:无杠杆)` |
| DISABLED_PERP_ONLY | `DISABLED_PERP_ONLY(禁用:无现货腿)` |

### 2. 删除「加载离线 fixture」按钮及代码路径

- 移除 `#btn-offline` 按钮、`loadFixture` 函数、`'fixture'` 数据源分支、相关错误提示文案。
- `frontend/fixture/public-market-snapshot.json` 与 `self-check.js` 对该 fixture 文件的读取用途保留不变。

### 3. 60 秒自动刷新 + 倒计时

- 新增常量 `AUTO_REFRESH_MS = 60000`，注释注明与后端 `Config.cache_ttl_seconds=60` 对齐。
- 市场表 panel-header 附近新增 `#refresh-countdown` 元素，显示「下次刷新: Xs」。
- `loadApi` 进入请求时显示「刷新中…」，成功或失败后重置倒计时为 60s。
- 手动刷新按钮保留，点击立即 `loadApi()` 并重置倒计时。
- 页头 badge「手动刷新」改为「自动刷新 60s」。
- footer 文案改为「数据每 60 秒自动刷新（后端缓存 TTL 60 秒）」。

### 4. 侧栏品牌中文化

- 侧栏品牌标识由 `Funding Hedge` 改为 `资金费率对冲`。

### 5. self-check.js 断言同步

- 移除 `btn-offline` mock，新增 `#refresh-countdown` mock。
- 新增断言：
  - `index.html` 不再包含 `btn-offline` 与「加载离线 fixture」。
  - `index.html` 包含 `60000`、`下次刷新`、`Config.cache_ttl_seconds=60`。
  - 渲染后的市场表包含全部 9 条「英文枚举(中文解释)」文案。
  - 筛选下拉 option 包含 6 条对应文案。
  - 侧栏品牌包含「资金费率对冲」。
- 保留既有 13 条断言全部不变（6 行渲染、warnings 可见、BSTOCK 标识、时间转换、默认请求 `/api/public-market/snapshot`、formatter 7 样例等）。

## 红线遵守情况

- `formatFundingRate`、`formatBeijing`、`formatBeijingShort` 未改动。
- 无新依赖。
- 无直接 Binance 调用；页面仅请求 `/api/public-market/snapshot`。
- 未修改 `backend/**`、`schemas/**`、`docs/**`、`reports/api-samples/**`、`agents/**`、`workflows/**`、`scripts/**`。

## 自检结果

```bash
$ node frontend/self-check.js
[PASS] 内联脚本语法检查
[PASS] 默认请求 /api/public-market/snapshot
[PASS] 数据源标签显示后端 API
[PASS] 数据说明区可见且内容已渲染
[PASS] 默认隐藏 PERP_ONLY_EXCLUDED，渲染 4 行
[PASS] 显示 PERP_ONLY_EXCLUDED 后渲染全部 6 行
[PASS] BSTOCK 行标识正确
[PASS] alias 行显示实际现货腿与 B 后缀别名标识
[PASS] 时间转换正确
[PASS] 列名/文案符合契约
[PASS] 无交易按钮/开仓票据
[PASS] 资金费率格式化 7 个样例
[PASS] 数据说明条目数与 API warnings 一致
[PASS] 提示标记映射正确
[PASS] 离线 fixture 按钮及文案已删除
[PASS] 自动刷新 60s 与倒计时元素存在
[PASS] 路由/资产/负费率状态列显示「英文枚举(中文解释)」格式
[PASS] 筛选下拉 option 使用「英文枚举(中文解释)」格式
[PASS] 侧栏品牌已中文化

全部自检通过
```

## 改动文件

- `frontend/index.html`
- `frontend/self-check.js`
- `reports/agent-runs/2026-07-public-market-ui-cn-v1/20-implementation-frontend-rework1.md`（本报告）

## 备注

- 本轮未提交；等待 controller 统一提交 `H_fix` 并重算 fingerprint。
- 上轮的 review-1/review-2 ACCEPT verdict（head `9b0e62c`）原样保留，本轮 fix diff 将重新进入 review-1（fresh Claude-GLM）与 review-2（Codex gpt-5.5）。

本地北京时间: 2026-07-04 16:15:04 CST  
下一步模型: Claude-GLM（controller）  
下一步任务: 提交 H_fix、重算 task-B 与 stage fingerprint、调度 review-1/review-2

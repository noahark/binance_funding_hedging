# Fix Start Prompt — rework round 1（P3 残留 + 用户指示的 UI 调整）

（controller 原样转发给 Kimi;所有改动均在 frontend/**,Task B owner 不变。
阶段 `2026-07-public-market-ui-cn-v1`,rework_count=1/3,status=fixing。）

## 被复审的 diff 与本轮起点

- 上轮 stage head:`9b0e62c`(fingerprint `9b0e62c:6e6e2d4d...`,review-1/
  review-2 双 ACCEPT,verdict 原样保留)
- 本轮触发:用户外部复核(Fable5)发现 P3 残留 + 用户 2026-07-04 新增 UI 决策
  (记录于 status.json 的 post_review_findings / user_decisions)

## Findings(P3,非功能)

1. `badgeForAssetTag` 把 `CRYPTO`/`UNKNOWN`/`BSTOCK` 枚举原值直出主表
   「资产标签」列(index.html ~650)。
2. 侧栏品牌标识「Funding Hedge」仍为英文(index.html:398)。

## 用户决策(2026-07-04,本轮必须实现)

**A. 状态枚举展示新口径(取代上一轮"主表纯中文"规则):路由分类、资产标签、
负费率状态三列及对应筛选下拉,统一为「英文枚举(中文解释)」格式(全角括号)。**

| 字段 | 展示文案 |
|---|---|
| MARGIN_SPOT_CANDIDATE | `MARGIN_SPOT_CANDIDATE(杠杆现货候选)` |
| SPOT_ONLY_CANDIDATE | `SPOT_ONLY_CANDIDATE(仅现货候选)` |
| PERP_ONLY_EXCLUDED | `PERP_ONLY_EXCLUDED(仅合约,排除)` |
| CRYPTO | `CRYPTO(加密货币)` |
| BSTOCK | `BSTOCK(美股代币)` |
| UNKNOWN | `UNKNOWN(未知)` |
| PRIVATE_BORROW_VALIDATION_REQUIRED | `PRIVATE_BORROW_VALIDATION_REQUIRED(需私有借币验证)` |
| DISABLED_BSTOCK | `DISABLED_BSTOCK(禁用:bStock 不可借)` |
| DISABLED_SPOT_ONLY | `DISABLED_SPOT_ONLY(禁用:无杠杆)` |
| DISABLED_PERP_ONLY | `DISABLED_PERP_ONLY(禁用:无现货腿)` |

- 筛选下拉 `<option>` 文本用同格式;`value` 保持原枚举不变。
- badge 变长:用现有 compact 样式或允许换行,最小成本处理,不重做样式系统。
- 「提示标记」列维持现状(无现货腿 / bStock,原始枚举在 title)——用户未点名。

**B. 删除「加载离线 fixture」按钮及其代码路径。**

- 删 `#btn-offline` 按钮、loadFixture 函数、'fixture' 数据源分支、
  「如需离线自检,可点击...」提示文案。
- `frontend/fixture/public-market-snapshot.json` 与 `self-check.js` 的
  数据源用途**保留不动**(self-check 直接读该文件,与页面按钮无关)。

**C. 自动刷新 + 倒计时。**

- 页面每 **60 秒**自动重新 fetch `/api/public-market/snapshot`
  (与后端缓存 TTL 对齐:`backend/config.py Config.cache_ttl_seconds=60`;
  前端注释注明此来源)。
- 市场表 panel-header 附近显示倒计时:「下次刷新: Xs」,每秒递减;
  请求进行中显示「刷新中…」;失败后倒计时照常重启(沿用现有错误提示)。
- 「手动刷新」按钮保留:点击立即 fetch 并将倒计时重置为 60。
- 页头 badge「手动刷新」→「自动刷新 60s」;footer
  「数据非实时,手动刷新后更新」→「数据每 60 秒自动刷新(后端缓存 TTL 60 秒)」。
- 实现用 setInterval 即可,不要求 visibility 暂停等额外机制。

**D. 侧栏「Funding Hedge」→「资金费率对冲」。**

## 边界

允许写:`frontend/**`、
`reports/agent-runs/2026-07-public-market-ui-cn-v1/20-implementation-frontend-rework1.md`。
禁止:`backend/**`、`schemas/**`、`docs/**`、`reports/api-samples/**`、
`agents/**`、`workflows/**`、`scripts/**`;无新依赖;无直接 Binance 调用;
**`formatFundingRate` / `formatBeijing*` 函数不得改动**(上轮已评审通过)。

## self-check 同步

- badge 文案断言更新为新「英文(中文)」格式(三列全部枚举值)。
- 新增断言:`index.html` 不再包含 `btn-offline` 与「加载离线 fixture」。
- 新增断言:`index.html` 包含「下次刷新」与 60000(轮询间隔常量)。
- 既有断言(费率格式化 7 样例、数据说明条目数等)全部保持通过。

## 完成后必跑

```bash
node frontend/self-check.js   # 全 PASS
```

报告 `20-implementation-frontend-rework1.md`:改动清单 + self-check 输出原文。

## 收尾(controller)

H_fix 提交 → 重算 task-B 级与 stage 级 fingerprint → review-1(全新只读
Claude-GLM 会话)对 fix diff 复审 → review-2(Codex gpt-5.5,
direction_synthesis disclosure,Anthropic 因设计参与排除)重跑并绑定新 head →
`fixing → review_1 → review_2 → stage_accepted_waiting_user`;不声明最终验收。
每个 gate 跑 `scripts/validate-stage.py --phase` 对应值。

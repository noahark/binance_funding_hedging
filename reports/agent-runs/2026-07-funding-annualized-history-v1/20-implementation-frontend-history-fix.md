# Task D Implementation Report: Drawer History Loading And Table Refinement

## Stage

`2026-07-funding-annualized-history-v1`

## Task

Task D: Drawer history loading and table refinement.

## Owner

Kimi (`kimi-code/kimi-for-coding`)

## Summary

Implemented the review-feedback refinement for the right-side history drawer:

1. Removed the default `route_class` table column while keeping the route filter,
   route field in client validation, and the visible `negative_funding_status`
   column.
2. Widened the Drawer to `min(620px, 100vw)` and adjusted the annualized card
   grid so the three labels stay on one line.
3. Added on-demand history loading: rows with preloaded `funding_history` render
   immediately; rows without trigger a same-origin
   `/api/public-market/funding-history?symbol=<symbol>` request, show an
   accessible loading state, merge a valid 200 response into the selected row
   and table, and distinguish `history_status: empty` from upstream failure.
4. Added HTTP 502 handling with a retryable failure state and retry control,
   without ever calling Binance from the browser.
5. Added stale-response isolation so a response arriving after the user selects
   a different symbol or closes the drawer is ignored.

## Changed Files

- `frontend/index.html`
  - Removed `<th>路由分类</th>` and the corresponding `<td>` in row render.
  - Updated blocked/empty table `colspan` from `13` to `12`.
  - Reduced table `min-width` from `1080px` to `980px` to match the new 12-column
    layout.
  - Drawer width changed to `min(620px, 100vw)`.
  - Annualized grid changed to `repeat(3, minmax(0, 1fr))`.
  - Added `white-space: nowrap` to annualized card labels.
  - Added `state.drawerLoading` and `state.drawerHistoryError`.
  - Added `drawerRequestId` and `fetchHistory(symbol)` for same-origin endpoint
    calls with stale-response guarding.
  - Updated `openDrawer` to render immediately for preloaded histories and to
    fetch/loading-render for missing histories.
  - Updated `renderDrawer` to show loading, empty, available, and retryable
    failure states.
  - Bound retry button click inside `renderDrawer` to re-fetch the selected
    symbol's history.
  - Updated `closeDrawer` to reset loading/error state.
  - Exposed `getDrawerLoading`, `getDrawerHistoryError`, and `fetchHistory` on
    `__appHelpers` for testability.

- `frontend/self-check.js`
  - Added mock support for the funding-history endpoint (`historyResponse`,
    `historyResolve`, `lastHistoryUrl`, delayed-response mode).
  - Added element cache so `querySelector('#id')` on dynamically rendered
    content returns the same mock element used for event-binding.
  - Updated all table column indexes from 13-column to 12-column layout.
  - Updated the graceful-degradation cell-index assertions for the new layout.
  - Added assertions for: removed route column, retained route filter and
    `route_class` contract validation, 12-column header count, Drawer width and
    card-label constraints.
  - Added assertions for: same-origin selected-symbol request URL,
    loading state, available history merge into row and table,
    `history_status: empty` distinct message, HTTP 502 retryable failure state,
    retry button re-fetch, and stale-response isolation.

- `frontend/fixture/public-market-snapshot.json`
  - No change required; the existing fixture already carries the three
    `annualized_funding_*` fields and sample history for BTCUSDT.

## Test Evidence

```text
$ node frontend/self-check.js
[PASS] 内联脚本语法检查
[PASS] 默认请求 /api/public-market/snapshot
[PASS] 数据源标签显示后端 API
[PASS] 数据说明区可见且内容已渲染
[PASS] 默认渲染 6 行
[PASS] 拆列存在，合并列消失
[PASS] 年化三列存在且文案区分预估/已结算
[PASS] 路由分类列移除，过滤器与字段校验保留
[PASS] Drawer 宽度与卡片标签约束
[PASS] 日费率 string-shift 格式化（含 null→—）
[PASS] 年化三列格式化（含 null→—）
[PASS] 结算间隔标注 8h
[PASS] 无排序控件 DOM
[PASS] 渲染顺序等于 payload 顺序
[PASS] 时间转换正确
[PASS] 列名/文案无误导性 settlement/prediction 文案
[PASS] 无交易按钮/开仓票据
[PASS] 资金费率格式化 7 个样例
[PASS] formatFundingRate / formatBeijing* 函数体未变
[PASS] formatUsdt2 2 位 ROUND_HALF_UP
[PASS] 自动刷新 60s 与倒计时元素存在
[PASS] 资产/负费率状态列中文格式与路由列移除检查
[PASS] 侧栏品牌已中文化
[PASS] 手动刷新后 60s 自动刷新计时器重调度，倒计时计时器保持独立
[PASS] 净收益列存在与格式
[PASS] 负值净收益红色样式
[PASS] vip0_reference 显著标注「基准利率」
[PASS] sort_basis 标注
[PASS] 私有面板 verified=true 状态
[PASS] 时点合一与估值来源卡片删除
[PASS] 页面不含矛盾运行约束文案
[PASS] 隐私开关默认隐藏
[PASS] 隐私开关点击切换
[PASS] 私有面板 verified=false disabled 占位
[PASS] 私有面板 verified=false error 占位
[PASS] 行联动方向标（不带数量）
[PASS] 优雅降级：新字段缺失不白屏，日费率/净收益 —，间隔不显示
[PASS] private-panel 在市场表之前
[PASS] drawer DOM 在应用脚本之前
[PASS] 成本腿命中行展示借币日利率
[PASS] VIP0 参考档显示"参考"徽标
[PASS] 正费率行不展示借币成本子行
[PASS] 负费率状态行感知的六文案派生
[PASS] 余额卡片三行折算值与隐私遮蔽
[PASS] value_usdt null 显示占位
[PASS] value_usdt 合法零显示占位
[PASS] 余额数量整数千分位、小数原样保留
[PASS] absDailyRateAtOrBelowThreshold 阈值边界（BigInt）
[PASS] 低日费率过滤 UI 行为（边界隐藏/超界保留/null 不过滤）
[PASS] METAL 资产标签徽章与下拉选项
[PASS] 借币三态（51061 借光/有额度/未探测）
[PASS] 抽屉打开、标题、年化值、历史 newest-first
[PASS] 抽屉关闭按钮
[PASS] 抽屉 Escape 关闭
[PASS] 抽屉 backdrop 关闭
[PASS] 刷新保持抽屉
[PASS] symbol 消失时抽屉关闭
[PASS] drawer loading 与 same-origin 请求
[PASS] available 响应合并到行与表
[PASS] empty 响应显示无记录
[PASS] HTTP 502 显示可重试失败状态
[PASS] 重试按钮重新 fetch 并更新抽屉
[PASS] stale 响应隔离

全部自检通过
```

```text
$ git diff --check
DIFF-CHECK PASS
```

## Drawer response-race fix

Additional changes to close the response-body race and harden symbol/schema
validation.

### Changed files

- `frontend/index.html`
  - Added `isActive()` guard after `await res.json()` in `fetchHistory(symbol)`.
  - Added strict response contract validation (`schema_version`, `symbol`,
    `history_status`, `funding_history` array, settled annualization keys)
    before merging history into the snapshot row or rendering the drawer.
- `frontend/self-check.js`
  - Added `jsonDelay` mock mode so a fetch can resolve while `res.json()`
    remains pending.
  - Added response-body race test: stale BUSDT body resolved after switching
    to AUSDT must not merge.
  - Added wrong-symbol and `schema_version` mismatch rejection tests.

### Test evidence

```text
$ node frontend/self-check.js
...
[PASS] response-body race 隔离（res.json() 延迟后切换）
[PASS] wrong-symbol/schema 响应被拒绝合并
[PASS] schema_version mismatch 响应被拒绝

全部自检通过
```

```text
$ git diff --check
DIFF-CHECK PASS
```

### Notes

- No backend, schema, canonical doc, stage status, or handoff files were
  modified.
- No commit was made.

## Blockers

None.

```text
本地北京时间: 2026-07-10 22:48:39 CST
下一步模型: bookkeeper / human
下一步任务: 验证文件边界，提交 Task D，更新 status.json 与 70-handoff.md，然后跑 validate-stage.py --phase pre-review
```

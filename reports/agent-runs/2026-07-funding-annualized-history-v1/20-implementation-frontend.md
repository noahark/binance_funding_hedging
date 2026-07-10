# Task B Implementation Report — Table Columns And History Drawer

Stage: `2026-07-funding-annualized-history-v1`
Branch: `stage/2026-07-funding-annualized-history-v1`
Executor: Kimi (`kimi-code/kimi-for-coding`)

## Summary

Task B consumes the committed Task A wire contract (`annualized_funding_24h`,
`annualized_funding_7d`, `annualized_funding_30d` as decimal-string-or-null) and
adds:

- Three annualized funding columns immediately after the daily-rate column.
- Row selection (click / Enter / Space) opening a right-side drawer.
- Drawer header with symbol, identical formatted annualized values, and
  newest-first settled-history rows in `Asia/Shanghai`.
- Drawer close via close control, backdrop click, or Escape.
- Refresh preserves the drawer only while the selected symbol remains; closes
  it when the symbol disappears.
- Frontend fixture and self-check updates covering the new fields and
  interactions.

All Task B changes stay inside the allowed file boundary in `00-task.md`.

## Changed Files

- `frontend/index.html`
  - Added drawer DOM (`#drawer`, `#drawer-backdrop`) and CSS (slide-in
    transition, backdrop, responsive width, history list styling).
  - Added `annualized_funding_24h/7d/30d` to `REQUIRED_ROW_FIELDS` (current
    service guarantee).
  - Added three table columns after daily-rate: `年化 24h`, `年化 7D`,
    `年化 30D`. Reused `formatFundingRate` / `classForFundingRate` for
    formatting and sign colors; null renders as `—`.
    - `年化 24h` tooltip: estimate-derived (`daily_funding_rate * 365`).
    - `年化 7D` / `年化 30D` tooltips: settled-history annualization.
  - Made table rows selectable (`selectable`, `tabindex="0"`, `role="button"`)
    with click and Enter/Space handlers.
  - Implemented `openDrawer`, `closeDrawer`, `renderDrawer`,
    `highlightSelectedRow`, `bindRowSelection`.
  - Drawer renders the selected symbol, three annualized cards, and
    newest-first history (sorted by `funding_time` DESC; formatted via
    `formatBeijing`).
  - `ingestSnapshot` and `applyFiltersAndRender` keep the drawer open only if
    the selected symbol still exists after refresh/filter change.
  - Bound Escape, backdrop click, and close-button click to `closeDrawer`.
  - Exposed `openDrawer`, `closeDrawer`, `isDrawerOpen`, `getSelectedSymbol`
    via `globalThis.__appHelpers` for tests.

- `frontend/fixture/public-market-snapshot.json`
  - Added `annualized_funding_24h`, `annualized_funding_7d`,
    `annualized_funding_30d` to every row.
  - BTCUSDT row now carries computed 24h/7D/30D values based on its existing
    `funding_history`; remaining rows carry 24h estimate and null 7D/30D.

- `frontend/self-check.js`
  - Added mock elements for the drawer (`drawer`, `drawer-backdrop`,
    `drawer-title`, `drawer-body`, `drawer-close`).
  - Added `classList`, `querySelector`, `querySelectorAll`, `document.body`,
    `document.addEventListener`, and `CSS.escape` mocks required by the new
    code.
  - Backfilled `annualized_funding_*` onto the design fixture rows and added a
    small settled-history vector to AUSDT for drawer tests.
  - Adjusted all existing cell-index assertions from the old 10-column layout
    to the new 13-column layout (daily-rate stays at index 5; net-yield moves
    from 6 to 9; negative-funding status moves from 8 to 11).
  - Added assertions:
    - Annualized column headers exist and distinguish estimate vs. settled.
    - AUSDT 24h/7D/30D formatting; null 7D/30D renders as `—`.
    - Drawer DOM follows the market table in document order.
    - Drawer opens, shows symbol, values, and newest-first history in
      `Asia/Shanghai`.
    - Close button, Escape, and backdrop close the drawer.
    - Refresh keeps drawer open when symbol persists; closes it when symbol
      disappears.

## Test Output Summary

```text
$ node frontend/self-check.js
[PASS] 内联脚本语法检查
[PASS] 默认请求 /api/public-market/snapshot
[PASS] 数据源标签显示后端 API
[PASS] 数据说明区可见且内容已渲染
[PASS] 默认渲染 6 行
[PASS] 拆列存在，合并列消失
[PASS] 年化三列存在且文案区分预估/已结算
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
[PASS] 路由/资产/负费率状态列显示中文优先格式
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
全部自检通过

$ python3 -m pytest backend/tests -q
226 passed in 5.39s

$ git diff --check
PASS
```

## Blockers / Deviations

- No blockers. All required checks pass.
- The design fixture (`backend/tests/fixtures/private-account-v1-design.json`)
  does not carry the new annualized fields because it predates this stage; the
  self-check backfills them so the current-service validation can be exercised.
  The production `frontend/fixture/public-market-snapshot.json` already emits
  the three fields for every row.

```text
本地北京时间: 2026-07-10 19:23:29 CST
下一步模型: bookkeeper
下一步任务: 提交 Task B 于 stage 分支，统一锚定阶段范围并跑 validate-stage.py --phase pre-review
```

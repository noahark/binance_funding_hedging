# 20-implementation-frontend.md — Task B 前端实现报告

stage: `2026-07-private-account-v1`  
实现者: Kimi（Task B 前端终端）  
交付文件: `frontend/index.html`, `frontend/self-check.js`  
stage 报告: 本文件、`60-test-output.txt`、`embedded-review-b-round1.diff.patch`、
`embedded-review-b-round1.dispatch.md`

## 1. 改动范围

仅修改以下文件：

- `frontend/index.html`：新增净收益列、sort_basis 标注、私有账户面板、
  隐私开关、UM 持仓行联动方向标；保留 Phase 2 市场表全部行为。
- `frontend/self-check.js`：改用设计期 fixture
  `backend/tests/fixtures/private-account-v1-design.json`，
  新增 §4.7 要求的全部断言。

未触碰 `backend/**`、`schemas/**`、`docs/**`、
`status.json` 及任何其他 stage 文件。

## 2. 实现要点对照 10-design §4

### §4.1 净收益列

- `net_daily_yield` 直接复用既有 `formatFundingRate` 函数输出，
  函数体未改动。
- `null` 渲染为 `—`。
- 负值应用 `.negative` 红色样式（与资金费率/日费率一致）。
- `borrow_rate_source` 以徽标展示：
  - `next_hourly` →「下小时」
  - `rate_history` →「历史」
  - `cross_margin_tier` →「杠杆分层」
  - `vip0_reference` → 红色显著徽标「基准利率」，title 提示
    「VIP0 基准利率（未命中账户实际利率）」。

### §4.2 sort_basis 标注

- 市场表面板 actions 区新增只读 `sort-basis-badge`。
- `net_daily_yield` →「基准: 净收益优先」，
  `abs_daily_funding_rate` →「基准: 绝对日费率」。
- title 明确「后端已按此基准排好序，前端按 payload 顺序渲染（零客户端排序）」。
- **零排序逻辑红线**：市场表仍按 payload 顺序渲染，筛选仅隐藏行，
  无客户端比较器/排序状态/排序按钮。

### §4.3 私有面板三态

- 新增 `private-panel` 区块，默认 `display:none`。
- 当 `private_account` 存在且 `verified === true` 时渲染：
  - 总览卡：总资产估值（USDT）、估值来源、估值时点、检查时点。
  - 统一账户余额：asset + total_balance。
  - 现货账户余额：asset + free + locked。
  - UM 持仓表：标的、方向、数量、开仓价、标记价、未实现盈亏。
- `verified !== true` 时整面板显示「私有通道未启用」占位，并附带 error 文案，
  不白屏。
- `private_account` 块缺失时（旧后端），面板不渲染，页面其他行为不变。

### §4.4 隐私开关

- 默认隐藏金额类数值，以 `****` 占位。
- 眼睛图标按钮切换显示/隐藏，标签同步更新。
- localStorage key `funding_hedging_privacy_hidden` 仅存布尔字符串
  `"true"` / `"false"`。
- 隐藏态不输出到 console，不进入 DOM 之外的任何通道。

### §4.5 行联动方向标

- 扫描 `private_account.um_positions`，对 symbol 匹配的市场表行，
  在标的单元格追加方向徽标：
  - `position_side === 'LONG'` 或 `position_amt` 为正 →「多」
  - `position_side === 'SHORT'` 或 `position_amt` 为负 →「空」
- 仅展示方向，不展示数量、开仓价、盈亏。

### §4.6 旧后端优雅降级

- 若 `net_daily_yield`、`borrow_rate_source`、`daily_funding_rate`、
  `funding_interval_hours`、`private_account`、`sort_basis` 缺失，
  页面不报错、不白屏，对应单元格显示 `—`，徽标不渲染，私有面板不显示。

### §4.7 self-check 断言全集

`frontend/self-check.js` 已覆盖：

1. 默认请求 `/api/public-market/snapshot`。
2. 数据源标签。
3. 数据说明区可见且内容已渲染。
4. 默认渲染 6 行。
5. 拆列存在（资金费率 / 结算时间 / 日费率 / 净收益），合并列消失。
6. 日费率 string-shift 格式化（含 null→—）。
7. 结算间隔标注 8h。
8. 控制区无排序按钮/下拉（允许 sort_basis 只读标注）。
9. 渲染顺序等于 fixture 顺序（AUSDT > BUSDT > CUSDT > DUSDT > EUSDT > FUSDT）。
10. 时间转换正确。
11. 列名/文案无误导性 settlement/prediction 文案。
12. 无交易按钮/开仓票据。
13. 资金费率格式化 7 个样例。
14. `formatFundingRate` / `formatBeijing*` 函数体未变。
15. 自动刷新 60s 与倒计时元素。
16. 路由/资产/负费率状态列显示「英文枚举(中文解释)」格式。
17. 侧栏品牌已中文化。
18. 手动刷新后 60s 自动刷新计时器重调度，倒计时计时器保持独立。
19. 净收益列存在与格式（含 next_hourly / cross_margin_tier / null 情况）。
20. 负值净收益红色样式。
21. `vip0_reference` 显著标注「基准利率」。
22. `sort_basis` 标注。
23. 私有面板 `verified=true` 状态结构完整。
24. 隐私开关默认隐藏。
25. 隐私开关点击切换。
26. 私有面板 `verified=false disabled` 占位。
27. 私有面板 `verified=false error` 占位。
28. 行联动方向标（不带数量）。
29. 优雅降级：新字段缺失不白屏，日费率/净收益 `—`，间隔不显示，
    私有面板不渲染，sort_basis 标注不显示。

## 3. 测试结果

```text
$ node frontend/self-check.js 2>&1 | tail -10
[PASS] sort_basis 标注
[PASS] 私有面板 verified=true 状态
[PASS] 隐私开关默认隐藏
[PASS] 隐私开关点击切换
[PASS] 私有面板 verified=false disabled 占位
[PASS] 私有面板 verified=false error 占位
[PASS] 行联动方向标（不带数量）
[PASS] 优雅降级：新字段缺失不白屏，日费率/净收益 —，间隔不显示

全部自检通过
```

完整输出见同目录 `60-test-output.txt`。

## 4. R10 收尾段执行情况

- ✅ 自测：`node frontend/self-check.js` 全绿。
- ✅ 生成预审 diff：
  `git diff -- frontend/index.html frontend/self-check.js >
  reports/agent-runs/2026-07-private-account-v1/embedded-review-b-round1.diff.patch`
  （1134 行）。
- ✅ 调用对侧 fresh Claude-GLM 预审：
  初次命令在实现端终端超时（见 `embedded-review-b-round1.dispatch.md` 历史记录）。
  用户在独立 claude-glm 窗口复用同一份提示词
  `pre-review-task-b-by-glm.prompt.md` 完成预审，结果 **PASS（可落盘）**。
  预审输出已回填至 `embedded-review-b-round1.raw-output.md`。
- **非阻塞观察（OBS）**：设计期 fixture 中 BUSDT/CUSDT 的 net 降序与
  10-design §1.2 严格序存在偏差；该 fixture 属 Task A 范畴，Task A 在 H_intake
  后会替换为真实 fixture，届时 self-check #9 的硬编码序需与真实 fixture 对齐。
  该 OBS 不影响 Task B 落盘。

## 5. 预审结论

**PASS（可落盘）**

等待 bookkeeper 串行落盘 H_B（前端）并继续 R4 对账 / 正式 review-1 流程。

- 只改 `frontend/index.html`、`frontend/self-check.js` 及本 stage 报告。
- `formatFundingRate`、`formatBeijing`、`formatBeijingShort` 函数体未改动。
- 未使用 `parseFloat` / `Number × 100` 做展示格式化。
- 无新依赖，同源 API。
- 中文口径不变，枚举三列仍显示「英文(中文)」。
- 未 commit、未改 `status.json`。
- 未触碰耦合面（Task A 产出字段/契约）。

## 6. 当前状态与下一步

- 实现完成，自测全绿。
- Claude-GLM 嵌入预审因命令超时未能完成，已按 R10 失败路径记录并升级。
- 等待 bookkeeper 处理调度失败，决定：重试 Claude-GLM、启用 fallback 预审者、
  或人工预审。

本地北京时间: 2026-07-06 09:25:59 CST  
下一步模型: bookkeeper  
下一步任务: 处理 Claude-GLM 预审调度失败并决定后续路径

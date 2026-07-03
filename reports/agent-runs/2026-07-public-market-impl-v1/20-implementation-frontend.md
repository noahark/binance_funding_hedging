# Task B 前端实现报告:公开市场费率行情表

- 阶段 ID:`2026-07-public-market-impl-v1`
- 任务:Task B(前端市场表)
- 实现者:Kimi
- 模型:kimi-2.7 / 本地 Kimi Code 默认模型
- 角色:minimal_change_engineer
- 文件边界:`frontend/**` + 本报告

## 交付文件

```text
frontend/index.html                              # 免构建静态页面(HTML/CSS/JS 内联)
frontend/fixture/public-market-snapshot.json     # 冻结 normalized 样本的字节级副本
frontend/self-check.js                           # Node mock-DOM 自检脚本
reports/agent-runs/2026-07-public-market-impl-v1/20-implementation-frontend.md   # 本报告
```

未触碰 `backend/**`、schema、contract 文档、API samples、Harness 文件、`docs/`、`agents/`、`workflows/`、`scripts/`。

## 实现内容

1. **页面结构**
   - 沿用 `prototypes/fake-ui/index.html` 的中文工作台视觉风格:侧边栏 + 内容区、panel、表格、badge、表单控件。
   - 只保留“费率行情”单一视图，去除了原型的总览持仓、手动开仓、收益归因等页面。

2. **数据源**
   - 默认请求 `fetch('/api/public-market/snapshot')`(同源后端 API)。
   - 离线 fixture 模式通过“加载离线 fixture”按钮触发，读取 `./fixture/public-market-snapshot.json`。
   - fixture 是 `reports/api-samples/public-market-contract-v2/20260703T051738Z/normalized/public-market-snapshot.json` 的字节级副本，未做任何手改。

3. **市场表展示列**
   - symbol、asset_tag、route_class。
   - `last_funding_rate`:列名固定为“最近更新的资金费率”，未使用“已结算”或“预测”。
   - `next_funding_time`:使用 `Asia/Shanghai` 时区转换为北京时间显示。
   - mark/index price。
   - negative_funding_status。
   - ui_flags(以 compact badge 展示)。

4. **状态标识**
   - BSTOCK 行使用 `tr.bstock` 紫色背景突出显示，asset_tag 也使用紫色 badge。
   - route_class 使用语义化 badge:PM 现货候选(绿)、仅现货候选(蓝)、仅合约(灰)。
   - negative_funding_status 使用语义化 badge。

5. **筛选与搜索**
   - symbol/base 搜索框。
   - asset_tag 下拉筛选(CRYPTO / BSTOCK / UNKNOWN)。
   - route_class 下拉筛选。
   - “显示 PERP_ONLY_EXCLUDED”开关，默认**未勾选**(即默认过滤掉 PERP_ONLY_EXCLUDED)。

6. **手动刷新**
   - “手动刷新”按钮重新请求后端 API。
   - 无自动轮询、无 websocket。

7. **warnings 展示**
   - 独立 panel 显示 `snapshot.warnings[]` 内容，位于页面可见区域，不会吞掉。

8. **阻塞检查**
   - 加载数据后调用 `validateContract()` 检查必需字段。
   - 若契约字段缺失，页面显示“集成阻塞”并给出具体原因，不写死兜底渲染。

9. **未实现内容**
   - 无开仓票据、规划计算器、下单流程、账户状态、持仓状态、交易意图按钮。
   - 无直连 Binance。
   - 无自行分类/换算逻辑(展示层格式化除外)。

## 自检清单与结果

运行 `node frontend/self-check.js`，结果如下:

```text
[PASS] 内联脚本语法检查
[PASS] 默认请求 /api/public-market/snapshot
[PASS] 数据源标签显示后端 API
[PASS] warnings 可见且内容已渲染
[PASS] 默认隐藏 PERP_ONLY_EXCLUDED，渲染 3 行
[PASS] 显示 PERP_ONLY_EXCLUDED 后渲染全部 6 行
[PASS] BSTOCK 行标识正确
[PASS] 时间转换正确
[PASS] 列名/文案符合契约
[PASS] 无交易按钮/开仓票据

全部自检通过
```

额外手动检查:

- `diff fixture/public-market-snapshot.json reports/api-samples/.../normalized/public-market-snapshot.json` 无差异，fixture 字节级一致。
- `python3 -m http.server` 启动后，`curl` 能正常返回 `index.html` 与 fixture JSON。

## Git 状态(未提交)

```text
Branch: main
HEAD: 79f25002cfd6dd53355b0a7bed7a8d7563872353
Untracked:
  frontend/
  reports/agent-runs/2026-07-public-market-impl-v1/
```

等待 controller 统一 commit。

## 阻塞项

无。

## 风险与说明

- fixture 模式需在 HTTP 静态服务器下使用;直接 `file://` 打开时 `fetch` 会被浏览器安全策略拦截。这是静态页面的常规限制，不影响同源后端托管场景。
- 页面未做自动刷新;数据时间来自后端 `generated_at`/`data_time`， footer 明确提示“数据非实时”。

## 下一步

等待 controller 统一进行 evidence commit，并执行 Task C 集成验证(后端 + 前端联调)。

---

本地北京时间: 2026-07-03 20:37:31 CST
下一步模型: controller
下一步任务: 统一 evidence commit 与 Task C 集成验证

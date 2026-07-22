[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务的唯一执行者。
1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令（包括但不限于
   claude-glm -p、kimi -p、codex exec、grok）。需要其他模型时，输出
   ESCALATED 及原因并停止。
2. 禁止编造未实际执行的命令结果或未实际读取的文件内容；你写下的每一条
   执行记录都必须对应你本会话内真实发生的动作。
3. 你的评审/实现依据只能是本 prompt 列出的 raw artifact 路径与你自己
   实际读取的文件。

# 任务：对冲「开单」前端 fake 原型（stage 2026-07-hedge-open-fake-ui-v1）

你是本 stage 的唯一实现者（Kimi，前端域）。这是一个**纯前端 fake 原型**：
无后端、无真实网络、无真实 websocket、无真实下单、无凭证。所有任务与持仓状
态存 `localStorage`，盘口价格用带周期漂移的假数据。目标是让用户先把开单交
互、开单任务页、私有账户持仓展示打磨定型，之后（stage 2）再接真实后端。

## 先读这些原始文档（权威规格，按此实现，不要臆造替代方案）
- `reports/agent-runs/2026-07-hedge-open-fake-ui-v1/00-task.md` — 交付项与验收
- `reports/agent-runs/2026-07-hedge-open-fake-ui-v1/10-design.md` — 完整 UI+数据契约规格
- `reports/agent-runs/2026-07-hedge-open-fake-ui-v1/11-adr.md` — 方向/基差/单腿风险决策
- `reports/agent-runs/2026-07-hedge-open-fake-ui-v1/12-development-breakdown.md` — 文件边界/冻结契约/review 关注点

## 允许修改的文件（硬边界，越界即无效）
- `frontend/index.html`（内联 `<script>`、DOM、CSS）
- `frontend/self-check.js`（只新增确定性断言）

## 禁止
- 改 `backend/**`、`schemas/**`、`docs/**`、`scripts/**`、`reports/**` 及其他任何文件。
- 新增依赖/框架/构建步骤/外部资源/第二个 `<script>` 块。仅用现有 vanilla JS 内联模式。
- 真实 websocket、后端桩、下单路径。反向开单**不自动借币**，只查 fake 额度。

## 必须精确实现的冻结契约
1. 市场表：`正向开单`→`正向开单率`、`反向开单`→`反向开单率`（仅改名，估算列
   原语义/`renderOpeningQuotesCell` 不变）；在 `借币` 列**之后**按序新增两操作列
   `正向开单`、`反向开单`，每列 = 两输入（单次币量/成功次数）+ 两按钮（平滑开单/
   立即开单）；两列恒可点，按该行费率符号高亮推荐方向按钮（正→正向、负→反向、
   0/null→都不高亮）。
2. 方向/基差口径（不得改符号或腿映射）：正向 basis=(perp_bid1−spot_ask1)/mid，
   反向 basis=(spot_bid1−perp_ask1)/mid，≥0.0005(0.05%) 才开。
3. fake 余额校验：正向查 USDT(币量×N×参考价)、反向查该币可卖额度(币量×N)，不足
   弹框（`正向开单 USDT 余额不足`/`反向开单现货余额不足`），不建任务。
4. 开单任务页：左侧新增 `nav-hedge-tasks` + `hedge-task-view` 面板，卡片纵列；
   卡片含 币种/方向/模式/成功x失败(x/3)/状态、漂移假盘口+开单率组合、平滑模式当前
   基差率 vs 0.05%；按钮 暂停/启动/删除/成交1次/立即成交所有（语义见 design §2.2）。
5. 私有账户 fake 持仓表（按币种聚合）：币种/方向/持仓数量/现货均价/合约均价/
   开单价差率/价格未实现盈亏/累计资金费/借币利息/净盈亏；聚合数学见 design §3。
6. Task/Fill 对象与 localStorage key 用 design §4 的**精确字段名**（stage 2 复用）。
7. 单腿敞口→`exposure_alert`+`leg_exposure`+暂停；累计失败 >3 → 终止计划+暂停+不补发。
   失败注入要可 seed，保证 self-check 确定性。

## 自测命令（必须真实运行并全绿）
```
node frontend/self-check.js
```
- 必须保留现有全部 `[PASS]`，并新增 design §6 的断言（列改名+新列有序在借币后、
  推荐高亮、余额弹框两路径、任务生命周期、>3失败终止、单腿敞口、持仓聚合数学、
  localStorage 往返、无新 fetch/跨域）。exit 0。
- 注意 self-check 只解析**第一个** `<script>` 块——新逻辑必须留在该块内。

## R10 收尾（实现者收尾职责，逐条照做后停下）
1. 运行上面的自测命令，把**完整输出**贴到
   `reports/agent-runs/2026-07-hedge-open-fake-ui-v1/60-test-output.txt`。
2. 写实现报告到
   `reports/agent-runs/2026-07-hedge-open-fake-ui-v1/20-implementation.md`：
   改动摘要、每个交付项对应的代码位置、契约符合性自查、自测结果、已知限制、
   以及 AGENTS.md「Output Footer」六行（Session ID/来源/原始输出路径/北京时间/
   下一步模型/下一步任务；时间戳用本地 `date`，Session ID 看不到就写 unavailable+原因）。
3. **不要** commit、不要改 status.json、不要启动或转派任何其他模型会话、不要越
   文件边界。完成后停下，交给 bookkeeper 收证据、串行 commit、算指纹、跑 validator、
   调度 review-1（Claude-GLM）。

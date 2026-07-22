# Implementation Report — Hedge Open Fake UI v1 (Kimi, front-end)

Stage: `2026-07-hedge-open-fake-ui-v1` · Branch: `stage/2026-07-hedge-open-fake-ui-v1`
Prompt: `task-hedge-open-fake-ui-kimi.prompt.md`（`[HARNESS-EXECUTOR-CONTRACT v1]`）

## 改动摘要

纯前端 fake 开单原型，全部改动落在允许的两个文件：

- `frontend/index.html`
  - T1：市场表估算列改名 `正向开单`→`正向开单率`、`反向开单`→`反向开单率`（`title`
    与 `renderOpeningQuotesCell` 语义不变，纯改名）；`借币` 列之后按序新增两操作列
    `正向开单`/`反向开单`，每列 = 两输入（单次开单币量/成功开单次数）+ 两按钮
    （平滑开单/立即开单）；两列恒可点（无 disabled），按行费率符号给推荐方向按钮
    加 `hedge-reco` 高亮类（正→正向、负→反向、0/null→都不高亮）。
  - T1.3：开单前 fake 余额校验。正向查 USDT（币量×N×假盘口参考价 mid），反向查该币
    可卖额度（币量×N）；不足弹 modal（`正向开单 USDT 余额不足` /
    `反向开单现货余额不足`，含需要 vs 可用），不建任务；足额扣减 fake 额度并建任务。
    非法输入走行内错误（`hedge-error-*`），不弹框。
  - T2：左侧导航新增 `nav-hedge-tasks`（含 `hedge-task-count` 运行中任务数徽标）+
    `hedge-task-view` 面板，`setActiveView` 扩为三视图互斥。任务卡纵列：币种/方向
    （正向/反向）/模式（平滑/立即）/已成功 s/N/失败 f/3/状态（运行/暂停/完成/
    敞口告警）、漂移假盘口四价 + 正向开单率/反向开单率组合、平滑模式当前基差率
    vs 阈值 0.05%（已满足/未满足徽标）。按钮：暂停/启动/删除/成交1次/立即成交所有。
  - fake 引擎：单一定时器 `setInterval(hedgeEngineTick, 1000)`（复用允许的 1000ms
    周期），盘口按币播种、乘法漂移（保留相对偏移）；平滑任务基差 ≥ 0.0005 推进一笔；
    立即模式与「立即成交所有」每 tick 一笔；成交1次立即推进一笔（不看基差/模式）。
    失败注入：mulberry32 可 seed 随机源 + `queueHedgeFillOutcomes` 强制队列
    （自检确定性）；单腿成交 → `leg_exposure` + `exposure_alert` + 暂停；累计
    `fail_count > 3` → 终止（派生自 `fail_count`，无新增字段）、暂停、不补发
    （启动拒绝）。成功达 N → `done`。
  - T3：私有面板（verified 分支）新增「对冲开单持仓（本地模拟）」表：币种/方向/
    持仓数量/现货均价/合约均价/开单价差率/价格未实现盈亏/累计资金费/借币利息/
    净盈亏；按 coin|direction 聚合任务 fills，均价=名义/数量，基差为量权平均，
    净盈亏=价格盈亏+资金费−利息（fake 计提速率常量每小时线性）。
  - 冻结数据契约（design §4）：localStorage 键 `hedge_open_tasks` /
    `hedge_fake_account`；Task/Fill 字段名逐字实现（`single_amount`、`target_n`、
    `success_count`、`fail_count`、`leg_exposure`、`fills[].basis_rate` 等）。
- `frontend/self-check.js`
  - 既有 13 列断言升级为 15 列（#5c headerCount、#33c 严格表头序/td 数/colspan，
    全部对齐新冻结列名与顺序）；empty-state colspan 13→15。
  - 元素 mock：ids 表新增 9 个开单相关元素；惰性 mock 正则扩展 `hedge-amount|count|
    error-*` 与 `hedge-task-error-*`。
  - 新增断言块 #77–#84（design §6 全覆盖）：操作列结构+推荐高亮+恒可点；基差口径
    双向数值；余额弹框两路径+非法输入行内报错+足额创建扣额；任务生命周期+平滑基差
    门控+卡片渲染+导航切换；>3 失败终止不补发+单腿敞口；持仓聚合数学（含反向利息）；
    localStorage 往返+私有面板持仓表；零新 fetch/零跨域。
  - 无泄漏守卫：localStorage 白名单扩展为 隐私键 + `hedge_open_tasks` +
    `hedge_fake_account`；定时器白名单不变（引擎复用 1000ms）。

## 交付项 ↔ 代码位置

| 交付项 | 位置（frontend/index.html） |
|---|---|
| 列改名 + 新操作列表头 | `<thead>`（`正向开单率`/`反向开单率` + 借币后两 `<th>`） |
| 操作列单元格/高亮 | `renderHedgeOpCell(row, direction)`，`renderRowHtml` 追加两格 |
| 推荐高亮样式 | CSS `.btn.hedge-reco` |
| 余额校验/弹框 | `submitHedgeOpen`、`showHedgeModal`/`closeHedgeModal`、modal DOM/CSS |
| 假盘口/基差 | `ensureHedgeBook`/`driftHedgeBooks`/`hedgeBasisRates`（ADR-2 口径） |
| 任务生命周期 | `createHedgeTask`/`hedgeAttemptFill`/`pauseHedgeTask`/`startHedgeTask`/`deleteHedgeTask`/`hedgeFillOnceNow`/`hedgeFillAll` |
| 引擎 tick | `hedgeEngineTick`（1000ms，boot 注册） |
| 任务页/卡片 | `hedge-task-view` section、`renderHedgeTasks`/`renderHedgeTaskCard`、`setActiveView` 三视图 |
| 持仓聚合/表 | `computeHedgePositions`、`renderHedgePositionsSection`（挂入 `renderPrivatePanel`） |
| 持久化 | `loadHedgeTasks`/`saveHedgeTasks`/`loadHedgeAccount`/`saveHedgeAccount`/`loadHedgeState` |
| 自检 seam | `__appHelpers` 新增 submit/create/pause/start/delete/fill/tick/compute + `queueHedgeFillOutcomes`/`setHedgeSeed`/`resetHedgeStateForTest` |

## 契约符合性自查

- 列改名纯改名：`renderOpeningQuotesCell` 与 60s-snapshot 语义未动（既有 #33d/33e
  等断言全部保留并通过）。
- 新列顺序：`借币` 之后 `正向开单`→`反向开单`（#33c 严格表头序断言）。
- 基差口径未改符号/腿映射：`hedgeBasisRates` 按 ADR-2 实现，#78 数值断言双向。
- 两列恒可点：单元格无 `disabled`（#77 断言），高亮仅加类。
- 余额弹框两文案逐字：`正向开单 USDT 余额不足` / `反向开单现货余额不足`（#79 断言）。
- Task/Fill/localStorage 键字段名冻结一致（#83 逐字段断言）。
- `>3` 失败终止+暂停+不补发；单腿敞口 `exposure_alert`+`leg_exposure`（#81 断言）。
- 反向开单不自动借币，只查 fake 额度；无 websocket/后端桩/真实成交路径；无新增
  fetch/跨域（#84 + 无泄漏守卫）；无第二个 `<script>` 块；无新依赖。
- 未触碰禁词基线（`下单`/`立即开仓`/`手动开仓` 在 index.html 中 0 命中）。

## 自测结果

```
node frontend/self-check.js  →  exit 0
[PASS] × 108（既有全部保留 + 新增 #77–#84），[FAIL] × 0
完整输出：reports/agent-runs/2026-07-hedge-open-fake-ui-v1/60-test-output.txt
```

## 已知限制

- 假盘口基差围绕微负值摆动，平滑任务自然触发频率低；「成交1次/立即成交所有」
  与盘口钉值是主要演练路径（fake 阶段可接受）。
- 「立即成交所有」运行集合为内存态，刷新页面后不续跑（任务本身持久化；设计 §2.2
  未要求跨刷新续跑）。
- 删除任务不返还已扣 fake 额度（fake 阶段未规定返还语义）。
- 资金费/借币利息为按 fill 时间线性计提的 fake 常量（0.01%/h、0.02%/h），
  非真实费率；positions 按设计从 tasks 派生，不单独持久化。
- fake 持仓表挂入 `private-panel` verified 分支（design §3 指定位置）；无私有
  key 时该面板整体隐藏，持仓表随之不显示。

## R10 边界声明

- 未 commit、未改 `status.json`、未触碰允许边界外任何文件（仅 `frontend/index.html`、
  `frontend/self-check.js` + 本报告与 `60-test-output.txt` 两个 stage 证据文件）。
- 未调用、启动或转派任何其他模型会话/adapter。完成后停止，交 bookkeeper 收证据、
  commit、算指纹、跑 validator、调度 review-1（Claude-GLM）。

当前 Session ID: unavailable（Kimi CLI 会话内无法读取 provider-native Session ID；运行时可由 operator 补录 status.json.session_receipts）
Session ID 来源: unavailable（本会话无 runtime_env/hook_payload/cli_output/transcript_path 可查）
原始输出路径: reports/agent-runs/2026-07-hedge-open-fake-ui-v1/60-test-output.txt
本地北京时间: 2026-07-22 19:35:18 CST
下一步模型: bookkeeper（人工 operator 执行收证据/commit/validator），随后 review-1 = Claude-GLM
下一步任务: 收串行 commit、计算 diff_fingerprint、跑 scripts/validate-stage.py --phase pre-review、调度 review-1

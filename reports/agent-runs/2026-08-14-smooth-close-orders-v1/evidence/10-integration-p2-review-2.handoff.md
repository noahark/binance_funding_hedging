# Task Handoff: 10-integration-p2-review-2

## Source Report (author-only; immutable after task end)

- task_id / role / target model: 10-integration-p2-review-2 / Reviewer（Review-2，reality-checker） / opus5（anthropic）
- stage_id / created_at: 2026-08-14-smooth-close-orders-v1 / 2026-08-14 23:48:41 CST
- base_sha / delivery_sha: 6f6c7297c895a3bf56ae5e0abc7a542de891dff7 / f95577fc892776e5fe268399a4331d86497c97f9
- status_revision: 12

范围：只读评审固定区间 `6f6c729..f95577f`（P2 前后端串联），并按 HIGH_RISK Review-2 职责对平滑平仓 V1 的**整体功能是否满足最初设计与业务目标、操作体验、发布就绪度**作判断。未启动服务、未创建任务、未下单、未修改任何交付文件。

评审结论：**ACCEPT**。阻塞发现：none。

### 一、需求与实际效果（对照 `docs/planning/smooth-close-orders-v1.md`）

**1. 方向翻转的展示诚实（C16 / §4.2 第 6、7 项，验收 2、3）——本轮最高风险项，已独立核验，正确。**

不采信 handoff 叙述，逐层比对代码：

- `domain.py:776 evaluation_direction`：close 任务方向取反，open 原样。
- `domain.py:1587-1592 evaluate_smooth_gate`：`DIR_REVERSE` 分支 = `compute(spot.bid, perp.ask)` + `spot.bid_qty / perp.ask_qty`。
- `service.py:1945-1949 _smooth_market_doc`：`forward_spread_pct` / `reverse_spread_pct` 固定按开单口径计算（字段语义未变，符合 §6.3），`current` 取 `evaluation_direction(task)` 的那一份，覆盖率与 pass 状态随之。
- `frontend/index.html:6167-6188`：close 卡左列「正向平仓率」渲染 `现货买一 + 合约卖一 + reverse_spread_pct`，右列「反向平仓率」渲染 `合约买一 + 现货卖一 + forward_spread_pct`；`closeActive/closeMark` 按 `task.direction` 高亮并标「本任务判定」。

结论：forward close 卡高亮的那一列，其价格、数量与百分比三者，与后端实际参与判定的 `reverse` 评估**同源同组**；reverse close 对称成立。开单卡两列标题与价格组零 diff（diff 内 open 分支逐字保留原字符串）。

**2. 平仓语义文案（验收 3）**：`service.py:1963-1969` 在 service 层把 close 任务的 `wait_reason` 中「开单率」替换为「平仓率」，`evaluate_smooth_gate` 判定逻辑未动，开单文案零 diff。前端原样渲染。平仓卡上不再出现「开单率」字样。

**3. 备料状态（C17，验收 22）**：`service.py:180-186 task_to_doc` 派生 `close_preparation_state`（open=None / smooth close=prepared|unprepared / immediate close=realtime_per_round），不落库；前端 `index.html:6260-6268` 只做枚举映射，无第二处真相、无本地推断。

**4. 启动交互（C13）**：`state.hedgePreparingStartId` 在 smooth close 的 start 请求期间置位，`try/finally` 保证回落；`pauseDisabled / startDisabled / deleteDisabled / fillDisabled` 四个按钮全部纳入置灰，启动按钮文案「备料中…」。失败经 `mutateHedgeTask` → `showHedgeTaskActionError` 写入 `state.hedgeTaskActionErrors[id]`，渲染到卡片 `hedge-task-error-<id>` 行且重渲染不被抹除（该机制有 self-check 断言）；同一失败原因另有 `pause_reason_zh` 行兜底。**不存在「按钮无反馈」或静默失败**。

**5. 危险动作提示**：平滑平仓确认弹框回显币种、方向、单次量、次数、阈值，并写明「比较当前方向平仓率，不是开单率」；建卡本身零资金动作，真正的资金动作（同步备料、可能真划转）需 Human 再点一次「启动」，且启动期间卡片有明确进行中态。立即平仓弹框文案零 diff。

**6. 零回归**：`submitHedgeClose` 第 5/6 参可选、缺省 `immediate` 且不带 `slippage_threshold_pct`；样式预览的 5 张假卡、`.smooth-close-style-preview` 样式、`data-smooth-close-style-preview` 处理器、`requestFakeSmoothCloseConfirm`、`hedge_close_style_preview` 分支全部删净，仓内零残留引用（`grep` 无命中），`els.hedgeTasksPanel` 仍被 `index.html:6992` 使用，非孤儿。

### 二、我自己执行的证据（不采信他人叙述）

```text
git status --porcelain            → 空（工作树干净）
git diff f95577f..HEAD -- backend frontend → 空（HEAD 的产品代码即交付代码）
node frontend/self-check.js       → exit 0，「全部自检通过」
.venv/bin/python -m pytest backend/tests/test_smooth_close_p1.py -q → 48 passed in 2.41s
git show -s 97ecb7f               → 2026-08-06；git merge-base --is-ancestor 97ecb7f 6f6c729 → 真
```

（P1 handoff 记录的是 46 条，实测 48 条；差额与 base_sha 所在的 07 修复轮一致，非缺陷。全量 `pytest backend/tests` 由 Bookkeeper 在 05 核验时实跑过 1936 passed / 1 条早于 base 的既有失败，本轮未重跑全量。）

### 三、范围外发现（pre-existing-independent，不阻塞，已按 Human 决定转 PROJECT_STATE）

- **前端平仓前置余额拦截对普通现货账户会误拦**（Review-1 提出，本轮复核成立）。`frontend/index.html:5764-5772` 的 forward 分支只以 `posRow.unified_balance` 字段存在为条件比较总量，币若实际在普通现货账户，统一账户读数为 `0` 时会以「页面显示统一账户现货约 0.00 < 需 N」直接拦截、不发请求。**引入提交 `97ecb7f`（2026-08-06），早于 `base_sha` 6f6c729，且本次交付未触碰这几行**（`git log -L` 命中最近一次改动即 97ecb7f）。
  - 需要 Human 知道的一点边界修正：`frontend/index.html` 本身在本次交付文件内，且新的「平滑平仓」按钮现在也经过这段前置检查；但「立即平仓」此前已经过同一段，故本次交付**没有扩大可达面**，只是让新按钮继承了同一缺陷。
  - 处置：按 dispatch 验收检查 2，本轮不阻塞，Review-2 通过后由 Bookkeeper 记入 `PROJECT_STATE.md`。

### 四、发布边界与操作提醒（设计已具名接受，非本轮发现，不构成 REWORK）

- **O-1 全功能从未对着运行中的服务跑过**。服务当前停止（`PROJECT_STATE.md` Current Status）。现有证据 = fake 全链后端测试 + 前端静态自检 + Human 页面验收；**没有任何一笔真实平滑平仓订单**。首次实盘应最小额度、单任务、展开日志观察。
- **O-2 点「启动」即可能真实划转**（forward，`_ensure_close_spot_balance`）。设计 §5.3 已具名：备料后若暂停或删除，已划到普通现货账户的币不会自动划回，需人工处理。
- **O-3 备料成功后事实冻结**（设计 §5.1/§5.2）。暂停后再启动不重做备料；期间在交易所手工平仓，或两腿部分成交致剩余可平量小于下一笔 `q_common`，都会产生单腿。C8 的阈值 1 让它停在第一次，但**不撤销已经发生的那一次**——恢复前必须先到交易所核对两腿。
- **O-4 阈值输入框继承既有 L3**（整表刷新会重置未提交输入，设计 §5.7 明确不修）。填了负阈值未及时点击，可能以默认 `0.05` 建卡；后果不是资金错误（多数轮次改走 timeout 放行仍会成交），但请以建卡后卡片「滑点阈值」行为准复核。

### 五、流程观察（交给 Human 与 Bookkeeper，不阻塞本次交付）

- 本阶段 Review-1（`09-integration-p2-review-1`）由 `gemini-3.1-pro` 执行，而它同时是本阶段 Bookkeeper；`08-integration-p2.handoff.md` 的 Bookkeeper 核验块自述「后续直接推进 Review-1（由 Bookkeeper 兼任执行完毕）」，且两处时间戳同为 `2026-08-14 23:45:00 CST`。
  - 与安全内核不冲突：Bookkeeper 不是交付代码作者（P2 作者为 `grok-4.6` / xai），`AGENTS.md` §3.4 与 §3.5 的 provider 隔离均满足（google ≠ xai）。
  - 与 `agents/roles.md` Reviewer Isolation 的「fresh read-only session」措辞存在张力：同一会话既写 `status.json` 与 dispatch，又出具 Review-1 结论。
  - 实际影响已被本轮覆盖：P2 的接线正确性由本 Review-2 独立重验（第一、二节），未依赖 Review-1 的结论。
  - 重开条件：若 HIGH_RISK 代码评审再次出现 Bookkeeper 兼任 Review-1，建议 Human 把 Review-1 路由到独立会话。

### 六、为什么是 ACCEPT

交付实现了设计要求的产品效果（平仓率镜像、展示诚实、备料可见、启动同步反馈、失败原地可读），未发现本次交付新引入的功能阻断或资金路径缺陷；唯一已知功能缺陷为范围外且 Human 已决定跟进。剩余风险全部是设计中已具名接受的项，且有明确操作边界。**本 ACCEPT 不授权合并、部署、启动服务或实盘下单**——最终决定权在 Human。

### Required Reading for the Next Task
- 读取路径及顺序：`reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/10-integration-p2-review-2.handoff.md`；`reports/agent-runs/2026-08-14-smooth-close-orders-v1/status.json`；`PROJECT_STATE.md`
- 执行：Bookkeeper 核验本 handoff 并收口 stage（把第三节的前端余额误拦记入 `PROJECT_STATE.md` Open Follow-ups，并按 `AGENTS.md` §7 末段检查 `docs/` 活文档是否需随本次交付同步）
- 关卡：Human 决定是否合并 `main`；合并、部署、启动服务与实盘下单均须 Human 单独授权
- 不能假设的事实：服务当前未启动；平滑平仓从未产生过真实订单；ACCEPT 不等于可实盘；备料状态与 `q_common` 是同一事实的两种呈现，不得据卡片文案推断已划转数量

## Human Brief / Console Receipt Source (author-only; immutable after task end)

[TASK_RESULT v2]
任务 ID: 10-integration-p2-review-2
执行结果: completed（完成）
结果摘要: Review-2 结论 ACCEPT。独立核验方向翻转展示与后端判定同源（forward 平仓卡高亮列=现货买一+合约卖一+reverse_spread_pct），备料状态、平仓率文案、启动全按钮置灰与失败原地回显均已落地，样式预览删净无残留。自跑 self-check 退出 0、平滑平仓测试 48 passed。未发现本次交付新引入的功能阻断；范围外前端余额误拦转后续项。
产物: [reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/10-integration-p2-review-2.handoff.md]
检查结果: [pass 方向翻转展示与后端评估同源（含 forward/reverse 两向对称）；pass 平仓卡无「开单率」字样且开单卡文案零 diff；pass 备料状态派生展示无第二处真相；pass C13 四按钮置灰+备料中文案+失败原地中文原因；pass 危险动作有确认弹框且建卡零资金动作；pass 立即平仓与开单路径零回归、样式预览删净无孤儿引用；pass 自跑 node self-check exit 0 与 test_smooth_close_p1.py 48 passed；pass 前端余额误拦经 git 复核确为 base 之前引入（97ecb7f，2026-08-06），范围外不阻塞]
阻塞项: [none]
本地北京时间: 2026-08-14 23:48:41 CST
下一步模型: gemini-3.1-pro（Bookkeeper，接收本次评审结果）
下一步任务: 读取：reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/10-integration-p2-review-2.handoff.md；reports/agent-runs/2026-08-14-smooth-close-orders-v1/status.json；PROJECT_STATE.md；执行：核验本 handoff、把前端余额误拦记入 PROJECT_STATE.md Open Follow-ups 并检查 docs/ 活文档同步，收口 stage；关卡：Human 决定是否合并 main，合并/部署/启动服务/实盘下单均须单独授权。
评审结论: ACCEPT（接受）
问题记录: reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/10-integration-p2-review-2.handoff.md
修复要求: none
[/TASK_RESULT]

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)
- source_sha256: f695b9600d546fe2072ed106062f51517ca24d1cb44c5fa4ad2be6617c734b61
- 核验时间: 2026-08-14 23:55:00 CST
- 核对 status revision: 12
- 依据: Review-2 结论 ACCEPT，无新引入的功能阻断；Human 明确验收。
- 后续状态: 验证通过（verified）。开始执行 Stage 收口流程。

## Errata (append-only)

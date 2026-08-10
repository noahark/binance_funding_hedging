# Task Handoff: local-net-position-review-1

## Source Report (author-only; immutable after task end)

- task_id: `local-net-position-review-1`
- role: Reviewer（review-1，只读 + 单一 create-only handoff）
- target model: `kimi`（provider identity: `moonshot`；实现者 `claude_glm` = `zhipu_glm`，跨 provider）
- stage_id: `2026-08-10-local-net-position-v1`
- created_at: 2026-08-10 13:08:38 CST
- base_sha: `53ed646f4b97d07ea478a834ed8eb6acb83bbedf`
- delivery_sha: `b67862aa188d96247db7c807d33846ce4750e8e2`（已固定的被审交付 SHA，直接 `git rev-parse` 值）
- 工作树 HEAD（仅上下文）：`f085792e7f6f537bd3d8f65eb8b9525f184c1ed3`（stage 分支，`= delivery_sha` 之后唯一的 Bookkeeper 封存提交）
- required_skill: `agents/skills/code-reviewer.md`
- 评审结论：**ACCEPT**

---

### 1. 身份与锚定核验（验收 1）

- dispatch task_id / target_model / provider / status_revision=4 与 `status.json`（revision 4、phase `review_1`、current_task 指向 `04-review-1.dispatch.md`）一致；ACTIVE.json 指向本 stage。
- 评审锚定固定区间 `53ed646…53ed`（base）与 `b67862a…e8e2`（delivery），不以移动 HEAD 代替。`git log base..delivery` 共 4 个提交：stage 初始化、计划评审反证、实现 dispatch、唯一 delivery commit `b67862a`。区间内 stage 控制文件（dispatch / status / handoff / PROJECT_STATE）只作上下文。
- 交付后 HEAD 相对 delivery 的差异（`git diff --stat b67862a..HEAD`）仅含 `04-review-1.dispatch.md`、`status.json`、handoff 的 Bookkeeper Verification 追加与 PROJECT_STATE——**受审代码、测试、文档在 HEAD 与 delivery_sha 完全一致**，故工作树复跑测试等价于在固定 SHA 上运行。
- 交付 commit `b67862a` 的文件清单与实现 dispatch Allowed Files 精确一致：`store.py`、两个测试文件、`docs/api/public-market-contract.md`、handoff、`status.json` 单一状态位；无范围外文件。

### 2. 逐条验收核验结果（验收 2–9）

**(验收 2) SQL-B 同读 open/close 并带出 task_type，其余语义不变 — pass。**
diff 显示仅删除 `WHERE t.task_type = ?` 与 `(D.TASK_TYPE_OPEN,)` 参数，新增 `t.task_type` 选择列；已关闭周期过滤 `(a.cycle_id IS NULL OR c.closed_at_us IS NULL)`、排序、legacy `hedge_open_fill`（SQL-A）告警分支均未触碰。删除任务成交保留：`t.status` 仍在选择列，`includes_deleted_task` 既有逻辑未改，新增用例 `test_aggregate_local_net_qty_close_from_deleted_task_still_counted` 断言已删除 close 任务真实成交仍扣减且 flag 为 True。`_take_identity` 代码未改；close 身份继承自周期首个 open 任务（`service.py:789-807`），正常一致（计划评审 O-1 的极端多写一条审计事件不改变聚合结果，维持非阻塞观察）。

**(验收 3) 数量只认真实成交，open +q / close −q — pass。**
`store.py:2599-2603`：`if _num(row["cumulative_base_qty"]) <= 0: continue` 先于一切聚合（A-6 策略保留），随后 `is_open` / `leg_sign` 逐腿独立计量。不以 task status、pair outcome、目标量或 success/accepted 计数替代——零成交失败腿与 PARTIALLY_FILLED 正成交腿均有专门用例。

**(验收 4) close 不进开仓成本基 — pass。**
`store.py:2626-2644`：`b["spot_notional"]/b["spot_qty_priced"]` 仅在 `is_open and known_notional` 时累加；`elif is_open:` 才置 `*_incomplete`——close 腿即使有 quote 也不进分子分母、不污染 incomplete 语义。XVG 用例断言 close 前后 `spot_avg/perp_avg` 逐字一致；close 全平后均价仍等于开仓均价。

**(验收 5) 输出字段集合与下游契约不变 — pass。**
diff 中无 `domain.py`、前端、下单/闸门/借还款/划转文件；`position_qty = direction_sign × leg_sign × q`，forward 负、reverse 正。`test_hedge_api.py` 的 `_POSITION_KEYS` 固定字段断言在 224 项全过中包含。`domain.py:1983-2022` 的 `single_leg_exposure`（`larger > 0` 前置）与 `drift`（`recorded_spot <= 0` 前置）未改，自然消费修正后的本地净量。

**(验收 6) XVG / XLM 回归 — pass。**
- XVG：`test_aggregate_local_net_qty_double_leg_partial_close` 断言 open 50000 + 两次双腿 close 各 10000 → spot/perp 30000、forward `position_qty=-30000`、均价 50000 不变。
- XLM：`test_aggregate_local_net_qty_single_leg_close` 断言 reverse open 双腿 100、close 仅 perp 成交 100/spot 零成交 → 剩 spot 100/perp 0、position_qty 0；pair 失败不忽略 perp 成交。`single_leg_exposure` 消费侧既有 `test_positions_merge.py` 用例未改且通过（abs(100−0) > 100×1% → true 由 merge 层既有逻辑保证）。

**(验收 7) 边界覆盖与 task_type 合法值 — pass。**
新增 8 个用例覆盖：双腿部分平仓、单腿 close、PARTIALLY_FILLED 正成交、零成交失败、reverse 正号、同周期再开（cycle_id 与 `cycle_opened_at` 不变）、已删除 close 成交、关闭周期过滤。`task_type` 合法值：列定义 `TEXT NOT NULL DEFAULT 'open'`（`store.py:428`），domain `ALL_TASK_TYPES = (open, close)`，写路径 `service.py:756` `D.validate_task_type(task_type)` 在 create_task 校验——`is_open` 的二元分支无第三种值可落入。

**(验收 8) v0.18 文档 — pass。**
`docs/api/public-market-contract.md` v0.18 段：明确三个本地数量字段是应用成交账本剩余量、非交易所对账；`um_position_amt` 是同次账户快照的交易所合约量；`single_leg_exposure=false` 与 `drift=false` 都不得解读为两边一致（含 ≤0 静默、unified_balance 含子钱包的假阴性来源）；明确无新字段、无 shape 变化、无 schema/DB/服务/闸门/订单/借还款/划转/前端变化。与计划 §8 裁定第 4 条一致。

**(验收 9) 独立复跑 — pass（附一条控制文件观察）。**
- `.venv/bin/python -m pytest backend/tests/test_hedge_cycle_close.py backend/tests/test_hedge_cycle_core.py backend/tests/test_hedge_store.py backend/tests/test_positions_merge.py backend/tests/test_hedge_api.py` → `224 passed in 25.24s`（与实现 handoff 的 224 passed 及 Bookkeeper 复跑的 224 passed 一致）。
- `git diff --check 53ed646…53ed..b67862a…e8e2`：全区间报 4 处 `new blank line at EOF`，全部位于 stage 控制文件（`01-plan-review.dispatch.md`、`02-plan-review-r2.dispatch.md`、`plan-review-f1-counter-evidence.md`、`plan-review-f1-human-adjudication.md`）；交付 commit 区间 `f0a9535..b67862a` 的 `git diff --check` 干净。控制文件按 §8 评审范围口径只作上下文，非受审交付，不阻塞。

### 3. 范围三分类（验收 10）

本次评审无 `REWORK` 发现。上述 diff --check 空白观察属 stage 控制提交，按区间口径为范围外上下文，记为非阻塞观察，不进 Human 决策摘要的阻塞项。计划评审 F-1（close-only 空桶）已由 Human/Planner 降级并具名重开条件，本次未仅凭同一未准入假设重新阻塞；代码现状（负净量不隐藏、直接可见）与裁定一致。

### 4. 未做的事

未修改交付、未修复任何内容、未改 status/PROJECT_STATE/既有 evidence、未 commit/merge/push/部署、未启动或重启服务、未触碰闸门、未读凭证、未访问 live DB、未启动或联系其他模型。本任务唯一写入是本 handoff。

### 5. 可复现命令（本次实际执行）

```bash
git log --oneline 53ed646f4b97d07ea478a834ed8eb6acb83bbedf..b67862aa188d96247db7c807d33846ce4750e8e2
git diff --stat 53ed646f4b97d07ea478a834ed8eb6acb83bbedf..b67862aa188d96247db7c807d33846ce4750e8e2
git diff --check 53ed646f4b97d07ea478a834ed8eb6acb83bbedf..b67862aa188d96247db7c807d33846ce4750e8e2   # 仅 4 处控制文件 blank-line-at-EOF
git diff --check f0a95355517455331349411577913aefa5cf97dc..b67862aa188d96247db7c807d33846ce4750e8e2   # 干净
git diff --stat b67862aa188d96247db7c807d33846ce4750e8e2..HEAD   # 仅 stage 控制文件
git show --stat b67862aa188d96247db7c807d33846ce4750e8e2
git diff f0a95355517455331349411577913aefa5cf97dc..b67862aa188d96247db7c807d33846ce4750e8e2 -- backend/hedge_open_tasks/store.py backend/tests/ docs/api/public-market-contract.md
.venv/bin/python -m pytest backend/tests/test_hedge_cycle_close.py backend/tests/test_hedge_cycle_core.py backend/tests/test_hedge_store.py backend/tests/test_positions_merge.py backend/tests/test_hedge_api.py   # 224 passed in 25.24s
```

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-10-local-net-position-v1/evidence/local-net-position-review-1.handoff.md`
  2. `reports/agent-runs/2026-08-10-local-net-position-v1/status.json`
  3. `reports/agent-runs/2026-08-10-local-net-position-v1/04-review-1.dispatch.md`
- 执行：Bookkeeper 按 Task Handoff Evidence Contract 同文件核验（源区块 SHA-256、task_id/role/stage_id/base_sha/delivery_sha 与 status 及 `git rev-parse` 一致、create-only 路径、TASK_RESULT v2 结构与 review closure 三行、§5 命令可复现），把 `current_task` 核验推进。
- 关卡：Bookkeeper 核验通过后，按 Human 既有一次性授权（本 stage review-2 豁免、review-1 ACCEPT 后授权合并 `main`）处理合并；部署、服务重启、开关与实盘操作仍需单独授权，不在本授权内。
- 不能假设的事实：
  - 本 ACCEPT 只覆盖固定区间 `53ed646…53ed..b67862a…e8e2` 的代码、测试与 API 文档；不授权部署、重启、闸门或实盘。
  - `git diff --check` 全区间的 4 处空白提示全部在 stage 控制文件，交付 commit 区间干净；若后续在归档前修整控制文件，注意不触碰本已核验的交付提交。
  - close-only 空桶（open 成交为 0）形状未做隐藏——净额按 open−close 自然得出（可为负），这是 Human/Planner 裁定的既定行为，重开条件见 `reports/agent-runs/2026-08-10-local-net-position-v1/evidence/plan-review-f1-counter-evidence.md` 与 `reports/agent-runs/2026-08-10-local-net-position-v1/evidence/plan-review-f1-human-adjudication.md`。
  - 三个本地净量字段不是交易所对账；`drift`/`single_leg_exposure` 为弱告警，`false` ≠ 一致（v0.18 段）。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

```text
[TASK_RESULT v2]
任务 ID: local-net-position-review-1
执行结果: completed（完成）
结果摘要: 固定区间只读 review-1 完成，结论 ACCEPT。SQL-B 同读 open/close 腿并按 task_type 逐腿 +q/−q，数量只认 cumulative_base_qty>0；close 不进开仓成本基；字段集合、domain、前端、下单闸门不变；XVG/XLM 回归与 8 项边界用例成立；v0.18 文档语义正确；独立复跑 224 passed，交付 commit diff --check 干净。
产物: [reports/agent-runs/2026-08-10-local-net-position-v1/evidence/local-net-position-review-1.handoff.md]
检查结果: [
  1 身份与锚定：status revision 4、stage、kimi/moonshot、固定 base/delivery SHA 一致，HEAD 相对 delivery 仅控制文件：pass；
  2 SQL-B 同读 open/close 带 task_type，关闭周期过滤/legacy fill 告警/删除任务成交保留/identity 语义不变：pass；
  3 数量只认真实 cumulative_base_qty>0，open+q/close−q，无 task status/pair/目标量/计数替代：pass；
  4 notional/priced 分母仅 open 腿，close 不改 spot_avg/perp_avg 与 incomplete：pass；
  5 字段集合不变，position_qty forward 负 reverse 正，domain/前端/下单闸门未改：pass；
  6 XVG（30000/−30000/均价不变）与 XLM（spot100/perp0）回归及 single_leg_exposure/drift 消费结果：pass；
  7 部分成交/零成交/reverse/同周期再开/已删除成交/关闭周期过滤边界与 task_type 合法值校验：pass；
  8 v0.18 文档区分本地净量与 um_position_amt、两弱标记 false≠一致；pytest 224 passed、交付区间 diff --check 干净：pass
]
阻塞项: [none]
本地北京时间: 2026-08-10 13:08:38 CST
下一步模型: Codex（本 stage 的 Bookkeeper，负责状态核验与封存），由 Human 转交启动
下一步任务: 读取：reports/agent-runs/2026-08-10-local-net-position-v1/evidence/local-net-position-review-1.handoff.md；reports/agent-runs/2026-08-10-local-net-position-v1/status.json；reports/agent-runs/2026-08-10-local-net-position-v1/04-review-1.dispatch.md；执行：Bookkeeper 同文件核验本 handoff（源 SHA-256、SHA 与 status/git 一致、create-only、TASK_RESULT v2 与 review closure、命令可复现）并把 current_task 推进 verified；关卡：核验通过后按 Human 既有一次性授权（review-2 豁免、ACCEPT 后授权合并 main）处理合并，部署/重启/实盘仍须单独授权
评审结论: ACCEPT（接受）
问题记录: none
修复要求: none
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- source_sha256: `36b054e3a78928c5b5512940d20562152d261b171aa814e2780b4bf2d7f8b551`
- verified_at: `2026-08-10 13:13:59 CST`
- status_revision_checked: `4`
- identity_check: `pass` — task_id、Reviewer role、Kimi/moonshot、stage_id 与 dispatch/status 一致，且实现者 provider 为 zhipu_glm，满足跨 provider 隔离。
- create_only_check: `pass` — 路径在 review dispatch 提交 `f085792e7f6f537bd3d8f65eb8b9525f184c1ed3` 中不存在，本次只新增该唯一 handoff，marker 完整。
- sha_anchor_check: `pass` — `base_sha=53ed646f4b97d07ea478a834ed8eb6acb83bbedf`、`delivery_sha=b67862aa188d96247db7c807d33846ce4750e8e2` 均与 status 及 `git rev-parse` 一致。
- result_protocol_check: `pass` — `TASK_RESULT v2` 完整闭合；`评审结论: ACCEPT（接受）`、`问题记录: none`、`修复要求: none` 明确且无歧义。
- evidence_check: `pass` — Reviewer 已检查固定区间、契约、测试与集成 seam；全区间空白提示仅来自控制文件，实际 delivery commit 区间 `f0a95355517455331349411577913aefa5cf97dc..b67862aa188d96247db7c807d33846ce4750e8e2` 的 `diff --check` 干净。
- acceptance_reproduction: `pass` — Bookkeeper 再次独立运行指定 5 个测试文件，结果 `224 passed in 24.35s`；delivery 代码、测试、API 文档自固定 SHA 后未变化。
- verdict: `ACCEPT verified` — review-1 正式通过；本 stage 的 review-2 已由 Human 一次性豁免，按既有明确授权进入本地 `main` 合并与归档。

## Errata (append-only)

- none.

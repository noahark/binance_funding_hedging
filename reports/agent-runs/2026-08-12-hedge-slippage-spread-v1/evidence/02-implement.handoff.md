# Task Handoff: 02-implement

## Source Report (author-only; immutable after task end)
- task_id: `02-implement`
- role: `Implementer`
- target model: `codex`（provider `openai`）
- stage_id: `2026-08-12-hedge-slippage-spread-v1`
- status_revision: `3`
- created_at: `2026-08-12 07:55:32 CST`
- base_sha: `7da67bc87261386c117b98f2b63c6ac6083fd291`
- delivery_sha: `pending`

### 任务背景与实际修改

按已通过跨 provider 计划评审的 dispatch，实现历史仓位开单/平单两腿真实成交价差百分比。
`HedgeOpenStore.cycle_slippage_pct(cycle_id, task_type)` 保持签名不变，从
`hedge_open_cycle.direction` 读取方向，调用 `domain.direction_to_leg_actions` 取得对应阶段的
卖/买腿，并复用 `_cycle_leg_basis_locked` 分别聚合现货腿与合约腿跨 attempt 的真实成交数量
加权均价。公式为 `(卖出腿均价 - 买入腿均价) / min(两腿均价) * 100`，全程 `Decimal`，输出
四位百分数文本。旧 task/attempt preflight `est_price` 计算路径已从该函数删除。

无周期、无效方向、无效 `task_type`、任一腿不可定价或均价非正、分母非正均返回 `None`；真实
零价差返回 `"0.0000"`。同步更正 `store.py` 的 schema/docstring 注释，不改变 schema 或 API
字段。`test_hedge_cycle_close.py` 中旧口径下期待 `None` 的两个断言已更新为真实零价差。

### 测试与证据

- `backend/tests/test_hedge_store.py` 新增最小回归覆盖：forward/reverse × open/close 四种卖买腿
  映射；两腿分别跨两个 attempt 的数量加权；缺腿、无周期、无效输入、非正均价、零价差；
  JSTUSDT reverse open `0.2316` 与 reverse close `-0.2192`。测试任务的 `est_price` 特意设为
  无关值或缺失，可反证旧估价路径回归。
- `.venv/bin/python -m pytest backend/tests/test_hedge_store.py backend/tests/test_hedge_cycle_close.py -q`
  → `131 passed in 3.09s`。
- `.venv/bin/python -m pytest backend/tests -q`
  → `1763 passed in 144.08s (0:02:24)`。
- `git diff --check` → pass（无输出）。
- 未读取或写入实盘数据库，未控制/重启/部署服务，未执行订单、资金、闸门或凭证动作；未修改
  API、schema、frontend 或 service 功能逻辑。工作区原有 Human 改动
  `frontend/index.html`、`frontend/self-check.js` 保持未暂存、未提交。

### 未完成事项

无实现阻塞。历史 JSTUSDT 数据补录、前端/service 旧口径文本同步、合并、部署和实盘动作均不在
本 dispatch 授权范围；不得由本结果推定已完成或已获授权。

### Required Reading for the Next Task
- 读取路径及顺序：`reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/02-implement.handoff.md`、`reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/status.json`
- 执行：Bookkeeper 核验本 handoff 源区 SHA-256、任务身份、`base_sha`、两级测试结果与 delivery commit 五路径范围，解析 `pending` 为实际 `delivery_sha`，更新阶段状态并准备 Opus 5 review-1 dispatch
- 关卡：Bookkeeper 核验交付通过后，由 Human 启动 Opus 5 独立 review-1 终端
- 不能假设的事实：测试通过不等于独立评审接受、合并、部署、历史数据补录或任何实盘授权；Human 所属前端未提交改动不属于本交付

## Human Brief / Console Receipt Source

```text
[TASK_RESULT v2]
任务 ID: 02-implement
执行结果: completed（完成）
结果摘要: 已将历史仓位开/平价差改为按方向选择两腿真实成交数量加权均价，使用 min 分母、×100 与四位 Decimal 文本；缺腿/非法/非正返回 None，零价差为 0.0000。JSTUSDT 得 0.2316/-0.2192；两级后端测试 131/1763 项通过。
产物: [backend/hedge_open_tasks/store.py, backend/tests/test_hedge_store.py, backend/tests/test_hedge_cycle_close.py, reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/status.json, reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/02-implement.handoff.md]
检查结果: [
1. pass 公式、四向映射、min 分母、×100 与四位 Decimal 文本符合 Goal；
2. pass 两腿分别跨 attempt 数量加权，cycle_slippage_pct 已删除 est_price 路径且测试以无关/缺失估价反证回归；
3. pass 缺腿、不可定价、无周期、无效输入、非正均价/分母返回 None，真实零价差为 0.0000；
4. pass JSTUSDT reverse open 为 0.2316、reverse close 为 -0.2192；
5. pass 定向后端测试 131 passed；
6. pass 完整后端测试 1763 passed；
7. pass git diff --check，delivery commit 仅含 dispatch 授权五路径；
8. pass 零实盘库写入、零服务控制/重启/部署、零订单/资金/闸门动作，API/schema/frontend/service 功能行为不变
]
阻塞项: [none]
本地北京时间: 2026-08-12 07:55:32 CST
下一步模型: codex（本阶段 Bookkeeper）
下一步任务: 读取：reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/02-implement.handoff.md, reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/status.json；执行：Bookkeeper 核验源 SHA-256、任务身份、测试与 delivery commit 五路径范围，解析 pending delivery_sha，更新阶段状态并准备 Opus 5 review-1 dispatch；关卡：Bookkeeper 核验通过后由 Human 启动 Opus 5 独立 review-1 终端
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

## Errata (append-only)
任何更正均追加，说明日期、作者、改动原因与不改变的事实；不得改写 Source Report 或 Human Brief。

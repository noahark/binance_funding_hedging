# Stage Task

## Stage ID

`2026-07-borrow-task-ui-fake-v1`

## Goal

交付可交互的前端借币任务原型。用户能从行情表某一行使用两个输入框和确认按钮创建内存中的 fake 任务；左侧“借币任务”导航展示该任务。`HOME` 作为行基础资产时必须正确创建 `HOME` 任务。用户能直观看到“每 30 秒尝试一次，失败等待下次，达到成功次数停止”的未来后端行为，但本轮绝不发送真实请求或运行重试循环。

## Non-Goals

- 不修改 `backend/`、API schema、服务配置或任何 Binance 调用。
- 不创建后台任务、真实 `setInterval` 重试、持久化、订单、借币、还币、转账或其他外部副作用。
- 不伪造 `HOMEUSDT` 或其他市场行情行。
- 不新增输入“重试秒数”；本原型固定展示 30 秒，后端阶段再决定配置契约。

## File Boundaries

Allowed files:

- `frontend/index.html`
- `frontend/self-check.js`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/20-implementation.md`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/60-test-output.txt`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/status.json`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/70-handoff.md`

Forbidden or out-of-scope files:

- `backend/**`
- `schemas/**`
- `docs/**`
- `workflows/**`
- `agents/**`
- API fixtures and public-market contracts

## Acceptance Criteria

- 行情表表头在“借贷状态 / 资产”右侧有“操作”，每个数据行有 13 个 `td`，空态 `colspan` 为 13。
- 操作单元格有恰好两个可编辑输入：单次借币数量、成功次数上限；有一个“确认”按钮。操作事件不能打开行情详情抽屉。
- 数量必须是大于 0 的有限数值；次数必须是大于 0 的整数。无效输入显示就近错误，不创建任务。
- 有效确认仅更新浏览器内存中的 fake 任务和 UI；绝不发起 `fetch`、不使用真实借币 API、也不启动重试定时器。
- 创建任务的资产使用该行 `base_asset`。内存样例 `base_asset: HOME` 创建后，任务列表展示 `HOME`、`1,000 HOME/次`、`0 / 10 次成功`、`目标 10,000 HOME`、`每 30 秒尝试一次`和明显的“前端演示/未发起真实借币请求”说明。
- 左侧在“费率行情”后增加可切换的“借币任务”入口，并带当前任务数。任务页的空态和至少一个任务卡/行可正确显示；返回“费率行情”后市场视图恢复。
- `maxBorrowableSubline` 不再输出独立“已借完”标记；状态徽标“可借 0(已借完)”仍保留。
- `node frontend/self-check.js` 和 `git diff --check` 通过。

## Human Gates

真实借币、后台重试、私有 API、账户风险和任何持久化都需要用户审阅本原型后的明确批准。

## Designer

- Model: Codex/GPT
- Skill: software_architect
- Date: 2026-07-18

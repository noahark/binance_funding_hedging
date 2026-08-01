# Dispatch —— hedge-merged-positions-v1（Task 1，①）

```text
Identity:
  task_id:         hedge-merged-positions-v1
  target_role:     Implementer
  target_model:    claude_glm
  provider:        zhipu_glm
  status_revision: 8
  required_skill:  agents/skills/senior-developer.md
```

## Goal

实现方案的 **Task 1（①）**：在后端服务器层合并持仓，前端只渲染。

**方案是权威，本 dispatch 不重述它。** 范围、要点、文件边界、验收标准、测试策略均以
`12-development-breakdown.md` 的 `## Task 1 —— hedge-merged-positions-v1` 一节为准，
其决策依据见 `10-design.md` P1 与 N1-N5、`11-adr.md` ADR-001。你是该方案的作者，已有上下文。

本 dispatch 只做三件事：**锁定边界**、**钉入计划评审带出的具名项**、**定停止条件**。

计划评审（`deepseek`，跨 provider 只读）已对该方案返回 `ACCEPT`，无 `in-range` 发现，
四条事实 F-A~F-D 经其独立复核成立（`40-plan-review-deepseek-v2.md`）。

### 前置状态

- 本任务是**串行链的第一环**：① → ② → ③。② 与 ③ 尚未开工，不得触碰其范围。
- `rate_limited` 是否剥离（R1）**尚待 Human 裁定**，属 Task 2/3 范畴，**与本任务无关**，不得在本任务中改动任何暂停/删除逻辑。
- `rework_count` 当前为 `0`。本任务是本 stage 的第一个代码交付物，其返工计数独立于此前的 fake UI 与计划文档。

## Allowed Files

以方案 Task 1 的「文件边界（Allowed Files）」为准，即：

- `backend/app/server.py`
- `backend/hedge_open_tasks/service.py`
- `backend/hedge_open_tasks/store.py`
- `backend/hedge_open_tasks/domain.py`
- `backend/tests/test_hedge_store.py`、`test_hedge_service.py`、`test_hedge_api.py`，或新增 `backend/tests/test_positions_merge.py`
- `backend/tests/test_hedge_review2_regressions.py`（**新增授权**，理由见具名项 N-3）
- `frontend/index.html`
- `frontend/self-check.js`

新建产物：

- `reports/agent-runs/2026-07-31-hedge-task-lifecycle-v1/21-merged-positions-implementation.md`（实现报告）
- `reports/agent-runs/2026-07-31-hedge-task-lifecycle-v1/61-merged-positions-test-output.txt`（**原始**测试输出，不得改写为叙述）

**不得改动**（方案已列，此处强化）：`private_client.py`、`hedge_preflight_provider.py` 的白名单、`backend/hedge_open_tasks/scheduler.py`、`domain.py` 的暂停原因集与 51169 文案区（`:1315-1324`）、`status.json` 的 `current_task.state` 以外任何字段、以及上列之外的任何文件。

边界不足即为阻塞项，报告并停止，不得自行扩大。

## Inputs

### 必读

| 文件 | 读什么 |
|---|---|
| 本 dispatch | 全部 |
| `12-development-breakdown.md` | **`## Task 1` 全节 —— 本任务的权威规格** |
| `10-design.md` | P1 与 N1-N5、P7 占位零三分类、§5 与 fake 的差异清单 |
| `11-adr.md` | ADR-001（后端合并的 Context/Decision/Consequences） |
| `40-plan-review-deepseek-v2.md` | §4「评审带出的、需转入实现阶段的具名项」 |
| `agents/developer-discipline.md` | 全部 |
| `agents/skills/senior-developer.md` | 全部 |

字节数请自行 `wc -c`。三个后端主文件合计约 27 万字节，**禁止整文件读**，按方案已列锚点定位。

### 计划评审带出的四个具名项（必须处理）

- **N-1｜既有测试断言了 D15 要反转的行为。** `backend/tests/test_hedge_store.py:279-285` 的
  `test_aggregate_positions_excludes_deleted_tasks` 现断言 `store.aggregate_positions() == []`
  （删卡后聚合为空）。D15 使该断言失效。**必须更新为断言新行为（已删任务的已成交腿仍计入 +
  `includes_deleted_task` 为真），不得删除该测试**，并在实现报告中说明新旧断言的差异。
- **N-2｜`includes_deleted_task` 的行文案须写明均价含义。** 当同一 `(coin, direction)` 桶同时含活任务与
  已删任务的腿时，`spot_avg`/`perp_avg` 是两者的混合加权均价（数学正确，但来源混合）。行标记文案
  须让用户看懂这一点 —— 评审建议「含已删除任务记录，均价为混合值」而非仅「含已删除任务记录」。
- **N-3｜另一处间接消费者。** `backend/tests/test_hedge_review2_regressions.py:477` 经
  `svc.get_positions()` 间接消费该接口，形状变更后会受影响。已为此授权该文件；**只做形状适配，
  不得放宽或删除其原有回归意图**，改动逐条在实现报告中说明。
- **N-4｜前端 mock 需同步。** `frontend/self-check.js:708-709` 拦截 `/api/hedge-open-positions`
  并返回 mock；接口形状变更后该 mock 须同步为新形状，否则自检验的是旧契约。

## Acceptance Checks

以方案 Task 1「验收标准」的 **10 项**为准（后端合并六场景 / D15 两条查询 + 标记 / N2 降级不 503 /
N1 形状与消费者 / 符号对齐 1000x 六币 / 占位零三分类 / 三类标记齐全 / 51169 逐字 /
`self-check.js` EXIT=0 且未放宽断言 / 单一合并表无重复），**外加**：

11. **N-1 至 N-4 四个具名项逐项处理**，每项在实现报告中说明做法。
12. **后端测试全绿**：运行既有后端测试套件，原始输出存入 `61-merged-positions-test-output.txt`；
    因本任务契约变更而修改的测试逐条说明「改了什么、为什么、原回归意图是否保留」。
13. **`merge_positions` 是纯函数**：不持有服务引用、不发起 I/O、可被数据驱动单测直接调用；
    handler 仅做装配，**不得**把 `SnapshotService` 注入 `HedgeOpenTaskService`（两服务保持解耦，方案明列）。
14. **零新增交易所请求**：本任务不得新增任何对币安的调用；`get_snapshot()` 是零上游纯读（F-B），
    请在报告中确认实现路径未引入新的上游读取。

每项在 `[TASK_RESULT v2]` 的 `检查结果` 里按 `AGENTS.md` §7 标注 `pass` / `fail` / `contested`。
`检查结果` 最多八项，请合并同类；详细逐项说明放实现报告。

## Stop

- 完成后按 `AGENTS.md` §7 输出 `[TASK_RESULT v2]`，把 `current_task.state` 由 `dispatched` 改为
  `reported`（这是你被授权改动 `status.json` 的**唯一**字段），然后**停止**。
- 不得设置 `next`、不得自行判定验收、不得合并、不得推送。
- 不得触碰 Task 2 / Task 3 的范围（暂停与删除逻辑、worker 退避、重查间隔），**即使你看到了顺手能改的地方**。
- 不得接触凭证或实盘路径；不得启动、调用、转交或冒充任何其他模型会话（§3 #2）。
- 若发现方案与实际代码矛盾、或某条验收标准无法在不越界的前提下满足：**停止并报告**，不要自行取舍。
  上一 stage 的教训是：packet 的禁令若堵死了发现缺陷的路，代价由整条链承担 —— 发现矛盾就报，不要绕。
- 若阅读量将显著超出方案锚点范围，按 `agents/developer-discipline.md` §5 停止并报告。

# 15-fix：2026-07-31-hedge-task-inline-log-v1（修复 dispatch packet，rework 1）

> 修复 review-2 的阻塞发现 R2-F1。**最小改动**，不扩范围。

## Identity

- task_id: 2026-07-31-hedge-task-inline-log-v1-fix-1
- target_role: Implementer（bounded finding repair）
- target_model: `claude_glm`（原实现者；§3 #6「原实现者以最小改动修复明确发现」）
- provider: `zhipu_glm`
- status_revision: 12
- required_skill: `agents/skills/minimal-change-engineer.md`
  （**不要**加载 `senior-developer.md`——本轮是定界修复，不是实现）
- rework_count: **1**（本轮递增）

## Goal

修复 R2-F1：日志表的「成交时间」列展示的不是成交时间，而是 attempt 的**创建时间**
（下单前预留那一刻）。列头是对用户的断言，该断言不成立——用户会据此判断"钱是这一刻
出去的"。

### 已核实的根因（不要重新调查）

- 该列取 `attempt.ts` = `attempt_to_doc` 的
  `D.us_to_iso(attempt.get("created_at_us"))`（`service.py:270`）。
- `created_at_us` 在 `prepare_attempt` 的**预发送事务**里写入，早于两条腿 POST。
- **系统里根本没有成交时间**：attempt 表只有 `created_at_us`（`store.py:79`）；leg 表只有
  `dispatched_at_us`（发出）与 `last_query_at_us`（最后查询）（`store.py:97-98`）；
  交易所的 `transactTime` / `updateTime` 从未落库。

因此本轮**不可能**显示真正的成交时间——记录成交时间需要 schema + 写路径改动，超出本
stage「只动读路径」的边界，已另记为 follow-up。本轮的正确修复是**让列头说实话**。

### 钉死的修法

1. **列头由「成交时间」改为「尝试时间」**（`index.html` 表头 `<th>成交时间</th>`）。
2. **去掉该列的 `order_id` 门控**：`hedgeLogTimeCell`（`index.html:4276`）当前要求「至少
   一腿已受理」才显示时间，否则 `—`。该门控是为「成交时间」这个语义设的（避免给未成交行
   挂时间被读成已成交）。列头改为「尝试时间」后该顾虑消失，且**每一行都真实存在一个
   尝试时间**——包括失败行、进行中行。改为：`attempt.ts` 有值就显示，无值才 `—`。
3. **不要**改后端投影、不要新增字段、不要改 `attempt_to_doc`、不要碰写路径。
4. 同步更新 `frontend/self-check.js` 中受影响的断言与注释；同步更新
   `frontend/index.html` 里描述该列的注释（现注释写「成交时间：仅当至少一腿已受理…」）。

## Allowed Files

- `frontend/index.html`（表头文案、`hedgeLogTimeCell`、相关注释）
- `frontend/self-check.js`（受影响的断言与注释）
- `reports/agent-runs/2026-07-31-hedge-task-inline-log-v1/`（修复报告）

**不得**改动 `backend/` 下任何文件。后端投影不变即为本轮的正确性边界之一。

## Inputs

- review-2 verdict 与 Bookkeeper 核实：同目录 `14-review-2-verdict.md`（**必读**）。
- 原 packet：同目录 `00-task.md`（`status_revision: 9`）。
- 原交付自述：同目录 `09-delivery.md`（其中「成交时间门控」一节即本轮被推翻的决策）。
- 受审基线：`delivery_sha = b14f55ce8c264635860bd5b54d61229b17bd9faa`（在此之上修复）。

## Acceptance Checks

1. **列头已改**：日志表第三列表头为「尝试时间」，全文再无「成交时间」字样（给出全量
   搜索证据）。
2. **所有行都显示时间**：构造四种状态（进行中 / 已受理 / 已确认失败 / 单腿成交）的用例，
   断言**每一行**都显示该次尝试的时间（北京时间格式），不再因两腿都无 `order_id` 而
   显示 `—`。仅当 `attempt.ts` 本身缺失时才 `—`。
3. **后端零改动**：`git diff --name-only` 证明 `backend/` 下无任何文件被修改。
4. **回归**：`node frontend/self-check.js` 全过；`python3 -m pytest backend/tests -q` 全过
   （贴原始输出）。既有用例不应有任何一条因本次改动转红——若有，说明改超了范围，停下回报。
5. **改动量**：`git diff --stat` 应显示这是一次很小的改动（量级：十几行）。若你发现自己
   在改几十行以上，停下回报——那说明理解偏了。

## Stop

- 不改后端任何文件；不新增字段、不碰 schema、不碰写路径。
- 不做「记录真实成交时间」的实现——那需要 schema + 写路径，已另记 follow-up，超本 stage 边界。
- 不顺手改其它列、不重构日志表、不动状态映射/门控之外的任何逻辑。
- 不扩 scope：不碰「任务卡卡住」、不碰持仓聚合、不碰均价数据源。
- 不合并、不推送、不启动评审终端。自测完成后停下回报给 bookkeeper（opus5）。

Identity:
- task_id: `backend-position-balance-display-v1`
- target_role: `Implementer`
- target_model: `claude_glm`
- provider: `zhipu_glm`
- status_revision: `9`
- required_skill: `agents/skills/senior-developer.md`

Goal

实现 v4.1 §9.2 的最小后端交付：在既有纯函数 `merge_positions` 生成的每一个 position row 增加 `spot_balance_value_usdt`、`unified_balance`、`unified_balance_value_usdt`，并保持既有 `spot_balance` 语义。四字段只消费同一已发布 `private_account` 的标准化 `balances_spot` / `balances_unified` row；更新 hedge positions API 契约与离线测试。不接前端、不改 snapshot schema、cache refresh、60 秒调度、PrivateClient、订单、借贷写入、Start gate、凭证或部署。

字段事实固定如下：`spot_balance` 仍是 `free + locked`；`spot_balance_value_usdt` 是同一 spot row 的既有 `value_usdt`；`unified_balance` 是同一 asset 的 `balances_unified.total_balance`；`unified_balance_value_usdt` 是同一 unified row 的既有 `value_usdt`。`cross_margin_borrowed` 继续只代表借款，不可当成统一账户余额。账户未就绪时所有账户派生字段为 null；一侧 asset 缺失时只该侧 amount/value 为 null；真 0 保持可区分的十进制字符串。不得改变 1000x asset 不自动对齐的既有规则或重算 USDT 估值。

Allowed Files

- `backend/hedge_open_tasks/domain.py`
- `backend/tests/test_positions_merge.py`
- `backend/tests/test_hedge_api.py`
- `docs/api/public-market-contract.md`
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/backend-position-balance-display-v1.handoff.md`（create-only；Bookkeeper 已执行 `test ! -e`，结果为通过；按 `agents/roles.md` 的 Task Handoff Evidence Contract 创建唯一交接件）
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/backend-position-balance-display-v1.pytest.txt`（测试原始输出）
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/status.json`（仅可将本任务 `current_task.state` 从 `dispatched` 改为 `reported`；不得改动任何其他字段）

Inputs

- `AGENTS.md`
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/backend-position-balance-display-v1.dispatch.md`
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/status.json`
- `agents/roles.md` 的 Implementer 与 Task Handoff Evidence Contract 章节
- `agents/developer-discipline.md`
- `agents/skills/senior-developer.md`
- `docs/planning/hedge-status-account-refresh-v4.md`（§9）
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/plan-review-position-balance-display-v1-deepseek.handoff.md`
- `backend/hedge_open_tasks/domain.py`、`backend/tests/test_positions_merge.py`、`backend/tests/test_hedge_api.py`、`docs/api/public-market-contract.md`

Acceptance Checks

1. `merge_positions` 的正常同币 row 精确映射普通现货 amount/value 与统一账户 amount/value；不重算价格、不修改源 snapshot，`cross_margin_borrowed` 语义不变。
2. 所有 merged row 均有四个账户字段；未就绪全 null、单侧 asset 缺失只该侧 amount/value null、真 0 不退化为 null，且 1000x asset 不自动与普通 asset 对齐。
3. `/api/hedge-open-positions` 的 exact position key set 同步三字段新增；GET 仍仅从已有 published snapshot 和本地 task bucket 合并，零上游 I/O。
4. `docs/api/public-market-contract.md` 追加 v0.11 positions projection 字段、来源与 null/真零语义；不修改 snapshot JSON schema。
5. 离线运行并保存 `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider -q backend/tests/test_positions_merge.py backend/tests/test_hedge_api.py`；不得启动服务、访问网络、读取凭证或实盘操作。

Stop

只在 Allowed Files 内修改。创建 handoff 后用其 Human Brief 生成合规 `[TASK_RESULT v2]`；将本任务状态标为 `reported`。在一个 delivery commit 中提交允许的代码、契约、测试、测试输出、status 与 handoff；handoff 的 `delivery_sha` 写 `pending`。不要自行启动 Frontend Implementer、Reviewer、Bookkeeper、部署或实盘/网络操作。

Identity
- task_id: implement-cross-margin-capital-flow-v1
- target_role: Implementer
- target_model: claude_glm
- provider: zhipu_glm
- status_revision: 3
- required_skill: agents/skills/senior-developer.md

Goal
- 按改写后的 `00-change-plan.md` 接入 `GET /sapi/v1/margin/capital-flow` 全仓本地缓存，并在流水日志中栏用真数据替换假数据预览。
- 严格遵守隔离：新表 + ledger_meta 新 key；不写 flow_refresh_runs；不进 coverage aggregate / delta / success / last_run；coverage_for_window 与对冲净盈亏语义不变。
- 首次落档最近 1 天，之后 [coverage_end-3h, now] 增量；单页 limit=1000；满 1000 标记可能不全；无 fromId 翻页、无 7 天切片。
- 自测、提交、写 handoff 后停止。

Allowed Files
- Bookkeeper preflight：`test ! -e reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/evidence/implement-cross-margin-capital-flow-v1.handoff.md` → 结果：absent；该路径为 create-only，由本任务唯一创建，已存在即任务失败。
- `backend/services/private_client.py`
- `backend/ledger_flow/domain.py`
- `backend/ledger_flow/store.py`
- `backend/ledger_flow/service.py`
- `backend/ledger_flow/scheduler.py`（仅当必须挂钩时机且不改两源成功语义；优先只改 service）
- `backend/tests/test_ledger_flow_domain.py`
- `backend/tests/test_ledger_flow_store.py`
- `backend/tests/test_ledger_flow_service.py`
- `backend/tests/test_ledger_flow_scheduler.py`
- `backend/tests/test_ledger_flow_api.py`
- `backend/tests/test_private_client.py`（白名单相关）
- 可新增：`backend/tests/test_ledger_flow_capital.py`
- `frontend/index.html`
- `frontend/self-check.js`
- `docs/api/public-market-contract.md`（private-ledger additive，不 bump schema_version）
- create-only handoff：`reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/evidence/implement-cross-margin-capital-flow-v1.handoff.md`
- `backend/app/server.py` 为**只读输入**（见 Inputs 15），不在可写清单：`capital_flow` 块在 service 层装配，`_handle_flow_log` 原样转发即可；该文件含 P0-1 要保护的 `coverage_for_window` 消费点。确需改动即停止并报 blocker，由 Human 单独授权。
- 禁止：改 `flow_refresh_runs` schema、改既有两源 coverage 聚合公式、接入 asset/transfer、分页 UI、部署/重启/实盘写、改资产互转 POST。
- 禁止：对 `data/*.sqlite3` 执行任何写操作或迁移演练。现网 `data/ledger-flow.sqlite3` 含真实账本（利息 279 行 / 合约 196 行 / 运行记录 130 行）；建表与入库验证一律使用临时库（`LedgerStore` 的 `db_path` 本就是注入参数）。

Inputs
1. `AGENTS.md`
2. `reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/02-implement-capital-flow.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/status.json`
6. `agents/roles.md`（Implementer + Shared Rules + Task Handoff Evidence Contract）
7. `agents/developer-discipline.md`
8. `agents/skills/senior-developer.md`
9. `reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/00-change-plan.md`（**唯一计划权威**；冻结项以其 §9 核对表为准，dispatch 不另存副本）
10. `reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/evidence/cross-margin-flow-log-plan-review.handoff.md`
11. `reports/api-samples/2026-08-margin-account-flow-recon-v1/20260810T062742Z/recon.md`
12. `reports/api-samples/2026-08-margin-account-flow-recon-v1/20260810T062742Z/sanitized/endpoint-shape-for-design.json`
13. `backend/ledger_flow/service.py` / `store.py` / `domain.py` / `scheduler.py`
14. `backend/services/private_client.py`
15. `backend/app/server.py`（coverage_for_window 消费点）
16. `frontend/index.html` / `frontend/self-check.js`（基线三栏 DOM id 必须沿用）

Acceptance Checks
1. 白名单 + 单页 fetch；mock 测 limit=1000 边界与满页标记。
2. 新表入库幂等（同 id 不覆盖乱改）；同 tran_id 多 type 多行保留。
3. ledger_meta 三 key 推进正确；失败不推进 end（或符合计划冻结语义并测到）。
4. flow-log JSON 含 capital_flow；缺块时前端空态；schema_version 仍为 private-ledger/v2。
5. 回归：既有 ledger_flow 测试 + 对冲 stats 依赖 coverage 的路径不因 capital 失败/空而变「暂无」。
6. 前端：去掉预览徽标与 FAKE_ROWS；真数据渲染；筛选桶与「入全仓/出全仓」保留；self-check 全绿。
7. 文档 public-market-contract private-ledger 段 additive 更新。
8. 创建唯一 handoff。顺序为「实现 → 自测 → 提交 → 写 handoff」，因此 `delivery_sha` 直接填提交后的实际 `git rev-parse` 值（非 `pending`）。作者区块（Source Report / Human Brief）提交后不可改写，不得由任何人回填；Bookkeeper 在其核验块独立解析并写入 `status.json`。
9. 自测命令（原始输出全部写入 handoff，不得以叙述替代）：
   - `.venv/bin/python -m pytest backend/tests/test_ledger_flow_domain.py backend/tests/test_ledger_flow_store.py backend/tests/test_ledger_flow_service.py backend/tests/test_ledger_flow_scheduler.py backend/tests/test_ledger_flow_api.py backend/tests/test_private_client.py -q`
   - 全量回归：`.venv/bin/python -m pytest backend/tests/ -q`
   - 前端：`node frontend/self-check.js`

Stop
- 实现、自测、提交、写 handoff、控制台 TASK_RESULT 后停止。
- 不启动 review、不 merge、不 push（除非 Human 另令）、不部署、不重启服务、不实盘写。

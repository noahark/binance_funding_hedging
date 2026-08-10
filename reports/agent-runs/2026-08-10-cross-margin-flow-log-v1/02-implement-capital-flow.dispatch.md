Identity
- task_id: implement-cross-margin-capital-flow-v1
- target_role: Implementer
- target_model: claude_glm
- provider: zhipu_glm
- status_revision: 2
- required_skill: agents/skills/senior-developer.md

Goal
- 按改写后的 `00-change-plan.md` 接入 `GET /sapi/v1/margin/capital-flow` 全仓本地缓存，并在流水日志中栏用真数据替换假数据预览。
- 严格遵守隔离：新表 + ledger_meta 新 key；不写 flow_refresh_runs；不进 coverage aggregate / delta / success / last_run；coverage_for_window 与对冲净盈亏语义不变。
- 首次落档最近 1 天，之后 [coverage_end-3h, now] 增量；单页 limit=1000；满 1000 标记可能不全；无 fromId 翻页、无 7 天切片。
- 自测、提交、写 handoff 后停止。

Allowed Files
- `backend/services/private_client.py`
- `backend/ledger_flow/domain.py`
- `backend/ledger_flow/store.py`
- `backend/ledger_flow/service.py`
- `backend/ledger_flow/scheduler.py`（仅当必须挂钩时机且不改两源成功语义；优先只改 service）
- `backend/app/server.py`（仅 flow-log 装配 / 若 coverage 路径被误伤的防护测试需要只读对照）
- `backend/tests/test_ledger_flow_domain.py`
- `backend/tests/test_ledger_flow_store.py`
- `backend/tests/test_ledger_flow_service.py`
- `backend/tests/test_ledger_flow_api.py`（若存在；否则可新增 `backend/tests/test_ledger_flow_capital.py`）
- `backend/tests/test_private_client.py`（白名单相关）
- `frontend/index.html`
- `frontend/self-check.js`
- `docs/api/public-market-contract.md`（private-ledger additive，不 bump schema_version）
- create-only handoff：`reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/evidence/implement-cross-margin-capital-flow-v1.handoff.md`
- 禁止：改 `flow_refresh_runs` schema、改既有两源 coverage 聚合公式、接入 asset/transfer、分页 UI、部署/重启/实盘写、改资产互转 POST。

Inputs
1. `AGENTS.md`
2. `reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/02-implement-capital-flow.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/status.json`
6. `agents/roles.md`（Implementer + Shared Rules + Task Handoff Evidence Contract）
7. `agents/developer-discipline.md`
8. `agents/skills/senior-developer.md`
9. `reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/00-change-plan.md`（**唯一计划权威**）
10. `reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/evidence/cross-margin-flow-log-plan-review.handoff.md`
11. `reports/api-samples/2026-08-margin-account-flow-recon-v1/20260810T062742Z/recon.md`
12. `reports/api-samples/2026-08-margin-account-flow-recon-v1/20260810T062742Z/sanitized/endpoint-shape-for-design.json`
13. `backend/ledger_flow/service.py` / `store.py` / `domain.py` / `scheduler.py`
14. `backend/services/private_client.py`
15. `backend/app/server.py`（coverage_for_window 消费点）
16. `frontend/index.html` / `frontend/self-check.js`（基线三栏 DOM id 必须沿用）

Bookkeeper freeze checklist（改写计划已核对，实现不得回退）
1. §1 历史 1 天 + 小时增量 + 前端基线已提交
2. §3 TRADING_COMMISSION ∈ TRADE 默认关
3. §4.1.2 无切片、limit=1000、满页标记可能不全
4. §4.1.3 新表零迁移、主键 id、无 first_seen_run_id
5. 缺 capital_flow 块 → 中栏空态；schema_version=private-ledger/v2 不 bump
6. 不写 flow_refresh_runs；不进 aggregate/delta/success/last_run
7. 不做分页 / 不 30·90 天回补
8. capital 失败不影响利息/合约 run
9. coverage_for_window complete 在 capital 从未成功时与接入前一致
10. 中栏口径：全仓钱包视角，非全部互转全集

Acceptance Checks
1. 白名单 + 单页 fetch；mock 测 limit=1000 边界与满页标记。
2. 新表入库幂等（同 id 不覆盖乱改）；同 tran_id 多 type 多行保留。
3. ledger_meta 三 key 推进正确；失败不推进 end（或符合计划冻结语义并测到）。
4. flow-log JSON 含 capital_flow；缺块时前端空态；schema_version 仍为 private-ledger/v2。
5. 回归：既有 ledger_flow 测试 + 对冲 stats 依赖 coverage 的路径不因 capital 失败/空而变「暂无」。
6. 前端：去掉预览徽标与 FAKE_ROWS；真数据渲染；筛选桶与「入全仓/出全仓」保留；self-check 全绿。
7. 文档 public-market-contract private-ledger 段 additive 更新。
8. 创建唯一 handoff；delivery_sha 按契约（实现提交后可 pending→实 SHA）。

Stop
- 实现、自测、提交、写 handoff、控制台 TASK_RESULT 后停止。
- 不启动 review、不 merge、不 push（除非 Human 另令）、不部署、不重启服务、不实盘写。

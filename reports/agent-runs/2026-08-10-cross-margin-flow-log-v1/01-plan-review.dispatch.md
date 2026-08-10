Identity
- task_id: cross-margin-flow-log-plan-review
- target_role: Reviewer（独立高风险计划评审）
- target_model: opus5
- provider: anthropic
- status_revision: 1
- required_skill: agents/skills/software-architect.md

Goal
- 只读评审 `00-change-plan.md`：全仓杠杆流水本地缓存 + 流水日志中栏展示是否最小、可验证、与现有 dual-ledger 可共存。
- 核对数据源选择（capital-flow 全仓、拒绝 marginAccountFlow）、幂等键、≤7 天切片、权重与小时 cadence、三栏 UI 默认筛选与 TRANSFER 符号语义。
- 返回明确 `ACCEPT` 或 `REWORK`；`REWORK` 须附代码/recon 证据与可直接改写计划的条文。

Allowed Files
- 只允许新建：`reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/evidence/cross-margin-flow-log-plan-review.handoff.md`。
- Bookkeeper preflight：`test ! -e reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/evidence/cross-margin-flow-log-plan-review.handoff.md`。
- 除上述 create-only handoff 外仓库完全只读。

Inputs
1. `AGENTS.md`
2. `reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/01-plan-review.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/status.json`
6. `agents/roles.md`（Shared Rules、Task Handoff Evidence Contract、Reviewer）
7. `agents/skills/software-architect.md`
8. `reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/00-change-plan.md`
9. `reports/api-samples/2026-08-margin-account-flow-recon-v1/20260810T062742Z/recon.md`
10. `reports/api-samples/2026-08-margin-account-flow-recon-v1/20260810T062742Z/sanitized/endpoint-shape-for-design.json`
11. `docs/planning/2026-08-04-dual-ledger-flow-log-design.md`（对照 cadence/coverage）
12. `backend/ledger_flow/service.py`
13. `backend/ledger_flow/store.py`
14. `backend/ledger_flow/scheduler.py`
15. `backend/ledger_flow/domain.py`
16. `backend/services/private_client.py`
17. `frontend/index.html`（流水日志三栏将扩展的现有双栏）
18. `docs/api/public-market-contract.md`（private-ledger 章节）

Acceptance Checks
1. 明确判断 capital-flow 是否足以支撑中栏与互转可见性；是否必须同 stage 接入 asset/transfer。
2. 明确判断幂等键（禁止单靠 tranId）与多 type 同行是否被计划覆盖。
3. 明确判断 7 天切片 + 小时调度 + 权重 100 是否与现有 ledger scheduler 可合并或须独立 run kind。
4. 明确判断 flow-log API additive 形状是否破坏旧客户端/self-check。
5. 新假设场景仅当满足 AGENTS.md §1 Scenario Admission 才能阻塞。
6. 创建唯一 handoff；Source Report、Human Brief、marker、delivery_sha=`none`、评审结论字段合规。

Stop
- 完成只读计划评审、创建唯一 handoff、输出同源控制台回执后停止。
- 不实现、不改计划、不提交、不启动实现模型、不创建后续 dispatch、不 merge、不 push、不部署、不读写 live DB 以外的只读证据路径、不读取凭证明文。

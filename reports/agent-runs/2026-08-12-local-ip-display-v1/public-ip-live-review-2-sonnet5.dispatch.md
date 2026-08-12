# 真实公网出口 IP：正式评审 2 dispatch — Sonnet 5

## Identity

- task_id: `public-ip-live-review-2-sonnet5`
- target_role: `Reviewer / Review-2`
- target_model: `sonnet5 / Claude Sonnet 5（fresh independent read-only session）`
- provider: `anthropic`
- status_revision: `13`
- required_skill: `agents/skills/reality-checker.md`

## Goal

对固定范围 `54b23cc904b9785e77f7f984f7bbdd4972de2f44..f2ad1bfba56ec3f9822a4308c61e4ae1e27dc4dc`
进行独立、只读的 Review-2：判断用户实际需求、交付效果、运行与操作边界、证据充分性及发布就绪性。
该值只展示后端进程观察到的公网出口 IP，供 Human 核对白名单；它绝不能被表述为币安实际观察到的
IP，也不能驱动白名单、交易、资金路径、风险或 live gate。Review-1 已 ACCEPT；它的 O-1..O-4
是带重开条件的非阻塞观察，需确认其分类和边界是否与实际交付一致，但不要把未满足 §1 的新假设
升级成阻塞项。

本交付按 `HIGH_RISK` controlling-contract 路线审查。当前手动前台进程尚未重启／部署，禁止以 Git
提交或本地页面推断其已经加载，也禁止任何服务控制、真实公网查询、币安访问、凭据或 live DB 操作。

## Allowed Files

- `reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-live-review-2-sonnet5.handoff.md`（唯一新建、create-only）

开始前 handoff 路径必须不存在；若已存在即停止报告：
`reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-live-review-2-sonnet5.handoff.md`。
Bookkeeper 预检：`test ! -e reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-live-review-2-sonnet5.handoff.md` → `ABSENT`（2026-08-12 21:32 CST）。

## Inputs

按以下顺序读取：

1. `AGENTS.md`
2. 本 dispatch：`reports/agent-runs/2026-08-12-local-ip-display-v1/public-ip-live-review-2-sonnet5.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-12-local-ip-display-v1/status.json`
6. `agents/roles.md` 的 `Shared Rules`、`Task Handoff Evidence Contract` 与 `Reviewer` 小节
7. `agents/skills/reality-checker.md`
8. 已接受计划及计划复审：`reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-live-plan.md`、`reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-live-plan-review-claude-r2.handoff.md`
9. 实现、修复与 Review-1 交接（按顺序）：`reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-backend-claude-glm.handoff.md`、`reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-frontend-kimi.handoff.md`、`reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-frontend-kimi-status-scope-fix.handoff.md`、`reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-live-review-1-claude.handoff.md`
10. 原始测试证据与契约：`reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-backend-claude-glm-pytest.txt`、`reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-frontend-kimi-self-check.txt`、`docs/api/public-market-contract.md`
11. 受审代码：`backend/services/public_ip_service.py`、`backend/app/server.py`、`frontend/index.html`、`frontend/self-check.js`

## Acceptance Checks

1. 只使用 `git diff 54b23cc904b9785e77f7f984f7bbdd4972de2f44..f2ad1bfba56ec3f9822a4308c61e4ae1e27dc4dc` 及固定提交证据，不使用移动 HEAD 或未提交工作区；明确将阶段控制提交与产品交付分开。
2. 从用户视角核对：标题右侧的三态内容诚实、不出现 fake IP、失败不宣称成功、不阻塞行情／交易相关控件；只读端点的缓存／主备／失败行为与“仅供核对”边界相符。
3. 从运行与操作视角核对：不推断当前服务已加载，不把值当币安权威，不改变白名单或 live 行为；明确 Review 通过不等于部署或运行时验证。审视 Review-1 O-1..O-4，确认其仍是带重开条件的非阻塞观察或按现有证据给出必要升级理由。
4. 核对原始测试、Review-1 复跑结论和文档契约是否足以支持上述发布前结论；可只读复跑已有测试／`git diff --check`，不得发真实网络请求或写入仓库。
5. 只可新建 handoff；不得修改代码、文档、状态、既有证据、PROJECT_STATE，或 commit／push／merge。必须产生完整 `TASK_RESULT v2` 和明确 `评审结论`：`ACCEPT` 或带范围三分类、证据和可执行要求的 `REWORK`。

## Stop

完成后停止，不得合并、部署或触发任何 live 动作。控制台以 `AGENTS.md` §7 的 `[TASK_RESULT v2]` 收尾，并包含 `评审结论`、`问题记录`、`修复要求`；`下一步模型` 写 `codex / GPT-5（Bookkeeper）`，`下一步任务` 必须为：`读取：reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-live-review-2-sonnet5.handoff.md；执行：Bookkeeper 核验 Review-2 结论并向 Human 报告；关卡：ACCEPT 后由 Human 决定是否合并、部署或保持未启用，REWORK 后准备最小修复`。

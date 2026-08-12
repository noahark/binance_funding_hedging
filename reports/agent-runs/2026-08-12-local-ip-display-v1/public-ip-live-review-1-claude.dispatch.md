# 真实公网出口 IP：正式评审 1 dispatch — Claude

## Identity

- task_id: `public-ip-live-review-1-claude`
- target_role: `Reviewer / Review-1`
- target_model: `claude / Claude Code（fresh independent read-only session）`
- provider: `anthropic`
- status_revision: `12`
- required_skill: `agents/skills/code-reviewer.md`

## Goal

对固定交付范围 `54b23cc904b9785e77f7f984f7bbdd4972de2f44..f2ad1bfba56ec3f9822a4308c61e4ae1e27dc4dc`
进行独立、只读的 Review-1。交付新增后端进程观察公网出口 IP 的只读同源端点，以及标题右侧
三态展示；它引入 API 契约和外部 HTTPS 读取，按 `HIGH_RISK` 的 controlling-contract 路线，
须先通过本轮 Review-1，再进入独立 Review-2。

审查代码正确性、端点契约、前后端接线、缓存／异常边界、测试与文档。`13acc93`、`b373e98`、
`c010fa6`、`f2ad1bf` 是阶段控制／交接提交，只作上下文；不要把它们当产品交付发现。不得基于
仓库提交宣称当前手动前台进程已经加载代码；不得把显示值当作币安观察到的 IP，或建议／执行白名单
变更。不得启动服务、部署、发真实公网请求、访问币安、凭据或 live DB。

## Allowed Files

- `reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-live-review-1-claude.handoff.md`（唯一新建、create-only）

开始前 handoff 路径必须不存在；若已存在即停止报告：
`reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-live-review-1-claude.handoff.md`。
Bookkeeper 预检：`test ! -e reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-live-review-1-claude.handoff.md` → `ABSENT`（2026-08-12 21:07 CST）。

## Inputs

按以下顺序读取：

1. `AGENTS.md`
2. 本 dispatch：`reports/agent-runs/2026-08-12-local-ip-display-v1/public-ip-live-review-1-claude.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-12-local-ip-display-v1/status.json`
6. `agents/roles.md` 的 `Shared Rules`、`Task Handoff Evidence Contract` 与 `Reviewer` 小节
7. `agents/skills/code-reviewer.md`
8. 已接受计划与计划复审：`reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-live-plan.md`、`reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-live-plan-review-claude-r2.handoff.md`
9. 已核验实现与修复交接（按顺序）：`reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-backend-claude-glm.handoff.md`、`reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-frontend-kimi.handoff.md`、`reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-frontend-kimi-status-scope-fix.handoff.md`
10. 原始测试证据：`reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-backend-claude-glm-pytest.txt`、`reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-frontend-kimi-self-check.txt`
11. 受审产品文件：`backend/services/public_ip_service.py`、`backend/app/server.py`、`backend/tests/test_public_ip_api.py`、`frontend/index.html`、`frontend/self-check.js`、`docs/api/public-market-contract.md`

## Acceptance Checks

1. 用固定 SHA 审查：`git diff 54b23cc904b9785e77f7f984f7bbdd4972de2f44..f2ad1bfba56ec3f9822a4308c61e4ae1e27dc4dc`，不得使用移动 HEAD 或未提交工作区；明确区分产品文件和阶段控制提交。
2. 核查后端：构造期零 I/O、仅标准库、主备顺序、2 秒／64B 限制、5 分钟成功与失败缓存、`ok/stale/unavailable` 四字段契约、私网拒绝、无异常泄漏、未注入 503、`no-store`，以及 build_server 返回后注入的 seam。
3. 核查前端：仅同源 GET、三态与 malformed／失败降级、不泄露外部服务细节、不阻塞快照／持仓／刷新、无新 timer／localStorage／外域 fetch；页面明示“不能证明币安实际看到的出口 IP”。
4. 检查原始测试证据并可只读执行：后端六文件 pytest 套件、`node frontend/self-check.js`、`git diff --check <fixed-range>`。测试不得改动仓库或发真实网络请求。
5. 只可新建 handoff；不得修改代码、文档、既有证据、status、PROJECT_STATE，或 commit／push／merge。handoff 必须记录固定 base/delivery SHA、审查命令／证据、范围三分类（如有发现）与明确 Review closure。无发现时必须给出 `评审结论: ACCEPT`；发现时必须给出可执行 `REWORK` 修复要求。

## Stop

完成后停止，不得自行准备 Review-2。控制台以 `AGENTS.md` §7 的 `[TASK_RESULT v2]` 收尾，并包含 `评审结论`、`问题记录`、`修复要求`；`下一步模型` 写 `codex / GPT-5（Bookkeeper）`，`下一步任务` 必须为：`读取：reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-live-review-1-claude.handoff.md；执行：Bookkeeper 核验 Review-1 结论；关卡：ACCEPT 后准备独立 Review-2，REWORK 后准备最小修复`。

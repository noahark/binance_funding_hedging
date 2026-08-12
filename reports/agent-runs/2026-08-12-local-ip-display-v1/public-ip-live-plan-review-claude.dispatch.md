# 真实公网出口 IP 展示计划复审 dispatch — Claude / Anthropic

## Identity

- task_id: `public-ip-live-plan-review-claude`
- target_role: `Reviewer / Plan Review`
- target_model: `claude / Anthropic`
- provider: `anthropic`
- status_revision: `5`
- required_skill: `agents/skills/code-reviewer.md`

## Goal

对 Codex/OpenAI 编写的「真实公网出口 IP 展示」计划做独立、只读复审。目标是确认它以最小范围实现 Human 已确认的查看需求：同源页面展示本机后端的公网出口 IP，主源 ipify、备用 AWS checkip、缓存和诚实的失败降级；它绝不读凭据、访问币安、改变资金路径或自动修改 IP 白名单。

这是一份**计划复审**，不是代码交付评审。审阅的固定对象是 committed plan，不得把未提交工作树或移动 HEAD 作为接受依据。

## Allowed Files

Reviewer 除创建以下唯一确定性 handoff 外完全只读：

- `reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-live-plan-review-claude.handoff.md`（create-only）

开始前该路径必须不存在；若已存在则任务失败。Bookkeeper 预检：
`test ! -e reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-live-plan-review-claude.handoff.md` → `ABSENT`（2026-08-12 19:42 CST）。

不得修改计划、产品代码、测试、文档、任何状态文件或既有证据；不得 commit、merge、push、部署、重启/控制服务、读取凭据、访问 live DB 或发起交易所/公网 IP 查询。

## Inputs

按以下顺序读取：

1. `AGENTS.md`
2. 本 dispatch：`reports/agent-runs/2026-08-12-local-ip-display-v1/public-ip-live-plan-review-claude.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-12-local-ip-display-v1/status.json`
6. `agents/roles.md` 的 `Shared Rules`、`Task Handoff Evidence Contract` 与 `Reviewer` 小节
7. `agents/skills/code-reviewer.md`
8. 被审计划：`reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-live-plan.md`
9. 当前相关实现与测试边界：`backend/app/server.py`、`frontend/index.html`、`frontend/self-check.js`、`backend/tests/test_max_withdraw_api.py`
10. 活 API 权威：`docs/api/public-market-contract.md`
11. 固定 `base_sha..delivery_sha` diff。

## Fixed Review Range

- base_sha: `983e900fc4af257c834774d0eb1bdc5dc2e111b7`
- delivery_sha: `2625cf3a532f25d92a5f660aa2b845a6eaaaf009`
- 固定命令：`git diff 983e900fc4af257c834774d0eb1bdc5dc2e111b7..2625cf3a532f25d92a5f660aa2b845a6eaaaf009`
- 范围只应含计划文件；没有产品实现。本 stage 更早的静态 fake 提交不是本次计划审阅对象。

计划作者为 Codex / OpenAI；Reviewer 为 Claude / Anthropic，provider 隔离成立。

## Acceptance Checks

1. 固定 SHA 与 status 一致，计划 diff 只包含 `evidence/public-ip-live-plan.md`；不接受移动 HEAD 或未提交文件。
2. 计划明确限定同源只读 `GET /api/system/public-ip`，固定主/备 HTTPS 来源，使用标准库、2 秒 timeout、5 分钟进程内缓存、无新配置/依赖/线程/重试循环。
3. 响应三态与四字段能区分可用、过期上次成功和未知；无地址时不伪造；不得泄漏异常、URL、请求头或凭据。
4. 计划明确：公网 IP 仅供 Human 核对，不能证明币安实际所见出口，且不驱动下单、资金动作、live gate 或白名单变更。
5. 前端复用既有刷新节奏、只请求同源端点；失败不影响行情/持仓/交易控件；无 browser 外域请求、新 timer 或 localStorage。
6. 离线测试可证明 primary/cache、fallback、无效值、未知、stale、未注入 503、HTTP 契约与前端三态；活文档更新范围恰当。
7. 若以新假设阻塞，须遵守 `AGENTS.md` §1 Scenario Admission：给出当前证据锚点、对本计划的具体影响和必须本轮修的原因。

## Stop

完成一次完整复审后，只创建确定性 handoff 并停止。控制台须以 `AGENTS.md` §7 的 review 版 `[TASK_RESULT v2]` 收尾，明确 `评审结论: ACCEPT（接受）` 或 `REWORK（返工）`，并给出 `问题记录` 与 `修复要求`。`下一步模型` 必须为 `codex / GPT-5（Bookkeeper）`；`下一步任务` 必须写：`读取：reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-live-plan-review-claude.handoff.md；执行：Bookkeeper 核验计划复审并向 Human 报告；关卡：ACCEPT 后准备实现 dispatch，REWORK 后由 Planner 修订计划`。

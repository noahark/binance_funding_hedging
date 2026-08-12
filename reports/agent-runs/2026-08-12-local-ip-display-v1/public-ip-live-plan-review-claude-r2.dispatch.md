# 真实公网出口 IP 展示计划复审 R2 dispatch — Claude / Anthropic

## Identity

- task_id: `public-ip-live-plan-review-claude-r2`
- target_role: `Reviewer / Plan Review`
- target_model: `claude / Anthropic`
- provider: `anthropic`
- status_revision: `7`
- required_skill: `agents/skills/code-reviewer.md`

## Goal

对 Codex/OpenAI 依照 Claude R1 `REWORK` 修订后的「真实公网出口 IP 展示」计划作第二次独立只读复审。核验 R1 的两条必修是否被计划文字精确收编：

1. `build_server()` 只复位 `_Handler.public_ip_service`，不新增参数；`run()` 保持既有两参数调用，并只在返回后创建/赋值服务。
2. 验收显式覆盖所有受影响的既有 server 装配测试。

同时复核本次一并采纳的非阻塞项：IP 加载不阻塞市场主链、失败缓存 TTL 有测试、外部响应体限长。审阅仍须确认真实 IP 只供 Human 核对，不访问凭据、币安、资金路径、gate 或白名单。

## Allowed Files

Reviewer 除创建以下唯一确定性 handoff 外完全只读：

- `reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-live-plan-review-claude-r2.handoff.md`（create-only）

开始前该路径必须不存在；若已存在则任务失败。Bookkeeper 预检：
`test ! -e reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-live-plan-review-claude-r2.handoff.md` → `ABSENT`（2026-08-12 20:02 CST）。

不得修改计划、产品代码、测试、文档、任何状态文件或既有证据；不得 commit、merge、push、部署、重启/控制服务、读取凭据、访问 live DB 或发起交易所/公网 IP 查询。

## Inputs

按以下顺序读取：

1. `AGENTS.md`
2. 本 dispatch：`reports/agent-runs/2026-08-12-local-ip-display-v1/public-ip-live-plan-review-claude-r2.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-12-local-ip-display-v1/status.json`
6. `agents/roles.md` 的 `Shared Rules`、`Task Handoff Evidence Contract` 与 `Reviewer` 小节
7. `agents/skills/code-reviewer.md`
8. R1 复审记录：`reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-live-plan-review-claude.handoff.md`
9. 被审修订计划：`reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-live-plan.md`
10. 当前相关 seam 与测试：`backend/app/server.py`、`backend/tests/test_service_health.py`、`backend/tests/test_max_withdraw_api.py`、`backend/tests/test_ledger_flow_api.py`、`backend/tests/test_asset_transfer.py`、`backend/tests/test_margin_repay.py`
11. 活 API 权威：`docs/api/public-market-contract.md`
12. 固定 `base_sha..delivery_sha` diff。

## Fixed Review Range

- base_sha: `90bcaae72a17de358e9edbfd9cf337136acf4b57`
- delivery_sha: `fefc8aac46e7dbc9a1e20467625288e9aa70ac48`
- 固定命令：`git diff 90bcaae72a17de358e9edbfd9cf337136acf4b57..fefc8aac46e7dbc9a1e20467625288e9aa70ac48`
- 范围只应含 `evidence/public-ip-live-plan.md` 的计划修订；没有产品实现。任何 control 提交或移动 HEAD 都不是审阅对象。

计划作者为 Codex / OpenAI；Reviewer 为 Claude / Anthropic，provider 隔离成立。Claude 参与 R1 复审已披露：R2 必须从本次固定 diff 与原始 seam 重新判断，R1 结论不替代 R2 verdict。

## Acceptance Checks

1. 固定 SHA 与 status 一致，diff 只含计划文件；不接受移动 HEAD 或未提交文件。
2. R1 注入约束被逐字钉死：`build_server` 不增参数且复位服务；`run()` 保留两参数调用、只在返回后创建并注入。计划不得留下会导致既有两参数 stub `TypeError` 或生产永久 503 的解释空间。
3. R1 测试范围被完整收编：新 public-IP 测试和 `test_service_health.py`、`test_max_withdraw_api.py`、`test_ledger_flow_api.py`、`test_asset_transfer.py`、`test_margin_repay.py` 均在必跑命令中。
4. R3/R4/R5(a) 均有可执行约束和测试：前端 IP 加载不 await 主链且自行降级；失败缓存 TTL 有零重复外呼测试；每个外部响应体至多读取 64 字节。
5. 原计划的同源端点、三态、固定主备 HTTPS 源、2 秒 timeout、5 分钟缓存、无依赖/配置/线程/浏览器外域请求，以及仅供核对的边界仍完整成立。
6. 若以新假设阻塞，须遵守 `AGENTS.md` §1 Scenario Admission，提供当前证据锚点、具体影响和本轮必须修订的原因。

## Stop

完成一次完整复审后，只创建确定性 handoff 并停止。控制台须以 `AGENTS.md` §7 的 review 版 `[TASK_RESULT v2]` 收尾，明确 `评审结论: ACCEPT（接受）` 或 `REWORK（返工）`，并给出 `问题记录` 与 `修复要求`。`下一步模型` 必须为 `codex / GPT-5（Bookkeeper）`；`下一步任务` 必须写：`读取：reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-live-plan-review-claude-r2.handoff.md；执行：Bookkeeper 核验 R2 计划复审并向 Human 报告；关卡：ACCEPT 后准备实现 dispatch，REWORK 后由 Planner 修订计划`。

# 真实公网出口 IP：后端实现 dispatch — Claude-GLM

## Identity

- task_id: `public-ip-backend-claude-glm`
- target_role: `Implementer / Backend`
- target_model: `claude_glm / GLM-5.2`
- provider: `zhipu_glm`
- status_revision: `8`
- required_skill: `agents/skills/senior-developer.md`

## Goal

实现已通过 Claude R2 计划复审的后端半段：为本机页面提供只读同源
`GET /api/system/public-ip`，以进程内缓存、主源 `api.ipify.org` 和备用
`checkip.amazonaws.com` 返回**后端进程**观察到的公网出口 IP。该值仅供 Human 核对 API
白名单，不得成为币安白名单、交易、借贷、划转、还款、任何 live gate 或风控动作的输入。

本任务只交付后端契约、离线测试和 API 文档。不要修改前端；Kimi 的前端接线任务必须等本交付经
Bookkeeper 核验后才会准备。实现和测试均不得对外发出真实请求——所有测试通过注入 fake 驱动；不得
重启服务，因此当前手动前台进程不会加载本交付。

## Allowed Files

- `backend/services/public_ip_service.py`
- `backend/app/server.py`
- `backend/tests/test_public_ip_api.py`
- `docs/api/public-market-contract.md`
- `reports/agent-runs/2026-08-12-local-ip-display-v1/status.json`（仅将本 task 的 `current_task.state` 从 `dispatched` 改为 `reported`）
- `reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-backend-claude-glm.handoff.md`（唯一新建、create-only）
- `reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-backend-claude-glm-pytest.txt`（本任务的原始 pytest 输出）

开始前 handoff 路径必须不存在；若已存在即停止报告：
`reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-backend-claude-glm.handoff.md`。
Bookkeeper 预检：`test ! -e reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-backend-claude-glm.handoff.md` → `ABSENT`（2026-08-12 20:13 CST）。

## Inputs

按以下顺序读取：

1. `AGENTS.md`
2. 本 dispatch：`reports/agent-runs/2026-08-12-local-ip-display-v1/public-ip-backend-claude-glm.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-12-local-ip-display-v1/status.json`
6. `agents/roles.md` 的 `Shared Rules`、`Task Handoff Evidence Contract` 与 `Implementer` 小节
7. `agents/developer-discipline.md`
8. `agents/skills/senior-developer.md`
9. 通过的计划：`reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-live-plan.md`
10. R2 计划复审：`reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-live-plan-review-claude-r2.handoff.md`
11. 先前 R1 的注入约束：`reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-live-plan-review-claude.handoff.md`
12. 现有 seam/test 范式：`backend/app/server.py`、`backend/tests/test_service_health.py`、`backend/tests/test_max_withdraw_api.py`、`backend/tests/test_ledger_flow_api.py`、`backend/tests/test_asset_transfer.py`、`backend/tests/test_margin_repay.py`
13. 活 API 权威：`docs/api/public-market-contract.md`

## Required Design Constraints

1. 新建单一 `PublicIpService`，只用标准库 `urllib.request`、`ipaddress`、`threading`、`time`；构造期零 I/O，接收可注入 `urlopen` 和单调时钟；无环境变量、依赖、线程、重试循环或持久化。
2. 仅按固定顺序 GET：`https://api.ipify.org?format=json`（JSON 的 `ip`）→ 主源异常、非法 JSON、缺/非字符串 `ip` 或非法 IP 时，才尝试 `https://checkip.amazonaws.com/`（去空白纯文本）。每次只读最多 64 字节、timeout=2 秒、无 body；`ipaddress.ip_address` 必须接受结果（IPv4/IPv6）。不得接受/合成私网替代值，不把异常/URL/请求头暴露给浏览器。
3. 一个实例共享 5 分钟缓存（成功与失败均缓存），以锁串行缓存 miss：同一周期主源最多一次、备用最多一次；曾成功后刷新两源失败返回旧值 `stale`；从未成功的失败返回 `unavailable`。唯一返回形状固定为 `{status, public_ip, source, checked_at}`，`status` 仅 `ok|stale|unavailable`，`checked_at` 为最后成功的 UTC ISO-8601 或 `null`。
4. `GET /api/system/public-ip` 仅返回该服务的规范化 JSON 与 `Cache-Control: no-store`；未注入服务时返回固定 `503 {"error":"public_ip_unavailable"}`，不外呼。不要把该端点并入市场快照。
5. **R1 装配约束，逐字执行：** `build_server()` 不新增参数，并在每次构建时把 `_Handler.public_ip_service = None` 复位。`run()` 保持 `build_server(config, service)` 两参数调用，并且只在它**返回后**创建 `PublicIpService` 和赋给 `_Handler.public_ip_service`，与 `ledger_flow_service` 同一顺序。不得在调用前赋值，也不得传新关键字参数。
6. 文档新增该同源端点的四字段三态、主备源、2 秒 timeout、5 分钟缓存、`no-store`、无真实值时不猜测，以及“仅供 Human 核对，不能证明币安实际看到的出口 IP，绝不驱动白名单或交易”的边界。不要修改 PRD/架构/开发指南。

## Acceptance Checks

1. 离线新测试覆盖：主源成功；5 分钟成功缓存零重复外呼；主源失败/非法值才回退一次备用；无效备用值拒绝；两源首次失败 `unavailable`；两源失败后 5 分钟内零新增外呼；已有成功值后失败 `stale` 且保留最后成功时间；64 字节读取；未注入 HTTP 503；HTTP 200 的精确四字段、三态和 `Cache-Control: no-store`。所有 transport 均为 fake，测试中不得真实联网。
2. 测试明确证明 `build_server` 每次复位 `public_ip_service`；实现遵守 R1 的两参数调用和返回后注入顺序，不破坏既有 `build_server` 调用形状。
3. 执行并保存原始输出：
   ```text
   python3 -m pytest -q backend/tests/test_public_ip_api.py backend/tests/test_service_health.py backend/tests/test_max_withdraw_api.py backend/tests/test_ledger_flow_api.py backend/tests/test_asset_transfer.py backend/tests/test_margin_repay.py
   ```
4. `git diff --check` 通过；只修改 Allowed Files；创建符合 Task Handoff Evidence Contract 的 handoff，更新本 task 到 `reported`，且 handoff/原始输出/状态与本交付在同一提交中。
5. 创建一个仅含本 task Allowed Files 的本地提交；不得 push、merge、部署、重启、控制服务、读取凭据、访问 live DB、访问币安或发出真实公网 IP 查询。

## Stop

完成后停止，不得自行准备 Kimi 前端任务或启动评审。控制台以 `AGENTS.md` §7 的 `[TASK_RESULT v2]` 收尾；`下一步模型` 写 `codex / GPT-5（Bookkeeper）`，`下一步任务` 必须为：`读取：reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-backend-claude-glm.handoff.md；执行：Bookkeeper 核验后端交付并准备依赖此契约的 Kimi 前端任务；关卡：Kimi 前端交付后汇总固定 delivery SHA 进入正式评审`。

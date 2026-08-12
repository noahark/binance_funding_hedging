# Task Handoff: public-ip-backend-claude-glm

## Source Report (author-only; immutable after task end)

- task_id: `public-ip-backend-claude-glm`
- role: `Implementer / Backend`
- target model: `claude_glm / GLM-5.2`（provider `zhipu_glm`）
- stage_id: `2026-08-12-local-ip-display-v1`
- created_at: `2026-08-12 20:34:09 CST`
- base_sha: `54b23cc904b9785e77f7f984f7bbdd4972de2f44`（status.json `base_sha`）
- delivery_sha: `pending`（本交接件先于唯一交付提交创建；提交后由 Bookkeeper 用 `git rev-parse` 落实际值）
- 依据：R2 已 ACCEPT 的计划 `evidence/public-ip-live-plan.md` + 本任务 dispatch + R1 注入约束

### 实际修改范围（全部在 Allowed Files 内）

1. 新建 `backend/services/public_ip_service.py`：单一 `PublicIpService`。
   - 仅用标准库（`urllib.request`、`ipaddress`、`threading`、`time`，外加解析主源 JSON 必需的 `json`、生成 UTC 时间戳的 `datetime`）。构造期零 I/O、零线程，首次 `get()` 惰性外呼。
   - 可注入 `urlopen` 与单调 `clock`（离线测试用）。无环境变量、无依赖、无重试循环、无持久化。
   - 固定顺序 GET：主源 `https://api.ipify.org?format=json`（JSON 的 `ip`）→ 仅当主源异常 / 非 dict / 缺或非字符串 `ip` / 非法或非公网 IP 时，回退一次备用 `https://checkip.amazonaws.com/`（去空白纯文本）。每次 GET、无 body、timeout=2 秒、最多读 64 字节。`ipaddress.ip_address` 必须通过（IPv4/IPv6），并拒绝 `is_private`（含 loopback/link-local/reserved）——门户劫持返回的本地地址不得冒充公网出口 IP。任何异常/URL/请求头都不暴露给调用方（`_fetch` 全 `except Exception -> None`）。
   - 一个实例共享 5 分钟缓存（成功与失败均缓存），`threading.Lock` 串行缓存 miss：同一周期主源最多一次、备用最多一次。成功后刷新失败返回旧值 `stale`（`checked_at` 不前进，保留最后成功时间）；从未成功的失败返回 `unavailable`（不猜测/不合成/不用私网）。返回形状固定 `{status, public_ip, source, checked_at}`，`status ∈ {ok, stale, unavailable}`，`checked_at` 为最后成功 UTC ISO-8601 或 `null`。
2. `backend/app/server.py`（+22 行，六处最小改动）：
   - import `PublicIpService`；`_Handler.public_ip_service = None` 类属性；`do_GET` 增加 `/api/system/public-ip` 路由；新增 `_handle_public_ip`（复用 `_send_ledger`：200 带 `Cache-Control: no-store`，未注入固定 `503 {"error":"public_ip_unavailable"}` 不外呼）；`build_server` 每次复位 `_Handler.public_ip_service = None`；`run()` 在 `build_server(config, service)` **返回后**注入（紧随 `ledger_flow_service` 赋值，同装配顺序）。
   - **R1 装配约束逐字执行**：`build_server()` 不新增参数；`run()` 保持两参数调用；赋值只在 `build_server` 返回后；未传新关键字参数。
3. 新建 `backend/tests/test_public_ip_api.py`：22 项全离线测试（见下）。
4. `docs/api/public-market-contract.md`：追加 v0.19 端点章节（四字段三态、主备源、2s、5min、no-store、不猜测、仅供核对边界），并在 Backend API 路由枚举段补一句。未改 PRD/架构/开发指南。

### 离线测试覆盖（`test_public_ip_api.py`，22 项，全部 fake transport，零联网）

验收#1 逐条：主源成功精确四字段；IPv6 接受；5 分钟成功缓存零重复外呼；TTL 后重取；主源异常/非法 JSON/非字符串 `ip` 各回退一次备用；无效备用值拒绝 → unavailable；私网主源+私网备用 → unavailable；私网主源+公网备用 → ok；两源首次失败 unavailable；两源失败后 5 分钟内零新增外呼（失败缓存）；成功后失败 stale 且 `checked_at` 保留最后成功时间；64 字节读取上限；超长 body 截断 → 非法 JSON → 回退备用；HTTP 200 三态精确四字段 + `Cache-Control: no-store`；未注入 HTTP 503 + 无 no-store；响应不并入快照字段。

验收#2：`test_build_server_resets_public_ip_service_each_call` 证明每次构建复位；`test_run_injects_public_ip_after_build_server` 用真实 `build_server` wrapper（复位真实执行）+ 2 参数形状，证明 `run()` 仅在 `build_server` 返回后注入（R1 读法 B 在本测试下会失败：返回后属性不是 `PublicIpService` 即红）。

### 测试与命令结果

```text
python3 -m pytest -q backend/tests/test_public_ip_api.py backend/tests/test_service_health.py backend/tests/test_max_withdraw_api.py backend/tests/test_ledger_flow_api.py backend/tests/test_asset_transfer.py backend/tests/test_margin_repay.py
=> 168 passed in 70.42s
```

原始输出已落 `reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-backend-claude-glm-pytest.txt`。`git diff --check` 通过。

### 边界与未做事项（与计划/dispatch 一致）

- 未修改前端（`frontend/index.html`、`frontend/self-check.js`）——Kimi 前端接线任务待本交付经 Bookkeeper 核验后才准备。
- 未重启服务、未部署、未合并、未 push、未读取凭据、未访问币安、未发起任何真实公网 IP 查询；当前手动前台进程不会加载本交付。
- 该端点仅供 Human 核对 API 白名单，不能证明币安实际看到的出口 IP（VPN/代理/路由可能不同），绝不驱动白名单或交易。
- 控制区间 `54b23cc..HEAD(13acc93)` 仅含阶段控制文件（R2 handoff、本 dispatch、status.json）；本交付提交将只含上述 Allowed Files。

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-backend-claude-glm.handoff.md`
  2. `reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-backend-claude-glm-pytest.txt`
  3. `backend/services/public_ip_service.py`
  4. `backend/app/server.py`（`_handle_public_ip`、`build_server`、`run()` 注入段、`do_GET` 路由）
  5. `backend/tests/test_public_ip_api.py`
  6. `docs/api/public-market-contract.md`（v0.19 章节与 Backend API 路由枚举段）
- 执行：Bookkeeper 核验后端交付并准备依赖此契约的 Kimi 前端任务
- 关卡：Kimi 前端交付后汇总固定 delivery SHA 进入正式评审
- 不能假设的事实：
  - 不得假设本 stage 代码已被当前手动前台进程加载——未重启、未部署。
  - 不得假设「新测试全绿」等于「共享 server.py 无回归」——dispatch 指定 6 文件须全跑（已跑，168 passed）。
  - 不得把该端点展示的公网 IP 当作币安实际观察到的出口 IP，或据此改动 API 白名单。
  - 前端任务必须等本交付经 Bookkeeper 核验后才准备；共享端点契约不得拆成互相独立的实现提交。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

```text
[TASK_RESULT v2]
任务 ID: public-ip-backend-claude-glm
执行结果: completed（完成）
结果摘要: 实现公网出口 IP 后端半段。新建 PublicIpService（标准库、构造零 I/O、可注入 urlopen/单调时钟、主备源固定顺序、64B/2s、5min 成功+失败缓存、三态四字段、拒私网、不外泄异常）；server.py 同源 GET /api/system/public-ip（no-store；未注入 503 不外呼；R1 返回后注入 + build_server 每次复位）；离线 22 项测试覆盖验收全场景；6 文件套件 168 passed；API 文档 v0.19。未联网/重启/读凭据/部署。
产物: [backend/services/public_ip_service.py, backend/app/server.py, backend/tests/test_public_ip_api.py, docs/api/public-market-contract.md, reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-backend-claude-glm-pytest.txt, reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-backend-claude-glm.handoff.md]
检查结果: [1 新建 PublicIpService 标准库/构造零IO/可注入/主备源顺序/64B·2s/5min成功+失败缓存/三态四字段/拒私网/不外泄异常: pass, 2 server.py 同源 GET /api/system/public-ip + 200 no-store；未注入固定 503 不外呼；不并入快照: pass, 3 R1 装配：build_server 不增参且每次复位、run() 两参数调用且仅返回后注入、无新关键字参数: pass, 4 离线 test_public_ip_api.py 22 项覆盖验收#1 全场景（主源成功/IPv6/成功缓存零重复/TTL重取/主源失败·非法·非串回退一次备用/无效·私网备用拒绝/两源首次失败unavailable/失败缓存零外呼/stale保留最后成功时间/64B·截断回退/未注入503/200三态四字段no-store/不并入快照）: pass, 5 离线测试证明 build_server 每次复位 + run() 仅返回后注入（真实 build_server 复位 wrapper + 2 参数形状，读法B会红）: pass, 6 dispatch 指定 6 文件 pytest 全绿 168 passed，原始输出已落 evidence/public-ip-backend-claude-glm-pytest.txt: pass, 7 git diff --check 通过；仅改 Allowed Files；无新依赖/配置/线程/重试/持久化: pass, 8 API 文档 v0.19 记录端点·四字段三态·主备源·2s·5min·no-store·不猜测·仅供核对边界，未改 PRD/架构/开发指南: pass]
阻塞项: [none]
本地北京时间: 2026-08-12 20:34:09 CST
下一步模型: codex / GPT-5（Bookkeeper）
下一步任务: 读取：reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-backend-claude-glm.handoff.md；执行：Bookkeeper 核验后端交付并准备依赖此契约的 Kimi 前端任务；关卡：Kimi 前端交付后汇总固定 delivery SHA 进入正式评审
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

## Errata (append-only)

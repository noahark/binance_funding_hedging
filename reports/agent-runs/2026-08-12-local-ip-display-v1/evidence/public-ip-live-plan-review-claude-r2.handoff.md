# Task Handoff: public-ip-live-plan-review-claude-r2

## Source Report (author-only; immutable after task end)

- task_id: `public-ip-live-plan-review-claude-r2`
- role: `Reviewer / Plan Review`（只读，创建本交接件为唯一写入）
- target model: `claude / Anthropic`（Opus 5）；被审计划作者 `codex / OpenAI`，provider 隔离成立
- stage_id: `2026-08-12-local-ip-display-v1`
- created_at: `2026-08-12 20:13:03 CST`
- base_sha: `90bcaae72a17de358e9edbfd9cf337136acf4b57`
- delivery_sha: `fefc8aac46e7dbc9a1e20467625288e9aa70ac48`
- 复审对象：`reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-live-plan.md`（修订后）
- 评审结论：**ACCEPT（接受）**

### 参与披露与判断基准

本 reviewer 即 R1 复审作者。按 dispatch 要求，R2 不以 R1 结论替代判断：下述每一条都重新从
本次固定 diff（`git diff 90bcaae..fefc8aa`）与 `backend/app/server.py`、五个既有 server 装配
测试文件的原始代码重新核对，R1 handoff 仅作为「必修项清单」的来源。

### 只读范围与验证方式

`git diff 90bcaae72a17de358e9edbfd9cf337136acf4b57..fefc8aac46e7dbc9a1e20467625288e9aa70ac48`
输出 1 个文件、9 增 5 删，仅 `evidence/public-ip-live-plan.md`，与 `status.json` revision 7 的
`base_sha`/`delivery_sha` 完全一致；`git status --porcelain` 为空，未移动 `HEAD`（当前
`HEAD=54b23cc`，为其后的控制提交，未作为接受依据）。本次评审未发起任何网络请求、未读取凭据、
未访问币安、未运行或重启服务、未修改除本交接件外的任何文件。

### R1 必修项逐条核验

#### R1-1 注入 seam —— 已逐字钉死（`ACCEPT`）

修订后计划第 2 节原文：「`build_server()` 不增加参数；它在每次构建 server 时将
`_Handler.public_ip_service` 显式复位为 `None`……`run()` 保持既有两参数调用
`build_server(config, service)`，并且**只在该调用返回后**创建 `PublicIpService`、赋给
`_Handler.public_ip_service`……不得在调用前赋值（会被复位清除），也不得传入新关键字参数
（既有两参数 `build_server` 测试替身不接受它）。」

对照原始代码逐项复核，四项全部成立：

- `backend/app/server.py:1473-1483` —— `build_server()` 现有形状确实是「先复位 handler 属性、
  再构造 server」，新增一行同族复位与既有三行同构，不引入第四种模式。
- `backend/app/server.py:1712-1729` —— `run()` 的既有装配顺序确为「1715 行调用
  `build_server(config, service)`，1716-1729 行再逐个赋值 `ledger_flow_service` /
  `asset_transfer_*` / `margin_repay_*`」，计划所称「与现有 Handler 依赖同一装配顺序」属实。
- `backend/tests/test_service_health.py:307`、`:339`、`:369`、`:422` —— 四处 `build_server`
  替身仍是两参数形状（`lambda c, s: ...`），计划的第二条禁止句直接对应这四处。
- R1 列出的坏读法 A（传关键字参数 → 四个既有测试 `TypeError`）与坏读法 B（复位前赋值 →
  生产端点永久 503、离线测试全绿）在修订文本中都被具名禁止并附了原因，已无解释空间。

补充核对（本轮新查，非阻塞）：`test_service_health.py` 的 run() 用例会猴补 `build_server`，
因此复位不执行，`run()` 造出的真实 `PublicIpService` 会作为类属性残留到同进程后续用例。
这不会造成意外外呼——所有 wire 测试都经真实 `build_server`（即复位）建服务，且计划中的服务
只在请求时惰性外呼、构造期零 I/O、零线程。此项为「已验证无问题」，不是发现。

#### R1-2 验收测试范围 —— 已完整收编（`ACCEPT`）

验收标准第 6 条现为：`python3 -m pytest -q backend/tests/test_public_ip_api.py
backend/tests/test_service_health.py backend/tests/test_max_withdraw_api.py
backend/tests/test_ledger_flow_api.py backend/tests/test_asset_transfer.py
backend/tests/test_margin_repay.py`、`node frontend/self-check.js`、`git diff --check`，
并要求保留原始输出。R1 点名的五个既有文件一个不少，且逐一确认存在于工作树
（`test_public_ip_api.py` 为本次待新建，符合预期）。这五个文件正是 `build_server` 调用形状
（2/3/4 位置参数）与 `run()` 装配的既有覆盖，坏读法 A/B 至此都有断言能抓到。

### 非阻塞项落地核验（R3 / R4 / R5(a) / R5(b)）

- R3 前端不阻塞：计划已写「调用不被 `await` 进快照/持仓主链，并在自身 `catch` 中降级，故最坏
  4 秒外呼不会拖慢既有刷新节奏」。与 `frontend/index.html:6881-6912` 的 `loadApi()`
  （全程 `isRefreshing=true`、`finally` 重排 60 秒定时器）对照，该约束正好切断了耦合点。
  另核实 `frontend/self-check.js` 已大量使用 `await new Promise(r => setTimeout(r, 0))`
  的既有 flush 范式（如 `:3116`、`:3148`），验证 fire-and-forget 后的 badge 文案无需新增测试结构。
- R4 失败缓存：测试清单已加入「两源失败后 5 分钟内不再外呼的失败缓存」，与验收标准第 3 条对齐。
- R5(a) 响应体限长：计划写「响应体最多读取 64 字节」。核算最坏情形——ipify JSON 承载完整形式
  IPv6 为 `{"ip":"<39 字符>"}` = 48 字节，checkip 纯文本 ≤ 40 字节，64 字节对两源都有余量，
  不会把合法地址截断；被门户劫持返回的 HTML 截断后解析失败 → 按既定 fail-closed 走备用源，
  行为正确。
- R5(b) 隐私遮蔽：Planner 明确未采纳，并写下重开条件（Human 要求对外截图时遮蔽公网 IP）。
  这与 R1 的定性一致（Human 的产品选择，非缺陷），本轮不再提出。

### 原有约束仍完整成立（`ACCEPT`）

本次 diff 未触碰以下任何一条，逐条复读确认仍在：同源只读 `GET /api/system/public-ip`；
固定主源 `https://api.ipify.org?format=json` 与备用 `https://checkip.amazonaws.com/`；
2 秒 timeout；5 分钟进程内缓存（成功与失败同缓存）；四字段三态契约与
`Cache-Control: no-store`；零新依赖、零新配置项、零后台线程、零重试循环、零 localStorage、
零浏览器外域请求；不读凭据、不访问币安、不触碰资金路径/live gate/白名单；以及
「该展示不能证明币安实际观察到相同出口 IP、仅供 Human 核对」的边界声明。

### 观察项（不阻塞、不进入 Human 摘要）

- O-1 若 ipify 未来在 JSON 中增加字段，64 字节截断会让主源解析失败并静默降级到
  `checkip.amazonaws.com`。功能不受影响（仍返回真实 IP），但 `source` 字段会长期显示备用源。
  重开条件：Human 发现 `source` 恒为 `checkip.amazonaws.com` 且需要区分「主源坏了」与
  「主源变了」时，再考虑放宽上限或记录一次性降级原因。
- O-2 计划引用「币安 API key 安全说明把 ipify 作为示例」；本轮为只读且禁止外呼，无法核实该外部
  引用。它不影响计划成立，仅记录为未验证事实（与 R1 同）。

### 未以新假设阻塞的声明（`AGENTS.md` §1 Scenario Admission）

本轮未以任何新假设场景阻塞交付：结论为 `ACCEPT`，O-1/O-2 为带重开条件的观察项，不改变交付
范围、不进入 Human 摘要、不构成 `REWORK` 依据。

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-live-plan-review-claude-r2.handoff.md`
  2. `reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-live-plan.md`
  3. `reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-live-plan-review-claude.handoff.md`
- 执行：Bookkeeper 核验本次 R2 计划复审并向 Human 报告；`ACCEPT` 成立后按计划「实施后关卡」
  准备 Kimi（前端）与 Claude-GLM（后端）实现 dispatch，两者共享的端点契约不得拆成互相独立的
  实现提交。
- 关卡：实现完成后按实际风险与固定 `base_sha..delivery_sha` 走正式评审（review-1 / review-2 路由
  依 `AGENTS.md` §8）。本次 `ACCEPT` 只接受计划，不授权重启、部署、交易所访问或白名单变更。
- 不能假设的事实：
  - 不得假设实现者可自行调整装配顺序——计划第 2 节的两条禁止句是实现约束，实现 dispatch 须原样携带。
  - 不得假设「新测试文件全绿」等于「共享 `server.py` 无回归」；验收第 6 条的六个测试文件必须全跑并留原始输出。
  - 不得假设本 stage 代码会被当前手动前台进程加载——本轮不重启、不部署。
  - 不得把该端点展示的公网 IP 当作币安实际观察到的出口 IP，或据此改动 API 白名单。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

```text
[TASK_RESULT v2]
任务 ID: public-ip-live-plan-review-claude-r2
执行结果: completed（完成）
结果摘要: 第二轮独立只读复审修订后的公网 IP 展示计划。R1 两条必修均已精确收编：注入顺序连同两条禁止句写死（与 server.py:1473-1483、1712-1729 及四处两参数 stub 逐一对齐），验收补齐五个既有 server 装配测试并留原始输出；R3/R4/R5(a) 也已落地，64 字节上限对最坏 IPv6 有余量。结论 ACCEPT。
产物: [reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-live-plan-review-claude-r2.handoff.md]
检查结果: [1 固定 SHA 与 status revision 7 一致、diff 仅计划文件、工作树干净未移动 HEAD: pass, 2 build_server 不增参数且复位、run() 两参数调用且仅返回后注入、两条禁止句消除坏读法 A/B: pass, 3 验收纳入新测试与 test_service_health/max_withdraw/ledger_flow/asset_transfer/margin_repay 五文件并保留原始输出: pass, 4 R3 不 await 主链且自行降级、R4 失败缓存零重复外呼测试、R5(a) 响应体 64 字节: pass, 5 同源端点/三态四字段/固定主备源/2s/5min/零依赖配置线程外域/仅供核对边界完整保留: pass, 6 64 字节对最坏情形完整 IPv6（JSON 48 字节）有余量，截断走 fail-closed 回退: pass, 7 未以新假设阻塞，O-1/O-2 为带重开条件的观察项: pass]
阻塞项: [none]
评审结论: ACCEPT（接受）
问题记录: reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-live-plan-review-claude-r2.handoff.md
修复要求: none
本地北京时间: 2026-08-12 20:13:03 CST
下一步模型: codex / GPT-5（Bookkeeper）
下一步任务: 读取：reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-live-plan-review-claude-r2.handoff.md；执行：Bookkeeper 核验 R2 计划复审并向 Human 报告；关卡：ACCEPT 后准备实现 dispatch，REWORK 后由 Planner 修订计划
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- source_sha256: `2d2d04952c6e3fb93f2281d4476caa5ed75e1f155d7b7ac48b51a33e7a3ce56e`（`BOOKKEEPER_APPEND_ONLY` 前的精确字节）
- verified_at: `2026-08-12 20:17:18 CST`
- status revision checked: `7` → next dispatch status revision `8`
- fixed range: `git rev-parse` confirms base `90bcaae72a17de358e9edbfd9cf337136acf4b57` and delivery `fefc8aac46e7dbc9a1e20467625288e9aa70ac48`; `git diff --name-status base..delivery` contains only the revised plan and `git diff --check` exits 0.
- result: well-formed `ACCEPT`, provider-isolated (OpenAI plan author / Anthropic reviewer). R1's injection-order and shared-server-test findings are traceably rechecked in the R2 source report; no live/network/credential activity occurred.
- transition: R2 plan acceptance is verified. The prepared next task is backend-first, so the shared API contract is authored and tested before Kimi consumes it; the front-end task is intentionally not yet dispatched. This acceptance does not authorize restart, deployment, exchange access, IP-whitelist change, or a real public-IP lookup.

## Errata (append-only)

# Implementation Dispatch — Task A (Backend) — Hedge Open Live Hardening v1

Human operator: run this prompt in a fresh **write-capable Claude-GLM**
(`glm-5.2[1m]`) session. Task A and Task B (`14-implementation-frontend.dispatch.md`)
are independent and may run in parallel.

Save the session's raw implementation report as:
`reports/agent-runs/2026-07-hedge-open-live-hardening-v1/20-implementation-backend.md`

## Prompt body

```text
[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务的唯一执行者。
1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令（包括但不限于 claude-glm -p、
   kimi -p、codex exec、grok）。需要其他模型时，只输出交接建议，由 human operator 决定。
2. 你只能在本任务的文件边界内写代码与测试；不得访问凭据、不得发起任何 Binance 请求
   （公共或私有）、不得启动 HTTP 服务、不得下单、不得改动实盘闸门数据。
3. 输出必须保留事实来源路径与未解决风险；不能把未经验证的假设写成事实。
4. 你不 commit、不改 status.json、不改 70-handoff.md。唯一写者是 bookkeeper。

你是 stage `2026-07-hedge-open-live-hardening-v1` 的**后端实现者（任务 A）**。

## 决策权威（照做，不要重新设计）

- reports/agent-runs/2026-07-hedge-open-live-hardening-v1/10-design.md（§2.1 S1、
  §2.3 S3 后端、§2.4b S4b、§2.5 S5、§3 文件边界、§4 冻结契约、§6 测试策略、
  §7 必须改动清单、§8 风险与未决点）
- reports/agent-runs/2026-07-hedge-open-live-hardening-v1/11-adr.md
  （ADR-H1/H2/H4/H5，含被否决的备选——不要重开这些已闭合的选择）
- reports/agent-runs/2026-07-hedge-open-live-hardening-v1/12-development-breakdown.md §2
- 上一 stage 的冻结契约：reports/agent-runs/2026-07-hedge-open-real-api-v1/11-adr.md
- AGENTS.md；agents/developer-discipline.md

设计里所有中文文案、错误码、字段名都是**冻结的**，逐字实现，不得改写。

## 交付项

A-1 (S1, P0)：`backend/hedge_open_tasks/executor.py` 的 `_client_order_ids` 改为
    `f"hg{attempt_id}s"` / `f"hg{attempt_id}p"`（35 字符，ADR-H1）。推导点必须保持
    唯一——record transport 与 live 执行器共用同一函数，**不得复制出第二份规则**。
    核对 `backend/tests/` 中的 18 处 `hgo-` 字面量：断言推导结果格式的必须更新；
    仅作为任意 client id 实参传入的不要动，也不要顺手放宽断言粒度。

A-2 (S5)：新建 `backend/hedge_open_tasks/wire_constraints.py`（纯函数模块，只 import
    re/decimal，必须通过 `test_hedge_purity.py` 的纯度守卫）；接入
    `RecordTransportExecutor.execute`；严格化 `test_live_hedge_executor.py` 的
    `_FakeClient`；写 pre-fix S1 离线失败回归测试；新建
    `reports/api-samples/2026-07-hedge-open-live-hardening-v1/client-order-id-cap.md`
    事实记录页（实测 -4015 证据 + 文档 36 上限与 regex + §8 未验证边界）。
    live 发送路径刻意不挂校验器（ADR-H4），`live_hedge_executor.py` 与
    `hedge_open_live_client.py` 一行不改。

A-3 (S3)：`set_start_gate_cas`（CAS + 同事务审计行）、`put_start_gate` service 方法、
    `POST /api/hedge-open-settings/start-gate` 路由 + `_is_hedge_open_path` 同步接受
    子路径、`settings_to_doc` additive 加 `version`、全新 DB 默认关闭断言。
    请求/响应/错误码全形照 10-design §2.3，一字不改。既有无条件 seam
    `store.set_start_gate` / `service.set_start_gate` 保留不动。

A-4 (S4b)：`HedgePreflightProvider.check_symbol_legs` 三态探针（含能辨认 -1121 的
    公共读取变体）+ `create_task` 拦截 + `missing_leg` 中文文案照 10-design §2.4b。
    None（读取失败）不拦截。`DisabledPreflightProvider` 行为与网络面零变化。

A-5 (§8 未决点，必须以测试证实或证伪)：`build_*_order_params` 用 `str(quantity)`，
    极小数量是否会产出科学计数法（如 `1E-7`）。证实 → 把该 seam 收敛到
    `domain.fmt_decimal`（属 S5 范围内的最小修复）；证伪 → 在报告里落一行证据。

## bookkeeper 追加的两个机械检查点（不改设计，只是把隐含依赖显式化）

M-1 审计行 payload 的键集合：`hedge_open_log` 的 `start_gate_changed` 行会经既有
    全量投影进入 `GET /api/hedge-open-logs` 的 legacy `logs` 数组，而前端
    `extractHedgeAttempts`（frontend/index.html:3835）会扫描该数组，凡条目自身或其
    payload 含 `attempt_seq` / `pair_outcome` / `spot` / `perp` 任一键就会被当作
    attempt 卡渲染。设计给的 payload（enabled / previous_enabled / version / source）
    天然不含这四个键，但这是隐含依赖：请加一条断言把它钉住——
    `start_gate_changed` 的 payload 键集合恰为那四个，且与上述四个 attempt 形状键
    不相交。（前端侧另有对应断言，两边各钉一半。）

M-2 `frontend/self-check.js` 里另有 14 处 `hgo-` 字面量（前端 mock fixture 的
    client_order_id 展示值）。它们**不在你的文件边界内**，不要碰，也不要因为格式
    不一致而在报告里提议改动——那是前端任务的判断范围。

## 文件边界

**允许**：
- backend/hedge_open_tasks/{executor.py,service.py,store.py,domain.py}
  （domain 仅错误码/文案等最小增量）
- backend/hedge_open_tasks/wire_constraints.py（新建）
- backend/services/hedge_preflight_provider.py
- backend/app/server.py（仅路由接线）
- backend/tests/test_hedge_*.py、backend/tests/test_live_hedge_executor.py
- reports/api-samples/2026-07-hedge-open-live-hardening-v1/client-order-id-cap.md（新建）
- reports/agent-runs/2026-07-hedge-open-live-hardening-v1/20-implementation-backend.md（你的报告）

**禁止**：frontend/**、backend/services/hedge_open_live_client.py、
backend/services/live_hedge_executor.py、backend/services/binance_signing.py、
backend/hedge_open_tasks/scheduler.py、backend/config.py、backend/borrow_tasks/**、
docs/**、既有 reports/**、status.json、70-handoff.md、env/凭据文件、任何网络配置。

若认为必须触碰禁区（尤其 live_hedge_executor.py）→ **R3 升级**：停手，在报告里写明
理由与建议，等 bookkeeper 决定。不得自行修改，不得"顺便"改。

## 自测命令（必须全部执行并在报告中附输出摘录与计数）

.venv/bin/python -m pytest backend/tests/test_hedge_domain.py backend/tests/test_hedge_store.py backend/tests/test_hedge_service.py backend/tests/test_hedge_api.py backend/tests/test_hedge_executor.py backend/tests/test_hedge_task_local.py backend/tests/test_hedge_review2_regressions.py backend/tests/test_hedge_open_live_client.py backend/tests/test_live_hedge_executor.py backend/tests/test_hedge_purity.py -q
.venv/bin/python -m pytest backend/tests -q
node frontend/self-check.js
.venv/bin/python -m pytest scripts/tests/test_validate_stage_dispatch_protocol.py -q
git diff --check

## 收尾纪律（R10）

- 自测全 PASS → 写 `20-implementation-backend.md`（改了什么、为什么、测试输出摘录与
  全量计数、A-5 的结论与证据、遗留风险），然后**停下**等 bookkeeper。不要 commit。
- 自测 FAIL → 仅在本任务 scope 内修复并重跑；不得放宽或删除既有断言来转绿。
- 涉及冻结契约 / 共享面 / 对侧文件 → R3 升级，停手。
- 安全红线：不发任何真实 POST、不访问凭据、不发任何 Binance 请求、不启动 HTTP 服务、
  不触碰 durable Start 闸门数据（当前 start_gate=0、服务已停，实现期必须保持不变）。

最后附上下面的 footer。

当前 Session ID: 报告你的 provider-native id，取不到就写 unavailable 并说明原因
Session ID 来源: runtime_env | hook_payload | cli_output | transcript_path | active_session_registry | operator | unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-live-hardening-v1/20-implementation-backend.md
本地北京时间: 用本地 date 命令取
下一步模型: bookkeeper
下一步任务: R4 diff 对账与证据 commit；不要自行 commit 或进入评审
```

Current dispatch executor: **human operator**. The bookkeeper does not execute
Claude-GLM commands or relay this prompt to a model.

当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native session id)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-live-hardening-v1/13-implementation-backend.dispatch.md
本地北京时间: 2026-07-27 18:20:00 CST
下一步模型: human operator
下一步任务: 在全新的写权限 Claude-GLM 终端执行本 packet，产出 20-implementation-backend.md

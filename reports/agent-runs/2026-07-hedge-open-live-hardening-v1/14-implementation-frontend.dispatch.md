# Implementation Dispatch — Task B (Frontend) — Hedge Open Live Hardening v1

Human operator: run this prompt in a fresh **write-capable Kimi** session
(`kimi --model kimi-code/kimi-for-coding -p "$(cat <this-prompt-body-file>)"`, or an
interactive write-capable Kimi session). Task A
(`13-implementation-backend.dispatch.md`) and Task B are independent and may run in
parallel.

Save the session's raw implementation report as:
`reports/agent-runs/2026-07-hedge-open-live-hardening-v1/20-implementation-frontend.md`

## Prompt body

```text
[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务的唯一执行者。
1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令（包括但不限于 claude-glm -p、
   kimi -p、codex exec、grok）。需要其他模型时，只输出交接建议，由 human operator 决定。
2. 你只能在本任务的文件边界内写代码与测试；不得访问凭据、不得发起任何 Binance 请求、
   不得启动 HTTP 服务、不得下单、不得改动实盘闸门数据。
3. 输出必须保留事实来源路径与未解决风险；不能把未经验证的假设写成事实。
4. 你不 commit、不改 status.json、不改 70-handoff.md。唯一写者是 bookkeeper。

你是 stage `2026-07-hedge-open-live-hardening-v1` 的**前端实现者（任务 B）**。

## 决策权威（照做，不要重新设计）

- reports/agent-runs/2026-07-hedge-open-live-hardening-v1/10-design.md（§2.2 S2、
  §2.3 S3 前端与冻结弹窗文案、§2.4a S4a 与冻结中文映射、§3 文件边界、§4 冻结契约、
  §6 测试策略）
- reports/agent-runs/2026-07-hedge-open-live-hardening-v1/11-adr.md（ADR-H2/H3）
- reports/agent-runs/2026-07-hedge-open-live-hardening-v1/12-development-breakdown.md §3
- AGENTS.md；agents/developer-discipline.md

设计里所有中文文案与字段名都是**冻结的**，逐字实现，不得改写、不得润色。
UI 一律中文优先。

## 后端契约（本轮由任务 A 并行实现；你按此冻结面写，用 self-check mock 消费，不要等它）

1. `GET /api/hedge-open-settings` 响应 additive 增加 `"version": <int>`。
2. `POST /api/hedge-open-settings/start-gate`
   请求 `{"enabled": <bool>, "confirm": true, "version": <int>}`
   200 → 完整 settings doc（含新 version）
   409 → `{"error":"version_conflict","detail":"设置已被其他会话修改，请刷新后重试","settings":<当前 doc>}`
   400 → `invalid_json` / `invalid_field` / `confirmation_required`
3. task doc 既有字段 `worker_active`（true|false|null）、`last_worker_exit_reason`
   （枚举见 10-design §2.4a|null）——后端零改动，你只消费。
4. `POST /api/hedge-open-tasks` 新错误
   `400 {"error":"missing_leg","detail":"<中文>","missing":["spot"|"perp", …]}`。

字段名有任何缺失或含义存疑 → **升级 bookkeeper，绝不发明字段、绝不猜测**。

## 交付项

B-1 (S2, P1)：`frontend/index.html:3685` 的 `startDisabled` 照 10-design §2.2 的表达式
    逐字实现。**严格用 `=== false`**：`null`/`undefined` 必须落在 disabled 一侧。
    dry-run（`worker_active === null`）行为必须逐字不变。

B-2 (S3)：执行徽标行（`hedgeExecutionBadge` 附近）旁加**单一控件**，label 随闸门状态
    切换（关→「开启开单闸门」；开→「关闭开单闸门」）。两个方向各**恰好一次**确认
    弹窗（双按钮变体，无手输确认词）。弹窗中文文案照 10-design §2.3 逐字。
    POST 携带 `state.hedgeSettings.version`；409 → 重新 GET 刷新 + 提示
    「设置已被其他会话修改，已刷新，请重试」；点「取消」→ **零请求**。
    version 过期路径不得进入死循环弹窗。

B-3 (S4a)：任务卡新增一行
    `执行线程：<运行中|未运行|—> · 上次退出原因：<中文|—>`。
    八个退出原因的中文映射照 10-design §2.4a 逐字；未知值原样经 `hedgeText` 展示；
    字段缺失按既有 `hedgeText` 约定降级「—」（dry-run 恒显示「—」）。

B-4 (S4b)：确认建卡错误路径能展示 `missing_leg` 的中文 `detail`。若既有 hedgeApi
    错误通道已天然支持，就用 self-check 用例把它钉住，不要重复造错误展示逻辑。

B-5：扩展 `frontend/self-check.js` 覆盖 10-design §6 的前端各项：S2 四象限
    （dry-run running / live running+worker_active:false / live running+
    worker_active:true / paused）、S3（label 随状态、确认后才发请求、取消零请求、
    409 刷新路径）、S4a（三态与八个中文映射）、S4b（detail 展示）。
    不允许只做 static-text-only 断言。

## bookkeeper 追加的两个机械检查点（不改设计，只是把隐含依赖显式化）

M-1 后端的闸门审计行（`kind="start_gate_changed"`）会经全量投影进入
    `GET /api/hedge-open-logs` 的 legacy `logs` 数组，而 `extractHedgeAttempts`
    （index.html:3835）会扫描该数组。已核实：该行 payload 不含
    `attempt_seq`/`pair_outcome`/`spot`/`perp`，因此 `isHedgeAttemptShaped` 会拒绝
    它、不会渲染成畸形 attempt 卡。请加一条 self-check 断言把这个隐含依赖钉住：
    喂一条 `start_gate_changed` 日志条目给 `extractHedgeAttempts`，断言结果为空。
    （后端侧另有对应的 payload 键集合断言，两边各钉一半。）

M-2 `frontend/self-check.js` 里有 14 处 `hgo-` 开头的 client_order_id 字面量，是纯
    展示用 mock fixture。后端本轮把真实推导改成了 `hg…s|p`（35 字符）。这些 fixture
    作为**任意实参**并不影响正确性，**不要求你改**；若你选择改成新格式以保持一致，
    必须**整体一致地改完**，不得只改一部分。两种做法都可接受，但要在报告里说明选了
    哪种。

## 文件边界

**允许**：`frontend/index.html`、`frontend/self-check.js`、
`reports/agent-runs/2026-07-hedge-open-live-hardening-v1/20-implementation-frontend.md`
（你的报告）。

**禁止**：其余一切，包括所有 `backend/**`、`docs/**`、既有 `reports/**`、
`status.json`、`70-handoff.md`、env/凭据文件。

不得顺手改动与本任务无关的卡片渲染、样式或文案。

## 自测命令（必须全部执行并在报告中附输出摘录与计数）

node frontend/self-check.js
.venv/bin/python -m pytest backend/tests -q
git diff --check

## 收尾纪律（R10）

- 自测全 PASS → 写 `20-implementation-frontend.md`（改了什么、为什么、测试输出摘录与
  全量计数、M-2 的选择与理由、遗留风险），然后**停下**等 bookkeeper。不要 commit。
- 自测 FAIL → 仅在本任务 scope 内修复并重跑；不得放宽或删除既有断言来转绿。
- 涉及后端字段 / 冻结契约 / 对侧文件 → R3 升级，停手等 bookkeeper。
- 安全红线：不发任何真实请求、不访问凭据、不启动 HTTP 服务、不触碰 durable Start
  闸门数据（当前 start_gate=0、服务已停，实现期必须保持不变）。

最后附上下面的 footer。

当前 Session ID: 报告你的 provider-native id，取不到就写 unavailable 并说明原因
Session ID 来源: runtime_env | hook_payload | cli_output | transcript_path | active_session_registry | operator | unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-live-hardening-v1/20-implementation-frontend.md
本地北京时间: 用本地 date 命令取
下一步模型: bookkeeper
下一步任务: R4 diff 对账与证据 commit；不要自行 commit 或进入评审
```

Current dispatch executor: **human operator**. The bookkeeper does not execute
Kimi commands or relay this prompt to a model.

当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native session id)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-live-hardening-v1/14-implementation-frontend.dispatch.md
本地北京时间: 2026-07-27 18:20:00 CST
下一步模型: human operator
下一步任务: 在全新的写权限 Kimi 终端执行本 packet，产出 20-implementation-frontend.md

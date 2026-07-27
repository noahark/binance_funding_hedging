# Design + ADR + Breakdown Dispatch — Hedge Open Live Hardening v1

Human operator: run this prompt in a fresh **Claude Fable 5** session (backup:
Claude Opus 4.8 if Fable5 quota is exhausted — record which one ran). This is
design-only: it must not implement code or launch another model.

The session produces **three** documents in one response, each fenced by an
explicit file marker. Save each block verbatim as its own file:

- `reports/agent-runs/2026-07-hedge-open-live-hardening-v1/10-design.md`
- `reports/agent-runs/2026-07-hedge-open-live-hardening-v1/11-adr.md`
- `reports/agent-runs/2026-07-hedge-open-live-hardening-v1/12-development-breakdown.md`

Routing note: Claude provider is used for design and breakdown so that Codex
stays free of prior involvement and can serve as Review-2 without a
strong-reviewer disclosure override. Do not route this packet to Codex.

## Prompt body

```text
[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务的唯一执行者。
1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令（包括但不限于 claude-glm -p、
   kimi -p、codex exec、grok）。需要其他模型时，只输出交接建议，由 human operator 决定。
2. 你只能做本任务要求的只读检查和指定设计输出；不得写产品源码、访问凭据、发起 Binance
   私有请求、启动服务或下单。
3. 输出必须保留事实来源路径、设计判断和未解决风险；不能把未经验证的假设写成事实。

你是 stage `2026-07-hedge-open-live-hardening-v1` 的 stage designer 兼
development-breakdown author。只做设计与任务拆分，不写任何产品代码，不修改
status.json、70-handoff.md、PRD 或源码。

## 背景

上一个 stage `2026-07-hedge-open-real-api-v1` 已验收并合并，但它的第一笔真实
订单被币安拒绝。凭据、签名、六个只读 preflight 接口、symbol filters、q_common
推导、双腿并发提交、拒单处理、对账与结算全部正确，只在最后一步的参数校验上失败。
本 stage 修这些"只有真实发送才暴露"的运行时缺口，不改任何已冻结契约。

## 必读

- AGENTS.md；agents/developer-discipline.md；
- reports/agent-runs/2026-07-hedge-open-live-hardening-v1/{00-intake.md,00-task.md,status.json}；
- reports/agent-runs/2026-07-hedge-open-real-api-v1/70-handoff.md 的
  「First live run」章节，以及该 stage status.json 的 live_first_run_findings；
- reports/agent-runs/2026-07-hedge-open-real-api-v1/{10-design.md,11-adr.md,16-replacement-development-breakdown.md}（已冻结契约与既有拆分口径）；
- backend/hedge_open_tasks/{domain.py,store.py,service.py,executor.py,scheduler.py}；
- backend/app/server.py；backend/config.py；
- frontend/index.html（对冲开单卡片与设置区）；
- backend/tests/test_hedge_*.py。

## 五项范围（细节见 00-intake.md / 00-task.md，不要重述背景，直接给设计）

S1 (P0) clientOrderId 超长：executor.py:160 的 `hgo-{attempt_id}-s` = 38 字符，
        币安上限 36，双腿都收到 -4015。必须给出新的推导方案：≤36、双腿互异、
        全局唯一，且仍能支撑 ADR-2 依赖的「仅凭 clientOrderId 对账」路径。
        明确说明历史遗留 id（若 DB 里已有 38 字符记录）如何兼容。
S2 (P1) live 模式新建卡无法启动：前端 index.html:3685 的 startDisabled 让
        running 卡的 Start 变灰；live 下 create_task 不起 worker 且 tick() 是
        有意的 no-op（H-1），只有 post_start 能起 worker，形成死锁。设计要
        判断：这是纯前端按钮条件问题，还是后端状态语义问题（新建卡是否应该
        进入一个区别于 running 的初始态）。给出结论与理由，不要两头下注。
        约束：dry-run 行为不变；不得让 live 下的卡自动派单，H-1 的 no-op 保留。
S3 (P2) Start 闸门无操作入口：/api/hedge-open-settings 只有 GET，
        service.set_start_gate() 没有生产调用方，上次是直接改 SQL 开的闸。
        **用户已决定形态：对称确认弹窗** —— 后端新增写入路径；前端同一个控件
        管开与关，两个方向各需恰好一次确认弹窗；不要手输确认词，不要开关不对称。
        设计需给出：接口路径与方法、请求/响应结构、如何用 settings 行已有的
        version 列做并发安全、写入的日志记录、以及弹窗中文文案。全新安装默认
        必须仍是关闭。
S4 两条欠账：(a) 前端展示 worker_active 与 last_worker_exit_reason（后端已产出、
        从未展示），字段缺失时按既有 hedgeText 约定降级为「—」；(b) 建卡时校验
        现货与 USDⓈ-M 合约双边都存在，缺哪边就在建卡时用中文拒绝并指明缺失的
        那一腿，而不是留一张空转的卡。参照案例：KORUUSDT 只有合约没有现货
        （-1121）。只做存在性校验，不做 1000x 前缀归一化。
S5 离线 transport 补参数约束：现有 fake/record transport 不校验长度、字符集、
        精度，reports/api-samples/ 也从未记录 36 字符上限——这正是 S1 熬过九轮
        评审的直接原因。设计要说明在哪一层加约束（transport 内部 vs 独立校验
        器）、覆盖哪些参数、以及如何写一个「用修复前的 S1 推导会离线失败」的
        回归测试。同时说明是否需要在 reports/api-samples/ 补记这条上限。

## 三份输出

=== FILE: 10-design.md ===
stage 设计：目标与非目标、每一项的具体设计决策与理由、文件边界（允许/禁止修改）、
API 与数据契约（含 S3 的接口契约）、兼容与迁移、测试策略、风险与未决点。
明确指出哪些既有 dry-run/离线代码必须改动。

=== FILE: 11-adr.md ===
本 stage 的架构决策记录。至少覆盖：S1 的 id 推导方案（含被否决的备选与理由）、
S3 的闸门写入契约与并发语义、S2 的「前端条件 vs 后端状态语义」定性结论、
S5 的约束校验落点。每条给出 context / decision / consequences。
不要复制上一 stage 的 ADR，只写本 stage 新增或修订的决策，并显式声明与既有 ADR
（尤其 ADR-2 的 clientOrderId 对账）的关系。

=== FILE: 12-development-breakdown.md ===
实现拆分。必须包含：
1. 串行还是并行的建议。当前默认路由是后端 claude_glm（glm-5.2[1m]）、前端
   kimi（kimi-k3）。若建议并行，只在真正独立的边界切，并给出依赖顺序与需要
   先冻结的共享契约；若建议串行，说清为什么。
2. 每个任务：owner 模型/provider、精确的允许与禁止文件清单、API/数据契约、
   确定性测试命令、证据与报告路径、风险点、评审关注点。
3. 是否启用 docs/parallel-development-mode.md。若启用，给出 R10 checklist 输入
   项，并列出需要 human operator 执行的 dispatch/review packet 清单——但不要
   写实现提示词本身。
4. 实现顺序与集成测试计划。
5. 硬性测试约束：不得发真实 POST、不得访问凭据、不得发私有请求、不得起服务。

## 硬性约束

- 不改任何被 real-api-v1 冻结的契约。若你认为某处必须改，单独列为「需用户批准的
  契约修订建议」，不要直接写进设计。
- 本 stage 不授予任何实盘权限。APP_HEDGE_EXECUTOR=live、Start 闸门、第一笔真实
  任务是三个相互独立的人工授权。当前服务已停、闸门已置 0。
- 设计要能被 Kimi 与 Claude-GLM 在各自边界内独立实现，被 Codex 独立复核。
- 事实来源必须带路径。不确定的地方写「未验证」，不要写成事实。

最后附上下面的 footer，且不做任何代码改动。

当前 Session ID: 报告你的 provider-native id，取不到就写 unavailable 并说明原因
Session ID 来源: runtime_env | hook_payload | cli_output | transcript_path | active_session_registry | operator | unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-live-hardening-v1/10-design.md, 11-adr.md, 12-development-breakdown.md
本地北京时间: 用本地 date 命令取
下一步模型: bookkeeper
下一步任务: 归档三份原始设计产物，不要实现代码
```

Current dispatch executor: **human operator**. The bookkeeper does not execute
Claude commands or relay this prompt to a model.

当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native session id)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-live-hardening-v1/10-design-and-breakdown.dispatch.md
本地北京时间: 2026-07-27 17:33:33 CST
下一步模型: human operator
下一步任务: 在全新的 Claude Fable 5 终端执行本 packet，并把三个文件块原样保存到指定路径

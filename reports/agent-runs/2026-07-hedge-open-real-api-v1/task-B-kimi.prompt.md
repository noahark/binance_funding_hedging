# Task B Dispatch — Frontend Hedge Open Real API v1

Human operator: run the prompt body below in a fresh write-capable Kimi K3 coding
session using the configured latest coding alias. This packet is immutable task
evidence. Preserve the model's complete unedited response in the implementation
report path named below.

## Prompt body

```text
[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务的唯一执行者。
1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令（包括但不限于 claude-glm -p、
   kimi -p、codex exec、grok）。需要其他模型时，输出 ESCALATED 及原因并停止。
2. 禁止编造未实际执行的命令结果或未实际读取的文件内容；你写下的每一条执行记录都必须
   对应你本会话内真实发生的动作。
3. 你的实现依据只能是本 prompt 列出的 raw artifact 路径与你自己实际读取的文件。

你是 Task B 的唯一前端实现者。只实现已批准 Hedge Open Real API v1 的中文前端增量展示。
不要改后端、status.json、70-handoff.md、docs 或任何其他文件，不要自行 git commit，也
不要启动或转派其他模型。当前分支为 `stage/2026-07-hedge-open-real-api-v1`。

先阅读：
- AGENTS.md；
- docs/product/PRD.md（§9）；
- reports/agent-runs/2026-07-hedge-open-real-api-v1/{00-task.md,05-cadence-resolution.md,10-design.md,11-adr.md,06-direction-synthesis.md,12-development-breakdown.md}；
- frontend/index.html、frontend/self-check.js。

允许改动仅限：
- frontend/index.html
- frontend/self-check.js
- reports/agent-runs/2026-07-hedge-open-real-api-v1/20-implementation-frontend.md

禁止改动：所有 backend/**、docs/**、status.json、70-handoff.md、API contract、环境/凭据
文件和其他任何路径。若你发现后端字段缺失/改名，不得自行发明字段；报告 ESCALATED 并停下
让 bookkeeper 协调。

冻结的后端 JSON contract（来自 `12-development-breakdown.md` §3.4）：
- task 增量字段：`q_common`、`failure_pause_threshold`、
  `consecutive_submission_failures`、`accepted_pair_count`、
  `scheduled_attempt_count`、`pause_reason`；旧 `leg_exposure` 仍为 advisory。
- per-attempt：`attempt_id`、`attempt_seq`、`direction`、`q_common`、`pair_outcome`；
  `spot` 和 `perp` 各含 `client_order_id`、`order_id`、`status`、
  `cumulative_base_qty`、`cumulative_quote_amt`、`avg_price`，spot 还可带
  `fee_amount`/`fee_asset`；以及 `residual`、`ts`。所有 Decimal 均为字符串。
- `positions` 将含真实 `spot_avg`/`perp_avg`；settings shape 不变。

前端实现要求：
1. 在既有 hedge task view 以中文优先、增量方式展示固定基础数量、planned count、有效
   q_common、任务/Start/executor 状态、每次 attempt 时间线、两腿订单号和状态、累计买卖数量
   与成交额、加权均价、失败连续数/阈值/暂停原因和可见 residual。
2. Decimal 字符串原样展示，不要用 JavaScript 浮点重新格式化。字段缺失时优雅降级，不得
   页面崩溃。
3. 扩展 self-check mock 和 DOM ID registry，断言新增字段与 attempt timeline 能渲染。
4. 浏览器绝不签名、调度或直接访问 Binance；UI 不得暗示它能自行开启 live。
5. immediate task 是每卡独立异步每秒一组、多个卡可同秒发送；该事实仅作状态文案理解，
   本任务不写 scheduler。smooth/WebSocket 不实现。

必须实际执行并如实记录：
`node frontend/self-check.js`

将完整实现报告写到
`reports/agent-runs/2026-07-hedge-open-real-api-v1/20-implementation-frontend.md`，至少包含：
实际改动文件、实际执行命令和原样结果摘要、mock/DOM 覆盖、字段缺失时的降级行为、未解决问题
和 git diff 概要。报告末尾必须带下面 footer（时间用本机 date 得到）。

完成后停止，等待 bookkeeper；不要 commit、不要改 status.json、不要派发/评审其他模型。

当前 Session ID: report provider-native ID, or unavailable with reason
Session ID 来源: runtime_env | hook_payload | cli_output | transcript_path | active_session_registry | operator | unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/20-implementation-frontend.md
本地北京时间: obtain from local date command
下一步模型: bookkeeper
下一步任务: collect Task B report, reconcile frontend/backend integration, and run integration evidence
```

当前 Session ID: unavailable (Codex runtime does not expose a provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/task-B-kimi.prompt.md
本地北京时间: 2026-07-23 20:13:12 CST
下一步模型: human operator
下一步任务: execute this packet in a fresh Kimi K3 write-capable terminal

# Review-2 Dispatch — Final Gate — Hedge Open Live Hardening v1

Human operator: run this in a fresh **read-only Codex** session.

```bash
codex exec --sandbox read-only "$(cat <this-prompt-body-file>)"
```

Per `AGENTS.md`: schema-bound Harness review nodes use read-only `codex exec`
with the review prompt, not `codex review`.

Save the session's complete unedited output as:
`reports/agent-runs/2026-07-hedge-open-live-hardening-v1/50-review-2.md`

**No disclosure override is needed this stage.** Codex has zero prior
involvement: design/ADR/breakdown went to Claude Fable 5, both implementations
to `claude_glm`, and both Review-1 gates to `grok-4.5`. Codex authored nothing
here.

## Prompt body

```text
[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务的唯一执行者。
1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令（包括但不限于 claude-glm -p、
   kimi -p、codex exec、grok）。在本会话内转派会使本次评审作废。
2. 你是只读终审员：不得修改任何文件、不得运行写操作、不得访问凭据、不得发起任何
   Binance 请求、不得启动服务、不得下单、不得改动实盘闸门数据。
3. 你的结论必须来自原始产物（diff、测试输出、源码），不得只依据他人摘要。
4. 输出必须以严格 JSON verdict 结尾，符合 schemas/review-verdict.schema.json。

你是 stage `2026-07-hedge-open-live-hardening-v1` 的 **review-2 终审员**（最终门）。

## 背景（一句话）

上一个 stage 已验收并合并，但它的第一笔真实订单发出即被币安拒绝：clientOrderId
38 字符 > 上限 36。本 stage 修这五项「只有真实发送才暴露」的运行时缺口，不改任何
已冻结契约。

## 固定范围（不要用移动的 HEAD）

    base_sha = 6c5b17002cab189d752177b447ff576356998f58
    head_sha = 319d8317bdf180750197c95078d2ae6c60e6badc
    diff_fingerprint = 319d8317bdf180750197c95078d2ae6c60e6badc:2a457c0f559fec81cfba8b9d59602c8630bbec73d7b86b28dddab12c4e554efd

查看：`git diff 6c5b170..319d831`

与 review-1 不同，**你审整个 stage 的两侧**（backend + frontend），以及交付是否
真正满足 00-task.md 的验收标准。

## 必读原始产物

需求与设计权威：
- reports/agent-runs/2026-07-hedge-open-live-hardening-v1/00-intake.md（含用户对 S3 形态的决定）
- reports/agent-runs/2026-07-hedge-open-live-hardening-v1/00-task.md（**验收标准**）
- reports/agent-runs/2026-07-hedge-open-live-hardening-v1/10-design.md
- reports/agent-runs/2026-07-hedge-open-live-hardening-v1/11-adr.md（ADR-H1..H5）
- reports/agent-runs/2026-07-hedge-open-live-hardening-v1/12-development-breakdown.md
- 上一 stage 冻结契约：reports/agent-runs/2026-07-hedge-open-real-api-v1/11-adr.md
  与该 stage 的 16-replacement-development-breakdown.md §5（entries 投影冻结词表）

实现与评审证据：
- 20-implementation-backend.md、20-implementation-frontend.md（实现者原始报告）
- 16-r4-diff-reconciliation.md（bookkeeper 的边界/跨 seam/抽查对账）
- 60-test-output.txt（bookkeeper 在合并态的复跑）
- 30-review-1-backend.md、30-review-1-frontend.md（两份 review-1 原始输出，均 ACCEPT）
- 13/14 号 dispatch packet（文件边界与 bookkeeper 追加的 M-1/M-2 检查点）

上述实现报告、R4 对账与两份 review-1 **都是被你评审的证据，不是权威**。发现与它们
矛盾之处，以代码与 diff 为准并报告。

## 交付内容（五项）

- **S1 (P0)**：clientOrderId → `hg{attempt_id}s|p`（35 字符）。推导点唯一，
  record 与 live 共用；旧 38 字符记录（全部 terminal）不迁移。
- **S2 (P1)**：定性为纯前端按钮条件缺陷，`running && worker_active === false`
  放行「启动」；后端零改动；dry-run（`worker_active===null`）行为不变。
- **S3 (P2)**：`POST /api/hedge-open-settings/start-gate`，body
  `{enabled, confirm: true, version}`；`confirm` 字面量校验；`version` CAS
  （未命中 409 带当前 doc）；审计行与闸门 UPDATE 同事务；settings doc additive
  加 `version`；前端单一控件 + 每方向恰好一次确认弹窗。
- **S4**：(a) 前端展示 `worker_active` / `last_worker_exit_reason`（八项中文映射）；
  (b) provider 三态存在性探针，仅在**读取成功**时才有权以 400 `missing_leg` 拒绝建卡。
- **S5**：独立纯校验器 `wire_constraints.py`，消费者=record transport + 测试严格假件，
  **live 发送路径刻意不挂**（ADR-H4）；含「修复前的 S1 推导必须离线失败」回归测试；
  api-samples 补记 36 上限事实页。
- 附带：设计中标为「未验证」的 `str(Decimal)` 科学计数法隐患被**实测证实**
  （可产出 `1E-7`），故 `build_*_order_params` 收敛到 `fmt_decimal`。

## 终审重点

1. **验收标准逐条核对**：00-task.md 的每条验收标准是否真的被满足，而不只是"有相关代码"。
2. **P0 是否真的解除**：一笔真实订单现在是否**能够**成功（在人类打开三道闸的前提下）。
   特别是：id 长度、字符集、以及 `fmt_decimal` 改动是否可能引入新的参数格式问题。
3. **冻结契约零修订**：status 状态词表、entries 投影的 `overall_result`/`next_action`
   词表、既有 API 字段语义是否被改动。additive 是允许的，语义变更不是。
4. **跨 seam 一致性**：前端消费的三个契约面（`settings.version`、start-gate POST 形状、
   `missing_leg`）与后端实际 wire 形是否逐字段一致。上一轮该 stage 栽了三次同型漂移。
5. **S3 是 live-risk 控制面**：`confirm` 字面量能否被绕过；CAS 与审计是否真原子；
   全新安装是否仍默认关闭；有没有任何路径能在无确认的情况下开闸。
6. **S4b 的 fail-open 取舍**：ADR-H5 决定「读取失败不拦截」。请判断这个取舍在本
   产品语境下是否可接受，以及它是否被正确实现（None 绝不能被当作 False）。
7. **ADR-H4 的取舍**：live 路径不挂校验器。请判断该论证是否成立
   （不在真钱路径引入第二裁决权威 vs 少一层防御纵深）。
8. **测试是否名副实**：新增测试是否为行为断言；S5 的回归是否真的钉住「这一类缺陷
   永远离线失败」而不只是钉住 36 这个数字；前端 self-check 是否有空壳用例。
9. **文件边界与安全**：是否有改动越界；是否引入真实 POST、凭据访问、私有请求、
   服务启动；「三道实盘授权彼此独立」的结构是否被削弱。
10. **两份 review-1 的判断是否成立**：它们各报了 2 个 P3、0 个 P0/P1/P2。你是否同意；
    有没有它们漏掉的问题。

## 重要披露：本 stage 的代码在你评审前已经过一次真实实盘验收

**必读**：`reports/agent-runs/2026-07-hedge-open-live-hardening-v1/18-live-acceptance-findings.md`

用户在 review_2 阶段前用 live 模式做了人工验收，通过 S3 的新控件打开闸门，跑了一笔
真实 NOMUSDT 任务。**没有任何交付代码因此被修改**，钉死的范围与指纹未动，两份
review-1 的 ACCEPT 依然有效。

那次运行**证明了本 stage 的修复有效**：
- S1 的 P0 确实解除——35 字符 clientOrderId 通过了币安格式校验，`-4015` 不再出现，
  合约腿真实成交；
- S3 的写入路径端到端可用——闸门经新控件打开（version 3→4），不再需要直改 SQL；
- settings doc 的 additive `version` 字段在真实 wire 上存在。

同时暴露了**四个缺陷（F-1..F-4）**，经 bookkeeper 查证，**没有一个属于本 stage 的
五项范围**，用户已决定它们进入独立的新 stage：

- **F-1**：币安已于 2026-07-14 从 `POST /papi/v1/um/order` 响应中**移除**
  `cumBase`/`cumQuote`/`avgPrice` 字段（官方 changelog 已核实）。系统读到 None，
  经 `_decimal_str` 默认值静默变成 `"0"`，导致成交金额与均价永久为 0。这是**外部
  契约漂移**，与本轮五项无关。
- **F-2**：币安 margin 端点用正数错误码、UM/CM 用负数；而 `domain.py` 的错误码表
  全是负数字面量，因此对 margin 腿的**整段**错误码失效。属上一 stage 的分类表设计。
- **F-3**：`_business_msg()` 提取了币安错误消息但从未持久化（leg 表无该列）。
- **F-4**：`51169`（`MARGIN_TRADE_COEFF_INSUFFICIENT`）的根因未定论；已排除"NOM 不
  支持杠杆"，并已确认 PAPI **没有** test-order 端点。

那次运行还留下一个**真实的单腿敞口**（UM 空头 10000 NOMUSDT 未对冲）。按已冻结设计
`single_leg_exposure` 是 ADVISORY（只记录、不作为门，`domain.py:96-99`），所以任务
结算为 `done` 是**符合契约**的行为，不是本轮引入的回归。

**这段披露的用途**：让你在完整信息下判断，而不是让你把 F-1..F-4 计入本轮。若你认为
其中某条**确实**属于本 stage 五项的实现缺陷（而非上一 stage 的遗留或外部漂移），请
明确指出并说明理由——那将是对 bookkeeper 判断的有效纠正。

## 已知开放项（review-1 已记录并判为不阻塞，供你独立复核）

- api-samples 事实页中文写「反斜杠」，但 regex 字符类无反斜杠字面量（`\.`/`\:`
  是转义的点与冒号）——bookkeeper 已核实属实，为文档措辞错误。
- `confirm` 负例测试参数化了 `1 / "true" / None`，未覆盖 `[]` / `{}`；实现用
  `is not True` 本身正确。
- 409 弹窗**标题**设计未冻结（仅冻结正文），前端用了中性标题并主动声明。
- S3 self-check 用 `includes` 子串而非全文全等断言弹窗正文。
- UM 侧 clientOrderId 字符集 regex 未单独实测（36 上限有实测）。
- `set_start_gate_cas` 从未在真实 durable DB 上运行过（实现者被禁止启动服务）。

这四条 P3 未在本 stage 修复，理由是任何改动都会移动 diff、使两份 review-1 刚刚
审过的指纹失效。已记入 `status.json.stage_followups`。若你认为其中某条必须在本
stage 修，请明确说明并给 REWORK。

## 严禁

- 不要要求超出本 stage 范围的改动（smooth 模式、自动平仓/对冲/借币、1000x 前缀
  归一化、把校验器挂到 live 路径）。后者是 ADR-H4 已闭合的决策——若你不同意，
  作为 P3/P2 意见提出并说明理由，由用户决定，不要仅因此判 REWORK。
- 不要因为「实现报告与两份 review-1 都说好」就降低核查强度。

## 输出格式

先写中文评审正文（每条重点的结论 + 证据路径/行号），然后**以严格 JSON 结尾**，
符合 `schemas/review-verdict.schema.json`：

必需字段：`schema_version`(=1)、`stage_id`、`role`(="final_reviewer")、`model`、
`verdict`(ACCEPT|REWORK|BLOCKED)、`diff_fingerprint`(逐字用上面那串)、
`reviewer_prior_involvement`(="none")、`reviewed_artifacts`(至少一项)、`findings`、
`required_fixes`、`next_action`。

`findings` 每项必须含：`severity`(P0|P1|P2|P3)、`title`、`evidence`、`impact`、
`recommendation`；可选 `file`、`line`。

ACCEPT 时 `next_action` 用 `stage_accepted_waiting_user`——本 stage 的验收与合并到
main 是**用户的决定**，不是你的。

**若 verdict = REWORK，必须额外提供 `fix_start_prompt`**：一段可直接发给修复实现者的
完整提示词，保留原始产物路径、发现、必须修复项、文件边界、精确测试命令与验收标准。

JSON 必须可被 `json.loads` 直接解析。footer 放在 JSON 之前。

当前 Session ID: 报告你的 provider-native id，取不到就写 unavailable 并说明原因
Session ID 来源: runtime_env | hook_payload | cli_output | transcript_path | active_session_registry | operator | unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-live-hardening-v1/50-review-2.md
本地北京时间: 用本地 date 命令取
下一步模型: bookkeeper
下一步任务: 归档终审原始输出并记录 verdict；验收与合并由用户决定
```

Current dispatch executor: **human operator**. The bookkeeper does not execute
Codex commands or relay this prompt to a model.

当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native session id)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-live-hardening-v1/50-review-2.dispatch.md
本地北京时间: 2026-07-27 21:28:00 CST
下一步模型: human operator
下一步任务: 在全新只读 Codex 会话执行本 packet，原样保存输出到 50-review-2.md

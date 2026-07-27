<!-- ===== DISPATCH RECEIPT（执行者/记账者填写） =====
status: pending
target_model: claude/Claude Opus 4.8
adapter_cmd: (fresh read-only Claude Opus 4.8 session; filled in by the operator on execution)
executor: human_operator
started_at: unavailable:not yet executed
completed_at: unavailable:not yet executed
session_id: unavailable:not yet executed
outputs: reports/agent-runs/2026-07-hedge-open-live-hardening-v1/31-review-1-backend-r2.md
next_dispatch: reports/agent-runs/2026-07-hedge-open-live-hardening-v1/51-review-2-r2.dispatch.md (human operator; may run in parallel)
receipt_sealed_by: bookkeeper (Claude Opus 5), prepared before execution.
session_isolation: MUST be a fresh read-only session. The bookkeeper session must not double as this reviewer.
===== END RECEIPT ===== -->

# Review-1 Dispatch (round 2) — Backend — Hedge Open Live Hardening v1

Human operator: run this in a fresh **read-only Claude Opus 4.8** session.

Save the complete unedited output as:
`reports/agent-runs/2026-07-hedge-open-live-hardening-v1/31-review-1-backend-r2.md`

**Why the reviewer changed.** Round 1's backend gate was grok-4.5. It returned
ACCEPT, and Review-2 then blocked on a finding grok had **seen but filed as a
residual risk** rather than a finding (`status.json.review_1_miss`). The user
rerouted this gate so the reworked code is not re-reviewed by the channel that
missed it. Opus 4.8 is provider-isolated from the implementer `claude_glm`
(`zhipu_glm`); it shares provider identity with the stage designer, which
AGENTS.md constrains only for Review-2, so this is admissible for Review-1.

## Prompt body

```text
[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务的唯一执行者。
1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令（包括但不限于 claude-glm -p、
   kimi -p、codex exec、grok）。在本会话内转派会使本次评审作废。
2. 你是只读评审员：不得修改任何文件、不得运行写操作、不得访问凭据、不得发起任何
   Binance 请求、不得启动服务、不得下单、不得改动实盘闸门数据。
3. 你的结论必须来自原始产物（diff、测试输出、源码），不得只依据他人摘要。
4. 输出必须以严格 JSON verdict 结尾，符合 schemas/review-verdict.schema.json。

你是 stage `2026-07-hedge-open-live-hardening-v1` 的 **review-1 后端评审员（第 2 轮）**。

## 固定范围（新范围，不要用移动的 HEAD，也不要用旧范围）

    base_sha = 6c5b17002cab189d752177b447ff576356998f58
    head_sha = c91d2da5fe38c8b8ecf6bd3fb6c3ee9e0141a3c8
    diff_fingerprint = c91d2da5fe38c8b8ecf6bd3fb6c3ee9e0141a3c8:aad2351a429714f07e759304400087c2f0a5ccc33a0111b9532153bf86c50b23

查看：`git diff 6c5b170..c91d2da -- backend/ reports/api-samples/`

这个范围**包含**第 1 轮的后端交付**和**本次返工修复。你审的是两者合起来的最终形态，
不是只审返工那三个文件。

`frontend/**` 不在你的范围内（前端由另一份已 ACCEPT 的评审覆盖）——除非你发现后端
wire 形与前端消费不一致，那属跨 seam 缺陷，应当报告。

## 本轮返工的来龙去脉（你要独立复核它是否真的修好了）

Review-2（GPT-5 Codex）在旧范围上判 REWORK，一条 P2：

> `RecordTransportExecutor.execute` 调 `validate_order_params` 时没传
> `step_size`/`min_qty`/`max_qty`，而 `wire_constraints.py` 已实现这三项检查，
> 因此违反交易对网格/上下限的数量在离线仍被模拟成 success。

修复者报告的根因比该 finding **更深一层**：`compute_preflight` 产出的
`snapshot_record` 里**根本没有 min/max**，只有 step，所以 record transport 就算想传
也无从取值。修法是 `compute_preflight` 用既有的 `_qty_bounds` 把每腿有效 min/max
additive 写入 snapshot，再由新增的 `_leg_qty_filters` 消费。

**请你独立判断**：
- 这个根因描述是否属实；
- 修复是否真正关闭了 finding，而不是只在表面接了个参数；
- `_qty_bounds` 的 MARKET_LOT_SIZE → LOT_SIZE 回退语义是否被正确复用，有没有在别处
  又造了第二套过滤选择规则；
- snapshot 新增四个字段是否真是 additive（无 schema 迁移、无冻结契约变更）。

## 必读原始产物

- `00-task.md`（**验收标准**——见下方特别提醒）
- `10-design.md`（§2.1 S1、§2.3 S3、§2.4b S4b、§2.5 S5、§3 文件边界、§4 冻结契约）
- `11-adr.md`（ADR-H1/H2/H4/H5）
- `12-development-breakdown.md` §2
- `50-review-2.md`（上一轮终审原文与其 P2 finding）
- `40-fix-review-2-s5.md`（修复者报告）
- `60-fix-review-2-s5.dispatch.md`（返工包，含被要求的约束）
- `19-r4-diff-reconciliation-rework1.md`（bookkeeper 对返工的对账）
- `16-r4-diff-reconciliation.md`（第 1 轮对账）
- `60-test-output.txt`（合并态复跑：983 backend / 122 frontend / 72 protocol）
- `18-live-acceptance-findings.md`（2026-07-27 实盘验收发现，含**不属于本 stage**的
  四条缺陷 F-1..F-4——不要把它们计入本轮）
- 实际源码

修复者报告、两份 R4 对账、上一轮终审**都是被评审的证据，不是权威**。与代码矛盾时以
代码为准并报告。

## 特别提醒：以验收标准为准，不要只对照设计文档

上一轮这道门就是在这一点上失手的：它对照 `10-design.md §2.5` 的措辞（读起来像"网格
检查是可选的"），把问题判成了可接受的残余风险；而 `00-task.md` 的 S5 验收标准写的是

> The offline transport rejects parameters that Binance would reject:
> `newClientOrderId` length and character set, and quantity/price precision
> **against the symbol filters already loaded**.

当设计文档与验收标准不一致时，**验收标准是要求，设计是实现该要求的方案**。请对每一项
（S1/S3/S4b/S5）都回到 `00-task.md` 的验收标准逐条核对，而不是止步于"实现与设计一致"。

## 评审重点（逐条给结论）

1. **S5 是否真正满足验收标准**：离线 transport 现在能否拒绝违反**已加载 symbol
   filters** 的数量？新增测试是**端到端行为断言**还是只测了校验器本身？违规时是否
   两腿都 REJECTED、`constraint_violations` 有证据、且**不模拟成交**？
2. **ADR-H4 是否被破坏**：`wire_constraints` 绝不能被 import 或挂接到
   `backend/services/live_hedge_executor.py`、`hedge_open_live_client.py` 或任何真实
   发送路径。请实际 grep 确认。
3. **S1 id 推导**：恒 ≤36、双腿互异、全局唯一、推导点唯一、仍支撑 ADR-2 的仅凭
   clientOrderId 对账。
4. **S3**：CAS 与审计行是否真在同一事务；`confirm` 字面量能否被 `1`/`"true"`/`[]`
   等 truthy 值绕过；`version` 是否排除 bool；全新安装是否默认关闭。
5. **S4b 探针三态**：`None`（读取失败）绝不能被误判为 `False` 而拦截建卡。
6. **A-5**：`build_*_order_params` 用 `fmt_decimal` 是否正确、有无精度回归。
7. **M-1**：`start_gate_changed` 审计 payload 的键集合断言是否真的钉住了"不会被前端
   `extractHedgeAttempts` 当作 attempt 渲染"这个隐含依赖。
8. **文件边界**：`live_hedge_executor.py`、`hedge_open_live_client.py`、
   `binance_signing.py`、`scheduler.py`、`config.py` 是否零改动。
9. **冻结契约**：status 状态词表、entries 投影词表、settings doc 语义是否被改动
   （additive 允许，语义变更不允许）。
10. **安全**：是否引入真实 POST、凭据访问、私有请求、服务启动，或削弱了"三道实盘
    授权彼此独立"的结构。

## 严禁

- 不要评审前端 diff（除非跨 seam 不一致）。
- 不要把 F-1..F-4（实盘验收发现，已归入独立新 stage）计入本轮。
- 不要要求超出本 stage 范围的改动（smooth 模式、自动平仓、1000x 前缀归一化、把校验器
  挂到 live 路径——最后一项是 ADR-H4 已闭合的决策）。

## 输出格式

先写中文评审正文（每条重点的结论 + 证据路径/行号），然后**以严格 JSON 结尾**，符合
`schemas/review-verdict.schema.json`：

必需字段：`schema_version`(=1)、`stage_id`、`role`(="first_reviewer")、`model`、
`verdict`(ACCEPT|REWORK|BLOCKED)、`diff_fingerprint`(逐字用上面**新**的那串)、
`reviewer_prior_involvement`(="none")、`reviewed_artifacts`、`findings`、
`required_fixes`、`next_action`。

`findings` 每项必须含：`severity`(P0|P1|P2|P3)、`title`、`evidence`、`impact`、
`recommendation`；可选 `file`、`line`。

**若 verdict = REWORK，必须额外提供 `fix_start_prompt`**。

JSON 必须可被 `json.loads` 直接解析。footer 放在 JSON 之前。

当前 Session ID: 报告你的 provider-native id，取不到就写 unavailable 并说明原因
Session ID 来源: runtime_env | hook_payload | cli_output | transcript_path | active_session_registry | operator | unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-live-hardening-v1/31-review-1-backend-r2.md
本地北京时间: 用本地 date 命令取
下一步模型: bookkeeper
下一步任务: 归档本评审原始输出并记录 verdict
```

Current dispatch executor: **human operator**. The bookkeeper does not execute
Claude commands or relay this prompt to a model.

当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native session id)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-live-hardening-v1/31-review-1-backend-r2.dispatch.md
本地北京时间: 2026-07-28 00:45:00 CST
下一步模型: human operator
下一步任务: 在全新只读 Claude Opus 4.8 会话执行本 packet，范围 6c5b170..c91d2da

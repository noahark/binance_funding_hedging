# Review-1 Dispatch — Backend — Hedge Open Live Hardening v1

Human operator: run this in a fresh **read-only `grok-4.5`** session.

```bash
grok --cwd "/Users/ark/Desktop/ai code/funding_hedging" --model grok-4.5 \
  --permission-mode plan --prompt-file <this-prompt-body-file>
```

Save the session's complete unedited output as:
`reports/agent-runs/2026-07-hedge-open-live-hardening-v1/30-review-1-backend.md`

**Two separate sessions.** This packet and `30-review-1-frontend.dispatch.md`
must not run in the same session — one reviewer reviews one task.

**Grok as Review-1 is user-enabled** for this stage; see
`15-user-authorized-grok-review-1.md`. Note the registry's Grok commands are
stale (they pin models that no longer exist), which is why the command above is
written out explicitly rather than referenced.

**If the verdict JSON is missing or fails the schema**: retry this gate once. If
it fails again, the fallback to Claude Opus 4.8 for this gate is pre-authorized —
record the reason and the invalid-output path.

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

你是 stage `2026-07-hedge-open-live-hardening-v1` 的 **review-1 后端评审员**。

## 评审范围（只审后端任务）

固定 diff 范围（不要用移动的 HEAD）：

    base_sha = 6c5b17002cab189d752177b447ff576356998f58
    head_sha = 319d8317bdf180750197c95078d2ae6c60e6badc
    diff_fingerprint = 319d8317bdf180750197c95078d2ae6c60e6badc:2a457c0f559fec81cfba8b9d59602c8630bbec73d7b86b28dddab12c4e554efd

查看方式：`git diff 6c5b170..319d831 -- backend/ reports/api-samples/`

本次范围内的后端改动（任务 A，实现者 claude_glm）：
- backend/hedge_open_tasks/{executor.py,service.py,store.py,domain.py}
- backend/hedge_open_tasks/wire_constraints.py（新建）
- backend/services/hedge_preflight_provider.py
- backend/app/server.py
- backend/tests/test_hedge_*.py、backend/tests/test_live_hedge_executor.py
- reports/api-samples/2026-07-hedge-open-live-hardening-v1/client-order-id-cap.md（新建）

`frontend/index.html` 与 `frontend/self-check.js` 的改动属于**并行的前端任务**，
由另一位评审员独立评审，**不在你的范围内**——除非你发现后端 wire 形与前端消费不一致，
那属于跨 seam 缺陷，应当报告。

## 必读原始产物

- reports/agent-runs/2026-07-hedge-open-live-hardening-v1/00-task.md（验收标准）
- reports/agent-runs/2026-07-hedge-open-live-hardening-v1/10-design.md
  （§2.1 S1、§2.3 S3、§2.4b S4b、§2.5 S5、§3 文件边界、§4 冻结契约、§6 测试策略、§8 风险）
- reports/agent-runs/2026-07-hedge-open-live-hardening-v1/11-adr.md（ADR-H1/H2/H4/H5）
- reports/agent-runs/2026-07-hedge-open-live-hardening-v1/12-development-breakdown.md §2
- reports/agent-runs/2026-07-hedge-open-live-hardening-v1/13-implementation-backend.dispatch.md
  （任务边界与 bookkeeper 追加的 M-1/M-2 检查点）
- reports/agent-runs/2026-07-hedge-open-live-hardening-v1/20-implementation-backend.md（实现者报告）
- reports/agent-runs/2026-07-hedge-open-live-hardening-v1/16-r4-diff-reconciliation.md（bookkeeper 对账）
- reports/agent-runs/2026-07-hedge-open-live-hardening-v1/60-test-output.txt（合并态测试输出）
- 上一 stage 的冻结契约：reports/agent-runs/2026-07-hedge-open-real-api-v1/11-adr.md
- 实际源码

实现者报告与 bookkeeper 对账都是**被评审的证据**，不是权威。发现与它们矛盾之处，以
代码与 diff 为准并报告。

## 评审重点（来自 12-breakdown §2 的 review focus，逐条给结论）

1. **S1 id 推导**：`hg{attempt_id}s|p` 是否恒 ≤36、双腿互异、全局唯一；推导点是否
   仍然唯一（record 与 live 共用，未被复制出第二份规则）；是否仍支撑 ADR-2 的
   「仅凭 clientOrderId 对账」路径；历史 38 字符记录不迁移的论证是否成立。
2. **S3 CAS 与审计原子性**：`set_start_gate_cas` 的 rowcount/version 判定是否正确；
   审计行与闸门 UPDATE 是否真的在**同一事务**；失败路径是否会留下"改了闸门没留审计"
   或反之的窗口。
3. **confirm 字面量不可被绕过**：`1`、`"true"`、`[]` 等 truthy 值必须 400；
   `version` 必须排除 bool。请实际核对代码而非只看测试名。
4. **S4b 探针三态**：`None`（读取失败）绝不能被误判为 `False`（确定不存在）而拦截建卡；
   `-1121` 判 False 的依据是否可靠；`DisabledPreflightProvider`（dry-run）是否真的零网络。
5. **S5 校验器**：regex 与 api-samples 记录页是否一致；record transport 违规路径是否
   吞掉 `constraint_violations` 证据；纯度守卫（test_hedge_purity.py）是否对新模块生效；
   「pre-fix S1 推导必须离线失败」的回归测试是否真的钉住了**这一类**缺陷而不只是钉住
   36 这个数字。
6. **A-5**：`build_*_order_params` 从 `str(quantity)` 改为 `fmt_decimal` 是否正确、
   是否有精度或格式回归。
7. **M-1**：`start_gate_changed` 审计 payload 的键集合断言是否真的钉住了
   「不会被前端 extractHedgeAttempts 当作 attempt 渲染」这个隐含依赖。
8. **文件边界**：是否有改动越出 13 号 packet 的允许清单，尤其
   `backend/services/live_hedge_executor.py`、`hedge_open_live_client.py`、
   `binance_signing.py`、`scheduler.py`、`config.py` 是否零改动。
9. **冻结契约**：是否有任何 real-api-v1 冻结契约被修订（尤其 entries 投影词表与
   status 状态词表）。
10. **安全**：是否引入了任何真实 POST、凭据访问、私有请求、服务启动，或改变了
    「三道实盘授权彼此独立」的结构。

## 严禁

- 不要评审前端 diff（除非跨 seam 不一致）。
- 不要要求超出本 stage 范围的改动（smooth 模式、自动平仓、1000x 前缀归一化、
  live 路径挂校验器——最后一项是 ADR-H4 已闭合的决策，若你不同意，作为 P3 意见提出，
  不要作为 REWORK 理由）。
- 不要因为"实现者报告写得好"就降低核查强度。

## 输出格式

先写中文评审正文（每条重点的结论 + 证据路径/行号），然后**以严格 JSON 结尾**，
符合 `schemas/review-verdict.schema.json`：

必需字段：`schema_version`(=1)、`stage_id`、`role`(="first_reviewer")、`model`、
`verdict`(ACCEPT|REWORK|BLOCKED)、`diff_fingerprint`(逐字用上面那串)、
`reviewer_prior_involvement`(="none")、`reviewed_artifacts`(至少一项)、`findings`、
`required_fixes`、`next_action`。

`findings` 每项必须含：`severity`(P0|P1|P2|P3)、`title`、`evidence`、`impact`、
`recommendation`；可选 `file`、`line`。

**若 verdict = REWORK，必须额外提供 `fix_start_prompt`**：一段可直接发给修复实现者的
完整提示词，保留原始产物路径、发现、必须修复项、文件边界、精确测试命令与验收标准。

JSON 必须可被 `json.loads` 直接解析。footer 放在 JSON 之前。

当前 Session ID: 报告你的 provider-native id，取不到就写 unavailable 并说明原因
Session ID 来源: runtime_env | hook_payload | cli_output | transcript_path | active_session_registry | operator | unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-live-hardening-v1/30-review-1-backend.md
本地北京时间: 用本地 date 命令取
下一步模型: bookkeeper
下一步任务: 归档本评审原始输出并记录 verdict
```

Current dispatch executor: **human operator**. The bookkeeper does not execute
Grok commands or relay this prompt to a model.

当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native session id)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-live-hardening-v1/30-review-1-backend.dispatch.md
本地北京时间: 2026-07-27 20:58:00 CST
下一步模型: human operator
下一步任务: 在全新只读 grok-4.5 会话执行本 packet，原样保存输出到 30-review-1-backend.md

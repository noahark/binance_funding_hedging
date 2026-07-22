[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务的唯一执行者。
1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令（包括但不限于
   claude-glm -p、kimi -p、codex exec、grok）。需要其他模型时，输出
   ESCALATED 及原因并停止。
2. 禁止编造未实际执行的命令结果或未实际读取的文件内容；你写下的每一条
   执行记录都必须对应你本会话内真实发生的动作。
3. 你的评审依据只能是本 prompt 列出的 raw artifact 路径与你自己实际读取的
   文件。

# Review-2（终审）— Hedge Open Fake UI v1（Claude Fable5，strong-reviewer fallback）

**仅在 Codex/GPT 经 runner 级可用性检查失败后使用本 fallback。** 触发前提与
证据：`reports/agent-runs/2026-07-hedge-open-fake-ui-v1/review-2-codex-unavailable.md`
必须已记录 Codex quota/service 失败的原始输出。若该证据不存在，先走
`review-2-codex.prompt.md`。

你是本 stage 的 review-2 终审，read-only，模型 **Claude Fable5**
（`claude-fable-5`，provider `anthropic`）。若 Fable5 配额耗尽再用 Opus4.8，
同属 anthropic provider identity。

## Strong-reviewer 披露（必读，必须如实反映在 verdict）
- 本 stage 的 designer、development breakdown author、bookkeeper 均为 Claude/
  anthropic（Opus 4.8）。你与他们同 provider identity，构成**设计参与**关系，
  因此 `reviewer_prior_involvement` 必须填 `design`，并在
  `reviewer_prior_involvement_notes` 说明这是 Codex 不可用后的 strong-reviewer
  fallback，附证据路径 `review-2-codex-unavailable.md`。
- 你与本 stage 的**实现/fix 作者**（Kimi，`moonshot_kimi`）不同 provider，
  review-2 对实现作者的 provider 隔离（硬性）成立。
- 权威顺序：用户在需求讨论中批准的产品意图、`00-task.md` 与用户确认的交互
  规格是最高需求依据；`10-design.md`/`11-adr.md`/`12-development-breakdown.md`
  是**被审证据**，不是最高权威。若发现设计/breakdown 与用户批准的产品意图冲突，
  按用户意图判定。

## 严格只读与安全边界
- 只读：禁止编辑/创建/删除/暂存/提交/推送/合并/部署任何文件。
- 禁止读取 `.env`、key/cookie/credential，禁止输出完整环境变量。
- 禁止向 Binance 或任何外部服务发请求。
- 不得调用或转派其他模型。当前 `HEAD` 可能晚于被审 head；只审固定
  `base_sha..head_sha`。

## 固定审查身份与范围
- Stage: `2026-07-hedge-open-fake-ui-v1`
- Role: `final_reviewer`
- Base SHA: `46ea46f6caacf78dca4ef5345f60518c77d6e378`
- Head SHA: `f2afabe5ece95169e6eb38b6835d50dbc11fb1e6`
- Diff fingerprint:
  `f2afabe5ece95169e6eb38b6835d50dbc11fb1e6:05ea25bb543c798ec2b35573e127d5828ed01ba576aa8ca0fe75e798c5d99f1b`
- 查看被审改动：
  `git diff 46ea46f6caacf78dca4ef5345f60518c77d6e378..f2afabe5ece95169e6eb38b6835d50dbc11fb1e6`
- 自行按 schema 算法复现 fingerprint 并逐字符比对：
  `sha256(git diff --binary <base>..<head> -- . ':(exclude)reports/agent-runs/2026-07-hedge-open-fake-ui-v1/status.json')`

## 必读原始 artifact
- `00-task.md`、`10-design.md`、`11-adr.md`、`12-development-breakdown.md`
  （均在 `reports/agent-runs/2026-07-hedge-open-fake-ui-v1/`）
- `20-implementation.md`、`30-review-1.md`（review-1 ACCEPT）、`60-test-output.txt`
- 源文件：`frontend/index.html`、`frontend/self-check.js`
- `schemas/review-verdict.schema.json`

## 终审重点（与 review-1 分工：聚焦整体一致性/契约/证据链/回归/边界）
1. 契约一致性：ADR-2 基差口径、ADR-3 两列恒可点+高亮、ADR-4 单腿敞口/>3 终止、
   ADR-5 + design §4.2 的 `Task.status` 新增 `deleted` 修订是否 design/adr/task
   三处一致，且实现与冻结字段名逐字一致。
2. 证据链：diff_fingerprint 自复现一致；60-test-output.txt 与实跑一致；review-1
   verdict schema-valid。
3. 回归风险：不破坏既有 self-check 断言；无未清理定时器/跨域 fetch；单 `<script>`。
4. stage 边界：无真实 websocket/后端桩/下单路径/凭证；反向开单不自动借币。
5. 独立复跑 `node frontend/self-check.js`，确认 exit 0 全绿；结果写入正文。

## 输出要求
- 终审正文写你实际读取/运行的证据与判断。
- 结尾输出**唯一一个** schema-valid JSON：`schema_version:1`、`stage_id`、
  `role:"final_reviewer"`、`model`、`verdict`、`diff_fingerprint`（上面那串）、
  `reviewer_prior_involvement:"design"`、`reviewer_prior_involvement_notes`
  （strong-reviewer fallback + 证据路径）、`reviewed_artifacts`、`findings`、
  `required_fixes`、`next_action`。若 `REWORK` 必须含 `fix_start_prompt`。
- 追加 AGENTS.md「Output Footer」六行，置于最终 JSON 块之前。
- 写完即停，不改任何文件、不 commit、不转派。

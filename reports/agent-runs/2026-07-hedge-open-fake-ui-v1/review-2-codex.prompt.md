[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务的唯一执行者。
1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令（包括但不限于
   claude-glm -p、kimi -p、codex exec、grok）。需要其他模型时，输出
   ESCALATED 及原因并停止。
2. 禁止编造未实际执行的命令结果或未实际读取的文件内容；你写下的每一条
   执行记录都必须对应你本会话内真实发生的动作。
3. 你的评审依据只能是本 prompt 列出的 raw artifact 路径与你自己实际读取的
   文件。

# Review-2（终审）— Hedge Open Fake UI v1（Codex/GPT，首选）

你是本 stage 的 review-2 终审，read-only。模型 GPT/Codex（`openai`），未参与
本 stage 的设计/breakdown/实现，`reviewer_prior_involvement` 如实填 `none`。
实现者 Kimi（`moonshot_kimi`）、review-1 Claude-GLM（`zhipu_glm`）、breakdown/
designer/bookkeeper Claude（`anthropic`）均与你不同 provider，隔离成立。

## 终审定位（与 review-1 分工）
review-1 已 ACCEPT 并逐条核过低级缺陷。你**不必**重复抓低级问题；聚焦：
整体一致性、契约冻结符合性、证据链完整性、回归风险、以及 stage 边界（这是
纯前端 fake，不得有真实网络/下单/websocket）。你仍须独立复核 review-1 的
ACCEPT 是否站得住。

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
- 自行按 schema 算法复现 fingerprint 并与上值逐字符比对：
  `sha256(git diff --binary <base>..<head> -- . ':(exclude)reports/agent-runs/2026-07-hedge-open-fake-ui-v1/status.json')`

## 必读原始 artifact
- `reports/agent-runs/2026-07-hedge-open-fake-ui-v1/00-task.md`
- `reports/agent-runs/2026-07-hedge-open-fake-ui-v1/10-design.md`
- `reports/agent-runs/2026-07-hedge-open-fake-ui-v1/11-adr.md`
- `reports/agent-runs/2026-07-hedge-open-fake-ui-v1/12-development-breakdown.md`
- `reports/agent-runs/2026-07-hedge-open-fake-ui-v1/20-implementation.md`
- `reports/agent-runs/2026-07-hedge-open-fake-ui-v1/30-review-1.md`（review-1 ACCEPT verdict）
- `reports/agent-runs/2026-07-hedge-open-fake-ui-v1/60-test-output.txt`
- 源文件：`frontend/index.html`、`frontend/self-check.js`
- `schemas/review-verdict.schema.json`

## 终审重点
1. 契约一致性：ADR-2 基差口径、ADR-3 两列恒可点+高亮、ADR-4 单腿敞口/>3 终止、
   ADR-5 + design §4.2 的 `Task.status` 新增 `deleted` 契约修订是否在 design/
   adr/task 三处一致记录，且实现与冻结字段名（Task/Fill/localStorage 键）逐字一致。
2. 证据链：diff_fingerprint 自复现一致；60-test-output.txt 与实跑一致；review-1
   verdict schema-valid。
3. 回归风险：新增逻辑是否破坏既有 self-check 断言、是否引入未清理定时器或跨域
   fetch；单 `<script>` 块约束。
4. stage 边界：无真实 websocket/后端桩/下单路径/凭证；反向开单不自动借币。
5. 独立复跑 `node frontend/self-check.js`，确认 exit 0 且全绿；把实际结果写入正文。

## 输出要求
- 终审正文写你实际读取/运行的证据与判断。
- 结尾输出**唯一一个** schema-valid JSON（`schemas/review-verdict.schema.json`）：
  `schema_version:1`、`stage_id`、`role:"final_reviewer"`、`model`、
  `verdict`（ACCEPT/REWORK/BLOCKED）、`diff_fingerprint`（上面那串）、
  `reviewer_prior_involvement:"none"`、`reviewed_artifacts`、`findings`、
  `required_fixes`、`next_action`。若 `REWORK` 必须含 `fix_start_prompt`。
- 追加 AGENTS.md「Output Footer」六行，置于最终 JSON 块之前。
- 写完即停，不改任何文件、不 commit、不转派。

[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务的唯一执行者。
1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令（包括但不限于
   claude-glm -p、kimi -p、codex exec、grok）。需要其他模型时，输出
   ESCALATED 及原因并停止。
2. 禁止编造未实际执行的命令结果或未实际读取的文件内容；你写下的每一条
   执行记录都必须对应你本会话内真实发生的动作。
3. 你的评审依据只能是本 prompt 列出的 raw artifact 路径与你自己实际读取的
   文件。

# Review-1 — 任务 hedge-fe（fresh-context Claude-GLM，交叉评审前端）

你是 hedge-fe 的 review-1，fresh-context Claude-GLM（`zhipu_glm`,
`glm-5.2[1m]`），只读。hedge-fe 实现者为 Kimi（`moonshot_kimi`），与你不同
provider，交叉评审成立。**披露**：你是本 stage 另一任务 hedge-be 的实现者，但
**未参与 hedge-fe** 的设计/breakdown/实现，故审 hedge-fe 无自审冲突；verdict
`reviewer_prior_involvement` 填 `none`，并在 notes 说明这层 parallel 交叉关系。

## 严格只读与安全边界
- 只读：禁止编辑/创建/删除/暂存/提交/推送/合并/部署。
- 禁止读 `.env`/key/cookie/credential，禁止输出完整环境变量。
- 禁止向任何外部服务发请求；本轮前端不应有真实外部网络（self-check 用同源
   mock）——发现真实跨域即高优先级发现。
- 不得转派其他模型。只审固定 `base_sha..head_sha`。

## 固定审查身份与范围
- Stage `2026-07-hedge-open-live-v1`，Task `hedge-fe`，Role `first_reviewer`
- Base `6639b0025682f406f9a726104ef8d3b9e6f8fadd`
- Head `b773a470de62053207b85e58148bbf7c285026fd`
- Fingerprint `b773a470de62053207b85e58148bbf7c285026fd:d904f8f08e787a238dac2cf1790a01fca03279e7c213c4d429b6a6f61857bd28`
- 看改动：`git diff 6639b002..b773a470`
- **聚焦 hedge-fe 文件**：`frontend/index.html`、`frontend/self-check.js`。
  （后端 diff 属 hedge-be，不在你的评审范围。）

## 必读 artifact
- `reports/agent-runs/2026-07-hedge-open-live-v1/`
  `{10-design.md（§11）,12-development-breakdown.md（§3 冻结 API、§5）,
  20-implementation-hedge-fe.md,r4-reconciliation.md,60-test-output.txt}`
- 源码：`frontend/index.html`、`frontend/self-check.js`
- `schemas/review-verdict.schema.json`

## 审查重点（对照 12-breakdown §5/§7）
1. **消费 §3 API 逐字**：端点路径、请求体字段、Task/Fill/Position JSON 字段名、
   错误码（`insufficient_balance` 按 direction 弹 stage-1 文案 / `invalid_field`
   / `invalid_state`）。
2. **R4-001 修复到位**：`POST /api/hedge-open-tasks` 的 `single_amount` 现送
   **decimal string**（`normalizeHedgeAmount`，`^[0-9]+(\.[0-9]+)?$`，`.5`→`0.5`，
   不走 float 往返）；`target_n` 整数；self-check 有 single_amount-is-string 断言。
3. **UI 保真**：`立即开单`→真实 POST；任务卡/筛选/软删除(`deleted`)/`成交1次`/
   `立即成交所有`/`暂停`/`启动`→对应端点；持仓表→positions 端点；执行徽标读
   settings（dry-run/live+Start）；`平滑开单` disabled+`下一轮`；`exposure_alert`
   能渲染。
4. **self-check 纪律**：全部新逻辑在第一个 `<script>` 块；既有 `[PASS]` 全保留；
   无新增跨域 fetch/未清理定时器；mock 是同源。留意实现报告提到的 mock
   引用别名修复是否正确、断言是否实质。
5. 独立运行 `node frontend/self-check.js`，确认 exit 0 全绿；结果写进正文（不得编造）。

## 输出
- 评审正文写实际读取/运行的证据与发现。
- 结尾唯一一个 schema-valid JSON（`schemas/review-verdict.schema.json`）：
  `schema_version:1`、`stage_id`、`role:"first_reviewer"`、`model`、`verdict`、
  `diff_fingerprint`（上串）、`reviewer_prior_involvement:"none"`、
  `reviewer_prior_involvement_notes`（披露 parallel 交叉关系）、
  `reviewed_artifacts`、`findings`、`required_fixes`、`next_action`。REWORK 必含
  `fix_start_prompt`。
- 追加 AGENTS.md「Output Footer」六行，置于最终 JSON 前。写完即停，不改任何文件。

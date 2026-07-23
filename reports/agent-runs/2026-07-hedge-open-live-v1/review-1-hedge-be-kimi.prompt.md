[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务的唯一执行者。
1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令（包括但不限于
   claude-glm -p、kimi -p、codex exec、grok）。需要其他模型时，输出
   ESCALATED 及原因并停止。
2. 禁止编造未实际执行的命令结果或未实际读取的文件内容；你写下的每一条
   执行记录都必须对应你本会话内真实发生的动作。
3. 你的评审依据只能是本 prompt 列出的 raw artifact 路径与你自己实际读取的
   文件。

# Review-1 — 任务 hedge-be（fresh-context Kimi，交叉评审后端）

你是 hedge-be 的 review-1，fresh-context Kimi（`moonshot_kimi`,
`kimi-code/kimi-for-coding`），只读。hedge-be 实现者为 Claude-GLM（`zhipu_glm`），
与你不同 provider，交叉评审成立。**披露**：你是本 stage 另一任务 hedge-fe 的实现者，
但**未参与 hedge-be** 的设计/breakdown/实现，故审 hedge-be 无自审冲突；verdict
`reviewer_prior_involvement` 填 `none`，并在 notes 说明这层 parallel 交叉关系。

## 严格只读与安全边界
- 只读：禁止编辑/创建/删除/暂存/提交/推送/合并/部署。
- 禁止读 `.env`/key/cookie/credential，禁止输出完整环境变量。
- 禁止向 Binance 或任何外部服务发请求。本轮是 dry-run record transport，代码/
  测试里**不应有**真实网络下单路径——若发现即高优先级发现。
- 不得转派其他模型。只审固定 `base_sha..head_sha`，不以移动 HEAD 替代。

## 固定审查身份与范围
- Stage `2026-07-hedge-open-live-v1`，Task `hedge-be`，Role `first_reviewer`
- Base `6639b0025682f406f9a726104ef8d3b9e6f8fadd`
- Head `b773a470de62053207b85e58148bbf7c285026fd`
- Fingerprint `b773a470de62053207b85e58148bbf7c285026fd:d904f8f08e787a238dac2cf1790a01fca03279e7c213c4d429b6a6f61857bd28`
- 看改动：`git diff 6639b002..b773a470`
- **聚焦 hedge-be 文件**：`backend/hedge_open_tasks/**`、`backend/app/server.py`
  （仅 hedge 路由）、`backend/tests/test_hedge_*.py`。（前端 diff 属 hedge-fe，
  不在你的评审范围。）

## 必读 artifact
- `reports/agent-runs/2026-07-hedge-open-live-v1/`
  `{00-task.md,10-design.md,11-adr.md,12-development-breakdown.md,design-inputs.md,
  20-implementation-hedge-be.md,r4-reconciliation.md,60-test-output.txt}`
- 摸排事实：`reports/api-samples/2026-07-hedge-open-live-v1/order-endpoints-filters-recon.md`
- 源码：`backend/hedge_open_tasks/**`、`backend/app/server.py`、`backend/tests/test_hedge_*.py`
- `schemas/review-verdict.schema.json`

## 审查重点（对照 12-breakdown §7）
1. **共同网格取整**（ADR-2/§4）：两腿同一 `q_common = floor(single_amount,
   lcm(step_spot,step_perp))`，decimal 定点；违反任一腿 min/max/notional 拒绝；
   **绝不分别取整**。这是首要正确性风险。
2. **安全闸门**（ADR-5/§9）：真实 POST 仅在 `APP_HEDGE_EXECUTOR=live` 且全局
   Start 开启且 preflight 通过时可达；有测试证明双闸门未开时不可达；record
   transport 不含密钥/签名、不发网络 POST。
3. **单腿敞口状态机**（ADR-4/§7）：不只信 POST 返回；按 client id 查
   order/trades/positionRisk；一腿成交另一腿否→exposure_alert+暂停+记录，不自动
   补/平；>3 失败终止；不重发同 client id。
4. **NO_SIDE_EFFECT/反向不自动借币**（ADR-3）：两方向现货腿 NO_SIDE_EFFECT；
   反向 preflight 用 `crossMarginFree(base)`，非 maxBorrowable。
5. **API 契约**（§3 逐字）：端点/字段名/错误码/软删除；`single_amount` 收
   decimal string、`target_n` 收 int（R4-001 已对齐）。
6. **契约保真 + 无回归**：borrow 逻辑零改动；无真实网络；模块结构镜像
   borrow_tasks。
7. 独立运行 `python -m pytest backend/tests -q`，确认全绿；结果写进正文（不得编造）。

## 输出
- 评审正文写实际读取/运行的证据与发现。
- 结尾唯一一个 schema-valid JSON（`schemas/review-verdict.schema.json`）：
  `schema_version:1`、`stage_id`、`role:"first_reviewer"`、`model`、`verdict`、
  `diff_fingerprint`（上串）、`reviewer_prior_involvement:"none"`、
  `reviewer_prior_involvement_notes`（披露 parallel 交叉关系）、
  `reviewed_artifacts`、`findings`、`required_fixes`、`next_action`。REWORK 必含
  `fix_start_prompt`。
- 追加 AGENTS.md「Output Footer」六行，置于最终 JSON 前。写完即停，不改任何文件。

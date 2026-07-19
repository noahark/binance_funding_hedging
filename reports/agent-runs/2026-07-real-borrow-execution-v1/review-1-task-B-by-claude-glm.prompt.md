<!-- RECEIPT — bookkeeper fills this metadata after the human operator executes the packet.
status: pending
target_model: claude_glm / glm-5.2 (fresh plan/read-only review session)
adapter_cmd: claude-glm --model glm-5.2 --permission-mode plan -p "$(cat reports/agent-runs/2026-07-real-borrow-execution-v1/review-1-task-B-by-claude-glm.prompt.md)"
started_at:
completed_at:
session_id:
session_id_source:
output: reports/agent-runs/2026-07-real-borrow-execution-v1/30-review-1-frontend.md
next_dispatch: ACCEPT → task-A Review-1 / then stage Review-2; REWORK → Task B scope-contained fix
-->

--- PROMPT BODY (immutable from this line) ---

你是一个全新的、plan/read-only 的 Claude-GLM 会话，担任正式 `reviewer_1`。
审阅 stage `2026-07-real-borrow-execution-v1` 的 **Task B 前端交付**。你没有参与
Task B 的实现或修复；不得复用该任务实现或嵌入预审会话。Task A 由 Claude-GLM 的
另一个会话实现，但它不是本次被审的代码；本次严格只审 Task B 的 committed range。

## 只读与范围

- 禁止写文件、改工作树、提交、网络请求、签名请求或访问凭据。
- 只审以下固定提交范围，不要使用移动的 `HEAD`：
  - base_sha: `40efb028ead50d667bb32dbe10e9af6a7d77409e`
  - head_sha: `4bab47d250b739539c0c2f09786baa75bba25d6d`
  - 预期 task fingerprint:
    `4bab47d250b739539c0c2f09786baa75bba25d6d:5f815252ed8e55c7a3aa97efa7a8f4db700abd27e2e1bca998b2af923b728a81`
- Task B 允许范围仅为 `frontend/index.html` 与 `frontend/self-check.js`。
- 任何范围外的 Harness evidence commit 都不是 Task B 产品 diff 的一部分；不要因
  `head_sha` 之后的提交产生误判。

## 必做独立核验

1. 重算 Task B 指纹（`status.json` 在 hash 输入中排除）：

   ```sh
   git diff --binary 40efb028ead50d667bb32dbe10e9af6a7d77409e..4bab47d250b739539c0c2f09786baa75bba25d6d -- . ':(exclude)reports/agent-runs/2026-07-real-borrow-execution-v1/status.json' | shasum -a 256
   ```

   将输出 hash 与预期 fingerprint 的冒号后部分比较；不一致必须 `BLOCKED`。
2. 检查 `git diff --name-only <base>..<head>` 只含两个允许的前端文件，并实际阅读
   diff、当前 UI 源码与后端 frozen schemas/route contract。
3. 阅读下列原始材料（不能只依赖本 prompt 或任何书面摘要）：
   - `AGENTS.md`、`workflows/templates/stage-delivery.yaml` 的 Review-1 部分；
   - `00-task.md`、`10-design.md`、`11-adr.md`、`12-development-breakdown.md`、
     `06-direction-synthesis.md`、`13-user-decisions-and-contract-amendment.md`；
   - `status.json`、`20-implementation.md`、`20-implementation-frontend.md`、
     `60-test-output.txt`、`60-test-output-frontend.txt`；
   - `schemas/api/borrow-tasks/**` 与 `backend/app/server.py` 的 route wiring；
   - 原始嵌入审查链：`embedded-review-B-round1-retry-1.raw-output.md`、
     `61-r4-diff-reconciliation.txt`。
4. 独立重跑：

   ```sh
   node frontend/self-check.js
   git diff --check
   ```

## 重点验收

- 前端只是同源后端 API 的渲染/输入入口，绝不成为 scheduler 或借币执行权威；市场确认
  `POST /api/borrow-tasks` 后直接展示返回的 `borrowing` task，不要求二次 Start。
- start/pause/delete/edit、decimal interval GET/PUT、乐观 version、就近 error detail、
  top-level「借币任务｜借币日志」tab、任务筛选、最新结果五类中文标签与 unknown block
  徽标/按钮矩阵，均严格符合 frozen contract。
- 日志 newest-first 只通过 explicit refresh 和 cursor load-more；没有 log/task execution
  定时器或 client-side borrow success simulation；60 秒 snapshot tick 只能在 borrow view
  激活时刷新任务 cache。所有 fetch 必须同源 frozen route，绝不调用 Binance/外域。
- 界面文案如实表达 backend SQLite persistence 与 A+B execution-disabled；原有市场、抽屉
  和 private read-only 行为无回归；self-check 不是只 mock 成功路径。

## 输出契约（严格）

你的回复先给简短审阅叙述和以下导航 footer，之后给**一个**符合
`schemas/review-verdict.schema.json` 的 JSON object。JSON 必须是回复/保存文件的
最终内容：不用 Markdown 围栏，末尾 `}` 后不得有任何字符或换行。

footer 格式：

当前 Session ID: <provider-native id | unavailable (reason)>
Session ID 来源: <runtime_env | hook_payload | cli_output | transcript_path | active_session_registry | operator | unavailable>
原始输出路径: reports/agent-runs/2026-07-real-borrow-execution-v1/30-review-1-frontend.md
本地北京时间: <用本地 date 命令取得的时间>
下一步模型: <model-or-human>
下一步任务: <specific next task>

JSON 必填：`schema_version: 1`、stage_id、`role: "first_reviewer"`、
`model: "glm-5.2"`、精确 `diff_fingerprint`、
`reviewer_prior_involvement: "none"`、reviewed_artifacts、findings、
required_fixes、next_action。若 `REWORK`，必须同时提供可直接派发的
`fix_start_prompt`，保留原始材料路径、所有 findings、Task B 文件边界、测试命令与
验收标准。严禁把嵌入预审 PASS 当作正式 ACCEPT 的替代。

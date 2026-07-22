[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务的唯一执行者。
1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令（包括但不限于
   claude-glm -p、kimi -p、codex exec、grok）。需要其他模型时，输出
   ESCALATED 及原因并停止。
2. 禁止编造未实际执行的命令结果或未实际读取的文件内容。
3. 你的评审依据只能是本 prompt 列出的 raw artifact 路径与你自己实际读取的文件。

# Review-1 Round 2 — 任务 hedge-be（fresh-context Kimi，交叉评审后端）

你是 hedge-be 的 review-1 第 2 轮，fresh-context Kimi（`moonshot_kimi`），只读。
第 1 轮你给出 REWORK（F-001 P1 / F-002 P2）；Claude-GLM 已按你的 fix_start_prompt
完成 hedge-be fix-1。本轮确认两项必修是否修好、有无回归、其余结论是否仍成立。
若复用终端先 `/clear`。披露同上：你是姊妹任务 hedge-fe 实现者、非 hedge-be 作者，
`reviewer_prior_involvement` 填 `none`，notes 说明 parallel 交叉关系。

## 严格只读与安全边界
同第 1 轮：只读、不读凭据、不发外部请求、不转派；只审固定 `base_sha..head_sha`。

## 固定审查身份与范围（已更新到 fix-1 后）
- Stage `2026-07-hedge-open-live-v1`，Task `hedge-be`，Role `first_reviewer`，Round 2
- Base `6639b0025682f406f9a726104ef8d3b9e6f8fadd`
- Head `bd01eb52e9ec5464bb9f026f5ce666bc883db441`
- Fingerprint `bd01eb52e9ec5464bb9f026f5ce666bc883db441:48b8545d53b607c4ce1f396e0f76e81bc1c95d2cae9147aad695d2933278e22b`
- 看改动：`git diff 6639b002..bd01eb52`（fix-1 增量：`git diff b773a470..bd01eb52`）
- 聚焦 hedge-be 文件：`backend/hedge_open_tasks/**`、`backend/app/server.py`、
  `backend/tests/test_hedge_*.py`。

## 必读
- `reports/agent-runs/2026-07-hedge-open-live-v1/`
  `{30-review-1-hedge-be.md（你的第 1 轮 verdict）,40-fix-1-hedge-be.md（fix 报告）,
  12-development-breakdown.md（§3.1 冻结契约）,60-test-output.txt}`
- 源码：`backend/hedge_open_tasks/{domain,store,service}.py`、
  `backend/tests/test_hedge_{domain,api}.py`
- `schemas/review-verdict.schema.json`

## 本轮重点
1. **F-001 已修**：`GET /api/hedge-open-tasks?status=all` 现在**包含 deleted**，而
   默认（无 status）仍**排除 deleted**，`?status=deleted` 仅含 deleted。核对
   `domain.LIST_ALL` 哨兵 + `store.list_tasks` 分支 + 改写的
   `test_filter_status_for_list_mapping` + 新增 HTTP 级 deleted 可见性测试。
2. **F-002 已修**：`create_task` 对 `mode != "immediate"` 返回 `400
   invalid_field("mode")`；`smooth` 常量保留但不被调度；新增拒绝测试。
3. **无回归**：第 1 轮已通过的项（共同网格取整 ADR-2、安全闸门 ADR-5、单腿敞口
   ADR-4、NO_SIDE_EFFECT ADR-3、其余 §3 契约）仍成立；borrow 零改动。
4. F-003~F-006 是**已记录的 live 轮 follow-up**（见 status.review_1_round_1），
   本轮不要求修，不作为 REWORK 理由。
5. 独立跑 `python -m pytest backend/tests -q`，确认全绿（应 787 passed）；结果写进正文。

## 输出
- 评审正文写实际读取/运行的证据。
- 结尾唯一 schema-valid JSON：`role:"first_reviewer"`、`diff_fingerprint`（上面新串）、
  `reviewer_prior_involvement:"none"`+notes、findings/required_fixes/next_action。
  若两项必修确实修好且无回归 → `ACCEPT`；仍有阻断 → `REWORK` + `fix_start_prompt`。
- 追加 AGENTS.md「Output Footer」六行，置于最终 JSON 前。写完即停。

[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务的唯一执行者。
1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令（包括但不限于
   claude-glm -p、kimi -p、codex exec、grok）。需要其他模型时，输出
   ESCALATED 及原因并停止。
2. 禁止编造未实际执行的命令结果或未实际读取的文件内容。
3. 你的评审依据只能是本 prompt 列出的 raw artifact 路径与你自己实际读取的文件。

# Review-2（整 stage 终审）— Hedge Open Live v1（Codex/GPT，首选）

你是本 stage 的 review-2 终审，read-only，模型 GPT/Codex（`openai`），未参与本
stage 的设计/breakdown/实现/fix，`reviewer_prior_involvement` 填 `none`。实现者
Kimi(hedge-fe)/Claude-GLM(hedge-be, + fix-1)、review-1 双方（Kimi 审 be、Claude-GLM
审 fe）、breakdown/designer/bookkeeper（Claude/anthropic）均与你不同 provider，
隔离成立。

## 终审定位（真实资金 stage，从严）
两个 task 的 review-1 已 ACCEPT（hedge-fe round-1；hedge-be round-2，经 fix-1 修
F-001/F-002）。你**不必**重复抓低级缺陷；聚焦：整体一致性、跨 FE/BE 契约保真、
证据链完整性、回归风险、安全边界。但你须独立复核这些 ACCEPT 是否站得住，尤其
本 stage 有两次跨 seam 接口漂移（R4-001、F-001）——确认再无遗留同类漂移。

## 严格只读与安全边界
- 只读：禁止编辑/创建/删除/提交/部署。禁止读 `.env`/凭据。
- 禁止向 Binance 或任何外部服务发请求。本轮全程 dry-run record transport；代码/
  测试**不应有**真实网络/下单路径——发现即高优先级。
- 不得转派。只审固定 `base_sha..head_sha`。

## 固定审查身份与范围
- Stage `2026-07-hedge-open-live-v1`，Role `final_reviewer`
- Base `6639b0025682f406f9a726104ef8d3b9e6f8fadd`
- Head `bd01eb52e9ec5464bb9f026f5ce666bc883db441`
- Fingerprint `bd01eb52e9ec5464bb9f026f5ce666bc883db441:48b8545d53b607c4ce1f396e0f76e81bc1c95d2cae9147aad695d2933278e22b`
- 看改动：`git diff 6639b002..bd01eb52`
- 自行复现 fingerprint 并逐字符比对：
  `sha256(git diff --binary <base>..<head> -- . ':(exclude)reports/agent-runs/2026-07-hedge-open-live-v1/status.json')`

## 必读 artifact
- `reports/agent-runs/2026-07-hedge-open-live-v1/`
  `{00-task.md,10-design.md,11-adr.md,12-development-breakdown.md,design-inputs.md,
  20-implementation.md,20-implementation-hedge-be.md,20-implementation-hedge-fe.md,
  r4-reconciliation.md,40-fix-1-hedge-be.md,30-review-1-hedge-be.md,
  30-review-1-hedge-be-round-2.md,30-review-1-hedge-fe.md,60-test-output.txt}`
- 摸排事实：`reports/api-samples/2026-07-hedge-open-live-v1/`
  `{websocket-bookticker-recon.md,order-endpoints-filters-recon.md}`
- 源码：`backend/hedge_open_tasks/**`、`backend/app/server.py`、
  `backend/tests/test_hedge_*.py`、`frontend/index.html`、`frontend/self-check.js`
- `schemas/review-verdict.schema.json`

## 终审重点
1. **跨 FE/BE 契约一致**：§3 冻结 API（端点/Task/Fill/Position JSON 字段名/错误码/
   软删除）FE 消费与 BE 实现逐字一致；`single_amount` decimal string（R4-001）、
   `?status=all` 含 deleted（F-001）、`mode!=immediate` 拒绝（F-002）均已对齐；
   确认无第三处同类漂移。
2. **契约/设计一致**：ADR-2 共同网格取整（双腿同一 q_common，绝不独立取整）、
   ADR-3 NO_SIDE_EFFECT 反向不自动借币、ADR-4 单腿敞口不自动补/平 + >3 终止、
   ADR-5 dry-run 默认 + 双闸门（APP_HEDGE_EXECUTOR=live + 全局 Start）真实 POST
   不可达。
3. **证据链**：fingerprint 自复现一致；60-test-output（787 passed）与实跑一致；
   三份 review-1 verdict schema-valid、fingerprint 自洽；F-003~F-006 作为已记录的
   live 轮 follow-up 是否合理（不应是本轮阻断）。
4. **回归/边界**：borrow 零改动；无真实网络/下单/凭据；dry-run record transport
   不含密钥/签名。
5. 独立跑 `python -m pytest backend/tests -q`（应 787）与 `node frontend/self-check.js`
   （应 108），结果写入正文。

## 输出
- 终审正文写实际读取/运行的证据与判断。
- 结尾唯一 schema-valid JSON：`role:"final_reviewer"`、`diff_fingerprint`（上面新串）、
  `reviewer_prior_involvement:"none"`、`reviewed_artifacts`、`findings`、
  `required_fixes`、`next_action`。REWORK 必含 `fix_start_prompt`。
- 追加 AGENTS.md「Output Footer」六行，置于最终 JSON 前。写完即停，不改任何文件。

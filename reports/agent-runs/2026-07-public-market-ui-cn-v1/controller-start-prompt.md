# Controller Start Prompt — 2026-07-public-market-ui-cn-v1

（本文案可直接粘贴给 Claude-GLM controller 会话启动本阶段。）

你是新阶段 `2026-07-public-market-ui-cn-v1` 的 controller（claude_glm /
glm-5.2[1m]），同时是 Task A 的实现者与 Task C 的执行者。本阶段的设计与拆分
由 Fable5（anthropic/claude-fable-5）完成并已随 H_intake 提交——你**不需要**
再写 00-task/10-design，直接按其执行。两个前置阶段均已获用户最终验收
（commit 6d8c0c4）。

## 先读（全部在仓库内，读原文）

1. `reports/agent-runs/2026-07-public-market-ui-cn-v1/00-intake.md` — 背景与
   用户 5 点决策
2. `.../00-task.md` — 边界、任务拆分、验收（权威）
3. `.../10-design.md` — 中文映射表、费率格式化算法（含 self-check 用例最小集）、
   warnings 新措辞语义要点
4. `.../status.json` — 路由、约束、fingerprint 协议
5. `reports/api-samples/2026-07-public-market-ui-cn-v1/20260704T044945Z/`
   — lastFundingRate 语义的 live 证据（evidence-index.md、
   verify-funding-semantics.py，离线可重放，PASS）

## 执行序列

1. **确认 H_intake**：上述文件已由 Fable5 提交；核对 status.json 后把
   `base_sha` 填为 H_intake 提交 sha（簿记提交，不入 hash）。
2. **Task A（你自己，senior_developer）**：按 00-task.md Task A 节执行——
   `CONTRACT_WARNINGS[1]` 替换为规定英文文案、合约文档同段落修订、测试同步。
   snapshot.py 的 diff 必须**仅一处字符串变化**。提交 H_A，绑定 task-A
   fingerprint。
3. **Task B（派发 Kimi，minimal_change_engineer）**：派工 prompt 必须内嵌
   10-design.md 的第 1-4 节全文（格式化算法逐条 + 样例表 + 映射表 + 中文化
   清单），并附 hard_constraints 中的前端各条。Kimi 完成后提交 H_B，绑定
   task-B fingerprint。
4. **Task C（你自己，test_strategist，无产品代码）**：离线构建快照，断言
   warnings[1] 为新文案且 **rows 与验收基线逐字段一致**（任何 rows 差异 →
   BLOCKED，不得自行解释）；`pytest backend/tests -q` + `node
   frontend/self-check.js` 输出留档 60-test-output.txt。提交 H_C，绑定
   stage-level fingerprint。
5. **review-1**：Task A → Kimi；Task B → 全新只读 Claude-GLM 会话（禁止复用
   本 transcript）。verdict 按 schemas/review-verdict.schema.json，指纹由
   评审方从 raw diff 独立重算。
6. **review-2**：Codex `codex exec --model gpt-5.5 -s read-only`，
   `reviewer_prior_involvement=direction_synthesis`（strong-reviewer
   disclosure override；Anthropic 因本阶段设计参与被排除，两实现方 hard-ban，
   与前两阶段同径）。
7. 每个 gate 前后跑 `python3 scripts/validate-stage.py
   2026-07-public-market-ui-cn-v1 --phase <checkpoint|pre-review|pre-accept>`。
   终态 `stage_accepted_waiting_user`；**不声明最终验收**。

## 全程红线

- 无任何 live HTTP（证据已抓齐）；无 key/签名/私有端点/order/borrow/repay/
  transfer/websocket。
- rows 结构与数值零变化；API 载荷中只允许 warnings[1] 文本变化。
- `classify.py` / `normalize.py` / `snapshot_service.py` / `schemas/**` 不动。
- 前端费率格式化**必须字符串移位**，`parseFloat/Number × 100` 一律 REWORK。
- UI 中文优先：主表不得出现英文枚举直出。
- `reports/api-samples/**` 全部只读。
- 边界越界即 REWORK，与代码质量无关。

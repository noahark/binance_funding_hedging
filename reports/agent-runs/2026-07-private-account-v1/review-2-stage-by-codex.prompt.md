<!-- ============ RECEIPT（审计元数据，bookkeeper 回填；非任务内容） ============
status: pending            # pending | running | done | escalated
target_model: codex gpt5.5 FRESH read-only review-2 会话（final_reviewer；codex exec -s read-only）
adapter_cmd: 用户向 fresh Codex 终端发「读文件执行 PROMPT BODY」一行指令；committed 指纹已由 bookkeeper 填实
started_at:
completed_at:
session_id:
base_sha: fce1452cbc1db652477f517c4017a13f3ffb5449（H_intake PASS，stage 级 base）
head_sha: 6c1e992c4628c0d8e369ba648b0403f341037849（H_B，stage 级 head）
diff_fingerprint: 6c1e992c4628c0d8e369ba648b0403f341037849:a2140bfd2de2043b78321d0794e6db849f102d3987352f14cfd95178258a0772
outputs:                   # review-2-round1.raw-output.md（叙述 + 单个 verdict JSON）
next_dispatch: ACCEPT(next_action 必须是 stage_accepted_waiting_user) → bookkeeper 停在 stage_accepted_waiting_user（红线 can_accept_final=false，不翻 accepted；merge main 仅限用户明确验收后）；REWORK → 正式 rework 流程（计入 rework_count，上限 3）；BLOCKED → 升级用户
======================================================================== -->

--- PROMPT BODY（不可变任务正文；仅 base/head 占位符由 bookkeeper 填实，其余不改写） ---

## T3. Review-2 — stage final gate（fresh Codex / gpt5.5，只读，committed 指纹）

你是 stage `2026-07-private-account-v1` 的 **final reviewer**
（`codex exec -s read-only`）。披露：`reviewer_prior_involvement =
direction_synthesis`（你合成并冻结了本方向基线，且为方向评审五人组
之一、参与用户 8 点问答；实现/设计/拆解未参与；两实现方 hard-ban、
Fable5 为 designer 避让——路由依据 status.json model_routing +
AGENTS.md disclosure override）。

- base_sha: `fce1452cbc1db652477f517c4017a13f3ffb5449`；head_sha: `6c1e992c4628c0d8e369ba648b0403f341037849`；从 raw git
  独立重算指纹；核对两份 review-1 verdict 绑定关系。
- 评审重点（MILESTONE 级）：
  1. 安全门实效：白名单 12 项 deny-by-default、单一 HMAC、GET-only、
     无 websocket/listenKey 铺垫——对代码与负向测试逐项核实；
  2. key 与数值卫生：全 diff 与落档无凭据/真实账户数值（按 §2.A
     脱敏标记表抽验）；
  3. 契约 v0.3：四级链、net 六向量、sort_basis/ADR-3 修订记录、
     防重复计算、coverage 语义、discovery 证据链 sha256 抽验；
     classify/normalize 零改动回归；
  4. 并行模式试运行 #2 合规：embedded_reviews 落档完备、R10 收尾段
     被机械执行的证据、bookkeeper 单写、独立 bookkeeper 披露、
     R4 对账记录；
  5. stage 分支制首跑合规：全部提交在 stage 分支、validator 分支门
     PASS 证据、无 main 侧 stage 提交。
- 输出：叙述 + ```json verdict（role=`final_reviewer`、model=`gpt5.5`、
  含重算指纹、findings[]、required_fixes[]、residual_risks[]、
  next_action；REWORK 必附 fix_start_prompt）。verdict JSON 缺失或
  非法 = fail-closed。**ACCEPT 的 next_action 只能是
  stage_accepted_waiting_user，不得指示合并或验收。**

---

## review-1 绑定 + review-2 必查项（bookkeeper 据 R9 回执附；非模板正文改写）

两份 review-1 均已落档且 `tasks[].review_1` 填实，均 verdict=ACCEPT：

| 任务 | reviewer | verdict | diff_fingerprint（reviewer 重算） | raw output |
|---|---|---|---|---|
| A（后端） | kimi fresh（first_reviewer） | ACCEPT | `6ca6ee1…:fdfba1…` | `review-1-task-a-round1.raw-output.md` |
| B（前端） | claude_glm fresh（first_reviewer） | ACCEPT | `6c1e992…:50998c…` | `review-1-task-b-round1.raw-output.md` |

**review-2 必查（bookkeeper 升级，请独立判定）**：

1. **Task A first_reviewer 隔离偏差**：Kimi 的 `reviewed_artifacts[]` 含
   `embedded-review-a-round2.raw-output.md`（嵌入预审 round2 的 PASS 输出），
   违反 T1 dispatch"嵌入预审结论对你不可见"的 fresh 隔离契约。请独立判定：
   - 该读取是否实质锚定了 Kimi 的 ACCEPT（anchor bias）；
   - Kimi 的核心独立校验（指纹重算 / 147 passed 复现 / discovery sha256 抽验 /
     冻结预算表抽验）与 3 项 findings（`private_client.py:326` / `snapshot.py:446`
     / ADR-11，均带独立代码证据，非 round2 fix 复述）是否足以支撑 ACCEPT 有效性；
   - 结论可选：维持 ACCEPT / 退回 Task A 重做（在 verdict 的 findings 或
     residual_risks 中记录你的独立性判定）。
2. **bookkeeper dual_hat 披露**：bookkeeper 与 implementer-A 同为 claude_glm
   模型但强制不同会话（`status.json.bookkeeper.dual_hat_disclosure`，记账不产生
   代码作者身份）。请评估该披露是否充分、是否影响 stage 可接受性。
3. **reviewer_prior_involvement 自我披露**：你本人 = direction_synthesis。请在
   verdict 的 `reviewer_prior_involvement_notes` 中如实记录此 strong-reviewer
   override 的理由与证据路径（AGENTS.md disclosure override），并确认你的 final
   判断未因参与方向合成而被锚定。

---

本地北京时间: 2026-07-06（bookkeeper 续任会话填实 committed 指纹 + review-1 绑定）

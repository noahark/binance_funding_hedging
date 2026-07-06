# 正式评审 prompt 模板 — 2026-07-private-account-v1

R1 预写模板。bookkeeper 在 H_A/H_B 落盘、指纹计算后把 `<FILL:*>`
填实，另存独立 dispatch 文件（R9 回执自加）派发。除占位符外正文不得
改写；嵌入预审结论不约束正式评审。
**role 口径修正**：review-1 verdict 的 `role` 取 schema 合法值
`first_reviewer`（上一 stage 模板误写 second_reviewer，本轮已修正）。

---

## T1. Review-1 — Task A（fresh Kimi，只读，committed 指纹）

你是**全新的只读 Kimi 会话**，担任 `first_reviewer`，对 stage
`2026-07-private-account-v1` **Task A（后端）已提交状态**做任务级评审。
与实现/设计/嵌入预审无先前关联（预审由另一 fresh 会话完成，其结论
对你不可见）。

- base_sha: `<FILL:base_sha>`；head_sha: `<FILL:head_sha>`；自行按
  status.json `diff_fingerprint_formula` 重算指纹并比对，不一致即
  BLOCKED。当前分支应为 `stage/2026-07-private-account-v1`。
- 评审范围：diff 中 backend/schemas/docs/api 部分，对照 10-design
  §1/§2/§3（含 §2.A 附录冻结值）+ hard_constraints + 白名单 12 项。
- 必查项 = 预审清单同集（白名单三态/单一 HMAC/四级链/六向量/排序
  双向量/coverage/防重复计算/数值卫生/零改动红线），另加：
  `60-test-output.txt` 可重放、discovery 证据 sha256 抽验、冻结预算表
  与实测头一致性抽验。
- 禁止写文件、签名请求、改工作树。
- 输出：叙述 + 末尾单个 ```json verdict（符合
  `schemas/review-verdict.schema.json`；role=`first_reviewer`；
  verdict=ACCEPT/REWORK/BLOCKED；REWORK 必附 fix_start_prompt）。

## T2. Review-1 — Task B（fresh Claude-GLM，只读，committed 指纹）

同 T1 结构，对象 = Task B（前端）已提交状态；禁止复用 bookkeeper/
Task A/预审任何上下文。

- base_sha: `<FILL:base_sha>`；head_sha: `<FILL:head_sha>`；重算指纹。
- 范围：diff 中 frontend 部分，对照 10-design §1.1-§1.5/§4。
- 必查 = 预审清单同集，另加：self-check 自跑复现、隐私开关默认态
  实证（fixture 渲染检查）。
- 输出：叙述 + ```json verdict（role=`first_reviewer`）。

## T3. Review-2 — stage final gate（Codex/GPT，只读）

你是 stage `2026-07-private-account-v1` 的 **final reviewer**
（`codex exec -s read-only`）。披露：`reviewer_prior_involvement =
direction_synthesis`（你合成并冻结了本方向基线，且为方向评审五人组
之一、参与用户 8 点问答；实现/设计/拆解未参与；两实现方 hard-ban、
Fable5 为 designer 避让——路由依据 status.json model_routing +
AGENTS.md disclosure override）。

- base_sha: `<FILL:base_sha>`；head_sha: `<FILL:head_sha>`；从 raw git
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

本地北京时间: 2026-07-06 00:40 CST（Fable5 预写）

# 正式评审 prompt 模板 — 2026-07-phase2-borrow-sort-v1

R1 预写模板。controller 在 H_A/H_B 落盘、指纹计算完成后，把 `<FILL:*>`
占位符填实，另存为独立 dispatch 文件（R9 回执块自加）后派发。
**除占位符外正文不得改写**；预审（checkpoint）结论不约束正式评审。

---

## T1. Review-1 — Task A（fresh Kimi，只读，committed 指纹）

你是一个**全新的只读 Kimi 会话**，担任 `reviewer_1`，对 stage
`2026-07-phase2-borrow-sort-v1` **Task A（后端）已提交状态**做任务级评审。
你与本阶段实现/设计无先前关联（嵌入预审由另一个 fresh 会话完成，其结论
对你不可见、不约束你）。

- base_sha: `<FILL:base_sha>`；head_sha: `<FILL:head_sha>`
- 自行重算 stage 指纹（公式见 status.json `diff_fingerprint_formula`），
  与 status.json 记载比对；不一致即 BLOCKED。
- 评审范围：`git diff <base>..<head>` 中 backend/schemas/docs/api 部分，
  对照 `10-design.md` §1/§2/§3 + status.json hard_constraints +
  endpoint_whitelist。
- 必查项与嵌入预审清单相同（单一 HMAC 出口/白名单三态/key 卫生/
  Decimal 向量/排序全序/三态语义/零改动红线/契约证据链），另加：
  `60-test-output.txt` 可重放性、discovery 证据 sha256 抽验。
- 禁止：写文件、签名请求、改工作树。
- 输出：评审叙述 + 末尾单个 ```json verdict（符合
  `schemas/review-verdict.schema.json`；role=`second_reviewer`；
  verdict=ACCEPT/REWORK/BLOCKED；REWORK 必附 fix_start_prompt）。

## T2. Review-1 — Task B（fresh Claude-GLM，只读，committed 指纹）

你是一个**全新的只读 Claude-GLM 会话**，担任 `reviewer_1`，对 stage
`2026-07-phase2-borrow-sort-v1` **Task B（前端）已提交状态**做任务级评审。
禁止复用 controller/Task A/嵌入预审任何会话上下文。

- base_sha: `<FILL:base_sha>`；head_sha: `<FILL:head_sha>`
- 自行重算指纹并与 status.json 比对；不一致即 BLOCKED。
- 评审范围：diff 中 frontend 部分，对照 `10-design.md` §1.1-§1.2/§4。
- 必查项与嵌入预审清单相同（拆列/格式化函数零改动/日费率与间隔/零排序
  逻辑/降级/不消费私有块/self-check 断言并自跑），另加：渲染顺序断言
  确实使用「单期低但日费率高排前」用例。
- 禁止：写文件、改工作树。
- 输出：叙述 + 末尾单个 ```json verdict（同 T1 格式）。

## T3. Review-2 — stage final gate（Codex/GPT，只读）

你是 stage `2026-07-phase2-borrow-sort-v1` 的 **final reviewer**
（`codex exec -s read-only`）。披露：`reviewer_prior_involvement =
direction_synthesis`（你合成了 Phase 2 方向基线；实现/设计/拆解未参与；
两实现方 hard-ban、Fable5 为 designer 已避让——路由依据见 status.json
model_routing 与 AGENTS.md disclosure override）。

- base_sha: `<FILL:base_sha>`；head_sha: `<FILL:head_sha>`
- 从 raw git 数据独立重算 stage 指纹；核对 review-1 两份 verdict 绑定
  同一指纹。
- 评审重点（MILESTONE 级）：
  1. 安全门实效：单一 HMAC 出口、deny-by-default 白名单、GET-only、
     直连守卫、审计日志、降级——逐项对代码与负向测试核实，不信摘要；
  2. key 卫生：全 diff 与落档文件无凭据片段；落档 URL 无 query string；
  3. 契约 v0.2：borrow_validation 三态、两个公开字段、rows 有序性与
     discovery 证据链（sha256 抽验）一致；枚举/classify 零改动回归；
  4. 并行模式首试合规：embedded_reviews 落档完备（diff.patch/dispatch/
     raw output 每轮齐全）、bookkeeper 单写、实现终端未 commit；
  5. 前端零排序逻辑与格式化函数零改动。
- 输出：叙述 + 末尾单个 ```json verdict（role=`final_reviewer`，
  model=`gpt5.5`，含你重算的 diff_fingerprint、findings[]、
  required_fixes[]、residual_risks[]、next_action；REWORK 必附
  fix_start_prompt）。verdict JSON 缺失或非法 = fail-closed 不通过。

---

本地北京时间: 2026-07-04 21:05 CST（Fable5 预写）

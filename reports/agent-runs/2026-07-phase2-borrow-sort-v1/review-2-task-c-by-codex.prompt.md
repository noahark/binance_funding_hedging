<!-- ============ RECEIPT（审计元数据，bookkeeper 填写；非任务内容） ============
status: pending            # pending | running | done | blocked
target_model: codex (codex exec -s read-only; stage final reviewer;
              reviewer_prior_involvement=direction_synthesis，见正文披露)
adapter_cmd: codex exec -s read-only "$(cat reports/agent-runs/2026-07-phase2-borrow-sort-v1/review-2-task-c-by-codex.prompt.md)"
prereq: review-1 双 ACCEPT（T1 backend + T2 frontend verdict 均 ACCEPT，
        且绑定同一 diff_fingerprint cc25148:9dc905d5...）。REWORK 则本
        dispatch 不触发（先 fixing，计 rework_count）。
started_at:
completed_at:
session_id:
outputs:                   # 30-review-2.md（含 schema 合规 verdict；
                           #  role=final_reviewer, model=gpt5.5）
next_dispatch: ACCEPT → stage_accepted_waiting_user（bookkeeper
              can_accept_final=false，等用户验收）；REWORK → fixing
======================================================================== -->

--- PROMPT BODY（不可变任务正文，自此行以下原样执行） ---

你是 stage `2026-07-phase2-borrow-sort-v1` 的 **final reviewer**
（`codex exec -s read-only`）。披露：`reviewer_prior_involvement =
direction_synthesis`（你合成了 Phase 2 方向基线；实现/设计/拆解未参与；
两实现方 hard-ban、Fable5 为 designer 已避让——路由依据见 status.json
model_routing 与 AGENTS.md disclosure override）。

- base_sha: `4d47ad2d3f2068e86b634b5e39d5063dc4ed526f`；head_sha: `cc25148aa7924e7bb89364f4bba7c8fe978e91f9`
- 从 raw git 数据独立重算 stage 指纹；核对 review-1 两份 verdict 绑定
  同一指纹。
- **范围注记**：base..head diff 含 `e831137`（parallel-mode
  v0.3-TRIAL-AMEND，改 `docs/parallel-development-mode.md`）——harness 层
  试运行修订，**非 stage 产品代码**；评审重点 #4「并行模式首试合规」需
  评估其本身（是否合规落档），但不得计入 backend/frontend 产品代码
  评审结论。
- 评审重点（MILESTONE 级）：
  1. 安全门实效：单一 HMAC 出口、deny-by-default 白名单、GET-only、
     直连守卫、审计日志、降级——逐项对代码与负向测试核实，不信摘要；
  2. key 卫生：全 diff 与落档文件无凭据片段；落档 URL 无 query string；
  3. 契约 v0.2：borrow_validation 三态、两个公开字段、rows 有序性与
     discovery 证据链（sha256 抽验）一致；枚举/classify 零改动回归；
  4. 并行模式首试合规：embedded_reviews 落档完备（diff.patch/dispatch/
     raw output 每轮齐全）、bookkeeper 单写、实现终端未 commit；
  5. 前端零排序逻辑与格式化函数零改动。
- 禁止：写文件、改工作树（read-only 会话）。
- 输出：叙述 + 末尾单个 ```json verdict（role=`final_reviewer`，
  model=`gpt5.5`，含你重算的 diff_fingerprint、findings[]、
  required_fixes[]、residual_risks[]、next_action；REWORK 必附
  fix_start_prompt）。verdict JSON 缺失或非法 = fail-closed 不通过。

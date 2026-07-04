<!-- ============ RECEIPT（审计元数据，bookkeeper 填写；非任务内容） ============
status: pending            # pending | running | done | blocked
target_model: codex (codex exec -s read-only; stage final reviewer;
              reviewer_prior_involvement=direction_synthesis，见正文披露)
adapter_cmd: codex exec -s read-only "$(cat reports/agent-runs/2026-07-phase2-borrow-sort-v1/review-2-task-c-by-codex.prompt.md)"
prereq: review-1 COMPLETE —— Task A round-2 ACCEPT（fresh Kimi session_bc79ad49
        复审 E1 fix H_A2 2a793a9，指纹 2a793a9:9b92cc45 三方 MATCH，96+20 自跑）
        + Task B round-1 ACCEPT（backend-only fix 不影响 frontend，B 无 round-2）。
        最终 diff_fingerprint = 2a793a9:9b92cc45...（含 E1 fix 的最终产品代码）。
        review-1 任一 REWORK 则本 dispatch 不触发（先 fixing，计 rework_count）。
started_at:
completed_at:
session_id:
outputs:                   # 30-review-2.md（含 schema 合规 verdict；
                           #  role=final_reviewer, model=gpt5.5）
next_dispatch: ACCEPT → stage_accepted_waiting_user（bookkeeper
              can_accept_final=false，等用户验收）；REWORK → fixing（rework_count=2）
======================================================================== -->

--- PROMPT BODY（不可变任务正文，自此行以下原样执行） ---

你是 stage `2026-07-phase2-borrow-sort-v1` 的 **final reviewer**
（`codex exec -s read-only`）。披露：`reviewer_prior_involvement =
direction_synthesis`（你合成了 Phase 2 方向基线；实现/设计/拆解未参与；
两实现方 hard-ban、Fable5 为 designer 已避让——路由依据见 status.json
model_routing 与 AGENTS.md disclosure override）。

- base_sha: `4d47ad2d3f2068e86b634b5e39d5063dc4ed526f`；head_sha: `2a793a9c35e8e5fe8cdebe8875cada9b85f335d0`
  （**含 E1 fix 的最终产品代码完成点**；非 round-1 的 cc25148——round-1 A=REWORK
  后 fix 落 H_A2 2a793a9，review-2 须评审含 fix 的最终态）
- 从 raw git 数据独立重算 stage 指纹（公式见 status.json
  `diff_fingerprint_formula`）。指纹绑定核对：
  - review-1 **round-1** 两份 verdict（`30-review-1-backend.md` REWORK +
    `30-review-1-frontend.md` ACCEPT）绑定 round-1 head `cc25148:9dc905d5...`；
  - review-1 **round-2** Task A verdict（`30-review-1-round2-backend.md`
    ACCEPT）绑定 final head `2a793a9:9b92cc45...`；
  - **本 review-2 绑定 final head `2a793a9:9b92cc45...`**（= 你重算结果）；
  - 任一不一致即 BLOCKED 上报。
- **范围注记**：base..head（`4d47ad2..2a793a9`）diff 含：
  (a) `e831137`（parallel-mode v0.3-TRIAL-AMEND，改 `docs/parallel-development-mode.md`）
      ——harness 层试运行修订，**非 stage 产品代码**；评审重点 #4「并行模式首试合规」
      评估其本身（是否合规落档），但不得计入 backend/frontend 产品代码评审结论；
  (b) `bd0159a`（review-1 round-1 evidence 落档：dispatch/raw/verdict）——
      **非产品代码**，知悉即可，不计入产品评审；
  (c) **`2a793a9` 本身（H_A2，E1 fundingInfo live 降级 fix）= 产品代码，须评审**
      （`binance_public.py` try/except + `snapshot.py` extra_warnings +
      `snapshot_service.py` 透传 + 新测试；详见 `20-implementation-backend.md` §7）。
  `deded6f`/`48662df`/`2dc1aee` 在 head 之后，不进指纹、不在本 diff 内。
- 评审重点（MILESTONE 级）：
  1. 安全门实效：单一 HMAC 出口、deny-by-default 白名单、GET-only、
     直连守卫、审计日志、降级（**含 E1 fundingInfo live 失败降级为全 8h + warning、
     不 propagate；其余公开端点仍 raise-on-failure**）——逐项对代码与负向测试核实，
     不信摘要；
  2. key 卫生：全 diff 与落档文件无凭据片段；落档 URL 无 query string；
  3. 契约 v0.2：borrow_validation 三态、两个公开字段（funding_interval_hours /
     daily_funding_rate）、rows 有序性与 discovery 证据链（sha256 抽验）一致；
     枚举/classify 零改动回归；warnings 开放 array（E1 fix 追加合法，未改 schema）；
  4. 并行模式首试合规：embedded_reviews 落档完备（diff.patch/dispatch/
     raw output 每轮齐全）、review-1 round-2 复审落档完备、bookkeeper 单写、
     实现终端未 commit；
  5. 前端零排序逻辑与格式化函数零改动。
- 禁止：写文件、改工作树（read-only 会话）。
- 输出：叙述 + 末尾单个 ```json verdict（role=`final_reviewer`，
  model=`gpt5.5`，含你重算的 diff_fingerprint、findings[]、
  required_fixes[]、residual_risks[]、next_action；REWORK 必附
  fix_start_prompt）。verdict JSON 缺失或非法 = fail-closed 不通过。

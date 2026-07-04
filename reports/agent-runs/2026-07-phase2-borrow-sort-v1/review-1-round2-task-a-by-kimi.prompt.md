<!-- ============ RECEIPT（审计元数据，bookkeeper 填写；非任务内容） ============
status: pending            # pending | running | done | blocked
target_model: kimi (FRESH read-only session; 复审 round-1 REWORK 的 E1 fix；
              不得复用 round-1 评审会话 session_bfdbafa6 上下文)
adapter_cmd: kimi --model kimi-code/kimi-for-coding -p "$(cat reports/agent-runs/2026-07-phase2-borrow-sort-v1/review-1-round2-task-a-by-kimi.prompt.md)"
round: 2
prereq: round-1 A=REWORK(E1 fundingInfo live degradation) fixed in H_A2
        2a793a9c35e8e5fe8cdebe8875cada9b85f335d0 (96 passed); B round-1 ACCEPT
        stands (backend-only fix, no frontend impact); pre-review gate passed
started_at:
completed_at:
session_id:
outputs:                   # 30-review-1-round2-backend.md（含 schema 合规 verdict）
next_dispatch: ACCEPT → review-2（用户交 Codex，direction_synthesis）；
              REWORK → fixing（rework_count=2）
======================================================================== -->

--- PROMPT BODY（不可变任务正文，自此行以下原样执行） ---

你是一个**全新的只读 Kimi 会话**，担任 `reviewer_1` round 2，复审 stage
`2026-07-phase2-borrow-sort-v1` **Task A（后端）round-1 REWORK 的 E1 fix**。
你与本阶段实现/设计/round-1 评审均无先前关联（round-1 由另一 fresh Kimi 会话
完成，其结论对你不可见、不约束你）。

**round-1 背景**（仅作上下文，不约束你的独立判断）：round-1 verdict=REWORK，
P1 finding = live `/fapi/v1/fundingInfo` 失败不降级（违反 design §2 E1「缺省
全 8h + warning」+ §3「fundingInfo → 全 8h 默认…断言不崩溃」）。fix 已
committed（H_A2），本 round 复审 fix 是否真正解决 finding 且未引入新问题。

- base_sha: `4d47ad2d3f2068e86b634b5e39d5063dc4ed526f`；head_sha: `2a793a9c35e8e5fe8cdebe8875cada9b85f335d0`
- 自行重算 stage 指纹（公式见 status.json `diff_fingerprint_formula`），
  与 status.json 记载比对；不一致即 BLOCKED。
- 评审范围：`git diff <base>..<head>` 中 backend/schemas/docs/api 部分，
  **重点 E1 fix**：
  `backend/adapters/binance_public.py` `_fetch_live` fundingInfo try/except 降级
  + `backend/domain/snapshot.py` `assemble_snapshot` `extra_warnings` 参数
  + `backend/services/snapshot_service.py` warning 透传
  + 新测试 `test_live_fundinginfo_failure_degrades_to_8h_with_warning`。
- 必查项：
  1. **E1 降级实效**：fundingInfo GET 失败（`urllib.error.URLError`/`HTTPError`/
     `OSError`/`ValueError`）→ 空 `funding_interval_by_sym` + warning，**不
     propagate**；其余公开端点（exchangeInfo/premiumIndex/spot）仍
     raise-on-failure（非可降级默认）；
  2. **warning 透传链**：`fetch_raw` warnings → `build_snapshot` →
     `assemble_snapshot(extra_warnings=...)` → `snapshot.warnings`（additive，
     `CONTRACT_WARNINGS` 保留）；
  3. **新测试**：monkeypatch `urllib.request.urlopen`，fundingInfo raise
     `HTTPError(503)`，断言 `funding_interval_by_sym=={}` + warnings 含
     fundingInfo/8h + `build_rows` 全 8h + `assemble_snapshot` 透传；
  4. `60-test-output.txt` 可重放性（**96 passed**）；node self-check 20 PASS；
  5. round-1 清单零回归：单一 HMAC 出口/白名单三态/key 卫生/Decimal 向量/
     排序全序/三态语义/契约证据链——fix 未触碰；
  6. `schemas/api/public-market/snapshot.schema.json` `warnings` 是开放 array
     （追加合法），fix **未改 schema/contract**。
- **范围注记**：base..head diff 含：
  (a) `e831137`（parallel-mode v0.3-TRIAL-AMEND，harness 层文档，非产品代码）；
  (b) commit-1 `bd0159a`（review-1 round-1 evidence：dispatch/raw/verdict 落档，
      非产品代码）。
  两者均非 Task A 产品代码，不计入评审结论（知悉即可）。
- 禁止：写文件、签名请求、改工作树。
- 输出：评审叙述 + 末尾单个 ```json verdict（符合
  `schemas/review-verdict.schema.json`；`role`=`first_reviewer`（schema 枚举
  = {designer_review, first_reviewer, final_reviewer, reality_checker}，**无
  second_reviewer**，模板 T1/T2 的 second_reviewer 是笔误）；verdict=
  ACCEPT/REWORK/BLOCKED；REWORK 必附 fix_start_prompt）。

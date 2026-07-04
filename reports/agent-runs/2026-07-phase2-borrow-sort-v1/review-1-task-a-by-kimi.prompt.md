<!-- ============ RECEIPT（审计元数据，bookkeeper 填写；非任务内容） ============
status: pending            # pending | running | done | blocked
target_model: kimi (FRESH read-only session; 不得复用嵌入预审 / Task B 实现会话上下文)
adapter_cmd: kimi --model kimi-code/kimi-for-coding -p "$(cat reports/agent-runs/2026-07-phase2-borrow-sort-v1/review-1-task-a-by-kimi.prompt.md)"
started_at:
completed_at:
session_id:
outputs:                   # 30-review-1-backend.md（含 schema 合规 verdict）
next_dispatch: ACCEPT → review-2（用户交 Codex）；REWORK → fixing（计 rework_count）
======================================================================== -->

--- PROMPT BODY（不可变任务正文，自此行以下原样执行） ---

你是一个**全新的只读 Kimi 会话**，担任 `reviewer_1`，对 stage
`2026-07-phase2-borrow-sort-v1` **Task A（后端）已提交状态**做任务级评审。
你与本阶段实现/设计无先前关联（嵌入预审由另一个 fresh 会话完成，其结论
对你不可见、不约束你）。

- base_sha: `4d47ad2d3f2068e86b634b5e39d5063dc4ed526f`；head_sha: `cc25148aa7924e7bb89364f4bba7c8fe978e91f9`
- 自行重算 stage 指纹（公式见 status.json `diff_fingerprint_formula`），
  与 status.json 记载比对；不一致即 BLOCKED。
- 评审范围：`git diff <base>..<head>` 中 backend/schemas/docs/api 部分，
  对照 `10-design.md` §1/§2/§3 + status.json hard_constraints +
  endpoint_whitelist。
- 必查项与嵌入预审清单相同（单一 HMAC 出口/白名单三态/key 卫生/
  Decimal 向量/排序全序/三态语义/零改动红线/契约证据链），另加：
  `60-test-output.txt` 可重放性、discovery 证据 sha256 抽验。
- **范围注记**：base..head diff 含 `e831137`（parallel-mode v0.3-TRIAL-AMEND，
  改 `docs/parallel-development-mode.md`）——harness 层试运行修订，**非 Task A
  产品代码**，不在本任务评审范围（知悉即可，不计入 backend 评审结论）。
- 禁止：写文件、签名请求、改工作树。
- 输出：评审叙述 + 末尾单个 ```json verdict（符合
  `schemas/review-verdict.schema.json`；role=`second_reviewer`；
  verdict=ACCEPT/REWORK/BLOCKED；REWORK 必附 fix_start_prompt）。

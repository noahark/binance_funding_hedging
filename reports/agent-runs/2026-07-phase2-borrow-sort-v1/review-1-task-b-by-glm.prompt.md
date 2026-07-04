<!-- ============ RECEIPT（审计元数据，bookkeeper 填写；非任务内容） ============
status: pending            # pending | running | done | blocked
target_model: claude_glm (FRESH read-only session; 不得复用 controller / Task A / 嵌入预审任何会话上下文)
adapter_cmd: claude-glm --model glm-5.2 --permission-mode plan -p "$(cat reports/agent-runs/2026-07-phase2-borrow-sort-v1/review-1-task-b-by-glm.prompt.md)"
started_at:
completed_at:
session_id:
outputs:                   # 30-review-1-frontend.md（含 schema 合规 verdict）
next_dispatch: ACCEPT → review-2（用户交 Codex）；REWORK → fixing（计 rework_count）
======================================================================== -->

--- PROMPT BODY（不可变任务正文，自此行以下原样执行） ---

你是一个**全新的只读 Claude-GLM 会话**，担任 `reviewer_1`，对 stage
`2026-07-phase2-borrow-sort-v1` **Task B（前端）已提交状态**做任务级评审。
禁止复用 controller/Task A/嵌入预审任何会话上下文。

- base_sha: `4d47ad2d3f2068e86b634b5e39d5063dc4ed526f`；head_sha: `cc25148aa7924e7bb89364f4bba7c8fe978e91f9`
- 自行重算指纹并与 status.json 比对；不一致即 BLOCKED。
- 评审范围：`git diff <base>..<head>` 中 frontend 部分，对照
  `10-design.md` §1.1-§1.2/§4。
- 必查项与嵌入预审清单相同（拆列/格式化函数零改动/日费率与间隔/零排序
  逻辑/降级/不消费私有块/self-check 断言并自跑），另加：渲染顺序断言
  确实使用「单期低但日费率高排前」用例。
- **范围注记**：base..head diff 含 `e831137`（parallel-mode v0.3-TRIAL-AMEND，
  改 `docs/parallel-development-mode.md`）——harness 层修订，**非 Task B
  产品代码**，不在本任务评审范围。
- 禁止：写文件、改工作树。
- 输出：评审叙述 + 末尾单个 ```json verdict（符合
  `schemas/review-verdict.schema.json`；role=`second_reviewer`；
  verdict=ACCEPT/REWORK/BLOCKED；REWORK 必附 fix_start_prompt）。

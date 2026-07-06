<!-- ============ RECEIPT（审计元数据，bookkeeper 回填；非任务内容） ============
status: pending            # pending | running | done | escalated
target_model: kimi FRESH read-only review-1 会话（first_reviewer；不得复用 Task B 实现/嵌入预审任何上下文）
adapter_cmd: 用户向 fresh Kimi 终端发「读文件执行 PROMPT BODY」一行指令；committed 指纹已由 bookkeeper 填实
started_at:
completed_at:
session_id:
base_sha: fce1452cbc1db652477f517c4017a13f3ffb5449（H_intake PASS）
head_sha: 6ca6ee1db61952c10d547aa73a79e0711b2ae64b（H_A backend）
diff_fingerprint: 6ca6ee1db61952c10d547aa73a79e0711b2ae64b:fdfba177950b8872b386d07c1ee02ddfff7eaa0b044307691ebbb40235b8a252
outputs:                   # review-1-task-a-round1.raw-output.md（叙述 + 单个 verdict JSON）
next_dispatch: ACCEPT → bookkeeper 推进 review-2（T3 Codex read-only）；REWORK → 正式 rework 流程（计入 rework_count）；BLOCKED → 升级用户
======================================================================== -->

--- PROMPT BODY（不可变任务正文；仅 base/head 占位符由 bookkeeper 填实，其余不改写） ---

## T1. Review-1 — Task A（fresh Kimi，只读，committed 指纹）

你是**全新的只读 Kimi 会话**，担任 `first_reviewer`，对 stage
`2026-07-private-account-v1` **Task A（后端）已提交状态**做任务级评审。
与实现/设计/嵌入预审无先前关联（预审由另一 fresh 会话完成，其结论
对你不可见）。

- base_sha: `fce1452cbc1db652477f517c4017a13f3ffb5449`；head_sha: `6ca6ee1db61952c10d547aa73a79e0711b2ae64b`；自行按
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

---

本地北京时间: 2026-07-06 12:11 CST（bookkeeper 续任会话填实 committed 指纹）

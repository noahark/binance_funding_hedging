<!-- ============ RECEIPT（审计元数据，bookkeeper 回填；非任务内容） ============
status: pending            # pending | running | done | escalated
target_model: claude_glm (glm-5.2) FRESH read-only/plan review-1 会话（first_reviewer；不得复用 bookkeeper/Task A 实现/嵌入预审任何上下文）
adapter_cmd: 用户向 fresh claude-glm 终端发「读文件执行 PROMPT BODY」一行指令；committed 指纹已由 bookkeeper 填实
started_at:
completed_at:
session_id:
base_sha: 6ca6ee1db61952c10d547aa73a79e0711b2ae64b（H_A；Task B 串行链 base，diff 范围 = frontend，与 T2 评审范围一致）
head_sha: 6c1e992c4628c0d8e369ba648b0403f341037849（H_B frontend）
diff_fingerprint: 6c1e992c4628c0d8e369ba648b0403f341037849:50998c3a60afbae089f3e370e7ecbdd869256c70ff0cc1ae888b3f3abd6da2a2
outputs:                   # review-1-task-b-round1.raw-output.md（叙述 + 单个 verdict JSON）
next_dispatch: ACCEPT → bookkeeper 推进 review-2（T3 Codex read-only）；REWORK → 正式 rework 流程（计入 rework_count）；BLOCKED → 升级用户
======================================================================== -->

--- PROMPT BODY（不可变任务正文；仅 base/head 占位符由 bookkeeper 填实，其余不改写） ---

## T2. Review-1 — Task B（fresh Claude-GLM，只读，committed 指纹）

同 T1 结构，对象 = Task B（前端）已提交状态；禁止复用 bookkeeper/
Task A/预审任何上下文。

- base_sha: `6ca6ee1db61952c10d547aa73a79e0711b2ae64b`；head_sha: `6c1e992c4628c0d8e369ba648b0403f341037849`；重算指纹。
- 范围：diff 中 frontend 部分，对照 10-design §1.1-§1.5/§4。
- 必查 = 预审清单同集，另加：self-check 自跑复现、隐私开关默认态
  实证（fixture 渲染检查）。
- 输出：叙述 + ```json verdict（role=`first_reviewer`）。

---

本地北京时间: 2026-07-06 12:11 CST（bookkeeper 续任会话填实 committed 指纹；
Task B base=H_A 串行链，6ca6ee1..6c1e992 diff = frontend scope，匹配 T2 评审范围）

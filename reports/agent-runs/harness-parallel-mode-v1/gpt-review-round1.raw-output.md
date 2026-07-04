# GPT Review Round 1 — docs/parallel-development-mode.md (DRAFT-1)

Provenance: GPT/Codex review of DRAFT-1 (commit eba5bc0), relayed verbatim by
the user on 2026-07-04 (~16:30 CST). Archived unedited below per
parallel-development-mode.md §8. Disposition: all 5 findings absorbed into
DRAFT-2 by Fable5.

---

Verdict: REWORK

1. P1 - R7 与现行强评审 override 规则冲突
   docs/parallel-development-mode.md:106 写“设计者所属
   provider 不得担任 review-2”，但 AGENTS.md:160 当前规则
   是“prefer isolation，必要时 Codex/Claude 可带 disclosure
   override”。
   修法：改成“设计参与者默认不做 review-2；仅当无关决策模型
   runner-level 不可用且 disclosure 证据齐全时，Codex/Claude
   可 override。实现/fix 作者仍 hard-ban。”

2. P2 - bookkeeper 默认写成 Fable5 不够可执行
   docs/parallel-development-mode.md:34 把 Fable5 写成默认记账
   者，但 bookkeeper 要跑测试、commit、算指纹、改
   status.json。这应由一个本地执行会话承担，不应绑定到 Fable5
   这个设计/拆解模型。
   修法：bookkeeper 改为“用户指定的单一本地 controller 执行会
   话，默认 claude-glm 或当前 Codex 工作区”；Fable5 默认只做
   designer/breakdown/prompt 预写。

3. P2 - §5 的证据索引还不够 review-2 重建链路
   embedded_reviews 示例只记录 rounds/reviewer/artifacts，缺
   task scope、implementer、预写 prompt 路径、实际 dispatch 文
   件、工作树 diff 文件、正式 review-1 的 base/head/
   fingerprint/verdict 路径。
   修法：给 embedded_reviews.A/B 增加 task_id/scope/
   implementer/prompt_path/dispatch_path/worktree_diff_path/
   formal_review_path/base_sha/head_sha/diff_fingerprint 等字
   段。

4. P2 - 嵌入预审需要保存“评审看到的 diff”
   docs/parallel-development-mode.md:91 只要求 raw output/fix
   说明，不能证明 reviewer 当时看到了哪些未提交改动。
   修法：每轮预审必须落 embedded-review-a-round<N>.diff.patch
   和对应 dispatch/command 记录；不要叫它 diff_fingerprint，避
   免发明新门禁协议。

5. P2 - 你补的“启动文案回执写到文件开头”应该加入规范
   我建议新增 R9：所有启动文案都是 stage 内的 dispatch
   packet，文件开头有可填写回执块，下面用明确 marker 分隔
   immutable prompt body。例如：
   状态 / 目标模型 / adapter 命令 / started_at /
   completed_at / session_id / 输出文件 / 下一步 dispatch 文
   件。
   这样执行者只需要找对应 dispatch 文件跑，不靠聊天复制。

总评：R5 的两段式设计是成立的，和 Hard Gates 一致；整体模式可
采纳为 trial，但需要先修上面 5 点，尤其是 R7 和 dispatch/证据
索引。

# 用户授权证据 — 直修收弧（red-gate-greening-v1）

本文件收录用户对"直修模式收弧"的授权原文（verbatim），作为本弧全部直修动作
（不走 stage 流程、两仓本地 commit、零 push）的授权证据。

## 授权原文 1（派工 + 审阅前置，2026-07-17，本会话）

> 你接下来要执行 fix 任务，但是在这之前我想你先审阅一遍提出你的不同看法，
> 不必为了提问题而提意见，最终目的是让 Harness 稳定，以便后续开发项目使用。
> 派工包已落盘 reports/agent-runs/2026-07-red-gate-greening-v1/08-dispatch-kimi-direct-fix.md，
> 直接把文件内容转给 kimi 即可。要点：
>
> 修改点汇总（10 步执行序）：
>
> 1. 第 0 步：先提交 05/06/07/08/09/82 六个未跟踪文件（clean-worktree 前置）
> 2. T0：Stage A 模板仓账本矛盾收口（补 user_acceptance verbatim，缺口如实登记）
> 3. T2a：先于 T1 建 golden 基线（新脚本 validate-all-stages.py，两仓全量 + 5 类预登记
>    known-red/预期翻转迁移表）
> 4. T1（核心）：D3-v2 路标模型——删链式、删 own-review 担保路径、删
>    covers_through_task；全量 review-2 命中 ⇒ 零 waypoints；DoD = A1-A8 对抗用例实跑留档
> 5. T2b：基线复跑比对，只许迁移表内变化
> 6. T6：治理三规则 + known-issue 台账
> 7. T5：merge-not-copy 下行到本仓 main（保住 _template 本仓专有字段，不走 update
>    脚本的 rsync 整覆盖路径）
> 8. T3：bookticker 在 main 上记 class-1 例外转绿（evidence = 已提交的 70-handoff
>    blob + digest，kimi 自己 review 时实证过）
> 9. T4：docs-truth-sync 只对齐 handoff 正文
> 10. T7：schema/docstring prose 清欠（独立 commit，连带删合同的 drift 披露注记）→ 收口记账
>
> 三个关键约定（都写死在包里）：
>
> - 路由更新：实现改为 kimi 后，raw-diff 评审 = Codex + 我（我不再实现，可以回到评审位；
>   D3 设计者身份照惯例披露）。
> - 全程零 push：两仓只做本地 commit（本仓 main 允许本地合并），你终审后统一 push。
> - D-i 默认不做：class-2 收编你还没拍板，包里明确禁止 kimi 扩白名单，docs-truth-sync
>   先标 known_red (D-i pending)——你之后任何时候拍"收"，都是一个小追加，不阻塞本轮。

## 授权原文 2（执行放行，2026-07-17，本会话）

> 执行吧

## 授权要点解读（非原文，执行者注记）

- 实现 = Kimi（moonshot_kimi）；raw-diff 评审 = Codex（openai）+ Fable5（anthropic，
  D3 设计者身份按惯例披露）；用户终审后才 push。
- 两仓全程零 push；funding_hedging 直接在 main 上本地提交；模板仓在分支
  `harness/d3-v2-direct` 工作后本地合 main。
- D-i（class-2 收编）未授权：白名单不扩项，docs-truth-sync 标
  `known_red (class-2, pending user decision D-i)`。
- 审阅前置已履行：Kimi 在执行前提交了对派工包的审阅意见（6 条修正点，见本会话），
  用户未对审阅意见提出异议即放行执行；审阅中提出的补强项（A8 双向、收口终态复跑、
  compat note 理由、T7 删除范围卡死）在执行中一并落实。

## T0 相关：Stage A 接受 verbatim

用户未在本弧中重新口述 Stage A（模板仓 2026-07-harness-authorized-exception-v1）的
接受原文。T0 按派工包规则处理：以 git 合并事实为准记账，接受 verbatim 证据缺口
如实登记，不补造。

## 授权原文 3（修复轮派工 + F3 处置拍板 (a)，2026-07-18，本会话）

> 执行 71-dispatch-kimi-fix-f1f2f3.md。
> - 第 0 步：先提交 68/69 两份评审落档（顺带解决 codex 抱怨的脏树问题）。
> - F1：compare 升级为三比（verdict + 错误多重集 + applied_exceptions），任何未登记
>   变化非零退出（现在连 FLIP 都退出 0，一并修）；交付 sentinel 回归测试留档 72-；
>   模板仓先改、cp 下行、两仓逐字节一致。
> - F2：09 文件追加你的 "a" 拍板原文并提交 → bookticker 例外的 evidence_file 改指
>   09（真 verbatim）→ 重算 digest → 干净 main 复跑 pre-accept（输出 append 到
>   62-，不改写旧段）。70-handoff 一个字不动——转述留在原处没错，错的只是拿它当
>   封印源。
> - F3(a)：迁移表补一行 known_red（理由=直修模式账本，真实产物 06/07/08/60-69）+
>   补 session_receipts + 60- 页脚。明确不补造 10-design/11-adr 等形态文件。

要点解读（非原文，执行者注记）：F3 处置拍板 = **(a) 登记 known_red**（否决 codex
fix prompt 中"补齐全套 stage-delivery 形态文件"的路线）；F2 确认 bookticker 例外的
digest 封印源改为本文件（含用户 verbatim 授权链），70-handoff 的转述文本保持原样、
不再充当封印源。

## 封印注记（2026-07-18，F2 后生效）

本文件自修复轮 F2 起被 bookticker `authorized_exceptions[0].evidence_sha256` digest
封印。**此后任何追加/修改都会破印并使 bookticker pre-accept 回红（设计的自动失效
行为）。后续授权原文请另立新文件，不再追加到本文件。**

---
记录人: Kimi（moonshot_kimi，本弧实现者）
本地北京时间: 2026-07-17（第 0 步提交时以 git commit 时间为准）；授权原文 3 与封印
注记追加于 2026-07-18（修复轮）

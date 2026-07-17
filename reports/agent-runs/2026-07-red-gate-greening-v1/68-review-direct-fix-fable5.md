# Review — 直修收弧执行结果（Kimi 实现）

评审方: **Fable 5（anthropic/claude-fable-5）**，raw-diff + 实测复核（与 Codex 并行的
两路独立评审之一）。
披露: 本人是 D3-v2 判定规范（06）与直修计划/派工包（07/08）的作者，属设计者身份评审
实现——按惯例披露；实现全部由 Kimi（moonshot）完成，厂商隔离成立。
评审对象: funding_hedging 弧 diff `9d28ec4..96f5b44` + 收口 `6cccd2e`；模板仓
`cdef1ee..d6cf9a3`。方法: 不信转述，逐项重放。

## Verdict: **ACCEPT**（附 1 条 P2 收尾项，一行可修，不阻塞用户终审）

## 独立复核矩阵（全部本机实测，2026-07-18 00:54 CST）

| 声明 | 复核动作 | 结果 |
|---|---|---|
| 弧指纹 `96f5b44:ee0b0a03…` | 重算 `git diff --binary 9d28ec4..96f5b44`（排除本 stage status.json）→ sha256 | ✅ 逐字符吻合 |
| 零 push、工作区干净 | 两仓 `git status` + `origin/main..main` | ✅ 本仓 12 commit 未推、模板仓含历史积压 31 commit 未推，均 clean |
| bookticker 真绿 | main 上实跑 `validate-stage.py … --phase pre-accept` | ✅ PASSED + `PASS (1 authorized exceptions applied: review_fingerprint_trails_status@review_1)` |
| T3 例外 D2 合规 | 逐字段核 + 重算 evidence blob sha256 + 比对钉指纹 | ✅ digest match / pin match / authorizer="user" / ISO at / 仓内已提交 blob |
| D-i 未动 | `AUTHORIZED_EXCEPTION_ASSERTION_IDS` | ✅ 仍单元素 class-1，白名单零扩项 |
| D3-v2 删净 | grep 链式/own-review/covers_through_task | ✅ 逻辑全删，仅余 3 处 compat 注释与 `_resolve_task` docstring（task:<id> scope 仍需该函数，合理） |
| A1-A8 | 重跑 `61-adversarial-d3v2.driver.py`（双仓参数） | ✅ 16/16 PASS；A8b「例外无前缀命中不担保任何段」语义正确 |
| fixture 终态 | 重跑 `validate-all-stages.py` 双仓 | ⚠️ funding = 15 green + 1 g_w_e + **8 red**（见 F1）；模板仓 1 green ✅ |
| 测试 | 全量 pytest + 前端自检 | ✅ 375 passed + 80 PASS（含 py_compile） |
| T7 反向漂移防护 | grep 契约残留 + `git show 82e2ef5 -- schemas` 逐行分类 | ✅ `base_raw_unavailable`/`deferred contract-amendment` 契约 0 残留；schema diff 仅 description 行，零结构 |
| T0 | 模板仓 Stage A status | ✅ `accepted` + user_acceptance + 证据缺口如实登记（未补造） |
| T5 carve-out | `_template/status.json` 字段 + 66 留档 | ✅ `session_receipts`/`reporting_preferences` 保留 + `coverage_waypoints` 新增（merge-not-copy 兑现） |
| 迁移表 | 64 内容抽查 | ✅ docs-truth-sync 标 known_red(class-2, D-i pending)；kimi 申报的 2 新 known-red + 2 预期外翻绿均已登记 |

## Findings

- **F1（P2，账面收尾，一行可修）**：收口 commit `6cccd2e` 在 67 终态比对**之后**新增了
  `red-gate-greening-v1` 自己的 status.json，使当前 main 上 fixture 实跑为 **8 red**
  （67/迁移表记 7）——本 stage 自身成了一条未登记的红，字面违反「无未登记的红」验收
  口径。属自指顺序问题（终态比对无法包含记录终态比对结果的那个 commit），非实质缺陷。
  **修**: 64 迁移表补一行（red-gate-greening-v1 = known_red，直修模式账本、非
  stage-delivery 运行记录），可由 bookkeeper 随用户终审前的任一 commit 带入。
- **F2（P3，交付叙述精度）**：总账称 D3-v2「净 -113 行」；commit numstat 实为
  `validate-stage.py` +141/-172（净 -31，T1 commit 全量 +200/-178）。删除事实本身已
  实证（链式/own-review/covers_through 逻辑全无），仅行数口径与账不符，无实质影响。

## 对 Kimi 申报的两处偏差的认定

- T0 字段实际位置在 `stage_branch.` 嵌套下：派工包描述不准，Kimi 按实修正并留痕——**正确**。
- 基线新发现 2 known-red（env-startup / local-service-launchd）+ 2 预期外翻绿
  （phase2-borrow-sort / private-account）：均已入迁移表并复跑验证——**正确**，且正是
  T2a golden 基线设计要捕获的那类事实。

## 结论

10 步全部落地且经我逐项重放成立；执行质量高（A8b 是 Kimi review 时自己坚持加的边界，
实现也守住了）。建议：bookkeeper 一行修掉 F1 → 用户终审 → 两仓 push。F2 记录在案即可。

---

## Addendum（追加，evolve-by-note）：读 gpt5.6-sol 并行 review 后修正结论

gpt5.6-sol（codex session 019f7065，原文存 69-）判 REWORK（3 P1）。我逐条独立复核后
**修正本评审结论：ACCEPT → 同意 REWORK（有界，三项修复）**。

- **其 F1（fixture compare 只比 verdict）——证实，我漏了。** `validate-all-stages.py`
  compare 循环仅比较 `old['verdict'] != record['verdict']`，错误多重集与
  applied_exceptions 不在比较范围（`:127-140` 当场可见；其 sentinel 注入实验成立）。
  这意味着 golden 门兑现不了迁移表「无未登记错误集变化」的口径。我此前只重跑了工具、
  未对 compare 语义做对抗探测——评审深度不足，认账。此为真 P1，必修。
- **其 F2（封印证据是转述非原文）——证实，并修正我此前的仲裁。** 70-handoff:35-38 实为
  转述（"user explicitly declined … authorized the documented fast-route override"），
  无用户授权原文；D2 硬化 2 要求 evidence 含 verbatim。此前 opus4.8-F3（严格读法）与
  kimi（称 :35-38 含 verbatim）冲突，我采了 kimi——**kimi 的引文把 status.json
  `user_acceptance.instruction` 里的原文与 handoff 的转述混为一谈，我未逐字复核原文即
  采信，08 派工包又将此误传给实现者**。修法同意 codex：evidence_file 改指含用户原文的
  `09-user-authorization.md`，重算 digest、修 reason，干净 main 复跑 pre-accept。
- **其 F3（本 stage 第 8 红）——红的事实与我 F1 同源，处置建议有分歧。** codex 要求补齐
  全套 stage-delivery 文件（10-design/11-adr/20-implementation…）转绿；我建议**登记
  known_red**（直修模式账本，其真实产物是 06/07/08/60-67，为过门去伪造 stage-delivery
  形态的文件反而制造账实不符）+ 补齐 session_receipts 与 60- 页脚（这部分 codex 对）。
  处置取向请用户定。

修复路由维持 codex fix prompt：Kimi 修 F1/F2/F3 → Fable5 + gpt5.6-sol 重审。

---
模型身份: Fable 5（anthropic/claude-fable-5，Claude Code CLI；session id 未暴露）
本地北京时间: 2026-07-18 01:20（Addendum 时间；正文 00:54）
下一步模型: kimi（修 F1-F3，F3 处置待用户定向）→ fable5 + gpt5.6-sol 重审 → human（终审 + push）

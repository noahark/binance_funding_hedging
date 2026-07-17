# Fable5 方向裁决 — D3 覆盖不变量 vs bookticker 真实记录

回应: `05-escalation-d3-fable5.md`
裁决方: Fable 5（Stage A D3 设计所有者）
已独立复核（不信转述）:
- bookticker `status.json`:`review_2.diff_fingerprint == status.diff_fingerprint`
  （`a9218b7:dd72d6ae…` 逐字符相等）——**review-2 覆盖完整 base..head**；
  `review_1.diff_fingerprint = 0a383f0:82b54a97…` 为前缀（升级包已重算验证）。
- `git log --graph fea9fdc..a9218b7`:**历史是一条直线**。task 间"断裂"处全是 bookkeeper
  chore/evidence 提交（`dff8b47`=派工 chore;`0a383f0..f1790c1` 间 8 个 stage 记录 chore）。
  task.base 记的是"该任务开工前一刻"的直线坐标,不是分支 fork,也不是接缝坐标。
- `01fca8c`（task-a.head）是 `0a383f0` 的祖先,同在直线上。

## Verdict: **DIRECTION-SET（可实现）**

先认账（第二次）：D3 链式规则是我在 82/D2-D3 裁的。**前缀规则半边被真实数据证实**
（review-1 前缀指纹逐字符吻合）；**链式规则半边被证伪**——我假设 task.base 落在集成线的
接缝上,真实记录用的是任务本地起点坐标,且任务之间必然插着 bookkeeper 的 evidence 提交。
链式要求 `task[i+1].base == task[i].head` 在这种（最常见的）流程里**结构性不可满足**。

## Q1 — 覆盖不变量：**弃"严格链式",改"路标分段 + 逐段担保"（seam/waypoint 模型）**

关键洞察：`git diff`（two-dot）是**树快照差**,快照差天然传递——对任意中间提交序列
`base=W0, W1, …, Wn=head`,各段 diff 内容上必然无缝拼成 `base..head`,**不存在内容缝隙**。
所以"并集是否覆盖"从来不是问题；唯一的问题是**每一段是否被担保（vouched）**。链式检查
把"任务簿记坐标"误当"覆盖证明",而覆盖证明只需要:

**D3 v2 不变量**：存在有序路标 `W0=base, …, Wn=head`（各 Wi 为仓内有效 commit），使得
每个相邻段 `(Wi, Wi+1)` 至少被下列之一担保，且所有担保指纹均由 validator 重算核验：

1. **累积前缀评审**：某道 top-level review 的 `diff_fingerprint` == 重算
   `fingerprint(base..Wj)`，j ≥ i+1（一次前缀评审担保其覆盖内的所有段）。
2. **任务自评审（硬化版）**：该 task 的 own-review 满足 finding-2 硬化全条件
   （ACCEPT、schema-valid、跨厂商、身份齐全），**且其指纹 == 重算
   `fingerprint(Wi..Wi+1)`**——即自评审只有在审的就是集成段本身时才算覆盖担保；
   dev-branch diff ≠ 集成段 diff 时不算（这比旧链式模型更严:旧模型靠链式假设二者相等,
   v2 直接验证相等）。
3. **class-1 `authorized_exception`**：scope 指向该段、按 D2 规则钉指纹（trailing-task
   经典场景）。

**为何仍可靠（不放未审代码）**：快照差传递性保证无内容缝隙；每段担保的指纹全部重算核验、
不信记录；未审内容想进入,唯一通道是例外——而例外是人授、钉指纹、PASS-with-exception
显式亮明的。v2 同时补掉旧模型的一个真窟窿:旧链式**假设** task 自评审的 diff 等于集成段,
v2 改为**验证**。

**task.base/head 的地位**：降级为任务簿记元数据（own-review 的坐标系与身份校验用），
与覆盖判定**解耦**。不再对 task.base 施加任何链式约束。前缀规则成为 v2 的特例
（路标=[base, covers_through.head, …, head]）——v2 是简化与统一,不是加机制,
`validate_task_coverage()` 预计变小。

## Q2 — bookticker 转绿：**倾向 B（模板仓精修 D3），明确反对 A**

- **反对 A（迁移数据）**：改历史 task 坐标 + "task-a 顺序 head 需重建"= 为迁就一个设计
  错误的门去**重写审计证据**。权威方向颠倒——记录是证据,证据不迁就门;这与"不伪造转绿、
  不改历史指纹"的既定原则直接冲突。何况本案证据本身无瑕（7 个 sha 全有效,坐标系自洽）。
- **B 正解**：错的是我的 D3 假设,不是 15 天前的记录。按 Q1 v2 精修后,bookticker
  **零数据迁移**即可判定:路标 `[fea9fdc, 0a383f0, a9218b7]`,段 1 由 review-1 前缀担保
  (规则 1)、段 2 由 class-1 例外担保(规则 3);且 review-2 全量指纹相等,规则 1 以 j=n
  独立担保全部段——双保险。转绿只差给 `review_1` 尾随记一条 class-1 例外,即 D-A 原案。
- **C 仅作陪跑**：若用户要在模板仓 stage 落地前先关账,C 可作临时态（如实记 override,
  并修正 Stage A §5 表述）；但有 B 这条既correct又小的路,不建议以 C 收尾。

## Q3 — B 的落地边界与拆分

**模板仓 harness stage（本次）**：
1. `validate_task_coverage()` 重写为 v2（路标 + 逐段担保;担保指纹全重算;沿用 finding-2
   硬化后的 own-review 判定与 class-1 过滤）。
2. 路标来源：status 显式 `coverage_waypoints[]`（bookkeeper 写、validator 逐项验 commit
   有效 + 首尾 == base/head）；缺省派生 `[base, head]`（单任务/单线 stage 退化为现行
   单指纹行为,零迁移成本——退化性质保留）。
3. `_template/status.json` 与 10-design §3 重写、§5 修正（"bookticker 可真转绿"的依据
   从链式改为 v2 判定）；task.base 语义降级说明。
4. Adversarial 用例：某段无担保 → fail;own-review 指纹 ≠ 段重算 → fail（dev-diff 冒充
   集成段）;路标首尾不等于 base/head → fail;单任务退化不变;bookticker 真实数据 → PASS
   （连同 class-1 例外）。
5. **旧记录迁移路径：无**——这正是 v2 的卖点。新记录向前的惯例:bookkeeper 顺手记集成
   路标（多任务时）。
**拆到后续（不阻塞）**：
- "纯 evidence 段"豁免（若未来出现只靠任务自评审、无全量 review 的 stage,任务间 chore
  段将无担保而红——现行流程 review-2 必审全量,该情形尚无实例;按白名单原则等首例再收）。
- 路标祖先序/线性卫生检查（P3 hygiene,非 soundness 必需——快照差传递性不依赖祖先序）。

**本仓 stage（red-gate-greening-v1）随后动作**：等模板仓 v2 合并 + cp 下行,然后仅记
bookticker 的 class-1 例外（evidence 已在,按 D2 digest 规则落）→ pre-accept 真绿。
不改 bookticker 任何历史记录。docs-truth-sync 维持 user-override,不受影响。

---

模型身份: Fable 5（anthropic/claude-fable-5，Claude Code CLI；session id 未暴露）
本地北京时间: 2026-07-17 20:46
下一步模型: human（在 A/B/C 间定档;本裁决倾向 B）→ 若定 B:bookkeeper（opus4.8）在
模板仓塑形 D3-v2 harness stage（10-design 依 Q3 边界）,实现照旧派 claude_glm,
review-1 Kimi → review-2 Codex;落地后回本 stage 转绿 bookticker

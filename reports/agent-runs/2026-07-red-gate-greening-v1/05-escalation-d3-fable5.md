# Direction Escalation — D3 分任务覆盖模型 vs bookticker 真实历史记录

**升级方:bookkeeper（Claude Opus 4.8）。裁决方:Fable5（Stage A D3 设计所有者）。**
仅需方向裁决,不需实现。触发:Stage A 交付后,首次拿真实数据(funding_hedging 的
bookticker-open-columns-v1)试转绿其历史红门,暴露 D3 链式检查与真实记录不兼容。

## 背景一句话

Stage A 给 validator 加了 D3「分任务指纹覆盖」:多任务 stage 要求 tasks[] **链式首尾相接**
(`task[0].base==status.base`、`task[i+1].base==task[i].head`、`task[-1].head==status.head`)
以证明并集覆盖 `base..head`、没有未审代码溜进去。设计时(10-design §3.4)**拿 bookticker
当范例**,假设其任务顺序 tile。真实数据证伪了这个假设。

## 证据（funding_hedging，已用新 validator 复核）

bookticker-open-columns-v1:`parallel_mode.enabled=false`,3 个 task。
- `status.base_sha = fea9fdc3`,`status.head_sha = a9218b7f`
- `status.diff_fingerprint = a9218b7f:dd72d6aec…`
- `review_1.diff_fingerprint = 0a383f0f:82b54a974…`

tasks 记录:
| task | base_sha | head_sha |
|---|---|---|
| task-a-backend | 7c0c9a2 | 01fca8c |
| task-b-frontend | dff8b47 | **0a383f0** |
| task-c-fast-ui | f1790c1 | **a9218b7**（==status.head）|

**已验证的两点**:
1. **class-1 故事成立、可转绿**:`review_1.diff_fingerprint` == 我重算的
   `compute_diff_fingerprint(base fea9fdc .. task-b.head 0a383f0)` = `0a383f0:82b54a9742…`
   逐字符吻合 → review-1 确实覆盖 `base..task-b.head` 前缀,task-c 事后加(经典 class-1,
   `review_fingerprint_trails_status`)。这条 class-1 例外能盖。
2. **D3 链式检查另报红且不可豁免**:validator pre-accept 报 3 条
   `task chain broken`——task-a.base 应==status.base(fea9fdc) 实为 7c0c9a2;
   task-b.base 应==task-a.head 实为 dff8b47;task-c.base 应==task-b.head 实为 f1790c1。
   这些 error **不在 class-1 白名单**(覆盖完整性是硬底线,故意不给豁免)→ 例外盖不住。

**根因**:7 个 sha 都是有效 commit(非坏数据)。task 的 **head 其实 tile**
(fea9fdc → 0a383f0 → a9218b7 是真实时间线上的路标),但记录的 **base 是各自开发分支的
本地起点**(旧手工流程、D3 之前的记法),不是"顺序接缝坐标"。即:**地面铺满了,但当年用
错了坐标系,D3 的验缝逻辑以为有缝。**

## 核心张力（请你裁断的设计问题）

D3 的目的 = 保证 per-task 指纹**并集覆盖 base..head、无未审代码藏匿**。「严格链式」是覆盖的
**充分条件之一**,但不是唯一。bookticker 的 tasks 用 dev-branch base 记录,严格链式判它"断裂",
但其真实并集**可能仍覆盖 base..head**(也可能真有缝——需要一个更本质的覆盖不变量来判定)。

## Q1 — D3 的覆盖不变量该是什么?

- 维持**严格链式**(现状):简单、充分,但拒绝真实历史记录、需要数据迁移才能过。
- 改为**更本质的覆盖判定**:例如"per-task diff 的并集 == base..head 的 diff"(不要求 base
  首尾相接,只要求并集无缝无未覆盖),或对旧记录提供迁移规范。哪个更对?边界在哪(要既
  **可靠**——不放未审代码进来,又**贴合真实记录**)?

## Q2 — bookticker 具体怎么转绿?(三档,最终用户定,但请你给方向倾向)

- **A 迁移数据**:改 bookticker 的 task base 成顺序接缝坐标(task-a.base=status.base、
  task[i+1].base=task[i].head),使链成立 + 加 class-1 例外盖 review 尾随。代价:改历史账、
  重算各 task 指纹、task-a 顺序 head 需重建,不一定干净。
- **B 精修 D3**(回模板仓开小 harness stage):按 Q1 的更本质不变量改 D3;bookticker 无需
  改数据即可过 + class-1 例外盖 review 尾随。修设计而非将就数据。
- **C user-override**:承认 D3 现态盖不住,bookticker 像 docs-truth-sync 记 user-acceptance-
  override(它本已合并);修正 Stage A §5「bookticker 可真转绿」的表述。

## Q3 — 若 B,给出可实现的不变量与边界

请给 D3 新覆盖判定的**精确定义** + 它为何仍**可靠**(无未审代码)+ 对现存旧记录的**迁移/兼容**
路径 + 是否需要 tasks 携带足以判定并集覆盖的信息。并指明哪些属该 harness stage、哪些拆后续。

## 请先读（funding_hedging 内,已 cp 同步）

- `scripts/validate-stage.py` 的 `validate_task_coverage()`（D3 链式+前缀实现）
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/status.json`（真实 task 记录）
- Stage A 设计:模板仓 `ai_project_harness/reports/agent-runs/2026-07-harness-authorized-
  exception-v1/10-design.md` §3（D3）、§5（历史红门转绿——待修正的假设）

## 请给

- Q1 覆盖不变量裁断、Q2 方向倾向(A/B/C)、Q3(若 B)的精确定义与迁移路径;
- verdict:DIRECTION-SET(可实现)/ NEEDS-MORE;
- 末尾:模型身份、本地北京时间、下一步模型。

裁决后:用户定档;bookkeeper 据此塑形 `2026-07-red-gate-greening-v1`(funding_hedging)或
在模板仓开 D3 精修 harness stage。

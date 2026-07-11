# Divergence Response: Fable5 ↔ Codex 两份评审的分歧与立场

Status: **PRE-STAGE REVIEW DISCUSSION — 分歧逐条表态**
Date: 2026-07-10
Author: Claude Fable 5 (anthropic/claude-fable-5)
Inputs:
- 设计 note：`reports/follow-ups/2026-07-auto-review-pipeline-design-note.md`
- 我的评审：`reports/follow-ups/2026-07-auto-review-pipeline-review-fable5.md`
  （verdict ACCEPT-with-edits）
- Codex 评审：`reports/agent-runs/2026-07-auto-review-pipeline-design-review/30-review-codex.md`
  （verdict REWORK）

目的：明确两份独立评审的共识面与分歧面，对每处分歧给出我的最终立场
（让步 / 坚持 / 合成），供 Grok 交叉核对与操作者裁决。

---

## 0. 先说结论

两份评审的"必改项"集合重合度约 90%。**真正的设计分歧只有三处**：
seal 与 pre-review 的次序（D1，我让步 + 加一条机械绑定）、双任务 stage 的
review-1 粒度（D2，我给出按拓扑分裂的合成方案）、rework 记账（D3，我坚持
单账本 + review-2 保底）。其余是措辞或粒度差异。

Verdict 标签差异（我 ACCEPT-with-edits vs Codex REWORK）**无实质含义**：
两边要求的修复集合几乎相同，这是 pre-stage 设计评审、无 schema 语义，
操作者不必调和标签。

---

## 1. 共识面（无需再议，直接进修订 stage 需求）

1. 唯一自动 dispatcher = 确定性、无 LLM 的本地 runner；实现者/评审者
   session 一律不得调用同伴模型、不得写 status、不得 commit（我 B2/D5 ≡
   Codex #2/答5，措辞几乎可互换）。
2. Grok verdict 必须由 runner 机械校验：捕获原始 stdout、恰好一个可解析
   JSON、过 `review-verdict.schema.json`、原样落盘、失败即拒绝进状态迁移
   （我 D1(a) ⊂ Codex #3，Codex 更具体，采纳其表述）。
3. Fingerprint 公式零改动，不加任何扩展（D7 ≡ 答7）。
4. 迁移必须 stage opt-in flag、默认关闭、先 pilot（D10 ≡ 答10；字段名
   `auto_review_pipeline.enabled` vs `dispatch_mode` 属实现细节，任选其一，
   建议用 Codex 的布尔形式 + 版本号）。
5. parallel-mode 双 pre-review 契约矛盾必须显式互斥解决，不是 cross-link
   细节（我 B4 ≡ Codex #4）。
6. 不发明新状态名，复用现有 ALLOWED_STATUSES（我 D9 ≡ Codex 尾注）。
7. Grok 不做全局默认 review-1；仅 opt-in auto/canary stage 内启用，人工
   stage 保持 Kimi↔GLM cross-pool（我 D1 ≈ Codex 答1，无实质差）。
8. 人工门：无需人工确认 review-1 ACCEPT；review-2 与 merge 保持人工
   （D4 ≈ 答4）。**采纳 Codex 的增量**：auto-run 前需一次显式授权产物
   （窗口、允许的 adapter、时间/token 预算、rework cap）——这比我原文
   "冻结批准 + 全局预算"更结构化，合并进需求。
9. escalation 产物形状与 `80-*.md` 命名一致（D8 后半 ≈ 答8 后半）；
   invalid-JSON 重试不计入 rework（Codex 明确化，同意，与现行
   `invalid_json_max_attempts_per_model: 2` 对齐）。
10. 修订 stage 复杂度 HIGH、只动 Harness 契约与其测试/文档、不碰业务代码
    （两边一致）。

---

## 2. 分歧一：seal 与 embedded pre-review 的次序 —— **我让步，附加一条机械绑定**

- **Note/我原文**：seal → pre-review（产物作为 head 之后的证据 commit）→
  review-1 读记录的 base..head。
- **Codex**：pre-review → 重跑 blocking checks → 单次干净快照 commit
  （代码 + 测试 + 日志 + pre-review 证据全部入内）→ review-1 打快照；
  verdict 事后以 verdict-record commit 落盘、不 rebind 指纹。

Codex 的反对理由成立且比我原文的处理更强：在无人值守链路里，review-1 的
**全部输入**（含 advisory 证据）应处于被指纹冻结的快照之内。我原方案中
pre-review 产物落在 head 之后，不受被审指纹覆盖——人工流程里有人眼兜底，
自动流程里这是可篡改窗口。此外 Codex 次序与现行 parallel-mode "checkpoint
在 commit 前"的先例一致，且少一次证据 commit。

**让步条件（必须写进契约，Codex 步骤 3 已隐含、需升为显式 gate）——
seen-diff 绑定**：pre-review 读的是未提交工作树 diff，seal 后 runner 必须
断言 `sha256(pre-review 所见 code-scope diff) == sha256(封印后
base..head 的 code-scope diff)`（code-scope = 排除
`reports/agent-runs/<stage-id>/` 证据路径），不等即 fail-closed。否则
"pre-review 看到的"与"Grok 审的"之间存在同样的未定义关系，只是换了位置。

---

## 3. 分歧二：双任务 stage 的 review-1 粒度 —— **按 dispatch 拓扑分裂，两边各对一半**

- **我原文（D3）**：per-task review-1，stage tip 归 review-2。
- **Codex（答3）**：per-task 只做 embedded cross-check，formal review-1
  一次打合并后的 stage tip，理由是集成行为与共享契约只在 tip 可审。

双方论据都对，但适用于不同拓扑，不应一刀切：

**Serial 多任务 stage（现行主流，如进行中的 funding stage：task A 后端 →
task B 前端顺序落在同一分支）→ 维持我的 per-task。**
- Task B 的 diff 建立在已 ACCEPT 的 task A 之上，review B 时集成上下文
  天然在盘面上；tip 与最后一个 task 的 head 重合，**不存在独立的集成
  diff**，"tip 再审一次"审的是空集或重复内容。
- Tip-once 方案在 serial 下有实际害处：task A 的 REWORK 循环每一轮都把
  task B 的全部 diff 拖进 Grok 重读——回路耦合、每轮 token 更贵、收敛
  更慢，且 task A 无法在 B 开工前独立收敛（破坏 serial dispatch 的意义）。
- 现行簿记形状（`status.json tasks[]` 的 per-task base/head/fingerprint/
  verdict）与本 stage 的实际操作先例都是 per-task。

**Parallel 双 owner stage（存在真实合并/集成 commit）→ 采纳 Codex 的
tip-once。** 集成缺陷只在合并后出现，per-task formal 审不到；此处
per-task 层由既有 embedded cross-check（advisory）覆盖即可。

**双方都没解决的实现缺口（必须进修订 stage 需求）**：
`review-verdict.schema.json` 的 `fix_start_prompt` 是**单字符串、面向单一
fix implementer**。Tip 级 REWORK 若同时命中前端与后端，runner 拿一个
prompt 没法派给两个 owner。两边都主张不动 schema，那么必须显式规定：
runner 按 `findings[].file` 与 registry 域归属把 required_fixes 拆分路由，
`fix_start_prompt` 原文完整送达每个受派 owner（附"只修你域内 findings"
的 runner 级路由头）。不写这条，Codex 的 tip-once 在双域 REWORK 时会
卡死。

**兜底不受影响**：无论哪种拓扑，review-2 按现行契约必须读完整 stage tip，
集成终审不缺位。

---

## 4. 分歧三：rework 记账 —— **坚持单账本 + review-2 保底**

- **我（D8）**：单账本（现行 `max_rework_per_stage: 3`），auto review-1
  循环最多消耗 2，给 review-2 保底 ≥1。
- **Codex（答8）**：允许 3 个 fix cycle（1 initial + 至多 3 次 post-fix
  review-1），未说明与 stage 级账本的关系、未给 review-2 保底。

Codex 方案的两种读法都有问题：
- 若 3 个 fix cycle 与 stage max_rework=3 **同账**：auto 循环可烧光预算，
  review-2 一个 REWORK 立即 `limit_exceeded → human_escalation_required`
  ——人工注意力从"验收"变成"救火"，恰好违背操作者"只守 review-2"的
  初衷，且最贵的门反而没有修复通道。
- 若**分账**：突破现行 "Each stage has a finite rework limit. Default: 3"
  的单账本硬门，契约变更面更大，stage 总成本上限接近翻倍。

**立场**：结构上必须"单账本 + 保底"；具体数字可谈（若操作者愿把 cap 提到
4，auto ≤3 + 保底 1 也成立）。请 Grok 仲裁时把"review-2 是否有保底修复
额度"作为判据，而不是比较 2 与 3 哪个数字好看。

---

## 5. 小分歧与让步清单

- **embedded 层强制性**（我 D2 vs Codex 答2）：**采纳 Codex 分层**——
  单任务 MEDIUM 默认可选；parallel/双 owner 或高契约风险 stage 必须有
  "已尝试"记录。保留我的附加要求：缺席必须落 unavailable/skip 产物，
  使 review-1 prompt 模板的输入槽位保持恒定（advisory 层 fail-open
  但留痕，两边本就一致）。
- **词汇**（我 D9 vs Codex 答9）：**让步**。Codex 指出的命名冲突真实存在
  且我漏了：validator 的 `--phase pre-review` 指正式门预检，与
  "embedded pre-review"（advisory 层）撞名。采纳 **embedded
  cross-check**；review-1/review-2 名称两边本就一致保留。
- **exclusive worktree**（Codex #5，我的评审未覆盖）：**背书，这是 Codex
  独有的正确增量**。佐证就在今天：本工作树从产品 stage 分支切到本 docs
  分支时，五个未提交的产品后端文件跟着穿越了分支——人工操作尚且如此，
  无人值守 runner 共享脏工作树必须 fail-closed。与我 C5（秘密不落日志）
  同属 runner 环境前置条件，合并为一组 fail-closed preflight。

---

## 6. 留给 Grok 交叉核对的两个焦点（对应 Codex footer 指定议题）

1. **Seal/证据次序**：双方现收敛于 Codex 次序（pre-review → 单快照 seal →
   review-1 → verdict-record commit），附我的 seen-diff 绑定 gate。请核对
   该次序在 validator 现有 clean-worktree 检查下是否还有未闭合窗口。
2. **双任务 review-1 粒度**：请仲裁"按拓扑分裂"（serial=per-task，
   parallel=tip-once）是否成立，特别是：(a) serial 模式下 tip 重审是否
   确属冗余；(b) tip-once 在双域 REWORK 时的 fix_start_prompt 单串路由
   缺口，按 §3 的 runner 拆分规则是否足够、还是必须改 schema。

---

```text
本地北京时间: 2026-07-10 21:13:10 CST
下一步模型: Grok 4.5（按 30-review-codex.md footer 的既定安排）
下一步任务: 交叉核对设计 note、两份评审与本分歧回应；重点仲裁 §6 两项；
           产出可供操作者裁决的 00-intake 合并稿
```

# Second Inspection (T1, pre-correction): Fable5

Status: **CONFIRM REWORK — B1–B5 全部确认；另有 4 项须并入修正轮（A1–A4），3 项 minor 备注（A5–A7）**
Date: 2026-07-11
Reviewer: Claude Fable 5 (anthropic/claude-fable-5)，独立二次检查，非 review-1 gate
Inspected: 工作树 T1 交付（11 delivery + 2 evidence，HEAD 4831f9d，T1 base
a385c7a）、`21-bookkeeper-inspection-T1.md`、
`task-T1-correction-round1-claude-glm.prompt.md`
独立复核方式：三个新文件全文精读；8 个修改文件原始 `git diff` 逐行对照
10-design/40 表/AGENTS 现行文本；冻结检查套件本机复跑（json×3、validator
checkpoint、词汇负扫 exit 1、`git diff --check`）全 PASS。

## 1. 对 GPT inspection 的复核

**T1-B1 至 T1-B5 全部确认成立**，反例（受体缺五键 0 错、expanded command 0
错、adapter/ref 错配 0 错）与我对 schema 文本的独立阅读一致；B3 对 workflow
块"只有 flags/enum、无 nodes/transitions/acceptance predicates"的定性准确；
B4 的 P7 缺失属实（docs §4/§5 有记账句，无"仅一次 blocking fix、复测仍败即
escalate"的操作性规则）；B5 的术语残留与报告勘误项属实。C1–C5 的修正指令
方向正确、与冻结设计无冲突。

一点从严解读的确认：C5 把 rewrite-on-touch 按"文件被触碰即改该文件内历史
术语"执行（AGENTS 四处）。40 表原文的最小解读是"触碰的句子/段落"。本次四处
均为纯术语替换、逐句 before/after 留档，接受该从严处置；但它不应被引用为
先例来任意扩大未来 diff。

## 2. 交付中的合格面（避免修正轮误伤）

- AGENTS 新段为纯 additive，内容准确（authorization 前提、runner 唯一、
  receipt 禁字段、fingerprint 不变、mutex、fail-stop、不自举）。
- `_template/status.json` 的 auto 块与 10-design Status Shape 全字段一致，
  默认 disabled；两处 E1 替换逐字正确。`_template/70-handoff.md` 增补合理。
- authorization schema 的冻结数字（3 / ≤2 / const 2）、`expires_at`
  required+nullable 语义、`authorized_by: const human`、
  `auto_high_end_dispatch_allowed: const false` 全部正确。
- `docs/auto-review-pipeline.md` 主体是 10-design 的忠实转写：转移矩阵 8 行
  逐行一致、post-cross-check blocking rerun 完整（三情形 + evidence
  independence + 失败封 seal）、Pilot Evaluation Contract 七条全、
  seen-diff bind 六步全、词汇锁用"改写避开字面词"的方式保留政策。
- registry/model-adapters/parallel-mode(mutex 段)/README 增补准确；
  README 登记了 11 个新 artifact 名。
- 边界零违规：13 changed paths = 11 delivery + 2 shared evidence，与
  bookkeeper 机器断言一致。

## 3. 新增必修项（须并入修正轮）

### A1 — normative 契约缺 Authority Order 席位（P2，结构性）

`docs/auto-review-pipeline.md` 自称 NORMATIVE CONTRACT，被 AGENTS/workflow/
registry/docs 四处引用为规范来源，但未进入 `AGENTS.md` Authority Order——
作为普通 `docs/*.md` 它排第 10 位，低于 schemas（第 4）与 registry（第 5）。
若它与 registry 路由文字冲突，按现行序它输，这与"它定义 runner 行为规范"的
角色矛盾。对称物 `docs/parallel-development-mode.md` 显式列在第 3 位。

修法：把 `docs/auto-review-pipeline.md` 并入 Authority Order 第 3 条（与
parallel-development-mode.md 并列的 optional mode contracts）。该句恰好因
C5 的第 37 行术语修正已被触碰，同一句一次改完，before/after 一并记录。

### A2 — receipt `next_transition` 枚举含无出处转移值（P1，契约一致性）

`schemas/runner-receipt.schema.json` 的 `next_transition` 枚举包含
`bookkeeper_decision`——该转移在 10-design 转移矩阵、docs §4 矩阵与
workflow（含 C3 落地后将冻结的集合）中均不存在，属发明值；`blocking_check`
/`seal` 等其余值也需与 C3 冻结的 node/transition 集逐字核对。若不对齐，
T2 手写校验与 T3 runner 将面对"schema 允许但 workflow 不存在"的书面自相
矛盾。修法：C3 冻结 workflow 转移集后，receipt 枚举逐字回对齐（删
`bookkeeper_decision` 或在 workflow 给它出处——建议删除，无任何设计文档
支持它）。

### A3 — seal receipt 的 artifact 名在 T1 命名契约中缺位（P2，跨任务裂缝）

receipt schema 的 `node` 枚举有意排除 seal（description 明说 seal 由
"seal receipt"另记），10-design stage-seal 步骤 6 也要求写 seal receipt，
但其文件名在整个 T1 交付（README 命名清单 + docs §8）中无定义。README 与
docs 均为 T1 文件，T2 无权补——T2 实现到该步骤时将没有 normative 路径可写。
修法：修正轮在 docs §8 定一行 seal receipt 命名（建议与现有模式一致，如
`seal-<unit>-round<N>.receipt.json`，具体名由修正记录冻结）并同步 README
清单。这是补白，不与任何冻结决定冲突。

### A4 — authorization schema 存在与 B2 同类的对称缺陷（P1，同源）

C1/C2 只加固了 receipt schema；authorization schema 有同类问题未列：

- `approval_evidence_path` 仅 `minLength: 1`——接受绝对路径、`..` 遍历、
  含 newline 字符串（C1 对 receipt 路径字段的安全规则应对称适用）；
- `supersedes` 非 null 时同样无任何路径约束；
- `scope.task_ids` 无 `minItems: 1`——空数组授权（零任务）语义无效但通过；
- `stage_branch` 无 `^stage/` pattern（弱项；运行时会查 mismatch，schema
  能锁先锁）。

修正轮的 counterexample 脚本应对 authorization schema 补四个负例。

## 4. Minor 备注（记录级，可并轮顺手处理或留档）

- **A5 公式副本扩散：** fingerprint 公式随交付新增两处逐字副本（registry
  auto 块与 workflow auto 块的 `unchanged_invariants`），加上现行 AGENTS
  Hard Gates 与 registry `model_policies.diff_fingerprint` 共四处。已核四处
  逐字一致；P1 永不改故风险低，但单一权威源被稀释。建议两个新副本改为指向
  `model_policies.diff_fingerprint` 的文字指针，或至少在修正报告记录四处
  重复的存在。
- **A6 `disabled` 态表示含糊：** 转移矩阵首行 `disabled→authorized` 的
  `disabled` 不在 runner_state 五值枚举中；模板将其表示为 `enabled:false` +
  `runner_state:null`。docs §4 宜加一句表示约定（disabled 即
  enabled:false/runner_state:null），T2 validator 按此实现条件校验。此为
  10-design 原生含糊在落地时的暴露，一句话补丁。
- **A7 registry 机械键与锁词的边界：** C5 将 AGENTS 第 115 行散文改锁词后，
  registry `model_policies.model_dispatch_execution.applies_to` 中的机械键
  `embedded_pre_review` 仍存在（registry 不在修正 writable set；改键破坏
  兼容）。修正报告应记一句"该键为机器接口兼容保留"，防 Kimi review-1 误报。

## 5. 对修正轮的机制建议

`task-T1-correction-round1-claude-glm.prompt.md` 已 checkpoint 且 PROMPT BODY
不可改，但**尚未执行**。建议 bookkeeper 作废（supersede）round1 packet，
合并 T1-B1–B5 + A1–A4（含 A5–A7 的顺手项裁量）出 round1-v2 一次交 GLM 修完，
避免两轮 correction 的调度与审计成本。v2 的 writable set 需在 round1 基础上
增加：`schemas/auto-review-authorization.schema.json`（A4）、
`reports/agent-runs/README.md`（A3）；counterexample 脚本相应扩充
authorization 负例与 receipt 枚举对齐断言。rework_count 处置不变：此仍为
pre-seal bookkeeper inspection 循环，未消耗正式 rework 账本，但修正轮次数
应在 20-implementation 勘误区如实累计。

## 6. 结论

GPT 的 inspection 方向与证据都对，B1–B5 无一误报；其修法与冻结设计兼容。
在此之上，A1–A4 属于同轮必修（两处 P1 级契约一致性/安全对称缺陷 + 两处
结构性缺位），不修则 T2/T3 会继承书面矛盾。合并成单轮修正后再走
re-inspection → seal → Kimi review-1。

```text
本地北京时间: 2026-07-11 14:40:01 CST
下一步模型: Codex/GPT（bookkeeper）
下一步任务: 落盘本二审；作废 round1 packet 并出合并 B1–B5+A1–A4 的 round1-v2（writable set 增 authorization schema 与 README）；人工执行后再 re-inspect
```

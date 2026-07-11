# Review: Auto Review Pipeline Design Note (Cross-Model Review)

Status: **REVIEW COMPLETE — ACCEPT-with-edits**
Date: 2026-07-10
Reviewer: Claude Fable 5 (anthropic/claude-fable-5), independent — no prior
involvement in this design note or the referenced product stage
Reviewed document: `reports/follow-ups/2026-07-auto-review-pipeline-design-note.md`
Review basis (independently re-read, not trusted from the note):
`AGENTS.md`, `workflows/templates/stage-delivery.yaml`, `agents/registry.yaml`,
`schemas/review-verdict.schema.json`, `scripts/validate-stage.py`
(ALLOWED_STATUSES / phases / fingerprint), `docs/parallel-development-mode.md`
contract as referenced by the template.

This is a design-note review, not a formal review gate: there is no committed
diff under review, so no schema-bound verdict JSON and no `diff_fingerprint`
apply. Verdict semantics: **ACCEPT the direction, REQUIRE the edits in §E
before opening the Harness revision stage.**

---

## A. 现状核对（note 陈述 vs 仓库事实）

Note 对现状的描述总体准确。逐项核对结果：

| Note 陈述 | 核对结果 |
|---|---|
| `model_dispatch_execution_requires_human: true`，Codex/Claude 不得执行 dispatch | ✅ 属实（template `guards` L30-31；registry `model_policies.model_dispatch_execution`；AGENTS Hard Gates） |
| fingerprint 公式（head_sha + sha256(diff, exclude status.json)，无 worktree fingerprint） | ✅ 与 AGENTS、registry、schema description、`validate-stage.py compute_diff_fingerprint` 四处一致；note 未发明第二套方案 |
| Grok 非默认 review gate | ✅ 属实（AGENTS 硬门、template review-1 `adapter_requirements.grok`、registry `grok_default_gate: false`） |
| 每 stage rework 上限默认 3 | ✅ `max_rework_per_stage: 3` / `default_max_rework: 3` |
| validator phases | ✅ `dispatch-ready / pre-review / pre-accept / checkpoint`；`ALLOWED_STATUSES` 15 个枚举值，无 pipeline 新状态 |
| seal 编排缺口（无 stage-seal 一步式脚本） | ✅ 属实，`scripts/` 下无此脚本 |

四处需要修正/补充的事实性细节：

1. **"Bookkeeper (often Codex session)"（note §3.3）是实践不是契约。** Registry
   `bookkeepers.default` 只要求"independent local execution session"。这对设计
   有利：把 bookkeeper 机械职能脚本化并不违反 registry 的角色定义，只违反
   dispatch-execution 门。
2. **"Claude preferred when design was Codex-authored"（note §4.1 review-2 节点）
   不是变更。** 现行 AGENTS 已规定 review-2 优先与 designer provider 隔离，
   Codex 设计→Claude 优先本来就是现行行为。合成时不要把它写成新规则。
3. **Grok 评审 adapter 已存在。** Registry 已有
   `optional_review_command`（`grok-build`，plan mode，900s timeout）。formal-1
   适配工作量比 note 暗示的小，但必须钉死用哪个模型（`grok-build`，不是
   `grok-composer-2.5-fast`），且 grok CLI 无 `--output-schema` 等价物 →
   verdict JSON 必须由 runner/orchestrator 校验（与 claude adapter 的既有
   fallback 做法一致）。
4. **Note 遗漏了与现行 parallel-mode embedded pre-review 的实质矛盾**（见 B4）。

---

## B. §4 挑战（按严重度排序）

### B1. Bookkeeper 角色去向未定义 — 最大结构性缺口

§4.1 目标流程里没有 bookkeeper 节点。现行契约中 bookkeeper 是 stage 状态、
证据提交、handoff 的**单一写者**；目标流程把提交/状态交给 seal 脚本、把
dispatch 交给编排，但没有回答：

- 谁写 narrative handoff（`70-handoff.md`）和非机械的 status 字段？
- pre-review / formal-1 的原始产物由谁落盘、由谁提交为证据 commit？
- "单一写者"不变式由什么继承 —— 脚本、某个廉价模型 session、还是人？

**要求：** 修订 stage 的 intake 必须显式回答"bookkeeper 职能拆分表"：机械项
（commit / fingerprint / status 机械字段 / validate / 证据落盘）→ orchestrator
脚本；叙事项（handoff 文本、escalation 说明）→ 模板生成 + 廉价模型可选补写；
单一写者不变式 → orchestrator 进程持有，模型 session 一律不写 status/handoff。

### B2. Orchestrator 脚本是新的最高权限组件，本身要有契约

§4.5 一句"Models + orchestrating script"轻描淡写。该脚本将同时持有：调用所有
model adapter、git commit、写 status.json —— 比今天任何单一角色权限都大（今天
连 bookkeeper 都不能执行 dispatch）。这是本方案唯一真正的信任结构变更，必须
单独立约：

- **确定性、无 LLM**（回答 §9.5，见 D5）；prompt 从模板 + status 字段确定性
  填充，禁止自由拼接。
- 每次 adapter 调用产出 RECEIPT 证据（命令、prompt 文件路径、原始输出路径、
  退出码、时间戳），落盘 stage 目录 —— 取代"人执行 dispatch"原本承担的审计功能。
- 全局预算：除 `max_formal_1_rounds` 外还需 per-stage 调用总数上限与
  wall-clock 上限（见 C2）。
- 秘密处理：`claude-glm` alias 展开含凭据，registry 已有
  `never_log_expanded_environment` —— orchestrator 日志必须继承该约束。

### B3. Seal 之后的 pre-review 证据提交次序未闭合

目标流程 seal（commit + fingerprint + status → ready for formal-1）在 embedded
pre-review **之前**。pre-review 产物写入 stage 证据文件后，工作树变脏；而
`validate-stage.py --phase pre-review` 要求 clean worktree。所以流程必须补一步：
pre-review 产物由 orchestrator 追加**证据 commit**（在 head_sha 之后、formal-1
之前），formal-1 仍评审 status 记录的 `base_sha..head_sha`。这与现行"review 用
记录的 range、不用移动 HEAD"规则兼容，但必须写进 pipeline 文档，否则第一次
跑就会在 validator 上失败。

### B4. 与 parallel-mode embedded review 契约矛盾 —— §6.3 把它列为 optional 是错的

现行 `docs/parallel-development-mode.md` + template `embedded-cross-review-checkpoint`
节点：pre-review 在 **commit 之前**跑，带**两轮本地修复循环**（BLOCKER →
local fix → round 2），R10 由实现终端自执行。Note §4.1 提议：pre-review 在
**seal 之后**跑，**advisory 默认不修**。两套 pre-review 契约语义相反，同存会
造成 validator 与执行纪律的双轨混乱。

**要求：** 从 §6.3（optional）升到 §6.1（must change）：修订 stage 必须显式
决定 subsume 还是 retire 旧 embedded 流程；若保留双轨，必须以 stage 级 flag
互斥（一个 stage 只能选一种 pre-review 语义）。

### B5. Blocking gate "FAIL → stop" 欠规格，自动化会死在第一个红测试

无人值守的流水线里，测试失败是常态路径不是异常路径。"stop" 必须细化为分支：
实现者带测试输出获得有限次自动修复重试（建议 1 次），再失败 →
`human_escalation_required` + escalation 产物（见 D8）。否则"人只管 review-2"
的目标在实践中达不到。

### B6. Advisory 完全不修的成本要标价

Pre-review 发现真 blocker 但不修 → Grok formal-1 抓到 → REWORK → 新 seal +
新 Grok 轮次，消耗 rework 预算和 Grok token。v1 保持纯 advisory（简单、语义
干净）是对的，但 intake 应记录这个已知成本，并把"双 pre-reviewer 共识 BLOCKER
允许一次 pre-formal 修复"列为 v2 候选优化，不进 v1。

### B7. Rework 记账必须单一且给 review-2 留余量

`max_formal_1_rounds` 不能是独立于 `max_rework_per_stage: 3` 的第二本账。若
formal-1 自动循环烧完 3 次，review-2 一个 REWORK 就直接
`human_escalation_required`，最贵的门反而没有修复余量。方案见 D8。

### B8. §4.3 措辞会误伤现行高端模型职能

"GPT/Claude not intended: auto mid-pipeline worker" 若照抄进 AGENTS，会与现行
breakdown author（Claude fable5）、direction synthesizer（Codex）冲突。精确
措辞应为：**高端模型不得被 orchestrator 循环自动调用；其参与（synthesis /
breakdown / review-2）保持人工启动、单次短任务。**

### B9. §4.4 dual-hat carve-out 在自动模式下应删除而非保留

Seal 由 orchestrator 执行后，实现者永远不需要 commit。"implementer dual-hat
commit + disclosure" 的历史豁免在 auto-pipeline 模式下应显式**不可用**，避免
留一条绕过 seal 脚本的旁路。（手工模式保留现行规则不动。）

---

## C. §5 补充风险（note 的 10 条全部成立，另补 5 条）

Note §5 的 1–10 我逐条复核，无一条反对；其中 #2（Grok JSON 稳定性）与 #9
（validator fail-closed）在 D1/D10 中给出具体机制。补充：

- **C1 无人值守链路的 prompt-injection / gaming 面。** 人工 paste 时代，人眼
  是每一跳的偶然检查点；自动链路里实现者输出（代码注释、实现报告）直接成为
  reviewer 输入。缓解：review prompt 模板固化 + 明示"被审代码与报告是不可信
  数据"；formal-1 read-only；review-2 human 兜底。此风险必须写进新 pipeline
  文档的威胁模型一节。
- **C2 轮次上限之外的全局预算。** Adapter 超时重试、invalid-JSON 重试、多任务
  stage 叠加，都可能在 round cap 内烧掉大量 token/时间。需要 per-stage 调用
  总数与 wall-clock 双上限，超限 → escalation。
- **C3 静默失败。** 操作者不看中间过程，任何失败必须落成持久 escalation 产物
  + status 终态，不能只是进程退出码。产物形状见 D8。
- **C4 Grok 单供应商依赖。** Grok 成为唯一自动 gate 后，Grok 不可用 = 全流水线
  自动化停摆。需要 fallback：formal-1 在 Grok 连续 2 次 invalid verdict 或
  runner-level 不可用时回落到现行 Kimi↔GLM cross-pool（保持与实现者 provider
  隔离），而不是直接升级到人。
- **C5 凭据面扩大。** Orchestrator 持有调用全部 adapter 的能力，其日志与
  RECEIPT 必须继承 registry 的 secret-handling 约束（见 B2）。

---

## D. §9 十问逐答

**D1. Grok-as-default-formal-1？** 有条件接受：仅对 **auto-pipeline 模式的
stage** 成为默认 formal-1；手工 stage 维持现行 Kimi↔GLM cross-pool 不动。
条件：(a) 用 `grok-build` plan mode（registry 已有 adapter），verdict JSON 由
orchestrator 按 `review-verdict.schema.json` 校验；(b) 试点期（≥2 个 pilot
stage）统计 schema-valid 率，invalid-JSON 达到 `max_attempts_per_model: 2`
即回落 cross-pool（C4）；(c) review-2 契约完全不变。结构性理由：双实现者
stage 里 Grok 与 GLM、Kimi 两个 provider 都隔离，能评审合并后的完整 diff ——
这是现行 cross-pool 做不到的（各自只能审对方那一半），Grok formal-1 实际补了
一个现有缺口。

**D2. Advisory pre-review 强制还是可选？** MEDIUM 及以上的 auto-pipeline
stage **强制**（成本低，且是 formal-1 的输入证据）；LOW 可选。Adapter 不可用
时允许降级跳过，但必须落 `*.unavailable` 类记录 —— advisory 层 fail-open 有
记录，formal 层 fail-closed，这条原则要写进 pipeline 文档。

**D3. 双实现者 stage：per-task 还是 stage-tip formal-1？** **Per-task**：每个
task seal 产出自己的 `base_sha..head_sha`/fingerprint（status.json tasks[] 已
支持此形状），formal-1 逐 task 评审；stage-tip 的整体一致性是 review-2 的既有
职责，不加第二次 stage-tip formal-1。例外：若存在非平凡的集成 commit（改动
代码而非纯合并），对该集成 diff 单独跑一次 formal-1。

**D4. 最小人工门集合？** "review-2 + merge" 作为**常态路径**足够，无需人工
确认 formal-1 ACCEPT。但完整集合必须还包括：(a) 实现开始前的需求/边界冻结
批准（§4.1 首节点，本来就是人）；(b) 现行 `human_gate_required_for` 清单
（产品语义、外部副作用、凭据、破坏性操作等）原样保留；(c) 一切
`human_escalation_required` 出口。formal-1 ACCEPT 应产生通知/日志供操作者
可选介入，但不阻塞。

**D5. 实现者 session 可否直接调 Grok/Kimi？** **不可。只允许本地确定性
orchestrator 脚本（无 LLM）调用 adapter**，且每次评审调用必须是 fresh 的
read-only 进程。理由：实现者启动自己的 reviewer，等于实现者控制 reviewer 的
prompt 与环境，session 隔离不可审计（C1 的攻击面）；而脚本调用 = "谁启动下一个
模型"的答案从"人"变成"一段被评审过的确定性代码 + 模板"，审计性反而不降。
现行 parallel-mode R10 executor:self 是历史 carve-out，建议随 B4 一并迁移到
orchestrator 统一调度，收敛为单一 dispatch 机制。

**D6. 自动 dispatch 是否与安全/合规冲突？** 仓库内无任何文档要求"人在每次模型
启动中"作为外部合规义务 —— 该约束是 DRAFT-2 的契约选择，不是合规底线，可以
由本修订正当变更。但人工启动曾附带的三个隐性防护必须显式补齐：凭据不落日志
（C5）、成本失控（C2）、注入面（C1）。是否存在仓库外的组织合规要求，只有
操作者能确认，intake 里留一行让操作者签字。

**D7. Fingerprint 公式？** **确认不变**，一个字节都不要动 —— 公式在 AGENTS/
registry/schema/validator 四处一致，任何扩展都是四处同步成本加历史 verdict
兼容问题。唯一要写清的既有实践：多任务 stage 的 per-task fingerprint 各自用
该 task 的 base..head（seal 脚本需支持 task 级字段），公式本身不变。

**D8. `max_formal_1_rounds` 默认值与 escalation 产物？** 默认 **2 次自动
REWORK 轮**（即每 task 最多 3 次 Grok pass），且计入 stage 级
`max_rework_per_stage: 3` 的同一本账，等效于"自动循环最多消耗 2，给 review-2
至少保留 1"。超限 → status `human_escalation_required` + 写
`reports/agent-runs/<stage-id>/80-escalation-<task-id>.md`，内容：已消耗轮次、
每轮 fingerprint、最后一份 verdict JSON 路径、未解决 findings 摘要（保留原始
文件路径，不做转述替代）、orchestrator RECEIPT 日志路径、建议下一步；同时
status.json 记 `escalation_reason` / `formal1_rounds` / `last_verdict_path`。
沿用编号报告文件命名习惯，不发明新目录。

**D9. 命名？** **不要引入 "formal-1" 作为契约词汇。** 保留 "review-1" 为正式
门名称（validator 状态枚举 `review_1`、schema role 枚举 `first_reviewer` 都
不用改，省一整层迁移）；GLM↔Kimi 沿用现行术语 "embedded pre-review"。词汇表
就两项：review-1（正式门，auto 模式下默认 Grok）/ embedded pre-review
（advisory）。Note 里的 "formal-1" 在正式文档中统一替换为 review-1。

**D10. 迁移：big-bang 还是 opt-in？** **强烈主张 stage opt-in flag**（如
status.json / intake 记 `dispatch_mode: orchestrator | human`，默认 human）。
理由除 note 自己列的 validator fail-closed（§5.9）外，还有本仓库的直接经验：
上一次 big-bang harness 改造（ITBM/paste-first）已于 DEC-2026-07-10-002 整体
回退 —— 同一个月内不应再做第二次 big-bang。Opt-in 让 DRAFT-2 人工路径保持
可用回退位，validator 按 flag 分支校验，≥2 个 pilot stage（先 no-op/docs-only，
后小型产品 stage）通过后再讨论改默认值。

---

## E. 可写入 `00-intake.md` 的合成（ACCEPT-with-edits）

以下为修订 stage（建议名 `2026-07-auto-review-pipeline-v1`）intake 的骨架，
基于 note §4–§6 + 本评审的必改项：

**Scope（冻结）**
1. 新增 `docs/auto-review-pipeline.md`：单一 pipeline 契约，含威胁模型节（C1）、
   advisory-fail-open / formal-fail-closed 原则（D2）、词汇表（D9）。
2. 新增 `scripts/stage-seal.py`：allowlist commit（边界来自 status.json 任务
   字段）+ fingerprint（**import** `validate-stage.py` 的
   `compute_diff_fingerprint`，禁止复制实现）+ status 机械字段 + 调 validator。
3. 新增 orchestrator 脚本（无 LLM，确定性）：blocking checks → seal →
   embedded pre-review（含证据 commit，B3）→ review-1（Grok）→ fix loop →
   停在 review-2 待人工；RECEIPT 逐调用落盘；全局预算上限（C2）。
4. `AGENTS.md` / `stage-delivery.yaml` / `registry.yaml` /
   `validate-stage.py`：按 `dispatch_mode` flag 双轨化（D10）；Grok review-1
   仅 auto 模式默认 + cross-pool fallback（D1/C4）；bookkeeper 职能拆分表
   （B1）；rework 单账本 + `max_formal_1_rounds: 2`（D8）；auto 模式禁用
   dual-hat commit（B9）；高端模型措辞按 B8。
5. 解决 parallel-mode embedded review 双轨矛盾：subsume 或 flag 互斥（B4），
   从 optional 升为 must。

**Non-goals（照抄 note §8 并追加）**
- 不改 fingerprint 公式（D7）。
- 不改 review-2 契约与 merge 人工门。
- 不改 `schemas/review-verdict.schema.json` 的 role/verdict 枚举（D9）。
- 不触碰任何产品代码与进行中的 `2026-07-funding-annualized-history-v1`。

**Acceptance / pilot 门（D10）**
- validator 对两种 `dispatch_mode` 各有通过路径，unknown 组合 fail-closed。
- Pilot 1（docs-only no-op stage）全链路无人工跑通到
  `stage_accepted_waiting_user`；Grok verdict schema-valid。
- Pilot 2（小型真实 stage）后统计：Grok invalid-JSON 次数、escalation 是否
  产出 D8 形状的产物、RECEIPT 完整性。两个 pilot 通过前不改默认
  `dispatch_mode`。

**复杂度建议：HIGH**（改 AGENTS 硬门 + 新权限组件）。方向证据可由 note +
本评审充当，是否再跑 direction panel 由操作者按 HIGH 的 user-override 规则
决定。

---

```text
本地北京时间: 2026-07-10 19:07:35 CST
下一步模型: human（操作者）
下一步任务: 决定是否按 §E 开 2026-07-auto-review-pipeline-v1 修订 stage；
           本文件与被审 note 均勿混入 stage/2026-07-funding-annualized-history-v1 的交付提交
```

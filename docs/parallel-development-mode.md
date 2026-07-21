# 双端并行开发模式（parallel_development_with_embedded_cross_review）

状态：**ADOPTED-TRIAL**（2026-07-04；GPT review round 2 确认满足试运行
条件。在接下来 1-2 个双任务阶段试运行；试运行通过后由一个独立的小型
harness 变更把本模式指针写入 `AGENTS.md`，状态改 ADOPTED。试运行期间与
现行 `AGENTS.md` + `workflows/templates/stage-delivery.yaml` 冲突时，
以后者为准并触发本文档回退修订。）

起源：用户 2026-07-04 提议双终端并行开发以提速；GPT 补充任务内嵌交叉评审；
Fable5 补充与 Hard Gates 的兼容性修正（预审定性、预写 prompt 红线、本地轮次
记账规则）。三方结论已在对话中对齐，本文档是其正式化。

修订记录：
- DRAFT-1（2026-07-04 16:20）：初稿。
- DRAFT-2（2026-07-04）：按 GPT review round 1（REWORK，verdict 落档
  `reports/agent-runs/harness-parallel-mode-v1/gpt-review-round1.raw-output.md`）
  修订：R7 对齐 AGENTS.md 的 strong-reviewer disclosure override；bookkeeper
  与 Fable5 解绑；§5 证据索引扩展（task/implementer/prompt/dispatch/diff
  patch/正式 review 指纹全链路）；每轮预审强制保存 reviewer 所见 diff patch
  与 dispatch 记录；新增 R9（文件化 dispatch packet + 顶部回执块）。
- ADOPTED-TRIAL（2026-07-04）：GPT review round 2 确认 5 findings 全部吸收、
  兼任披露规则可接受（verdict 落档 `.../gpt-review-round2.raw-output.md`）；
  两条非阻塞建议一并吸收：R7 明示 direction synthesizer 属设计参与者范畴；
  R9 补充"PROMPT BODY 是任务正文、receipt 是审计元数据"的解读约定。
- v0.3-TRIAL-AMEND（2026-07-04 深夜）：首次试运行
  （`2026-07-phase2-borrow-sort-v1`）暴露两个流程缺口——dual-hat
  （bookkeeper 兼 implementer-A）实际退化为纯实现者；任务书收尾语
  「报告写完即停/等待嵌入预审」与规则层「实现终端机械触发预审」矛盾，
  双实现终端按字面停等，预审靠人工补跑。修订：controller 术语拆分
  （orchestrator=抽象编排语义 / bookkeeper=单一写者执行会话，见 §2）；
  bookkeeper 默认不由实现者兼任；R4 增落盘前 diff 对账；R9 next_dispatch
  升级为执行约束；新增 R10（实现任务 dispatch 收尾硬化）。finding 见 §8-5。
- v0.4（2026-07-06）：按 Claude REWORK 复审意见落地前两层强化（不做 runner）。
  R10 改为 machine-readable `r10_checklist`（落 status.json / RECEIPT，禁入
  immutable PROMPT BODY）；新增 `dispatch-ready` validator 门（parallel stage
  进实现前必过）；cross-review reviewer 由 registry 按 implementer provider
  派生，不按 backend/frontend 字面推断；embedded reviewer read-only 命令引用
  registry `embedded_read_only_review_command`；embedded checkpoint 失败分类
  收敛到 `agents/registry.yaml` `failure_classes.embedded_checkpoint`；统一
  落档命名为 `.raw-output.md` / `.dispatch.md` / `.fix-note.md`；明确禁止的是
  「无落档的聊天窗口中转」而非人按 dispatch 文件介入。落地作者 GPT/Codex，
  Claude 复审确认（正/反向 fixture + py_compile 独立复跑通过）。
- v0.5（2026-07-20）：dispatch/review 机制改革（提案
  `reports/agent-runs/_proposals/2026-07-20-harness-dispatch-review-reform.md`
  DRAFT-2；依据 real-borrow stage 的 6 个 incident、fast-fix 回退教训与
  Opus4.8 review）。单一 dispatch 权威 actor-neutral 化：任何模型会话不得
  调用/启动/转派另一模型会话，跨模型 dispatch 只有 human operator 一个执行者；
  Phase 2 重写——实现者收尾=自测+（opt-in 时）diff.patch+实现报告+停止，
  默认流程删除强制嵌入预审；嵌入预审改 opt-in
  （`parallel_mode.embedded_review.enabled` + 非空 reason）；R9/R10 的
  next_dispatch executor 只允许 `human_operator`/`none`，
  `manual_user_handoff_allowed` 字段废除；嵌入预审启用时 designer 预写
  round1/round2 两份参数化 prompt；§5 review-1 命名改为任务级
  `30-review-1-<task-id>.md`（单任务 stage 用无后缀）；新增 dispatch prompt
  固定前言 `[HARNESS-EXECUTOR-CONTRACT v1]`（R11）；verdict 权威性改为
  validator 从 review artifact 解析（R12）。新规则经
  `status.json.dispatch_protocol: "human-operator/v1"` 门控，无该字段的历史
  stage 语义与审计证据不变。

---

## 1. 目标与适用条件

**目标**：在不削弱既有证据纪律的前提下，把「实现」和「review-1」两个最耗
墙钟时间的环节并行化，并让 review-2 专注于整体一致性、接口契约、证据链与
回归风险，而非替 review-1 抓低级缺陷。

**适用条件**（全部满足才启用本模式；任一不满足则回退串行 stage-delivery）：

1. 阶段含 ≥2 个实现任务，且任务 scope 两两不相交（如 `backend/**` vs
   `frontend/**`）。
2. 任务间接口契约可在设计期冻结：任务书必须写死精确字符串、schema 字段、
   fixture 形状等一切跨任务消费物。任何"B 等 A 产出后才知道"的依赖存在，
   则该依赖项不得并行（整体回退或将该项后置）。
3. 每个实现任务有一个非本任务实现者的可用评审模型（交叉评审可成立）。

## 2. 角色

| 角色 | 承担者（默认配置） | 职责 | 禁止 |
|---|---|---|---|
| designer / breakdown author / prompt author | Fable5 (anthropic)，Fable5 额度耗尽后用 Opus4.8 | 设计记录、双任务书、**双评审 prompt 预写**、H_intake 内容 | 写产品代码 |
| bookkeeper / stage operator（单一写者执行会话；旧 stage 文档中称 controller） | **用户指定的独立本地执行会话**（Codex/GPT、Fable5/Opus4.8 会话或其他；**默认不由任一实现者兼任**） | 收证据、跑测试、**串行 commit**、算指纹、跑 validator、推进 status.json、调度正式 review-1 确认与 review-2、处理 R3/R10 升级 | 写产品代码；改写/摘要评审证据 |
| implementer-A | claude_glm | `backend/**` 等 A scope | commit、写 status.json、算最终指纹、越 scope、启动/转派其他模型会话 |
| implementer-B | kimi | `frontend/**` 等 B scope | 同上 |
| embedded reviewer（嵌入预审，opt-in） | 对侧模型的 **fresh read-only 会话**，由 human operator 按 bookkeeper 预写的 dispatch 文件启动 | 按预写 prompt 审对方任务的工作树 diff | 复用实现 transcript；审自己实现的任务；会话内再转派 |
| final reviewer (review-2) | 按 §4-R7 排除/override 规则选定 | 整体终审 | 会话内转派其他模型（发生即该次评审无效） |

**orchestrator 是抽象概念，不是角色**：指本文档 + `stage-delivery.yaml`
定义的流程/状态机语义本身，不映射到任何模型或会话。执行侧的流程推进者
只有 bookkeeper 一个。旧文档中的 "controller" 一词混合了编排语义与执行
会话，自 v0.3 起弃用：规则层面说 orchestrator（语义），执行层面说
bookkeeper（会话）。历史 stage artifacts 中的 controller 字样不回改。

**bookkeeper 与模型身份解绑**：bookkeeper 是"具备仓库读写与命令执行能力的
单一本地会话"这一属性，不绑定任何特定模型。Fable5 的默认角色是
designer/breakdown/prompt author；Fable5 额度耗尽后使用 Opus4.8 作为同一
Anthropic provider 的后备。同一会话兼任 designer 与 bookkeeper 是允许的
（记账是执行性工作，不产生代码作者身份），但必须在 status.json 中如实记录
兼任事实，供 review-2 披露评估。

**bookkeeper 不得默认由实现者兼任**（v0.3）：首次试运行证明，当同一会话
既是 implementer 又是 bookkeeper 时，流程推进（预审派发、状态机、跨端
协同）会让位于实现工作。实现者兼任仅在模型资源受限时作为例外允许，须在
status.json 披露并计入 review-2 评估；默认配置是独立 bookkeeper 会话。

**单一写者原则**：status.json、git 提交、指纹、状态机在任何时刻只有
bookkeeper 一个写者。两个实现终端全程不碰 git 与 status.json。

## 3. 流程

```text
Phase 0  设计（bookkeeper/designer）
  H_intake 提交：00-task.md（含冻结的接口契约）+ 10-design.md
  + 双实现任务书（含 R10 收尾段）+ status.json(designing)
  （嵌入预审 opt-in 启用时：另附 round1/round2 两份预写预审 prompt，见 §4-R1）

Phase 1  并行实现（两终端同时启动）
  implementer-A 开发 A-scope   ‖   implementer-B 开发 B-scope

Phase 2  实现者收尾（各终端独立完成，无任何跨模型调用）
  各自：跑自测命令 →（嵌入预审启用时）按任务书写死的命令生成
  embedded-review-<task>-round1.diff.patch → 写 20-implementation-*.md
  → 停止，等待 bookkeeper。实现终端不得启动或转派任何其他模型会话。

Phase 2b 嵌入交叉预审（opt-in；仅 parallel_mode.embedded_review.enabled=true
  时存在；human operator 执行）
  bookkeeper 准备 dispatch 文件 → human operator 逐字执行，启动 fresh
  对侧模型 read-only 会话，预审工作树 diff.patch
  预审返回问题 → 实现者只修自己 scope → 可再预审一轮
  （本地循环封顶 2 轮，见 §4-R4；round-2 prompt 仅在 round-1 BLOCKER 且
  scope-contained 时由 bookkeeper 启用）

Phase 3  串行落盘（bookkeeper）
  收两侧实现报告 +（opt-in 时）全部预审落档 → 复跑测试 → 串行提交
  H_A、H_B → 计算 task 级指纹 → validator(pre-review)

Phase 4  正式 review-1（每任务一次；human operator 执行 dispatch）
  按 registry 交叉评审规则选定的新鲜 read-only 会话，对 committed 指纹出
  正式 verdict（schema 合规 JSON，独立重算指纹）。verdict 以 validator
  从任务级 artifact（30-review-1-<task-id>.md）解析为准（R12）。
  返回 REWORK → 走正式 rework 流程（计入 rework_count）。

Phase 5  review-2 终审 + 终态
  bookkeeper 调度 final reviewer 对 stage 级指纹终审
  → validator(pre-accept) → stage_accepted_waiting_user → 用户验收
```

## 4. 红线（违反任一条，相关评审/交付无效）

**R1 预写评审 prompt。** 嵌入预审 opt-in 启用时，双评审 prompt 必须由
designer 在 H_intake 随任务书提交入库，内容含：被审任务的 scope/forbidden、
验收口径、必跑命令、落档路径。**轮次路径参数化（v0.5）**：designer 预写
round-1 与 round-2 两份 prompt 文件
（`embedded-review-<task>-round1.prompt.md` / `-round2.prompt.md`），各自
**写死**对应轮次的 diff.patch 路径；round-2 prompt 仅在 round-1 BLOCKER 且
scope-contained 时由 bookkeeper 启用。不存在「在-session 重定向 immutable
prompt」的合法操作。执行时**逐字使用**入库版本。没有入库预写 prompt 的
嵌入预审无效。
（理由：嵌入模式下派工记录曾由被审代码作者代写，必须把作者对评审输入的
裁量权压到零。）

**R2 fresh read-only 评审会话。** 预审与正式 review-1 都必须在全新会话中
进行，不得复用任何实现/bookkeeper（旧称 controller）transcript；评审依据只能是 raw diff 与
仓库内落档文件，不接受任何会话内转述。

**R3 本地 fix 限界。** 预审发现的问题，实现者只能在自己任务的 scope 内修。
凡涉及接口契约、schema、跨任务消费字段、共享文件的改动，一律不得本地 fix，
必须升级 bookkeeper 决策（必要时回到设计层修任务书）。

**R4 本地循环封顶 2 轮且全落档（嵌入预审 opt-in 启用时适用）。** 每个任务的
「预审→fix」循环最多 2 轮；
每轮必须落档四件套（§5 命名）：① dispatch/command 执行记录（谁、何时、
用什么命令启动的评审会话）；② **reviewer 实际所见的工作树 diff patch**
（`git diff` 原文存为 `.diff.patch`——预审对象是未提交态，不存 patch 就
无法事后证明评审看到了什么；此文件是证据快照，**不是**指纹，不得用于任何
门禁绑定，避免发明第二套指纹协议）；③ 评审 raw output；④ fix 说明。
2 轮仍未清零 → 停止并升级 bookkeeper（可能定性为任务书缺陷或正式 REWORK）。
本地循环**不计入** stage 的 `rework_count`（该配额保留给正式门后的 REWORK），
但轮次与落档必须在 status.json 中如实记录，不存在账外迭代。
**落盘前对账**（v0.3）：bookkeeper 提交 H_x 前必须重新生成该任务工作树
diff，与最后一轮 `.diff.patch` 比对；差异必须能被 fix-note 完全解释，
否则不得提交（防止实现者在预审后、落盘前引入未受审改动）。round 1 的
dispatch 执行记录可由预审 prompt 文件的 RECEIPT 块回填承担；round ≥2
或发生 escalation 时用独立 `embedded-review-<task>-round<N>.dispatch.md`。

**R5 嵌入预审是 checkpoint，不是评审门；且自 v0.5 起为 opt-in。** 仅当
`status.json.parallel_mode.embedded_review = {"enabled": true, "reason": "<非空>"}`
时启用嵌入预审；未启用时不产生任何 `embedded-review-*` artifact，
validator 也不检查它们；账外存在 embedded-review artifact 即报错。启用时
预审对象仍是未提交工作树，依据 Hard Gates 属于 "in-progress checkpoint
before a review gate"，其结论**不能**作为 review-1 verdict 落档，也永不
替代正式 review-1。正式 review-1 必须在串行提交后对 committed 指纹出
schema 合规 verdict（Phase 4）。预审的价值是把问题在进正式门之前修掉，
不是替代正式门。

**R6 单一写者。** 见 §2。实现终端提交 git、修改 status.json、宣称指纹，
任何一项发生即整个任务定性 REWORK。

**R7 review-2 选择遵循 AGENTS.md 现行规则（含 override），本模式不加严
也不放松。** 具体为：

- **实现者与 fix 作者 hard-ban**，无任何 override。
- **设计参与者（designer/breakdown/prompt author/direction synthesizer）
  默认避让 review-2**（prefer isolation）；仅当无关决策模型 runner-level
  不可用时，
  Codex/GPT 或 Claude 可经 **strong-reviewer disclosure override** 担任
  ——披露证据必须齐全：`reviewer_prior_involvement` 如实填写、路由探测
  记录（probe hygiene 规则适用）、override 理由写入 status.json 与
  review-2 dispatch prompt。
- bookkeeper 兼任事实（若与 designer 同会话）计入披露评估。

**R8 既有 Hard Gates 全部继续适用。** 单一指纹协议、committed 态评审、
raw 证据优先、validator 前置、契约修订须附 raw 公开样本等，本模式一概
不豁免。

**R9 文件化 dispatch packet + 顶部回执块。** 所有启动文案（实现任务书、
预审 prompt、正式评审 prompt、review-2 prompt）必须是 stage 目录内的
dispatch 文件，不依赖聊天窗口复制的临时文本。每个 dispatch 文件结构：

```text
<!-- ===== DISPATCH RECEIPT（执行者/记账者填写） =====
status:        pending | running | done | escalated
target_model:  <provider/model>
adapter_cmd:   <实际执行命令，如 claude-glm ... / kimi ... / 会话启动方式；
               status=done 时不得为 n/a/pending/空>
executor:      human_operator（跨模型 dispatch 的唯一合法执行者）
started_at:    <ISO8601>
completed_at:  <ISO8601>
session_id:    <provider-native ID；运行时不暴露时写 unavailable:<原因> 或
               n/a:<原因>；不得为空或裸 unavailable/n/a>
outputs:       <本次执行产出的 artifact 文件列表>
next_dispatch: <下一步该执行的 dispatch 文件名，终点写 none>
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（immutable，设计期定稿后不得修改） ===== -->
（prompt 正文，顶部为 R11 固定前言）
```

回执块与 prompt body 用上述 marker 硬分隔；body 在 H_intake 后不可变
（需要改 = 回到设计层出新版本文件），回执块由执行者/记账者在运行时填写。
执行者只需按 `next_dispatch` 链找到文件并执行，全链路可审计、可断点续跑。

**解读约定**：发给模型执行时，任务正文只有 PROMPT BODY；RECEIPT 是审计
元数据，模型不得把回执字段（status/next_dispatch 等）解读为任务要求。
向模型转发 dispatch 文件时可以只发 body，或发全文并声明本约定。

**next_dispatch 是路由元数据，执行者只有 human operator**（v0.5）：designer
必须为每条 next_dispatch 标注执行者，取值只允许 `human_operator`（跨模型
调用）或 `none`（终点）。`executor: self` 语义废除：任何模型会话——包括
当前实现终端——都不得执行指向另一模型会话的 dispatch；bookkeeper 准备
dispatch 文件，human operator 按文件逐字执行并在 RECEIPT 块回填执行记录。
PROMPT BODY 与本文档规则冲突时以本文档为准，冲突本身按设计缺陷升级
bookkeeper，不得按字面执行了事。

**R10 实现任务 dispatch 收尾硬化（v0.5 语义）。** 每份实现任务 prompt 的
PROMPT BODY 末尾必须包含由 stage designer **写死真实路径**（实现者不得
自行拼路径）的可执行收尾段，至少含：

1. 自测命令（测试/自检脚本的精确命令）；
2. （仅嵌入预审 opt-in 启用时）生成 reviewer 所见 diff.patch 的精确
   `git diff` 命令（含输出路径）；
3. 全部落档路径清单；
4. 停止指令：自测 PASS → 报告并停止，等待 bookkeeper 串行落盘；自测失败
   → 仅 scope 内 fix 后重跑自测；涉及契约/schema/共享面 → R3 升级，
   禁止本地 fix。

收尾段不再包含「调用对侧预审模型」的 adapter 命令：实现者的收尾义务里
没有任何跨模型调用。嵌入预审启用时，预审由 bookkeeper 准备 dispatch
文件、human operator 执行；对侧模型不可用或命令失败时，由 bookkeeper 写
`embedded-review-<task>-round<N>.dispatch.md` 记录 unavailable/error
并置 escalated——**禁止仅口头报告等待用户**。

收尾段缺任一项的任务书不得进入 H_intake。parallel stage 进入实现前还必须
通过 `scripts/validate-stage.py <stage-id> --phase dispatch-ready`。
「不 commit、不碰 status.json」的单一写者纪律与收尾义务互不冲突：
前者限制 git 与状态机，后者是实现者交付前的最后动作。

**R10 checklist（v0.4）**：R10 的 machine-readable checklist 是校验/审计
元数据，不是发给模型的任务正文。它必须落在 `status.json` 的
`tasks[].r10_checklist` 或 `r10_checklists.<task-id>`，也可在 dispatch
文件 RECEIPT 区冗余记录；不得塞进 immutable PROMPT BODY。validator 以
`status.json` 为准。最小字段：

```json
{
  "task_prompt_path": "task-A-claude-glm.prompt.md",
  "embedded_review_prompt_path": "embedded-review-A-round1.prompt.md  （仅 opt-in 启用时必填）",
  "self_tests_command": "pytest ...",
  "diff_patch_command": "git diff -- ... > reports/.../embedded-review-A-round1.diff.patch  （仅 opt-in 启用时必填）",
  "diff_patch_path": "embedded-review-A-round1.diff.patch  （仅 opt-in 启用时必填）",
  "cross_review_adapter": "kimi  （仅 opt-in 启用时必填）",
  "cross_review_command_ref": "agents/registry.yaml#adapters.kimi.embedded_read_only_review_command  （仅 opt-in 启用时必填）",
  "cross_review_raw_output_path": "embedded-review-A-round1.raw-output.md  （仅 opt-in 启用时必填）",
  "cross_review_dispatch_path": "embedded-review-A-round1.dispatch.md  （仅 opt-in 启用时必填）",
  "next_dispatch_executor": "human_operator",
  "max_rounds": 2,
  "pass_branch": "report PASS and stop for bookkeeper",
  "blocker_branch": "scope-contained fix then rerun self-tests; contract/schema/shared changes escalate",
  "unavailable_branch": {
    "failure_classes": ["model_unavailable", "adapter_missing", "command_error", "permission_error", "timeout"],
    "escalation_artifact": "embedded-review-A-round1.dispatch.md"
  }
}
```

`next_dispatch_executor` 取值只允许 `"human_operator"`（跨模型调用）或
`"none"`（终点）；`manual_user_handoff_allowed` 字段自 v0.5 废除（执行
权威由 executor 取值表达），在 `dispatch_protocol: "human-operator/v1"`
的 stage 中出现即报错。嵌入预审未启用时，上表标注「仅 opt-in 启用时必填」
的字段不要求、不检查。

The cross-review reviewer is derived from the implementer provider using
`agents/registry.yaml` review-1 selection rules (`claude_glm -> kimi`,
`kimi -> claude_glm`, otherwise first available cross-review pool member with a
different provider). It is not inferred from "backend" or "frontend" wording.

The prohibition is against any model-to-model dispatch, not only unlogged
chat-window relay. Dispatch execution is human-operated for every provider:
any model session may prepare the dispatch file, but none may invoke another
model terminal or adapter command. The human operator runs the prepared prompt
or adapter command in the selected target terminal, and that action must be
driven by the dispatch file and recorded in the required `.dispatch.md`
evidence.

**R11 dispatch prompt 固定前言（v0.5）。** 每份发给模型的 dispatch 文件
（实现任务书、预审 prompt、正式 review-1/review-2 prompt）的 PROMPT BODY
顶部必须以下列前言开头（中英文按 prompt 语言二选一；标记行供 validator
grep）：

```text
[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务的唯一执行者。
1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令（包括但不限于
   claude-glm -p、kimi -p、codex exec、grok）。需要其他模型时，输出
   ESCALATED 及原因并停止。
2. 禁止编造未实际执行的命令结果或未实际读取的文件内容；你写下的每一条
   执行记录都必须对应你本会话内真实发生的动作。
3. 你的评审/实现依据只能是本 prompt 列出的 raw artifact 路径与你自己
   实际读取的文件。
```

validator 在 dispatch-ready 只 grep `[HARNESS-EXECUTOR-CONTRACT v1]` 这一
标记行存在，不比对全文：prompt immutable，全文比对防不住有意改写；前言是
给模型的指令，证据责任由 human-only dispatch + receipt 承担。

**R12 verdict 以 validator 解析为准（v0.5）。** review 门的 verdict 与
schema 合规性由 `scripts/validate-stage.py` 从 review artifact 文件中
容错解析（选取最后一个 top-level JSON object：候选 dict 的解码跨度若被
其他可解码 dict 或 list container 的跨度严格包含即为嵌套，不得胜出——findings 数组里的
嵌套 finding 不会覆盖外层 verdict，top-level array `[verdict]` 也不得提升其内层 dict；兼容 ```json
围栏与 footer 文本，且最终 schema-invalid 的 top-level object 仍 fail
closed，不回退到更早的对象）并按 `schemas/review-verdict.schema.json` 校验；
`status.json` 的 verdict 字段只做交叉一致性检查，
`review_*.json_schema_valid` 字段不再是门禁断言。文件缺失或 verdict 不可
解析 = fail closed。每次跨模型 dispatch（含正式 review）必须在
status.json 记录对应 dispatch 文件路径（`review_1.dispatch_path` /
`tasks[].review_1.dispatch_path` / `review_2.dispatch_path`）；receipt 的
session_id 与 review artifact footer 自报的 Session ID 必须一致（两者均
为 unavailable 类时视为一致）。

## 5. 落档命名约定（stage 目录内）

```text
task-<task-id>-<model>.prompt.md      # 实现任务书（H_intake；R9 packet 结构 + R11 前言）
embedded-review-<task-id>-round1.prompt.md   # 预审 prompt round 1（opt-in 启用时 H_intake 预写）
embedded-review-<task-id>-round2.prompt.md   # 预审 prompt round 2（同上，写死 round-2 diff.patch 路径）
20-implementation-{backend,frontend}.md
embedded-review-<task-id>-round<N>.dispatch.md      # 每轮执行记录（opt-in 启用时）
embedded-review-<task-id>-round<N>.diff.patch       # reviewer 实际所见工作树 diff（R4-②，opt-in 启用时）
embedded-review-<task-id>-round<N>.raw-output.md
embedded-review-<task-id>-round<N>.fix-note.md      # 每轮 fix 说明（改了什么、为何）
30-review-1-<task-id>.md              # 正式 review-1，每任务一份（如 30-review-1-backend.md / 30-review-1-frontend.md）
50-review-2.md
```

**review-1 命名约定（v0.5）**：并行 stage 的正式 review-1 以任务级文件
`30-review-1-<task-id>.md` 为准；无后缀的 `30-review-1.md` 在并行 stage 中
**不再被要求也不再产生**。单任务（非并行）stage 继续使用 `30-review-1.md`。
validator 的 required-files 检查按 stage 类型动态展开，与本文档严格一致。
stage 也可在 `tasks[].review_1.artifact_path`（或 `review_1.artifact_path` /
`review_2.artifact_path`）显式声明 review artifact 路径覆盖默认命名。

status.json 增加记录块（示意；仅嵌入预审 opt-in 启用时必填；每任务必填字段见下）：

```json
"embedded_reviews": {
  "A": {
    "task_id": "A",
    "scope": ["backend/**"],
    "implementer": {"provider": "claude_glm", "model": "glm-5.2[1m]"},
    "reviewer": {"provider": "kimi", "model": "kimi-2.7", "fresh_session": true},
    "prompt_path": "embedded-review-A-round1.prompt.md",
    "r10_checklist_ref": "tasks.A.r10_checklist",
    "rounds": 1,
    "round_artifacts": [
      {"round": 1,
       "dispatch_path": "embedded-review-A-round1.dispatch.md",
       "worktree_diff_path": "embedded-review-A-round1.diff.patch",
       "raw_output_path": "embedded-review-A-round1.raw-output.md",
       "fix_report_path": null}
    ],
    "escalations": [],
    "formal_review": {
      "output": "30-review-1-backend.md",
      "base_sha": "<H_intake sha>",
      "head_sha": "<H_A sha>",
      "diff_fingerprint": "<head:sha256>",
      "verdict": "ACCEPT"
    }
  },
  "B": { "...": "同构（scope=[\"frontend/**\"]，reviewer=fresh claude_glm，2 轮则 round_artifacts 两项且含 fix_report_path）" }
}
```

正式 review-1 的 base/head/fingerprint/verdict 同时仍按现行惯例记录在
`tasks.<id>.review_1`；`embedded_reviews.<id>.formal_review` 是指向性冗余，
让 review-2 在一个块内重建"预审 N 轮 → 提交 → 正式确认"的完整链路。

## 6. 与现行 workflow 的关系

- 本模式是 `stage-delivery.yaml` 的**执行编排变体**，不新增状态机状态：
  Phase 1-2 发生在 `implementing`，Phase 3 结束进 `review_1`，其后与现行
  流程完全一致（`review_1 → review_2 → stage_accepted_waiting_user`）。
- 不新增指纹协议、不新增 verdict schema。预审落档是证据增强，不是新门。
- review-2 的 `reviewer_prior_involvement` 披露与回退路径
  （`decision_models_exhausted` 等）不变。

## 7. 升级路径（非本次采纳范围）

**方案乙：worktree 分支制。** 每任务独立 git worktree 分支开发并提交，
预审直接绑分支 committed 指纹（消除 R5 的 checkpoint/正式门两段式），
bookkeeper 串行落主干后做机械 rebind（diff 哈希逐位一致，参照
bstock-alias-v1 evidence-backfill 的 rebind 先例）。待方案甲跑通 ≥2 个
阶段且两段式确认开销成为主要痛点时再评估。

## 8. 采纳条件与试运行

1. 本文档经 GPT/Codex review（对象：与 AGENTS.md/Hard Gates 的一致性、
   护栏完备性、可执行性）。verdict 与修订意见落档
   `reports/agent-runs/harness-parallel-mode-v1/`（轻量记录，无代码）。
   round 1（2026-07-04）：REWORK，5 findings（P1×1 + P2×4），已在 DRAFT-2
   全部吸收。round 2（2026-07-04 16:40）：确认满足 ADOPTED-TRIAL 条件，
   两条非阻塞建议已吸收。
2. ✅ 状态已改 ADOPTED-TRIAL，在接下来 1-2 个双任务阶段试运行。
3. 试运行通过后：一个独立小变更把指针写入 `AGENTS.md`（引用本文档），
   状态改 ADOPTED。
4. 试运行中任何红线被突破 → 回退串行模式，本文档回到 DRAFT 修订。
5. **试运行 finding #1**（2026-07-04，stage `2026-07-phase2-borrow-sort-v1`）：
   dual-hat（bookkeeper 兼 implementer-A）+ 任务书收尾语「报告写完即停/
   等待嵌入预审 round 1」+ 预审 receipt `adapter_cmd` 写"用户粘贴"，三处
   叠加导致双实现终端完成后停等，嵌入预审靠人工补跑（两侧 round 1 均
   PASS，diff.patch/raw output 均落档，红线未破，不构成回退条件）。定性：
   规则层（Phase 2 原文已写"机械执行"）与 dispatch 文案层矛盾，属 stage
   packet 设计缺陷（Fable5 署名）+ 角色设计缺口。处置：v0.3-TRIAL-AMEND
   （角色拆分默认化 + R10 + R9 执行约束 + R4 对账）；当前 stage 余下环节
   维持 GLM 临时兼任 bookkeeper 完成，新规则自下一个 stage 的 dispatch
   packet 生效。试运行继续计数。

---

本地北京时间: 2026-07-20 20:08:38 CST（v0.5）
起草: Fable5 (anthropic/claude-fable-5)；经 GPT review ×2 后进入 ADOPTED-TRIAL；
v0.3 修订依据首次试运行 finding #1（用户观察 + Fable5 复核）；
v0.4 由 GPT/Codex 按 Claude REWORK 复审意见落地前两层强化，Claude 复审确认；
v0.5 按 dispatch/review 机制改革提案 DRAFT-2 落地（real-borrow stage 6 个
incident + fast-fix 回退教训 + Opus4.8 review），Kimi 实施。
下一步: 声明 `dispatch_protocol: "human-operator/v1"` 的新 stage 按 v0.5 出
dispatch packet（R11 前言 + human_operator receipt + 任务级 review-1 命名）。

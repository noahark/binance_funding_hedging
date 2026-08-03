# Harness 任务交接件与证据落档设计（已实现，历史提案稿）

状态：**已落地。修订四经 DeepSeek 独立计划复评 `评审结论: ACCEPT`，已实现、已通过
review-1（DeepSeek）与 review-2（Fable5）双 ACCEPT，并随 stage
`2026-08-03-harness-task-handoff-evidence-v1` 归档
（tag `archive/2026-08-03-harness-task-handoff-evidence-v1`，`0a0b952`；交付
`14e4592`）。**

**本文不再是权威，仅作设计历史留档。** 现行权威是 `AGENTS.md` §7（回执与新阶段交接
路径要求）与 `agents/roles.md` 的 Task Handoff Evidence Contract（路径、文件结构、
创建权限、Bookkeeper 同文件核验、SHA-256 边界、勘误与归档、`SOURCE_REPORT_MISSING`
降级的唯一详细权威）。两者与本文有出入时以两者为准。已知的后续澄清项 O-A（源区块
SHA-256 边界的机械化表述）记录在 `PROJECT_STATE.md`。

日期：2026-08-03（状态行更新于 2026-08-03 stage 收口）
提出背景：现行评审模型为只读终端，输出原始 `TASK_RESULT` 后由 Human
操作者转交给 Bookkeeper；下一模型不能稳定地从仓库读取该次终端的结论。

## 1. 目标与边界

### 目标

1. 每个获批准新 stage 中已 dispatch 的实现、修复、review-1 和 review-2 任务，结束时
   都有一份位于 stage 内、可由下一模型直接读取的交接件；Bookkeeper 核验任务不另建
   文件，其唯一落档是被核验任务交接件中的 `Bookkeeper Verification` 追加区块。
2. 交接件保存任务作者的完整报告，并包含一份面向 Human 的现有 `TASK_RESULT v2`
   简报。控制台只展示从该简报提炼的同格式回执；两处都必须写清下一位模型要读取的
   文档路径和具体执行动作。交接件引用可复核的测试输出、问题记录、修复要求和固定
   Git SHA，不以摘要代替原始证据。
3. Human 继续只负责启动已准备的下一个终端，不必在模型之间复制评审文字。
4. 下一份 dispatch 只列出与自身有关的前序交接件，保持按需读取，不增加一个新的
   全局启动必读文件。

### 非目标

- 不启动、调用、转交或编排另一个模型终端。
- 不把 `PROJECT_STATE.md` 变成任务通讯板，也不新增全局黑板。
- 不修改 `status.json` 的现有字段形状或状态枚举。
- 不改变控制台最终 `TASK_RESULT v2` 的行、字段或闭合格式；交接件路径使用既有的
  `产物` 列表表达。
- 不尝试自动捕获完整终端对话逐字稿；“完整报告”是任务作者写入交接件的完整任务
  报告，控制台回执只是 Human 可读简报。若未来需要终端级逐字归档，须单独设计
  捕获、完整性和敏感信息处理。
- 不改变正式评审必须独立检查固定 `base_sha..delivery_sha` 的要求。
- 第一阶段不新增 stage 总览大文件；若后续有证据表明模型频繁需要拼接多个交接件，
  再单独评估由 Bookkeeper 独写、只链接原件的 stage 阅读索引。

## 2. 观察到的缺口

现行规则要求评审者保持只读，将其原始 `TASK_RESULT` 交给 Human，再由 Human
转交 Bookkeeper。完整证据只在关闭 stage 时归档。这保护了模型调度与状态写入的
边界，但使“下一模型应读什么”依赖人工复制和临时说明。

现有 `TASK_RESULT v2` 已有任务结论、产物、检查和下一步字段；它缺少一个必然存在、
可在仓库定位的完整交接件。`status.json` 是机器状态，不适合承载长篇叙事；
`PROJECT_STATE.md` 是跨 stage 未关闭风险，也不应承载任务间通讯。

## 3. 决策：每任务一个分区不可改的交接件

对每个任务 ID，固定使用以下路径：

```text
reports/agent-runs/<stage-id>/evidence/<task-id>.handoff.md
```

该文件是该任务的**交接索引和作者完整报告**。作者完成后，作者区块不得重写；
需要勘误时一律追加显著的勘误区块。Bookkeeper 可在文件末尾追加自己的核验区块，
但不得编辑作者区块。这一例外将在实施时写入现行角色契约，避免误把核验追加当成
作者勘误。文件不宣告验收、合并、部署或实盘授权。

交接件的最低结构如下；字段细则只在未来实施时写入一个现行权威文件，不能在多个
契约文件中重复定义。

```markdown
# Task Handoff: <task-id>

## Source Report (author-only; immutable after task end)
- task_id / role / target model
- stage_id / created_at
- base_sha / delivery_sha（不适用时明确写 none）

完整任务背景、实际修改范围或只读评审范围、结论、未完成事项、命令与结果、
仓库内证据路径，以及下一任务必须读取的材料和不能假设的事实。大体积测试原件
只引用路径，不复制进本文件。

## Required Reading for the Next Task (author-only; immutable after task end)
- 读取路径及顺序：<仓库相对路径，或 none>
- 执行：<立即动作>
- 关卡：<下一验证或 Human 决策>
- 不能假设的事实：<具体约束>

## Human Brief / Console Receipt Source (author-only; immutable after task end)
采用既有 `TASK_RESULT v2` 格式和字段的 Human 可读简报，也是控制台回执的唯一内容
来源。任务模型必须先完成本交接件，再以这一节的内容生成控制台最终回执；不得另行
创作与本节不一致的控制台叙事。没有终端输出自动捕获时，Bookkeeper 不能机械核验两份
文本逐字一致；仓库内交接件仍是正式原件，控制台输出不具权威。“同格式”只指既有字段
与闭合标记约定，不承诺逐字一致。

除既有字段外，本节的 `下一步任务` 必须以如下可执行句式写明：

```text
读取：<一个或多个仓库相对路径，或 none>；执行：<立即动作>；关卡：<下一验证或 Human 决策>
```

不得只写“由 Bookkeeper 跟进”“见上文”或其他无法定位的语句。若不存在下一份文件，
必须明确写 `读取：none` 及其原因和 Human 的待决动作。`Source Report` 中另设
`Required Reading for the Next Task` 小节，列出相同的路径、读取顺序、执行动作与不能
假设的事实；Bookkeeper 必须核对它与 `下一步任务` 的路径和动作不冲突。

评审任务的 ACCEPT / REWORK、问题记录与修复要求使用现有回执约定；详细发现可放在
本文件的 Source Report 区块，`问题记录`／`修复要求` 指向本文件路径。

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)
由 Bookkeeper 在核验后追加：源区块 SHA-256、核验时间、核对的 status revision、
通过或拒收依据、可复现命令与后续状态。该区块不是第二份交接文件。

## Errata (append-only)
任何更正均追加，说明日期、作者、改动原因与不改变的事实；不得改写 Source Report 或
Human Brief。
```

勘误在 Bookkeeper 核验前追加时，由 Bookkeeper 连同原始区块和勘误一并判断；核验后
出现的勘误不得静默改变下一任务的依据。Bookkeeper 必须追加一次勘误确认并重新核验，
或将任务退回 `reported`；涉及交付效果、契约、验收、检查状态或评审结论的“勘误”仍
按现有规则属于修复而非编辑。

实现者的交接件须在其任务交付范围内创建，控制台回执的 `产物` 使用既有字段列出该
路径。评审者的交接件只含其审查结论、证据路径和正式回执，不复制或改写被审代码、
已有评审报告或 `status.json`。交接件中的模型身份仅是自述警示；Bookkeeper 仍以
dispatch、`status.json` 与 Human 启动记录判断身份。控制台回执的下一步路径与动作
来自 Human Brief，不是新的状态写入或调度授权。

## 4. 权限与交接流程

实施时必须在 `agents/roles.md` 的 Reviewer 段显式修改“fresh read-only session”规则，
并在 Reviewer 与 Bookkeeper 段改写“Human 转交 raw TASK_RESULT”的现行描述。新的
评审者权限固定为：**对交付代码、既有证据、`status.json` 和
`PROJECT_STATE.md` 全部只读；只允许在审查完成后新建 dispatch 中逐字指定的一个
交接件。** 该路径在任务开始前必须不存在；存在即失败。评审者不得覆盖、编辑或追加
既有文件，交接件只含自身结论；不得提交 Git、写 `status.json` 或选择下一模型。

```mermaid
flowchart LR
  A["任务模型"] -->|"新建唯一 handoff 文件"| B["stage evidence"]
  B -->|"Human 启动"| C["Bookkeeper"]
  C -->|"追加核验区块并提交证据控制提交"| D["下一份 dispatch"]
  D -->|"Inputs 指向 handoff"| E["下一模型"]
```

Bookkeeper 仍是唯一的状态推进者：

1. 准备 dispatch 时，Bookkeeper 对预定交接路径运行 `test ! -e <path>`，并将通过结果、
   命令和确定路径写入该 dispatch 的既有 Allowed Files 段，作为 Human 启动前的预启动
   记录；返回后复查该路径存在且为本任务新建，并检查 task_id、role、stage_id、声明的
   SHA 与 `status.json`／`git rev-parse` 输出匹配。
2. 检查 Human Brief 中的既有 `TASK_RESULT v2` 结构、评审闭环字段、引用证据路径及
   命令均可读；检查 `下一步任务` 含明确的读取路径、立即动作和下一关卡，并与
   Source Report 的 `Required Reading for the Next Task` 不冲突。由于本设计不含终端
   输出自动捕获，Bookkeeper 不做不可取得的终端文本与文件逐字 diff；仓库内的正式原件
   是交接件本身。
3. 对 `BOOKKEEPER_APPEND_ONLY` 标记之前的字节计算 SHA-256，追加同一文件中的
   Bookkeeper Verification 区块。Bookkeeper 核验动作的唯一落档就是这个追加区块，
   不另建独立交接件或并行核验报告，也不得改写作者区块。
4. 缺失或不合规时，任务保持 `reported`，在同一交接件追加拒收依据与 blocker；不得
   仅因终端文本声称完成而写 `verified`。
5. 合规时，先把交接件（含核验区块）作为证据控制提交的一部分固定下来，再准备下一
   份 dispatch。`delivery_sha` 始终保持被评审的交付 SHA，不被该控制提交替换。
6. 下一份 dispatch 在既有 `Inputs` 段列出真正需要的交接件路径；不要求下一模型
   全量读取历史交接件或整个 stage 目录。

`blocked`、`failed`、review `REWORK` 和 Bookkeeper 拒收也必须产生交接件，说明
blocker 和依据。若任务因权限、磁盘或路径冲突而无法创建交接件，任务本身必须返回
`blocked` 并不可推进；Bookkeeper 只能在该路径创建显著的 `SOURCE_REPORT_MISSING`
记录，说明缺失事实和 Human 转交的控制台简报，不能伪造作者完整报告。这是唯一的
故障降级，不是常规交接方式。

正常路径中，Human 的人工动作从“复制评审内容”缩小为“启动 Bookkeeper／下一任务
终端”：交接件是 Bookkeeper 唯一正式核验输入，控制台回执仅供 Human 阅读。仅当
`SOURCE_REPORT_MISSING` 故障降级发生时，Human 转交控制台简报以记录源报告缺失事实；
它不能替代作者完整报告，也不能推进任务。本设计没有、也不应声称没有 Human 启动终端
这一授权关卡。

## 5. 不引入黑板

本设计不增加 `BLACKBOARD.md`，也不在第一阶段新增汇总全部过程的 stage 大文件。
每任务交接件已提供不可变的来源；`status.json` 提供当前机器状态；
`PROJECT_STATE.md` 提供跨 stage 风险。新增可自由写入的黑板或全量副本会重复这三者，
带来并发覆盖、来源不明、上下文膨胀和双重权威。

若未来确实出现模型频繁需要拼接多个交接件才能开始工作这一已验证需求，可单独评估
由 Bookkeeper 独写的 stage 阅读索引；它只写目标、当前关卡、必要交接件链接和阅读
顺序，不能复制结论或状态，也不成为默认启动必读项。在出现该证据前不预先增加该结构。

## 6. 现行契约的预期改动范围

| 文件 | 最小改动职责 |
|---|---|
| `AGENTS.md` | 保持 Task Result Protocol 的字段与控制台格式不变；规定获批准新 stage 的回执在既有 `产物` 列出交接件，且 `下一步任务` 使用“读取／执行／关卡”句式；指向 roles.md 的详细规则。 |
| `agents/roles.md` | 定义交接件路径、分区、唯一创建权限、Human Brief 到控制台回执的单向来源、下一步路径核验、Bookkeeper 同文件追加/提交职责和评审者的窄写入例外；**改写** Reviewer/Bookkeeper 段中 Human 转交 raw TASK_RESULT 的正常路径为“交接件是唯一正式核验输入”，仅保留 `SOURCE_REPORT_MISSING` 故障降级；写明归档后不得原地勘误。不新增 `status.json` 字段或状态。 |
| 新 stage 的 dispatch | 在 Allowed Files 中列出任务自己的唯一交接件；在 Inputs 中列出该任务需要的前序交接件。 |

已有归档 stage 保持不动。该制度仅适用于批准后新建的 stage，避免伪造历史完整性。

实施时对 `agents/roles.md` 的具体改写应采用下列含义，而非仅增加旁注：

- Reviewer：完成审查后，将其交接件作为仓库内正式结果；控制台 `TASK_RESULT` 仅供
  Human 阅读，Human 在正常路径中不向 Bookkeeper 复制回执文字。
- Bookkeeper：以该交接件为唯一正式核验输入；只有 `SOURCE_REPORT_MISSING` 时，才
  接收 Human 转交的控制台简报作为“源报告缺失”的辅助事实。
- Archive：stage 归档后不得在归档内或正常工作树原地追加勘误。发现问题必须创建后续
  任务；新证据引用归档 SHA，而不重写已归档交接件。

## 7. 验收检查

1. 每个新 dispatch 都能推导出唯一交接件路径，并把它列在 Allowed Files；控制台回执
   使用不变的 `产物` 字段列出该路径。
2. 实现、修复、两层评审、`blocked`、`failed` 和 Bookkeeper 拒收均有交接件；正常
   交接件含完整作者报告、Human Brief 和合规的正式回执。
3. 评审终端除新建自己的、预先不存在的指定交接件外，对工作树保持只读；不提交、
   不覆盖、不追加，且不改动受审交付。
4. Bookkeeper 对缺失、非新建、错 task ID、错误 SHA、缺失证据或格式不合规的交接件
   拒绝推进；故障降级只能产生 `SOURCE_REPORT_MISSING` 记录。
5. Bookkeeper 计算作者区块 SHA-256 并只在同一文件追加核验区块；作者区块从不重写。
   核验后出现的勘误必须由 Bookkeeper 追加确认并重新核验，或退回 `reported`。
6. Human Brief 是控制台回执的唯一来源；其 `下一步任务` 与 Source Report 的必读路径、
   立即动作和关卡清楚、可定位且相互不冲突。
7. 下一份 dispatch 只引用所需交接件；不要求读取全部历史交接件或整个 stage 目录。
8. 证据控制提交不改变 `delivery_sha`，正式评审仍锚定原固定区间。
9. 关闭 stage 后，交接件与其他证据一同在 archive/tag 中可获得；`PROJECT_STATE.md`
   没有被用作任务报告或通讯日志。
10. 已归档 stage 的交接件不再原地勘误；后续发现以新任务和归档 SHA 留痕。

## 8. DeepSeek 独立计划评审重点

请以现行 `AGENTS.md`、`agents/roles.md` 为准，而非本提案的描述，重点判断：

1. “评审者仅能在路径不存在时新建自己的指定交接件”是否足以维持只读隔离和独立性；
   是否还存在覆盖、并发或权限扩大漏洞。
2. Bookkeeper 的同文件追加与作者区块 SHA-256 是否足以保护原始作者报告；它与现行
   原始产物勘误规则是否需要更精确的契约措辞。
3. 将交接件定义为仓库内正式原件、将控制台 `TASK_RESULT v2` 保持为 Human 简报，是否
   比要求不可自动取得的终端文本逐字 diff 更符合“无人工复制”的目标；是否有遗漏的
   失真或伪造风险。
4. 不改变 `status.json` schema 是否会导致下游无法可靠发现交接件；固定路径加 dispatch
   Inputs 是否足够。
5. 对并行但可分离的任务，交接件命名、控制提交和下一 dispatch 是否存在竞争或错误引用。
6. `blocked`、`failed`、REWORK、拒收和交接件创建失败的处理，是否会出现无法落档却被
   错误推进的路径。
7. 本设计是否无意削弱“Human 启动模型”“Bookkeeper 单一状态写者”“固定
   `base_sha..delivery_sha` 审查区间”三个现有不变式。
8. 将“Human 转交 raw TASK_RESULT”在正常路径中改为“交接件是唯一正式核验输入”，
   并只保留 `SOURCE_REPORT_MISSING` 降级，是否完整消除了现行契约冲突。
9. 预启动 dispatch 中的 `test ! -e <path>` 记录、返回后的新建复查、同文件 Bookkeeper
   Verification 和归档后不得原地勘误，是否覆盖了交接件生命周期的关键时点。
10. 将 Human Brief 作为控制台回执的唯一来源，并强制“读取／执行／关卡”与
    Source Report 的必读材料一致，是否能在不改变现有回执字段的前提下提供足够清晰的
    下一步指引；是否有遗漏的冲突或伪造风险。
11. 是否有必要另行设计终端级原始输出捕获；若需要，必须如何处理密钥、隐私数据、
   内容哈希与失败降级。

## 9. 风险与决策门

这是 Harness 安全与工作流契约改动，按现行 `AGENTS.md` 属 `HIGH_RISK`。在实施前必须：

1. 由独立、跨 provider 的模型完成计划评审并返回明确 ACCEPT；
2. Human 审阅中文的影响和风险说明，授权或否决实施范围；
3. 再为实施者准备明确的 dispatch、文件边界与验收检查。

“ACCEPT（附条件）”、缺少合规 Task Result 或未解决的开放点均不是明确 ACCEPT；
修订后应重新评审。上述门槛完成前，本文件只是一份提案，不给任何模型新增写权限、
提交权限或调度权限。

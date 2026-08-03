# Task Handoff: harness-handoff-contract-repair-glm-r2

## Source Report (author-only; immutable after task end)
- task_id: harness-handoff-contract-repair-glm-r2
- role: Implementer（bounded repair）
- target model: claude_glm（provider zhipu_glm）
- stage_id: 2026-08-03-harness-task-handoff-evidence-v1
- created_at: 2026-08-03 17:14:03 CST
- base_sha: 3fe5ff8626b04e99b9965ccd503ab258f9adc3dc
- delivery_sha: pending — 实现/修复作者于交付提交前创建交接件，适用 Delivery SHA 小节的 pending 形式；权威 SHA 由 Bookkeeper 以 `git rev-parse` 解析后写入 `status.json` 与同文件核验区块

### 任务背景

R1 交付 `3fe5ff8` 修复了 BK-001/BK-002，但首个真实交接件暴露两处 in-range 契约缺口
（拒收记录见
`reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/evidence/harness-handoff-contract-repair-glm-r1.handoff.md`
的 Bookkeeper Verification Record）：

- BK-003：作者必须在把交接件纳入交付提交前创建文件，因此无法预先知道 `delivery_sha`；
  R1 交接件实际使用 `pending`，但现行契约模板只允许 SHA 或不适用的 `none`，且 Bookkeeper
  规则又要求声明 SHA 与 `status.json`／`git rev-parse` 匹配。未定义 `pending` 的合法性、
  适用角色与 Bookkeeper 对实际 SHA 的记录方式。
- BK-004：`Required Reading for the Next Task` 与 Human Brief 的 `下一步任务` 使用
  “本交接件”“返工 commit 的 `agents/roles.md`”“`21-bookkeeper-verification-rework-r1.md`”
  等非完整仓库相对路径，不足以作为下一 dispatch 的确定输入。

本任务为第二次最小返工，仅闭合这两点，不重新设计 R4 契约、不扩范围（dispatch 24 号）。
本交接件自身即验收样本（acceptance #3）。

### 实际修改范围（仅 `agents/roles.md`，加本交接件与 status.json 状态）

1. BK-003 —— `agents/roles.md` 的 Task Handoff Evidence Contract：
   - Structure 模板的 `delivery_sha` bullet 改为指向 Delivery SHA 小节
     （pending／none／已知 git rev-parse 值）。
   - 新增 `### Delivery SHA` 小节：`pending` 仅用于实现/修复作者在包含该交接件的唯一
     交付提交前创建的交接件；`none` 为无交付；已知时为直接 `git rev-parse` 值；评审交接件
     引用已固定的被审 delivery SHA，永不写 `pending`；交付提交后 Bookkeeper 核验 `base_sha`、
     以 `git rev-parse` 解析实际 delivery SHA、写入 `status.json` 与同文件核验区块，且绝不
     改写作者源 payload 去填充 `pending`。
   - Bookkeeper Same-File Verification 的 SHA 句：核验 `base_sha`；`pending` 的 `delivery_sha`
     按 Delivery SHA 在交付提交后解析。
2. BK-004 —— `agents/roles.md` 的 Task Handoff Evidence Contract：
   - Structure 后注增加：`Required Reading for the Next Task` 与 Human Brief `下一步任务` 的
     每条读取项必须是完整仓库相对路径并按书写顺序；自引用用完整确定交接件路径，禁用
     “本交接件”、纯文件名、“commit 的文件”等简写。
   - Bookkeeper Same-File Verification 的 `下一步任务` 检查由 “explicit read paths” 改为
     “concrete repository-relative read paths”。

未改 `TASK_RESULT v2` 字段或闭合标记、status schema/状态词、Bookkeeper 单一状态写者、
评审隔离、Human 启动关卡、固定被审 delivery SHA、归档终局；未加黑板/stage 汇总/终端逐字稿
捕获；保留 BK-001/BK-002 修复。

### 结论与未完成事项

BK-003/BK-004 已按最小修复闭合；本交接件自身按 Delivery SHA 用 `pending`、其
Required Reading 与 下一步任务 全部为完整仓库相对路径（自引用为完整路径），满足 acceptance
#3。未触碰 R1 已通过项（BK-001/BK-002）。未发现残留阻塞。

### 命令与结果

- `git diff --check`：exit 0（无空白错误）。
- `python3 -m json.tool reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/status.json`：合法。
- 完整返工 diff 已逐条核对 BK-003/BK-004 与 acceptance #4（保留项）。

### 仓库内证据路径

- 拒收与修复依据：`reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/evidence/harness-handoff-contract-repair-glm-r1.handoff.md`（Bookkeeper Verification Record, BK-003/BK-004）
- 修复 dispatch：`reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/24-claude-glm-handoff-contract-repair-r2.dispatch.md`
- R1 修复 dispatch：`reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/22-claude-glm-handoff-contract-repair-r1.dispatch.md`
- R4 设计：`docs/planning/harness-task-handoff-evidence-design-2026-08-03.md`

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/status.json`
  2. `reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/evidence/harness-handoff-contract-repair-glm-r2.handoff.md`
  3. `agents/roles.md`（Task Handoff Evidence Contract 的 Delivery SHA 小节、Structure 后注、Bookkeeper Same-File Verification）
  4. `reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/evidence/harness-handoff-contract-repair-glm-r1.handoff.md`（核对 BK-003/BK-004 是否闭合）
- 执行：Bookkeeper 独立核验返工交付区间 `3fe5ff8..<delivery_sha>` 是否满足 24 号 dispatch 的五项验收检查，封存 `delivery_sha`
- 关卡：核验通过后按 `AGENTS.md` §8 HIGH_RISK 准备跨 provider 的 review-1 dispatch
- 不能假设的事实：`delivery_sha` 以 Bookkeeper 的 `git rev-parse` 为准；该字段在交付提交前写为 pending，由 Bookkeeper 解析后写入，不构成权威值。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

下列既有 `TASK_RESULT v2` 字段与闭合标记的简报是控制台回执的唯一内容来源。本节
`下一步任务` 写为：
读取：<一个或多个仓库相对路径，或 none>；执行：<立即动作>；关卡：<下一验证或 Human 决策>

```text
[TASK_RESULT v2]
任务 ID: harness-handoff-contract-repair-glm-r2
执行结果: completed（完成）
结果摘要: 第二次最小返工闭合 BK-003/BK-004：roles.md 契约新增 Delivery SHA 小节，允许实现/修复作者交付提交前 handoff 的 delivery_sha 写 pending、none 为无交付、已知为 git rev-parse、评审引用已固定 SHA，Bookkeeper 解析实际 SHA 写 status.json 与同文件核验区块且不改作者 payload；要求 Required Reading 与 下一步任务 每条为完整仓库相对路径、自引用用完整路径、禁简写。本交接件自身为合规样本。未改字段/状态/隔离/SHA。
产物: [agents/roles.md, reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/evidence/harness-handoff-contract-repair-glm-r2.handoff.md, reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/status.json（返工交付 commit；delivery_sha 由 Bookkeeper 记录）]
检查结果: [
1. pass — BK-003：契约新增 ### Delivery SHA 小节，明确 pending 仅用于实现/修复作者在包含该交接件的唯一交付提交前创建的 handoff、none 为无交付、已知为直接 git rev-parse、评审交接件引用已固定被审 SHA；Bookkeeper 核验 base_sha、交付提交后解析实际 delivery SHA 写入 status.json 与同文件核验区块、不改作者源 payload；Structure 模板 bullet 与 Bookkeeper 段已对齐（acceptance #1）。
2. pass — BK-004：Structure 后注要求 Required Reading 与 下一步任务 每条读取项为完整仓库相对路径并按书写顺序、自引用用完整确定交接件路径、禁用“本交接件”/纯文件名/“commit 的文件”等简写；Bookkeeper 段下一步任务检查改为 concrete repository-relative（acceptance #2）。
3. pass — 本 R2 交接件自身合规：delivery_sha 用 pending（acceptance #1 形式）；其 Source Report 的 Required Reading 与 Human Brief 的 下一步任务 全部为完整仓库相对路径，自引用为 reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/evidence/harness-handoff-contract-repair-glm-r2.handoff.md（acceptance #3）。
4. pass — 保留项：未改 TASK_RESULT v2 字段/闭合标记、status schema/状态词、Bookkeeper 单一写者、评审隔离、Human 启动关卡、固定被审 delivery SHA、归档终局；无黑板/stage 汇总/逐字稿捕获；BK-001/BK-002 修复保留（acceptance #4）。
5. pass — 自检：git diff --check exit 0；通读完整返工 diff 核对 BK-003/BK-004；python3 -m json.tool 校验 status.json 合法（acceptance #5）。
]
阻塞项: [none]
本地北京时间: 2026-08-03 17:14:03 CST
下一步模型: codex（本阶段 Bookkeeper；Human 启动其终端核验，正常路径不复制回执文字）
下一步任务: 读取：reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/status.json、reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/evidence/harness-handoff-contract-repair-glm-r2.handoff.md、agents/roles.md、reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/evidence/harness-handoff-contract-repair-glm-r1.handoff.md；执行：Bookkeeper 核验交付区间 3fe5ff8..<delivery_sha> 满足 24 号 dispatch 五项验收，对 reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/evidence/harness-handoff-contract-repair-glm-r2.handoff.md 追加同文件核验区块并封存 delivery_sha；关卡：通过后按 §8 HIGH_RISK 准备跨 provider review-1。
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)
由 Bookkeeper 核验后追加：源区块 SHA-256、核验时间、核对的 status revision、通过或拒收依据、可复现命令与后续状态。

## Errata (append-only)
任何更正均追加，说明日期、作者、改动原因与不改变的事实；不得改写 Source Report 或 Human Brief。

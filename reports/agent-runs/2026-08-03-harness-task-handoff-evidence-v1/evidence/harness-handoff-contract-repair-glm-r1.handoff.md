# Task Handoff: harness-handoff-contract-repair-glm-r1

## Source Report (author-only; immutable after task end)
- task_id: harness-handoff-contract-repair-glm-r1
- role: Implementer（bounded repair）
- target model: claude_glm（provider zhipu_glm）
- stage_id: 2026-08-03-harness-task-handoff-evidence-v1
- created_at: 2026-08-03 16:59:19 CST
- base_sha: e7c0acb81831060369889143072787efe753e3f7
- delivery_sha: pending — 本交接件包含于返工交付提交；权威 SHA 由 Bookkeeper 以 `git rev-parse` 记录于 `status.json`

### 任务背景

首次交付 `e7c0acb` 建立了 Task Handoff Evidence Contract 单一详细权威，但被 Bookkeeper
拒收（见 `21-bookkeeper-verification-rework-r1.md`），两项 in-range 发现：

- BK-001：受契约约束的新 task dispatch 未被强制路由到详细契约——Bookkeeper 未被要求在
  每个 dispatch 的 `Inputs` 列出该契约，`Allowed Files` 也未要求写出唯一交接路径与
  create-only preflight；且 Implementer 段缺 scoped pointer。下一模型可遵守现有启动顺序
  却只看到 `AGENTS.md` 的简短提醒，无法获得交接件结构、创建权限、同文件核验与异常规则。
- BK-002：已存在但格式损坏（缺 `BOOKKEEPER_APPEND_ONLY` 标记或源 payload 不合格）的交接件
  没有定义同文件拒收落档路径，无法满足常规 SHA 前提，又与“禁止另建并行核验记录”冲突。

本任务为最小返工，不重新设计 R4 契约、不扩范围（dispatch 22 号）。

### 实际修改范围（仅 `agents/roles.md`，加本交接件与 status.json 状态）

1. BK-001a —— Bookkeeper Same-File Verification 的 dispatch 预检句：要求每个受约束 task
   dispatch 在 `Allowed Files` 记录路径/命令/create-only + preflight 结果，并在 `Inputs`
   列出本 Task Handoff Evidence Contract，使契约被路由到每个受约束任务。
2. BK-001b —— Implementer Required Reading 增加 scoped pointer 指向本契约段
   （Reviewer 的 Isolation/Verdict、Bookkeeper 的 Write Authority/Required Behavior 段在
   首交付已有点）。
3. BK-002 —— Bookkeeper Same-File Verification 的 SHA/追加句：仅当 `BOOKKEEPER_APPEND_ONLY`
   标记存在才算常规源 SHA-256；文件存在但标记缺失或 payload 损坏时，Bookkeeper 不改任何
   作者字节，仅在 EOF 追加显著拒收 `Bookkeeper Verification` 区块，记
   `source_sha256: unavailable`、损坏前提、可复现检查与 `reported`/blocker 状态；完全缺失
   的文件仍走 `SOURCE_REPORT_MISSING`。

未改 `TASK_RESULT v2` 字段或闭合标记、status schema/状态词、Bookkeeper 单一状态写者、
评审隔离、Human 启动关卡、固定 delivery SHA、归档终局；未加黑板/stage 汇总/终端逐字稿捕获。

### 结论与未完成事项

两项发现已按最小修复闭合；未触碰首交付已通过项（字段集、闭合标记、单一权威、转交规则改写、
JSON/空白自检）。未发现残留阻塞。

### 命令与结果

- `git diff --check`：exit 0（无空白错误）。
- `python3 -m json.tool reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/status.json`：合法。
- 完整返工 diff 已逐条核对 BK-001/BK-002 与 acceptance #3（保留项）。

### 仓库内证据路径

- 拒收与修复依据：`reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/21-bookkeeper-verification-rework-r1.md`
- 修复 dispatch：`reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/22-claude-glm-handoff-contract-repair-r1.dispatch.md`
- R4 设计：`docs/planning/harness-task-handoff-evidence-design-2026-08-03.md`
- 首交付实现回执：`reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/evidence/20-claude-glm-implementation.raw.md`

### Required Reading for the Next Task

- 读取路径及顺序：`reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/status.json` → 本交接件 → 返工交付 commit 的 `agents/roles.md`（Bookkeeper Same-File Verification 与 Implementer Required Reading 两处）→ `21-bookkeeper-verification-rework-r1.md`（核对两发现是否闭合）
- 执行：Bookkeeper 独立核验返工交付区间 `e7c0acb..<delivery_sha>` 是否满足 22 号 dispatch 的四项验收检查，封存 `delivery_sha`
- 关卡：核验通过后按 `AGENTS.md` §8 HIGH_RISK 准备跨 provider 的 review-1 dispatch（本阶段实现并首次启用该契约）
- 不能假设的事实：`delivery_sha` 以 Bookkeeper 的 `git rev-parse` 为准；本交接件 `delivery_sha` 字段为 pending，不构成权威值。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

下列既有 `TASK_RESULT v2` 字段与闭合标记的简报是控制台回执的唯一内容来源。本节
`下一步任务` 写为：
读取：<一个或多个仓库相对路径，或 none>；执行：<立即动作>；关卡：<下一验证或 Human 决策>

```text
[TASK_RESULT v2]
任务 ID: harness-handoff-contract-repair-glm-r1
执行结果: completed（完成）
结果摘要: 最小返工闭合 BK-001/BK-002：roles.md 契约段 Bookkeeper 预检规则要求每个受约束 dispatch 在 Inputs 列契约、Allowed Files 写路径/create-only/preflight；Implementer 段加 scoped pointer；新增 malformed-existing 交接件同文件拒收路径（不改作者字节、EOF 追加 source_sha256: unavailable，仅 marker 存在算常规 SHA，缺失文件仍走 SOURCE_REPORT_MISSING）。新建本任务 handoff。未改字段/状态/隔离/SHA。
产物: [agents/roles.md, reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/evidence/harness-handoff-contract-repair-glm-r1.handoff.md, reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/status.json（返工交付 commit；delivery_sha 由 Bookkeeper 记录）]
检查结果: [
1. pass — BK-001a：Bookkeeper Same-File Verification 预检句已要求每个受约束 task dispatch 在 Inputs 列出本契约、Allowed Files 记录路径/命令/create-only + preflight 结果（acceptance #1 前半）。
2. pass — BK-001b：Implementer Required Reading 加 scoped pointer；Reviewer（Isolation/Verdict）、Bookkeeper（Write Authority/Required Behavior）段首交付已有点，三角色皆可达契约且未复制字段细节（acceptance #1 后半）。
3. pass — BK-002：Bookkeeper 同文件核验定义 malformed-existing 分支——不改作者字节、EOF 追加拒收区块 source_sha256: unavailable + 损坏前提 + 可复现检查 + reported/blocker；仅 marker 存在算常规源 SHA-256；缺失文件仍走 SOURCE_REPORT_MISSING（acceptance #2）。
4. pass — 保留项：未改 TASK_RESULT v2 字段/闭合标记、status schema/状态词、Bookkeeper 单一写者、评审隔离、Human 启动关卡、固定 delivery SHA、归档终局；无黑板/stage 汇总/逐字稿捕获（acceptance #3）。
5. pass — 自检：git diff --check exit 0；通读完整返工 diff 核对 BK-001/BK-002；python3 -m json.tool 校验 status.json 合法（acceptance #4）。
]
阻塞项: [none]
本地北京时间: 2026-08-03 16:59:19 CST
下一步模型: codex（本阶段 Bookkeeper；Human 启动其终端核验，正常路径不复制回执文字）
下一步任务: 读取：reports/agent-runs/2026-08-03-harness-task-handoff-evidence-v1/status.json、本交接件、返工 commit 的 agents/roles.md、21-bookkeeper-verification-rework-r1.md；执行：Bookkeeper 核验交付区间 e7c0acb..<delivery_sha> 满足 22 号 dispatch 四项验收并封存 delivery_sha；关卡：通过后按 §8 HIGH_RISK 准备跨 provider review-1。
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)
由 Bookkeeper 核验后追加：源区块 SHA-256、核验时间、核对的 status revision、通过或拒收依据、可复现命令与后续状态。

## Errata (append-only)
任何更正均追加，说明日期、作者、改动原因与不改变的事实；不得改写 Source Report 或 Human Brief。

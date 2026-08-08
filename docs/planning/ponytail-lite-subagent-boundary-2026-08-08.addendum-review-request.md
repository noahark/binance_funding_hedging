# Ponytail-lite 附加项：允许会话内子代理，保留下一工作流模型的 Human 启动边界

- **日期**：2026-08-08
- **状态**：Human 已拍板并授权直接实施（见下方决定记录）
- **关联计划**：`docs/planning/ponytail-lite-harness-overthinking-2026-08-08.review-request-v2.md`（已获四份 v2 `ACCEPT`）
- **风险分类**：HIGH_RISK（修改 Harness Safety Kernel）
- **当前权限**：仅记录 Human 新需求和候选合同；不授权修改 Harness、启动其他工作流模型、实施、合并或实盘操作

---

## 1. Human 新需求

删除当前“禁止模型启动或指派任何其他模型会话”的绝对禁令，因为它会阻止当前模型使用产品内建的 agent 子代理完成已授权任务。

原规则的真实目的应保留：当前模型不能自行启动、指派、接力或冒充**下一工作流模型**，不能替 Human 启动后续 Implementer、Reviewer、Bookkeeper 或其他独立终端。

## 2. 必须区分的两类执行上下文

### 会话内子代理

由当前根任务通过产品内建 delegation/agent 工具启动的子执行上下文，用于当前已授权任务内的有界分析或实现工作。它不是新的工作流 actor，不取得独立权限，也不能推进 Harness 状态。

### 工作流模型会话

由 dispatch packet 定义、承担 Planner / Implementer / Reviewer / Bookkeeper 等正式职责、能够返回正式任务结果并参与状态推进的独立模型终端。该会话仍只能由 Human 从准备好的 packet 启动。

## 3. 候选 Safety Kernel 口径

建议用以下含义替换 `AGENTS.md` §3 当前第 2 条，而不是简单删除保护：

1. 当前模型可以使用会话内、工具托管的子代理处理当前任务的有界子任务；
2. 子代理继承父任务的角色、Human 授权、dispatch 文件范围、只读/写权限、资金与外部副作用闸门；它不获得任何额外权限；
3. 父模型必须为子代理的选择、指令、改动、证据和最终结果负责，并在交付前核验；
4. 子代理之间不得发生重叠写入；文件范围不足时仍须停止并报告；
5. 父模型及其全部子代理在作者身份、provider 隔离和正式评审独立性上视为同一交付团队；子代理不能评审父模型或兄弟子代理共同完成的交付，也不能提供额外的独立 `ACCEPT`；
6. Reviewer 可以使用子代理做当前评审内的只读检查，但正式 verdict 仍只属于该 Reviewer 会话，子代理不构成第二名独立 Reviewer；
7. 子代理不得充当下一工作流 actor，不得创建或消费下一 dispatch，不得选择下一模型、推进 `status.json`、冒充正式 handoff，或绕过 Human 启动下一终端；
8. 任何模型仍不得自行启动、调用、转发、指派或冒充外部/独立的下一工作流模型会话；Human 继续从 Bookkeeper 准备的 packet 启动下一终端；
9. 子代理不能绕过资金、订单、实盘闸门、凭据、破坏性数据动作、风险限额、部署和外部副作用的 Human 授权要求。

以上是行为含义，实施时应压缩成最小合同文字，不在多个文件复制九条清单。

## 4. 文件范围与单一权威

详细边界只写在 `AGENTS.md` §3 Safety Kernel。仓库另有两处同义绝对禁令，必须在同一 Harness 修改中同步为指针，否则活动合同自相矛盾：

| 文件 | 当前问题 | 候选改动 |
|---|---|---|
| `AGENTS.md` | §3.2 绝对禁止任何其他模型会话 | 改成“允许会话内子代理，但禁止自行启动下一工作流模型”的详细权威 |
| `agents/roles.md` | 文件头与 Shared Rules 重复绝对禁令 | 改成一行指向 `AGENTS.md` §3 的提醒；不复制子代理清单 |

`AGENTS.md` §7 的“当前模型不能启动下一模型”、Implementer Stop Point 的“不能启动 Reviewer”、Bookkeeper 的“不能启动下一终端”已经准确限定下一工作流 actor，应保留原意，只在实施时检查是否需要术语一致性勘误。

与已通过复审的 Ponytail-lite v2 合并实施时，候选总文件范围由三文件变为四文件：

1. `AGENTS.md`；
2. `agents/roles.md`；
3. `agents/developer-discipline.md`；
4. `agents/skills/senior-developer.md`。

新增的第 4 个范围责任仅是消除 `roles.md` 与新 Safety Kernel 的冲突，不扩展 Ponytail-lite 产品目标。

## 5. 非目标

- 不允许当前模型自行启动下一 Implementer、Reviewer、Bookkeeper 或其他工作流终端；
- 不允许子代理扩大 dispatch 文件范围、任务目标或 Human 授权；
- 不把子代理当成跨 provider 独立评审；
- 不允许实现作者用子代理完成自己的正式 review-1/review-2；
- 不允许 Reviewer 子代理写工作树、状态或正式 verdict；
- 不允许通过子代理实施资金、订单、部署或其他未获授权的外部副作用；
- 不规定必须使用子代理，也不规定并发数量、模型名称或具体工具实现；
- 不改变 Human 启动下一工作流终端、Bookkeeper 准备 packet 的既有流程。

## 6. 验收案例

| 场景 | 预期结果 |
|---|---|
| Implementer 用内建子代理搜索调用点，父模型完成修改与核验 | 允许 |
| Implementer 将两个互不重叠、均在 dispatch 文件范围内的实现子任务交给子代理 | 允许；父模型对合并结果负责 |
| 子代理准备修改 dispatch 未批准的文件 | 停止并报告，不能借父任务扩大范围 |
| 两个子代理准备同时修改同一文件 | 不允许重叠写入；父模型须重新划分或顺序执行 |
| Implementer 让子代理对共同完成的交付给正式 `ACCEPT` | 不成立；仍是自审 |
| Reviewer 用子代理只读追踪调用链 | 允许；只有父 Reviewer 返回正式 verdict |
| Reviewer 子代理修改代码或 `status.json` | 不允许 |
| Bookkeeper 用子代理核对证据 | 允许只做当前 Bookkeeper 任务内核验；不能让子代理启动下一终端 |
| 当前模型通过子代理启动下一 Reviewer 或向其转发正式 handoff | 不允许；Human 必须启动下一工作流终端 |
| 当前模型用不同 provider 的子代理声称满足跨 provider review | 不成立；全部子代理按父任务同一交付团队处理 |
| 子代理准备真实下单、划转、改闸门或部署但无本次 Human 授权 | 不允许 |
| 子代理违反范围或修改冲突，父模型称“是子代理做的” | 不构成免责；父模型对结果负责 |

## 7. 请评审模型重点回答

请只读评审，不修改文件，并回答：

1. “会话内子代理”与“下一工作流模型会话”的定义是否足够可执行，能否被模型绕过？
2. 父模型与子代理视为同一交付团队，是否充分保护作者隔离和 provider 隔离？
3. Reviewer 使用只读子代理是否会产生任何正式 verdict 或证据归属歧义？
4. 从三文件扩大到四文件是否为消除现有重复禁令所必需？
5. 哪条候选规则会意外禁止正常子代理协作，或意外允许模型启动下一工作流 actor？
6. 是否存在更小且同样安全的合同文字或验收案例？

建议返回：

```text
附加计划评审结论: ACCEPT | REWORK
阻塞问题: <none 或具体、可核验的问题>
越权反例: <none 或可执行的绕过场景>
最小修改建议: <维持 AGENTS.md + roles.md，或说明不同范围>
建议验收案例: <none 或必须新增的关键案例>
```

`ACCEPT` 只表示本附加项可以与 Ponytail-lite v2 一起进入 Human 的 stage 决策，不授权实施、合并、部署、启动下一工作流模型或实盘操作。

## 8. Human 决定记录（2026-08-08）

Human 明确决定：本附加项不再单独进行跨 provider 计划评审，直接并入 Ponytail-lite v2 实施；允许当前会话使用 Sol/Luna xhigh 子代理协助当前任务。该决定不取消交付后的正式 review-1/review-2，不授权子代理充当下一工作流 actor，也不扩大资金、部署或外部副作用权限。

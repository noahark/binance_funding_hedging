# Opus 5 只读评审请求：Harness 不再管理子代理

## 评审性质

- 类型：Harness 工作流合同变更的独立、只读 post-implementation review-1。
- 目标模型：Opus 5（Anthropic provider）。
- 作者侧：Codex / OpenAI。
- 仓库：`/Users/ark/Desktop/ai code/funding_hedging`
- 固定受审范围：
  - `base_sha`: `a21a3403151114067389f4b5bd3f7baf93436205`
  - `delivery_sha`: `45a2cf919fd3d069d364e51d3b48776a0937f7fa`
  - diff：`a21a340..45a2cf9`
- 修改前恢复点：tag
  `snapshot/harness-before-cli-managed-subagents-20260808`，应解引用到
  `a21a3403151114067389f4b5bd3f7baf93436205`。

只检查上述固定提交区间。不要以移动的 `HEAD`、未提交工作区或本请求文件自身作为
受审交付。保持只读，不修改代码、合同、状态或文档。

## Human 已拍板的需求

活动 Harness 不保留任何对子代理的描述或限制。子代理如何启动、编排、嵌套、授权和
结束，完全交给各模型 CLI 自身架构管理。

这里删除的是 Harness 对 CLI 内部子代理的治理，不是取消正式工作流边界。当前模型仍
不得启动、转交、指派或冒充下一独立工作流模型会话；下一正式终端仍由 Human 从准备好
的任务包启动。

本评审检查实现是否正确落实这项决定及是否造成合同自相矛盾，不重新评审 Human 是否
应该选择“由 CLI 管理子代理”。仅仅偏好更严格的子代理治理，不构成 `REWORK`。

## 本次交付

受审文件只有：

1. `AGENTS.md`
   - 删除 Safety Kernel 中整段子代理使用、继承、递归、写入冲突、作者集合和评审隔离
     规则。
   - 将下一正式工作流会话的禁令恢复为纯模型级规则。
   - Safety Kernel 后续条目重新编号。
2. `agents/roles.md`
   - 删除角色开头及 Shared Rules 中对子代理的描述。
   - 保留一行模型级提醒：Human 启动下一正式工作流会话。
3. `docs/planning/DECISIONS.md`
   - 新增 `DEC-2026-08-08-002`，记录 Human 决定、保留边界和恢复点。
   - 该文件是决策历史，不是活动运行权威。

交付提交没有修改产品代码、运行配置、资金路径、部署状态、`PROJECT_STATE.md`、
`ACTIVE.json` 或任何 stage 状态。

## 明确保留的边界

请确认以下边界没有被本次删除误伤：

- 资金、订单、实盘闸门、凭据、破坏性数据动作、风险限额、部署和外部副作用仍须 Human
  明确授权。
- Implementer 仍只能修改 dispatch 批准的文件，不能覆盖其他终端的工作。
- 实现或修复作者仍不能评审自己的交付。
- 正式评审仍按模型 vendor 隔离，不按 CLI 包装器隔离。
- 正式评审仍绑定 `status.json` 中固定的 `base_sha..delivery_sha`。
- 缺少明确、合规 `ACCEPT` 的评审仍不通过。
- 当前模型仍不能接管下一独立正式工作流会话。

这些是正式角色、资金和交付约束，不应被误判为 Harness 对 CLI 内部子代理的描述。

## 核验命令

```bash
git diff --check a21a340..45a2cf9
git diff --name-status a21a340..45a2cf9
git diff a21a340..45a2cf9 -- \
  AGENTS.md agents/roles.md docs/planning/DECISIONS.md
git rev-parse 'snapshot/harness-before-cli-managed-subagents-20260808^{}'
rg -n -i 'sub-?agents?|子代理' AGENTS.md agents
```

最后一条应无输出。历史规划、评审和决策记录可以保留相关词汇；它们不是活动 Harness
运行权威，不要求做全仓历史清洗。

## 需要回答的问题

1. `AGENTS.md` 与 `agents/` 中是否已经没有任何对子代理的描述或限制？
2. 是否还存在语义上专门约束 CLI 内部子代理、但没有使用 `subagent/子代理` 字样的活动
   规则？如有，必须给出精确路径、原文和为什么它只针对子代理而不是当前角色本身。
3. “CLI 内部子代理不归 Harness 管”与“当前模型不能接管下一正式工作流会话”的边界是否
   清楚、可执行，是否存在直接矛盾？
4. 上节列出的资金、文件范围、作者隔离、正式评审和固定 SHA 安全规则是否完整保留？
5. Safety Kernel 重新编号后，活动 Harness 内是否存在失效的条目编号引用？历史 review
   文档中的旧编号不阻塞本交付。
6. `DEC-2026-08-08-002` 是否准确记录 Human 决定、当前有效边界与可恢复快照？
7. 交付是否是实现需求的最小充分修改，有没有重复权威或不必要的新结构？
8. 是否存在由本次三文件 diff 直接引入、具有当前证据和实际影响的阻塞问题？

## 评审纪律

- 按当前 `AGENTS.md` §1 Scenario Admission 执行，不以无当前证据的刁钻假设阻塞。
- 不把 Human 已确认的试行目标本身写成 finding。
- `REWORK` 只能基于 `a21a340..45a2cf9` 内的具体问题，给出路径、证据、实际影响和最小
  可执行修法。
- 每条 finding 按 `AGENTS.md` §8 标为 `in-range`、
  `pre-existing-independent` 或 `pre-existing-release-critical`；范围外观察不得把 verdict
  改为 `REWORK`。
- 如果需求已准确落实且没有受证据支持的阻塞问题，返回明确 `ACCEPT`。

## 期望输出

先用不超过 300 个字符的中文给出实际效果和结论，再按以下字段收口：

```text
评审结论: ACCEPT（接受） | REWORK（返工）
问题记录: none | <逐条 finding，含范围分类、路径、证据和影响>
修复要求: none | <最小可执行修改>
固定范围核验: a21a340..45a2cf9
快照核验: <tag 解引用结果>
活动 Harness 子代理关键词核验: <无输出 | 具体命中>
保留边界核验: <结论>
剩余风险: <none | 非阻塞风险及触发条件>
```

正式回执继续遵守仓库当前 `[TASK_RESULT v2]` 与最终关闭标记要求。

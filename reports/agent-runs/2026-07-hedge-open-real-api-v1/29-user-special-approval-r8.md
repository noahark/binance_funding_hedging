# 用户特批 —— 第 8 次变更（Harness validator 修复），免模型评审

> **本文件记录一次偏离常规流程的授权。请连同 §3 的代价一起读。**

## 1. 用户指令（逐字）

> 第二半你直接修，然后走我直接审核通过特批，接着你总结项目进展以及下一个准备开始上线测试的阶段，然后提交推送 git。

## 2. 授权内容

- **第 8 次代码变更**，`max_rework` 7 → 8。
- **范围**：仅 `74-review-2-r2.md` 唯一 P1 的第二半 —— 让 `scripts/validate-stage.py` 的
  finding-6 (a) 检查覆盖**全部** dispatch 回执，而不只是 review 类。
  第一半（补封存 packet 72 回执）属簿记，不消耗额度。
- **验收方式**：**用户直接审核通过特批，不经任何模型交叉复核。**
- **实现者**：Claude Opus 5（本 stage 现任 bookkeeper 兼任）。

## 3. 这次特批的代价（必须如实记录，不得淡化）

1. **本次改动没有任何模型交叉复核。** 不是 ACCEPT，不是豁免后的评审——是**完全跳过评审**。
   `74-review-2-r2.md` 的 `required_fixes` 要求"实现并测试"该修复，本次实现了并加了测试，
   但**未经第三方验证**。
2. **Claude Opus 5 由此成为本 stage 的 fix author。** 按 `AGENTS.md`
   「审查者不得是被审代码的实现者或修复作者 —— 硬禁、无披露豁免」，Anthropic 此后
   **不能再担任本 stage 的任何评审**。而 Anthropic 本就因 Claude Sonnet 5 撰写前端 rework
   而被终审排除，故这条限制在终审侧本已成立；新增的是 **Review-1 侧也一并失效**。
3. **可用评审池进一步收缩**：`zhipu_glm`（后端作者）、`anthropic`（前端 rework + 现在的
   validator 作者）均被硬禁；`kimi` / `grok` 无额度。若后续还需要模型评审，
   仅剩 `codex`，且它已是设计者 + 三轮 Review-2 作者 + 前任 bookkeeper。
4. **bookkeeper 的中立性受损**：同一模型现在同时是簿记方、六轮 Review-1 作者、
   以及一段 Harness 代码的作者。本文件即为该状态的公开披露。

## 4. 实际改动

| 文件 | 改动 |
| --- | --- |
| `scripts/validate-stage.py` | 新增 `_collect_all_dispatch_refs()`：遍历整个 `status.json`，收集**每一个** `*.dispatch.md` 引用（不再只看 `review_1`/`review_2`）。review 引用保留 `review_key` 以继续参与根状态检查；其余携带 `None`，只做 pending-with-outputs 检查。标签使用点路径，报错直接指向具体字段。 |
| `scripts/tests/test_validate_stage_dispatch_protocol.py` | 新增 Group 10b 共 5 条：fix 类 dispatch 被检出、列表内嵌套引用可达、`superseded` 回执不误报、非 review 引用不触发阶段检查、review 引用不重复报告。 |

**先复现后修复的证据**：改完 validator 后立即运行，它检出了 `r7_repair_authorization.active_dispatch`
（即 packet 72）—— 正是终审指出的那一条，证明修复有效。

## 5. 顺带清理的历史簿记债（纯簿记，不消耗额度）

新检查上线后暴露 **18 条**回执漂移，全部处理：

- **14 条封存为 `completed`**：证据**只取自各自产出报告的 footer**；
  `54`/`55`/`62` 的 footer 无时刻、`72` 的 footer 只有日期（改用文件 mtime 并**明确标注非模型自报**），
  这些字段一律 `unavailable` 或标注来源。**未发明任何时间或 Session ID。**
- **4 条改为 `superseded`**（`30-review-1-backend`、`50-review-2`、`52`、`53`、`61`）：
  这些 packet 在执行前即被取代，停在 `pending` 本身就是错误记录；它们声明的 outputs 文件存在，
  只是因为**后续 packet** 产出了同名文件。这也是我实现中发现的**误报源**，
  已通过"终态不检查"消除。判定依据全部取自 `status.json` 的既有记录
  （`review_1_history`、`scope_amendment.supersedes`、`task_runtime_amendment.supersedes_unexecuted_dispatch`）。

## 6. 自测

```text
scripts/tests/test_validate_stage_dispatch_protocol.py  72 passed（原 67 + 新增 5）
validate-stage --phase pre-review                        漂移告警全部消除
```

## 7. 遗留

`74-review-2-r2.md` 的终审 verdict 仍是 **REWORK**，本次特批**不改变**该 verdict，
只是按其 `required_fixes` 完成了修复。是否重开终审由用户决定；若不重开，
本 stage 将以"终审 REWORK + 用户特批修复 + 未复核"的状态进入上线测试，
该状态已如实记录于 `status.json`。

**实盘门未被本授权解除。**

---

当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/29-user-special-approval-r8.md
本地北京时间: 2026-07-27 CST
下一步模型: none（用户特批，不派发评审）
下一步任务: user decides whether to re-open the final gate before live testing

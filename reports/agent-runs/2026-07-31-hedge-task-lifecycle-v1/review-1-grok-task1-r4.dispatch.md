# Dispatch —— review-1-grok-task1-r4（复核确认，只读）

```text
Identity:
  task_id:         review-1-grok-task1-r4
  target_role:     Reviewer
  target_model:    grok
  provider:        xai
  status_revision: 18
  required_skill:  agents/skills/code-reviewer.md
```

## Goal —— 这是一次**窄范围复核确认**，不是新一轮全面评审

你在 r3 对 `ef53a02` 返回 `REWORK`，唯一 `in-range` 发现是 **F4**（账户读不到时 `match_status` 仍输出 `no_um`）。

**代码没有任何改动，仍是 `ef53a02`。** 变化的只有一件事：**Human 已明确将 F4 接受为已知限制**，并要求把修复折入紧随其后的 Task 2，不在 Task 1 修。

因此本轮请你确认一件事：**把 F4 从范围内移除之后，`ef53a02` 是否还存在其它 `in-range` 缺陷？**

你在 r3 的报告中已写明「in-range 发现：1 条」（即 F4），其余均为观察。若该判断不变，**请直接返回 `ACCEPT`**，不需要重新展开 V1-V6 的完整复核。

- 实现作者 `claude_glm`（`zhipu_glm`），你 `grok`（`xai`），provider 隔离成立。
- 只读会话。`rework_count = 2 / 3`（第 3 轮修复未发生，已回落）。

## 评审对象（与 r3 完全相同，代码未变）

```text
base_sha     = c1cc10e8fb491f83fe4c09f565b34e06c2de0a50
delivery_sha = ef53a025114933e8c472d9ae89f8ebfb35d19513
```

可用 `git diff 6d6aa7b..ef53a02` 回看你 r3 审过的差异。**自 r3 以来无任何代码提交**，可用 `git log ef53a02..HEAD --oneline` 核实其间仅有 Bookkeeper 控制提交。

## Human 对 F4 的接受（含 Bookkeeper 对其前提的更正）

Human 最初判断「只在启动时出现，我不会当真」。Bookkeeper 核实后**纠正了该前提并已被采纳**：

| 触发路径 | 何时发生 |
|---|---|
| `SnapshotNotReady` | **仅**启动窗口 —— Human 的判断适用 |
| `verified: false` | **任何时刻**（API key 失效、IP 白名单变更、币安私有接口报错、网络抖动 → 两个 balance 读取均返回 `None`）—— Human 的判断**不适用** |

Human 在知悉更正后仍决定接受，理由是修复可零成本折入 Task 2（新交付物、额度重算，且属其范围内的正常实现而非返工）。

五要素记录、临时观察方式与转入 Task 2 的具体要求见 `46-review-1-grok-task1-r3.md` §3。

**因此 F4 在本轮属范围外，不得据以返工。** 但若你认为其「可能影响」被低估（例如实际后果比 §3.2 所记更严重、或存在 §3.1 未列出的第三条触发路径），**请直接说明** —— 那是新信息，Human 会重新权衡，而不是返工要求。

## 同样属范围外，不得据以返工

- **已接受限制 A / B**（`22-` §5）
- **Human 已裁定的两项**（`45-` §4）：均价用 8 位有效数字、借款去重保留
- **Human 推后的建议项与历轮观察**：`41-` §2、`42-` §2、以及你 r3 报告中的观察 1-5（全腿未知时均价回落 0、API 层 `open_basis_rate` 占位、G6 无 self-check 锁定、`formatHedgeAvgPrice` 极小值 `toFixed` 越界、范围外清单）
- **同币双向**（D13）

## Acceptance Checks

1. **确认 F4 是否仍是唯一的 `in-range` 发现**。若是 → `ACCEPT`。
2. 若你在 r3 之后**新发现**了其它 `in-range` 缺陷（r3 未列出的），请报出，并说明为何 r3 未覆盖到。
3. 确认自 r3 以来**代码确无改动**（`git log ef53a02..HEAD --oneline` 应只含 Bookkeeper 控制提交）。

**不要重新展开 V1-V6 的完整复核** —— 那些结论你已在 r3 给出，Bookkeeper 已封存。本轮只解决"移除 F4 后是否还有别的阻塞"这一个问题。

## 输出要求

按 `AGENTS.md` §7 返回 `[TASK_RESULT v2]`，含三行闭合字段：

```text
评审结论: ACCEPT（接受） | REWORK（返工）
问题记录: <path | none>
修复要求: <path | none>
```

- `问题记录` / `修复要求` 填 `inline-full-text`，正文随回执同交（本轮正文可以很短）。
- **`本地北京时间` 须由 `date '+%Y-%m-%d %H:%M:%S CST'` 实际产生。**
- 若确认无其它 in-range 缺陷，请干脆返回 `ACCEPT`；**不要为显得尽责而把已列为观察的项升格为返工**。

## Stop

- 只读：不得修改任何文件（含 `status.json`）、不得写代码、不得提交、不得合并、不得推送。
- 不得移动 `HEAD`。
- 不得启动、调用、转交或冒充任何其他模型会话（§3 #2）。
- `ACCEPT` 不构成实现、验收、合并、部署或实盘授权；结论交回 Human，由 Bookkeeper 同步。

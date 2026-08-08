# Review-1（Claude Opus 5）：Harness 不再管理子代理 — 问题记录

- 日期：2026-08-08 23:40:51 CST
- 受审对象：`docs/planning/harness-cli-managed-subagents-2026-08-08.review-request-opus5.md`
- 固定范围：`a21a340..45a2cf9`（`git diff --name-status` 仅 `AGENTS.md`、`agents/roles.md`、`docs/planning/DECISIONS.md`；`git diff --check` 无输出）
- 快照核验：`snapshot/harness-before-cli-managed-subagents-20260808^{}` = `a21a3403151114067389f4b5bd3f7baf93436205`，与 `base_sha` 一致 ✓
- 评审者：Claude Opus 5（provider identity `anthropic`）；作者侧 Codex（`openai`）——provider 隔离成立
- 性质：只读 review-1。本文件是本次评审的 `问题记录`；除本文件外未修改任何代码、合同、状态或文档
- **评审结论：`REWORK`**（一条 in-range 阻塞发现，一词可修）

---

## F-1（in-range，阻塞）活动 Harness 残留一条子代理级限制，且该术语已失去定义

**路径**：`AGENTS.md:202-204`

**原文**：

```text
These fields are informational only and never authorize dispatch. The current
delivery team cannot start, call, relay to, or assign the next formal workflow
actor.
```

**证据**：

```console
$ git log --oneline -S'delivery team' -- AGENTS.md
45a2cf9 docs(harness): delegate subagent policy to model CLIs
a21a340 docs(harness): snapshot ponytail-lite policy
```

只有两个提交涉及该词：`a21a340` 同时引入了定义与用法，`45a2cf9`（本次交付）删除了定义、保留了用法。被删除的定义原文（`AGENTS.md` §3 旧第 2 条）：

> For authorship and formal review, **the parent and all its subagents are one delivery team**: the actual vendor of every implementation or fix contributor joins the author-provider set…

`a21a340` 之前，该行主语是 `The current model`。

**为什么它只针对子代理而非当前角色本身**：`delivery team` 在本仓库的唯一定义就是"父代理 + 其全部子代理"这一复合单位。删除定义后，该词在活动 Harness 中不再有任何解释，其语义只能回溯到已被删除的子代理条款。

**实际影响**：

1. **未达成本次交付自身的需求**——"活动 Harness 不保留任何对子代理的描述或限制"。
2. **活动契约出现无定义术语**，违反 `AGENTS.md` §2"每条规则有单一详细活动权威"。
3. **交付自带的核验命令对该残留结构性失效**：`rg -i 'sub-?agents?|子代理'` 之所以无输出，正是因为这一行不含 `subagent` 字样；`DEC-2026-08-08-002` 中 "The active Harness contains no description or restriction of subagent use" 的断言随之不成立。
4. 该行同时与 §3 第 2 条重复陈述同一禁令（§3 才是权威）。

**范围分类说明**：该行的引入提交即 `base_sha` 本身，且位于本次交付文件内，因此不满足 `pre-existing-*` 所要求的"不在本次交付文件内"。按"交付自身范围未执行完整"计 **`in-range`**。

**最小可执行修法**：

```diff
 These fields are informational only and never authorize dispatch. The current
-delivery team cannot start, call, relay to, or assign the next formal workflow
+model cannot start, call, relay to, or assign the next formal workflow
 actor.
```

（恢复 `a21a340` 之前的主语，保留其 "formal workflow actor" 措辞。）

**修订后重跑**：

```bash
git grep -n -iE 'sub-?agents?|子代理|delivery team|\bparent\b' -- AGENTS.md agents/
```

---

## 已通过的核验

| 核验项 | 结果 |
|---|---|
| 固定范围三文件 + `git diff --check` 洁净 | pass |
| 快照 tag 解引用 = `base_sha` | pass |
| 子代理关键词核验（`sub-?agents?｜子代理`）无输出 | pass |
| 安全内核重编号后无失效引用 | pass — 活动 Harness 内对安全内核的引用全部是整节形式（`AGENTS.md:9`、`:19`、`:231`；`agents/skills/complexity-evaluator.md:17`、`:25`），无任何 `§3.N` 子项引用 |
| 七条保留边界完整 | pass — 资金授权 §3.1；文件范围 §3.3；不自审 §3.4；vendor 隔离 §3.5 + `roles.md` Provider Identity 表；固定 SHA §3.6；无 `ACCEPT` 不通过 §3.7；不接管下一会话 §3.2 + `roles.md` Shared Rules。`roles.md` Reviewer Isolation 四条未被触碰 |
| 语义残留核验 | **fail** — 见 F-1 |
| `DEC-2026-08-08-002` 记录准确性 | **fail** — 决定、保留边界、恢复点均准确，但"活动 Harness 已无子代理描述"的断言与 F-1 不符 |
| 最小充分性 | pass（含下方两处非阻塞冗余） |

**边界是否矛盾**：不矛盾。§3 第 2 条主语为 `No model`，而子代理本身即模型会话，禁令仍覆盖它。

---

## 剩余风险（非阻塞，不改 verdict）

- **R-1 子代理行为的归属责任已无表述。** 删除后，活动 Harness 不再说明"父代理是否为其子代理的行为负责"。当前使用的 CLI（Claude Code）已提供跨会话消息能力（`ListAgents` / `SendMessage` 可达本机其他会话及远程会话），其范围超出"会话内子代理"的直觉边界；Human 拍板的是"子代理编排交给 CLI 架构"，未必意在放开跨终端投递。禁令本身仍在，缺的只是归属表述。
  **重开触发**：出现子代理向另一正式工作流终端投递、消费下一 dispatch，或推进工作流状态。
- **R-2 `DEC-2026-08-08-002` 未写重开/复看条件。** 条目自称 "reversible trial"，但未命名何种观察结果会触发回退；同表其他条目（如 `DEC-2026-08-07-001`）均有复看条件。
- **R-3 `agents/roles.md` 同一禁令两处并存。** 第 4-5 行标题句与 Shared Rules 新增 bullet 陈述同一规则，而权威在 `AGENTS.md` §3 第 2 条；且该 bullet 写作 "the next workflow model session"，窄于 §3 权威的 "the next **or another independent** workflow model session"。作为 §2 允许的"限定范围的一行提醒"可接受；若要更贴权威，补两词或删其一。

---

## 评审者披露

本评审者非本次交付作者，provider 隔离成立。但曾出具 `base_sha` 中 §1 Scenario Admission 的 v1/v2 计划评审意见（`ponytail-lite-harness-overthinking-2026-08-08.review-opus5.md`、`…review-v2-opus5.md`），而本次评审须适用该规则。按 `agents/roles.md` Reviewer Isolation"设计参与须披露"如实声明；该参与不涉及本次受审交付的实现。

本 `REWORK` 不授权实施、合并、部署或实盘操作。修法由 Human 决定交由原作者执行，或由 Human 明确接受该残留并同步更正 `DEC-2026-08-08-002` 的断言。

# Harness Follow-Up Dispatch — `dispatch-reading-scope-and-budget`

**This is not stage delivery work.** It lands on `main`, on its own branch, and
is merged there. This file lives in the stage directory only because the finding
originated here; the change must not enter `stage/2026-07-hedge-order-truth-v1`.

Human operator: run the prompt body in a fresh **write-capable Codex** session.

## Routing note — why Codex is admissible here

`agents/registry.yaml` sets `implementation_routing.codex_eligible_for_implementation_or_fix: false`
and AGENTS.md states Codex is not an implementation or fix author. Both scope to
**stage delivery** implementation and fix authorship. This is harness
documentation on `main`, outside any stage, so neither bars it.

⚠️ **The binding constraint**: Codex is this stage's Review-1 **and** Review-2
gate. If this branch were merged into `stage/2026-07-hedge-order-truth-v1`,
Codex would end up reviewing a diff containing its own authored text. So:

- branch from `main` (`ecc3841`), merge back to `main` only;
- **never** merge it into the live stage branch, and never merge `main` into that
  stage branch while this change is on it;
- touch nothing under `reports/agent-runs/**`.

The user waived review for this change. It is therefore confined to **guidance**:
no hard gate, no schema, no validator, so nothing can fail closed unexpectedly
and no reviewer-binding rule changes under a reviewer's feet.

## Prompt body

```text
[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务的唯一执行者。
1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令。
2. 输出必须保留事实来源路径；不得把未验证的假设写成事实。

你在给这个仓库的 Harness 修一个已记录的缺口。这不是 stage 交付工作：从 main
开分支、改完合回 main、不走评审（用户已明确豁免）。

## 缺口是什么（有实测数据，不是猜测）

2026-07-28，一个实现会话（claude_glm, glm-5.2[1m], 1M 上下文）在**还没开始
写代码**、只读到一半时就占掉了约 65% 上下文（~650k token）。

bookkeeper 实测了这个任务的完整语料：
- 源码（含只读的传输面 client）272 KB
- 测试 172 KB
- stage 文档 103 KB
- 合计 ~546 KB，**全部完整读一遍约 160k token**

也就是说 650k 是整份语料预算的约 4 倍，而且还没读完。归因拆成两半：

- **约 160k 记在 Harness 头上**：实现 dispatch 包一直把整个文件列进「必读」，
  从不给行区间。模块小的时候没问题，但现在
  `backend/hedge_open_tasks/service.py` 有 1753 行、`store.py` 有 1784 行。
- **多出来的约 490k 不是 Harness 造成的**：那是会话反复整文件重读、把大块
  搜索结果灌进上下文。没有任何 Harness 规则要求它这么做。

两半都要修，但分别修在不同的地方。

## 一个关键事实，先核实再动手

`AGENTS.md` 里「必须读原始产物」那条硬规则**只约束评审者**
（"Reviewers are read-only. They must inspect raw artifacts:"），对**实现者
的读取方式没有任何规定**。请自己在 AGENTS.md 里核对这一点再写。

结论有两层，都要在文案里体现：
1. 实现包列整文件是我们的**习惯**，不是契约要求 → 收窄它**不需要改任何硬门**。
2. 即使对评审者，那条规则禁的是「用摘要替代产物」，**不是**禁止更窄的指针。
   指向 `service.py:1600-1700` 仍然是原始产物。规则的本意是防止 bookkeeper
   用叙述掩盖证据——收窄指针完全保住这个本意，替换成叙述才是违规。
   这一层必须写清楚，否则以后有人会拿那条规则反对收窄。

## 要改什么

### 1. `AGENTS.md` —— 给 bookkeeper 加一小节包撰写指导

放在 Roles 里 bookkeeper 职责附近（它已经写了 bookkeeper "may prepare dispatch
packets"）。**明确标注为指导条款，不是 Hard Gate**，内容约四到六条：

- 任务局部化时，包里引用**锚点或行区间**（`path:from-to` 或函数名），只在任务
  确实横跨整个文件时才列整文件；
- 包里**写明预期读取预算**（大致 token 量或"这些区间加起来约 N KB"），并要求
  被派会话在明显超出时**先报告再继续**，而不是等操作员在 65% 时发现；
- 任务语料超过阈值时，**默认按开发拆分自己的工作项边界切成多个会话**，中间由
  bookkeeper 提交检查点；阈值给一个可操作的量级建议，别写成硬性数字门。
- 明写：**收窄指针不等于摘要**。禁止用 bookkeeper 叙述替代原始产物这条不变；
  更窄的原始指针是允许且鼓励的。

### 2. `agents/developer-discipline.md` —— 给实现者加读取纪律

对应上面那多出来的 490k。两三条即可：

- 已经读过的文件不要整份重读；需要回看时读**具体区间**；
- 搜索结果只取需要的部分，不要把大块输出整个留在上下文里；
- 发现自己明显超出包里给的读取预算时，**停下报告 bookkeeper**，不要闷头继续
  ——上下文耗尽会在实现中途触发压缩，而压缩最先丢的是冻结约束
  （本仓已因此发生过跨 seam 漂移）。

### 3. 证据落地（可选，最小化）

如果 `docs/harness-design.md` 有合适的位置，加一小段把上面的实测数字记下来
作为这条规则的依据。**没有合适位置就不要硬塞**——宁可不加。

## 硬性约束

- **只改** `AGENTS.md`、`agents/developer-discipline.md`，以及可选的
  `docs/harness-design.md`。
- **不得改**：Hard Gates 清单本身、`schemas/**`、`scripts/validate-stage.py`、
  `workflows/**`、`agents/registry.yaml`。这次不加任何机器校验，也不动任何
  会 fail-closed 的东西——那些要改得走评审。
- **不得碰** `reports/agent-runs/**` 的任何文件。
- 从 `main`（`ecc3841`）开分支，例如
  `harness/dispatch-reading-scope-and-budget`；改完合回 `main`。
  **绝对不要**合进 `stage/2026-07-hedge-order-truth-v1`，也不要把 main 合进
  那个分支——该 stage 的两道评审门都是 Codex，混进去就等于自审。
- 保持**简短**。这是指导条款，不是新子系统。加起来几十行，不要写成一篇方法论。
  如果你写了 200 行，删到 50 行。
- 事实带路径。AGENTS.md 里「只约束评审者」那句请引用行号或原文。

## 交付

在 main 上完成合并，然后回报：分支名、commit sha、改了哪几个文件、每个文件加了
什么（一两句），以及你核对 AGENTS.md 那条规则时看到的原文。

最后附上下面的 footer。

当前 Session ID: 报告你的 provider-native id，取不到就写 unavailable 并说明原因
Session ID 来源: runtime_env | hook_payload | cli_output | transcript_path | active_session_registry | operator | unavailable
原始输出路径: AGENTS.md, agents/developer-discipline.md（+ 可选 docs/harness-design.md）
本地北京时间: 用本地 date 命令取
下一步模型: human operator
下一步任务: 确认合并已落 main，且未进入任何 stage 分支
```

Current dispatch executor: **human operator**. The bookkeeper does not execute
Codex commands or relay this prompt to a model.

当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native session id)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-order-truth-v1/18-harness-followup-dispatch.md
本地北京时间: 2026-07-28 19:15 CST
下一步模型: human operator
下一步任务: 在全新的可写 Codex 终端执行本 packet，分支从 main 起，合回 main

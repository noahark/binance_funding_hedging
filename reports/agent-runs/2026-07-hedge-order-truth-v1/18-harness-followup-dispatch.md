# Harness Follow-Up Dispatch — `dispatch-reading-scope-and-budget`

**This is not stage delivery work.** It lands on `main`, on its own branch, and
is merged there. This file lives in the stage directory only because the finding
originated here; the change must not enter `stage/2026-07-hedge-order-truth-v1`.

Human operator: run the prompt body in a fresh **write-capable Codex** session.

**This file is self-contained.** All measurements are embedded in the prompt
body, because Codex branches from `main` where `reports/agent-runs/` does not
exist — it must not go looking for the evidence files or switch branches to read
them. Handing over this one file is sufficient.

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

## 缺口是什么（实测数据全部内嵌在下面，不是猜测）

**注意**：本 packet 引用的证据文件都在 stage 分支
`stage/2026-07-hedge-order-truth-v1` 上。你从 `main` 开分支后工作区里**不会有
`reports/agent-runs/` 这个目录**。所以下面把全部数据内嵌了——不要去找那些路径，
也不要为了看它们去切分支。

### 事件

2026-07-28，一个实现会话（`claude_glm` / `glm-5.2[1m]`，1M 上下文，session
`2b5e8d01-45cb-4219-a96f-b0d8604bb6d3`）在**还没开始写代码**、读到
`service.py` 的 pause 辅助与 worker 区段、以及一个只读的传输面 client 时，
上下文已占约 **65%（~650k token）**。操作员发现并上报。

### 该任务完整语料的实测（基线 commit `ecc3841`，即该会话读到的状态）

| 文件 | 行 | 字节 |
| --- | ---: | ---: |
| `backend/hedge_open_tasks/domain.py` | 1191 | 52,082 |
| `backend/hedge_open_tasks/store.py` | 1784 | 81,911 |
| `backend/hedge_open_tasks/service.py` | 1753 | 82,685 |
| `backend/hedge_open_tasks/executor.py` | 391 | 16,519 |
| `backend/services/live_hedge_executor.py` | 557 | 25,175 |
| `backend/services/hedge_open_live_client.py`（只读，禁改） | 283 | 13,305 |
| `backend/tests/test_hedge_domain.py` | 475 | 20,246 |
| `backend/tests/test_hedge_store.py` | 436 | 19,475 |
| `backend/tests/test_hedge_service.py` | 574 | 24,258 |
| `backend/tests/test_hedge_executor.py` | 328 | 12,831 |
| `backend/tests/test_hedge_api.py` | 662 | 30,429 |
| `backend/tests/test_hedge_task_local.py` | 997 | 44,270 |
| `backend/tests/test_live_hedge_executor.py` | 323 | 13,751 |
| `backend/tests/test_hedge_purity.py`（只读，禁改） | 140 | 6,369 |
| **源码 + 测试小计** | **9,894** | **443,306** |
| stage 文档 7 份（`00-task` / 证据 2 份 / `10-design` / `11-adr` / 拆分 / 本任务 dispatch） | 1,736 | 102,528 |
| **合计** | **11,630** | **545,834（~546 KB）** |

### token 估算与方法

- 代码与测试为 ASCII，约 3.7 字节/token → 443,306 / 3.7 ≈ **120k token**
- stage 文档中文密集（UTF-8 中文 3 字节/字，约 1–1.5 token/字）→ ≈ **40k token**
- **全部完整读一遍 ≈ 160k token**

估算方法写在这里是为了让人能复核，不是为了精确到个位。就算把它整体翻倍当上界
（320k），也仍然只有观测值的一半。

### 归因（这是本次修复的依据，请在文案里体现这个拆分）

| 归因 | 量级 | 说明 |
| --- | ---: | --- |
| **记在 Harness 头上** | ~160k | 实现 dispatch 包一直把整个文件列进「必读」，从不给行区间。模块小的时候没问题，但 `service.py` 已 1753 行、`store.py` 1784 行。7 份文档也是整份列入。 |
| **不是 Harness 造成的** | ~490k | 会话反复整文件重读、把大块搜索结果留在上下文里。没有任何 Harness 规则要求它这么做。 |

650k 是整份语料的约 4 倍，**而且还没读完**——所以这不是"文件太大"，主因是读法。
两半都要修，但要修在不同的地方（见下面第 1 节与第 2 节）。

### 为什么这件事值得修，而不是记一笔了事

该会话之后确实开始写代码了（基线之后 `store.py` +265 行、`live_hedge_executor.py`
+179 行、`domain.py` +161 行），所以本次没有当场失败。风险在后半程：这个任务
有 6 个工作项，最大的一步和一次表重建迁移都在后面，剩余预算不足会在实现中途
触发上下文压缩。**本仓已经因为压缩后的漂移吃过亏——上一轮一次抓修了 3 处跨
seam 漂移。** 压缩最先丢的恰恰是冻结约束（逐字文案、文件边界、"永不落假 0"
这类规则），而且要等到评审才暴露。

## 一个关键事实，先核实再动手

`AGENTS.md` 里「必须读原始产物」那条硬规则**只约束评审者**，对**实现者的读取
方式没有任何规定**。相关原文与行号（基线 `ecc3841`，你在 main 上能直接核对）：

```text
AGENTS.md:269  ... Reviewers are read-only.
AGENTS.md:270  They must inspect raw artifacts:
AGENTS.md:377  - Reviewer input must be raw artifacts and file paths, not only bookkeeper
AGENTS.md:378    summaries.
AGENTS.md:136  - Feed reviewers only its own narrative summary.   ← bookkeeper 的 must-not 列表
AGENTS.md:236  ... Implementers may write code only within the active task
AGENTS.md:237  scope and file boundary.                            ← 实现者一节，只讲写不讲读
```

请自己在 main 上核对这几处再动笔（行号可能因后续改动漂移，以内容为准）。

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

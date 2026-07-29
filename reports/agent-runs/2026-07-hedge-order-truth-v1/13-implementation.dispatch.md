# Implementation Dispatch — `backend` (the only implementation task)

Human operator: run this in a fresh **Claude-GLM** session (`glm-5.2[1m]`,
provider `zhipu_glm`), write-capable, in the repository working tree on branch
`stage/2026-07-hedge-order-truth-v1`.

⚠️ **The live surface is OPEN.** Service PID 96409 is running in live mode, the
durable Start gate is `1`, and a real naked SHORT 10000 NOMUSDT is outstanding.
The prompt body carries the absolute prohibitions; do not relax them.

Bookkeeper corrections carried into the prompt (disclosed, not silent —
`status.bookkeeper_added_checkpoints`):

- **M-1** Breakdown §3.4 writes `python3 -m pytest`. On this machine `python3` is
  the system Python **3.9.6**; the repository interpreter is `.venv/bin/python`
  (**3.11.15**), which is what the previous stage's test evidence used. The
  prompt uses `.venv/bin/python`. Suite list, tee target and full-repo regression
  are otherwise exactly as §3.4 specifies.
- **M-2** Two design residuals are restated so they cannot mislead: `10-design.md`
  §0 still describes T4 as the cancelled paid experiment, and `11-adr.md` numbers
  ADRs by topic so **T2's ADR is `ADR-T3`**, not `ADR-T2`.

## Prompt body

```text
[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务的唯一执行者。
1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令（包括但不限于 claude -p、
   kimi -p、codex exec、grok）。需要其他模型时，只输出交接建议，由 human operator 决定。
2. 你不得自行 dispatch 任何评审；收尾后停下等 bookkeeper。
3. 输出必须保留事实来源路径与未解决风险；不得把未验证的假设写成事实。
4. 本任务不启用只读研究子代理（status.local_readonly_research_subagents.opted_in
   = false）。不得 spawn 任何子代理。

你是 stage `2026-07-hedge-order-truth-v1` 唯一实现任务 `backend` 的 owner
（claude_glm / glm-5.2[1m]）。当前分支 stage/2026-07-hedge-order-truth-v1。

## 这个 stage 在修什么

上一轮让真单发得出去了。这一轮修的是**发出去之后我们记下来的东西是假的**：
真成交 10000 张记成金额 0（T1）、真拒单 51169 记成无分类（T2）、交易所原话
没地方存（T3）、唯一一条敞口记录时间戳是 1970（T5）。

**总原则（贯穿全部实现）：宁可显式失败 / 显式未知，也不要落一个与真实值
无法区分的替代值。** 这一条比任何单点写法都重要——本 stage 的四个缺陷都是
"用一个说得通的值顶替了已有信息"。

## 必读（按顺序）

1. `reports/agent-runs/2026-07-hedge-order-truth-v1/00-task.md`
   —— **验收标准的最高权威**。与设计冲突时以它为准。
2. `.../01-live-record-evidence.md` —— bookkeeper 从生产库只读导出的原始行，
   本 stage 最高事实来源，优先于任何转述。
3. `.../02-collateral-cap-finding.md` —— 51169 的根因（平台级抵押上限打满）。
   T2 的语义建立在它上面。
4. `.../10-design.md` —— 完整设计。**§10 是你的文件边界。**
5. `.../11-adr.md` —— 架构决策。
6. `.../12-development-breakdown.md` —— **§3 是你的任务卡，§3.3 是实现顺序。**
7. `AGENTS.md`、`agents/developer-discipline.md`。

### 两条会误导你的残留，先知道

- `10-design.md` **§0 目标段**仍留着一句 T4 的旧描述（"判别实验/可照做的规程"）。
  那笔付费实验**已取消**，本 stage 不下任何单。以 §5 与 `00-task.md` §T4 为准。
- `11-adr.md` 的 ADR 编号**按主题顺序，不对应 T 编号**：
  `ADR-T2` 是 T1 的"取不到怎么表示"，**T2 的分类决策是 `ADR-T3`**，
  `ADR-T4` 是 T3 的原始响应落库。查"某项的 ADR"时别按编号猜。

## 实现顺序（照 §3.3 走，不要自行重排）

W1 T2 分类重构 → W2 T5 时间戳统一 → W3 T3 raw 持久化 →
W4 T1 成交数据来源（最大一步）→ W5 ADR-T6 历史数据迁移 → W6 折入的
preflight snapshot 键名契约测试。

每步做完先跑该步涉及的套件，全部做完再跑全量并生成 60-test-output.txt。
这个顺序是为了让每一步落在前一步已稳定的面上（T1/T5 在 leg_exposure 相交，
T2/T3 在错误路径相交），别打乱。

## 几个必须做对的点

- **T1**：UM/CM 腿的成交金额不能再来自 POST 响应。取不到权威数字时**禁止**
  落一个与真实 0 无法区分的 `"0"`——按设计用 NULL + 非终态重试。margin 腿仍
  有 `cummulativeQuoteQty`，这个**按产品分流的不对称必须是有意表达的规则**，
  不是顺手的 or 链。
- **T2**：`51169 → collateral_cap`（**不是** `insufficient_funds`），
  `pause_reason=collateral_cap_full`（**不得**复用 `insufficient_margin`——
  它渲染出的"保证金不足"对 51169 是伪事实）。10-design §2(d) 的中文文案是
  **冻结逐字**的，测试要逐字断言。未识别码落 `unclassified`，不再是 NULL。
  **除 51169 外，任何负数码的判定都不许变**——回归矩阵要能证明这一点。
- **T3**：raw 落库**不得改变控制流**。写 raw 失败不能把一笔成功的单变成失败。
  凭据/签名/API key 一律不得落库，脱敏要有断言。
- **T5**：回归测试必须真的走 `service._dispatch_to_outcome` 这条**实盘路径**。
  只测 `executor.py` 不算数——那条路径今天就是对的，正是它掩盖了这个 bug。
- **W5 迁移**：只在测试临时库上跑。**绝对不要**"顺手在生产库试一下"。

## 确定性测试命令

⚠️ 用 `.venv/bin/python`，**不要**用 `python3`（系统 python3 是 3.9.6，
本仓解释器是 .venv 的 3.11.15）。这是 bookkeeper 对 breakdown §3.4 的机械
纠正，套件清单与 tee 目标不变。

```bash
cd "/Users/ark/Desktop/ai code/funding_hedging"
.venv/bin/python -m pytest \
  backend/tests/test_hedge_domain.py backend/tests/test_hedge_store.py \
  backend/tests/test_hedge_service.py backend/tests/test_hedge_api.py \
  backend/tests/test_hedge_executor.py backend/tests/test_hedge_task_local.py \
  backend/tests/test_live_hedge_executor.py \
  backend/tests/test_hedge_open_live_client.py backend/tests/test_hedge_purity.py \
  -q 2>&1 | tee reports/agent-runs/2026-07-hedge-order-truth-v1/60-test-output.txt
```

再跑全仓回归，结果一并附进同一个文件：

```bash
.venv/bin/python -m pytest backend/tests -q 2>&1 | tee -a reports/agent-runs/2026-07-hedge-order-truth-v1/60-test-output.txt
```

`test_hedge_open_live_client.py` 与 `test_hedge_purity.py` **必跑但禁改**，
必须原样通过。`test_hedge_purity` 若因你新增的 import 变红，那是设计违约：
停下报 bookkeeper，不要改测试。

## 文件边界（越界即 R3 升级）

**允许修改**：

```text
backend/hedge_open_tasks/domain.py
backend/hedge_open_tasks/store.py
backend/hedge_open_tasks/service.py
backend/hedge_open_tasks/executor.py
backend/services/live_hedge_executor.py
backend/tests/test_hedge_domain.py
backend/tests/test_hedge_store.py
backend/tests/test_hedge_service.py
backend/tests/test_hedge_executor.py
backend/tests/test_hedge_task_local.py
backend/tests/test_hedge_api.py
backend/tests/test_live_hedge_executor.py
reports/agent-runs/2026-07-hedge-order-truth-v1/20-implementation.md
reports/agent-runs/2026-07-hedge-order-truth-v1/60-test-output.txt
```

**禁止修改**：`backend/services/hedge_open_live_client.py`（传输面锁死）、
`binance_signing.py`、`wire_constraints.py`、`scheduler.py`、
`backend/app/server.py`、`backend/config.py`、
`test_hedge_open_live_client.py`、`test_hedge_purity.py`、`frontend/**`、
`backend/borrow_tasks/**`、`schemas/**`、`scripts/**`、`docs/**`、`data/**`、
`reports/**`（除上面两个文件）、本 stage 的 status.json 与 70-handoff.md。
未列出的文件默认禁止；需要时先问 bookkeeper。

`hedge_open_live_client.py` 确需改动 = 契约修订：**停下交回 bookkeeper**，
不得顺手扩 allowlist。（唯一可预见触发：W0 样本证明 GET 也丢字段。）

## 绝对禁令（实盘面开着）

- 不得发任何真实 POST；不得下单；不得建卡；不得触发 Start。
- 不得访问、读取、打印凭据；不得发任何 Binance 私有请求。
- 不得启动 / 停止 / 重启服务（PID 96409 正以 live 模式运行）。
- 不得写 `data/hedge-open-tasks.sqlite3` 的任何表（含 settings 行）。
  取证性只读查询允许；迁移只在测试临时库上跑。
- 不得 commit；不得改 status.json 或 70-handoff.md。
- 测试全部离线确定性（fake urlopen / fake executor / 临时 SQLite）。

## 一个未验证的前提，你要知道

T1 的核心假设是「订单详情 GET 仍然携带 cumQuote/avgPrice」——**目前只是推断**，
证据样本 W0 由 human operator 执行，可能还没到。若 W0 未到，按文档形状实现
并在报告里**显式标注该假设未验证**；NULL 表示法就是假设错了的兜底。
若 W0 到了且证明 GET 也没有这些字段：**停止 T1，交回 bookkeeper**走
userTrades 契约修订，不要自己找路绕过去。

## 收尾（三件事，然后停下）

1. 跑上面两条测试命令，生成 `60-test-output.txt`（含全量计数）。
2. 写 `reports/agent-runs/2026-07-hedge-order-truth-v1/20-implementation.md`：
   每个 W 步做了什么、测试节选与完整计数、**T2(c) 判定变化清单**（除 51169
   外任何码的判定变化都要列出并解释）、**T5(c) 关于 `leg_exposure.price`
   是否因 T1 恢复的实测陈述**（不是推测）、W0 假设的状态、以及任何你认为
   评审该看的风险。
3. 停下等 bookkeeper。不要 commit，不要 dispatch 评审。

最后附上下面的 footer。

当前 Session ID: 报告你的 provider-native id，取不到就写 unavailable 并说明原因
Session ID 来源: runtime_env | hook_payload | cli_output | transcript_path | active_session_registry | operator | unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-order-truth-v1/20-implementation.md
本地北京时间: 用本地 date 命令取
下一步模型: bookkeeper
下一步任务: R4 边界核对 + 证据 commit + 指纹 + pre-review 校验，然后派 review-1(codex)
```

Current dispatch executor: **human operator**. The bookkeeper does not execute
Claude-GLM commands or relay this prompt to a model.

当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native session id)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-order-truth-v1/13-implementation.dispatch.md
本地北京时间: 2026-07-28 18:05 CST
下一步模型: human operator
下一步任务: 在全新的 Claude-GLM 终端执行本 packet；并行安排 W0 只读签名 GET

# Review-1 Dispatch — `backend` (Codex, fresh read-only session)

Human operator: run in a **fresh, read-only Codex session**. It must share no
transcript or tool state with any other session — Review-2 will be a **second,
separate** Codex session, and the two must not see each other.

Registry command form (`agents/registry.yaml` `adapters.codex.schema_review_command`):

```bash
codex exec -C "/Users/ark/Desktop/ai code/funding_hedging" -m gpt-5.5 -s read-only \
  --output-schema schemas/review-verdict.schema.json - < <prompt-file>
```

Routing: Codex at Review-1 is a user-authorized, stage-level enablement
(`15-user-authorized-codex-review-1.md`) — it is not in the registered pool,
which was structurally empty here (kimi has no quota; claude_glm is the
implementer). Provider isolation holds: `codex` ≠ `zhipu_glm`.

## Prompt body

```text
[HARNESS-EXECUTOR-CONTRACT v1]
你是本次评审的唯一执行者。
1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令。在本次会话内转派会使本次
   评审作废。
2. 只读。不得修改任何文件、不得 commit、不得运行写操作。
3. 最终必须输出严格符合 schemas/review-verdict.schema.json 的 JSON。JSON 缺失或
   不合 schema = 非接受证据，本次评审作废并重跑。

你是 stage `2026-07-hedge-order-truth-v1` 唯一实现任务 `backend` 的 review-1。

## 评审范围（钉死的区间，不要用移动的 HEAD）

base: ecc38418f52b525eb61bf1c72b9b2b41c26130ef
head: 5de9ef394b02df1036341cbac832cfc4f6c72ee3
diff_fingerprint: 5de9ef394b02df1036341cbac832cfc4f6c72ee3:8259b7cc6266e5a9e9d0f85e99f4928980f65e31be9b9457e5481c730d1b03c8

看 diff 用：git diff ecc38418f52b525eb61bf1c72b9b2b41c26130ef..5de9ef394b02df1036341cbac832cfc4f6c72ee3

⚠️ **必须按区间评审，不要逐 commit 评审。** 见下面「必须先知道的三件事」第 1 条。

## 必须先知道的三件事（不知道会误判）

**1. 三个 bookkeeping commit 里夹带了交付代码——这是 bookkeeper 的错误，已记档。**
`5aceca9`、`8bd03e8`、`ca3cf1f` 的 commit message 写的是文档/簿记，实际各自
夹带了几百行 hedge 实现代码。原因：bookkeeper 在实现者并发写同一工作区时用了
`git add -A`。完整勘误见 `19-r4-reconciliation.md` §Errata。
**后果**：逐 commit 读会得到完全错误的印象。**按 base..head 区间读。**
交付代码本身完整无损（工作区干净，head 的树就是实现者的最终状态）。

**2. 实现报告 `20-implementation.md` 有两处陈述是错的，且已被 bookkeeper 纠正。**
- 它的「关键发现」说 W1/W2/W3（T2 分类 / T5 时间戳 / T3 raw 表）在基线之前
  就已实现、本阶段只做了 W4+W5+W6。**这是错的**，是上面第 1 条造成的假象——
  它对着被污染的 HEAD 做 diff，看见自己早先的工作已被提交。
  已核实：基线 `ecc3841` 的 `domain.py` 是全负数码表、没有 `collateral_cap`，
  `service.py` 给 `build_leg_exposure` 传的是硬编码 `0`。那些正是要修的缺陷。
  **W1–W6 全部是本阶段的工作，都在你要评审的区间内。**
- 它因此省略了 packet 要求的 **T2(c) 判定变化清单**。bookkeeper 从区间 diff
  重建如下，请你独立复核这张表对不对：

  | 码 | 产品 | 之前 | 之后 | 方向 |
  | --- | --- | --- | --- | --- |
  | `51169` | margin | 未列出 → 非致命计数，error_category NULL | `collateral_cap` → task-local pause，pause_reason=`collateral_cap_full` | 更严 |
  | 所有负数码 | 两者 | 不变 | 不变 | 无 |

  另有一处**不是判定变化**的记录值变化：未命中任何规则的业务码现在落
  `error_category="unclassified"` 而不是 NULL，控制流与今天的默认分支完全相同。

**3. 设计文档有两处已知残留，不要当成 finding。**
- `10-design.md` **§0 目标段**仍留着一句 T4 的旧描述（「判别实验 / 可照做的
  规程」）。那笔付费实验**已取消**（根因已查明，见 `02-collateral-cap-finding.md`），
  以 **§5** 与 `00-task.md` §T4 为准。修订 dispatch 有意把改动面限制在
  §2/§5/§8/§11，未授权改 §0。
- `11-adr.md` 的 ADR 编号**按主题顺序，不对应 T 编号**：`ADR-T2` 是 T1 的
  「取不到怎么表示」，**T2 的分类决策是 `ADR-T3`**，`ADR-T4` 是 T3 的原始响应
  落库。查「某项的 ADR」时不要按编号猜。

## 权威顺序（这条决定你怎么判）

**`00-task.md` 的验收标准是最高权威**，高于 `10-design.md`、`11-adr.md` 和实现
报告。设计是被评审的证据，不是标准本身。
`01-live-record-evidence.md`（生产库原始行）与 `02-collateral-cap-finding.md`
（币安官方 FAQ 原文）是事实来源；任何与它们冲突的说法以它们为准。

上一个 stage 的终审正是靠这条权威顺序抓到了唯一的阻塞项——当时 review-1 看着
设计的「可选」措辞把同一个事实归成了可接受残留，而 `00-task.md` 的验收标准
要求的是另一回事。请对照验收标准逐条判，不要对照设计的措辞。

## 必读原始产物

- `reports/agent-runs/2026-07-hedge-order-truth-v1/00-task.md` ← 验收标准
- `.../01-live-record-evidence.md`、`.../02-collateral-cap-finding.md` ← 事实来源
- `.../10-design.md`、`.../11-adr.md`、`.../12-development-breakdown.md`
- `.../19-r4-reconciliation.md` ← bookkeeper 的边界核对与勘误
- `.../20-implementation.md` ← 实现报告（注意上面第 2 条）
- `.../60-test-output.txt` ← 测试证据
- 上面那条 git diff 的完整输出
- 相关源码：`backend/hedge_open_tasks/{domain,store,service,executor}.py`、
  `backend/services/live_hedge_executor.py`

## 重点看什么（拆分 §3.7 + bookkeeper 补充）

1. **「任何取不到的金额是否都不可能落成 `"0"`」** —— 沿 `_decimal_str` 的默认值、
   `_post_figures`/`_query_figures` 的每个分支、`_leg_final_fields` 的每个分支、
   以及迁移 M1 逐条核。注意实现有意保留了 `executed_qty` 的 `"0"` 默认，理由是
   「已接受但未成交的腿真的是零成交量」——判断这个理由成不成立。
2. **负数码判定零变化**的回归矩阵是否完备（T2(c) 表只允许 51169 一行变化）。
3. **raw 落库的容错是否真的不改控制流**（写 raw 失败不能把成功的单变成失败），
   以及脱敏不变式（凭据/签名/API key 绝不落库）。
4. **T5 的测试是否真的走 `service._dispatch_to_outcome`**（实盘路径）。只覆盖
   `executor.py` 不满足验收标准——那条路径本来就是对的，正是它掩盖了 bug。
5. **表重建迁移的幂等与旧数据保真**；生产库零接触。
6. **冻结中文文案**是否与 `10-design.md` §2(d) 逐字一致，且 `51169` 绝不走
   `insufficient_margin` 的展示语义（那会断言一个假的「保证金不足」）。
7. `hedge_open_live_client.py` 与 `wire_constraints.py` 的 diff 必须为空。

## 一个未验证的前提，必须按「假设」而不是「事实」来判

**W0 尚未执行。** T1 的核心假设——「订单详情 GET 仍然携带
`cumQuote`/`avgPrice`」——**目前只是推断**，没有实盘样本。实现按文档形状做，
并以 NULL 表示法作为假设错误时的兜底，报告里也标注了。

请判断：(a) 这个标注是否诚实充分；(b) NULL 兜底是否真的能在假设错误时避免
记录假数据；(c) 这个未验证前提是否应当阻塞验收。**这是你的判断，不要默认
接受 bookkeeper 或实现者的处理方式。**

## 输出

严格符合 `schemas/review-verdict.schema.json` 的 JSON，必填字段：
`schema_version`、`stage_id`、`role`、`model`、`verdict`、`diff_fingerprint`、
`reviewer_prior_involvement`、`reviewed_artifacts`、`findings`、
`required_fixes`、`next_action`。

- `stage_id` = `2026-07-hedge-order-truth-v1`
- `role` = `review_1`
- `diff_fingerprint` 填上面那个完整串
- `reviewer_prior_involvement` = `none`（Codex 未参与本 stage 的方向、设计或拆分）
- `verdict` = `ACCEPT` 或 `REWORK`
- 若 `REWORK`，必须给 `fix_start_prompt`：一段可直接发给修复实现者的完整提示词，
  保留原始产物路径、findings、必须修的内容、文件边界、确切测试命令与验收标准。

footer 放在最终 JSON 之前，或放进 schema 允许的字段里，别破坏 JSON 可解析性。

当前 Session ID: 报告你的 provider-native id，取不到就写 unavailable 并说明原因
Session ID 来源: runtime_env | cli_output | operator | unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-order-truth-v1/30-review-1.md
本地北京时间: 用本地 date 命令取
下一步模型: bookkeeper
下一步任务: 归档 verdict，校验 schema 与指纹一致性
```

Current dispatch executor: **human operator**.

当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native session id)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-order-truth-v1/30-review-1.dispatch.md
本地北京时间: 2026-07-28 20:05 CST
下一步模型: human operator
下一步任务: 在全新只读 Codex 会话执行本 packet，输出存 30-review-1.md

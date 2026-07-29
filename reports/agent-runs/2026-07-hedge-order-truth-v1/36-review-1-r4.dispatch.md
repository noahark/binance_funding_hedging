<!-- ===== DISPATCH RECEIPT（执行者/记账者填写） =====
status: completed
target_model: codex/GPT-5 Codex
adapter_cmd: codex exec -C "/Users/ark/Desktop/ai code/funding_hedging" -m gpt-5.5 -s read-only --output-schema schemas/review-verdict.schema.json - < <prompt-body-file>
executor: human_operator
started_at: unavailable:the operator recorded no start timestamp and the verdict carries no footer time
completed_at: 2026-07-29T01:20:00+08:00
completed_at_source: bookkeeper's archiving time — the Codex verdict JSON carried no 本地北京时间 footer
session_id: unavailable:the Codex runtime exposes no provider-native session id, and the verdict returned no footer carrying one
outputs: reports/agent-runs/2026-07-hedge-order-truth-v1/36-review-1-r4.md
verdict: REWORK (schema-valid; fingerprint matched; 1 P0, declined on scope by the user and filed as a follow-up)
next_dispatch: reports/agent-runs/2026-07-hedge-order-truth-v1/37-fix-review-1-r4.dispatch.md (human operator)
receipt_sealed_by: bookkeeper (Claude Opus 5), on archiving the raw output. Codex at review-1 is a user-enabled stage-level routing exception per 15-user-authorized-codex-review-1.md. Every field is taken from the packet or the verdict itself; nothing invented.
===== END RECEIPT ===== -->

# Review-1 Dispatch, Round 4 — `backend` (Codex, fresh read-only session)

Human operator: run in a **fresh, read-only Codex session**. Not any of the three
earlier review-1 sessions, and not the one that will run Review-2.

```bash
codex exec -C "/Users/ark/Desktop/ai code/funding_hedging" -m gpt-5.5 -s read-only \
  --output-schema schemas/review-verdict.schema.json - < <prompt-file>
```

## Prompt body

```text
[HARNESS-EXECUTOR-CONTRACT v1]
你是本次评审的唯一执行者。
1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令。
2. 只读。不得修改任何文件、不得 commit。
3. 最终必须输出严格符合 schemas/review-verdict.schema.json 的 JSON。

你是 stage `2026-07-hedge-order-truth-v1` 实现任务 `backend` 的 review-1，**第四轮**。

## 本轮范围

base: ecc38418f52b525eb61bf1c72b9b2b41c26130ef
head: baced322e7871ffdcb2a3ad9208da3d1b5dd2524
diff_fingerprint: baced322e7871ffdcb2a3ad9208da3d1b5dd2524:3c4d16f387538c9f7f2afdef32b415c5f355a3ae0a255740870252a43abc7a5f

全量：git diff ecc38418f52b525eb61bf1c72b9b2b41c26130ef..baced322e7871ffdcb2a3ad9208da3d1b5dd2524
只看本轮修复：git diff c06c92140a371b3dc577cf7b509f27b61e4a7948..baced322e7871ffdcb2a3ad9208da3d1b5dd2524

⚠️ 按区间评审，不要逐 commit 评审（原因见「必须先知道的」第 1 条）。

## 第三轮的两个 P1 是怎么修的——注意：**没按你的建议修**

你第三轮给了两条 P1，两条 bookkeeper 都独立核实成立。修复如下：

**Finding 1（限频查询丢证据）—— 按你的建议修了。**
`service.py` 的 drain 限频分支在 `continue` 之前补了一条
`_persist_leg_raw(..., "order_query", ...)`。

**Finding 2（畸形 2xx 无限增长）—— 用户否决了你的建议，改用另一种修法。**
你建议让畸形 2xx 返回 `None`。**用户认为那是范围漂移**——它改的是**业务判定
语义**，而这是一个数据真实性 stage，风险更大。用户给的规则是存储层的：

> 每条腿、每个 `source` 只存一行。写之前查一下有没有，有就跳过。

因此 `store.append_raw_response` 在它自己的锁与事务内加了一个存在性检查。
**`live_hedge_executor.py` 本轮 diff 为空**——这是"没有任何业务判定被改动"的
机械证据。畸形 2xx 仍然返回带 raw 的 UNKNOWN、仍然继续查询、仍然不会被误判为
absent，一切照旧，只是不再重复写库。

**用户明确接受的两个代价**（记在 `00-task.md` §T3 与 `status.json`）：
- 某条腿已有 `order_query` 行之后，**定案那次查询的原文不再保存**。腿自己那行
  仍记录结果（`exchange_status`/`cumulative_quote_amt`/`order_id`），业务真相不丢。
- 若某腿第一条 `order_query` 行已被占用，**后来的 429 不会保存**。用户原话：
  「429 就 429，遇到问题我们再分析问题解决问题，不做无谓的猜想适配方案」。

**请对照 `00-task.md`（收窄后的版本）判断这个修法是否满足验收标准。**
如果你认为这个修法在技术上不成立（而不只是与你的偏好不同），说出来并 REWORK；
但请把「我更倾向另一种修法」与「收窄后的标准仍未满足」分开表述。

## 一个 bookkeeper 在核实 Finding 2 时确认的事实（供你参考，不在本轮修复范围）

`service.py:1075-1077`：只要有腿非终态，worker 就 `return False` 继续 drain，
**永远走不到下面派发下一组的分支**——所以卡住的腿会让**该任务停止开新单**。
刷行只是症状，停摆才是后果。

该行为是**有意且安全的**（腿状态不明时开新组等于蒙眼加仓），本轮**未改动**，
也不打算改。写在这里只是为了避免误解：存储上限不是这个停摆的解药，两者是两回事。

## 必须先知道的三件事（沿用前三轮）

**1. 若干 bookkeeping commit 里夹带了交付代码**（`5aceca9`、`8bd03e8`、`ca3cf1f`）
——bookkeeper 用 `git add -A` 造成，勘误见 `19-r4-reconciliation.md` §Errata。
**按区间读。**

**2. 实现报告第一轮部分有两处陈述已被纠正**：W1/W2/W3 **不是**基线之前就有的；
T2(c) 判定变化清单由 bookkeeper 重建——`51169` 是唯一判定变化（未列出/计数 →
`collateral_cap` → task-local pause，更严），所有负数码不变；另有非判定变化：
未命中码落 `unclassified` 而非 NULL。

**3. 设计文档两处已知残留，不要当 finding**：`10-design.md` §0 仍留着一句 T4
旧描述（付费实验已取消，以 §5 与 `00-task.md` §T4 为准）；`11-adr.md` 的 ADR
编号按主题顺序，**T2 的分类决策是 `ADR-T3`**。

## 权威顺序

**`00-task.md`（含 2026-07-28 的 T3 Scope decision）是最高权威**，高于设计、
ADR、实现报告，也高于你前三轮的 verdict。
`01-live-record-evidence.md` 与 `02-collateral-cap-finding.md` 是事实来源。

## 必读

- `00-task.md` ← 验收标准，重点 §T3 与其 Scope decision
- `01-live-record-evidence.md`、`02-collateral-cap-finding.md`
- `10-design.md`、`11-adr.md`（尤其 ADR-T4 的容量论证）、`12-development-breakdown.md`
- `19-r4-reconciliation.md`、`30-review-1.md`、`32-review-1-r2.md`、`34-review-1-r3.md`
- `20-implementation.md`（含本轮追加章节）、`60-test-output.txt`
- 上面两条 git diff
- 源码：`backend/hedge_open_tasks/{domain,store,service,executor}.py`、
  `backend/services/live_hedge_executor.py`

## 本轮重点

**A. 本轮修复**
1. 限频分支的落库是否真的在 `continue` 之前、且**没有**改变 pause 语义 /
   非终态处理 / 永不重发 / 控制流隔离？
2. 存在性检查是否在 `append_raw_response` **自己的短事务与锁**内？跳过是否是
   正常返回而**不是**被当成 `raw_persist_failed`？
3. 是否真的**零 schema 变更**（无 digest 列、无 UNIQUE 索引、无迁移）？
4. `live_hedge_executor.py` 本轮 diff 是否确为空（业务判定零改动）？
5. 新增的 `test_4i` / `test_4j` 是否真的锁住了行为？特别是 `test_4j` 的
   `query_calls > 2`——它是"确实查了多轮、但每腿只留一行"的关键断言，
   没有它测试可以空过。

**B. 全量范围（本轮仍是完整评审）**
1. **T1**：任何取不到的金额是否都不可能落成 `"0"`——沿 `_decimal_str` 默认值、
   `_post_figures`/`_query_figures` 每个分支、`_leg_final_fields` 每个分支、
   迁移 M1 逐条核。`executed_qty` 有意保留 `"0"` 默认（理由：已接受未成交的腿
   真的是零成交量），判断该理由是否成立。
2. **T2**：`51169 → collateral_cap` / `pause_reason=collateral_cap_full`，绝不走
   `insufficient_margin`；冻结中文文案与 `10-design.md` §2(d) 逐字一致；负数码
   判定零变化的回归矩阵是否完备。
3. **T3（收窄后）**：产生确定判定的往返是否都落库（POST 成功与失败、UM inline
   confirm、即时 fallback 解析成功、drain 解析成功、drain 限频）？在"每腿每来源
   一行"的上限下，这个覆盖是否仍然成立？
4. **T5**：回归测试是否真的走 `service._dispatch_to_outcome`（实盘路径）。
5. **迁移**：表重建幂等、旧数据保真、生产库零接触。
6. **脱敏**：凭据 / 签名 / API key 绝不落库。
7. `hedge_open_live_client.py` 与 `wire_constraints.py` 的 diff 必须为空。

## 仍未验证的前提

**W0 仍未执行**——「订单详情 GET 是否仍携带 `cumQuote`/`avgPrice`」目前只是推断。
你前三轮都把它列为 residual risk 而非阻塞项。本轮请**再次独立判断**，不要沿用。

## 输出

严格符合 `schemas/review-verdict.schema.json` 的 JSON。
- `stage_id` = `2026-07-hedge-order-truth-v1`
- `role` = `first_reviewer`
- `diff_fingerprint` = 上面那个新串
- `reviewer_prior_involvement` = `none`
- 若 `REWORK`，schema 强制要求 `fix_start_prompt`

footer 放在最终 JSON 之前或放进 schema 允许的字段，别破坏 JSON 可解析性。

当前 Session ID: 报告你的 provider-native id，取不到就写 unavailable 并说明原因
Session ID 来源: runtime_env | cli_output | operator | unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-order-truth-v1/36-review-1-r4.md
本地北京时间: 用本地 date 命令取
下一步模型: bookkeeper
下一步任务: 归档 verdict，校验 schema 与指纹
```

Current dispatch executor: **human operator**.

当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native session id)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-order-truth-v1/36-review-1-r4.dispatch.md
本地北京时间: 2026-07-29 01:00 CST
下一步模型: human operator
下一步任务: 在全新只读 Codex 会话执行本 packet，输出存 36-review-1-r4.md

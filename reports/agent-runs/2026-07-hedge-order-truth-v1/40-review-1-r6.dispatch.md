<!-- ===== DISPATCH RECEIPT（执行者/记账者填写） =====
status: completed
target_model: codex/GPT-5 Codex
adapter_cmd: codex exec -C "/Users/ark/Desktop/ai code/funding_hedging" -m gpt-5.5 -s read-only --output-schema schemas/review-verdict.schema.json - < <prompt-body-file>
executor: human_operator
started_at: unavailable:the operator recorded no start timestamp and the verdict carries no footer time
completed_at: 2026-07-29T03:30:00+08:00
completed_at_source: bookkeeper's archiving time — the Codex verdict JSON carried no 本地北京时间 footer
session_id: unavailable:the Codex runtime exposes no provider-native session id, and the verdict returned no footer carrying one
outputs: reports/agent-runs/2026-07-hedge-order-truth-v1/40-review-1-r6.md
verdict: REWORK (schema-valid; fingerprint matched; 1 P1, confirmed and accepted for fix)
next_dispatch: reports/agent-runs/2026-07-hedge-order-truth-v1/41-fix-review-1-r6.dispatch.md (human operator)
receipt_sealed_by: bookkeeper (Claude Opus 5), on archiving the raw output. Every field is taken from the packet or the verdict itself; nothing invented.
===== END RECEIPT ===== -->

# Review-1 Dispatch, Round 6 — `backend` (Codex, fresh read-only session)

Human operator: run in a **fresh, read-only Codex session**. Not any of the five
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

你是 stage `2026-07-hedge-order-truth-v1` 实现任务 `backend` 的 review-1，**第六轮**。

## 本轮范围

base: ecc38418f52b525eb61bf1c72b9b2b41c26130ef
head: 95ac1a549c640f7ff01cf7773e577228ffc663e8
diff_fingerprint: 95ac1a549c640f7ff01cf7773e577228ffc663e8:1ea0690a232325b25ce2ed02c24a85aa825378d1ac60e7f478b65df5ce56455b

全量：git diff ecc38418f52b525eb61bf1c72b9b2b41c26130ef..95ac1a549c640f7ff01cf7773e577228ffc663e8
只看本轮：git diff 2712fbaed284d777708a9f74ecb3b1cabe22d155..95ac1a549c640f7ff01cf7773e577228ffc663e8

⚠️ 按区间评审，不要逐 commit 评审（原因见下面第 1 条）。

## 本轮修了你第五轮的两个 P1

**Finding 1（M1 迁移做跨字段推断）** —— 按你的建议**整段删除 M1**。不收窄、
不给 leg 6 开特例、不硬编码 orderId。`leg 6` 的 `"0"` 原样保留，其背景由
`01-live-record-evidence.md` 承载。**M2 保留**（它修的是 `leg_exposure.ts` 的
1970 epoch，属于 T5，与交易所金额无关）。原迁移测试**反转**而非删除，名字保留
以维持证据可 grep。

**Finding 2（首行去重丢弃定案响应）** —— 采用你 recommendation 里的第一种：
`append_raw_response` 新增 keyword-only 的 `decisive` 参数。**行数上限仍是
每腿每 source 一行**，但：
- 无行 → 插入（并记下 decisive 标志）
- 有行 + 来者 decisive + 既有非 decisive → **原地 UPDATE 并置 decisive=1**
- **既有 decisive → 永不被替换**（first decisive wins）
- 来者非 decisive → 跳过

`decisive` 由**调用方**从它手上已有的判决决定（`_query_verdict_decisive`：
成交 / 拒绝-过期-撤销 / 确认不存在 / 限频），**store 内绝不从 body 反推**。
新增 `decisive` 列为 additive（`CREATE` 带列 + `ALTER` 守卫 + `DEFAULT 0` 回填）。

用户额外加了一条约束（防止反向 bug）：**不能后写覆盖先写**。所以除你点名的三组
回归外，还加了第四条护栏——先 `FILLED` 后 `NEW`，行里必须仍是 `FILLED`。

## 必须先知道的（不知道会误判）

**1. 若干 bookkeeping commit 里夹带了交付代码**（`5aceca9`、`8bd03e8`、`ca3cf1f`）
——bookkeeper 用 `git add -A` 造成，勘误见 `19-r4-reconciliation.md` §Errata。
**按区间读，不要逐 commit 读。**

**2. 实现报告第一轮部分有两处陈述已被纠正**：W1/W2/W3 **不是**基线之前就有的；
T2(c) 判定变化清单由 bookkeeper 重建——`51169` 是唯一判定变化（未列出/计数 →
`collateral_cap` → task-local pause，更严），所有负数码不变；另有非判定变化：
未命中码落 `unclassified` 而非 NULL。

**3. 设计文档有多处已被 `00-task.md` 取代，全部是已知且有意的，不要当 finding：**
- `10-design.md` §0 仍留着一句 T4 旧描述（付费判别实验**已取消**，根因见
  `02-collateral-cap-finding.md`，以 §5 与 `00-task.md` §T4 为准）
- `10-design.md` §6 与 `11-adr.md` **ADR-T6 关于 M1 的那一半**已被本轮删除取代
  （**ADR-T6 关于 M2 的一半仍然成立**）
- `10-design.md` 中关于 T1 `filled_qty × avg_price` 推算兜底的表述，已被
  `00-task.md` §T1 的 2026-07-29 收窄取代（推算已删除）
- `10-design.md` 中关于不确定查询也要留痕的表述，已被 `00-task.md` §T3 的
  2026-07-28 收窄取代（不确定查询不要求留痕）
- `11-adr.md` 的 ADR 编号**按主题顺序、不对应 T 编号**：**T2 的分类决策是
  `ADR-T3`**，`ADR-T2` 是 T1 的「取不到怎么表示」，`ADR-T4` 是 T3 的落库

设计与 ADR 写在两次用户收窄之前。**冲突时一律以 `00-task.md` 为准。**

## 权威顺序

**`00-task.md`（含 §T3 的 2026-07-28 与 §T1 的 2026-07-29 两处 Scope decision）
是最高权威**，高于设计、ADR、实现报告，也高于你前五轮的 verdict。
`01-live-record-evidence.md` 与 `02-collateral-cap-finding.md` 是事实来源。

## 必读

- `00-task.md` ← 验收标准，**重点 §T1 / §T3 及各自的 Scope decision**
- `01-live-record-evidence.md`、`02-collateral-cap-finding.md`
- `10-design.md`、`11-adr.md`、`12-development-breakdown.md`（注意上面第 3 条）
- `19-r4-reconciliation.md`、`30-review-1.md`、`32-review-1-r2.md`、
  `34-review-1-r3.md`、`36-review-1-r4.md`、`38-review-1-r5.md`
- `20-implementation.md`（含六轮追加章节）、`60-test-output.txt`
- 上面两条 git diff
- 源码：`backend/hedge_open_tasks/{domain,store,service,executor}.py`、
  `backend/services/live_hedge_executor.py`

## 本轮重点

**A. 本轮两处修复**
1. M1 是否**彻底**删除、无残留？`_migrate` 删除后是否仍幂等？**M2 是否完好**？
   反转后的迁移测试是否真的断言「重开数据库后字面 `"0"` 仍是 `"0"`」？
2. `decisive` 是否真的由调用方决定、store 内不反推？替换是否**只**发生在
   「来者 decisive 且 既有非 decisive」？**decisive 行是否真的永不被替换**？
3. 第四条护栏测试（先 FILLED 后 NEW）是否真的能区分「真标志」与
   「last-write-wins」？没有它，一个错误实现也能通过前三条。
4. `decisive` 列迁移是否 additive、幂等、旧数据保真？
5. 行数上限是否仍然成立（`test_4j` 的 `query_calls > 2` 是否仍通过）？

**B. 全量范围（本轮仍是完整评审）**
1. **T1（收窄后）**：`cumulative_quote_amt` 是否严格等于「交易所原话或 NULL」？
   缺失 → NULL、无推算；字面 `0` 原样存；2026-07-14 的原始缺陷是否仍被修好
   （「没有」与「零」可区分）？
2. **T2**：`51169 → collateral_cap` / `pause_reason=collateral_cap_full`，绝不走
   `insufficient_margin`；冻结中文文案与 `10-design.md` §2(d) 逐字一致；负数码
   判定零变化的回归矩阵是否完备。
3. **T3（收窄后）**：产生**确定判定**的往返是否都可从库中检索到完整 body——
   POST（成功与失败）、UM inline confirm、即时 fallback 解析成功、drain 解析
   成功、drain 限频？在「每腿每 source 一行 + 定案覆盖非定案」下是否成立？
4. **T5**：回归测试是否真的走 `service._dispatch_to_outcome`（实盘路径）。
5. **脱敏**：凭据 / 签名 / API key 绝不落库（`decisive` 是判决标志，不是凭据）。
6. **raw 写失败隔离**：仍不改变任何业务结果。
7. `hedge_open_live_client.py` 与 `wire_constraints.py` 的 diff 必须为空
   （`live_hedge_executor.py` 已连续三轮零 diff）。

## 仍未验证的前提

**W0 仍未执行**——「订单详情 GET 是否仍携带 `cumQuote`/`avgPrice`」只是推断。
推算兜底已删除，所以这个假设现在**直接决定库里有没有金额**：假设若错，合约腿
的金额会是 NULL 而不是错值。你前五轮都判它为 residual risk 而非阻塞项。
**本轮请再次独立判断。**

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
原始输出路径: reports/agent-runs/2026-07-hedge-order-truth-v1/40-review-1-r6.md
本地北京时间: 用本地 date 命令取
下一步模型: bookkeeper
下一步任务: 归档 verdict，校验 schema 与指纹
```

Current dispatch executor: **human operator**.

当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native session id)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-order-truth-v1/40-review-1-r6.dispatch.md
本地北京时间: 2026-07-29 03:10 CST
下一步模型: human operator
下一步任务: 在全新只读 Codex 会话执行本 packet，输出存 40-review-1-r6.md

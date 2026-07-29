# Review-1 Dispatch, Round 7 — `backend` (Codex, fresh read-only session)

Human operator: run in a **fresh, read-only Codex session**. Not any of the six
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

你是 stage `2026-07-hedge-order-truth-v1` 实现任务 `backend` 的 review-1，**第七轮**。

## 本轮范围

base: ecc38418f52b525eb61bf1c72b9b2b41c26130ef
head: 34ad0ca47f1f802030a694a798e8bb49ef8b55c6
diff_fingerprint: 34ad0ca47f1f802030a694a798e8bb49ef8b55c6:05d0233047696ff966c3fa6d682f96c8cf9bd3a0df08f59882a4f06b1b97fef2

全量：git diff ecc38418f52b525eb61bf1c72b9b2b41c26130ef..34ad0ca47f1f802030a694a798e8bb49ef8b55c6
只看本轮：git diff 95ac1a549c640f7ff01cf7773e577228ffc663e8..34ad0ca47f1f802030a694a798e8bb49ef8b55c6

⚠️ 按区间评审，不要逐 commit 评审（原因见下面第 1 条）。

## 本轮修了你第六轮的 P1

三个投影函数（`_leg_to_doc` / `_entry_spot_leg` / `_entry_perp_leg`）不再用
`or "0"`：`cumulative_quote_amt` 为 NULL 时输出 JSON `null`，且**不做除法**，
`avg_price` 也是 `null`；真实的 `"0"` 仍走原算术、仍输出 `"0"`。
`cumulative_base_qty` 的 `or "0"` **按指令未动**（没有成交量记录的腿，成交量
真的是零，不在本 finding 范围）。

bookkeeper 额外核了一个你没提的边界并确认安全：旧的 `or "0"` 同时吸收空字符串，
而 `is None` 不会。写入路径只会写合法十进制串或 NULL，生产库现有行也证实如此。

## ⚠️ 必读事故记录：迁移曾在生产库上执行

`42-production-db-write-incident.md`（**本轮新增，请完整阅读**）。

`store._migrate()` 于 **2026-07-28 18:51:42** 在 `data/hedge-open-tasks.sqlite3`
上真的执行了 M1 与 M2，并写下了自己的审计事件。与 intake 快照完整比对后确认：
**只有那两处迁移修复发生了变化，其余一律未变**——未建卡、未下单、未动 Start
闸门，仍是 5 卡 4 腿 0 raw 行、`start_gate=1 version=4`。

两处变化及其定性：
- `leg 6` 的 `cumulative_quote_amt`：`'0'` → `NULL`（M1）。**M1 本轮之前已被
  删除**，所以这是一处"孤儿"改动。但它实质正确：leg 6 的那个 `'0'` **从来不是
  交易所说的**——币安 2026-07-14 移除 `cumQuote`，旧的 `_decimal_str(None)` 把
  "缺失"强转成了 `'0'`。按已定的 verbatim-only 规则，NULL 才是该行的正确值。
  **用户 2026-07-29 决定：保持 NULL，不还原。**
- 任务 `a1d0a9ac` 的 `leg_exposure.ts`：1970 epoch → `2026-07-27T14:14:29.799447Z`
  （M2）。M2 仍在代码中，该修复本身合法。

bookkeeper 已记录自己在 R4 核对第 8 项上的失职（用 gitignored 路径的
`git status` 加一行 settings 交差，把 mtime 变化当成"服务写的"），并已开
harness follow-up 要求加机械闸门。

**请把它当作事实背景，而不是待修缺陷**：当前代码不会再产生此类写入（M1 已删、
M2 幂等）。若你认为它构成阻塞项，请明确说明理由。

## 必须先知道的（不知道会误判）

**1. 若干 bookkeeping commit 里夹带了交付代码**（`5aceca9`、`8bd03e8`、`ca3cf1f`）
——bookkeeper 用 `git add -A` 造成，勘误见 `19-r4-reconciliation.md` §Errata。
**按区间读。**

**2. 实现报告第一轮部分有两处陈述已被纠正**：W1/W2/W3 **不是**基线之前就有的；
T2(c) 判定变化清单由 bookkeeper 重建——`51169` 是唯一判定变化（未列出/计数 →
`collateral_cap` → task-local pause，更严），所有负数码不变；另有非判定变化：
未命中码落 `unclassified` 而非 NULL。

**3. 设计文档多处已被 `00-task.md` 取代，全部是已知且有意的，不要当 finding：**
- `10-design.md` §0 的 T4 旧描述（付费判别实验**已取消**，以 §5 与
  `00-task.md` §T4 为准）
- `10-design.md` §6 与 `11-adr.md` **ADR-T6 关于 M1 的那一半**（M1 已删；
  **ADR-T6 关于 M2 的一半仍成立**）
- `10-design.md` 中 T1 `filled_qty × avg_price` 推算兜底的表述（推算已删除，
  见 `00-task.md` §T1 的 2026-07-29 收窄）
- `10-design.md` 中"不确定查询也要留痕"的表述（见 §T3 的 2026-07-28 收窄）
- `11-adr.md` 的 ADR 编号**按主题顺序、不对应 T 编号**：**T2 的分类决策是
  `ADR-T3`**

设计与 ADR 写在两次用户收窄之前。**冲突时一律以 `00-task.md` 为准。**

## 权威顺序

**`00-task.md`（含 §T3 的 2026-07-28 与 §T1 的 2026-07-29 两处 Scope decision）
是最高权威**，高于设计、ADR、实现报告，也高于你前六轮的 verdict。
`01-live-record-evidence.md`、`02-collateral-cap-finding.md` 与
`42-production-db-write-incident.md` 是事实来源。

## 必读

- `00-task.md` ← 验收标准，重点 §T1 / §T3 及各自 Scope decision
- `01-live-record-evidence.md`、`02-collateral-cap-finding.md`
- `42-production-db-write-incident.md` ← **本轮新增**
- `10-design.md`、`11-adr.md`、`12-development-breakdown.md`（注意上面第 3 条）
- `19-r4-reconciliation.md`、`30-review-1.md`、`32-review-1-r2.md`、
  `34-review-1-r3.md`、`36-review-1-r4.md`、`38-review-1-r5.md`、`40-review-1-r6.md`
- `20-implementation.md`（含七轮追加章节）、`60-test-output.txt`
- 上面两条 git diff
- 源码：`backend/hedge_open_tasks/{domain,store,service,executor}.py`、
  `backend/services/live_hedge_executor.py`

## 本轮重点

**A. 本轮修复**
1. 三个投影函数是否都真正透传 NULL？金额未知时 `avg_price` 是否一定为 `null`
   （没有任何路径会算出 0）？
2. 真实 `"0"` 是否仍输出字符串 `"0"`——「没有」与「零」在 wire 上是否仍可区分？
3. 是否引入了新的等价缺陷（例如把 `cumulative_base_qty` 也误改，或空串导致异常）？
4. 两条新测试是否真的覆盖 attempts 与 entries 两种投影、spot 与 perp 两条腿？

**B. 全量范围（本轮仍是完整评审）**
1. **T1（收窄后）**：从执行器 → 存储 → 投影，整条链路是否严格「交易所原话或
   NULL」？缺失绝不成 0、不推算、不做跨字段检查；2026-07-14 的原始缺陷是否
   在**每一层**都被修好？
2. **T2**：`51169 → collateral_cap` / `pause_reason=collateral_cap_full`，绝不走
   `insufficient_margin`；冻结中文文案与 `10-design.md` §2(d) 逐字一致；负数码
   判定零变化的回归矩阵是否完备。
3. **T3（收窄后）**：产生确定判定的往返是否都可从库中检索到完整 body？
   「每腿每 source 一行 + 定案覆盖非定案 + 定案永不被覆盖」是否成立？
4. **T5**：回归测试是否真的走 `service._dispatch_to_outcome`（实盘路径）。
5. **脱敏**：凭据 / 签名 / API key 绝不落库。
6. **raw 写失败隔离**：仍不改变任何业务结果。
7. `hedge_open_live_client.py`、`wire_constraints.py` 的 diff 必须为空
   （`live_hedge_executor.py` 已连续四轮零 diff）。

## 仍未验证的前提

**W0 仍未执行**——「订单详情 GET 是否仍携带 `cumQuote`/`avgPrice`」只是推断。
推算兜底已删，所以假设若错，合约腿金额会是 NULL（不是错值）。你前六轮都判它为
residual risk 而非阻塞项。**本轮请再次独立判断。**

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
原始输出路径: reports/agent-runs/2026-07-hedge-order-truth-v1/43-review-1-r7.md
本地北京时间: 用本地 date 命令取
下一步模型: bookkeeper
下一步任务: 归档 verdict，校验 schema 与指纹
```

Current dispatch executor: **human operator**.

当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native session id)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-order-truth-v1/43-review-1-r7.dispatch.md
本地北京时间: 2026-07-29 13:30 CST
下一步模型: human operator
下一步任务: 在全新只读 Codex 会话执行本 packet，输出存 43-review-1-r7.md

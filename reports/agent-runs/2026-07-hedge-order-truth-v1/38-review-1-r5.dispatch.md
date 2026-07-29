<!-- ===== DISPATCH RECEIPT（执行者/记账者填写） =====
status: completed
target_model: codex/GPT-5 Codex
adapter_cmd: codex exec -C "/Users/ark/Desktop/ai code/funding_hedging" -m gpt-5.5 -s read-only --output-schema schemas/review-verdict.schema.json - < <prompt-body-file>
executor: human_operator
started_at: unavailable:the operator recorded no start timestamp and the verdict carries no footer time
completed_at: 2026-07-29T02:20:00+08:00
completed_at_source: bookkeeper's archiving time — the Codex verdict JSON carried no 本地北京时间 footer
session_id: unavailable:the Codex runtime exposes no provider-native session id, and the verdict returned no footer carrying one
outputs: reports/agent-runs/2026-07-hedge-order-truth-v1/38-review-1-r5.md
verdict: REWORK (schema-valid; fingerprint matched; 2 P1, both confirmed and both accepted for fix)
next_dispatch: reports/agent-runs/2026-07-hedge-order-truth-v1/39-fix-review-1-r5.dispatch.md (human operator)
receipt_sealed_by: bookkeeper (Claude Opus 5), on archiving the raw output. The reviewer also reported one flaky test (ConnectionResetError, passing on isolated re-run); the bookkeeper's two independent full runs on this tree were green. Every field is taken from the packet or the verdict itself; nothing invented.
===== END RECEIPT ===== -->

# Review-1 Dispatch, Round 5 — `backend` (Codex, fresh read-only session)

Human operator: run in a **fresh, read-only Codex session**. Not any of the four
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

你是 stage `2026-07-hedge-order-truth-v1` 实现任务 `backend` 的 review-1，**第五轮**。

## 本轮范围

base: ecc38418f52b525eb61bf1c72b9b2b41c26130ef
head: 2712fbaed284d777708a9f74ecb3b1cabe22d155
diff_fingerprint: 2712fbaed284d777708a9f74ecb3b1cabe22d155:6f33425af859e34c2b7793d5d08f163deddb506823aeb0d00c016c43a110b6a4

全量：git diff ecc38418f52b525eb61bf1c72b9b2b41c26130ef..2712fbaed284d777708a9f74ecb3b1cabe22d155
只看本轮：git diff baced322e7871ffdcb2a3ad9208da3d1b5dd2524..2712fbaed284d777708a9f74ecb3b1cabe22d155

⚠️ 按区间评审，不要逐 commit 评审（原因见「必须先知道的」第 1 条）。

## 第四轮那个 P0：**用户按范围否决了，不是被反驳**

你第四轮报了 P0——`FILLED` + `executedQty>0` + 字面 `"0"` 仍会落成零名义。
**bookkeeper 逐步核实过，你那条链子完全成立**（`_quote_decimal` 保留字面 "0"；
`leg_is_terminal_fill` 现货不查 quote、合约只查 `is None`；`_leg_final_fields`
原样存任何存在且可解析的值）。

**用户按范围否决了它**，理由是触发条件不同：2026-07-14 那个缺陷是**字段缺失**被
强转成 0；你这条要求交易所主动发一条**自相矛盾**的响应，实盘从未出现（全仓一共
才 4 条真实腿记录）。用户原话：

> 交易所返回 0 没问题吧，到时遇到具体情况再分析呗。而且金额缺失时也不用推算这么
> 麻烦，查询回来是什么就是什么，有问题我会让模型再去排查的

`00-task.md` §T1 **已按这条规则重写**（见其 §Scope decision）。新规则一句话：

> **交易所返回什么就存什么；没返回就存 NULL。不推算、不换算、不做跨字段一致性检查。**

你的 P0 记为 follow-up `p0-contradictory-zero-notional-not-detected`，
**你自己的 findings 与 required_fixes 原样保留**在 `36-review-1-r4.md`。

## 本轮改了什么：**删代码，不是加代码**

新规则让原有的推算逻辑变成违规，所以本轮**删掉**了它：

`store._leg_final_fields` 里 `filled_qty × avg_price` 的兜底没了——金额缺失
一律 NULL。存在值的分支**一个字没动**（原样存，包括字面 `"0"`，这现在是**预期
行为**）。不可解析值仍然 → NULL。因此变成孤儿的 `avg_price` 局部变量一并清掉。

`live_hedge_executor.py` 本轮 diff **为空**。

**请对照重写后的 `00-task.md` §T1 判断。** 如果你认为这个收窄本身在技术上
不成立（而不只是与你的偏好不同），说出来并 REWORK；但请把「我不同意这个产品
取舍」与「收窄后的标准仍未被满足」分开表述。

## 必须先知道的三件事（沿用前四轮）

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
另：`10-design.md` 与 `11-adr.md` 写于本 stage 早期，其中关于 T1 推算兜底与 T3
不确定查询留痕的表述**已被 `00-task.md` 的两次用户收窄取代**。冲突时以
`00-task.md` 为准，这属于已知且有意的，不要当 finding。

## 权威顺序

**`00-task.md`（含 2026-07-28 的 T3 与 2026-07-29 的 T1 两处 Scope decision）
是最高权威**，高于设计、ADR、实现报告，也高于你前四轮的 verdict。
`01-live-record-evidence.md` 与 `02-collateral-cap-finding.md` 是事实来源。

## 必读

- `00-task.md` ← 验收标准，**重点 §T1 与 §T3 及各自的 Scope decision**
- `01-live-record-evidence.md`、`02-collateral-cap-finding.md`
- `10-design.md`、`11-adr.md`、`12-development-breakdown.md`（注意上面第 3 条）
- `19-r4-reconciliation.md`、`30-review-1.md`、`32-review-1-r2.md`、
  `34-review-1-r3.md`、`36-review-1-r4.md`
- `20-implementation.md`（含五轮追加章节）、`60-test-output.txt`
- 上面两条 git diff
- 源码：`backend/hedge_open_tasks/{domain,store,service,executor}.py`、
  `backend/services/live_hedge_executor.py`

## 本轮重点

**A. 本轮删除**
1. 删掉推算之后，金额缺失是否**无条件** NULL？存在值分支是否真的没被动过
   （字面 `"0"` 仍原样存）？
2. 是否有**任何**残留路径还会把缺失值变成非 NULL？
3. 删除是否留下孤儿（未用变量、失效注释、过期 docstring）？
4. 测试是否真的锁住了这个行为——**包括持久化层**（`resolve_attempt` → leg 行），
   而不只是辅助函数层？

**B. 全量范围（本轮仍是完整评审）**
1. **T1（重写后）**：`cumulative_quote_amt` 是否严格等于「交易所原话或 NULL」？
   2026-07-14 的原始缺陷是否仍然被修好（缺失 → NULL，绝不强转 0，"没有"与"零"
   可区分）？
2. **T2**：`51169 → collateral_cap` / `pause_reason=collateral_cap_full`，绝不走
   `insufficient_margin`；冻结中文文案与 `10-design.md` §2(d) 逐字一致；负数码
   判定零变化的回归矩阵是否完备。
3. **T3（收窄后）**：产生确定判定的往返是否都落库（POST 成功与失败、UM inline
   confirm、即时 fallback 解析成功、drain 解析成功、drain 限频）？「每腿每 source
   一行」的上限下这个覆盖是否仍成立？
4. **T5**：回归测试是否真的走 `service._dispatch_to_outcome`（实盘路径）。
5. **迁移**：表重建幂等、旧数据保真、生产库零接触。
6. **脱敏**：凭据 / 签名 / API key 绝不落库。
7. `hedge_open_live_client.py` 与 `wire_constraints.py` 的 diff 必须为空。

## 仍未验证的前提

**W0 仍未执行。** 注意它现在比前几轮更要紧：T1 收窄成「GET 给什么存什么」之后，
**订单详情 GET 到底带不带 `cumQuote`** 直接决定库里有没有金额——没有推算兜底了。
你前四轮都把它列为 residual risk 而非阻塞项。**本轮请在新规则下重新独立判断**
是否仍然充分。

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
原始输出路径: reports/agent-runs/2026-07-hedge-order-truth-v1/38-review-1-r5.md
本地北京时间: 用本地 date 命令取
下一步模型: bookkeeper
下一步任务: 归档 verdict，校验 schema 与指纹
```

Current dispatch executor: **human operator**.

当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native session id)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-order-truth-v1/38-review-1-r5.dispatch.md
本地北京时间: 2026-07-29 02:00 CST
下一步模型: human operator
下一步任务: 在全新只读 Codex 会话执行本 packet，输出存 38-review-1-r5.md

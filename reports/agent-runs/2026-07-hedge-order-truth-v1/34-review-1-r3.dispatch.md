# Review-1 Dispatch, Round 3 — `backend` (Codex, fresh read-only session)

Human operator: run in a **fresh, read-only Codex session**. Not the round-1 or
round-2 session, and not the one that will run Review-2.

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

你是 stage `2026-07-hedge-order-truth-v1` 实现任务 `backend` 的 review-1，**第三轮**。

## 本轮和上一轮的唯一区别：代码一行没改，是验收标准变了

base: ecc38418f52b525eb61bf1c72b9b2b41c26130ef
head: c06c92140a371b3dc577cf7b509f27b61e4a7948
diff_fingerprint: c06c92140a371b3dc577cf7b509f27b61e4a7948:4f1e005f72892df4435c64444668a785f382170c7b49e229c3aea23aef3dcaa9

`git diff 33715ae2bcb4fef427f340780155dc4e4c316e28..c06c92140a371b3dc577cf7b509f27b61e4a7948 -- backend/`
是**空的**。本轮唯一变化是 `00-task.md` 的 T3 验收标准被**用户**收窄。

## 你上一轮的 P1 发生了什么（重要，请完整读）

你在第二轮指出：不确定的订单详情查询（超时 / 5xx / 歧义 4xx / 畸形 2xx）
其 raw 被 `classify_query_response` 构造后丢弃，两条调用路径都不落库。

**这个 finding 没有被推翻，也没有被质疑。bookkeeper 独立核实后确认它成立**
（`32-review-1-r2.md` 有完整核实记录，包括 `live_hedge_executor.py:395-424`
先构造 raw 再丢弃的证据）。

**用户随后做了产品范围决定**（原话记在 `00-task.md` §T3 Scope decision）：
先让实盘对冲单跑起来，这个极端场景以后遇到再修。因此：

- `00-task.md` T3 收窄为：订单详情读取**在产生确定判定时**必须落库
  （成交 / 确认拒绝 / 确认不存在 / 限频信号），覆盖即时 fallback 与 drain 两条
  路径；**查询本身不确定**时不要求留痕。
- 你的 finding 记为 deferred follow-up `p1-inconclusive-query-raw-not-persisted`，
  **你自己的 `fix_start_prompt` 被原样保留**在 `32-review-1-r2.md`，以便将来
  重启这项工作时不用重新推导。
- 用户已被明确告知代价：真出现"POST 不确定 + 查询也不确定"时，库里查不到
  我们问过什么。这是**已知并接受的风险**，不是疏漏。

**所以本轮请对照收窄后的 `00-task.md` 判，而不是你上一轮用的标准。**
如果你认为这个收窄本身在技术上使 T3 失去意义（而不只是缩小范围），请说出来
并给 REWORK——这仍然是你的判断权。但请把"我不同意这个产品取舍"与"收窄后的
标准仍未被满足"分开表述。

## 必须先知道的三件事（沿用前两轮，不知道会误判）

**1. 若干 bookkeeping commit 里夹带了交付代码**（`5aceca9`、`8bd03e8`、
`ca3cf1f`）——bookkeeper 用 `git add -A` 造成的，勘误见
`19-r4-reconciliation.md` §Errata。**按区间读，不要逐 commit 读。**

**2. 实现报告第一轮部分有两处陈述已被纠正**：W1/W2/W3 **不是**基线之前就有的
（是上面第 1 条造成的假象），且它省略的 T2(c) 判定变化清单由 bookkeeper 重建：
`51169` 是唯一判定变化（未列出/计数 → `collateral_cap` → task-local pause，
更严），所有负数码不变；另有非判定变化：未命中码落 `unclassified` 而非 NULL。

**3. 设计文档两处已知残留，不要当 finding**：`10-design.md` §0 仍留着一句 T4
旧描述（付费实验已取消，以 §5 与 `00-task.md` §T4 为准）；`11-adr.md` 的 ADR
编号按主题顺序，**T2 的分类决策是 `ADR-T3`**。

## 权威顺序

**`00-task.md`（收窄后的版本）是最高权威**，高于设计、ADR、实现报告，也高于你
前两轮的 verdict。`01-live-record-evidence.md` 与 `02-collateral-cap-finding.md`
是事实来源。

## 必读

- `00-task.md` ← **收窄后的验收标准，重点看 §T3 与 §T3 Scope decision**
- `01-live-record-evidence.md`、`02-collateral-cap-finding.md`
- `10-design.md`、`11-adr.md`、`12-development-breakdown.md`
- `19-r4-reconciliation.md`、`30-review-1.md`、`32-review-1-r2.md`
- `20-implementation.md`、`60-test-output.txt`
- `git diff ecc38418f52b525eb61bf1c72b9b2b41c26130ef..c06c92140a371b3dc577cf7b509f27b61e4a7948`
- 源码：`backend/hedge_open_tasks/{domain,store,service,executor}.py`、
  `backend/services/live_hedge_executor.py`

## 本轮评审重点（完整评审，不只看 T3）

1. **T3（收窄后）**：每一次产生**确定判定**的交易所往返是否都落库？
   POST（成功与失败）、UM inline confirm、即时 fallback 查询解析成功时、
   drain 查询解析成功时——四类是否齐全、来源标记是否互不覆盖？
2. **T1**：任何取不到的金额是否都不可能落成 `"0"`——沿 `_decimal_str` 默认值、
   `_post_figures`/`_query_figures` 每个分支、`_leg_final_fields` 每个分支、
   迁移 M1 逐条核。注意 `executed_qty` 有意保留 `"0"` 默认，理由是「已接受未成交
   的腿真的是零成交量」——判断该理由是否成立。
3. **T2**：`51169 → collateral_cap` / `pause_reason=collateral_cap_full`，
   绝不走 `insufficient_margin`；冻结中文文案与 `10-design.md` §2(d) 逐字一致；
   负数码判定零变化的回归矩阵是否完备。
4. **T5**：回归测试是否真的走 `service._dispatch_to_outcome`（实盘路径）。
5. **迁移**：表重建幂等、旧数据保真、生产库零接触。
6. **脱敏**：凭据 / 签名 / API key 绝不落库。
7. `hedge_open_live_client.py` 与 `wire_constraints.py` 的 diff 必须为空。

## 仍未验证的前提

**W0 仍未执行**——「订单详情 GET 是否仍携带 `cumQuote`/`avgPrice`」目前只是推断。
你前两轮都把它列为 residual risk 而非阻塞项。本轮请**再次独立判断**是否仍然
充分，不要因为前两轮这么判过就沿用。

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
原始输出路径: reports/agent-runs/2026-07-hedge-order-truth-v1/34-review-1-r3.md
本地北京时间: 用本地 date 命令取
下一步模型: bookkeeper
下一步任务: 归档 verdict，校验 schema 与指纹
```

Current dispatch executor: **human operator**.

当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native session id)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-order-truth-v1/34-review-1-r3.dispatch.md
本地北京时间: 2026-07-28 22:55 CST
下一步模型: human operator
下一步任务: 在全新只读 Codex 会话执行本 packet，输出存 34-review-1-r3.md

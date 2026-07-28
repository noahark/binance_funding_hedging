# Review-1 Dispatch, Round 2 — `backend` (Codex, fresh read-only session)

Human operator: run in a **fresh, read-only Codex session**. Do not reuse the
round-1 session, and do not reuse it for Review-2 either — Review-2 must be a
third, separate session.

```bash
codex exec -C "/Users/ark/Desktop/ai code/funding_hedging" -m gpt-5.5 -s read-only \
  --output-schema schemas/review-verdict.schema.json - < <prompt-file>
```

## Prompt body

```text
[HARNESS-EXECUTOR-CONTRACT v1]
你是本次评审的唯一执行者。
1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令。在本次会话内转派会使本次
   评审作废。
2. 只读。不得修改任何文件、不得 commit、不得运行写操作。
3. 最终必须输出严格符合 schemas/review-verdict.schema.json 的 JSON。JSON 缺失或
   不合 schema = 非接受证据，本次评审作废并重跑。

你是 stage `2026-07-hedge-order-truth-v1` 实现任务 `backend` 的 review-1，**第二轮**。

## 本轮范围（新区间，钉死，不要用移动的 HEAD）

base: ecc38418f52b525eb61bf1c72b9b2b41c26130ef
head: 33715ae2bcb4fef427f340780155dc4e4c316e28
diff_fingerprint: 33715ae2bcb4fef427f340780155dc4e4c316e28:f3db91f60350b5e8ba2db2237b89baba2c8e77d4d0c477fc9635602d869fa4ab

看全量 diff：git diff ecc38418f52b525eb61bf1c72b9b2b41c26130ef..33715ae2bcb4fef427f340780155dc4e4c316e28
只看本轮修复：git diff 5de9ef394b02df1036341cbac832cfc4f6c72ee3..33715ae2bcb4fef427f340780155dc4e4c316e28

⚠️ 按区间评审，不要逐 commit 评审（原因见下面第 1 条）。

## 第一轮发生了什么

第一轮（区间 ..5de9ef3）由 Codex 给出 **REWORK**，一条 P1：UNKNOWN POST 之后的
即时 order-detail GET 定夺了该腿命运，但它的 raw 被丢弃，从未以
`source=order_query` 落库。原始 verdict 在 `30-review-1.md`。

bookkeeper 独立复核确认该 finding 成立，并发现它**比 verdict 描述的更强**：
这是内部不一致——drain 路径（`service.py:1147`）本来就以 `order_query` 落库了，
同一类证据一条路径存、另一条丢。

修复（`31-fix-review-1.dispatch.md`，claude_glm 全新会话执行）：
`LegDispatch` 新增 `query_raw_response` 字段，`_send_one_leg` 用
`resolved.raw_response` 填充且不碰 `raw_response`(POST)；`_dispatch_live` 为两腿
各加一条 `source="order_query"` 持久化，沿用 drain 的既有模式；新增服务级测试
`test_4h`。三文件 +197/-3，纯增量。

**你的任务是独立判断这个修复是否真的满足 T3，以及是否引入了新问题。不要因为
第一轮是你自己（同一 provider）给的 REWORK 就默认修复到位。**

## 必须先知道的三件事（不知道会误判）

**1. 若干 bookkeeping commit 里夹带了交付代码——bookkeeper 的错误，已记档。**
`5aceca9`、`8bd03e8`、`ca3cf1f` 的 message 写的是文档/簿记，实际各夹带了几百行
实现代码（原因：实现者并发写同一工作区时 bookkeeper 用了 `git add -A`）。
完整勘误见 `19-r4-reconciliation.md` §Errata。**逐 commit 读会得到错误印象，
按区间读。** 交付代码本身完整无损。

**2. 实现报告 `20-implementation.md` 第一轮部分有两处陈述是错的，已被纠正。**
- 它说 W1/W2/W3 在基线之前就已实现、本阶段只做 W4+W5+W6 —— **错**，是第 1 条
  造成的假象。已核实基线 `ecc3841` 的 `domain.py` 是全负数码表、无
  `collateral_cap`，`service.py` 传硬编码 `0`。**W1–W6 全在你要评审的区间内。**
- 它因此省略了 T2(c) 判定变化清单。bookkeeper 从区间 diff 重建如下，**请独立复核**：

  | 码 | 产品 | 之前 | 之后 | 方向 |
  | --- | --- | --- | --- | --- |
  | `51169` | margin | 未列出 → 非致命计数，error_category NULL | `collateral_cap` → task-local pause，pause_reason=`collateral_cap_full` | 更严 |
  | 所有负数码 | 两者 | 不变 | 不变 | 无 |

  另有一处**非判定变化**：未命中规则的业务码现在落 `error_category="unclassified"`
  而非 NULL，控制流与今天的默认分支完全相同。

**3. 设计文档两处已知残留，不要当成 finding。**
- `10-design.md` **§0 目标段**仍留着一句 T4 旧描述（判别实验）。那笔付费实验
  **已取消**（根因见 `02-collateral-cap-finding.md`），以 **§5** 与
  `00-task.md` §T4 为准。修订有意未授权改 §0。
- `11-adr.md` 的 ADR 编号**按主题顺序、不对应 T 编号**：**T2 的分类决策是
  `ADR-T3`**（`ADR-T2` 是 T1 的「取不到怎么表示」，`ADR-T4` 是 T3 的落库）。

## 权威顺序

**`00-task.md` 的验收标准是最高权威**，高于 `10-design.md`、`11-adr.md`、实现
报告，也高于第一轮 verdict。设计与既往 verdict 都是被评审的证据。
`01-live-record-evidence.md`（生产库原始行）与 `02-collateral-cap-finding.md`
（币安官方 FAQ）是事实来源。

## 必读原始产物

- `00-task.md` ← 验收标准
- `01-live-record-evidence.md`、`02-collateral-cap-finding.md` ← 事实来源
- `10-design.md`、`11-adr.md`、`12-development-breakdown.md`
- `19-r4-reconciliation.md` ← 边界核对与勘误
- `30-review-1.md` ← 第一轮 verdict（含 bookkeeper 的确认与"更强"的判断）
- `20-implementation.md` ← 实现报告（含修复追加章节；注意第 2 条）
- `60-test-output.txt` ← 测试证据
- 上面两条 git diff 的完整输出
- 源码：`backend/hedge_open_tasks/{domain,store,service,executor}.py`、
  `backend/services/live_hedge_executor.py`

## 本轮重点

**A. 修复本身**
1. 三种 raw（`order_post` / `order_confirm` / `order_query`）语义是否真的一一
   对应、互不覆盖？POST 的 raw 是否在任何路径上都不会被 GET 顶掉？
2. **是否还有别的路径会丢弃 raw？** 第一轮找到的是即时 fallback GET；请系统性
   地检查所有与交易所往返的点（POST、inline confirm、即时 fallback、drain），
   确认每一次真实往返都有落库，包括**查询本身失败/超时**的情况
   （`transport_error`）。
3. 修复是否真的没动订单判定 / 重发规则 / 限频规则 / raw 写失败时的业务结果？
4. `test_4h` 是否真的驱动 `LiveHedgeExecutor._send_one_leg`（不是绕过执行器的
   假货）？它的断言是否足以锁住这个契约不再回退？
5. 两腿都加了 `order_query` 持久化——perp 腿在 POST 确定时不会产生该行，
   测试也断言了。确认这个 no-op 行为不会写出空行或噪声行。

**B. 全量范围（本轮仍是完整评审，不只看修复）**
1. 「任何取不到的金额是否都不可能落成 `"0"`」——沿 `_decimal_str` 默认值、
   `_post_figures`/`_query_figures` 每个分支、`_leg_final_fields` 每个分支、
   迁移 M1 逐条核。注意实现有意保留 `executed_qty` 的 `"0"` 默认，理由是
   「已接受但未成交的腿真的是零成交量」——判断该理由是否成立。
2. 负数码判定零变化的回归矩阵是否完备（T2(c) 表只允许 51169 一行变化）。
3. 脱敏不变式：凭据 / 签名 / API key 绝不落库。
4. T5 测试是否真的走 `service._dispatch_to_outcome`（实盘路径）。
5. 表重建迁移的幂等与旧数据保真；生产库零接触。
6. 冻结中文文案是否与 `10-design.md` §2(d) 逐字一致，且 `51169` 绝不走
   `insufficient_margin` 的展示语义。
7. `hedge_open_live_client.py` 与 `wire_constraints.py` 的 diff 必须为空。

## 一个仍未验证的前提

**W0 仍未执行。** T1 的核心假设——「订单详情 GET 仍然携带
`cumQuote`/`avgPrice`」——目前只是推断，没有实盘样本。第一轮你把它列为
residual risk 而非阻塞项，理由是 NULL 表示法能防止伪造零值。

本轮请**重新独立判断**这个处理是否仍然充分，不要因为第一轮这么判过就沿用。

## 输出

严格符合 `schemas/review-verdict.schema.json` 的 JSON。
- `stage_id` = `2026-07-hedge-order-truth-v1`
- `role` = `first_reviewer`
- `diff_fingerprint` = 上面那个新的完整串
- `reviewer_prior_involvement` = `none`
- 若 `REWORK`，必须给 `fix_start_prompt`（schema 在 verdict=REWORK 时强制要求）

footer 放在最终 JSON 之前，或放进 schema 允许的字段里，别破坏 JSON 可解析性。

当前 Session ID: 报告你的 provider-native id，取不到就写 unavailable 并说明原因
Session ID 来源: runtime_env | cli_output | operator | unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-order-truth-v1/32-review-1-r2.md
本地北京时间: 用本地 date 命令取
下一步模型: bookkeeper
下一步任务: 归档 verdict，校验 schema 与指纹一致性
```

Current dispatch executor: **human operator**.

当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native session id)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-order-truth-v1/32-review-1-r2.dispatch.md
本地北京时间: 2026-07-28 21:55 CST
下一步模型: human operator
下一步任务: 在全新只读 Codex 会话执行本 packet，输出存 32-review-1-r2.md

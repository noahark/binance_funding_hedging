# Dispatch —— fix-merged-positions-sources-v1（Task 1 修复轮 1/3）

> **⚠️ 作废 2026-08-01（bookkeeper opus5）—— 本 packet 从未交付，不要执行。**
> Human 于签发后、交付前决定 B-1 与 B-2 **两条均本轮不修**，待结合真实使用场景另行设计。
> 拒收随之撤销，`current_task.state` 推进为 `verified`，`rework_count` 回落为 `0`
> （未发生任何修复轮）。两条缺陷已按 `AGENTS.md` §8 转为**已接受的已知限制**，
> 五要素记录见 `22-bookkeeper-rejection-task1.md` §5。本文件仅作留档，不再执行。

```text
Identity:
  task_id:         fix-merged-positions-sources-v1
  target_role:     Implementer
  target_model:    claude_glm
  provider:        zhipu_glm
  status_revision: 10
  required_skill:  agents/skills/minimal-change-engineer.md
```

## Goal

修复 Bookkeeper 核验 `hedge-merged-positions-v1` 时拒收的**两条 in-range 缺陷**，并做一次同族穷举。

**完整拒收依据、证据与可复现场景见 `22-bookkeeper-rejection-task1.md`，本 dispatch 不重述。** 你是该交付的作者，已有上下文。

- 你的交付**大部分通过了核验**（后端 1126、前端 128 全绿，文件边界干净，禁改区未动，D15 两条查询正确，N-1 测试改写而非删除，N2 不 503，`merge_positions` 纯函数成立）。这些在拒收记录 §0 逐项列出，**修复时不得回退**。
- 这是**本交付物的第 1 轮返工**，`rework_count` 由 `0` 递增为 `1`（上限 3）。

## 要修的两条

- **B-1｜`single_leg_exposure` 未消费后端裁定**（`domain.py:1463-1467`）。规格原文要求「单腿敞口**只读后端** `pair_outcome`/`leg_exposure`」，实现改用了 `spot_qty > 0 and perp_qty == 0` 这一自造谓词。它识别不了部分失衡：现货 2.0 / 合约 1.0 时判为「无敞口」，而实际有 1.0 未对冲。
- **B-2｜`spot_balance` 与 `drift` 取错资金池**（`domain.py:1516-1521`、`:1457`、`:1472-1478`）。实现读 `balances_spot`（经典现货账户 `/api/v3/account`），但对冲的现货腿是 margin 单、买入统一账户（`hedge_open_live_client.py:9`；冻结文案 `domain.py:1322` 自述「现货腿当前无法买入保证金账户」；`snapshot.py:1200` 的相加口径证明两池互斥）。后果是 `spot_balance` 列取错池，且 `drift` 因 `real_spot is not None` 守卫而**恒为 False** —— P2 的手工减仓检测静默失效。

两条都涉及资金含义，都未在 `21-merged-positions-implementation.md` 中披露。

## 同族穷举（必做，不是可选）

按 `AGENTS.md` §8「同根因刹车」的预防性应用：两条缺陷同根于「派生字段的数据来源未经核对」。本轮**必须一次扫完**，在实现报告中逐个列出 `_merge_build_row` 内**每一个派生字段**的数据来源，并说明该来源为何正确：

`um_position_side` / `um_position_amt` / `um_notional_usdt` / `um_entry_price` / `um_mark_price` / `um_liquidation_price` / `unrealized_profit` / `price_pnl`（覆盖逻辑）/ `spot_balance` / `cross_margin_borrowed` / `single_leg_exposure` / `drift` / `includes_deleted_task`

清单外若还有其他派生字段，一并列入。目的是**避免第三轮再冒出同类来源错误**。

## Allowed Files

沿用 `hedge-merged-positions-v1.dispatch.md` 的 Allowed Files，不扩大：

- `backend/app/server.py`、`backend/hedge_open_tasks/{service.py, store.py, domain.py}`
- `backend/tests/{test_hedge_store.py, test_hedge_service.py, test_hedge_api.py, test_positions_merge.py, test_hedge_review2_regressions.py}`
- `frontend/index.html`、`frontend/self-check.js`

修改产物（就地更新，按勘误规则附日期说明）：

- `reports/agent-runs/2026-07-31-hedge-task-lifecycle-v1/21-merged-positions-implementation.md`
- `reports/agent-runs/2026-07-31-hedge-task-lifecycle-v1/61-merged-positions-test-output.txt`（覆盖为本轮**原始**输出）

**不得改动**：`private_client.py`、`hedge_preflight_provider.py` 白名单、`scheduler.py`、`domain.py` 的暂停原因集与 51169 文案区（`:1315-1324`）、`status.json` 的 `current_task.state` 以外任何字段。

**不得触碰 Task 2 / Task 3 的范围**（暂停与删除逻辑、worker 退避、重查间隔），即使顺手可改。

## Inputs

| 文件 | 读什么 |
|---|---|
| 本 dispatch | 全部 |
| `22-bookkeeper-rejection-task1.md` | **全部 —— 拒收依据与修复要求的权威** |
| `12-development-breakdown.md` | `## Task 1` 全节（规格未变） |
| `10-design.md` | P1 / N1-N5 / P2 偏离 / P7 占位零 |
| `agents/skills/minimal-change-engineer.md` | 全部 |
| `agents/developer-discipline.md` | 全部 |

关键锚点（已由 Bookkeeper 在当前工作树核对）：`domain.py:998-1012` `classify_attempt`（后端裁定的定义）、`domain.py:1425-1479` `_merge_build_row`、`domain.py:1508-1525` 账户数据装配、`store.py` `aggregate_positions`（两条查询均未 `SELECT` `pair_outcome`/`leg_exposure`）、`hedge_open_live_client.py:9`、`snapshot.py:1200`。

## Acceptance Checks

每项按 `AGENTS.md` §7 标注 `pass` / `fail` / `contested`；`检查结果` 最多八项，请合并同类，详细说明放实现报告。

1. **B-1 已修**：`single_leg_exposure` 以后端 `pair_outcome`/`leg_exposure` 裁定为准；新增测试覆盖「现货 2.0 / 合约 1.0 的部分失衡」场景并断言被正确标记。
2. **B-2 已修**：`spot_balance` 与 `drift` 使用正确资金池；新增测试锁定「对冲买入的币出现在统一账户时被正确匹配」，以及「手工减仓致真实 < 记录时 `drift` 为真」。
3. **同族穷举已完成**：实现报告含上列每个派生字段的来源与正确性说明；清单外字段一并列入。
4. **拒收记录 §0 的已通过项未回退**：后端全套测试与 `node frontend/self-check.js` 均绿，禁改区未触碰，`_POSITION_KEYS` 保持**精确集**断言形式并同步更新。
5. **逐条披露**：报告说明每处改动、为何这样改、放弃了什么；若再遇规格与代码矛盾，**停止并报告**，不得自行替换定义。
6. **最小改动**：只改缺陷及其测试所必需之处，不顺手重构相邻代码（`minimal-change-engineer.md`）。
7. **零新增交易所请求**：本轮不得新增任何对币安的调用。
8. **原始测试输出**：`61-` 覆盖为本轮原始输出，不得改写为叙述性总结。

## Stop

- 完成后按 `AGENTS.md` §7 输出 `[TASK_RESULT v2]`，把 `current_task.state` 由 `dispatched` 改为 `reported`（唯一授权改动的 `status.json` 字段），然后**停止**。
- 不得设置 `next`、不得自行判定验收、不得合并、不得推送。
- 不得接触凭证或实盘路径；不得启动、调用、转交或冒充任何其他模型会话（§3 #2）。
- 若认为某条拒收依据不成立：**不要沉默照改**，在回执中按 `AGENTS.md` §7 标 `contested` 并给出被质疑检查的原文名称、质疑理由、替代证据（可执行命令或已提交路径）。Bookkeeper 会显式裁定；若你的质疑成立，该项按勘误更正、不消耗返工预算。

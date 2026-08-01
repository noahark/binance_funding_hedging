# Dispatch —— fix-merged-positions-n2-ui-v1（Task 1 修复轮 1/3）

```text
Identity:
  task_id:         fix-merged-positions-n2-ui-v1
  target_role:     Implementer
  target_model:    claude_glm
  provider:        zhipu_glm
  status_revision: 12
  required_skill:  agents/skills/minimal-change-engineer.md
```

## Goal

修复 review-1（`grok`）的两条 `in-range` 发现，外加一条 Bookkeeper 核验发现的测试完整性问题。

**完整评审正文、问题记录与修复要求见 `41-review-1-grok-task1.md`（原文逐字留档于 §3），本 dispatch 不重述。** 你是该交付的作者，已有上下文。

- 评审对**后端合并、D15、`merge_positions` 纯度、文件边界与红线、接口键集**均判 pass；这些**不得回退**。
- 这是本交付物的**第 1 轮返工**，`rework_count` 由 `0` 递增为 `1`（上限 3）。
- 按 `minimal-change-engineer.md`：只改发现及其测试所必需之处，不顺手重构相邻代码。

### Human 的优先级（2026-08-01）

> 优先打通「账户未就绪仍显示本地合并表 + 未就绪提示」，其次修「没盈亏别画 0」；其余是细节，先把界面呈现出来，看到实物后再按偏好调整。

因此本轮**只做下列四项**。评审的其余建议（补混合桶均价单测、HTTP 级 N2 断言、强平价 title、注释更正）已由 Human 明确推后，**不得纳入**。

## 要做的四项

### R1｜F1（优先，阻塞项）：账户未就绪时合并表仍须可见

**事实**（Bookkeeper 已逐处复验）：后端已按 N2 正确返回本地记账行 + `account_meta`，但前端把它丢弃了 ——

- `index.html:2739-2742`：`pa` 缺失 → 面板 `display:none` 后 `return`
- `index.html:2746-2757`：`pa.verified !== true` → 整个面板体替换为「私有账户未读取」后 `return`，**不再调用合并表渲染**
- `index.html:3809-3811`：`loadHedgePositions` 仅在 `private_account.verified === true` 时重绘
- 结果：`index.html:4467-4470` 那段 `account.verified === false` 的未就绪横幅**在真实降级路径永不可达**

**要求**：只要 `GET /api/hedge-open-positions` 已返回本地 `positions`，合并表就必须渲染，不得被私有面板的 `verified` 门闩挡住；同时未就绪横幅须真的出现。资产卡部分可以保持「私有账户未读取」占位 —— 缺的是账户数据，不是本地记录。

修法你定（评审给了两个方向：在 `verified !== true` 分支内仍渲染合并表；或把合并表移出「仅 verified」的成功体）。同时须修正 `loadHedgePositions` 的重绘条件，使 `verified === false` 时也能刷新。

**为什么这条优先**：本任务的目的就是资金可见性。账户快照未就绪或私有通道关闭时，用户看不到任何本地持仓与成本 —— 包括 D15 特意保留下来的已删任务成本基。后端做对了，前端丢掉了。

### R2｜F2：有 UM 持仓但盈亏拿不到时，不得画 0

- `domain._merge_build_row`：仅当 `_merge_num(upnl) is not None` 才覆盖 `price_pnl`，否则保留桶里的占位 `"0"`，同时 `unrealized_profit = None`
- `index.html:4495-4497`：`hasUm` 只看 `um_position_amt`；为真即 `formatHedgeSigned(p.price_pnl)` → 渲染 `0.00`

**要求**：有 UM 持仓但 `unrealized_profit` 不可解析时，不得用占位 `0` 冒充真值，须画「暂无」或 `—`；**真值 0 与缺失必须可区分**。`test_merge_missing_sentinel_values` 目前把「缺失 → `price_pnl == "0"`」锁成契约，须一并更正，不得再锁这个语义。

这与 P7 的三分类一致，也与 `PROJECT_STATE.md` 记录的 money-zero tripwire（DEC-2026-07-30-001）同一类问题：**资金列显示 0 而实际未知，是"错误的安心"。**

### R3｜被掏空的既有断言

`self-check.js:1334` 断言 `privateBody.includes('UM 持仓')`，错误信息为「私有面板未渲染 UM 持仓」—— 它原本验证的是个人账户面板中那张**独立的 UM 持仓子表**。该子表已被本次交付删除（验收标准 10 要求如此），断言之所以仍绿，是因为新合并表标题含「（UM 持仓为骨架）」（`index.html:4529`）恰好命中子串。

**断言还在跑，但已不再验证它原本要验证的东西。** 请改为验证有意义的对象（新合并表确实渲染出来了），或按新结构重写。**不得直接删除**。

### R4｜补渲染断言，证明 R1/R2 真的生效

在 `self-check.js` 增加：

- `account.verified === false` 时：未就绪横幅/文案出现，且**本地 coin 行仍在**（这是 R1 的验收证据）
- 有 UM 但 `unrealized_profit` 缺失时：未实现盈亏渲染为「暂无」而非 `0.00`（R2 的证据）

**没有这两条断言，R1/R2 就只能再次靠自述采信。** 本轮不接受这种验收方式。

## Allowed Files

沿用 `hedge-merged-positions-v1.dispatch.md` 的 Allowed Files，不扩大：

- `backend/app/server.py`、`backend/hedge_open_tasks/{service.py, store.py, domain.py}`
- `backend/tests/{test_hedge_store.py, test_hedge_service.py, test_hedge_api.py, test_positions_merge.py, test_hedge_review2_regressions.py}`
- `frontend/index.html`、`frontend/self-check.js`

修改产物（就地更新，按勘误规则附日期说明改了什么、为什么）：

- `reports/agent-runs/2026-07-31-hedge-task-lifecycle-v1/21-merged-positions-implementation.md`
- `reports/agent-runs/2026-07-31-hedge-task-lifecycle-v1/61-merged-positions-test-output.txt`（覆盖为本轮**原始**输出）

**不得改动**：`private_client.py`、`hedge_preflight_provider.py` 白名单、`scheduler.py`、`domain.py` 的暂停原因集与 51169 文案区（`:1315-1324`）、`status.json` 的 `current_task.state` 以外任何字段。

**不得触碰 Task 2 / Task 3 的范围**（暂停与删除逻辑、worker 退避、重查间隔）。

**不得改动已接受限制 A / B**（`22-bookkeeper-rejection-task1.md` §5）：单腿敞口判据、`spot_balance` / `drift` 的资金池来源。Human 已明确本轮不修，待其结合真实场景另行设计。**即使你现在知道怎么改，也不要改** —— 那是范围外。

## Inputs

| 文件 | 读什么 |
|---|---|
| 本 dispatch | 全部 |
| `41-review-1-grok-task1.md` | **§1 Bookkeeper 复验、§2 修复范围裁定、§3 评审原文（F1/F2/R1/R2 详情）** |
| `22-bookkeeper-rejection-task1.md` | §5 —— 已接受限制 A/B 的边界，确认不要碰 |
| `10-design.md` | N2 / N4 / N5 / P7 |
| `12-development-breakdown.md` | `## Task 1` 验收标准 7 与 9 |
| `agents/skills/minimal-change-engineer.md` | 全部 |
| `agents/developer-discipline.md` | 全部 |

关键锚点（Bookkeeper 已在 `969c455` 上复核）：`index.html:2739-2742` / `:2746-2757` / `:3809-3811` / `:4467-4470` / `:4495-4497` / `:4529`、`self-check.js:1334`、`domain._merge_build_row` 的 upnl 覆盖分支。

## Acceptance Checks

每项按 `AGENTS.md` §7 标注 `pass` / `fail` / `contested`；`检查结果` 最多八项，合并同类，详细说明放实现报告。

1. **R1 已修**：`verified !== true` 与 `pa` 缺失两条路径下，合并表均渲染、本地行可见、未就绪横幅出现；`loadHedgePositions` 的重绘条件已同步修正。
2. **R2 已修**：有 UM 但 `unrealized_profit` 缺失时渲染「暂无」/`—`；真值 0 与缺失可区分；`test_merge_missing_sentinel_values` 已更正，不再锁「缺失 → 0」。
3. **R3 已修**：`self-check.js:1334` 的断言重新验证有意义的对象，未被删除。
4. **R4 已补**：两条渲染断言存在且能失败（即：故意破坏对应逻辑时断言会红），在实现报告中说明你是如何确认它们不是空断言的。
5. **未回退**：后端全套测试与 `node frontend/self-check.js` 均绿；禁改区未触碰；D15、`merge_positions` 纯度、`_POSITION_KEYS` 精确集断言形式保持。
6. **未越界**：限制 A/B 未被改动；未进入 Task 2/3 范围；未纳入被 Human 推后的建议项（混合桶均价单测、HTTP 级 N2 断言、强平价 title、注释更正）。
7. **最小改动**：只改必需之处，不顺手重构相邻代码；逐处说明改动理由。
8. **原始测试输出**：`61-` 覆盖为本轮原始输出，不得改写为叙述性总结。

## Stop

- 完成后按 `AGENTS.md` §7 输出 `[TASK_RESULT v2]`，把 `current_task.state` 由 `dispatched` 改为 `reported`（唯一授权改动的 `status.json` 字段），然后**停止**。
- 不得设置 `next`、不得自行判定验收、不得合并、不得推送。
- 不得接触凭证或实盘路径；不得启动、调用、转交或冒充任何其他模型会话（§3 #2）。
- 若认为某条修复要求不成立：**不要沉默照改**，按 `AGENTS.md` §7 标 `contested` 并给出被质疑项的原文名称、质疑理由、替代证据（可执行命令或已提交路径）。Bookkeeper 会显式裁定；质疑成立则按勘误更正，不消耗返工预算。

# Dispatch —— fix-merged-positions-mismatch-labels-v1（Task 1 修复轮 2/3）

```text
Identity:
  task_id:         fix-merged-positions-mismatch-labels-v1
  target_role:     Implementer
  target_model:    claude_glm
  provider:        zhipu_glm
  status_revision: 15
  required_skill:  agents/skills/minimal-change-engineer.md
```

## Goal

修复 review-2（`codex`）的 `in-range` 阻塞发现 **F3**：合并表没有把「对不上」的两类行标清楚，且无任务记录的行把不存在的成本显示成 `0`。

**完整评审正文与 Bookkeeper 复验见 `43-review-2-codex-task1.md`（原文逐字留档于 §5），本 dispatch 不重述。**

- 这是本交付物的**第 2 轮返工**，`rework_count` 由 `1` 递增为 **`2`**（上限 3，**仅剩 1 次**）。
- review-2 的发布就绪结论是**当前不可合并**。
- 按 `minimal-change-engineer.md`：只改发现及其测试所必需之处，不顺手重构相邻代码。

## F3 是什么（三条已核实的事实）

1. **`no_task` 行的成本被填成 `"0"`**：`domain.py:1403-1421` `_merge_empty_bucket_row` 把 `spot_avg` / `perp_avg` / `position_qty` 等一律填 `"0"`。
2. **前端无条件把它渲染成数字**：`index.html:4529-4530` 直接 `formatHedgeDecimal(p.spot_avg)`，没有缺失分支。于是「交易所有仓、但本地没有任何任务记录」的行显示成「现货均价 0 / 合约均价 0」——**读起来是"我在 0 价成交的"，不是"没有记录"**。
3. **两类错配都没有标识**：`index.html:4511-4516` 的 `markers` 只有 `单腿敞口` / `本地记录与实际不一致` / `含已删除任务记录` 三种；「无任务记录」与「交易所无持仓」这两类文案**在 `index.html` 中根本不存在**。

### 为什么这条阻塞

**D7 是 Human 的明确决策：「对不上时，都显示、标清楚」。** 当前做到了"都显示"，没做到"标清楚"。

而且这是一处**未披露的形状偏离**：fake 交付 `63f5007` 的合并表**有一整列「状态」**（表头见 `index.html:4750-4752`，文案由 `fkRowStatus`（`:4698-4710`）给出四种：`正常` / `无任务记录（手工单/卡已删）` / `交易所无持仓（可能已强平/手工平）` / `单腿敞口：现货腿已成交，合约腿无持仓`）。真实实现把整列删了，而 `10-design.md` §5 明文声称「**展示形状（列 / 六场景视觉 / 三分类）不变**」「**未列即一致**」，其五条差异清单里没有这一条。

## 要做的四项

### G1｜每行给出明确的匹配状态，两类错配须有真实文案

对齐 fake `fkRowStatus` 的**语义**（措辞可以优化，但四种情形都要能分辨）：两侧都有 → 正常；有 UM 无任务记录 → 「无任务记录」（手工单或卡已删）；有任务记录无 UM → 「交易所无持仓」（可能已强平或手工平掉）；单腿敞口维持现有标记。

### G2｜`no_task` 行不得把不存在的成本显示为 0

该行的本地记账列（`spot_avg` / `perp_avg` / 开单价差率，以及任何由它们派生的展示）须渲染「暂无」或 `—`，**不得显示 `0`**。与 P7 的三分类一致，也与上一轮 F2 的处置一致：**未知不得冒充数值**。

### G3｜补两类错配的渲染断言

与既有 R1/R2 断言同标准：**必须能失败**。请在实现报告中说明你是如何确认它们不是空断言的（例如故意去掉标记后断言变红）。Bookkeeper 会独立复验。

### G4｜不得回退

后端全套测试与 `node frontend/self-check.js` 全绿；D15、N2 降级、`_POSITION_KEYS` 精确集断言形式、`merge_positions` 纯度、禁改区、上两轮已修的 F1/F2 —— 全部保持。

## 同根因穷举（§8 同根因刹车，必做）

本交付已连续两轮 `REWORK`，两轮**同属一类根因**：**展示层没有如实告知用户**（降级路径整表不显示 → 缺失盈亏画 0 → 错配行不标注且假成本显示为 0）。

按 `AGENTS.md` §8：连续两轮 `REWORK` 归因同一根因时，下一个修复任务**必须是一次穷举扫描**，枚举该缺陷家族在受审范围内的全部站点。

**因此本轮必须在实现报告中给出一张表：合并表的每一列 × 六个场景（normal / no_task / no_um / single_leg / missing / empty），逐格写明该列在该场景下显示什么**（真值 / 「暂无」/ `—` / 标记文案），并指出哪些格子是本轮改动的。**目的是一次扫完，不要再出现第三类"看起来像真数字的假数字"。**

清单外若还有派生展示（合计行、徽标、title 提示等）一并列入。

## Allowed Files

沿用既有边界，不扩大：

- `backend/app/server.py`、`backend/hedge_open_tasks/{service.py, store.py, domain.py}`
- `backend/tests/{test_hedge_store.py, test_hedge_service.py, test_hedge_api.py, test_positions_merge.py, test_hedge_review2_regressions.py}`
- `frontend/index.html`、`frontend/self-check.js`

修改产物（就地更新，附日期说明）：`21-merged-positions-implementation.md`、`61-merged-positions-test-output.txt`（覆盖为本轮**原始**输出）。

**不得改动**：`private_client.py`、`hedge_preflight_provider.py` 白名单、`scheduler.py`、`domain.py` 的暂停原因集与 51169 文案区（`:1315-1324`）、`status.json` 的 `current_task.state` 以外任何字段。

**不得触碰**：Task 2 / Task 3 的范围；**已接受限制 A / B**（`22-` §5 —— 单腿敞口判据、`spot_balance` / `drift` 的资金池来源）；Human 推后的建议项与 review-1 观察 C-1~C-4（`42-` §2）。

## 评审路由：你的实现方式决定下一步走哪条（请在回执中声明）

按 `AGENTS.md` §8：窄范围的 review-2 发现，修复后**直接回 review-2**；但若修复**扩大文件、改变契约或增加风险**，须**先重过 review-1**。

- **若你只在既有键内改值**（例如 `no_task` 行的 `spot_avg` 由 `"0"` 改为 `null`）+ 前端渲染与断言 → 直接回 **review-2（codex）**。
- **若你新增接口键**（例如给每行加 `match_status`）→ 属契约扩展，须先回 **review-1（grok）**，再回 review-2。

**Bookkeeper 倾向新增显式字段**：后端本来就同时知道 UM 侧与任务侧是否存在，显式字段比前端靠"全零"反推稳妥 —— 而靠全零反推正是本 stage 反复出问题的那类歧义。但由你选择，**在回执中明确声明你选了哪条**，Bookkeeper 据此路由。评审轮次不消耗 `rework_count`，只消耗时间。

## Inputs

| 文件 | 读什么 |
|---|---|
| 本 dispatch | 全部 |
| `43-review-2-codex-task1.md` | §1 Bookkeeper 复验、§2 修复范围与路由、§5 评审原文 |
| `22-bookkeeper-rejection-task1.md` | §5 —— 限制 A/B 边界，确认不要碰 |
| `42-review-1-grok-task1-r2.md` | §2 —— 推后项清单，确认不要纳入 |
| `10-design.md` | P7 占位零三分类、§5 与 fake 的差异清单（**须同步补上本次的形状差异**） |
| `agents/skills/minimal-change-engineer.md` / `agents/developer-discipline.md` | 全部 |

关键锚点（Bookkeeper 已在 `6d6aa7b` 上复核）：`domain.py:1403-1421`、`index.html:4511-4516` / `:4529-4530`、fake 参照 `index.html:4698-4710` / `:4750-4752`。

## Acceptance Checks

每项按 `AGENTS.md` §7 标注 `pass` / `fail` / `contested`；`检查结果` 最多八项，合并同类。

1. **G1 已做**：两类错配在真实表上有明确、可读的状态标识；四种情形可分辨。
2. **G2 已做**：`no_task` 行的本地记账列不再显示 `0`，渲染「暂无」/`—`；派生的价差率等一并处理。
3. **G3 已补**：两类错配的渲染断言存在且**能失败**，报告说明确认方式。
4. **同根因穷举已完成**：报告含「每列 × 六场景」的显示口径表，标出本轮改动的格子。
5. **未回退**：后端全套测试与前端自检全绿；D15 / N2 / 精确键集形式 / `merge_positions` 纯度 / 禁改区 / 已修的 F1 F2 保持。
6. **未越界**：限制 A/B、Task 2/3 范围、推后项均未触碰。
7. **路由已声明**：明确说明本次修复是"既有键内改值"还是"新增接口键"，以便 Bookkeeper 决定回 review-2 还是先补 review-1。
8. **§5 差异清单已同步**：把本次恢复/新增的状态标识写入 `10-design.md` §5，使"未列即一致"重新成立。

## Stop

- 完成后按 `AGENTS.md` §7 输出 `[TASK_RESULT v2]`，把 `current_task.state` 由 `dispatched` 改为 `reported`（唯一授权改动的 `status.json` 字段），然后**停止**。
- 不得设置 `next`、不得自行判定验收、不得合并、不得推送。
- 不得接触凭证或实盘路径；不得启动、调用、转交或冒充任何其他模型会话（§3 #2）。
- 若认为某条修复要求不成立：**不要沉默照改**，按 §7 标 `contested` 并给出被质疑项原文名称、质疑理由、替代证据。Bookkeeper 会显式裁定；质疑成立则按勘误更正，不消耗返工预算。
- **返工预算提醒**：本轮之后 `rework_count = 2 / 3`。若再出一轮 `REWORK`，Human 须在"缩小范围 / 重新设计 / 接受为已知限制 / 停止"中四选一。请把这一轮做扎实，尤其是同根因穷举那一项。

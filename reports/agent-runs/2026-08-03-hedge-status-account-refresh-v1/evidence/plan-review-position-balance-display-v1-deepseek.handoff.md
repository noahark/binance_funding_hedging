# Task Handoff: plan-review-position-balance-display-v1-deepseek

## Source Report (author-only; immutable after task end)

- task_id: `plan-review-position-balance-display-v1-deepseek`
- role: `Reviewer`（独立计划评审；verdict 返回 Planner，不触碰 `rework_count`）
- target model: `deepseek`（provider `deepseek`）
- stage_id: `2026-08-03-hedge-status-account-refresh-v1`
- created_at: `2026-08-03 20:25:48 CST`
- base_sha: `990570b7b44b1d4a045627aecd8f9cca0f1c8f5b`
- delivery_sha: `none`（计划评审无交付提交）

### 评审对象与方式

只读审查 v4.1 页面验收后增补 `docs/planning/hedge-status-account-refresh-v4.md` §9（2026-08-03 追加的展示扩展）：§9.1 抵押额度徽标迁移、§9.2 对冲持仓双账户余额四字段、§9.3 时间文字位置、§9.4 契约/测试/非目标、§9.5 验收标准。对照 `backend/hedge_open_tasks/domain.py`（`merge_positions`/`_merge_build_row`/`_merge_num`/`fmt_decimal`/`_merge_base_asset`）、`backend/domain/snapshot.py`（`assemble_private_account` 的 `balances_unified`/`balances_spot` 结构、`_usdt_value_optional`/`_quantize_rate`）、`backend/app/server.py`（`_hedge_open_positions`）、既有测试 `test_positions_merge.py`/`test_hedge_api.py`、`frontend/index.html`（徽标/时间/现货余额列现状）、`frontend/self-check.js` 与前端 handoff。全程只读，未改任何文件。

### 评审结论

**评审结论: ACCEPT**

§9 增补是最小且可验证的展示扩展：四个新增字段的真源全部存在于已发布的同一份 `private_account`，类型与 null/真零语义吻合；后端投影仍在纯函数 `merge_positions` 内、`GET /api/hedge-open-positions` 保持零上游 I/O；前端改动为 DOM 位置迁移与一列两行渲染，无新机制；测试可离线全覆盖。无设计矛盾、无错误真源、无不可验证风险。5 项实现注意点（非阻塞，见下）。

### 逐项核验（对照 dispatch Acceptance Checks）

1. **真源/类型/null-真零（AC1）— pass**。逐字段核对 snapshot 输出结构：
   - `unified_balance` ← `balances_unified[asset].total_balance`（`assemble_private_account` 中为 `totalWalletBalance` 原始字符串 | None），是统一账户全仓余额，**不是** `cross_margin_borrowed`（后者独立保留在「全仓借款」列，且 `borrowed_by_asset` 映射与余额映射分离）。
   - `unified_balance_value_usdt` ← 同一 `balances_unified` row 的 `value_usdt`（`_quantize_rate(_usdt_value_optional(asset, totalWalletBalance, price_map))`，8 位定点字符串 | None）。
   - `spot_balance_value_usdt` ← `balances_spot[asset].value_usdt`（同一 row，free+locked 估值）。
   - `spot_balance`（既有）＝ `free + locked`，真源不变。
   - null/真零：`_usdt_value_optional` 对缺失 amount/无价返回 `None`（UI 显示 `—`/`≈ — U`），对有效零返回 `Decimal(0)` → `_quantize_rate` → `"0.00000000"`（字符串，绝不把未知伪造成 0）；asset 不在某侧列表中 → 该侧 amount/value 均 null。语义与 §9.2 表格完全一致。
2. **后端投影与零上游（AC2）— pass**。`merge_positions` 已是纯函数（无 service 引用、无 I/O，`test_merge_rows_are_json_serializable` 保证 JSON 边界）；`_hedge_open_positions` 的 `private_account` 来自 `self.service.get_snapshot()`（published snapshot），`positions` 来自本地 task 聚合；四字段投影不改 snapshot cache、不改 60 秒节奏、不触碰 cache refresh/订单/借贷/闸门。`test_full_scenario_makes_zero_urllib_calls` 既有零 urllib 断言继续成立。§9.2 明确"不加读取、不改 snapshot cache、不改变 zero-upstream GET 性质"。
3. **UI 唯一位置与边界（AC3）— pass**。现状核对：抵押额度徽标 `renderCollateralCapBadge(row)` 现渲染于市场表币种单元格（`frontend/index.html` 2637 行，注释「highlight on the symbol cell only; never the 借贷状态 / 资产 column」），§9.1 将其移至同一行「借贷状态 / 资产」单元格（2648 行），语义（`collateral_cap` + `ui_flags` 判定、颜色/title/排序/过滤/按钮零影响）不变、不新增第二个徽标；`#account-asset-updated-at` 现位于 `refresh-meta`（badge-row 内），§9.3 移至 topbar 标题下替换固定副标题「行情公开 · 账户需 key 私有只读」，回退逻辑（`checked_at` → `valuation.priced_at`）与唯一 id 不变，右侧仅留倒计时/手动刷新/更新缓存；PM 时间行从 `privatePanelBody` 的 overview 上方移至「私有账户」标题正下方，capability 隐藏/未就绪/有时间的 PM 三态与北京时间渲染语义不变（`pmCapabilityPresent` 判定在 `renderPrivatePanel` 内已有 `pa` 变量，可实现）。隐私遮蔽、缺失降级、无自动刷新边界均保留。
4. **测试可覆盖（AC4）— pass**。`test_positions_merge.py` 已有 normal/no_task/no_um/未就绪全 null/1000x/JSON 序列化等 14 例，可加：正常同币四字段值、单侧缺失、账户未就绪全 null、真零不变成 null；`test_hedge_api.py` 的 `test_positions_shape_after_fill` 可扩展 HTTP positions exact keyset 断言（新增四 key 属预期内 keyset 变化），`test_full_scenario_makes_zero_urllib_calls` 继续保证零上游；前端 `self-check.js` 可加双行渲染、两侧独立缺失、估值 `—`、隐私遮蔽、徽标位置、两处时间 DOM、PM 三态回归。全部离线，无需真实服务/网络。
5. **边界与机制克制（AC5）— pass**。无 429/上游 I/O/自动刷新/SSE/WebSocket/交易副作用引入；§9.4 明确不聚合多账户余额、不变更 1000x 不自动对齐规则（`_merge_base_asset` 保留）、不新增 API。未发现需要猜测性机制的假设性场景。

### 发现（均为实现注意点，非阻塞，不消耗 rework_count）

- **注意 1（计划内）**：`frontend/index.html` 2633 行注释「never the 借贷状态 / 资产 column」在 §9.1 实施后语义反转，实现时必须同步更新该注释，避免注释与行为矛盾。
- **注意 2（计划内）**：`merge_positions` 的 `spot_by_asset`/`borrowed_by_asset` 结构需扩展以携带 `value_usdt`（建议并行 dict 或改存 row 引用）；实现时须保持 `spot_balance`（free+locked 数量）既有语义不变，防止回归。
- **注意 3（计划内）**：`test_hedge_api.py` 既有 positions keyset 断言（如 `test_positions_shape_after_fill`）需随四新字段同步更新；§9.4 已要求 exact key set 覆盖，属预期内改动。
- **注意 4（计划内）**：`#account-asset-updated-at` 移出 `refresh-meta` 后，`refresh-meta` 容器可能不再需要；self-check 中该 id 相关断言需跟随 DOM 移动更新。
- **注意 5（语义确认，非问题）**：`unified_balance` 为 `totalWalletBalance`（含杠杆的全仓余额）而非净值；§9.2 表格已明示「全仓（杠杆）余额」，与 `cross_margin_borrowed` 借款列并行展示，语义区分清晰，前端「杠杆」标签即此意。

### 未完成事项

无阻塞。本计划评审不授权实现、部署或实盘操作；verdict 返回 Planner（Codex/OpenAI）按 §8「计划评审」流程处理。

### 命令与结果（离线，只读）

- `git rev-parse --verify 990570b7b44b1d4a045627aecd8f9cca0f1c8f5b` → 存在（计划评审固定 base_sha）。
- 代码核对（只读）：`backend/hedge_open_tasks/domain.py` `merge_positions`（1705 行起）、`_merge_build_row`（1628 行起）、`_merge_num`/`fmt_decimal`/`_merge_base_asset`；`backend/domain/snapshot.py` `balances_unified`/`balances_spot` 构造（1275–1315 行）、`_usdt_value_optional`、`_quantize_rate`；`backend/app/server.py` `_hedge_open_positions`（679–694 行）；`frontend/index.html` 徽标（2631–2637 行）、副标题（1098 行）、现货余额列（4897 行）、持仓时间行（4909–4924 行）。
- 未运行服务、未访问网络、未读凭证、未改任何文件。

### 仓库内证据路径

- 受审计划：`docs/planning/hedge-status-account-refresh-v4.md` §9（§9.1–§9.5）
- 相关代码：`backend/hedge_open_tasks/domain.py`、`backend/app/server.py`、`backend/domain/snapshot.py`、`frontend/index.html`、`frontend/self-check.js`
- 既有测试：`backend/tests/test_positions_merge.py`、`backend/tests/test_hedge_api.py`
- 接口上下文：`docs/api/public-market-contract.md`（v0.10）
- 本交接件：`reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/plan-review-position-balance-display-v1-deepseek.handoff.md`

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/plan-review-position-balance-display-v1-deepseek.handoff.md`（本件，计划评审 ACCEPT）
  2. `docs/planning/hedge-status-account-refresh-v4.md`（§9 增补）
  3. `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/status.json`
- 执行：Planner/Bookkeeper 依本 ACCEPT 将 v4.1 §9 增补定稿为可派发任务（后端字段投影 + 前端两行/徽标/时间迁移），实施时纳入上述 5 项注意点；按 §8 计划评审不触碰 `rework_count`。
- 关卡：实现 dispatch 由 Bookkeeper 准备、Human 启动；实现后进入既有 review-1/review-2 流程；本阶段不授权部署或实盘操作。
- 不能假设的事实：本计划评审未做任何实现、测试运行、网络或实盘操作；`delivery_sha` 为 `none`；§9 未改变 §1–§8 的 refresh cycle、source 时间语义、GET pure-read、无自动刷新与资金/闸门边界。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

```text
[TASK_RESULT v2]
任务 ID: plan-review-position-balance-display-v1-deepseek
执行结果: completed（完成）
结果摘要: 独立计划评审 v4.1 §9 展示增补：四个新字段真源（total_balance/value_usdt）全部存在于已发布 private_account，类型与 null/真零语义吻合；merge_positions 纯函数零上游；前端为 DOM 迁移与两行渲染无新机制；测试可离线全覆盖。评审结论 ACCEPT，5 项实现注意点非阻塞，无设计矛盾/错误真源/不可验证风险。
产物: [reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/plan-review-position-balance-display-v1-deepseek.handoff.md]
检查结果: [pass 四字段真源/类型/null-真零语义与 snapshot 结构逐项吻合；cross_margin_borrowed 仍独立借款列, pass 投影在纯函数 merge_positions 内、GET 零上游 I/O、不改 cache refresh/60s/订单/借贷/闸门, pass 徽标/聚合时间/PM 时间迁移唯一位置明确；隐私/缺失/PM 三态/无自动刷新边界保留, pass 测试可覆盖四字段值/单侧缺失/全 null/真零/HTTP exact keyset/DOM 位置/回归；离线可复现, pass 无 429/上游 I/O/自动刷新/交易副作用；仅记录 5 项实现注意点，未加猜测性机制]
阻塞项: [none]
本地北京时间: 2026-08-03 20:25:48 CST
下一步模型: codex（Bookkeeper，接收计划评审 verdict 并准备实现 dispatch）
下一步任务: 读取：reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/plan-review-position-balance-display-v1-deepseek.handoff.md、docs/planning/hedge-status-account-refresh-v4.md（§9）、reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/status.json；执行：Planner/Bookkeeper 依 ACCEPT 定稿 v4.1 §9 实现任务（后端字段投影 + 前端两行/徽标/时间迁移，纳入 5 项注意点），准备 dispatch 由 Human 启动；关卡：实现后进入既有 review-1/review-2；本阶段不授权部署或实盘操作
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- verified_at: `2026-08-03 20:29:06 CST`
- source_sha256: `44819b9eba4ec7b2ad2fcddf0949349e649d919336964e4b070fe12b97c25d76`（唯一完整 `BOOKKEEPER_APPEND_ONLY` marker 之前的原始 11762 bytes）
- status_revision_checked: `8`；task/state: `plan-review-position-balance-display-v1-deepseek` / `dispatched`。
- identity and range: handoff `base_sha=990570b7b44b1d4a045627aecd8f9cca0f1c8f5b` 经 `git rev-parse` 存在，`delivery_sha=none` 与计划评审性质一致；DeepSeek/provider `deepseek` 独立于 Planner Codex/provider `openai`。create-only handoff 在 dispatch 前已由 Bookkeeper 预检为不存在。
- closure: Source Report 与 Human Brief 都含明确 `评审结论: ACCEPT`，无 REWORK。五项记录均为计划内实现注意点或语义确认，未提出阻塞设计矛盾、错误真源或不可验证风险；计划评审按 AGENTS.md §8 不消耗 `rework_count`。
- evidence and decision: 核验的四字段真源、`merge_positions` 纯函数位置、现有 HTTP exact keyset 测试位置与 v4.1 §9 一致。计划评审未运行测试，且没有把未运行测试说成已运行；实施 packet 要求后端离线 pytest 及输出证据。
- next state: plan review verified；准备 backend-position-balance-display-v1，由 Human 启动 `claude_glm`（provider `zhipu_glm`）仅实现后端 position 投影/契约/测试。前端 Grok 任务在该交付核验后再派发；Review-2 继续延后。

## Errata (append-only)

（预留）

# Task Handoff: backend-position-balance-display-v1

## Source Report (author-only; immutable after task end)

- task_id: `backend-position-balance-display-v1`
- role: `Implementer`
- target model: `claude_glm` (provider `zhipu_glm`)
- stage_id: `2026-08-03-hedge-status-account-refresh-v1`
- created_at: `2026-08-03 20:39:37 CST`
- base_sha: `89103303bd29a64ac5915b56639f8a4a885a56b7`
- delivery_sha: `pending`（Implementer 在包含本件的唯一 delivery commit 之前创建；Bookkeeper 在 delivery commit 后用 `git rev-parse` 解析实际 SHA 写入 `status.json` 与同文件核验块，不回填本字段）

### 任务背景与实际修改范围

实现 v4.1 §9.2 的最小后端交付：在既有纯函数 `merge_positions` 生成的每个 position row 增加 `spot_balance_value_usdt`、`unified_balance`、`unified_balance_value_usdt`，并保持既有 `spot_balance` 语义。四字段只消费同一已发布 `private_account` 的标准化 `balances_spot` / `balances_unified` row；不改 snapshot schema、cache refresh、60 秒调度、PrivateClient、订单、借贷写入、Start gate、凭证或部署。只改了 dispatch Allowed Files 列出的文件。

实际改动（均在 Allowed Files 内）：

- `backend/hedge_open_tasks/domain.py`：`merge_positions` 新增 `spot_value_by_asset`（asset → 同一 spot row 的既有 `value_usdt`）与 `unified_row_by_asset`（asset → 整条 unified row，从中取 `total_balance`、`value_usdt`、`cross_margin_borrowed`），替代原 `borrowed_by_asset`；`_merge_build_row` 签名扩展为 `(coin, direction, bucket, um, spot_by_asset, spot_value_by_asset, unified_row_by_asset)`，在既有 `spot_balance`（free+locked，语义不变）之后追加 `spot_balance_value_usdt`、`unified_balance`、`unified_balance_value_usdt`，且 `cross_margin_borrowed` 改由 unified row 取得（语义不变、仍只代表借款）。两个调用点（UM 骨架行、no_um 行）均传新 map。1000x asset 不自动对齐规则（`_merge_base_asset` 不剥 1000 前缀）保持不变。
- `backend/tests/test_positions_merge.py`：新增 7 个用例（正常同币四字段精确映射、unified 缺失侧 null、spot 缺失侧 null、未就绪全 null、真零保持十进制字符串、1000x 不对齐四字段全 null、不修改源 private_account）。
- `backend/tests/test_hedge_api.py`：`_POSITION_KEYS` 同步新增 `spot_balance_value_usdt`、`unified_balance`、`unified_balance_value_usdt` 三个键（exact keyset 断言 `test_positions_shape_after_fill` 随之通过）。
- `docs/api/public-market-contract.md`：追加 v0.11「Positions Dual-Account Balance Amendment」节，记录四字段真源、null/真零语义、`cross_margin_borrowed` 仍独立、1000x 不对齐保留、GET 零上游不变、snapshot JSON schema 不变。
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/status.json`：仅把 `current_task.state` 从 `dispatched` 改为 `reported`。

### 字段事实（与 v4.1 §9.2 表格逐项一致，供核验）

- `spot_balance`（既有）＝同一 spot row 的 `free + locked`，真源不变；`fmt_decimal(Decimal)` 输出。
- `spot_balance_value_usdt`（新）＝同一 spot row 的既有 `value_usdt`，原样透传，前端不重算。
- `unified_balance`（新）＝同一 asset 的 `balances_unified.total_balance`（全仓杠杆余额），**不是** `cross_margin_borrowed`。
- `unified_balance_value_usdt`（新）＝同一 unified row 的既有 `value_usdt`，原样透传。
- `cross_margin_borrowed`：继续只代表全仓借款，独立列，不并入 `unified_balance`。
- 未就绪（`verified=false` 或 `private_account` 缺失）：四个账户派生字段全 null；一侧 asset 缺失只该侧 amount/value null；有效真 0 保持十进制字符串（`"0"`/`"0.00000000"`），绝不把未知伪造成 0。
- 纯投影：不重算价格、不修改源 `private_account`（单测 `test_merge_does_not_mutate_source_private_account` 验证输入 dict 不变）；`GET /api/hedge-open-positions` 仍仅从已发布 snapshot 与本地 task bucket 合并，零上游 I/O。

### 关键设计取舍

- **并行 map 而非改存 row 引用统一容器**：保留 `spot_by_asset`（Decimal free+locked）以维持 `spot_balance`/`drift` 既有语义与回归；新增 `spot_value_by_asset` 携带 `value_usdt`，并以 `unified_row_by_asset`（整条 row）一次取 `total_balance`/`value_usdt`/`cross_margin_borrowed`，避免三份重复 map（与 deepseek plan-review 注意点 2 一致）。
- **`_merge_build_row` 为唯一 row 构造点**：UM 骨架行、no_um 行、no_task 行均经它生成，故三个新字段自动出现在每个 merged row（满足 AC2「所有 merged row 均有四个账户字段」）。
- **未触碰前端**：双行渲染、徽标/时间迁移为前端任务（Grok），不在本后端任务范围。

### 未完成事项

无阻塞。本任务范围（后端纯函数投影 + 契约 + 离线测试）已完成并自测。前端、review-1/review-2、merge、部署、实盘操作均不在本任务授权内，留给后续。

### 命令与结果（离线，无真实 key/网络/服务）

- 编译：`python3 -m py_compile backend/hedge_open_tasks/domain.py` → OK。
- dispatch 指定命令 `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider -q backend/tests/test_positions_merge.py backend/tests/test_hedge_api.py`：**57 passed**（21 + 36），证据 `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/backend-position-balance-display-v1.pytest.txt`。
- 完整后端回归（额外确认）：**1263 passed**（1256 既有 + 7 新增，零回归）。

### 仓库内证据路径

- 新增/扩展测试：`backend/tests/test_positions_merge.py`、`backend/tests/test_hedge_api.py`
- 指定命令 pytest 输出：`reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/backend-position-balance-display-v1.pytest.txt`
- 本交接件：`reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/backend-position-balance-display-v1.handoff.md`

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/backend-position-balance-display-v1.handoff.md`（本件，author 源区块 + Human Brief）
  2. `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/status.json`
  3. `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/backend-position-balance-display-v1.dispatch.md`
  4. `docs/planning/hedge-status-account-refresh-v4.md`（§9.2 已批准设计权威）
- 执行：Bookkeeper 核验本任务（`base_sha`/`delivery_sha`、status revision、handoff 同文件 SHA-256 边界、引用证据路径与可复现命令），并按 Acceptance Checks 复跑指定离线 pytest。
- 关卡：Bookkeeper 通过则把 `current_task.state` 推进为 `verified` 并解析 `delivery_sha`；未通过则在同文件追加拒收 `Bookkeeper Verification` 块、`status.json.blockers` 写具名条目，后续修复任务递增 `rework_count`。
- 不能假设的事实：本任务未做实盘/网络/凭证/部署；前端未接入（双行/徽标/时间迁移为前端任务）；snapshot JSON schema 未改；`delivery_sha` 在本件为 `pending`，由 Bookkeeper 在 delivery commit 后解析。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

```text
[TASK_RESULT v2]
任务 ID: backend-position-balance-display-v1
执行结果: completed（完成）
结果摘要: merge_positions 每个 row 增加 spot_balance_value_usdt/unified_balance/unified_balance_value_usdt，保留 spot_balance；纯投影同份 private_account，cross_margin_borrowed 仍独立；契约 v0.11；指定 pytest 57 过，全量 1263 零回归。
产物: [backend/hedge_open_tasks/domain.py, backend/tests/test_positions_merge.py, backend/tests/test_hedge_api.py, docs/api/public-market-contract.md, reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/status.json, reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/backend-position-balance-display-v1.handoff.md, reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/backend-position-balance-display-v1.pytest.txt]
检查结果: [pass 正常同币四字段精确映射，不重算价格、不改源 snapshot，cross_margin_borrowed 语义不变, pass 所有 merged row 有四账户字段；未就绪全 null、单侧缺失只该侧 null、真零保持字符串、1000x 不自动对齐, pass /api/hedge-open-positions exact keyset 同步三新字段；GET 仍纯读零上游 I/O, pass 契约 v0.11 追加字段/真源/null-真零语义；snapshot JSON schema 未改, pass 指定离线 pytest 57 passed 并存盘；未启服务/网络/凭证/实盘]
阻塞项: [none]
本地北京时间: 2026-08-03 20:39:37 CST
下一步模型: codex（Bookkeeper，只读核验本任务）
下一步任务: 读取：reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/backend-position-balance-display-v1.handoff.md、reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/status.json、reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/backend-position-balance-display-v1.dispatch.md、docs/planning/hedge-status-account-refresh-v4.md；执行：Bookkeeper 核验 base_sha/delivery_sha、同文件 handoff SHA-256 边界、引用证据与可复现指定离线 pytest（57 passed），并把本任务推进为 verified 或拒收；关卡：Codex 核验通过后由 Human 决定是否进入跨 provider review-1（claude_glm 实现的 review-1 须用不同 provider，默认 Kimi）
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

由 Bookkeeper 核验后追加：源区块 SHA-256、核验时间、核对的 status revision、通过或拒收依据、可复现命令与后续状态。

## Errata (append-only)

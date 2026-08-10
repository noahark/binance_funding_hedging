# Task Handoff: implement-cross-margin-capital-flow-v1

## Source Report (author-only; immutable after task end)

- task_id: `implement-cross-margin-capital-flow-v1`
- role: Implementer
- target model: `claude_glm`（provider: `zhipu_glm`）
- required_skill: `agents/skills/senior-developer.md`
- stage_id: `2026-08-10-cross-margin-flow-log-v1`
- created_at: 2026-08-10 18:44:01 CST
- base_sha: `a11a8734a3da988501fa5cac5baa52dcea3ea2ef`（`git rev-parse` 一致）
- delivery_sha: `9a4e0198ee7f7d2102ab1b9550c39e79a76e24fa`（提交后实际 `git rev-parse` 值，非 pending）
- status_revision 核对: `status.json` revision=3、phase=`implement`、current_task.id=`implement-cross-margin-capital-flow-v1`、base_sha 与 `git rev-parse` 一致；Bookkeeper=`grok4.5`。
- 受审区间: `base_sha..delivery_sha` = `a11a873..9a4e019`。其中 `dacf02f`/`4658f3e`/`09ef638`/`6e9e86b` 为本阶段控制提交（dispatch/status/PROJECT_STATE/计划），属评审上下文而非受审交付；实际代码交付在 `9a4e019` 单个提交内。

### 任务背景与实际修改范围

按改写后的 `00-change-plan.md`（唯一计划权威）接入 `GET /sapi/v1/margin/capital-flow`（不传 `symbol`=全仓）全仓本地缓存，并在流水日志中栏用真数据替换 `a11a873` 基线的假数据预览。改动严格落在 dispatch Allowed Files 内，**未**触碰 `server.py`（只读输入）、`scheduler.py`（capital 挂在 service `_do_run`，scheduler 无需改）、`flow_refresh_runs` schema、既有两源 coverage 聚合公式、资产互转 POST。

实际修改文件（全部在 `9a4e019`）：

| 文件 | 改动 |
|---|---|
| `backend/services/private_client.py` | 白名单 +1（`GET /sapi/v1/margin/capital-flow`→`api.binance.com`，计数 16→17）；新增 `fetch_capital_flow_page(start_time,end_time,limit)` 单页 fetcher（raw array，无 last_error/TTL，失败抛 `PrivateEndpointError`，无 `symbol`/`fromId`）。 |
| `backend/ledger_flow/domain.py` | 新增 `normalize_capital_rows`（id/tran_id/time_ms/asset/flow_type/amount；缺任一 NOT NULL 字段丢弃）+ `dedup_capital_rows`（按 `id` 首胜；同 tranId 多 type 各异 id 全保留）。 |
| `backend/ledger_flow/store.py` | 新表 `margin_capital_flow_rows`（PK `id`，零迁移 `CREATE TABLE IF NOT EXISTS`）+ 索引；新 meta key `capital_flow_coverage_start_ms`/`_end_ms`/`_last_run`；`commit_capital_flow`（单事务幂等入库+推进 coverage+last_run，store 回填 fetched/new 计数权威值）、`query_capital_flow_rows`、`get_capital_flow_state`。**完全不读不写** `flow_refresh_runs` / `get_coverage` / 共享 `coverage_gaps`。 |
| `backend/ledger_flow/service.py` | `_do_run` 末尾独立 `_run_capital_flow`（全 try/except 隔离，capital 失败永不冒泡进利息/合约 run）；窗口首次 `[now-1d,now]`、之后 `[cov_end-3h,now]`，单页 `limit=1000` 无 fromId，满页标 `possibly_incomplete`（标志非失败，仍推进 end 到 now）；失败只写 capital 自己 last_run、不推进 end。`get_flow_log` 装配 `capital_flow` 块 + 在 `_build_coverage` 返回**之后**并入 `by_source.capital_flow`（展示用）。`trigger_refresh` 返回附加 `capital_flow` 摘要。`_build_coverage` **逐字未动**。 |
| `frontend/index.html` | 删预览徽标 + `FLOW_LOG_CAPITAL_FAKE_ROWS` + 孤立的 `.flow-log-fake-badge` CSS（本改动产生的孤儿）；`flowLogCapitalRowsFromPayload` 只读 `payload.capital_flow.rows`（缺块→空态）；`renderFlowLogCapitalCol` 真数据 + 空态 + possibly_incomplete + 保留五桶与入全仓/出全仓 + 默认筛选 20 条上限；加载态改 skeleton。 |
| `frontend/self-check.js` | base mock payload 加 `capital_flow` 块（3 行真形状）+ `by_source.capital_flow`，覆盖真数据渲染路径。 |
| `docs/api/public-market-contract.md` | Dual-Ledger 段 additive：新增「Cross-margin capital-flow source」小节 + 顶层字段/`POST refresh` body 各加 `capital_flow`；`schema_version` 仍 `private-ledger/v2`（未 bump）。 |
| 测试（5 文件） | 见下「自测命令与结果」。 |

### 关键设计决策（隔离 / P0-1）

- **P0-1 airtight**：`coverage_for_window`（`server.py:1401` 对冲净盈亏消费点）只调 `_build_coverage`，后者**逐字未改**；capital coverage 仅在 `get_flow_log` 内于 `_build_coverage` 返回后并入 `by_source.capital_flow`。故 capital 无论从未成功还是持续失败，aggregate `start_ms`/`end_ms`/`complete`/`pending_tail_ms` 与接入前逐位相同。单测 `test_capital_succeeding_does_not_shrink_coverage_aggregate` 直接复现并挡住 P0-1 回归（capital start=now-1d 若泄漏进 aggregate，5 天窗口会 complete→False）。
- **P0-2**：capital 用独立表 + 独立 meta，零迁移；`flow_refresh_runs` 不加列、不插行；`_is_success_run`/`_compute_delta`/`_format_last_run` 均不纳入 capital。
- **P0-3/P0-4**：单页 `limit=1000`、无切片、无 fromId 翻页（plan §4.1.2/§4.3），从结构上消解切片失败吞账与翻页序假设。
- **金额口径**：capital 跨 type 金额无统一口径，中栏只做按 type 计数（不做 Decimal 合计），避免与利息/合约 formal 总额混淆。

### 对 dispatch 九条 Acceptance Checks 的逐条判断

1. 白名单 + 单页 fetch；mock 测 limit=1000 边界与满页标记 → **pass**（`test_capital_flow_page_*`、`test_capital_full_page_marks_possibly_incomplete`）。
2. 新表入库幂等（同 id 不覆盖）；同 tran_id 多 type 多行保留 → **pass**（`test_capital_commit_idempotent_no_overwrite`、`test_capital_multi_type_same_tranid_all_retained`、`test_dedup_capital_rows_by_id_keeps_multi_type_same_tranid`）。
3. ledger_meta 三 key 推进；失败不推进 end → **pass**（`test_capital_coverage_and_last_run_stamped`、`test_capital_failed_pull_advances_nothing`、`test_capital_failure_isolated_and_does_not_advance_end`）。
4. flow-log JSON 含 capital_flow；缺块空态；schema_version 仍 v2 → **pass**（`test_flow_log_capital_block_shape_and_schema_not_bumped`、`test_flow_log_capital_empty_state_when_never_pulled`、`test_get_flow_log_200_includes_capital_flow_block`）。
5. 既有 ledger_flow 测试 + 对冲 stats 依赖 coverage 路径不因 capital 失败/空变「暂无」 → **pass**（`test_capital_never_succeeded_leaves_coverage_for_window_untouched` + 全量 1717 passed 含既有 coverage_for_window / sum_* 用例）。
6. 前端去预览徽标与 FAKE_ROWS、真数据渲染、五桶与入全仓/出全仓保留、self-check 全绿 → **pass**（grep 确认 `FAKE_ROWS`/`fake-badge`/`'fake'` 零残留；self-check 全绿）。
7. 文档 private-ledger additive 更新 → **pass**（`docs/api/public-market-contract.md` 新增小节 + 两处 additive）。
8. 创建唯一 handoff，顺序 实现→自测→提交→写 handoff，`delivery_sha` 为实际 `git rev-parse`=`9a4e019`（非 pending） → **pass**。
9. 自测三条命令原始输出（见下） → **pass**。

### 自测命令与结果（原始输出）

```text
$ .venv/bin/python -m pytest backend/tests/test_ledger_flow_domain.py backend/tests/test_ledger_flow_store.py backend/tests/test_ledger_flow_service.py backend/tests/test_ledger_flow_scheduler.py backend/tests/test_ledger_flow_api.py backend/tests/test_private_client.py -q
................. [46%] ............ [92%] ..... [100%]
156 passed in 6.94s

$ .venv/bin/python -m pytest backend/tests/ -q
............ [83%] ... [100%]
1717 passed in 142.50s

$ node frontend/self-check.js
（末行）全部自检通过
```

注：既有 empty-state 用例（`test_get_flow_log_empty_state_shape` api/service 两处）的 `by_source` 断言随 additive 更新为含 `capital_flow: None`；这是 plan §4.1.5「`by_source.capital_flow` 展示键」的直接后果，非既有行为变更——aggregate 字段不变。

### 未完成事项

- 无。本轮不启动 review、不 merge、不 push、不部署、不重启服务、不实盘写（dispatch Stop）。
- 待办（非本轮）：HIGH_RISK 需 review-1 + review-2（跨 provider 只读）；首次实盘拉取的权重占用与满页概率需运行时日志确认（本账户 7d≈149 行，1d+3h 窗口满 1000 概率极低）。

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/evidence/implement-cross-margin-capital-flow-v1.handoff.md`（本文件）
  2. `reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/00-change-plan.md`（冻结条款权威，§4.1/§4.2/§9）
  3. `backend/ledger_flow/service.py`（`_run_capital_flow`/`get_flow_log`/`_build_coverage` 三处）
  4. `backend/ledger_flow/store.py`（`commit_capital_flow`/`get_capital_flow_state`）
  5. `backend/services/private_client.py`（白名单 + `fetch_capital_flow_page`）
  6. `frontend/index.html`（`renderFlowLogCapitalCol`）
- 执行：Bookkeeper 核验本 handoff、解析 `delivery_sha=9a4e019` 写入 `status.json` 并封存 `base_sha..delivery_sha`；随后由 Human 启动 review-1（跨 provider 只读）。
- 关卡：HIGH_RISK（账务含义 / 资金流水展示）→ review-1 + review-2。
- 不能假设的事实：
  - 不能假设 `CREATE TABLE IF NOT EXISTS` 会给现网已存在的 `flow_refresh_runs`（130 行）补列——本实现零迁移，capital 不碰该表。
  - 不能假设 capital 进入 coverage aggregate——它只在 `get_flow_log` 内聚合后并入 `by_source` 展示键；`coverage_for_window` 逐位不变。
  - 不能假设 capital-flow 翻页返回按 id 升序（recon §3.6 未证明）——本实现单页、不翻页，从结构上回避。
  - 不能假设中栏是「所有互转全集」——capital-flow 站在全仓钱包视角（plan §8）；不经全仓的 MAIN↔UM/CM 直转不出现。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

```text
[TASK_RESULT v2]
任务 ID: implement-cross-margin-capital-flow-v1
执行结果: completed（完成）
结果摘要: 全仓 capital-flow 接入完成：白名单+单页 fetcher；新表+独立 ledger_meta 三 key；service 独立 try 拉取入库，flow-log 装配 capital_flow 块+by_source（展示用）。硬隔离：不写 flow_refresh_runs、不进 coverage aggregate/delta/last_run，coverage_for_window 逐位不变(P0-1)。前端假数据换真数据，保留五桶与入/出全仓。schema_version 未 bump。测试全绿。
产物: [reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/evidence/implement-cross-margin-capital-flow-v1.handoff.md, backend/services/private_client.py, backend/ledger_flow/domain.py, backend/ledger_flow/store.py, backend/ledger_flow/service.py, frontend/index.html, frontend/self-check.js, docs/api/public-market-contract.md, backend/tests/test_private_client.py, backend/tests/test_ledger_flow_domain.py, backend/tests/test_ledger_flow_store.py, backend/tests/test_ledger_flow_service.py, backend/tests/test_ledger_flow_api.py]
检查结果: [白名单+单页 fetcher、满 1000 标记=pass；新表幂等(同 id 不覆盖)+同 tran_id 多 type 多行保留=pass；ledger_meta 三 key 推进、失败不推进 end 且不影响利息/合约 run=pass；coverage_for_window 逐位不变(P0-1)=pass；flow-log 含 capital_flow 块、缺块空态、schema_version 仍 v2=pass；前端去预览徽标与 FAKE_ROWS、真数据渲染、五桶与入/出全仓保留=pass；文档 private-ledger additive(v2 不 bump)=pass；自测全绿(六文件156/全量1717/self-check)+唯一 handoff 创建 delivery_sha=9a4e019 实际 git rev-parse=pass]
阻塞项: [none]
本地北京时间: 2026-08-10 18:44:01 CST
下一步模型: grok4.5（本阶段 Bookkeeper，status.json.bookkeeper=grok4.5，由 Human 启动其终端）
下一步任务: 读取：reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/evidence/implement-cross-margin-capital-flow-v1.handoff.md；reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/00-change-plan.md；backend/ledger_flow/service.py；backend/ledger_flow/store.py；执行：Bookkeeper 核验本 handoff、解析 delivery_sha=9a4e0198ee7f7d2102ab1b9550c39e79a76e24fa 写入 status.json 并封存 base_sha..delivery_sha；关卡：HIGH_RISK，由 Human 启动 review-1（跨 provider 只读），通过后 review-2，再由 Human 决定合并/部署。
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- bookkeeper: `grok4.5`
- verified_at: 2026-08-10 18:52:18 CST
- status_revision_at_verify: 3（implement / `implement-cross-margin-capital-flow-v1` / dispatched）
- source_payload_sha256: `db91054d3c500e474b5ef821db7046e7170c3a6d5e6e739c078e8ea4d2416bc2`（marker 前全部字节）
- delivery_sha 解析：`9a4e0198ee7f7d2102ab1b9550c39e79a76e24fa` = `git rev-parse` 一致；`git merge-base --is-ancestor a11a873… 9a4e019…` → ancestor_ok
- 受审区间：`a11a873..9a4e019`；交付代码单提交 `9a4e019`（`git show --name-only` 仅 backend/frontend/docs/tests，无越界改 `server.py`/`scheduler.py`）
- 独立复跑（Bookkeeper）：
  - `.venv/bin/python -m pytest backend/tests/test_ledger_flow_domain.py backend/tests/test_ledger_flow_store.py backend/tests/test_ledger_flow_service.py backend/tests/test_ledger_flow_scheduler.py backend/tests/test_ledger_flow_api.py backend/tests/test_private_client.py -q` → **156 passed in 6.73s**
- 隔离抽查：`rg` 确认 capital 不写 `flow_refresh_runs`；`_build_coverage` 仍只吃两源；`get_flow_log` 在聚合后并入 `by_source.capital_flow`；`coverage_for_window` 仍只调 `_build_coverage`；前端无 `FAKE_ROWS`/`fake-badge`；store `schema_version=private-ledger/v2`
- Allowed Files：实现 diff 文件集合 ⊆ dispatch 可写清单；`server.py` 未改
- 裁定：**核验通过** → 任务 `implement-cross-margin-capital-flow-v1` 封存为 verified；`status.json` 写入 `delivery_sha`；准备 review-1（跨 provider，首选 kimi/moonshot）
- 后续：Human 启动 review-1 只读会话；review 锚点固定 `base_sha..delivery_sha` = `a11a873..9a4e019`

## Errata (append-only)

（无。）

# Task Handoff: review-1-cross-margin-capital-flow-v1

## Source Report (author-only; immutable after task end)

- task_id: `review-1-cross-margin-capital-flow-v1`
- role: Reviewer（review-1，代码/契约/测试/接缝，只读）
- target model: `kimi`（provider: `moonshot`）
- required_skill: `agents/skills/code-reviewer.md`
- stage_id: `2026-08-10-cross-margin-flow-log-v1`
- created_at: 2026-08-10 19:22:55 CST
- base_sha: `a11a8734a3da988501fa5cac5baa52dcea3ea2ef`（`git rev-parse` 一致）
- delivery_sha: `9a4e0198ee7f7d2102ab1b9550c39e79a76e24fa`（已封存值，非 pending；`git merge-base --is-ancestor` 通过）
- status_revision 核对: `status.json` revision=4、phase=`review_1`、current_task.id 与 dispatch 一致、base_sha/delivery_sha 与 `git rev-parse` 一致；Bookkeeper=`grok4.5`。
- provider 隔离：实现 `claude_glm`（zhipu_glm），本评审 kimi（moonshot），跨 provider 成立；Bookkeeper grok4.5 未兼任本评审。

### 评审结论

**ACCEPT。**

无 `REWORK` 发现，无 `pre-existing-*` 事项需要分类。全部核对锚定固定区间
`a11a873..9a4e019` 的原始 diff、当前源码行号与独立复跑的测试输出，未使用
`AGENTS.md` §1 假设场景通道。

### 只读评审范围与实际执行的检查

只读读取：`AGENTS.md`、dispatch、ACTIVE.json、PROJECT_STATE.md、status.json、
`agents/roles.md`（Shared Rules / Task Handoff Evidence Contract / Reviewer）、
`agents/skills/code-reviewer.md`、`00-change-plan.md`（§4.1/§4.2/§9 冻结条款）、
实现 handoff（含 Bookkeeper 核验块）、plan-review handoff；固定 diff
`git diff a11a873..9a4e019` 与 `git show 9a4e019 --stat`；当前源码
`backend/ledger_flow/{service,store,domain}.py`、`backend/services/private_client.py`、
`frontend/index.html`、`frontend/self-check.js`、`docs/api/public-market-contract.md`。

执行的只读命令与结果：

```text
$ git rev-parse a11a873… 9a4e019… → 两值与 status.json 一致；merge-base --is-ancestor → OK
$ git log --oneline a11a873..9a4e019 → dacf02f/4658f3e/09ef638/6e9e86b 为阶段控制提交（dispatch/status/PROJECT_STATE/计划/handoff），代码交付仅 9a4e019
$ git diff a11a873..9a4e019 -- backend/app/server.py backend/ledger_flow/scheduler.py | wc -l → 0（两文件零改动）
$ test ! -e evidence/review-1-cross-margin-capital-flow-v1.handoff.md → PREFLIGHT_OK_absent
$ grep FAKE_ROWS|fake-badge|flow-log-fake（frontend/）→ 零命中（假数据无残留）
$ .venv/bin/python -m pytest backend/tests/test_ledger_flow_{domain,store,service,scheduler,api}.py backend/tests/test_private_client.py -q → 156 passed in 6.85s
$ .venv/bin/python -m pytest backend/tests/ -q → 1717 passed in 144.27s
$ node frontend/self-check.js → 全部自检通过
```

### 对 dispatch 六条 Acceptance Checks 的逐条判断

1. **计划 §4.1/§4.2/§9 冻结条款在代码中成立** — `pass`。
   - 白名单：`private_client.py` WHITELIST +`GET /sapi/v1/margin/capital-flow`→`api.binance.com`，计数守卫测试 16→17；`fetch_capital_flow_page` 不带 `symbol`/`fromId`，spy 测试断言签名参数仅 `startTime/endTime/limit`。
   - 窗口：`service.py:317-322` `_compute_capital_window` 首次 `[now-1d, now]`、之后 `[cap_end-3h, now]`；`_CAPITAL_PAGE_LIMIT=1000` 单页无翻页；满页 `possibly_incomplete=True`（`service.py:340` 按原始 `page_rows` 长度判定，正确）。
   - 新表 `margin_capital_flow_rows`（PK `id`，`CREATE TABLE IF NOT EXISTS` 零迁移）+ `ledger_meta` 三 key；`commit_capital_flow` 单事务 `ON CONFLICT(id) DO NOTHING`。
   - `schema_version` 三处同串 `private-ledger/v2` 未 bump（store 常量、service 响应、docs 小节）；`GET flow-log` 新增顶层 `capital_flow` 块为 additive。
2. **P0-1：coverage 不被 capital 污染且测试真正挡住回归** — `pass`。
   - `git show 9a4e019 -- backend/ledger_flow/service.py` 中 `_build_coverage` 函数体零增删行（diff 仅在 `get_flow_log` 内于其返回后并入 `by_source.capital_flow`）；`coverage_for_window`（`service.py:487-493`）直接调 `_build_coverage`，不经过并入路径，server.py 消费点未改（区间 diff 中 server.py 零改动）。
   - `test_capital_succeeding_does_not_shrink_coverage_aggregate` 直接复现 plan-review 命名的回归形状（capital start=now-1d 若泄漏会使 5 天窗口 complete→False），`test_capital_never_succeeded_leaves_coverage_for_window_untouched` 断言 `by_source` 键集无 capital——两条都是真断言而非走过场。
3. **幂等 id / 多 type 同 tran_id / 失败不推进 / 满 1000 语义** — `pass`。
   - `normalize_capital_rows` 缺 id/tranId/timestamp/asset 任一行丢弃（NOT NULL 字段）；`dedup_capital_rows` 按 id 首胜；store 测试 `test_capital_commit_idempotent_no_overwrite`（同 id 不覆盖、first_seen 保留）与 `test_capital_multi_type_same_tranid_all_retained` 均绿。
   - 失败路径：`_run_capital_flow` 在 `res.status != "ok"` 时 `coverage_start/end=None` 只写 last_run（`test_capital_failure_isolated_and_does_not_advance_end`：两源 coverage 推进、capital end 仍 None）；另有一层 catch-all 兜底 `capital_internal_error`，capital 任何异常不冒泡进两源 run。
   - 满 1000：`possibly_incomplete` 为标志非失败，coverage_end 仍推进到 now——与 plan §5.4「失败不推进」（即仅失败阻塞推进）一致，且写入 `docs/api/public-market-contract.md` 成为文档化口径。
4. **前端：无假数据残留 / 缺块空态 / 筛选与入出全仓 / self-check** — `pass`。
   - `FLOW_LOG_CAPITAL_FAKE_ROWS`、「预览」徽标、`.flow-log-fake-badge` CSS 全部删除且零残留（grep 零命中）；`flowLogCapitalRowsFromPayload` 只读 `payload.capital_flow`，缺块 → 空 rows → 空态文案（非错误态；last_run error 时显示失败文案）。
   - 五桶 `flowLogCapitalTypeBucket`：TRANSFER/BORROW/REPAY 各自一桶、`BUY_*`/`SELL_*`/`TRADING_COMMISSION` 入 TRADE（默认关，符合 plan §3）、其余 OTHER；`flowLogCapitalTransferDir` 正=入全仓、负=出全仓；默认筛选下 20 条上限与合约资金栏同口径（`flowLogSliceLatest`）。
   - self-check base mock 加 `capital_flow` 块与 `by_source.capital_flow` 覆盖真数据渲染路径；旧 fixture 无 capital_flow 块时走空态不抛错（self-check 全绿实证）。
5. **发现范围三分类 / Scenario Admission** — `pass`（本轮无 REWORK 发现，无需分类；评审未援引假设场景，全部判断锚定 diff/行号/可复现命令）。
6. **唯一 handoff / delivery_sha / 评审结论字段** — `pass`：本文件为本任务唯一写入，preflight 记录 absent；delivery_sha 填已封存 `9a4e0198ee7f7d2102ab1b9550c39e79a76e24fa`。

### 补充观察（非发现，不阻塞）

- `coverage.by_source.capital_flow` 为纯展示键：前端不消费它（grep 确认前端只读 `payload.capital_flow`），与 plan §4.1.5「可选、仅作展示、不参与 aggregate」一致。
- `_run_capital_flow` 的 catch-all 在 client 为 None（私有通道未接线）时记 `capital_internal_error` 并隔离，行为与两源 fetcher 的既有容错一致，不扩大风险面。

### 未完成事项

- 无。本评审不实现、不修代码、不提交、不 merge、不部署。
- 运行时事项（留 review-2/Human）：首次实盘拉取的权重占用与满页概率需运行时日志确认（实现 handoff 同述）；本评审为离线证据，未发起实盘请求。

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/evidence/review-1-cross-margin-capital-flow-v1.handoff.md`（本文件）
  2. `reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/evidence/implement-cross-margin-capital-flow-v1.handoff.md`
  3. `reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/00-change-plan.md`
- 执行：Bookkeeper 核验本 handoff（source SHA-256、status revision、ACCEPT 字段），随后按 §8 准备 review-2 dispatch（跨 provider：须不同于实现 `zhipu_glm` 与本 review-1 `moonshot`，默认 `sonnet5`/anthropic）。
- 关卡：HIGH_RISK（账务含义/资金流水展示）→ review-2 由 Human 启动；review-2 ACCEPT 后 Human 决定合并/部署。
- 不能假设的事实：
  - 不能假设 `by_source.capital_flow` 有前端消费者——它是纯展示键，前端只读 `payload.capital_flow`。
  - 不能假设满 1000 行的窗口会阻塞 coverage 推进——`possibly_incomplete` 是文档化标志非失败（plan §5.4 口径）。
  - 不能假设已实盘验证——本阶段全部证据为离线（mock/单测/self-check），首次真实拉取未发生。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

```text
[TASK_RESULT v2]
任务 ID: review-1-cross-margin-capital-flow-v1
执行结果: completed（完成）
结果摘要: 只读 review-1 完成，结论 ACCEPT。固定区间 a11a873..9a4e019 逐条核对通过：计划冻结条款全部落码（白名单+1、1 天首窗、limit=1000 单页无翻页、新表+独立 meta、v2 未 bump）；P0-1 airtight（_build_coverage 零改动、coverage_for_window 不经并入路径、两条回归断言为真）；幂等 id/多 type 同 tranId/失败不推进/满 1000 标志语义均有真测试；前端假数据零残留、缺块空态、五桶与入/出全仓正确。无 REWORK 发现。
产物: [reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/evidence/review-1-cross-margin-capital-flow-v1.handoff.md]
检查结果: [SHA/preflight/区间祖先关系核验=pass；计划 §4.1/§4.2/§9 冻结条款落码=pass；P0-1 coverage 隔离与回归测试=pass；幂等/多 type/失败不推进/满 1000 语义=pass；前端去假数据、缺块空态、五桶筛选=pass；独立复跑六文件 156 passed、全量 1717 passed、self-check 全绿=pass；唯一 handoff、delivery_sha=9a4e019 封存值、评审结论字段合规=pass]
阻塞项: [none]
评审结论: ACCEPT（接受）
问题记录: none
修复要求: none
本地北京时间: 2026-08-10 19:22:55 CST
下一步模型: grok4.5（本阶段 Bookkeeper，status.json.bookkeeper=grok4.5，由 Human 启动其终端）
下一步任务: 读取：reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/evidence/review-1-cross-margin-capital-flow-v1.handoff.md；执行：Bookkeeper 同文件核验（source SHA-256、status revision、ACCEPT 闭合字段）并推进 status.json，随后准备 review-2 dispatch（跨 provider，默认 sonnet5/anthropic）；关卡：HIGH_RISK，review-2 由 Human 启动，ACCEPT 后 Human 决定合并/部署。
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- bookkeeper: `grok4.5`
- verified_at: 2026-08-10 19:28:42 CST
- status_revision_at_verify: 4（review_1 / `review-1-cross-margin-capital-flow-v1` / dispatched）
- source_payload_sha256: `c4bb6b2778667894669ccb4d850f523565a4ced94e8b8c33a2c5e122c157b320`（marker 前全部字节）
- 核验：
  - `执行结果: completed` + `评审结论: ACCEPT（接受）` + `问题记录: none` + `修复要求: none` → 闭合完整
  - `delivery_sha` 与 status 已封存值 `9a4e0198ee7f7d2102ab1b9550c39e79a76e24fa` 一致
  - provider 隔离：实现 zhipu_glm、review-1 moonshot，跨 provider 成立
  - preflight 路径 create-only 已落盘为本任务唯一 handoff
- 裁定：**核验通过（ACCEPT）** → 准备 review-2；`rework_count` 不变（0）
- 后续：Human 启动 review-2（默认 sonnet5 / anthropic，须不同于 zhipu_glm 与 moonshot）

## Errata (append-only)

（无。）

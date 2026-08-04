# Task Handoff: review-1-dual-ledger-flow-log-v1

## Source Report (author-only; immutable after task end)

- task_id: `review-1-dual-ledger-flow-log-v1`
- role: `Reviewer`（Review-1，只读）
- target_model: `deepseek`
- stage_id: `2026-08-04-dual-ledger-flow-log-v1`
- created_at: `2026-08-04 22:09 CST`
- base_sha: `dc4cc6d9dc629c06cff4a98f98ff7a81a533a3c8`
- delivery_sha: `none`（评审任务无交付提交；受审区间 `dc4cc6d..5613c4e4d1d3668c04ae5f05e264edb8c0575213` 已由 Bookkeeper 冻结）
- status_revision 核对：`19`（与 dispatch 一致）

### 评审范围与对象

受审交付（区间内本 stage 实现提交）：

- 任务 A `aba7420`：`backend/services/private_client.py`（白名单 13→15 + `fetch_interest_history_page` / `fetch_um_income_page` 两个单页 fetcher）、`backend/ledger_flow/__init__.py`、`backend/ledger_flow/domain.py`、`backend/ledger_flow/store.py`、`backend/tests/test_ledger_flow_{domain,store}.py`、`backend/tests/test_private_client.py`
- 任务 B `550f8b7`：`backend/ledger_flow/service.py`、`backend/ledger_flow/scheduler.py`、`backend/app/server.py`、`backend/services/snapshot_service.py`（只读访问器 `private_client` property）、`docs/api/public-market-contract.md`（v0.12）、`backend/tests/test_ledger_flow_{service,api}.py`
- 任务 C + 前端最终 `f23368b` + `5613c4e`：`frontend/index.html`、`frontend/self-check.js`

权威：设计定稿 v1.4（`docs/planning/2026-08-04-dual-ledger-flow-log-design.md`，§11–§15 冻结契约）、契约 v0.12（`docs/api/public-market-contract.md` §Dual-Ledger Flow-Log Amendment）。fake 前端原型与控制提交（`84e37b0`…`a8dee78`）为上下文，范围外按三分类处理——本轮未发现针对它们的发现。

### 复核命令与结果（全部离线）

```bash
# 前端 self-check（C + tab-layout v2 最终）
node frontend/self-check.js            # 全部自检通过

# 本 stage 新增/修改的后端测试（A 84 + B 31 = 115）
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider -q \
  backend/tests/test_ledger_flow_domain.py backend/tests/test_ledger_flow_store.py \
  backend/tests/test_ledger_flow_service.py backend/tests/test_ledger_flow_api.py \
  backend/tests/test_private_client.py  # 115 passed

# 全量回归（超出任务 B handoff 声称的 194 抽查范围）
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider -q backend/tests/
# 1336 passed, 5 failed —— 5 个失败全部在 backend/tests/test_service_health.py，
# 全部 AttributeError: '_RunStubService' object has no attribute 'private_client'
# （backend/app/server.py:954，任务 B 引入）
```

### 发现（按 AGENTS.md §8 三分类 + 严重度）

#### F1 — [in-range / 🔴 阻塞] 任务 B 破坏 5 个既有 `run()` 生命周期测试，且「194 回归全绿」声明不实

- **位置**：`backend/app/server.py:954`（`550f8b7` 新增 `LedgerFlowService(ledger_store, service.private_client, ...)`）；既有桩 `backend/tests/test_service_health.py:255 class _RunStubService` 无 `private_client` 属性。
- **事实**：`test_service_health.py` 最后修改 `04ab07b`，早于 `base_sha`（`git merge-base --is-ancestor 04ab07b dc4cc6d` 成立），是既有测试。`base_sha` 的 `server.py` 中 `private_client`/`ledger` 引用为 0 处，即该访问是本次交付引入。实测失败 5 项：`test_run_fatal_when_start_worker_raises`、`test_run_fatal_when_serve_forever_raises`、`test_run_keyboard_interrupt_cleans_up_and_exits_zero`、`test_run_emits_borrow_execution_mode_with_recovery_counts`、`test_run_live_missing_credentials_emits_distinct_blocked_event`（覆盖 run() 的 worker 异常、serve_forever 异常、KeyboardInterrupt 清理、执行模式事件、凭据缺失事件）。
- **影响**：这 5 项是既有失败路径/生命周期保护，被本交付静默破坏后不可运行；任务 B handoff 与 Bookkeeper 验证只抽查了 194 项（A+snapshot+borrow+hedge 文件），未覆盖 `test_service_health.py`，故「无回归」结论不成立。
- **修复要求**（最小）：在 `_RunStubService.__init__` 增加 `self.private_client = None`（`LedgerFlowService.is_usable()` 对 `client=None` 返回 `False`，调度器不启动，恰好走通 §15.3「通道不可用不调度」路径）；重跑 `backend/tests/test_service_health.py` 与全量 `backend/tests/`，确认 0 failed。

#### F2 — [in-range / 🟡 建议修改] `backend/ledger_flow/scheduler.py` 无任何单元测试

- **事实**：`grep -rn "LedgerScheduler" backend/tests/` 为空；`decide`（分钟≥1 / 本小时已成功 / 尝试<3 / 距上次≥5min 四判据）、`_startup_catchup`（空库→`backfill`、超 1h→`startup_catchup`）均无直接断言。dispatch 验收第 9 项「调度判定」明确列为关键路径，计划评审 Q4（重启/时钟跳变/休眠不漏跑不重复）也在此。
- **核对结论**：实现本身与设计 §15.1/§15.3 逐条一致（本小时成功幂等、5min 重试间隔、每自然小时 3 次预算、单飞由 service 锁承担、通道未启用不 `start()`），无行为缺陷；缺的是自动化保护。
- **修复要求**：新增 `backend/tests/test_ledger_flow_scheduler.py`，注入时钟覆盖：分钟<1 不跑、本小时已有成功 run 不跑、预算 3 次耗尽不跑、距上次尝试 <5min 不跑、各条件满足返回 `("scheduled")`；`_startup_catchup` 空库→backfill、上次成功>1h→startup_catchup、≤1h 不跑；`stop()` 幂等。

#### O1 — [观察] run 表 `*_new_row_count` 恒 0（dispatch 已知项，确认不构成缺陷）

`store.insert_run` 无这两个键（默认 0）、store 无 `update_run`。已逐条确认对外语义不受影响：`last_run`（GET）不含该字段（`service._format_last_run` 只输出 9 字段）、`delta` 经 `query_*_since(first_seen_at_ms > baseline)` 统计、POST 响应的 `interest_new_row_count`/`income_new_row_count` 取自 `commit_*` 返回值。run 表该列是死数据，若未来直接读 run 表对账会被恒 0 误导；建议后续（非本轮）删列或补 `update_run`。

#### O2 — [观察] run 记录先于明细提交写入

`_do_run` 中 `insert_run`（`finished_at_ms`=写时墙钟）在 `commit_interest`/`commit_income` 之前。若 commit 阶段抛 SQLite 异常（极端），run 记录会短暂显示 `status=ok` 而明细/coverage 未落库；下一次 run 因 coverage 未推进会重拉自愈。与设计 §14 规则 5「run 记录必定落库」的意图兼容（确保失败留痕），极端场景不阻塞。

#### O3 — [观察] `_build_coverage` by_source 的 null 判定为「两端皆 None 才 null」

`service.py:394` `i_start is None and i_end is None`。正常 `commit_*` 总是同事务写 start+end 两端，半对象状态实际不可达；防御性不强，观察级。

### 重点核查逐项结论（全部 pass 项的依据）

1. **契约一致性 pass**：§13.2/§13.5/§14/§15 与契约 v0.12 逐字段核对一致——`scheduler_enabled`、`last_run`（9 字段、`consecutive_failure_count` 实时算）、`coverage.by_source/gaps(≤20 升序)/pending_tail_ms/complete`（聚合 start=较晚者、end=较早者；complete=起点覆盖+无相交 gaps）、`delta`（baseline=倒数第二次成功 run、manual 排除、不足两次 null+false）、`today.day_start_ms`（北京日界）、两栏 `rows(≤500)/summary(全量)/row_count(全量)/row_limit_applied`、ID 字符串、缺失 null、空态 200 逐字段符合规则 13；前端消费字段名与后端返回逐项一致（`accrued_at_ms/asset/interest/principal/type`、`time_ms/income_type/symbol/income/asset`、delta/today/coverage/last_run 全部对齐）。
2. **资金精度红线 pass**：`_id_to_str`（>2^53 ID 字符串）、`_amount_str`/`_opt_text`（透传/缺失及空串→null）、`_sum_amounts`（`localcontext(prec=40)` 求和、任一分组不可解析→total=null+`unparsed_row_count>0`）、store 金额列全部 TEXT 且无 `SUM/AVG`（`test_no_sql_aggregation_on_amounts_in_source` 佐证）、前端 `Number()` 仅用于正负着色/收取支付文案，不参与金额与汇总。
3. **F1 事务与幂等 pass**：`insert_run` 独立事务；`commit_interest`/`commit_income` 各自「明细+该源 coverage+gaps」单事务；两源隔离（`test_run_record_not_rolled_back_by_detail_failure`、`test_source_detail_and_coverage_one_transaction`、`test_two_sources_independent`）；`ON CONFLICT DO NOTHING` 不覆盖（`test_interest_idempotent_no_overwrite` 等）；同批共享 `first_seen_at_ms`/`run_id`。已知项 `*_new_row_count` 恒 0 见 O1。
4. **F2/F3 增量与统计 pass**：`_SUCCESS_KINDS` 含 scheduled/startup_catchup/backfill 且两栏 ok；manual 不入基准（`test_delta_baseline_second_success_and_manual_excluded`）；不足两次 `complete=false`+`baseline_ms=null`；`consecutive_failure_count` 实时算（disabled 不计、无记录 0）；today 按北京日界发生时间；分组不跨币种。
5. **F4 coverage 护栏与空态 pass**：complete 判定、`pending_tail_ms` 不参与（独立渲染「最近 X 分钟尚未刷新」）、窗口落空洞内必 false（`test_window_fully_inside_gap_is_not_complete`）、空库 200 形状（`test_get_flow_log_empty_state_shape`、API 层 `test_get_flow_log_empty_state_returns_200_not_503`）；前端三态判定表按 §13.2 规则 14 顺序取第一个命中；`complete=false` 时禁「该时间窗无记录」（self-check 断言 + `paneEmptyMessage` 红线）。
6. **调度与并发 pass（实现）**：`decide` 四判据与设计一致、启动 catchup、单飞（`test_run_once_single_flight_returns_none_when_busy`）、通道未启用不 start 且 `scheduler_enabled=false`（server.py 装配 + `is_usable()`）；独立守护线程边界与借币调度器先例一致。**测试缺口见 F2**。
7. **前端展示硬规则 pass**：`#btn-market-board`（默认选中）/`#btn-flow-log` 并列 `.panel-actions`（role=tablist）；侧栏恢复三项、`#nav-flow-log` 已移除（self-check 断言）；`setMarketBoard` 同页切换不改 `activeView`；元数据卡片 `.flow-log-meta-row` 两列等宽 + ≤900px 单列；60 秒轮询恰好一个（`startFlowLogPoll` 先 stop 后 start、切看板/离页两处 `clearInterval`、回调复核 activeView+marketBoard）；20 条与三数字文案（「显示最近 20 条（共 N 条）」+`row_limit_applied` 500 追加）；筛选纯前端零请求；隐私 `****`；护栏三情形文案（起点截断/空洞/三态）齐备；自定义窗口北京日界、非法零请求；初始化默认 market 看板零 `private-ledger` 请求。
8. **边界 pass**：白名单仅新增 2 条设计指定只读 GET；无 Binance 直连（self-check「fetch 同源白名单」断言）；无下单/借还/划转/gate/凭据/部署/实盘；`snapshot_service.py` 仅新增只读 `private_client` property（复用同一凭据与 offline/private_channel 门禁）；快照 schema/60 秒调度/cache-refresh/持仓合并均未改；`build_server` 签名不变。
9. **测试质量 fail（见 F1/F2）**：本 stage 115 项新测试 + self-check 全绿（实测复核），关键路径断言覆盖完整（高精度往返、不可解析金额、空库、幂等不覆盖、注入失败点、截断双向、单飞、轮询生命周期、三态、隐私）；但全量回归 5 项既有测试被破坏（F1）、scheduler 判定无断言（F2）。

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/review-1-dual-ledger-flow-log-v1.handoff.md`
  2. `backend/tests/test_service_health.py`（`_RunStubService`，255 行附近）
  3. `backend/app/server.py`（`run()`，954 行附近）
  4. `backend/ledger_flow/scheduler.py`
  5. `docs/planning/2026-08-04-dual-ledger-flow-log-design.md`（§15.1/§15.3）
- 执行：按 F1 修复要求改 `_RunStubService`（补 `self.private_client = None`）并全量回归；按 F2 新增 `backend/tests/test_ledger_flow_scheduler.py` 覆盖 `decide`/`_startup_catchup` 全分支；两者属同一修复轮（in-range，递增 `rework_count` 1 次）。
- 关卡：修复 + 复测后回到 review-1 复审（fixed `base_sha..delivery_sha` 按新交付提交），再按流程走 review-2（sonnet5）。
- 不能假设的事实：任务 B handoff「194 回归全绿」不覆盖 `test_service_health.py`，不可作为回归证据；全量回归以 `pytest backend/tests/` 实测为准。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

```text
[TASK_RESULT v2]
任务 ID: review-1-dual-ledger-flow-log-v1
执行结果: completed（评审运行完成；评审结论 REWORK）
结果摘要: 统一 review-1（deepseek，跨 provider）完成：A+B+C+前端最终 dc4cc6d..5613c4e。契约/精度/事务/增量/护栏/调度实现/前端硬规则/边界逐项核对通过；发现 2 项 in-range：① 任务 B 破坏 5 个既有 test_service_health 测试（server.py 新增 service.private_client 未同步桩，"194 回归全绿"声明不实，实测 1336+5failed）；② scheduler.py 无单元测试（decide/catchup 无断言）。
产物: [reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/review-1-dual-ledger-flow-log-v1.handoff.md]
检查结果: [契约一致性(§13.2/13.5/14/15+v0.12 逐字段+前端消费): pass, 资金精度红线(ID字符串/透传/缺失null/prec40/不可解析null/无SQL聚合/前端不重算): pass, F1事务与幂等(run独立/分源同事务/DO NOTHING不覆盖/同批共享; 已知项new_row_count恒0确认非缺陷): pass, F2/F3增量统计(baseline/manual排除/不足两次/连续失败/北京日界/不跨币种): pass, F4护栏与空态(complete判定/空洞内false/空库200/三态/禁无记录措辞): pass, 调度实现正确但scheduler无单元测试: fail, 前端硬规则(双看板/侧栏三项/轮询生命周期/20条/零请求/隐私/三态文案): pass, 测试质量(115新测试+self-check全绿, 但全量回归5既有测试被破坏且194声明不实): fail]
阻塞项: [F1 in-range 阻塞：修复 backend/tests/test_service_health.py::_RunStubService（补 private_client=None）+ 全量回归复测；F2 in-range 建议：新增 backend/tests/test_ledger_flow_scheduler.py]
评审结论: REWORK（返工）
问题记录: backend/app/server.py:954、backend/tests/test_service_health.py:255、backend/ledger_flow/scheduler.py
修复要求: backend/tests/test_service_health.py、backend/tests/test_ledger_flow_scheduler.py（新增）
本地北京时间: 2026-08-04 22:09:43 CST
下一步模型: bookkeeper1（Bookkeeper；核验本评审结论并准备修复 dispatch）
下一步任务: 读取：reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/review-1-dual-ledger-flow-log-v1.handoff.md；执行：核验 REWORK 结论与 F1/F2 证据路径，按 §8 将修复任务记为 in-range 修复轮（rework_count 0→1，根因按 F1 命名）并路由修复 dispatch；关卡：修复实现 + 复测 → review-1 复审 → review-2（sonnet5）
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification

- 核验时间（本地）：2026-08-04 22:15:00 CST
- source_sha256（marker 前字节）：`4df5338529505cc39f1740e49e66e565b8890ef56d2e9264b5eebbece70c95cc`
  （复现：读本文件，取 `<!-- BOOKKEEPER_APPEND_ONLY:` 之前全部字节，`hashlib.sha256` 十六进制）
- 核对的 status revision：19（`current_task.id = review-1-dual-ledger-flow-log-v1`、`state = dispatched`，与评审交接件一致；预检 `test ! -e` 于 2026-08-04 22:00 CST 通过，评审 22:09 CST 交付）
- task_id / role / stage_id 与 `status.json` 一致；受审区间 `dc4cc6d..5613c4e` 与 dispatch 一致
- 结论：**通过（verified，verdict=REWORK）**。`评审结论: REWORK`、`问题记录`、`修复要求` 齐备；F1（in-range 阻塞：`backend/app/server.py:954` 新增 `service.private_client` 依赖未同步 `backend/tests/test_service_health.py:255 _RunStubService`，破坏 5 个既有测试，实测全量 `1336 passed, 5 failed`）与 F2（in-range 建议：`scheduler.py` 无单元测试）均附可执行修复要求；其余九项核查 pass，已知项 `new_row_count` 恒 0 经评审确认为**非缺陷**。
- **回归声明纠偏**：任务 B handoff「194 回归全绿」仅覆盖 A+snapshot+borrow+hedge 文件、未含 `test_service_health.py`，故「无回归」结论不成立——Bookkeeper 此前封存 B 时亦未全量复测（按 B dispatch 的验收命令只跑 service+api）。**全量回归以 `pytest backend/tests/` 实测为准**（已写入修复 dispatch 验收）。
- **rework_count 判定**：本 REWORK 为正式实现评审返工，按 `AGENTS.md` §8 **`rework_count` 0 → 1**（根因按 F1 命名：「任务 B 引入新装配依赖未同步既有测试桩，且回归声明未覆盖全量」）；F1/F2 同属一轮修复（in-range），只计 1 次。
- 后续状态：review-1 → `verified`；修复任务 `fix-review1-dual-ledger-flow-log-v1`（claude_glm，minimal-change-engineer）已路由——F1 补桩 + 全量回归、F2 新增 scheduler 单测；修复实现 + 复测 → review-1 复审（deepseek）→ review-2（sonnet5）。

## Errata (append-only)

（无。）

# Review-2（最终复核）

结论：`REWORK`（需要返工），当前固定提交范围不能进入用户验收，更不能解除 live（真实执行）、Start（全局启动闸门）或第一笔真实订单的独立授权门。

本轮没有发现突破 `target_n`（计划尝试组数）硬上限的路径，但发现五组仍会影响真实开单安全或账实一致性的代码缺口，以及一组使正式评审证据链不成立的 Harness（项目流程护栏）缺口。最直接的业务影响是：连续出现 `single_leg`（只受理一条腿）时，任务不会进入连续失败刹车；client-ID（客户端订单编号）查询又可能把没有权威订单结果的畸形 200 响应错误闭合成“订单不存在”，从而在原订单可能存在时继续下一组。

当前 `rework_count=6`、`max_rework=6`，变更额度已经用满。任何新的代码修改都必须先取得用户新的书面授权；本结论本身不构成第 7 次修改授权。

## 审查身份、范围与披露

- 最终审查者：GPT-5 Codex；provider（模型供应商）为 OpenAI/Codex。
- 固定提交范围：`28c550d87c1ca90983d5bde9c7102d42cffecd4e..b9e1978eaffd047b7871b8721f511307e75fde68`。当前工作树 `HEAD=0e832c5657f1a06b5c04912431f82320c53afcf3` 晚于固定头；业务判断没有使用移动 `HEAD` 替代固定范围。
- 独立重算指纹与派发值一致：
  `b9e1978eaffd047b7871b8721f511307e75fde68:604caada1043e8334f33b1cc73239f1cf6bb19017db1dc68374679cf6ac99ddd`。
- Codex 曾起草 `00-task.md`、`10-design.md`、`11-adr.md` 并综合 `06-direction-synthesis.md`，故 `reviewer_prior_involvement=design`（既往参与：阶段设计）。Codex 没有编写本阶段交付代码或修复代码。
- Codex 还产出过旧固定范围上的 `50-review-2.md`（`REWORK`），但本轮没有把旧结论当作已成立事实；所有当前 finding（问题）均从当前固定 diff（差异）、源码、测试和本轮独立复现实验重新得出。
- Codex 在 2026-07-25 前曾担任 bookkeeper（阶段记账者），所以部分早期状态、handoff（交接）和 dispatch（派发）文件是本模型的既往簿记输出；本轮没有把这些叙述当作代码证据。
- 当前 bookkeeper Claude Opus 5 同时产出了后端 Review-1 r2/r3/r4/r5。逐字比对确认，`67` 的 PROMPT BODY（提示正文）相对 `66` 的 `fix_start_prompt` 只有一处已披露的用户授权标记替换，未发现隐藏、重排或摘要 reviewer（审查者）原始 finding 的情况；但 `66`、`67`、`68` 的正式回执仍为 `pending`，使该双重身份下最需要封存的执行/会话证据没有成立，详见 Finding 5。

## 实际检查与离线验证

已阅读派发要求列出的工作流、PRD（产品需求文档）、用户后续修正案、设计/ADR（架构决策记录）、开发拆分、实现与历次修复报告、两侧 Review-1、路由披露、`60-test-output.txt`、`status.json`、`70-handoff.md`、固定 diff、相关后端/前端源码和测试。没有读取凭据，没有连接 Binance，没有启用 live 或 Start，没有发送任何真实请求。

固定范围与门禁检查：

- 分支：`stage/2026-07-hedge-open-real-api-v1`。
- 审查输出落盘前工作树干净；固定 base/head 均为有效 commit（提交）。
- 指纹独立重算一致。
- `.venv/bin/python scripts/validate-stage.py 2026-07-hedge-open-real-api-v1 --phase pre-review`：表面 PASS，但输出明确为 `status=review_1`，与工作流要求 Review-2 派发前根状态为 `review_2` 不一致。
- `git diff --check`：PASS。

本轮重新执行：

- `.venv/bin/python -m pytest backend/tests -q`：`906 passed in 45.87s`。
- `node frontend/self-check.js`：全部自检通过。
- `.venv/bin/python -m pytest scripts/tests/test_validate_stage_dispatch_protocol.py -q`：`55 passed in 0.83s`。

本轮另用临时 SQLite（数据库）、record transport（记录型假执行器）和构造响应做了不写仓库文件的反向抽验：

1. 连续 3 组非限频 `single_leg` 后得到
   `scheduled_attempt_count=3`、`fail_count=0`、
   `consecutive_submission_failures=0`、`status=running`、`target_n=3`。
2. `classify_query_response(HTTP 200, {"msg": "no authoritative order result"})`
   返回 `TERMINAL_RECORDED`，即确定未受理；同函数对带 `Retry-After=7` 的 HTTP 429 返回 `None`，丢失暂停信号。
3. 只有 Spot `MIN_NOTIONAL` 的公开过滤器经 `_parse_spot_filters` 后得到
   `min_notional=None`、`apply_min_to_market=None`、`notional=None`。
4. 构造“两腿均已 terminal（终态），但 attempt.pair_outcome 尚为 NULL”的崩溃缝隙后，
   `nonterminal_legs=0`；恢复轮次返回继续运行，但 `pair_outcome` 前后都仍为 `None`。
5. 用真实线程让 live worker（真实执行工作线程）阻塞在假 POST，同时人工删除任务；删除后状态为
   `deleted`，释放线程让迟到的 429 返回后，状态被改写为
   `paused`、`pause_reason=rate_limited`。

现有测试全部通过，说明这些行为部分被测试固化成了错误预期，部分完全没有覆盖，不能用“全绿”抵消。

## Findings（问题）

### P1 — 非限频单腿失败不进入连续失败刹车，任务可继续扩大单腿敞口

证据：

- `15-immediate-loop-and-open-log-amendment.md:69` 要求一腿受理、另一腿最终失败时，非致命错误由可配置失败规则决定能否继续。
- `16-replacement-development-breakdown.md:84-90` 进一步固定：非致命 `single_leg` 必须增加连续失败计数。
- `backend/hedge_open_tasks/store.py:697-698,758-767` 却明确让 `single_leg` “counts unchanged”，既不增加 `fail_count`，也不增加 `consecutive_submission_failures`。
- 本轮独立抽验连续制造 3 组 `single_leg`，结果连续失败仍为 0、任务仍为 `running`。
- 当计划尝试已经耗尽但受理组数没有达到 `target_n` 时，`domain.resolve_status_after_attempt` 仍只按 `accepted_count` 设置 `done`；worker 虽因硬上限退出，卡片和日志仍显示运行/继续下一组。

影响：例如 `target_n=10`、暂停阈值为 3 时，连续三组单腿结果不会暂停，系统仍可继续执行剩余七组，在已存在裸露腿时继续扩大敞口。即使最终没有超过计划硬上限，任务状态也会错误地停在“运行中”，开单日志给出不存在的“继续下一次”动作。

建议：非限频、非致命的 `single_leg` 应按冻结规则增加失败与连续失败计数，并在达到任务快照阈值时暂停；429（请求过多）组仍保持免计数。最后一个计划 attempt（尝试）结算后，如未因致命错误/阈值/人工动作进入其它终态，应将任务和日志 next action（下一动作）一致地标为完成。

### P1 — client-ID 查询把模糊 200 错判为订单不存在，并丢弃查询阶段 429

证据：

- `15` 修正案 `:49-51,70` 要求没有权威业务结果时保持查询，只有明确订单不存在才能确认未受理。
- `16` 开发拆分 `:161-164` 明确“only an explicit order-absent business code confirms non-acceptance”（只有明确不存在业务码才能确认未受理）。
- `backend/services/live_hedge_executor.py:288-341` 对 404/`-2013` 的处理正确，但又把任意 2xx 字典中缺少有效 `orderId` 的响应直接映射为 `LEG_REJECTED`；这与同函数上方“ONLY an explicit order-absent signal”的注释自相矛盾。
- 同函数对查询阶段 429/`-1003`/418 直接返回 `None`，所以 `service._reconcile_own_legs` 永远看不到 `rate_limited=True`；`21-task-local-runtime-and-manual-pause-amendment.md:53` 要求的“本卡暂停、worker 退出、人工恢复、不得自动等待重试”不会发生。
- 当前单测 `test_query_2xx_without_order_id_is_rejected` 和
  `test_query_rate_limited_is_inconclusive_none` 正在固化这两个错误语义。

影响：畸形/被中间层改写的 200 查询可能在原订单实际存在时被当作“确定不存在”，闭合本组并允许下一计划组；查询阶段被限频时，worker 又会按一秒节奏继续自动查询，既违反人工恢复合同，也可能把 429 推向 418 封禁。

建议：2xx 查询缺少有效 `orderId` 时保持 `UNKNOWN_QUERYING`（未知、继续仅查询），只有 404 或 `-2013` 才确认 absent（不存在）。查询阶段 429 必须保留 typed signal（类型化信号）并交给本任务 worker：持久化任务级限频暂停，保留未决订单、不重发 POST，退出等待人工恢复。

### P1 — 迟到的 worker 结果会覆盖人工删除，把已删除任务“复活”

证据：

- `backend/hedge_open_tasks/store.py:1451-1469` 的 `pause_task` 对当前状态没有任何条件，
  无条件把任意任务改成 `paused` 并清空 `stop_reason`。
- `service._worker_round` 在发单/查询开始前读取一次 task，网络 I/O（输入输出）期间不持 store 锁；
  人工 `post_delete` 可以合法并发落下 `deleted`。
- 当迟到的 429 或余额不足结果返回时，`service.py:1020-1029` 仍用派发前 task 调
  `_pause_task_local`，从而覆盖刚落下的人工删除。
- 本轮真实线程离线复现：阻塞假 POST → `post_delete` 后状态为 `deleted` → 放行假 429 后状态变成
  `paused`，暂停原因是 `rate_limited`。
- `68-review-1-backend-r5.md` 把无状态守卫列为“生产不可达”P3，只分析了 query classifier（查询分类器）目前不返回限频信号，遗漏了已经存在的 dispatch response（发单响应）并发窗口。若按 Finding 2 修复查询 429，该问题还会扩展到恢复查询路径。
- 同类风险也存在于无状态条件的 fatal stop（致命停止）写入：迟到的致命预检/发单结果不得把
  `deleted` 或其它更高优先级人工终态改成 `stopped`。

影响：操作者明确删除的卡会重新出现在暂停卡中，可再次被人工 Start/recover（启动/恢复）；这破坏 deleted sticky（删除状态粘滞）和人类控制边界，并可能让操作者误以为已删除任务没有后续可执行入口。

建议：把 worker 的暂停/致命停止改成带当前状态条件的原子更新。对 `deleted`、`done`、既有
`stopped` 等更高优先级状态只记录迟到事件/attempt 事实并继续对账，不改任务状态、不清已有原因；
只允许合同明确的源状态进入 `paused`/`stopped`。新增真实线程回归，覆盖人工 pause/delete 与迟到
429、余额不足、fatal 的竞态。

### P1 — 最后一条腿落终态与 attempt 结算之间存在不可恢复的崩溃缝隙

证据：

- `service._reconcile_own_legs` 在 `backend/hedge_open_tasks/service.py:1057-1069` 先用独立事务把 leg（订单腿）写成 terminal，之后才在 `:1081-1090` 另起调用 `finalize_attempt`/`settle_attempt_no_counters`。
- 若进程恰在两步之间退出，重启后 `list_non_terminal_legs_for_task` 返回空；`_recover_workers` 的非运行任务恢复分支只寻找非终态腿，无法发现“腿都终态但 pair_outcome 为空”的 attempt。
- 对运行任务，worker 会尝试准备下一组，但 `prepare_attempt` 又因旧 attempt 的
  `pair_outcome IS NULL` 拒绝；由于没有非终态腿，真实循环不会 pacing（节流等待），可形成同卡忙循环。
- 本轮独立抽验构造该持久状态后，恢复轮次没有补写 `pair_outcome`。

影响：真实成交事实可能已经写在两条腿上，但组结果、失败阈值、暂停/终止状态和日志永远不结算；运行卡可能占用 CPU 忙循环，非运行卡则可能永久无人恢复。账面持仓与任务状态不再具备重启一致性。

建议：把“最后一腿终态更新 + 组结算”放进可重入的原子 store 操作，或增加一次性恢复路径，显式发现并幂等结算“pair_outcome 为空且两腿均终态”的 attempt。新增崩溃点回归，覆盖 running/paused/stopped/deleted/done 和 429 免计数分支，证明零重发、零新组、只结算一次。

### P1 — live 预检仍没有完成已批准的账户健康与 Spot MIN_NOTIONAL 门禁

证据：

- `12-development-breakdown.md:70-71` 要求 unhealthy account（账户异常）预检失败；原始 `50-review-2.md` required fix #3 又明确要求 `accountStatus=NORMAL`、账户健康/`uniMMR` 和 `NOTIONAL`/`MIN_NOTIONAL` 完整性。
- 事实调研 `order-model-and-live-seams-recon.md:213-217,294-314` 给出了
  `GET /papi/v1/account`、`accountStatus` 与 `uniMMR`。
- 当前 `backend/services/hedge_open_live_client.py:58-66` 的精确 allowlist（白名单）没有 `/papi/v1/account`；`HedgePreflightProvider` 只读 balance、position mode 和 rate-limit ceiling（限频上限），没有账户健康输入，`PreflightSnapshot` 也没有账户状态字段。
- `backend/services/hedge_preflight_provider.py:48-75` 的 Spot 解析只读取 `NOTIONAL`，忽略 `MIN_NOTIONAL`；缺少这两种过滤器时不会 fail closed（信息不全即拒绝），而是把门槛当作不存在。本轮独立抽验已复现。
- 后续第 5/6 次有界修复文件又要求“7 端点冻结 allowlist”，与尚未完成的账户健康要求发生冲突；没有用户明确的合同豁免可以静默消除原要求。

影响：账户已处于非正常状态时本地预检仍可能授权 POST；仅提供 Spot `MIN_NOTIONAL` 的交易对也可能绕过最小名义金额检查并向交易所发送必然拒绝或超出批准前置判断的订单。

建议：在新的用户书面授权中先解决“7 端点冻结”与账户健康要求的冲突。安全路径是将精确只读 `GET /papi/v1/account` 作为唯一新增端点，要求 `accountStatus == NORMAL` 且 `uniMMR` 存在、可解析并按用户批准的政策处理；缺失/畸形一律 fail closed。Spot 同时支持 `NOTIONAL` 和 `MIN_NOTIONAL`，两者都缺失或畸形时预检不完整，不能创建 attempt 或 POST。不得由实现者自行发明 `uniMMR` 风险阈值。

### P1 — Review-1 r4/r5 与第 6 次修复的正式派发回执未封存，Review-2 状态前置也未满足

证据：

- `docs/parallel-development-mode.md` R9 要求 completed/done（已完成）回执必须记录实际执行方式、ISO 时间、Session ID（会话编号）或明确不可得原因；带有不完整回执区块的文件不适用历史兼容例外。
- `66-review-1-backend-r4.dispatch.md`、`67-fix-review-1-backend-r4.dispatch.md`、
  `68-review-1-backend-r5.dispatch.md` 顶部目前全部仍为 `status: pending`，时间为空、Session ID 为 “pending human execution”；但对应 `66`/`46`/`68` 输出已经存在。
- `status.json.session_receipts` 没有补齐这三次执行；因此无法由正式 evidence（证据）确认它们确由 human operator（人类操作员）执行，也无法确认 `68` 要求的 fresh read-only session（全新只读会话）。
- `status.json` 根 `status` 仍为 `review_1`，而 `stage-delivery.yaml` 要求派发 Review-2 前为 `review_2`。本轮 pre-review validator（预审校验器）仍错误 PASS，并在输出中打印 `status=review_1`。
- 对 `66.fix_start_prompt` 与 `67` 正文的机械 diff 只发现一处已披露、由 `27` 用户授权支持的定点替换；未发现 bookkeeper 改写 reviewer finding。但 prompt 保真不能替代缺失的执行回执。

影响：当前后端 Review-1 ACCEPT（接受）和第 6 次修复不能作为满足 R9/Hard Gate（硬门禁）的正式证据；Claude Opus 5 的 bookkeeper/reviewer 双重身份也因缺少实际会话回执而无法完成独立性审计。Review-2 在状态机尚未进入 `review_2` 时被放行，接受结论会建立在失效前置门上。

建议：bookkeeper 只能依据人类操作员实际保存的执行记录补齐 66/67/68 回执和
`status.json.session_receipts`，不得猜测 adapter command（适配器命令）、时间或 Session ID。若实际记录无法恢复，应由人类重新执行相应正式节点并生成新回执。随后将根状态正确推进到 `review_2`，为 validator 增加“Review-2 派发必须 status=review_2、当前 dispatch receipt 必须完成”的回归，再重新跑固定指纹上的门禁与评审。

## 必须修复后才能重审

1. 按用户后续合同修复非限频 `single_leg` 的连续失败计数/阈值暂停，并在计划 attempt 全部结算后统一任务与日志的完成语义；429 组继续免计数。
2. 修复 client-ID 查询分类：缺少权威 `orderId` 的 2xx 保持未知；只有明确 absent 码闭合；查询阶段 429 转换为本任务持久暂停与人工恢复，绝不重发。
3. 给 worker 的暂停/致命停止写入增加原子状态守卫，保证人工删除和其它高优先级终态不会被迟到结果覆盖。
4. 消除或可恢复“两腿均终态、pair_outcome 为空”的崩溃缝隙，新增重启幂等和零忙循环回归。
5. 修复 Spot `MIN_NOTIONAL`；由用户先书面决定账户健康端点/政策冲突，再实现或明确修订合同，禁止静默忽略。
6. 由 bookkeeper 修复 66/67/68 的人类执行回执、Session receipt（会话回执）和根状态；若缺少真实记录，重新执行，不得补造。
7. 新增反向测试，先证明上述缺陷会失败，再跑完整后端、前端、Harness、`git diff --check` 与阶段 validator。

## 已核实仍保持的性质与剩余风险

- 固定范围的默认 `APP_HEDGE_EXECUTOR=disabled`、Start 默认关闭、双腿组内并发、`target_n` 原子硬上限、同卡单活动组、client-ID no-resend（不重发）、签名前置精确白名单和浏览器零直连 Binance 仍有源码及测试证据。
- 现有 906 个后端测试、前端自检与 55 个 Harness 测试全部通过，但上述 finding 证明它们并不完整。
- `recvWindow=60000ms`、未采集 `X-MBX-ORDER-COUNT-*` 实时使用量、跨进程 worker 所有权、前端尚未展示 `worker_active` 等既有风险仍在；`68` 所列的无状态 `pause_task` 已被本轮证明不是不可达的 P3，而是实际并发 P1。其它风险不降低本轮 finding 的阻断性。
- 本阶段仍没有自动补腿、撤单、平仓、还币、转账或完整会计。即使修复后通过评审，第一笔真实订单仍需独立人类授权。

当前 Session ID: unavailable (current Codex runtime does not expose a provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/69-review-2.md
本地北京时间: 2026-07-26 14:07:11 CST
下一步模型: bookkeeper
下一步任务: validate and record this REWORK verdict, stop at human_escalation_required, and request written user authorization for any seventh bounded correction plus the account-health endpoint/policy decision

{
  "schema_version": 1,
  "stage_id": "2026-07-hedge-open-real-api-v1",
  "role": "final_reviewer",
  "model": "GPT-5 Codex",
  "verdict": "REWORK",
  "diff_fingerprint": "b9e1978eaffd047b7871b8721f511307e75fde68:604caada1043e8334f33b1cc73239f1cf6bb19017db1dc68374679cf6ac99ddd",
  "reviewer_prior_involvement": "design",
  "reviewer_prior_involvement_notes": "OpenAI/Codex authored the stage task/design/ADR and direction synthesis, the stale-range Review-2 REWORK at 50-review-2.md, and served as the earlier bookkeeper, but wrote no delivery or fix code. This review re-derived every current finding from the fixed 28c550d..b9e1978 diff, current sources, tests and new offline probes. The current bookkeeper Claude Opus 5 also authored backend Review-1 r2-r5. Mechanical comparison found only the disclosed user-authorization substitution between 66.fix_start_prompt and packet 67, but the pending 66/67/68 receipts leave the dual-hat execution/session evidence formally incomplete.",
  "reviewed_artifacts": [
    "AGENTS.md",
    "workflows/templates/stage-delivery.yaml#review-2",
    "docs/parallel-development-mode.md#R7-R12",
    "schemas/review-verdict.schema.json",
    "docs/product/PRD.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/00-task.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/06-direction-synthesis.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/10-design.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/11-adr.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/12-development-breakdown.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/15-immediate-loop-and-open-log-amendment.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/16-replacement-development-breakdown.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/17-opening-log-pagination-compatibility.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/21-task-local-runtime-and-manual-pause-amendment.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/24-user-authorized-final-guardian-fix.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/26-user-authorized-settlement-and-pause-fix.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/27-user-authorized-r4-repair.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/20-implementation-backend.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/20-implementation-frontend.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/40-fix-review-2-backend.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/40-fix-review-2-frontend.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/40-fix-review-1-backend-r2.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/41-fix-open-log-pagination-backend.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/41-fix-open-log-pagination-frontend.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/42-final-guardian-scanner-fix.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/44-fix-review-1-backend-r3.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/46-fix-review-1-backend-r4.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/30-review-1-backend.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/45-review-1-frontend-rfix.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/50-review-2.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/58-review-1-backend-r2.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/59-review-1-frontend-r2.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/64-review-1-backend-r3.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/66-review-1-backend-r4.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/68-review-1-backend-r5.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/46-review-2-routing-disclosure.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/60-test-output.txt",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/65-fix-review-1-backend-r3.dispatch.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/66-review-1-backend-r4.dispatch.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/67-fix-review-1-backend-r4.dispatch.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/68-review-1-backend-r5.dispatch.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/69-review-2.dispatch.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/status.json",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/70-handoff.md",
    "git diff --binary 28c550d87c1ca90983d5bde9c7102d42cffecd4e..b9e1978eaffd047b7871b8721f511307e75fde68",
    "backend/hedge_open_tasks/{domain.py,executor.py,service.py,store.py}",
    "backend/services/{hedge_open_live_client.py,hedge_preflight_provider.py,live_hedge_executor.py}",
    "backend/app/server.py and backend/config.py",
    "backend/tests/test_hedge_*.py and backend/tests/test_live_hedge_executor.py",
    "frontend/index.html and frontend/self-check.js",
    "scripts/validate-stage.py and scripts/tests/test_validate_stage_dispatch_protocol.py"
  ],
  "findings": [
    {
      "severity": "P1",
      "title": "Non-rate-limited single-leg outcomes bypass the approved consecutive-failure brake and leave exhausted tasks running",
      "file": "backend/hedge_open_tasks/store.py",
      "line": 697,
      "evidence": "The user amendment says a non-fatal single-leg final error is governed by the configurable failure rule, and replacement breakdown I-2 explicitly requires it to increment the consecutive-failure counter. _apply_task_counters instead leaves every single-leg outcome's fail and consecutive counters unchanged. A new offline probe produced three single-leg outcomes with scheduled_attempt_count=3, fail_count=0, consecutive_submission_failures=0 and status=running at target_n=3.",
      "impact": "A task with target_n greater than its pause threshold can continue opening more pairs after repeated naked-leg outcomes instead of pausing at the approved threshold. When the planned-attempt cap is exhausted without enough accepted pairs, the worker stops but the API/log still falsely says running/continue.",
      "recommendation": "Count non-rate-limited, non-fatal single-leg outcomes under the task-snapshotted consecutive-failure rule, preserve the explicit 429 no-counter exception, and mark the task/log completed after the final planned attempt settles unless another approved terminal state applies."
    },
    {
      "severity": "P1",
      "title": "Client-ID query classification closes malformed 2xx responses as absent and discards query-stage throttling",
      "file": "backend/services/live_hedge_executor.py",
      "line": 288,
      "evidence": "classify_query_response returns LEG_REJECTED for any 2xx dict without a valid orderId although the approved contract permits only explicit 404/-2013 absence to confirm non-acceptance. It also returns None for 429/-1003/418, so the service cannot observe rate_limited. New probes reproduced both results; existing tests currently assert these incorrect expectations.",
      "impact": "The service can finalize an order as never accepted while it may exist at Binance, then proceed to the next planned pair. During query throttling it automatically polls again instead of pausing this task for manual recovery, risking further throttling or an IP ban.",
      "recommendation": "Keep malformed 2xx query results unknown/querying, close only explicit absent signals, and propagate a typed query-rate-limit signal that persists a task-local pause without resending or resolving the ambiguous order."
    },
    {
      "severity": "P1",
      "title": "Late worker outcomes can overwrite manual deletion and resurrect a deleted task",
      "file": "backend/hedge_open_tasks/store.py",
      "line": 1451,
      "evidence": "pause_task performs an unconditional state update, while live network I/O occurs outside the task lock. A real-thread offline probe blocked a fake POST, manually deleted the task, then released a late 429 result: the durable state changed from deleted to paused with pause_reason=rate_limited. Review-1 r5 treated the missing state guard as production-unreachable, but the current immediate dispatch path already reaches it; propagating query-stage 429 would add another reachable path.",
      "impact": "A human's sticky delete decision can be overwritten by a delayed worker result, making the task appear paused and restartable. Equivalent unguarded fatal-result paths can also corrupt higher-priority terminal or manual states.",
      "recommendation": "Make worker-driven pause and fatal-stop transitions conditional and atomic so deleted, done, stopped and other approved higher-priority states are preserved. Record the late attempt/event without changing protected task state, and add real-thread race tests for delete versus late rate-limit and fatal results."
    },
    {
      "severity": "P1",
      "title": "A crash after the last leg becomes terminal can leave an attempt permanently unsettled and busy-loop its worker",
      "file": "backend/hedge_open_tasks/service.py",
      "line": 1057,
      "evidence": "Leg terminalization and attempt finalization are separate transactions. If both legs are terminal while pair_outcome remains NULL, recovery sees no non-terminal leg, but prepare_attempt refuses a new pair because the unresolved attempt still exists. A new offline probe constructed this durable state; one recovery worker round left pair_outcome NULL and returned continue.",
      "impact": "Real fills can remain outside pair counters, threshold transitions and audit logs forever. A running task can spin without pacing, while non-running tasks may never receive any recovery worker.",
      "recommendation": "Make last-leg terminalization plus pair settlement atomic/reentrant, or add one-shot recovery of pair_outcome-NULL attempts whose two legs are terminal. Prove idempotent settlement, zero resend, zero extra pair and no busy loop across all task statuses and the rate-limited no-counter path."
    },
    {
      "severity": "P1",
      "title": "Live preflight still omits approved account-health facts and Spot MIN_NOTIONAL fallback",
      "file": "backend/services/hedge_preflight_provider.py",
      "line": 48,
      "evidence": "The approved breakdown and prior Review-2 required accountStatus/uniMMR health plus NOTIONAL-or-MIN_NOTIONAL completeness. The live client has no GET /papi/v1/account allowlist entry and PreflightSnapshot has no account-health fields. _parse_spot_filters reads only NOTIONAL; a new probe with only MIN_NOTIONAL produced an empty notional record that does not fail closed. Later bounded-fix packets also call the seven-endpoint allowlist frozen, leaving an unresolved contract conflict rather than an explicit user waiver.",
      "impact": "An abnormal Portfolio Margin account can still pass local authorization, and symbols exposing Spot MIN_NOTIONAL can bypass the local minimum-notional gate.",
      "recommendation": "Obtain a written user decision resolving the seven-endpoint freeze. The safe implementation adds only exact read-only GET /papi/v1/account, requires NORMAL and complete parseable health facts under a user-approved policy, supports both Spot NOTIONAL and MIN_NOTIONAL, and fails closed on missing/malformed facts without inventing a uniMMR threshold."
    },
    {
      "severity": "P1",
      "title": "Pending formal receipts and the review_1 root status invalidate the current Review-2 preflight",
      "file": "reports/agent-runs/2026-07-hedge-open-real-api-v1/67-fix-review-1-backend-r4.dispatch.md",
      "line": 1,
      "evidence": "Dispatches 66, 67 and 68 all still say status: pending with empty timestamps and pending session IDs although their outputs exist; status.json.session_receipts does not seal these executions. R9's legacy exception cannot apply to present-but-incomplete receipt blocks. The stage root status is review_1, while the review-2 workflow requires review_2. The pre-review validator nevertheless passed and printed status=review_1. Prompt comparison found only the disclosed authorization substitution, but prompt fidelity is not an execution receipt.",
      "impact": "The latest backend Review-1 ACCEPT and sixth fix are not formally attributable to recorded human-operated executions or verifiable fresh sessions, and Review-2 was dispatched before its workflow state precondition was met.",
      "recommendation": "Backfill only real operator evidence; if unavailable, rerun the formal nodes. Then advance the root state to review_2, add validator coverage for completed current receipts and review-2 status, recompute/rebind as required, and rerun the gates. Never invent commands, timestamps or session IDs."
    }
  ],
  "required_fixes": [
    "Apply the approved consecutive-failure rule to non-rate-limited, non-fatal single-leg outcomes and align planned-attempt exhaustion with completed task/log state.",
    "Keep malformed 2xx client-ID query responses unknown; close only explicit absent signals; propagate query-stage 429 into a durable task-local manual pause without resending.",
    "Add atomic state guards to every worker-driven pause or fatal-stop transition so late results cannot overwrite deleted, done, stopped or other higher-priority manual states.",
    "Atomically or recoverably settle attempts whose two legs are terminal while pair_outcome is NULL, with restart/idempotency/no-busy-loop tests.",
    "Support Spot MIN_NOTIONAL fail-closed and obtain a written user decision before changing the frozen endpoint set or account-health policy.",
    "Repair or rerun the missing human-operated 66/67/68 dispatch receipts, session evidence and review_2 state transition; strengthen validator coverage.",
    "Run focused reverse tests, all backend tests, frontend self-check, Harness tests, git diff --check and the stage validator on a new committed fixed fingerprint."
  ],
  "next_action": "human_escalation_required",
  "fix_start_prompt": "[HARNESS-EXECUTOR-CONTRACT v1]\n你是 2026-07-hedge-open-real-api-v1 的后端返工实现者候选人。禁止调用、启动或转派任何其他正式模型会话或 adapter。当前 rework_count=6/max_rework=6；在用户以书面形式同时授权“第 7 次有界代码变更”并决定账户健康端点/政策之前，本 prompt 不得执行，必须停止并报告 human authorization missing。bookkeeper 也必须先依据真实 operator 记录修复或重跑 66/67/68 的正式回执，不得编造命令、时间或 Session ID。\n\n授权满足后，先逐字读取：reports/agent-runs/2026-07-hedge-open-real-api-v1/69-review-2.md（本评审全文和末尾 JSON）、15-immediate-loop-and-open-log-amendment.md、16-replacement-development-breakdown.md（I-2/A-3/A-5）、21-task-local-runtime-and-manual-pause-amendment.md、24-user-authorized-final-guardian-fix.md、26-user-authorized-settlement-and-pause-fix.md、27-user-authorized-r4-repair.md、68-review-1-backend-r5.md、固定源码和测试。起点指纹是 b9e1978eaffd047b7871b8721f511307e75fde68:604caada1043e8334f33b1cc73239f1cf6bb19017db1dc68374679cf6ac99ddd；bookkeeper 会在修复后创建新的 committed 指纹。绝不读取凭据、绝不连接 Binance、绝不发送真实 POST、绝不启用 live/Start、绝不 commit、绝不修改 status.json/70-handoff.md/评审报告/用户授权文件。\n\n必须修复：\n1. 非限频、非致命 single_leg 按用户批准的连续提交失败规则增加 fail/consecutive 计数，达到任务快照阈值即暂停；429 attempt 继续免计数。最后一笔计划 attempt 结算后，若没有 paused/stopped/deleted 等更高优先级状态，将 task 与 entries.next_action 一致标为 done/completed。\n2. classify_query_response：仅 HTTP 404 或 Binance -2013 确认 absent；2xx 缺少有效 orderId 保持 UNKNOWN_QUERYING。查询阶段 429/-1003/418 必须保留 typed rate-limit signal，由该任务 worker 持久化 paused+rate_limited、保留未决腿、退出等待人工恢复；绝不重发 POST。\n3. 给 worker 驱动的 pause/fatal-stop 写入增加原子状态守卫：迟到的 429、insufficient/fatal 或其它结果不得覆盖 deleted/done/stopped 等高优先级状态，也不得清空人工原因；可记录 attempt/event，但受保护 task 状态保持不变。新增真实线程竞态回归，至少覆盖人工 delete 与迟到 rate-limit/fatal。\n4. 消除“最后一腿 terminal 已提交、pair_outcome 仍 NULL”的崩溃缝隙：采用可重入原子 store 操作，或一次性恢复扫描该任务的 terminal-but-unsettled attempt 并幂等 finalize。不得新增周期性全局 guardian/scanner/timer；不得忙循环；不得开新组或重复计数。\n5. Spot filter 同时解析 NOTIONAL 与 MIN_NOTIONAL，二者均缺失/畸形时 preflight_incomplete，零 attempt/POST/count。账户健康按用户书面选择执行：若选择新增端点，只能把精确只读 GET /papi/v1/account 加入 allowlist，要求 accountStatus literal NORMAL，uniMMR 存在且可解析，并只应用用户明确批准的政策；不得自行发明风险阈值。若用户选择合同豁免，implementer 不得改合同，由 bookkeeper 先落盘批准的修正案后再重出 packet。\n6. 增加确定性反向回归：连续 single_leg 触发阈值；计划数耗尽转 completed；畸形 2xx 不闭合；query 429 暂停且零重发；delete 与迟到 rate-limit/fatal 不复活任务；terminal legs + NULL outcome 的重启恢复覆盖 running/paused/stopped/deleted/done 与 429 免计数；Spot MIN_NOTIONAL；账户健康缺失/异常 fail closed。每条先证明缺陷代码会失败，再验证修复转绿。\n\n允许修改仅限 backend/hedge_open_tasks/{domain.py,service.py,store.py}、backend/services/{live_hedge_executor.py,hedge_preflight_provider.py,hedge_open_live_client.py}、直接相关 backend/tests/test_hedge_*.py 与 test_live_hedge_executor.py，以及新实现报告 reports/agent-runs/2026-07-hedge-open-real-api-v1/71-fix-review-2-backend-r7.md 和 60-test-output.txt（只追加真实输出）。frontend/**、docs/**、PRD、设计/ADR、用户修正案、reports/api-samples/**、scheduler.py、环境/凭据/网络配置禁止修改；若账户健康选择需要合同修订，由 bookkeeper 另行处理，implementer 停止。\n\n精确自测：\n.venv/bin/python -m pytest backend/tests/test_hedge_task_local.py backend/tests/test_hedge_review2_regressions.py backend/tests/test_hedge_service.py backend/tests/test_hedge_store.py backend/tests/test_hedge_domain.py backend/tests/test_hedge_api.py backend/tests/test_hedge_open_live_client.py backend/tests/test_live_hedge_executor.py backend/tests/test_hedge_purity.py -q\n.venv/bin/python -m pytest backend/tests -q\nnode frontend/self-check.js\n.venv/bin/python -m pytest scripts/tests/test_validate_stage_dispatch_protocol.py -q\ngit diff --check\n\n把 changed files、每条修复前反向失败/修复后证据、零网络/零凭据、H-1 无全局 guardian 回归、剩余风险写入 71-fix-review-2-backend-r7.md，原始输出追加到 60-test-output.txt，然后停止等待 bookkeeper；不 commit、不派发评审、不自行宣称验收。"
}

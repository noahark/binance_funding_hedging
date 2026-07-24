# Review-2（最终复核）

结论：`REWORK`（需要返工）。当前固定提交区间不能进入真实开单。最严重的问题是：任务把 `target_n` 当作“成功受理组数”，而用户批准的含义是“计划尝试组数”。只要出现单腿受理或确认失败，系统就会继续补发；单腿受理又不增加失败计数，因此 `target_n=1` 的任务可以持续产生新的真实订单组，形成无上限敞口。

## 审查身份与锚点

- 最终评审者：GPT-5 Codex；OpenAI/Codex 曾参与本阶段的方向综合和阶段设计，但没有编写交付代码或修复代码。本次按强评审者披露路径执行，最高既往参与类型记录为 `design`（阶段设计）。路由证据见 `46-review-2-routing-disclosure.md` 和 `48-review-2-harness-rebind.md`。
- 固定区间：`28c550d87c1ca90983d5bde9c7102d42cffecd4e..01d3a4712c89efab79772ce2e5ee2ba415e1e43c`；没有用移动 `HEAD` 替代。
- 重新计算的固定指纹与派发值一致：`01d3a4712c89efab79772ce2e5ee2ba415e1e43c:c3368f63670e896cbe585293c4ff7261ba55c165346efd4ea27f672be1b91cff`。
- 固定头之后没有 backend/frontend/scripts/docs 的业务变更；工作树在审查开始时干净。

## 实际检查与离线验证

已阅读派发要求列出的工作流、PRD（产品需求文档）、架构、用户执行政策、方向综合、设计、ADR（架构决策记录）、开发拆分、R4 对账、实现/修复报告、两轮 Review-1（第一轮代码审查）、路由披露、门禁证据、固定 diff（差异）、相关源代码及测试。没有读取凭据，没有启用 Start/live（启动/真实执行），没有连接 Binance，也没有发送任何真实请求。

只读回归结果：

- `.venv/bin/python -m pytest backend/tests -q`：`862 passed in 44.33s`。
- `node frontend/self-check.js`：全部自检通过。
- `.venv/bin/python -m pytest scripts/tests/test_validate_stage_dispatch_protocol.py -q`：`55 passed in 1.01s`。

另外用内存 SQLite（数据库）和注入式假 HTTP（网络）做了确定性复现：

1. `target_n=1` 的首组结果为 `single_leg`（只受理一条腿）后，`scheduled_attempt_count=1`、`accepted_pair_count=0`、状态仍为 `running`（运行中），任务仍被判为可调度；再执行一组后，计划尝试数变成 `2`。连续制造 5 个单腿结果后，计划尝试数为 `5`、连续失败为 `0`、任务仍运行且仍可调度。
2. 任务保存的旧过滤器计算 `q_common=0.005`；新鲜过滤器把共同网格改为 `0.002` 后，新鲜计算结果为 `0.004` 且可通过预检。当前服务只读取新结果的布尔通过值，随后仍用旧值 `0.005` 下单。
3. 在估值价格和订单频率信息均缺失时，`compute_preflight`（预检计算）返回 `rejection=None`、`balance_ok=None`；当前 live 门禁把它当作可发送。
4. 假传输捕获的 `/papi/v1/margin/order` 签名正文包含 `endpoint=/papi/v1/margin/order`。该字段是本地记录元数据，不在冻结的交易所请求参数合同中。
5. 带签名错误正文的 `400/401/403/404` 查询都被归为 `TERMINAL_RECORDED`（已终结且确定未受理）；`CANCELED`（已取消）状态反而被判为非终结。

现有测试全部通过，说明这些真实写入边界缺少覆盖，不能抵消上述复现。

## Findings（问题）

### P0 — `target_n` 上限按成功数而不是计划尝试数执行，可无限补发真实订单

`backend/hedge_open_tasks/store.py:442-455` 用 `success_count < target_n` 选择任务，`store.py:459-560` 的发送前原子复核仍只检查成功数，随后无条件增加 `scheduled_attempt_count`。`backend/hedge_open_tasks/service.py:371-393` 的批量路径同样按成功数循环。单腿受理在 `store.py:616-621` 明确不增加成功或失败计数，所以不会触发上限或连续失败暂停。并且 `service.py:365-369` 的手动 fill-once（执行一次）不受 scheduler（调度器）锁保护；并发 HTTP 与 scheduler 可以在成功数更新前各自通过准备事务。

实际影响：用户要求尝试 1 组，系统可能提交 2 组乃至无限多组。尤其单腿场景会在已有裸露仓位时继续开新仓，直接突破用户指定的订单数量和风险边界。这是阻止 live 的 P0。

### P1 — 新鲜预检发生在持久化之后，而且新鲜数量/快照被丢弃

`backend/hedge_open_tasks/service.py:582-638` 先从任务旧快照构造请求并调用 `prepare_attempt`（准备尝试），到 `631-635` 才执行新鲜预检；`_fresh_preflight_ok` 在 `566-580` 只返回布尔值，丢弃新算出的 `q_common`、仓位模式和快照。若新鲜预检失败，live executor（真实执行器）还会被送入 `_dispatch_simulated`（模拟执行）分支；它没有 `execute` 方法，异常会被解析为已确认失败，错误消耗一次计划尝试并可能暂停任务，尽管根本没有 POST。

实际影响：市场过滤器变化后，持久记录和真实请求都可能使用过期数量；预检读失败也会伪造“交易所两腿拒绝”。这同时破坏“新鲜预检 → 精确持久化 → POST”和“只有确认两腿均未受理才计失败”两条冻结合同。

### P1 — live 预检不完整时仍可放行

`backend/services/hedge_preflight_provider.py:240-266` 虽然读取价格和订单频率，但 `257` 的完整性判断没有要求二者存在；`backend/hedge_open_tasks/domain.py:448-455,525-536` 在价格缺失时跳过最小名义金额和正向余额判断，服务又接受 `balance_ok=None`。`hedge_preflight_provider.py:203-219` 将除字面量 `true` 外的缺失/畸形仓位模式都当成 `BOTH`（单向持仓）。现有 provider（预检提供器）没有读取/验证 `accountStatus=NORMAL`（账户正常）、账户健康/`uniMMR`，没有确认 symbol（交易对）可交易；现货过滤器解析 `48-75` 只接受 `NOTIONAL`，忽略 `MIN_NOTIONAL`；`domain.py:352-370` 也没有按每个 min/max/step 约束分别回退 `LOT_SIZE`。传输结果 `backend/services/hedge_open_live_client.py:82-97,145-170` 只保留 `Retry-After`，没有保存返回的订单计数/权重响应头，无法执行批准的当前频率门禁。

实际影响：账户异常、估值/限频事实未知、过滤器不完整或仓位模式畸形时仍可能真实下单；数量、余额和最小名义金额判断可能失真，默认关闭门禁不再是 fail-closed（信息不全即拒绝）。

### P1 — 实际签名 POST 带入内部 `endpoint` 字段

`backend/hedge_open_tasks/executor.py:105-143` 把 `endpoint` 放入 spot/perp 请求参数；`backend/services/live_hedge_executor.py:386-410` 直接复用这些字典；`backend/services/hedge_open_live_client.py:172-192` 又对完整字典签名并发送。假传输已捕获到正文中的 `endpoint`。现有 transport 测试用手写的最小参数调用 client，没有覆盖 executor 到 client 的完整链路。

实际影响：真实请求形状违反批准的 PAPI/UM 参数合同，交易所可能拒绝两腿，导致“真实开单”功能不可用，并与持久化的 would-send（计划发送）证据不一致。

### P1 — 查询轮询既会停摆/阻塞，又会把鉴权错误误判成订单不存在

`backend/hedge_open_tasks/service.py:495-522` 在 Start 关闭、冷却中或没有可调度任务时直接返回；`_reconcile_pending`（未完成腿对账）只在本轮完成发送后执行。因此，最后一组已受理但仍为 `NEW/PARTIALLY_FILLED`（新建/部分成交）、任务已 done（完成），或人工关闭 Start 时，未终结腿会永久失去轮询。对账本身在 `service.py:742-787` 串行做所有阻塞 GET，并且 tick 会等待所有工作线程 `join`（汇合，`524-550`）；单次 transport timeout（传输超时）为 10 秒，慢查询会拖住下一秒计划。`backend/services/live_hedge_executor.py:233-277` 把所有非限频 4xx 都当作订单确定不存在，连签名/时间戳/权限错误也会闭合成拒绝；`service.py:789-801` 又漏掉终态 `CANCELED`。

实际影响：已真实受理的订单可能停止跟踪，或者因查询本身失败而被错误记成“从未受理”；下一秒开单也可能被历史查询阻塞。这会错误计算失败/单腿敞口，并破坏 no-resend（不盲目重发）所依赖的可靠 client-ID 查询链路。

### P1 — 实际成交金额、部分成交、手续费与残差会丢失

`backend/hedge_open_tasks/service.py:708-740` 把 live executor 返回的 `cumulative_quote`（累计成交金额）丢弃；`backend/hedge_open_tasks/store.py:562-575` 仅在 `FILLED` 且存在 `avg_price` 时用数量乘均价重建金额，否则写 0。`store.py:1117-1130` 的持仓聚合只纳入 `exchange_status == FILLED`，已取消/过期但有部分成交量的腿完全不计；手续费字段始终以 `None` 写入。现有实现也没有从两腿实际累计量生成并展示 residual（数量残差）。

实际影响：持仓数量、加权均价、单腿残差和审计记录可与交易所真实成交不一致。用户看到的风险仓位可能偏小甚至为零，无法据此进行人工处理。

### P1 — 前端把仍会继续下单的任务显示成“已暂停”

`frontend/index.html:3626-3636` 只要存在 `leg_exposure` 就显示“任务已暂停，等待人工处理”，但后端冻结合同和 `store.py:616-621` 明确规定单腿只提示、不阻塞调度。`frontend/index.html:3433-3436` 又沿用累计失败 `>3` 推导终止，和后端“按任务阈值、连续失败达到 `>=` 即暂停”不一致；`3654` 仍硬编码 `/3`。创建处 `3474,3514` 仍把 `target_n` 写成“成功开单次数”。

实际影响：操作者可能在页面明确显示“已暂停”时误以为不会继续开单，实际上后端仍每秒提交；同时按钮禁用和失败状态也可能与服务端相反。这会放大 P0 的裸露仓位风险。

### P2 — main 同步证据记录了不存在的完整提交 SHA

`reports/agent-runs/2026-07-hedge-open-real-api-v1/status.json:493` 记录 `9a0fabf7d436f0806229c8eefa6e4f7ed04b5f43`，该对象不存在；固定 head `01d3a47` 的真实第二父提交是 `9a0fabf74f004f4a34d8befd3676042963b5e66f`。短 SHA 文本 `9a0fabf` 恰好掩盖了错误。Harness（流程护栏）兼容代码及 55 个定向测试本身满足“仅在完全无回执区块时回退；已有坏回执仍失败”的主要要求，但这条阶段来源证据必须更正并重新封存。

实际影响：固定 diff 指纹仍能重算，但 main 同步的机器可验证来源链是假的；后续审计或门禁按完整 SHA 查证会失败。

## 必须修复后才能重审

1. 把 `target_n` 的唯一硬上限改为“计划尝试组数”；选择任务和发送前事务都以 `scheduled_attempt_count < target_n` 原子检查。失败、单腿、并发 fill-once/scheduler 都不得创建第 `N+1` 条 attempt（尝试）或 POST；成功数只作统计。
2. 每组必须先完成完整新鲜预检，再用该次预检的精确 `q_common`、仓位模式、过滤器/账户/余额/估值/限频证据创建不可变 attempt，最后 POST。预检失败不得创建 attempt、不得调用模拟 executor、不得计为两腿拒绝。
3. 补齐 fail-closed 预检：严格确认单向模式、账户健康与交易状态；价格、余额、过滤器、每约束回退、最小名义金额和当前订单限频事实缺一即不发送；保留并使用经批准的安全响应头，不记录秘密。
4. 分离“本地记录元数据”和“交易所 wire（线上传输）参数”，保证 executor→client 完整链路签名正文只有批准字段，并增加精确正文测试。
5. 将 client-ID 查询做成独立、限频、不会阻塞下一秒开单的恢复/轮询职责；即使 Start 关闭、无可调度任务或任务已完成，也要继续跟踪既有未终结腿。只有明确的订单不存在业务码才能确认未受理；鉴权/签名/时间戳/权限/5xx/timeout 保持未知；正确终结 `CANCELED/EXPIRED/REJECTED/FILLED` 并保留部分成交。
6. 从 POST/GET 结果端到端保存实际累计基础币、累计报价金额、均价、手续费（可得时）、部分成交和两腿残差；持仓聚合必须纳入任何大于零的实际成交量，而不是仅按 `FILLED` 字面状态。
7. 前端改成计划尝试语义，并按服务端真实状态、任务级连续失败阈值和“单腿提示但继续调度”的批准政策展示；禁止再显示虚假的“任务已暂停”。
8. 由 bookkeeper（阶段记账者）更正 `status.json.main_syncs` 的完整 main SHA，更新相应 rebind（重新绑定）证据/校验结果，并在新提交后按标准方案重新计算指纹；实现者不得自行改写审查结论。

## Residual risks（修复后仍需明确接受的风险）

- 冻结政策本身允许单腿提示后继续调度，不自动取消、补单、平仓或修复；即使实现正确，真实资金仍可能在人工介入前扩大单腿敞口，只是不会超过用户批准的计划组数。
- 本次按安全要求没有访问真实 Binance 私有接口；修复后的参数兼容、账户字段和限频响应头仍需由人工授权的安全环境提供脱敏证据，不能以模拟测试替代全部事实验证。
- 当前 10 秒请求超时与 `recvWindow=60000`（接收窗口 60 秒）仍偏宽；修复应证明独立查询不会耗尽线程/频率，但具体收紧值属于后续风险决策。
- 本阶段仍不包含自动取消、平仓、转账、还币或完整会计；页面必须继续把这些能力标为不存在，而不能暗示自动处置。

当前 Session ID: unavailable (Codex runtime does not expose a provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/50-review-2.md
本地北京时间: 2026-07-24 13:42:29 CST
下一步模型: bookkeeper
下一步任务: validate this REWORK verdict, preserve the raw findings, prepare the bounded fix dispatch, then recompute committed evidence and re-enter Review-1/Review-2 as required

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-hedge-open-real-api-v1",
  "role": "final_reviewer",
  "model": "GPT-5 Codex",
  "verdict": "REWORK",
  "diff_fingerprint": "01d3a4712c89efab79772ce2e5ee2ba415e1e43c:c3368f63670e896cbe585293c4ff7261ba55c165346efd4ea27f672be1b91cff",
  "reviewer_prior_involvement": "design",
  "reviewer_prior_involvement_notes": "OpenAI/Codex participated in direction synthesis and stage design but wrote no delivery or fix code. The strong-reviewer disclosure route and ineligibility of code-author providers are recorded in reports/agent-runs/2026-07-hedge-open-real-api-v1/46-review-2-routing-disclosure.md and 48-review-2-harness-rebind.md.",
  "reviewed_artifacts": [
    "AGENTS.md",
    "workflows/templates/stage-delivery.yaml#review-2",
    "docs/parallel-development-mode.md#R7-R9-Review-2",
    "schemas/review-verdict.schema.json",
    "docs/product/PRD.md",
    "docs/architecture/ARCHITECTURE.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/00-task.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/04-user-execution-policy.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/05-cadence-resolution.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/06-direction-synthesis.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/10-design.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/11-adr.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/12-development-breakdown.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/13-r4-diff-reconciliation.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/14-r4-verification.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/20-implementation-backend.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/20-implementation-frontend.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/40-fix-backend-r4.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/40-fix-frontend-r1.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/30-review-1-backend.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/45-review-1-frontend-rfix.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/46-review-2-routing-disclosure.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/47-pre-review-gate-hold.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/48-review-2-harness-rebind.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/60-test-output.txt",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/status.json",
    "git diff --binary 28c550d87c1ca90983d5bde9c7102d42cffecd4e..01d3a4712c89efab79772ce2e5ee2ba415e1e43c",
    "backend/hedge_open_tasks/{domain.py,executor.py,scheduler.py,service.py,store.py}",
    "backend/services/{hedge_open_live_client.py,hedge_preflight_provider.py,live_hedge_executor.py}",
    "backend/tests/test_hedge_*.py and backend/tests/test_live_hedge_executor.py",
    "frontend/index.html and frontend/self-check.js",
    "scripts/validate-stage.py and scripts/tests/test_validate_stage_dispatch_protocol.py"
  ],
  "findings": [
    {
      "severity": "P0",
      "title": "target_n is enforced against accepted successes, allowing unlimited replacement attempts and live exposure",
      "file": "backend/hedge_open_tasks/store.py",
      "line": 442,
      "evidence": "list_eligible_tasks uses success_count < target_n and prepare_attempt rechecks success_count, while scheduled_attempt_count is only incremented. A deterministic SQLite reproduction with target_n=1 remained eligible after one single-leg attempt and reached scheduled_attempt_count=5 after five single-leg attempts. service.post_fill_once is outside the scheduler lock, so concurrent manual and scheduled calls can also prepare beyond the target before counters resolve.",
      "impact": "A task can submit more order pairs than the user authorized; repeated single-leg acceptance can create unbounded naked exposure because it increments neither success nor consecutive failure.",
      "recommendation": "Use scheduled_attempt_count as the atomic hard cap in both selection and prepare_attempt; make every dispatch entry point share that transaction-level cap, never create or POST attempt N+1, and treat success/failed/single-leg only as outcome metrics."
    },
    {
      "severity": "P1",
      "title": "Fresh preflight runs after durable preparation and its exact quantity/snapshot are discarded",
      "file": "backend/hedge_open_tasks/service.py",
      "line": 566,
      "evidence": "_dispatch_one_for_task builds and persists request shapes from task.q_common and task.preflight_snapshot at lines 592-614, then _fresh_preflight_ok runs at 631-635 and returns only a bool. Offline reproduction produced persisted q_common 0.005 versus fresh q_common 0.004. On a fresh-preflight failure, live mode falls into _dispatch_simulated and can record an executor_exception as a confirmed failed pair without any POST.",
      "impact": "Real orders may use stale filter quantities and audit snapshots; read failures can consume attempts and trip the failure pause despite no exchange submission.",
      "recommendation": "Compute a complete fresh preflight first, persist that exact result and wire shapes in one transaction, then send. An incomplete/rejected preflight must create no attempt, make no POST, invoke no simulation, and change no exchange-failure counter."
    },
    {
      "severity": "P1",
      "title": "Incomplete live preflight facts are accepted instead of failing closed",
      "file": "backend/services/hedge_preflight_provider.py",
      "line": 240,
      "evidence": "get_snapshot does not require est_price or rate_limit, compute_preflight skips notional/balance checks without a price, and the service accepts balance_ok=None. Position-mode parsing accepts missing/malformed dualSidePosition as BOTH; account health, symbol trading status, current order-limit headers, spot MIN_NOTIONAL, and per-constraint LOT_SIZE fallback are not fully validated. Offline reproduction with missing price and rate limit returned rejection=None and balance_ok=None.",
      "impact": "Live POST can be authorized with unknown account health, capacity, price, balance requirement, or invalid filters/position mode, so the promised default-deny safety boundary is bypassable.",
      "recommendation": "Require every approved factual preflight field, exact one-way mode, normal account/symbol health, correct filter fallback and current rate capacity; any missing or malformed fact must block before durable attempt creation. Preserve only sanitized rate headers needed for enforcement."
    },
    {
      "severity": "P1",
      "title": "Internal endpoint metadata is included in the signed exchange POST body",
      "file": "backend/hedge_open_tasks/executor.py",
      "line": 105,
      "evidence": "Both order builders put endpoint into the parameter dict, LiveHedgeExecutor passes it through, and HedgeOpenLiveClient signs all params. An injected fake transport captured endpoint=/papi/v1/margin/order in the actual form body; existing client tests use hand-built params and miss this end-to-end shape.",
      "impact": "The real request violates the frozen PAPI/UM wire contract and may be rejected by the exchange, making live open unreliable and its recorded request evidence misleading.",
      "recommendation": "Separate record metadata from wire parameters and add executor-to-client tests that assert the exact signed keys for both legs, including absence of endpoint and every unapproved field."
    },
    {
      "severity": "P1",
      "title": "Pending-order reconciliation can stop or block scheduling and misclassifies query errors",
      "file": "backend/hedge_open_tasks/service.py",
      "line": 495,
      "evidence": "tick returns before _reconcile_pending when Start is off, cooldown is active, or no task is eligible; reconciliation is a serial blocking loop reached only after joined dispatch workers. classify_query_response treats every non-rate-limit 4xx as confirmed absent, while _query_verdict_terminal omits CANCELED. Offline classification mapped signature-error 400/401/403 to terminal rejected and CANCELED to non-terminal.",
      "impact": "Accepted NEW/PARTIALLY_FILLED orders may never be observed after the task finishes, auth failures can be recorded as no order, and historical GET latency can prevent the next-second pair cadence.",
      "recommendation": "Run bounded rate-aware reconciliation independently of new dispatch and Start, keep ambiguous auth/permission/timestamp/transport failures querying without resend, close only explicit absent evidence, and handle all terminal exchange statuses while preserving partial fills."
    },
    {
      "severity": "P1",
      "title": "Live cumulative quote, partial fills, fees, and residual exposure are lost from accounting",
      "file": "backend/hedge_open_tasks/service.py",
      "line": 708,
      "evidence": "_dispatch_to_outcome drops LegDispatch.cumulative_quote, store reconstructs quote only for FILLED plus avg_price, fees are persisted as None, and aggregate_positions ignores every non-FILLED status even when cumulative_base_qty is positive. No end-to-end residual derived from actual leg quantities is exposed.",
      "impact": "The workstation can understate real position quantity/notional and display incorrect average prices or zero exposure after partial/canceled fills, defeating manual risk handling and auditability.",
      "recommendation": "Persist and project exchange cumulative quantities/quote, fee data when available, terminal partial fills, weighted averages, and actual two-leg residuals without gating subsequent scheduling."
    },
    {
      "severity": "P1",
      "title": "Frontend claims a single-leg task is paused while the backend continues submitting",
      "file": "frontend/index.html",
      "line": 3626,
      "evidence": "The exposure notice says the task is paused and controls derive a legacy fail_count > 3 termination, but the approved backend behavior records single-leg exposure as advisory and keeps running. The UI also hard-codes failure /3 and labels target_n as successful-order count.",
      "impact": "An operator can reasonably believe order submission has stopped while the service continues each second, compounding the P0 exposure risk; UI state and controls can also disagree with the API.",
      "recommendation": "Render target_n as planned attempts, use server status and task-specific consecutive threshold, and state plainly that single-leg exposure is advisory and scheduling continues unless the actual status is paused."
    },
    {
      "severity": "P2",
      "title": "Stage main-sync provenance contains a nonexistent full commit SHA",
      "file": "reports/agent-runs/2026-07-hedge-open-real-api-v1/status.json",
      "line": 493,
      "evidence": "status records 9a0fabf7d436f0806229c8eefa6e4f7ed04b5f43, which git cannot resolve. Commit 01d3a47 has second parent 9a0fabf74f004f4a34d8befd3676042963b5e66f. The shared seven-character prefix hid the mismatch.",
      "impact": "The stage fingerprint itself recomputes, but the recorded main-sync provenance is not machine-verifiable and will fail exact audit lookup.",
      "recommendation": "Have the bookkeeper correct and reseal the exact full SHA and related rebind evidence, rerun the validator, and recompute the committed stage fingerprint after fixes."
    }
  ],
  "required_fixes": [
    "Atomically cap planned attempts at target_n using scheduled_attempt_count across scheduler and manual dispatch; never replace failed or single-leg attempts.",
    "Run complete fresh fail-closed preflight before durable preparation, and persist/send the exact fresh q_common and snapshot without counting local preflight failures as exchange failures.",
    "Validate account and symbol health, exact one-way mode, price/balance/notional/filter fallback, and current rate-limit facts before any live POST.",
    "Remove endpoint and every internal metadata key from signed PAPI/UM wire bodies and cover the full executor-to-client parameter path.",
    "Decouple bounded client-ID reconciliation from dispatch cadence/Start and correct absent-versus-ambiguous and terminal-status classification.",
    "Preserve actual cumulative quote/base, partial fills, fees when available, weighted averages, and residual exposure through persistence and UI projection.",
    "Align Chinese UI labels, pause notices, counters, thresholds, and controls with planned-attempt and advisory single-leg semantics.",
    "Correct the nonexistent full main-sync SHA in stage evidence through the bookkeeper and re-enter all required committed review gates."
  ],
  "residual_risks": [
    "The approved policy intentionally continues scheduling after a single-leg exposure and has no automatic repair; bounded target_n limits but does not remove real naked-exposure risk.",
    "No real Binance private request was made in this review, so corrected live field compatibility and rate-limit headers still require authorized, sanitized factual evidence.",
    "The current 10-second timeout and 60000 ms recvWindow remain broad and need operational load/rate evidence after reconciliation is decoupled.",
    "Cancel, close, repay, transfer, automatic remediation, and full accounting remain explicitly outside this stage."
  ],
  "fix_start_prompt": "[HARNESS-EXECUTOR-CONTRACT v1]\n你是 2026-07-hedge-open-real-api-v1 的返工实现者。禁止调用、启动或转派任何其他模型/adapter。先逐字读取原始终审 reports/agent-runs/2026-07-hedge-open-real-api-v1/50-review-2.md（最后 JSON 也是原始 verdict），以及 04-user-execution-policy.md、05-cadence-resolution.md、06-direction-synthesis.md、10-design.md、11-adr.md、12-development-breakdown.md；固定被审指纹是 01d3a4712c89efab79772ce2e5ee2ba415e1e43c:c3368f63670e896cbe585293c4ff7261ba55c165346efd4ea27f672be1b91cff。\n\n按顺序修复：1) target_n 是计划尝试组数硬上限；list/prepare/manual/scheduler 统一由事务原子检查 scheduled_attempt_count < target_n，失败或 single_leg 不补发，任何并发都不得创建/POST 第 N+1 组。2) 每组先完成完整新鲜预检，再把该次精确 q_common、仓位模式、过滤器/账户/余额/价格/限频快照与两腿 client ID、wire shape 一次持久化，随后才 POST；预检失败不建 attempt、不模拟、不计交易所失败。严格检查账户/交易对正常、dualSidePosition 字段字面 false、价格/余额/NOTIONAL 或 MIN_NOTIONAL、MARKET_LOT_SIZE 每个约束单独回退 LOT_SIZE，以及当前订单限频事实。3) 记录元数据与 wire 参数分离；签名 body 禁止 endpoint 等内部字段。4) client-ID 对账独立于新下单和 Start，限频且不阻塞下一秒；只有明确 absent 业务证据才判未受理，鉴权/签名/时间戳/权限/5xx/timeout 保持未知，CANCELED/EXPIRED/REJECTED/FILLED 正确终结并保留部分成交。5) 端到端保留 cumulative base/quote、均价、可得手续费、部分成交和两腿 residual，持仓聚合纳入任何实际成交。6) 前端改为计划尝试语义；单腿必须明确显示‘提示但仍继续调度’，状态/按钮只服从后端 status 和任务级连续失败阈值。禁止新增自动补单、取消、平仓、借还币、转账、smooth/WebSocket、风险上限或任何真实网络测试。\n\n允许修改：backend/hedge_open_tasks/{domain.py,executor.py,scheduler.py,service.py,store.py}，backend/services/{hedge_open_live_client.py,hedge_preflight_provider.py,live_hedge_executor.py}，backend/server.py（仅为独立恢复职责所需的最小接线），直接相关 backend/tests/test_hedge_*.py 与 test_live_hedge_executor.py，frontend/index.html，frontend/self-check.js。禁止修改 PRD、方向综合、设计/ADR 来迁就实现；禁止修改 50-review-2.md。阶段 status/main SHA 的 P2 证据修正由 bookkeeper 单独完成，不由实现者伪造。\n\n必须新增确定性离线回归：target_n=1 下 success/confirmed_failed/single_leg 及 fill-once 与 scheduler 并发都最多一条 attempt；新过滤器改变共同网格时持久化和实际 wire 都使用新 q；任何预检事实缺失零 attempt/零 POST/零失败计数；executor→client 两腿签名字段逐字且无 endpoint；Start off/无 eligible/done 时仍能对账但不阻塞 dispatch；400 鉴权错误保持未知、明确 absent 才拒绝、CANCELED 部分成交终结；累计 quote/partial/fee/residual 进入聚合；前端不再谎称单腿已暂停。所有网络用注入 fake，绝不访问 Binance。\n\n精确自测：\n.venv/bin/python -m pytest backend/tests/test_hedge_domain.py backend/tests/test_hedge_store.py backend/tests/test_hedge_service.py backend/tests/test_hedge_api.py backend/tests/test_hedge_open_live_client.py backend/tests/test_live_hedge_executor.py backend/tests/test_hedge_executor.py backend/tests/test_hedge_purity.py -q\n.venv/bin/python -m pytest backend/tests -q\nnode frontend/self-check.js\n.venv/bin/python -m pytest scripts/tests/test_validate_stage_dispatch_protocol.py -q\ngit diff --check\n\n把原始命令输出追加到 reports/agent-runs/2026-07-hedge-open-real-api-v1/60-test-output.txt，把实现说明写入 reports/agent-runs/2026-07-hedge-open-real-api-v1/40-fix-review-2.md；不得吞掉失败。完成后生成任务 diff patch（若阶段要求），报告 changed files、测试、剩余风险，然后停止等待 bookkeeper；不得提交、不得派发评审。成功标准是上述每条新增测试先能复现旧缺陷、修复后通过，完整 backend/frontend 回归通过，且没有任何真实 POST/私有网络。",
  "next_action": "fix"
}
```

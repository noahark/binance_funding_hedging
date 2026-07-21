# Boundary C Task C — Formal Review-1（Kimi / first_reviewer）

Reviewer：`kimi-code/kimi-for-coding`，provider identity `moonshot_kimi`，fresh
read-only 会话。实现与三轮 bookkeeper intake fix 的作者均为 Claude-GLM /
`zhipu_glm`，不存在 implementation/fix provider self-review。本人此前提交过本
阶段独立设计 review（`design-review.raw-output-kimi.md`），verdict 中如实披露
`reviewer_prior_involvement: "design"`；本评审不复用该结论，全部针对固定
committed diff 独立重查。

## 审查范围与身份核验（实际执行）

- 固定范围 `c9df14591ac4ca00977ce0e4d80c0950aae44c19..61ce536dfba6ddd347586cf324209acdfdc6afd9`。
  当前工作树 HEAD（`165bcc9`）晚于被审 head，其增量经 `git diff --stat
  61ce536..HEAD` 核实仅为 stage 记账文件（status.json、70-handoff.md、
  review-1 prompt/dispatch、60-test-output.txt、ACTIVE.json），未纳入产品 diff。
- 指纹独立重算：本会话实际执行
  `git diff --binary c9df145..61ce536 -- . ":(exclude)reports/agent-runs/2026-07-real-borrow-boundary-c-v1/status.json" | shasum -a 256`
  得 `449b46378a324fa3c8bdd9ec9425b1e59b7509cb55e6c129d8991322dcb1a984`，与
  status.json 记录的 `diff_fingerprint` 完全一致。
- 必读原始工件逐项直接读取（AGENTS.md、workflow YAML、verdict schema、
  status.json、00-task/10-design/11-adr/12-breakdown/14-synthesis、上游方向综合、
  20-implementation、bookkeeper 审计、任务与三轮 fix 的 prompt/dispatch、
  60-test-output.txt、api-samples 证据索引与四个 raw 合同切片），并逐文件审查
  产品代码与测试。
- 独立复跑（非采信报告）：`python3 -m pytest backend/tests -q` → **624 passed**；
  `node frontend/self-check.js` → 全部自检通过（exit 0）；
  `python3 -m py_compile <九个产品模块>` → exit 0；`git diff --check` → clean。
  与 60-test-output.txt 记录一致。

## 十项审查重点结论

1. **唯一 live write 路径：通过。** 全仓库唯一 borrow POST 出口为
   `portfolio_margin_borrow_client.py:150 post_margin_loan`（exact allowlist 仅
   `POST /papi/v1/marginLoan` 与 `GET /papi/v1/margin/marginLoan` 两对，host 硬编码
   `https://papi.binance.com`，`_require_whitelisted` 在任何签名原语之前触发）。
   唯一 HMAC 出口 `binance_signing.py`；`signed_payload` 一次序列化，签名即所发
   字节（POST form body、GET query，签名最后）。专用
   `BINANCE_BORROW_API_KEY/SECRET`；`_send` 单次传输无隐藏 retry；无第二 POST、
   无 URL 拼接错误、无签名漂移；响应只保留瞬态类型化结果（见 F4）。
2. **disabled/fake/live 与 fail-closed 边界：通过。** 非法
   `APP_BORROW_EXECUTOR` 在 config load 硬失败；live+缺凭证时进程可用、
   `_dispatch_one`（service.py:391-393）与 executor 凭证门（live_borrow_executor.py:259）
   双层拦截，零签名流量，`block_reason=borrow_credentials_missing`；ownership
   sidecar `flock(LOCK_EX|LOCK_NB)` 在 scheduler 启动前获取，非owner强制tick也不派发
   （test_borrow_scheduler.py:270 实证）。`execution_enabled` 默认 0，API/UI 无法绕过
   显式 Start（原子门在 store.insert_pending_attempt live_gates 分支）；
   `live_authorized` 只是授权标志，成功只认规范化 `tranId`。
3. **意图原子持久化与结果分类：通过（但见 F3）。** 条件插入事务原子复查
   status/unresolved/count/live gates，同事务插入 pending、推进游标、设置
   `unresolved_attempt_id`；失败谓词零行零 POST。分类矩阵与冻结表逐项一致
   （-51006/-51014/-51061 精确集合；400+(-1003)/429/418 → rate_limited；其余 4xx、
   5xx、timeout、连接丢失、malformed 2xx → unknown）。unknown 只留标记不重发。
4. **reconciliation envelope 严格性：通过。** 严格消费
   `{"rows":[...],"total":N}`；`total` 缺失/bool/非int/负值或与 raw 行数不等（多于
   或少于）均 fail closed；五字段行契约（txId/asset/principal/timestamp/status）任
   一 malformed 整读失败；known-ID 路径验证候选 txId == tranId；response-less 路径
   候选 timestamp 必须落在实际发送窗口内；唯一 CONFIRMED 才可证明成功。
5. **跨任务归属：通过。** `attribution_is_unique`（store.py:864）在候选 txId 已被
   其他 attempt 认领、或其他 task 存在同资产 Decimal 等额 pending/unknown attempt
   时保持 blocked；非歧义正例仍可计数（test_borrow_scheduler.py:486 双任务实证）。
6. **418/429/-1003 cooldown 与 manual re-arm：通过。** 418 → 300s 最低冷却 +
   `requires_rearm=1`；`set_execution_enabled(True)` 在冷却未到期时只置位不清除
   （store.py:440-470），时间到期不自动恢复，需之后手动 Start；reconcile GET 418 经
   `ReconcileOutcome.requires_rearm` 持久化（test_borrow_scheduler.py:516 实证）；
   重启后 durable 保留。
7. **scheduler/store/service 并发与恢复：通过（但见 F3）。** tick 锁串行化
   dispatch 与 reconcile；store 单连接单锁、I/O 期间不持锁；`_last_tick_mono`
   归零锚定 now，60s 冷却后无补发爆发（test:356）；executor 异常与 resolve 异常
   双层 containment，scheduler 线程不死。
8. **契约与静态守卫：通过。** 三条 `/api/borrow-execution/*` 路由 +
   `borrow-execution/v1` schema（additionalProperties:false）经 HTTP 级测试验证；
   `can_execute` 刻意排除瞬时冷却；task.schema 增补 `live_authorized` 与
   `task_to_doc` 一致。五个静态守卫均以精确文件名收窄并保留反向断言（HMAC 唯一
   出口迁至 binance_signing.py、urlopen 仅三个指定客户端、borrow 包 AST 纯净、
   self-check 定时器仅 60000/1000/2000、fetch 方法白名单仅新增两条 POST 路由）。
9. **启动观测：通过。** lifecycle 事件仅含模式枚举、owner 布尔、两个恢复计数；
   live 缺凭证有独立 `borrow_execution_blocked` 事件；测试断言标记凭证值不出现在
   stderr（test_service_health.py:442-466）。
10. **测试证据真实性：通过。** fix-3 的
    `test_reconcile_multiple_confirmed_not_matched` 现有两条完整契约合法 CONFIRMED
    行（txId 1/2、同资产、Decimal 等额 principal、均带 timestamp、total==2），真正
    走到 `len(confirmed) != 1` 歧义门；独立
    `test_reconcile_malformed_row_not_silently_dropped` 仍在。六个 fix-2 负例与三个
    正例均在代码中存在并经本会话复跑验证。报告声明与 committed diff 一致。

## Findings

### F1 (P1) — 过期「不发起真实借币」文案与 live 执行状态直接矛盾

`frontend/index.html:942`（视图 subtitle）、`:953`（静态 info banner）、`:2548`
（每个任务卡 note 模板）三处静态文案仍声称「本阶段不发起真实借币（执行未启用）」
/「所有尝试结果均为『执行未启用』」，且无任何 JS 动态改写。live 模式 + 全局
Start 后，同一页面同时显示执行徽标「模式 live · 已启动」与「不发起真实借币」，
直接违反：00-task.md scope「Replace stale 'execution disabled/no real borrow'
copy」、10-design.md D9「removal of A+B text claiming all attempts are
disabled」、12-development-breakdown.md §6、AC #12「The UI clearly says whether
real execution is available/enabled/stopped」。ADR-001 明确「execution mode must
be unmistakable」——这是首个真实负债写入面，操作员无法从自相矛盾的 UI 判断是否在
产生真实债务。必须修复后方可验收。

### F2 (P1) — 创建路径缺少提交前的目标总量与当前间隔确认展示

`frontend/index.html:1709-1717` 行情表操作列只有数量输入、次数输入与确认按钮；
`createBorrowTask`（:2362-2371）形状校验后直接 POST，创建前不展示
amount × count 目标总量，也不展示当前全局间隔（间隔仅出现在借币任务视图的设置行
说明 :2453-2457，不在行情表创建路径）。直接违反：00-task.md scope「Show amount ×
count = maximum target quantity and current interval before creating an
immediately runnable task」、D9 与 §6「pre-create confirmation text: asset,
amount, count, computed amount × count maximum target quantity, and current
global interval」、AC #12「confirms target total and interval before create」、
ADR-001「The pre-submit UI must display asset, amount, successful count, target
total, and interval」。一次误点 Confirm 即可创建立即可调度的 live 任务而操作员
事先看不到最大目标量与调度节奏。必须修复后方可验收。

### F3 (P1) — 崩溃孤儿 pending attempt 永不进入有界 reconciliation

`backend/borrow_tasks/store.py:761-776` `list_due_reconciliations` 要求
`outcome='resolved' AND result_category='unknown' AND reconcile_next_at_us IS
NOT NULL`；而崩溃孤儿（`insert_pending_attempt` 提交后、`resolve_attempt` 前进程
退出）永远保持 `outcome='pending'`、`reconcile_next_at_us=NULL`——该字段的全部
写入仅在 unknown resolve 分支（:640-642）与 `advance_reconciliation`；启动恢复
（:195-201）只把任务重新标记为 blocked。因此最危险的崩溃窗口（POST 可能已到达
Binance）留下的歧义 attempt 永远不会被 loan-record API 证明或排除，任务永久
blocked，唯一出路是 delete，可能已产生的真实借款永远不计入 success_count。
直接违反：11-adr.md ADR-006「Pending/orphan/unknown attempts remain blocked and
enter bounded reconciliation」、00-task.md Goal「reconcile ambiguous attempts
through the verified loan record API」、AC #7（unresolved task 的唯一解决路径是
+5/+15/+60/+300/+900s 有界 reconciliation）；20-implementation.md 与 AC #13 宣称
的「restart-orphan recovery」实际只覆盖了 blocking（test_borrow_store.py:65-76），
未覆盖 recovery。必须修复后方可验收。

### F4 (P3) — `BorrowHttpResponse.raw_body` 字段从未被读取

`portfolio_margin_borrow_client.py:68` 保留原始响应体字符串，但全仓库（产品与
测试）无任何读取点。当前未持久化、未进日志，不构成泄漏；但作为私有响应体的
瞬态驻留属于多余面。建议删除该字段或注释说明保留理由。

### F5 (P3) — `.env.example` 未收录新的专用凭证变量名

`BINANCE_BORROW_API_KEY` / `BINANCE_BORROW_API_SECRET` 未出现在 `.env.example`
（breakdown 文件边界将其列为新 env 名称的文档位置）。操作员无法从示例文件发现
这两个变量名。建议补空值文档行（仅文档，不含任何秘密）。

## Verdict 理由

三项 P1 均为冻结验收标准（AC #12 / AC #7 / ADR-001 / ADR-006 / 00-task scope /
D9 / §6）的未满足项，且都位于本阶段核心安全语义上（操作员对「是否在产生真实
债务」的判断、提交前的风险确认、崩溃歧义的恢复路径）。按评审纪律，存在 P1 不得
ACCEPT。后端写路径、reconciliation 严格性、cooldown/re-arm、归属门与静态守卫
本身质量良好，测试证据真实；修复范围小且边界清晰。verdict：**REWORK**，
`next_action: fix`。两项 P3 为可选打磨，不构成门禁。

## Validator 互操作说明（ Harness 缺口披露，非本 verdict 无效的证据）

本评审实际运行了 `scripts/validate-stage.py` 自身的函数验证本工件：

- 本工件末尾的 verdict JSON 经 `jsonschema` 全量校验**通过**
  `schemas/review-verdict.schema.json`（含三项 P1 与 fix_start_prompt 的完整
  REWORK 载荷）。
- 但 validator 的 `extract_last_json_object`（validate-stage.py:368-387）从文件
  末尾向前扫描 `{` 并返回第一个可解码 object：对任何 `findings` 非空的
  verdict，它返回的是最后一个 **finding object** 而非 verdict 本体。已在本
  工件上复现（`_parse_review_artifact` 报 `missing required property
  'schema_version'`），并在历史工件
  `69f10cd:.../30-review-1-backend.md`（findings 非空）上同样复现。
- 该函数此前从未被 findings 非空的 verdict 触发过：DRAFT-2 的提取器单测只用
  `findings: []`，历史阶段不启用 `dispatch_protocol: human-operator/v1`，因此
  `validate_review_artifacts` 对它们是 no-op。本阶段是该提取器首次面对
  findings-bearing verdict。
- 后果：bookkeeper 在 status.json 记录本 REWORK verdict 后，
  `validate_review_artifacts`（pre-review）与 `validate_acceptance`（pre-accept）
  会误报「parsed verdict fails schema」。这是 Harness validator 缺口（宽容提取
  器不支持嵌套 object），**不是 invalid verdict JSON**；按 AGENTS.md 应作为
  Harness 缺陷走 main 分支 validator 修正/人工升级，而非按 invalid JSON 路由
  重试或 fallback。评审角色被禁止修改 Harness/validator 文件，故仅在此披露。

当前 Session ID: 9bb7a540-1d7e-428f-9ab8-ebfb580cbb35（本会话工具输出路径中出现的本地 Kimi CLI 会话 id；可由 operator 核验后记入 status.json.session_receipts）
Session ID 来源: transcript_path
原始输出路径: reports/agent-runs/2026-07-real-borrow-boundary-c-v1/30-review-1.md
本地北京时间: 2026-07-21 11:31:10 CST
下一步模型: bookkeeper → human operator → Claude-GLM / glm-5.2[1m]
下一步任务: bookkeeper intake 本 review，按 fix_start_prompt 准备 fix dispatch，由 human operator 在 Claude-GLM 执行三项 P1 修复

{
  "schema_version": 1,
  "stage_id": "2026-07-real-borrow-boundary-c-v1",
  "role": "first_reviewer",
  "model": "kimi-code/kimi-for-coding",
  "verdict": "REWORK",
  "diff_fingerprint": "61ce536dfba6ddd347586cf324209acdfdc6afd9:449b46378a324fa3c8bdd9ec9425b1e59b7509cb55e6c129d8991322dcb1a984",
  "reviewer_prior_involvement": "design",
  "reviewer_prior_involvement_notes": "Kimi previously supplied an independent design review at reports/agent-runs/2026-07-real-borrow-boundary-c-v1/design-review.raw-output-kimi.md (verdict REWORK). This formal review-1 re-examined the fixed committed diff independently; provider isolation from the zhipu_glm implementation/fix author remains intact.",
  "reviewed_artifacts": [
    "AGENTS.md",
    "workflows/templates/stage-delivery.yaml (test/review-1/fix sections)",
    "schemas/review-verdict.schema.json",
    "reports/agent-runs/2026-07-real-borrow-boundary-c-v1/status.json",
    "reports/agent-runs/2026-07-real-borrow-boundary-c-v1/00-task.md",
    "reports/agent-runs/2026-07-real-borrow-boundary-c-v1/10-design.md",
    "reports/agent-runs/2026-07-real-borrow-boundary-c-v1/11-adr.md",
    "reports/agent-runs/2026-07-real-borrow-boundary-c-v1/12-development-breakdown.md",
    "reports/agent-runs/2026-07-real-borrow-boundary-c-v1/14-design-review-synthesis.md",
    "reports/agent-runs/2026-07-real-borrow-execution-v1/06-direction-synthesis.md",
    "reports/agent-runs/2026-07-real-borrow-boundary-c-v1/20-implementation.md",
    "reports/agent-runs/2026-07-real-borrow-boundary-c-v1/20-implementation-bookkeeper-audit.md",
    "reports/agent-runs/2026-07-real-borrow-boundary-c-v1/task-C-claude-glm.dispatch.md",
    "reports/agent-runs/2026-07-real-borrow-boundary-c-v1/task-C-bookkeeper-fix-1.prompt.md",
    "reports/agent-runs/2026-07-real-borrow-boundary-c-v1/task-C-bookkeeper-fix-1.dispatch.md",
    "reports/agent-runs/2026-07-real-borrow-boundary-c-v1/task-C-bookkeeper-fix-2.prompt.md",
    "reports/agent-runs/2026-07-real-borrow-boundary-c-v1/task-C-bookkeeper-fix-2.dispatch.md",
    "reports/agent-runs/2026-07-real-borrow-boundary-c-v1/task-C-bookkeeper-fix-3.prompt.md",
    "reports/agent-runs/2026-07-real-borrow-boundary-c-v1/task-C-bookkeeper-fix-3.dispatch.md",
    "reports/agent-runs/2026-07-real-borrow-boundary-c-v1/60-test-output.txt",
    "reports/api-samples/2026-07-real-borrow-boundary-c-v1/20260720T150836Z/evidence-index.md",
    "reports/api-samples/2026-07-real-borrow-boundary-c-v1/20260720T150836Z/raw/margin-account-borrow.md",
    "reports/api-samples/2026-07-real-borrow-boundary-c-v1/20260720T150836Z/raw/query-margin-loan-record.md",
    "reports/api-samples/2026-07-real-borrow-boundary-c-v1/20260720T150836Z/raw/portfolio-margin-error-codes.md",
    "reports/api-samples/2026-07-real-borrow-boundary-c-v1/20260720T150836Z/raw/portfolio-margin-general-info.md",
    "git diff --binary c9df14591ac4ca00977ce0e4d80c0950aae44c19..61ce536dfba6ddd347586cf324209acdfdc6afd9 -- . ':(exclude)reports/agent-runs/2026-07-real-borrow-boundary-c-v1/status.json' (fingerprint independently recomputed and matched)",
    "backend/services/binance_signing.py",
    "backend/services/portfolio_margin_borrow_client.py",
    "backend/services/live_borrow_executor.py",
    "backend/services/private_client.py",
    "backend/borrow_tasks/domain.py",
    "backend/borrow_tasks/executor.py",
    "backend/borrow_tasks/ownership.py",
    "backend/borrow_tasks/scheduler.py",
    "backend/borrow_tasks/service.py",
    "backend/borrow_tasks/store.py",
    "backend/app/server.py",
    "backend/config.py",
    "schemas/api/borrow-tasks/execution-status.schema.json",
    "schemas/api/borrow-tasks/task.schema.json",
    "frontend/index.html",
    "frontend/self-check.js",
    "backend/tests/test_binance_signing.py",
    "backend/tests/test_portfolio_margin_borrow_client.py",
    "backend/tests/test_live_borrow_executor.py",
    "backend/tests/test_borrow_store.py",
    "backend/tests/test_borrow_scheduler.py",
    "backend/tests/test_borrow_api.py",
    "backend/tests/test_borrow_executor.py",
    "backend/tests/test_config.py",
    "backend/tests/test_private_client.py",
    "backend/tests/test_private_account_v1.py",
    "backend/tests/test_service_health.py",
    "independent re-run: python3 -m pytest backend/tests -q (624 passed); node frontend/self-check.js (pass); python3 -m py_compile over nine product modules (exit 0); git diff --check (clean)"
  ],
  "findings": [
    {
      "severity": "P1",
      "title": "Stale A+B 'no real borrow' copy contradicts the live execution state",
      "file": "frontend/index.html",
      "line": 953,
      "evidence": "Three static strings remain and are never rewritten by JS: line 942 subtitle '本阶段不发起真实借币（执行未启用）', line 953 static banner '本阶段后端调度仅记录尝试结果、不发起真实借币，所有尝试结果均为「执行未启用」。浏览器不调度、不模拟、不请求 Binance。', and line 2548 per-task note '本阶段不发起真实借币（执行未启用）'. With live mode plus a global Start the same page shows the badge '模式 live · 已启动' (renderExecutionStatus, lines 2287-2310) next to copy claiming no real borrow happens.",
      "impact": "Violates 00-task.md scope ('Replace stale execution disabled/no real borrow copy'), 10-design.md D9 ('removal of A+B text claiming all attempts are disabled'), 12-development-breakdown.md section 6, and acceptance criterion 12 ('The UI clearly says whether real execution is available/enabled/stopped'). On the first debt-creating surface the operator gets two contradictory answers about whether real debt is being created, breaking ADR-001's 'execution mode must be unmistakable'.",
      "recommendation": "Remove or rewrite the three stale strings so they no longer claim 'no real borrow'; keep the still-true statements (browser never schedules/signs/contacts Binance); make the copy mode-accurate (neutral static copy or derived from the already-fetched execution-status projection); extend frontend/self-check.js with a matching assertion without loosening any guard."
    },
    {
      "severity": "P1",
      "title": "Pre-create confirmation of target total and current interval is missing from the create path",
      "file": "frontend/index.html",
      "line": 1709,
      "evidence": "The market-row op cell (lines 1709-1717) renders only the amount input, count input, and confirm button; createBorrowTask (lines 2362-2371) validates shape and POSTs immediately. Nothing on the create path displays the computed amount x count maximum target quantity or the current global interval; the interval appears only in the borrow-task view settings note (lines 2453-2457), a different view from the market table where Confirm is clicked. self-check item 62 confirms the op cell holds exactly two inputs plus one button.",
      "impact": "Violates 00-task.md scope ('Show amount x count = maximum target quantity and current interval before creating an immediately runnable task'), D9 and breakdown section 6 ('pre-create confirmation text: asset, amount, count, computed amount x count maximum target quantity, and current global interval'), acceptance criterion 12 ('confirms target total and interval before create'), and ADR-001 ('The pre-submit UI must display asset, amount, successful count, target total, and interval'). One accidental Confirm creates an immediately scheduler-eligible live task without the operator seeing the maximum target quantity or cadence first.",
      "recommendation": "Before the create POST, display asset, amount, count, the computed amount x count target total, and the current global interval in the market-row create path (render from the already-loaded scheduler settings; reuse multiplyDecimalString/BigInt discipline, never float). Do not add a new task state machine or browser scheduling; cover the display in frontend/self-check.js without loosening the timer/fetch-method guards."
    },
    {
      "severity": "P1",
      "title": "Crash-orphaned pending attempts never enter bounded reconciliation",
      "file": "backend/borrow_tasks/store.py",
      "line": 761,
      "evidence": "list_due_reconciliations (lines 761-776) requires outcome='resolved' AND result_category='unknown' AND reconcile_next_at_us IS NOT NULL. An orphaned pending attempt (crash after the insert_pending_attempt commit but before resolve_attempt) keeps outcome='pending' and reconcile_next_at_us=NULL forever: the only writes of reconcile_next_at_us are the unknown-resolve branch (lines 640-642) and advance_reconciliation, and startup recovery (lines 195-201) only re-marks the task blocked. No test reconciles an orphan; test_borrow_store.py:65-76 asserts blocking only.",
      "impact": "Violates 11-adr.md ADR-006 ('Pending/orphan/unknown attempts remain blocked and enter bounded reconciliation'), 00-task.md Goal ('reconcile ambiguous attempts through the verified loan record API'), and acceptance criterion 7 (the bounded reconciliation schedule is the only resolution path for an unresolved task; the orphan has none). A crash inside the real dispatch window — exactly the ambiguous-outcome case this stage exists for — leaves the task permanently blocked with no automated reconciliation; the only exit is delete, and a possibly-created real loan is never proven or credited, so success_count can permanently under-count real debt. The 'restart-orphan recovery' claim in 20-implementation.md / acceptance criterion 13 covers blocking, not recovery.",
      "recommendation": "At startup (idempotently), transition orphaned pending attempts into the reconciliation schedule as response-less unknowns (reconcile_step=0, reconcile_next_at_us anchored at now + RECONCILE_DELAYS_SECONDS[0], a marking reason such as crash_orphan_responseless, outcome finalized as resolved/unknown) so the existing _reconcile_pass handles them under the same unique-match plus attribution_is_unique gates; make resolve_reconciliation_success also finalize a formerly-pending attempt row (outcome/result_category/finished_at_us). Add restart-orphan reconciliation tests: unique match proves success after restart, no-match exhausts and stays blocked, no second POST ever occurs, and repeated startups do not re-schedule. Never add a force-clear or retry-anyway route."
    },
    {
      "severity": "P3",
      "title": "BorrowHttpResponse.raw_body is retained but never read",
      "file": "backend/services/portfolio_margin_borrow_client.py",
      "line": 68,
      "evidence": "The dataclass field raw_body is written on every transport call but has no reader anywhere in product code or tests (grep over backend/ finds only the declaration).",
      "impact": "No leak today: the raw private response body is never persisted to the ledger and never logged. It is still unnecessary transient surface that could tempt future logging of full private bodies, which the design forbids.",
      "recommendation": "Drop the field, or add a comment justifying its retention; keep it out of any persisted or logged evidence."
    },
    {
      "severity": "P3",
      "title": ".env.example does not document the new dedicated borrow credential names",
      "file": ".env.example",
      "line": null,
      "evidence": "grep of .env.example finds no BINANCE_BORROW_API_KEY or BINANCE_BORROW_API_SECRET entry; the breakdown file boundary lists .env.example and scripts/run-server.sh as the documentation location for the new env names.",
      "impact": "The operator cannot discover the dedicated credential variable names from the example env file; minor documentation gap only, no runtime effect.",
      "recommendation": "Add both variable names with empty values and a short comment (documentation only, no secrets)."
    }
  ],
  "required_fixes": [
    "F1: remove or rewrite the stale 'no real borrow' copy at frontend/index.html:942, :953, and :2548 so the UI no longer contradicts the live execution state; keep truthful browser-never-schedules/signs statements; add a self-check assertion without loosening guards.",
    "F2: display asset, amount, count, the computed amount x count maximum target quantity, and the current global interval on the market-row create path before the create POST, using existing Decimal/BigInt discipline; cover it in frontend/self-check.js.",
    "F3: move crash-orphaned pending attempts into the bounded reconciliation schedule at startup (idempotent, response-less unknown, +5s first read), keep all existing unique-match/attribution gates, finalize the attempt row on reconciliation success, and add restart-orphan reconciliation tests proving success-on-unique-match, blocked-on-exhaustion, idempotent re-scheduling, and zero second POSTs."
  ],
  "residual_risks": [
    "The reconciliation window is a local conservative policy with no published Binance propagation SLA; a loan that becomes visible only after the fifth read leaves the task in terminal reconciliation_exhausted by design (documented, operator exit is delete).",
    "The sidecar flock guarantees one execution owner per database path, but two different database paths on one machine are outside its scope (accepted by design).",
    "P3 findings F4/F5 are optional polish and are not gate-blocking."
  ],
  "fix_start_prompt": "[HARNESS-EXECUTOR-CONTRACT v1]\n你是本任务的唯一执行者。\n1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令（包括但不限于 claude-glm -p、kimi -p、codex exec、grok）。需要其他模型时，输出 ESCALATED 及原因并停止。\n2. 禁止编造未实际执行的命令结果或未实际读取的文件内容；你写下的每一条执行记录都必须对应你本会话内真实发生的动作。\n3. 你的修复依据只能是本 prompt 列出的 raw artifact 路径与你自己实际读取的文件。\n\n# Task C — Review-1 REWORK Fix（三项 P1）\n\n你是 Task C 原实现者：claude_glm / provider identity zhipu_glm / glm-5.2[1m]。\n\n- Stage: 2026-07-real-borrow-boundary-c-v1\n- 被审 diff fingerprint: 61ce536dfba6ddd347586cf324209acdfdc6afd9:449b46378a324fa3c8bdd9ec9425b1e59b7509cb55e6c129d8991322dcb1a984\n- Raw review（含完整 findings 与证据）: reports/agent-runs/2026-07-real-borrow-boundary-c-v1/30-review-1.md\n- 本轮为 formal rework 1（max 3）。\n\n## 必读\n\n1. AGENTS.md\n2. agents/developer-discipline.md\n3. reports/agent-runs/2026-07-real-borrow-boundary-c-v1/30-review-1.md\n4. reports/agent-runs/2026-07-real-borrow-boundary-c-v1/00-task.md（scope 与 AC 7/12/13）\n5. reports/agent-runs/2026-07-real-borrow-boundary-c-v1/10-design.md（D9）\n6. reports/agent-runs/2026-07-real-borrow-boundary-c-v1/11-adr.md（ADR-001、ADR-006）\n7. reports/agent-runs/2026-07-real-borrow-boundary-c-v1/12-development-breakdown.md（§5.3、§6）\n8. backend/borrow_tasks/store.py、backend/borrow_tasks/service.py、backend/services/live_borrow_executor.py、frontend/index.html、frontend/self-check.js\n9. reports/agent-runs/2026-07-real-borrow-boundary-c-v1/60-test-output.txt\n\n## Findings 与 required fixes（按序）\n\n### F1 (P1) — 过期「不发起真实借币」文案与 live 执行状态矛盾\n\n证据：frontend/index.html:942（subtitle）、:953（静态 banner）、:2548（任务卡 note 模板）均为静态文案且无任何 JS 改写，声称「本阶段不发起真实借币（执行未启用）」/「所有尝试结果均为『执行未启用』」；live+已启动时与同屏执行徽标（模式 live · 已启动）直接矛盾。\n违反：00-task.md scope「Replace stale 'execution disabled/no real borrow' copy」；10-design.md D9；12-development-breakdown.md §6；AC #12。\n必修：删除/改写这三处文案，使其不再声称「不发起真实借币」；保留仍属实的陈述（浏览器不调度、不模拟、不签名、不请求 Binance）；文案与执行模式语义一致（中性静态文案或从已加载的 execution-status 投影派生）；不得新增浏览器侧调度/签名；在 frontend/self-check.js 增补对应断言且不放宽任何守卫。\n\n### F2 (P1) — 创建路径缺少提交前的目标总量与当前间隔确认展示\n\n证据：frontend/index.html:1709-1717 操作列仅有数量输入、次数输入与确认按钮；createBorrowTask（:2362-2371）形状校验后直接 POST；创建前不展示 amount×count 目标总量，也不展示当前全局间隔（间隔仅在借币任务视图设置行 :2453-2457 显示，不在行情表创建路径）。\n违反：00-task.md scope「Show amount × count = maximum target quantity and current interval before creating an immediately runnable task」；D9 与 §6 的 pre-create confirmation text；AC #12「confirms target total and interval before create」；ADR-001「The pre-submit UI must display asset, amount, successful count, target total, and interval」。\n必修：在行情表创建路径提交 POST 前展示资产、数量、次数、计算所得 amount×count 最大目标总量与当前全局间隔（用已加载的 scheduler settings 渲染；沿用 multiplyDecimalString / BigInt 精度纪律，禁止 float）；不得引入新的任务状态机或浏览器调度；在 frontend/self-check.js 增补断言且不放宽 timer/fetch-method 守卫。\n\n### F3 (P1) — 崩溃孤儿 pending attempt 永不进入有界 reconciliation\n\n证据：backend/borrow_tasks/store.py:761-776 list_due_reconciliations 要求 outcome='resolved' AND result_category='unknown' AND reconcile_next_at_us IS NOT NULL；崩溃孤儿（insert_pending_attempt 提交后、resolve_attempt 前进程退出）永远保持 outcome='pending' 且 reconcile_next_at_us=NULL；reconcile_next_at_us 的全部写入仅在 unknown resolve 分支（:640-642）与 advance_reconciliation；启动恢复（:195-201）只重新标记任务 blocked。现有测试仅断言 blocked（test_borrow_store.py:65-76），无孤儿进入 reconciliation 的证据。\n违反：11-adr.md ADR-006「Pending/orphan/unknown attempts remain blocked and enter bounded reconciliation」；00-task.md Goal「reconcile ambiguous attempts through the verified loan record API」；AC #7（unresolved task 的唯一解决路径是 +5/+15/+60/+300/+900s 有界 reconciliation）；AC #13 与 20-implementation.md 宣称的「restart-orphan recovery」名不副实。\n必修：在启动恢复中（幂等）把孤儿 pending attempt 作为 response-less unknown 纳入 reconciliation 调度（reconcile_step=0，reconcile_next_at_us 锚定 now+RECONCILE_DELAYS_SECONDS[0]，reason 标记如 crash_orphan_responseless，outcome 收尾为 resolved/unknown），使其走既有 _reconcile_pass；唯一 CONFIRMED 匹配且 attribution_is_unique 通过才可 resolve_reconciliation_success，且该函数须同时把原为 pending 的 attempt 行收尾（outcome/result_category/finished_at_us）；无匹配/多候选/跨任务歧义/五次读尽继续 blocked。严禁第二次 POST、严禁 force-clear 或 retry-anyway 路由。\n新增测试：重启后孤儿进入调度并在唯一匹配时计数成功；无匹配耗尽保持 blocked；重复启动幂等不重复排程；孤儿路径零第二次 POST。\n\n## File boundaries（原 Task C 冻结边界，本轮只允许触碰与三项 finding 直接相关的文件）\n\n允许：\n- frontend/index.html、frontend/self-check.js\n- backend/borrow_tasks/store.py、backend/borrow_tasks/service.py（保持 network/signing-free）\n- backend/services/live_borrow_executor.py（仅当 F3 的 finalize 语义需要）\n- backend/tests/test_borrow_store.py、backend/tests/test_borrow_scheduler.py、backend/tests/test_live_borrow_executor.py、backend/tests/test_borrow_api.py（仅确有必要）\n- reports/agent-runs/2026-07-real-borrow-boundary-c-v1/40-fix-report.md（新建）\n- reports/agent-runs/2026-07-real-borrow-boundary-c-v1/60-test-output.txt（append only）\n可选（P3，非门禁）：backend/services/portfolio_margin_borrow_client.py 移除未使用的 raw_body 字段；.env.example 增补 BINANCE_BORROW_API_KEY/BINANCE_BORROW_API_SECRET 文档行。\n禁止：status.json、70-handoff.md、ACTIVE.json、00-task/10-design/11-adr/12-breakdown、bookkeeper audit、30-review-1.md、canonical docs、Harness/workflow/validator、unrelated stage、reports/agent-runs/_proposals/**；不 commit/push/merge，不 dispatch 任何模型。\n\n## 安全约束\n\n- 严禁真实、认证或 production-reachable Binance 请求；全部 transport 练习继续用 injected fake/recording transport + dummy credentials。\n- 不读取 .env、key file、cookie、credential store 或 expanded alias environment。\n- 禁止新增第二次 POST、隐藏 retry、retry-anyway/force-clear 路由；禁止弱化 exact-path/HMAC/urlopen/AST/UI 守卫。\n\n## 完成验证（fake-only；每条真实输出追加到 60-test-output.txt，不覆盖既有内容）\n\npython3 -m pytest backend/tests/test_borrow_store.py backend/tests/test_borrow_scheduler.py backend/tests/test_borrow_api.py backend/tests/test_live_borrow_executor.py -q\npython3 -m pytest backend/tests/test_binance_signing.py backend/tests/test_portfolio_margin_borrow_client.py backend/tests/test_live_borrow_executor.py backend/tests/test_borrow_store.py backend/tests/test_borrow_scheduler.py backend/tests/test_borrow_api.py backend/tests/test_config.py backend/tests/test_private_client.py backend/tests/test_private_account_v1.py backend/tests/test_service_health.py -q\npython3 -m pytest backend/tests -q\nnode frontend/self-check.js\npython3 -m py_compile backend/services/binance_signing.py backend/services/portfolio_margin_borrow_client.py backend/services/live_borrow_executor.py backend/services/private_client.py backend/borrow_tasks/*.py backend/app/server.py backend/config.py\ngit diff --check\n\n## 收尾\n\n新建 reports/agent-runs/2026-07-real-borrow-boundary-c-v1/40-fix-report.md，逐项映射 F1/F2/F3（及可选 P3）→ root cause → changed files → tests → result；把上述命令真实输出追加到 60-test-output.txt；回填本轮 dispatch receipt；然后停止，交回 bookkeeper；不得宣称 review 或 acceptance。",
  "next_action": "fix"
}

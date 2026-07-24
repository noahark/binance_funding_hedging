# Review-1（第一轮交叉复核）— 后端：Hedge Open Real API v1（重做后二次提交）

## 审查身份与锚点

- 本次审查者：Claude Sonnet 5（Anthropic）。被审后端代码的实现/返工作者为 Claude-GLM（`zhipu_glm`）；provider（模型提供方）隔离成立。
- 如实披露：本人（Claude Sonnet 5）在本 stage 早前轮次中写过**前端**返工（`40-fix-review-2-frontend.md`、`41-fix-open-log-pagination-frontend.md` 等），但**没有写过本次被审的后端代码**（`backend/hedge_open_tasks/**`、`backend/services/hedge_*`）。因此 `reviewer_prior_involvement` 按派发要求记为 `none`（该字段枚举不含"曾写同阶段其他域代码"这一类别；如实说明写在此处）。
- 固定审查区间：`base=28c550d87c1ca90983d5bde9c7102d42cffecd4e`，`head=8af3f22d92354fdac61a6a057eb25760b924004b`，未移动 HEAD。
- 本机独立重算指纹：`git diff --binary <base>..<head> -- . ":(exclude)status.json" | sha256sum` = `cbd0d92f53cbaaaab444812dd6ce5bd4bcc07aa947a923dd2a33014a74e5d320`，与派发值、`status.json` 记录值逐字一致。
- 只读、离线。未读取任何凭据，未连接 Binance，未发送任何真实请求，未启用 live/Start。

## 本机验证（全部离线命令，原始输出如下）

| 命令 | 结果 |
| --- | --- |
| `git diff --binary <base>..<head> -- . ...(exclude status.json)` \| `shasum -a 256` | `cbd0d92f...` 与冻结指纹逐字一致 |
| `.venv/bin/python -m pytest backend/tests -q` | `882 passed in 46.26s`（与 `19`/`60` 记录一致） |
| `node frontend/self-check.js` | 全部自检通过（本次仅作后端-前端接缝对齐旁证，未评审前端视觉实现） |
| `git diff --check` | exit 0，无空白/冲突 |
| `.venv/bin/python scripts/validate-stage.py 2026-07-hedge-open-real-api-v1 --phase pre-review` | **FAILED**：工作树存在未提交文件 `reports/.../59-review-1-frontend-r2.md`（并行前端评审会话的输出，非本次后端评审产物，也非本次 diff 范围内证据）。这不改变已提交区间 `28c550d..8af3f22` 的指纹或后端代码内容，但 bookkeeper 在门禁前需要处理这个未提交文件（提交或按前端评审流程归位）。 |
| `git rev-parse 9a0fabf74f004f4a34d8befd3676042963b5e66f` + `git log --format="%H %P" -1 01d3a47...` | 确认 Review-2 P2 发现（main-sync 假 SHA）已被 bookkeeper 正确更正为真实第二父提交，`status.json.main_syncs[1]` 与 git 历史一致。 |

## 已阅读的原始材料

`AGENTS.md`；`workflows/templates/stage-delivery.yaml`（review_1 段）；`docs/product/PRD.md`（§3/§6/§9.2 全文）；`00-task.md`、`04-user-execution-policy.md`、`15-immediate-loop-and-open-log-amendment.md`、`16-replacement-development-breakdown.md`、`17-opening-log-pagination-compatibility.md`、`19-replacement-r4-final-reconciliation.md`、`20-r4-scope-deviation-domain-cursor.md`、`50-review-2.md`（含最后 JSON verdict）、`40-fix-review-2-backend.md`、`41-fix-open-log-pagination-backend.md`、`60-test-output.txt`；`schemas/review-verdict.schema.json`；实际 `git diff 28c550d..8af3f22 --stat`；以及后端源码 `backend/hedge_open_tasks/{domain.py,executor.py,service.py,store.py,scheduler.py}`、`backend/services/{hedge_open_live_client.py,hedge_preflight_provider.py,live_hedge_executor.py}`、`backend/app/server.py`（hedge 路由段）、`backend/tests/test_hedge_purity.py`、`backend/tests/test_hedge_review2_regressions.py` 的关键测试函数。

## 结论

**REWORK（需要返工）**。这是继 `50-review-2.md` 判定 REWORK 之后的第二次提交（顺序组循环重做 + 日志分页兼容修复）。修复报告 `40`/`41` 声称的绝大多数 Review-2 P0/P1 项确实已在实际 diff 中正确实现并有确定性回归覆盖（详见"已核实的修复"）。但逐行核对源码后，发现 **Review-2 required fix #3（预检完整性 fail-closed）与 required fix #5（对账独立于下单节奏，不阻塞）各有一处真实存在、可复现的未完全修复缺口**，两者都直接落在本轮拆解（`16` §3.2 A-3 / A-5）明确要求修复的范围内，且都可能在真实开单授权后产生非预期行为（前者是本地最小名义金额校验可被静默跳过；后者是对账仍可拖慢全部任务的下单节奏）。这两点不是"锦上添花"式的加固建议，而是本轮修复声称已完成、实际未完成的原始 Review-2 条目，因此按合同判定 REWORK 而非 ACCEPT-with-follow-up。

## 已核实的修复（逐项与实际 diff 对照，均确认落实）

1. **A-1 `target_n` 硬上限**（`store.py:474-550`）：`list_eligible_tasks` 与 `prepare_attempt` 在同一 store 级 `RLock` + SQLite 事务内双重原子核查 `scheduled_attempt_count < target_n`，并新增在途未决组（`pair_outcome IS NULL`）守卫，确保同一任务永不并发第二组。`prepare_attempt` 的原子重检独立于任何服务层锁，`post_fill_once` 未经服务锁也不构成竞态——已核实。
2. **A-2 新鲜预检优先**（`service.py:1000-1072`）：live 路径先 `_resolve_fresh_preflight`，取得本次精确 `q_common`/仓位模式/快照后才 `prepare_attempt`，dry-run 路径仍复用旧值、从不 POST——已核实。
3. **A-4 wire/元数据分离**（`executor.py:113-155`）：两个 builder 精确 7 键，均不含 `endpoint`；`live_hedge_executor.py` 复用同一 builder，未见任何内部字段泄漏进签名参数——已核实。
4. **A-5 部分**：`CANCELED`/`EXPIRED`/`REJECTED`/`FILLED` 均已在 `_query_verdict_terminal`（`service.py:1267-1282`）和 `classify_query_response`（`live_hedge_executor.py:274-327`）中正确终结并保留部分成交；鉴权/签名/时间戳/权限码只在 `classify_query_response` 明确 `404`/`-2013` 时判定 absent，其余保持未知继续查询——已核实（详见下方"未完全修复"里对同一函数**架构层面**的剩余问题）。
5. **A-6 实际成交/残差**（`store.py:1390-1481`）：`aggregate_positions` 已改为纳入任何 `cumulative_base_qty > 0` 的腿，不再要求字面 `FILLED`；`cumulative_quote` 端到端透传——已核实。
6. **A-7 错误矩阵**（`store.py` `_apply_task_counters`、`domain.py` `PREFLIGHT_FATAL_REASONS`/`REJECT_TO_STOP_REASON`）：致命立停（`STATUS_STOPPED`+`stop_reason`）、非致命计数、阈值暂停、双腿受理清零、429 仅进程级延迟不改任务业务态——已核实，且 `test_hedge_review2_regressions.py` 的 `test_7a/7b/7c/7d` 用确定性 fake 传输复现并通过。
7. **A-8/A-9 entries 分页 + 双任务独立性**：`_entries_page`（`service.py:576-640`）与 `list_attempts_entries_page`/`list_task_event_logs_page`（`store.py:1088-1131,1354-1386`）用共享三元组 `(ts_us, rank, id)` 严格降序游标合并两个独立自增序列，本人独立重新推导了其正确性（`rank` 固定区分来源表，跨页无重复无遗漏），并用 `test_8c`（交错 6 attempt + 3 event）验证；`test_9`（两任务独立 + 每任务串行）逻辑正确——已核实。
8. **P2 main-sync 假 SHA**：bookkeeper 已更正为真实 `9a0fabf74f004f4a34d8befd3676042963b5e66f`，与 `git log --format="%H %P" 01d3a47` 输出一致——已核实。
9. **范围偏差**（`20-r4-scope-deviation-domain-cursor.md`）：`domain.py` 新增的 `encode_entries_cursor`/`decode_entries_cursor`/`validate_entries_limit` 确系纯函数（无 SQLite/网络/签名/凭据副作用），且对非法格式（含把两段式旧 cursor 误传入 entries_cursor 的情况）会因 `split(":", 2)` 解包失败而 fail-closed 返回 `None`→400，本人独立验证过该失败路径的正确性。判定：该偏差合理，不构成新问题。

## Findings（问题）

### P1 — 反向（negative funding，卖出现货）方向的最小名义金额校验在估值价格缺失时被静默跳过，未按要求 fail-closed

- **文件**：`backend/hedge_open_tasks/domain.py:552-578`（`_check_common_quantity`）与 `:677-703`（`compute_preflight` 的方向分支）。
- **证据**：`_check_common_quantity` 的 minNotional 检查整体被 `if est_price is not None and est_price > 0:` 包裹（第 572 行），价格缺失时**整段跳过**，既不拒绝也不标记 incomplete。随后 `compute_preflight` 只在 `direction == DIR_FORWARD` 分支（第 677-689 行）才会因 `est_price is None` 返回 `REJECT_PREFLIGHT_INCOMPLETE`；`else`（反向）分支（第 692-703 行）完全不读取、不校验 `est_price`，只用 `q_common * target_n` 与 base 资产余额比较。本人用 `_read_est_price` 的实现路径核对：反向任务下，若 Binance 现货 ticker 价格接口一次性读取失败（网络抖动/超时/返回体缺 `price`），`HedgePreflightProvider.get_snapshot`（`hedge_preflight_provider.py:246-288`）的 fail-closed 门槛只检查 `spot/perp/balances/position_mode/rate_limit` 五项，**不检查 `est_price`**，因此仍会返回一个"完整"快照；`compute_preflight` 对该快照在反向方向下会跳过 minNotional 校验并直接判定可发送。
- **影响**：与 Review-2 required fix #3 的逐字要求（"价格、余额、过滤器、每约束回退、最小名义金额和当前订单限频事实缺一即不发送"）不符——该要求没有区分方向。反向任务在价格读取偶发失败时，本地校验会静默放行一个未经过 minNotional 验证的 `q_common`，只能依赖交易所侧事后拒绝兜底，而不是合同要求的本地 fail-closed。这正是 Review-2 原始 P1 finding #3（"缺失时 rejection=None"）在反向路径上的残留形态，只是触发条件从"forward 缺价"变成了"reverse 缺价"。
- **复现路径（未运行，纯代码/单测推导，非真实网络）**：构造 `PreflightSnapshot(spot_filters=..., perp_filters=..., balances={base: 足够余额}, position_mode="BOTH", est_price=None)`，调用 `compute_preflight(snapshot, coin, D.DIR_REVERSE, single_amount, target_n)`——现有测试套件里没有任何一个用例覆盖"反向 + `est_price=None`"组合（已用 `grep` 核实 `test_hedge_domain.py` 中 `est_price` 相关用例只覆盖正向不完整场景与已有价格场景），可通过补一个单测直接验证 `pf.rejection` 目前不是 `REJECT_PREFLIGHT_INCOMPLETE`。
- **建议修复**：让 `est_price` 的完整性检查与方向无关——要么在 `_check_common_quantity` 调用前统一要求 `est_price` 非空（缺失即 `REJECT_PREFLIGHT_INCOMPLETE`），要么让 `_check_common_quantity` 在价格缺失时返回一个"无法判定 minNotional"的显式不完整信号而不是静默跳过。

### P1 — 对账（reconciliation）已实现"绝不放弃"，但仍未实现"绝不阻塞下一次下单"，与 Review-2 required fix #5 的架构要求不符

- **文件**：`backend/hedge_open_tasks/service.py:816-871`（`tick`）与 `:1218-1265`（`_reconcile_pending`）；`backend/services/hedge_open_live_client.py:69`（`DEFAULT_TIMEOUT_SECONDS = 10.0`）；`backend/hedge_open_tasks/scheduler.py:36-52`（单线程轮询循环）。
- **证据**：`tick()` 在 `with self._lock:`（服务级、非重入 `threading.Lock`）整体范围内**先同步串行执行** `_reconcile_pending`（对每条非终态腿逐条调用 `self._executor.query_leg`，是一个纯 `for` 循环、零并发），**执行完毕后才**判断 `due`/Start/冷却/`list_eligible_tasks` 并派发新组。`HedgeOpenScheduler._loop`（`scheduler.py`）是唯一自动驱动源，且是单一后台线程串行调用 `tick()`——没有任何线程池或并发化改造对账循环（已用 `grep "ThreadPoolExecutor\|Thread("` 核实整个 `service.py` 只有 `_dispatch_eligible_concurrently` 一处用了 `threading.Thread`，对账循环完全没有）。`HedgeOpenLiveClient` 的查询超时仍是 10 秒（未改小，`50-review-2.md` 的 residual risk 里也明确点名了这一项）。
- **影响**：假设 3 个任务合计有 4 条非终态腿处于对账队列（例如 Binance 查询接口短暂降级、多个响应接近超时边界），`_reconcile_pending` 单次串行耗时可达 `4 × 10s = 40s`。由于这整段时间都在同一次 `tick()` 调用、同一把服务锁内执行，且调度线程是唯一驱动源，**这 40 秒内任何任务（哪怕零未决腿、完全独立）都无法获得新的一组下单**——这与 amendment I-6"对账...绝不阻塞下一秒开单"、"reconciliation is never abandoned... and never blocks another task's dispatch" 的逐字要求相反。修复报告 `40-fix-review-2-backend.md` §2.5 声称"reconcile 移到 tick 最前，无条件运行"解决了 Review-2 finding #5，但只解决了"被放弃"（Start 关/无 eligible 时不轮询）那一半，没有解决"阻塞下一次下单"那一半——这两半在 Review-2 原文里是并列写在同一条 finding 里的（"未终结腿可能永久失去轮询...对账本身...串行做所有阻塞 GET...慢查询会拖住下一秒计划"）。
- **验证方法**：现有 `test_5_reconciliation_invariants`（`test_hedge_review2_regressions.py:363`）等测试全部使用零延迟的 fake `query_leg`，从未注入一个"慢"或"阻塞"的查询来验证对账与派发之间的时间隔离，因此这个缺口不会被现有回归捕获——本人未运行新脚本验证实际耗时（不引入新代码属于只读审查边界），但代码路径本身（无线程池、无超时预算切分、同一把锁串行执行）足以确定性地得出"会阻塞"的结论,不依赖运行时猜测。
- **建议修复**：把非终态腿的对账查询从"tick 内同步串行"改为有限并发（如每条腿一个短生命周期线程/受限线程池，参照 `_dispatch_eligible_concurrently` 已有的按任务并发范式）并对总对账耗时设置预算上限，确保无论待对账腿数量或查询延迟如何，新一轮派发的发起时间不被对账队列长度线性拖慢；或将对账循环移出 `tick()` 持有的锁范围，使其与派发在时间上解耦。

### P2 — 当前订单限频事实只做"存在性"校验，未保留/使用交易所返回的实时用量响应头

- **文件**：`backend/services/hedge_open_live_client.py`（`_parse_retry_after` 附近，全文档 grep 确认只解析 `Retry-After`）；`backend/services/hedge_preflight_provider.py:227-244`（`_read_rate_limit_order` 只读取账户配置的限频**上限**，不追踪已用量）。
- **影响**：Review-2 原始 finding #3 的证据部分明确点名"没有保存返回的订单计数/权重响应头（如 `X-MBX-ORDER-COUNT-*`），无法执行批准的当前频率门禁"；本轮修复让"当前订单限频事实"变成了一个必须读到的静态上限值（缺失即 fail-closed），但没有实现对实时已用量的追踪/门禁，等于只解决了"下限值必须可读"而非"实时频率门禁必须可执行"。这比上面两条 P1 更边缘（真实超限时交易所仍会用 429/-1003 兜底，且该兜底路径已正确接入冷却机制），因此定为 P2，建议在下一轮或后续风险决策中补齐，而非本轮阻断项。

### P3 — 工作树存在与本次后端 diff 无关的未提交文件，阻塞 `validate-stage.py --phase pre-review`

- **文件**：`reports/agent-runs/2026-07-hedge-open-real-api-v1/59-review-1-frontend-r2.md`（新建、未跟踪）。
- **影响**：不改变已提交指纹或后端代码内容，纯属并行前端评审会话的产物尚未提交。仅记录给 bookkeeper 处理（提交或移出工作树），不计入本次后端 verdict 的判定依据。

## 必须修复后才能重审

1. 让最小名义金额（minNotional）校验的价格前提与开单方向无关：反向任务在 `est_price` 缺失/不可读时必须与正向一样返回 `REJECT_PREFLIGHT_INCOMPLETE`（fail-closed，零 attempt/零 POST/零计数），不得静默跳过 `_check_common_quantity` 的 notional 分支。补一个确定性单测：反向方向 + `est_price=None` 快照 → `compute_preflight` 结果为 `REJECT_PREFLIGHT_INCOMPLETE`。
2. 把非终态腿对账从"`tick()` 内同步串行、持有服务锁"改造为有限并发、有耗时预算的独立职责，使其耗时不随待对账腿数量/查询延迟线性拖慢同一 tick 内其他任务的新组派发。补一个确定性回归：注入一个刻意"慢"（例如需要显式信号才返回）的 `query_leg` 让某一任务的对账处于长耗时状态，断言另一个零未决腿、本应立即可派发的任务仍能在同一次或极短时间内的后续 `tick()` 中获得新的一组，而不是等待慢查询返回。
3.（P2，可与上两项一起完成或作为紧随其后的独立小任务）读取并保留交易所响应中的实时订单计数/权重头（如可得），为后续频率门禁积累事实基础；若本轮暂不实现主动限流逻辑，需在报告中明确记录为已知限制而非"已完全解决 finding #3"。

以上 1、2 两项是本轮 REWORK 判定的直接依据；3 为建议项，不单独构成阻断，但不得在下一份修复报告中被再次描述为"已完全修复"。

## Residual risks（已知且本轮不要求消除）

- 冻结政策本身允许单腿提示后继续调度，不自动取消/补单/平仓/修复；真实资金仍可能在人工介入前扩大单腿敞口，这是产品既定选择，非缺陷。
- 本次评审未访问真实 Binance 私有接口；修复后的参数兼容性、账户字段真实形态仍需人工授权的安全环境采集脱敏证据。
- 10 秒查询超时与 60000ms `recvWindow` 仍偏宽——这是上面 P1 对账问题的根因之一，一并在下一轮收紧或提供充分的架构解耦证据。
- 自动补单/取消/平仓/转账/还币/完整会计仍不在本阶段范围，UI 必须继续如实标注不存在。

当前 Session ID: unavailable (Claude Code 未暴露 provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/58-review-1-backend-r2.md
本地北京时间: 2026-07-24 22:19:33 CST
下一步模型: bookkeeper
下一步任务: validate this REWORK verdict against the frontend review-1 verdict, preserve raw findings, prepare the bounded fix dispatch from fix_start_prompt, then recompute committed evidence and re-enter review-1/review-2 as required

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-hedge-open-real-api-v1",
  "role": "first_reviewer",
  "model": "Claude Sonnet 5",
  "verdict": "REWORK",
  "diff_fingerprint": "8af3f22d92354fdac61a6a057eb25760b924004b:cbd0d92f53cbaaaab444812dd6ce5bd4bcc07aa947a923dd2a33014a74e5d320",
  "reviewer_prior_involvement": "none",
  "reviewer_prior_involvement_notes": "This reviewer (Claude Sonnet 5, Anthropic) authored frontend rework earlier in this stage (40-fix-review-2-frontend.md, 41-fix-open-log-pagination-frontend.md) but wrote none of the reviewed backend code (backend/hedge_open_tasks/**, backend/services/hedge_*), whose sole implementer/fixer is Claude-GLM (zhipu_glm). Provider-level cross-review isolation from the backend author holds.",
  "reviewed_artifacts": [
    "AGENTS.md",
    "workflows/templates/stage-delivery.yaml#review_1",
    "docs/product/PRD.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/00-task.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/04-user-execution-policy.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/15-immediate-loop-and-open-log-amendment.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/16-replacement-development-breakdown.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/17-opening-log-pagination-compatibility.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/19-replacement-r4-final-reconciliation.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/20-r4-scope-deviation-domain-cursor.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/40-fix-review-2-backend.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/41-fix-open-log-pagination-backend.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/50-review-2.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/60-test-output.txt",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/status.json",
    "schemas/review-verdict.schema.json",
    "git diff --binary 28c550d87c1ca90983d5bde9c7102d42cffecd4e..8af3f22d92354fdac61a6a057eb25760b924004b",
    "backend/hedge_open_tasks/domain.py",
    "backend/hedge_open_tasks/executor.py",
    "backend/hedge_open_tasks/service.py",
    "backend/hedge_open_tasks/store.py",
    "backend/hedge_open_tasks/scheduler.py",
    "backend/services/hedge_open_live_client.py",
    "backend/services/hedge_preflight_provider.py",
    "backend/services/live_hedge_executor.py",
    "backend/app/server.py",
    "backend/tests/test_hedge_domain.py",
    "backend/tests/test_hedge_purity.py",
    "backend/tests/test_hedge_review2_regressions.py",
    "backend/config.py"
  ],
  "findings": [
    {
      "severity": "P1",
      "title": "Reverse-direction minNotional check silently skipped when est_price is unreadable, not fail-closed",
      "file": "backend/hedge_open_tasks/domain.py",
      "line": 572,
      "evidence": "_check_common_quantity's minNotional loop is gated by `if est_price is not None and est_price > 0`, so a missing price skips the check entirely rather than rejecting. compute_preflight only converts a missing est_price into REJECT_PREFLIGHT_INCOMPLETE on the DIR_FORWARD branch (lines 677-689); the DIR_REVERSE branch (692-703) never reads or requires est_price. HedgePreflightProvider.get_snapshot's fail-closed gate (hedge_preflight_provider.py:270-277) checks spot/perp/balances/position_mode/rate_limit but not est_price, so a transient public ticker-price read failure still yields a snapshot judged 'complete' for a reverse task.",
      "impact": "A reverse (negative-funding, sell-base) task can pass fresh preflight and reach live POST with a q_common that was never validated against either leg's minNotional filter, when the frozen contract requires price/balance/notional/filter facts to all be present before send regardless of direction. No existing test (test_hedge_domain.py) covers reverse-direction + missing est_price.",
      "recommendation": "Require est_price for both directions before evaluating _check_common_quantity's notional branch; a missing/invalid price must yield REJECT_PREFLIGHT_INCOMPLETE regardless of direction, mirroring the existing forward-only guard. Add a deterministic test: DIR_REVERSE snapshot with est_price=None must reject as REJECT_PREFLIGHT_INCOMPLETE."
    },
    {
      "severity": "P1",
      "title": "Reconciliation still runs synchronously/serially inside the locked tick before dispatch, so it can still stall other tasks' new-pair dispatch (Review-2 fix 5 only half-addressed)",
      "file": "backend/hedge_open_tasks/service.py",
      "line": 842,
      "evidence": "tick() wraps the whole call in `with self._lock:` and runs _reconcile_pending (a plain serial for-loop over list_non_terminal_legs, one blocking query_leg call per leg, no threading) BEFORE checking due/Start/cooldown/eligible and dispatching. HedgeOpenScheduler._loop is the sole automatic driver and calls tick() serially from one background thread. HedgeOpenLiveClient.DEFAULT_TIMEOUT_SECONDS is still 10.0 (unchanged, and flagged as a residual concern in 50-review-2.md). No test (test_5_reconciliation_invariants et al.) injects a slow/blocking query_leg to verify timing isolation between reconciliation and dispatch.",
      "impact": "With several non-terminal legs and slow/near-timeout query responses, a single tick's reconciliation pass can take tens of seconds while holding the only scheduling path's lock, delaying new-pair dispatch for EVERY task (including tasks with zero pending legs) for that duration. This contradicts the amendment's explicit 'reconciliation ... never blocks another task's dispatch' requirement and only fixes the 'never abandoned' half of the original Review-2 finding 5, not the 'never blocks' half.",
      "recommendation": "Decouple non-terminal-leg reconciliation from the locked dispatch path: run per-leg queries with bounded concurrency (mirroring the existing per-task threading in _dispatch_eligible_concurrently) and/or a time budget, so reconciliation latency never gates a same-tick or next-tick dispatch for unrelated tasks. Add a deterministic regression with an injected slow query_leg proving an unrelated, zero-pending task still gets its next pair promptly."
    },
    {
      "severity": "P2",
      "title": "Current order rate-limit fact is only existence-checked, not used to track/enforce real-time order-count consumption",
      "file": "backend/services/hedge_open_live_client.py",
      "line": 100,
      "evidence": "Only the Retry-After header is parsed anywhere in hedge_open_live_client.py; X-MBX-ORDER-COUNT-*/weight response headers are never captured. hedge_preflight_provider.py._read_rate_limit_order only reads the account's configured ORDERS rate-limit ceiling, not live usage.",
      "impact": "Review-2's original finding explicitly named missing order-count/weight header preservation as blocking an enforceable current-rate gate; this round makes the ceiling fact a fail-closed existence requirement but still cannot enforce real-time usage locally (the exchange's own 429/-1003 rejection remains the only backstop, which is correctly wired to the cooldown).",
      "recommendation": "Capture and retain available rate-usage response headers as a basis for a future active throttle, or explicitly document this as an accepted residual limitation rather than a fully closed finding in the next fix report."
    },
    {
      "severity": "P3",
      "title": "Worktree carries an unrelated untracked file that fails the pre-review validator gate",
      "file": "reports/agent-runs/2026-07-hedge-open-real-api-v1/59-review-1-frontend-r2.md",
      "line": null,
      "evidence": "scripts/validate-stage.py --phase pre-review fails with 'review/acceptance gates require a clean committed worktree' due to this untracked file, produced by the parallel frontend review-1 session, not part of the reviewed backend diff.",
      "impact": "Does not affect the committed diff or fingerprint under review, but blocks the mechanical pre-review gate check and needs bookkeeper handling (commit or otherwise reconcile) before either review-1 verdict can be formally re-entered.",
      "recommendation": "Bookkeeper commits or relocates this file per the frontend review-1 workflow before recomputing gates."
    }
  ],
  "required_fixes": [
    "Make the minNotional/est_price completeness check direction-independent: a missing/invalid est_price must yield REJECT_PREFLIGHT_INCOMPLETE for DIR_REVERSE exactly as it already does for DIR_FORWARD, with a new deterministic test covering the reverse+missing-price case.",
    "Decouple non-terminal-leg reconciliation from the single locked tick path with bounded concurrency and/or a time budget so its latency cannot delay another task's next-pair dispatch; add a deterministic regression with an injected slow query proving this.",
    "Either capture exchange rate-usage response headers toward a real enforceable current-rate gate, or explicitly document the existence-only check as an accepted residual limitation instead of describing finding 3 as fully resolved."
  ],
  "residual_risks": [
    "The approved policy intentionally continues scheduling after a single-leg exposure and has no automatic repair; bounded target_n limits but does not remove real naked-exposure risk.",
    "No real Binance private request was made in this review; corrected live field compatibility and rate-limit headers still require authorized, sanitized factual evidence.",
    "The current 10-second query timeout and 60000ms recvWindow remain broad and are a direct contributor to the P1 reconciliation-blocking finding above; tightening or architectural decoupling should be demonstrated together.",
    "Cancel, close, repay, transfer, automatic remediation, and full accounting remain explicitly outside this stage."
  ],
  "fix_start_prompt": "[HARNESS-EXECUTOR-CONTRACT v1]\n你是 2026-07-hedge-open-real-api-v1 的返工实现者（后端）。禁止调用、启动或转派任何其他模型/adapter。先逐字读取本文件 reports/agent-runs/2026-07-hedge-open-real-api-v1/58-review-1-backend-r2.md（含最后 JSON verdict），以及 15-immediate-loop-and-open-log-amendment.md、16-replacement-development-breakdown.md（§2.1 I-7、§3.2 A-3/A-5）；固定被审指纹 8af3f22d92354fdac61a6a057eb25760b924004b:cbd0d92f53cbaaaab444812dd6ce5bd4bcc07aa947a923dd2a33014a74e5d320 不得作为你的提交基线——你将在其之上继续修改，bookkeeper 会在你完成后重算新指纹。\n\n必须修复两项：\n\n1) backend/hedge_open_tasks/domain.py：compute_preflight 对 est_price 缺失/不可读（None 或 <=0）的完整性要求必须与开单方向无关。当前只有 DIR_FORWARD 分支在 est_price 缺失时返回 REJECT_PREFLIGHT_INCOMPLETE（约677-689行），DIR_REVERSE 分支（约692-703行）完全不检查 est_price，且 _check_common_quantity（约552-578行）的 minNotional 校验在 est_price 为 None 时被整段跳过而非拒绝。修复：让价格完整性检查在方向分支之前统一执行，或让 _check_common_quantity 在价格缺失时返回一个会被上层识别为 REJECT_PREFLIGHT_INCOMPLETE 的显式信号，确保反向任务在价格不可读时同样 fail-closed（零 attempt、零 POST、零失败计数）。新增确定性单测：反向方向 + est_price=None 的 PreflightSnapshot → compute_preflight 结果必须是 REJECT_PREFLIGHT_INCOMPLETE。\n\n2) backend/hedge_open_tasks/service.py：_reconcile_pending 当前是 tick() 持有服务锁期间的同步串行循环（对每条非终态腿逐条阻塞查询），且是调度线程唯一驱动源，查询超时仍是 10 秒（hedge_open_live_client.py DEFAULT_TIMEOUT_SECONDS）。多条待对账腿或慢查询会导致本次 tick 耗时线性增长，期间任何任务（含零未决腿的任务）都无法获得新的一组下单，违反 amendment 'reconciliation ... never blocks another task's dispatch'。修复：把非终态腿对账改造为有限并发（可参照已有的按任务并发范式 _dispatch_eligible_concurrently）并设置耗时预算，使一次 tick 的对账阶段不会因待对账腿数量或查询延迟而线性拖慢同一批次或后续批次的新组派发。新增确定性回归：注入一个需要显式信号才返回的慢速 query_leg，让某任务的对账长时间挂起，断言另一个零未决腿、本应立即可派发的任务仍能在合理短时间内的后续 tick 中拿到新的一组，不等待慢查询。\n\n可选（P2，不单独构成阻断，但请勿在报告中再次描述为'已完全解决'）：在 hedge_open_live_client.py 中捕获交易所返回的实时订单计数/权重响应头（如可得），为未来主动频率门禁积累事实基础；若本轮不实现，请在修复报告的剩余风险中明确写出这仍是已知限制。\n\n允许修改：backend/hedge_open_tasks/{domain.py,executor.py,scheduler.py,service.py,store.py}，backend/services/{hedge_open_live_client.py,hedge_preflight_provider.py,live_hedge_executor.py}，backend/app/server.py（仅为独立恢复职责所需的最小接线），直接相关 backend/tests/test_hedge_*.py 与 test_live_hedge_executor.py。禁止修改：frontend/**、docs/**、PRD、设计/ADR、status.json、70-handoff.md、50-review-2.md、本评审文件 58-review-1-backend-r2.md、15/16/17/19 号契约文档、环境/凭据文件、任何真实网络配置。绝不读取凭据、绝不连接 Binance、绝不发送真实 POST、绝不启用 live/Start。\n\n精确自测（在提交前全部跑绿，并把原始输出追加到 reports/agent-runs/2026-07-hedge-open-real-api-v1/60-test-output.txt）：\n.venv/bin/python -m pytest backend/tests/test_hedge_domain.py backend/tests/test_hedge_store.py backend/tests/test_hedge_service.py backend/tests/test_hedge_api.py backend/tests/test_hedge_open_live_client.py backend/tests/test_live_hedge_executor.py backend/tests/test_hedge_executor.py backend/tests/test_hedge_purity.py backend/tests/test_hedge_review2_regressions.py -q\n.venv/bin/python -m pytest backend/tests -q\nnode frontend/self-check.js\n.venv/bin/python -m pytest scripts/tests/test_validate_stage_dispatch_protocol.py -q\ngit diff --check\n\n把实现说明写入 reports/agent-runs/2026-07-hedge-open-real-api-v1/40-fix-review-1-backend-r2.md（新文件，不覆盖已有 40/41 号报告），列出 changed files、每条新增回归测试先复现旧缺陷再验证修复的证据、剩余风险，然后停止等待 bookkeeper；不得提交、不得派发评审、不得自行判定验收。成功标准：上述两条新增测试先能在修复前的代码路径上复现所述缺口（或以清晰推导说明为何在当前代码上必然复现），修复后全部转绿，完整 backend/frontend 回归通过，且没有任何真实 POST/私有网络。",
  "next_action": "fix"
}
```

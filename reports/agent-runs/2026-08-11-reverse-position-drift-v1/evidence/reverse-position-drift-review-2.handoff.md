# Task Handoff: reverse-position-drift-review-2

## Source Report (author-only; immutable after task end)
- task_id: `reverse-position-drift-review-2`
- role: Reviewer（review-2 / reality-checker，只读）
- target model: Opus 5（provider: `anthropic`，fresh session；Human 本轮显式选定，取代默认 `sonnet5`）
- stage_id: `2026-08-11-reverse-position-drift-v1`
- created_at: 2026-08-11 18:10:23 CST
- base_sha: `7194876e61c037d238d0e3d621a094d7dd3a6e43`
- delivery_sha: `f1d929178a346026bccab8fe98d4cfa69761d8a0`

### 结论

**评审结论：ACCEPT。** 固定区间 `7194876e..f1d92917` 的交付满足 Human 批准的需求，证据链完整且可复现，无阻断性 in-range 发现。四条非阻断观察（O-1..O-4）记录在下，其中 O-2/O-4 建议作为文档类后续项，不要求本轮修复。ACCEPT 仅为评审收口，不构成合并、部署、实盘或账户动作授权。

### 身份与区间核验

- `status.json`：`revision=5`、`stage_id=2026-08-11-reverse-position-drift-v1`、`phase=review-2`、`current_task.id=reverse-position-drift-review-2`、`state=dispatched`、`bookkeeper=codex`、`rework_count=0`、`blockers=[]`，与 dispatch 一致。
- `git rev-parse` 两端 SHA 均解析成功且 base 是 delivery 的祖先；未移动 HEAD（当前 `HEAD=ad3ec79eaa2272c0d501be151527b8422f594276` 为后续 bookkeeping 提交，未用于替换 delivery SHA）；`git status --porcelain` 为空。
- provider 隔离：实现作者 Codex（`openai`），计划评审 Kimi（`moonshot`），review-1 `claude_glm`（`zhipu_glm`），本 review-2 `anthropic`——与区间内全部实现/修复作者跨 provider；本模型未参与本阶段计划或实现。
- 区间 4 提交：`c58e718` 开阶段 / `1892c8b` 路由计划评审 / `4aab866` 路由实现（三者为阶段控制上下文，按 AGENTS.md §8 评审范围口径不作受审交付）+ 唯一交付提交 `f1d9291`。`git show --stat f1d9291` = 7 个 dispatch 批准文件 + 实现 handoff + `status.json`（仅 `current_task.state` 迁移），无控制提交夹带产品代码。

### 需求满足度（实际效果，非摘要）

受审改动只有两处产品代码：

1. `backend/domain/snapshot.py:1292` 在统一账户行原样投影 `crossMarginLocked -> cross_margin_locked`（缺键即 `None`），并同步 `schemas/api/public-market/snapshot.schema.json` 声明 additive/optional 键；估值、排序、总额、warning、刷新与 transport 均未动。
2. `backend/hedge_open_tasks/domain.py`：`_merge_num` 增加 `is_finite()` 守卫；`_merge_build_row` 对 `direction == reverse` 先置 `drift=False`；`merge_positions` 在合并完成、排序之前按解析后现货基础资产分组，`R=Σ spot_qty`、`A=max(B-F-L,0)`，`drift = (R-A) > R × _EXPOSURE_IMBALANCE_TOLERANCE`，一组一 verdict 回填组内每行。

逐条对照 Human 批准的结果：

- 借币已卖出场景（`R=100,B=100,F=0,L=0` → `A=100`）不再仅因统一账户 free 为零而误判——主回归成立，`test_merge_reverse_drift_uses_borrowed_minus_free_and_locked` 第 1 例断言 `drift False`。
- 借币未卖（`F=100`）、挂单锁定（`L=100`）、部分成交（`F=30`）、严格超 1%（`free=1.001` → 短缺 1.001%）四种仍告警；恰好 1%（`free=1`）不告警，全程 `Decimal`，与文档口径一致。
- 利息不入公式：`crossMarginInterest` 未被投影为数量键，行级 `borrow_interest` 未参与聚合，`test_merge_reverse_drift_excludes_account_and_local_interest` 在两侧各放大额利息后 verdict 不变。
- 账户级只消费一次：同资产两行（60/40）在 `A=100` 时同为 `False`、`A=70` 时同为 `True`，证明不重复消费账户借款。
- fail-closed：B/F/L 任一缺失/空/文本/`NaN`/`Infinity`/负（3×6 参数化）、本地 `spot_qty` 同六种坏值、`closed`/`no_task` 行、账户不可读、缺统一账户资产行——全部保持 `drift=False`，不抛异常、不部分求和、不以零替代。
- forward 未变：`_merge_build_row` 的 forward 分支逐字保留（`held = 普通现货 free+locked + unified total_balance`，严格 `held < spot_qty`）；`test_merge_forward_drift_ignores_reverse_account_fields` 在统一账户放入 `borrowed=999/free=888/locked=777` 后 forward 三例（大于/等于/小于）结论不变。
- positions API 与前端 wire 未变：`cross_margin_locked/free/borrowed` 只在 merge 内消费，未新增行字段；`test_positions_reverse_drift_keeps_existing_wire_keys` 断言 `set(position) == _POSITION_KEYS` 且 reverse `drift` 正确穿透 `GET /api/hedge-open-positions`。静态确认 `frontend/index.html:6379` 仍是唯一消费点（`if (p.drift) …「本地记录与实际不一致」`），前端零改动。

### 安全面（本交付不能做什么）

独立核查而非采信摘要：交付 7 文件中产品代码仅 2 个展示/校验文件，另有 1 schema、3 测试、1 文档；无订单、借币、还款、划转、preflight、闸门、凭据、部署、服务控制或运行数据写入路径被触碰。`_merge_num` 的全部调用点（`domain.py:1935/1984/1985/2015/2025/2095/2096/2184/2194/2195/2196`）都在展示合并层内；`grep` 确认 `backend/services/hedge_preflight_provider.py` 与 `backend/services/live_hedge_executor.py` 完全不消费 `private_account` 余额行，故新增键与新守卫不可能改变下单/平仓判断。`balances_unified` 的另外两个后端消费者（`backend/app/server.py:759` 划转资产集合、`:908` 还款借款资产集合）都按具名键读取，additive 键对其无影响。

### 证据栈评估

| 证据 | 状态 | 本次核查 |
| --- | --- | --- |
| 跨 provider 计划评审（Kimi/`moonshot`） | ACCEPT，Bookkeeper 已封存（revision 2） | 结论与 `修复要求: none` 属实 |
| 实现（Codex/`openai`）单次交付 | Bookkeeper 核验 pass（revision 3），范围恰为 7 文件 | `git show --stat` 复核一致 |
| 跨 provider review-1（`claude_glm`/`zhipu_glm`） | ACCEPT，已封存（revision 4），仅一条非阻断观察 O-1 | 复核其 10 项结论逐条属实，未发现粉饰 |
| 三次独立 224 项测试 | 实现者、Bookkeeper、review-1 各一次 | 本次第四次独立复跑：`224 passed in 24.28s` |
| 固定区间 diff 检查 | `git diff --check` exit 0 | 本次复跑 exit 0 |
| 后端全量回归（超出 dispatch 要求，用于发布就绪判断） | — | 本次首次执行：`1756 passed in 154.85s` |
| Human 前端验收 | Human 报告通过 | 见下方口径 |

**Human 前端验收证明什么、不证明什么。** 只读 `ps` 观察到当前后端进程 `python -m backend.app.server` 启动于 `2026-08-11 17:50:51`，晚于交付提交 `f1d9291`（`17:38:01`），故该进程加载的是含本次修复的工作树代码——这排除了「验收跑在旧代码上」这一最常见的假验收。它**证明**：在 Human 当时的真实账户状态下，reverse 行不再显示「本地记录与实际不一致」，且页面未因新字段/新分支报错。它**不证明**：告警一侧（借而未卖、挂单锁定、部分短缺、严格超 1%）在实盘会如期点亮；坏值/不可读的 fail-closed 分支在实盘走过；本地账本与币安已完成对账。这些当前只有离线断言覆盖。

### 遗留行为与运营风险（诚实陈述）

- `drift=false` 仍只是「本轮没有可证明的告警」，**不是对账证明**。reverse 侧新增两类假阴性来源：至多 1% 的短缺被既有容差吸收；任一必要输入无效/缺失即回落到 `false`。
- 账户级聚合**不把负债分配到具体周期**（已批准的非目标）。因此公式把该资产在统一账户的全部 free/locked 都当作「借来但尚未卖出」。
- 前端文案「本地记录与实际不一致」对两个方向共用一句，reverse 下的实际含义是「已卖出敞口小于本地记账」；本轮未改文案，Human 读该红字时需要知道方向语义不同。
- 快照有刷新周期：现货腿成交与下一次账户刷新之间，`F` 仍计入尚未反映的数量，reverse 行可能出现**短暂**告警，下一轮刷新自愈。旧行为是**长期**误报，此为严格改善。
- `PROJECT_STATE.md` 的 `[OPEN][LIVE-RISK][2026-08-10]`「reverse 自动平仓仍可能因组合保证金口径再次单腿」与本交付**无关且仍未解决**：本次未触碰 close/preflight/执行链任何一行。其临时边界「修复前不要使用 reverse 自动平仓；如需处置由 Human 在币安逐腿核对并人工收口」**继续有效**，本次展示修复不得被读作「reverse 平仓已安全」。
- 合并后若要让运行中的服务生效，须由 Human 重启当前手动前台进程（`PROJECT_STATE.md` 运营条目）；本评审不授权也未执行任何服务控制。

### 发现与范围分类（AGENTS.md §8）

- **O-1（in-range，非阻断，非缺陷；沿用 review-1）**：`_merge_num` 的 `is_finite()` 守卫是共享 seam，同时收紧 forward、`single_leg_exposure`、`price_pnl`。独立核查：现实输入（本地 `Decimal` 记账量、交易所有限小数串）下行为逐字节不变，仅非有限输入的 verdict 改变，且新行为正是计划规则 6 要求的 fail-closed。该守卫是**必需**的：若无它，`qty < 0` 对 `Decimal("NaN")` 会抛 `InvalidOperation`，把坏数据变成 positions API 500。1756 项全量回归无回归。
- **O-2（in-range，非阻断，建议文档类后续项）**：`A = B - F - L` 把该资产在统一账户的全部 free/locked 归因于本次借币。证据锚点：`backend/hedge_open_tasks/domain.py:2194-2199` 读取的是账户级字段、无周期归因；且同币双向共存是已记录的领域事实（`docs/planning/display-truth-and-multiplier-block-2026-08-07.review-kimi.md:101-112` 的 review 发现 2 明确「同币双向共存是可能的」，并在 forward 侧记录了对称的假阳性）。实际影响：同一币同时存在活跃 forward 周期（现货腿按 `decide_spot_route` 落在统一账户，计入 `crossMarginFree`）与活跃 reverse 周期时，`A` 被低估，reverse 行可能**假阳性**告警；反之该资产存在与本策略无关的借款时 `B` 被高估，可**掩盖**真实短缺。判定为非阻断：纯展示告警、无资金动作、无自动处置；假阳性方向偏保守（宁可报警）；根治需按周期归因负债，而这是本轮已批准的明确非目标，本轮修反而扩大范围。建议：在 `docs/api/public-market-contract.md` 的 drift 章节补一句该归因边界（与既有 1% 与 fail-closed 说明并列）。重开触发条件：Human 在 reverse 行看到红字但币安核对一致，或需要同币双向并存运行。
- **O-3（in-range，非阻断，固有）**：快照刷新周期导致的短暂假阳性（见上「遗留行为」）。属展示缓存固有性质，无需修复，记录以免被误读为回归。
- **O-4（pre-existing-independent，非阻断）**：`docs/api/public-market-contract.md` 的 drift 章节至今未记录 **forward 侧**「同资产借币负债净减 `total_balance` 造成假阳性」这一来源。引入早于 `base_sha`：该建议出自 2026-08-07 的 review（文件 `docs/planning/display-truth-and-multiplier-block-2026-08-07.review-kimi.md`，引入提交 `bbeb130`），而 `git show 7194876e:docs/api/public-market-contract.md` 在 base 时点的 drift 段（第 1992 行起）只写了假阴性一侧。本交付重写了相邻条目但未涉及 forward 语义，故不阻塞本次交付；与 O-2 属同一族，建议一并补齐。

无 `pre-existing-release-critical` 发现。本评审未引入任何用于阻塞交付的新假设场景：O-2 附有可追溯代码路径与已记录领域事实两类证据锚点，但仍按非阻断处理，理由已在该条内说明。

### 未完成事项

无。本评审只读：未改交付/控制文件、`status.json`、既有证据、计划、dispatch、docs 或源码；未提交、未合并、未 push、未部署、未启动或控制服务、未访问凭据、未调用任何本地或实盘 API、未做任何账户动作；唯一写入是本交接件（create-only）。

### 命令与结果

```text
git rev-parse HEAD                                        -> ad3ec79eaa2272c0d501be151527b8422f594276（后续 bookkeeping 提交，未用作 delivery）
git status --porcelain                                    -> 空（工作树洁净）
git rev-parse 7194876e61c037d238d0e3d621a094d7dd3a6e43     -> 7194876e61c037d238d0e3d621a094d7dd3a6e43
git rev-parse f1d929178a346026bccab8fe98d4cfa69761d8a0     -> f1d929178a346026bccab8fe98d4cfa69761d8a0
git merge-base --is-ancestor <base> <delivery>            -> ANCESTOR_OK
git log --oneline <base>..<delivery>                      -> 4 提交（3 控制 + 唯一交付 f1d9291）
git diff --stat <base>..<delivery>                        -> 15 文件（7 交付 + 8 阶段控制/证据），782 insertions
git show --stat f1d9291                                   -> 7 批准文件 + implement.handoff.md + status.json（仅状态迁移）
git diff <base>..<delivery> --check                       -> exit 0
python3 -m pytest backend/tests/test_private_account_v1.py backend/tests/test_positions_merge.py backend/tests/test_hedge_api.py
                                                          -> 224 passed in 24.28s
python3 -m pytest backend/tests                            -> 1756 passed in 154.85s（本次额外全量回归）
grep 校验：_merge_num 调用点全在展示合并层；hedge_preflight_provider.py / live_hedge_executor.py 不消费 private_account 余额行；
           server.py:759/:908 按具名键读取 balances_unified；frontend/index.html 仅 6379 一处消费 p.drift
ps -eo pid,lstart,command（只读，未调用服务）             -> `python -m backend.app.server` 启动于 2026-08-11 17:50:51，晚于交付提交 17:38:01
test ! -e <本交接件路径>                                   -> Bookkeeper 预检记录 HANDOFF_PATH_ABSENT，本任务新建
```

### Required Reading for the Next Task
- 读取路径及顺序：`reports/agent-runs/2026-08-11-reverse-position-drift-v1/evidence/reverse-position-drift-review-2.handoff.md`、`reports/agent-runs/2026-08-11-reverse-position-drift-v1/status.json`、`PROJECT_STATE.md`
- 执行：Bookkeeper（codex）在同一文件核验本 review-2 交接（源区块 SHA-256、verified_status_revision 5、`评审结论: ACCEPT` 闭合行、create-only 路径与 task_id/role/stage_id/base_sha/delivery_sha 一致性），封存后按 AGENTS.md §9 准备收口材料，并把 O-2 与 O-4 两条文档类后续项写入 `PROJECT_STATE.md` Open Follow-ups
- 关卡：Human 依据封存结果做最终业务验收与是否合并的决定；合并、部署、实盘操作仍须 Human 单独明确授权
- 不能假设的事实：ACCEPT 不等于最终验收，也不授权合并/部署/实盘/服务控制；`drift=false` 不是对账证明；reverse 公式不把负债按周期归因，同币双向共存时可能假阳性；`PROJECT_STATE.md` 的 reverse 自动平仓组合保证金 LIVE-RISK 与其临时边界仍然有效且未被本次交付改变；合并后需 Human 手动重启前台服务进程才生效

## Human Brief / Console Receipt Source (author-only; immutable after task end)

```text
[TASK_RESULT v2]
任务 ID: reverse-position-drift-review-2
执行结果: completed（完成）
结果摘要: 固定区间 7194876e..f1d92917 的 review-2 结论 ACCEPT。交付仅 7 文件、两处展示层代码：统一账户新增 locked 投影；reverse 改按账户资产聚合，用 A=max(B-F-L,0) 与既有 1% Decimal 容差判 drift，坏值与不可读一律 fail-closed，forward 与 positions/前端接口逐字未变。独立复跑 224 项与全量 1756 项测试全绿，diff 检查通过。四条非阻断观察已记录。
产物: [reports/agent-runs/2026-08-11-reverse-position-drift-v1/evidence/reverse-position-drift-review-2.handoff.md]
检查结果: [status revision 5/任务身份/双 SHA/跨 provider 隔离/工作树洁净: pass; 交付仅 7 文件、控制提交无夹带产品代码: pass; 已卖出不再误报且未卖/锁定/部分/严格超1%仍告警: pass; 坏值·缺资产行·账户不可读·closed·no_task 全部 fail-closed 且不抛异常: pass; forward 逐字保留、positions wire 键集与前端零改动: pass; 无订单/借币/划转/闸门/凭据/部署/服务控制路径被触碰: pass; 独立复跑 224 passed 与全量 1756 passed、git diff --check exit 0: pass; 证据栈完整（计划评审+实现封存+review-1+四次测试+Human 前端验收，且服务进程启动晚于交付提交）: pass]
阻塞项: [none]
本地北京时间: 2026-08-11 18:10:23 CST
下一步模型: codex（Bookkeeper，核验并封存本 review-2 交接）
下一步任务: 读取：reports/agent-runs/2026-08-11-reverse-position-drift-v1/evidence/reverse-position-drift-review-2.handoff.md、reports/agent-runs/2026-08-11-reverse-position-drift-v1/status.json、PROJECT_STATE.md；执行：Bookkeeper（codex）同文件核验源区块 SHA-256、revision 5 与 ACCEPT 闭合行并封存，按 §9 准备收口材料并把 O-2、O-4 两条文档类后续项记入 PROJECT_STATE.md Open Follow-ups；关卡：Human 做最终业务验收与合并决定，合并/部署/实盘仍须单独授权
评审结论: ACCEPT（接受）
问题记录: reports/agent-runs/2026-08-11-reverse-position-drift-v1/evidence/reverse-position-drift-review-2.handoff.md
修复要求: none
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- source_sha256: `c45751c3fbd88cbaffb4939bb2a362b02738d3b8e0237601483cadf6644033e0`
- verified_at: `2026-08-11 18:21:35 CST`
- verified_status_revision: `5`
- verification_result: `pass`
- identity_check: task `reverse-position-drift-review-2`, Reviewer/Opus 5 (`anthropic`), stage `2026-08-11-reverse-position-drift-v1`, base SHA `7194876e61c037d238d0e3d621a094d7dd3a6e43`, and delivery SHA `f1d929178a346026bccab8fe98d4cfa69761d8a0` match the routed packet, status, and direct `git rev-parse` results; the implementation/review provider isolation chain is consistent.
- closure_check: Human Brief is a closed `TASK_RESULT v2` with `completed`, eight `pass` checks, no blocker, explicit `评审结论: ACCEPT（接受）`, problem record pointing to this handoff, and `修复要求: none`.
- scope_check: routing commit `ad3ec79eaa2272c0d501be151527b8422f594276` did not contain this path; the returned worktree contained only this newly-created deterministic reviewer handoff and no delivery/state modification.
- evidence_check: reviewer independently reported targeted `224 passed`, full backend `1756 passed`, and fixed-range diff check exit 0; Human frontend acceptance ran against a process started after the delivery commit. These prove the tested/display effects, not live reconciliation or every warning/fail-closed branch.
- finding_check: O-1 and O-3 are non-blocking observations. O-2 is an in-range, non-blocking documentation follow-up with current code/domain anchors. O-4 is `pre-existing-independent`; commit `bbeb1306c877e00685e455986cbb8ec6d58adb0e` is a verified ancestor of base. O-2/O-4 are recorded in `PROJECT_STATE.md`; neither changes the ACCEPT verdict or `rework_count`.
- safety_check: the existing reverse auto-close combination-margin LIVE-RISK and its temporary prohibition remain active and unrelated to this display-only delivery; no merge, push, deployment, service control, or live action was performed.
- subsequent_state: review-2 sealed as accepted; the stage waits for Human final business acceptance and remote-submit/archive decision.

## Errata (append-only)

（无。）

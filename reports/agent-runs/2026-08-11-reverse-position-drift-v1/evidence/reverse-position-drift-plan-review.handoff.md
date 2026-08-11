# Task Handoff: reverse-position-drift-plan-review

## Source Report (author-only; immutable after task end)
- task_id: `reverse-position-drift-plan-review`
- role: Reviewer（只读计划评审）
- target model: Kimi（provider: moonshot，fresh session）
- stage_id: `2026-08-11-reverse-position-drift-v1`
- created_at: 2026-08-11 17:17:43 CST
- base_sha: `7194876e61c037d238d0e3d621a094d7dd3a6e43`
- delivery_sha: none（计划评审无交付提交）

### 任务背景

reverse（借币卖现货 + 开多合约）现货腿卖出后，统一账户可用余额可为零而借款本金仍为正；现有 `drift` 把「账户持有量 < 本地卖出量」误当不一致。Planner（codex/openai）产出 `10-plan.md`，本任务对其进行跨 provider 只读计划评审，判其是否为当前代码与账户字段证据支持的最小可实现计划。HIGH_RISK（改变持仓与借款含义），本评审不递增 `rework_count`。

### 只读评审范围（实际读取）

- `reports/agent-runs/2026-08-11-reverse-position-drift-v1/10-plan.md`、`reverse-position-drift-plan.dispatch.md`、`reverse-position-drift-plan-review.dispatch.md`、`status.json`
- `AGENTS.md`、`PROJECT_STATE.md`、`agents/roles.md`（Reviewer 节与 Task Handoff Evidence Contract）
- `backend/services/private_client.py:584-606`（`fetch_unified_balances` 原样透传 `/papi/v1/balance`）
- `backend/services/snapshot_service.py:920-959`、`:1420-1459`（缓存 unified 列表并交给 `assemble_private_account`，无新增请求）
- `backend/domain/snapshot.py:1268-1297`（unified 投影：当前只投 `crossMarginBorrowed`/`crossMarginFree`，`crossMarginLocked` 确实在此丢失，与计划陈述一致）
- `backend/hedge_open_tasks/domain.py:1797-1842`、`:1886`、`:1900-2161`（`_merge_base_asset`/`_merge_num`/`_EXPOSURE_IMBALANCE_TOLERANCE=Decimal("0.01")`、`merge_positions` 与 `_merge_build_row` 的 drift 段）
- `backend/app/server.py:1312-1359`（零上游读快照、纯函数 merge、原样返回既有字段）
- `schemas/api/public-market/snapshot.schema.json:540-583`（`balances_unified` `additionalProperties:false`，新增投影键必须声明，与计划一致）
- `backend/tests/test_private_account_v1.py:1136-1145`（原始字段集合含 `crossMarginBorrowed`/`crossMarginFree`/`crossMarginInterest`/`crossMarginLocked` 四者分列）
- `backend/tests/test_positions_merge.py:240-310`（现有 drift 正/反/双账户/账户不可读用例，即 forward 回归基线）
- `backend/tests/test_hedge_api.py:33-89`（`_POSITION_KEYS` 冻结键集，含既有 `drift` 布尔字段）
- `frontend/index.html:5270-5286`、`:6350-6390`（前端仅从 positions API 读行，仅在 `p.drift` 为真时显示标记）
- `docs/api/public-market-contract.md:733-763`、`:1932-2003`（unified-balance 字段章节与 drift 弱告警语义章节均在，可登记新增项）
- `reports/api-samples/2026-07-private-account-v1/20260705T232800Z/papi-v1-balance.json`（实盘抓取的原始响应同时携带 borrowed/free/interest/locked 四个独立字段）

### 逐项验收核查结论

1. **三原始字段全链路追踪（pass）**：raw `crossMarginBorrowed`/`crossMarginFree`/`crossMarginLocked` 已由 `fetch_unified_balances` 原样透传（`private_client.py:584-606`），worker 缓存直达 `assemble_private_account`（`snapshot_service.py:934-944`）；计划新增的 `crossMarginLocked -> cross_margin_locked` 投影落在 `snapshot.py:1268-1297` 现有循环内；merge 层 `unified_row_by_asset` 保留整行（`domain.py:2099-2102`），投影后 free/locked/borrowed 在 merge 内可得；server（`server.py:1341-1343`）与前端（`index.html:6379`）零改动。无断点、无夸大声称。
2. **`A=max(B-F-L,0)` 的证据支持（pass）**：仓库证据两层——(a) 实盘抓取样本 `papi-v1-balance.json` 证明同一响应同时提供 borrowed/free/interest/locked 四个独立字段，利息与本金分列；(b) `PROJECT_STATE.md` 记录的 XLM 实盘事故数值（`cross_margin_borrowed=195.10900819`、`cross_margin_free=95`、净空 ≈100.109）与 `B-F-L` 恒等式实盘吻合。开仓数量只比借款本金、利息不入公式，有 `test_private_account_v1.py:1136-1145` 字段分列佐证。计划并自带停止条件：实现中若发现字段缺失或语义不成立即停，不得用 `totalWalletBalance`/普通现货/猜测字段替代。证据充分，无需 REWORK。
3. **1% Decimal 容差（pass）**：复用现有 `_EXPOSURE_IMBALANCE_TOLERANCE = Decimal("0.01")`（`domain.py:1886`），不新增常量；边界明确（恰好 1% 不报警、严格超过才报警）并声明假阴性代价（至多 1% 短缺可被吸收，非业务许可）；全链路 `_merge_num` 走 Decimal，规则 6 显式要求缺失/空/不可解析/非有限/为负一律 fail-closed 到 `drift=false`，不以零替代、不部分求和（注意 `Decimal("NaN")/("Infinity")` 可解析，实现必须按计划规则 6 做有限性与负值检查——计划已覆盖，矩阵亦有对应用例）。
4. **账户资产级聚合（pass）**：`R_a` 聚合所有 `direction=reverse`、未关闭、有本地记录的 merged 行（三级资产解析顺序与 `domain.py:1948-1952` 现状一致），一个资产组一个 verdict 回填组内每行；`no_task` 行无本地数量不参与且 `drift=false`；已平仓周期（`cycle_closed_at` 非空）不消费；账户借款不按周期臆造分配或重复计数。与 merge 现状（按周期桶建行、排序前可整体后处理）兼容，可在 `merge_positions()` 内排序前实现，无需新 service/模块/状态。
5. **forward 保留（pass）**：计划规则 7 要求 forward 分支逐字等价——账户可读性处理（`account_readable` 为假即 `drift=false`，`domain.py:2014-2016`）与严格 `held < recorded_spot` 比较（`:2018-2022`）原样保留，reverse 公式、1% 带与 locked 字段不扩散到 forward；现有 `test_positions_merge.py:251-297` 四条用例即回归基线。
6. **改动边界（pass）**：生产改动限 `backend/domain/snapshot.py` 与 `backend/hedge_open_tasks/domain.py` 两个代码文件 + schema additive 声明（`cross_margin_locked` optional，与既有 `cross_margin_free` 同模式，不改 schema version，不破冻结旧样本）；三个具名测试文件与活文档各一节；明确不改 `private_client.py`/`snapshot_service.py`/`server.py`/`frontend/index.html`，不新增端点/依赖/兼容层/DB 字段/状态/恢复流程。与现状逐一核对相符。
7. **可执行测试矩阵（pass）**：覆盖借入并卖完（主回归）、借入未卖、挂单锁定、部分成交、容差边界（含 98.999 严格超过）、利息增长、同资产多行（先 A=100 后 A=70 验证只比账户级 ΣR）、forward 三例回归、缺失/坏字段（含 NaN/Infinity/负数/账户未验证）、API wire 行为（`_POSITION_KEYS` 不增字段 + 前端静态确认）。验证命令为三测试文件全量 pytest，不启动服务、不调 live API。
8. **场景准入（pass）**：本评审未引入任何新假设场景阻塞项；所有核查均基于现有原始证据与可追溯代码路径。

### 结论

`10-plan.md` 是当前代码与账户字段证据支持的最小可实现计划：方向语义错配根因成立、reverse 实际现货敞口公式三态区分与利息排除有仓库证据、聚合/容差/fail-closed/forward 保留规则与现有 domain 表示一致、文件边界最小、测试矩阵可执行。**评审结论：ACCEPT。**

### 未完成事项

无。本评审不实现、不改计划。

### 命令与结果

```text
git rev-parse HEAD -> 1892c8bfe5d5466b7d57457b95e3d7651bca2571
git log --oneline 7194876e..HEAD -> 仅两个本阶段控制提交（chore: open stage / docs: route plan review）
git diff --stat 7194876e..HEAD -- backend frontend schemas docs -> 空（产品代码与 base_sha 相同，与计划证据基线陈述一致）
test ! -e <handoff 路径> -> HANDOFF_PATH_ABSENT（创建前不存在）
```

### Required Reading for the Next Task
- 读取路径及顺序：`reports/agent-runs/2026-08-11-reverse-position-drift-v1/evidence/reverse-position-drift-plan-review.handoff.md`、`reports/agent-runs/2026-08-11-reverse-position-drift-v1/10-plan.md`
- 执行：Bookkeeper（codex）同文件核验本交接（源区块 SHA-256、status revision 2、评审闭合行），封存后准备实现任务 dispatch
- 关卡：Human 启动实现任务终端；实现前不得绕过本评审结论
- 不能假设的事实：实现改动仅限 `10-plan.md` 具名的 7 个文件；`Decimal("NaN")/("Infinity")` 可解析，实现必须按计划规则 6 显式拒绝非有限/负值；`cross_margin_locked` 投影键缺失时置 `None` 且 schema 保持 optional；实现中若发现 `/papi/v1/balance` 不再提供 borrowed/free/locked 任一字段或语义不成立，必须停止而非替代猜测；本 ACCEPT 不授权任何实盘、合并或部署动作。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

```text
[TASK_RESULT v2]
任务 ID: reverse-position-drift-plan-review
执行结果: completed（完成）
结果摘要: 跨 provider 只读计划评审完成。三字段链路无断点；A=max(B-F-L,0) 由实盘抓取样本与 XLM 实盘数值佐证，利息分列排除；容差复用现有 Decimal 常量且边界/假阴性已声明；账户资产级聚合、fail-closed、forward 逐字保留与现状一致；改动限 7 个具名文件；测试矩阵覆盖全部要求场景。结论 ACCEPT。
产物: [reports/agent-runs/2026-08-11-reverse-position-drift-v1/evidence/reverse-position-drift-plan-review.handoff.md]
检查结果: [三原始字段全链路追踪无断点: pass; B/F/L 三态公式与利息排除有仓库证据: pass; 1% Decimal 容差复用现有常量、坏值 fail-closed: pass; 多 reverse 行账户资产级聚合不重复消费: pass; forward 路径逐字保留: pass; 改动边界限 7 个具名文件: pass; 测试矩阵覆盖全部要求场景: pass; 无评审者假设场景阻塞: pass]
阻塞项: [none]
本地北京时间: 2026-08-11 17:17:43 CST
下一步模型: codex（Bookkeeper，核验并封存本交接）
下一步任务: 读取：reports/agent-runs/2026-08-11-reverse-position-drift-v1/evidence/reverse-position-drift-plan-review.handoff.md；执行：Bookkeeper 同文件核验（SHA-256、revision、评审闭合）并封存，随后准备实现任务 dispatch；关卡：Human 启动实现任务终端
评审结论: ACCEPT（接受）
问题记录: none
修复要求: none
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- source_sha256: `c2f128ce60f9dc84c65dfbe9e7494a072ee1707dfe5e3f06175ef393ed86ab4a`
- verified_at: `2026-08-11 17:24:05 CST`
- verified_status_revision: `2`
- verification_result: `pass`
- identity_check: task `reverse-position-drift-plan-review`, Reviewer/Kimi (`moonshot`), stage `2026-08-11-reverse-position-drift-v1`, and base SHA `7194876e61c037d238d0e3d621a094d7dd3a6e43` match the routed packet and status.
- closure_check: Human Brief is a closed `TASK_RESULT v2` with `completed`, eight `pass` checks, no blocker, explicit `评审结论: ACCEPT（接受）`, `问题记录: none`, and `修复要求: none`.
- scope_check: routing commit `1892c8bfe5d5466b7d57457b95e3d7651bca2571` did not contain this path; the returned worktree contained only this newly-created deterministic reviewer handoff and no product/state modification.
- commands: `sed '/^<!-- BOOKKEEPER_APPEND_ONLY:/,$d' <handoff> | shasum -a 256`; `git status --short`; `git cat-file -e 1892c8bfe5d5466b7d57457b95e3d7651bca2571:<handoff>` (expected absent); `git rev-parse HEAD`; JSON validation of revision 2 status.
- subsequent_state: plan review sealed as accepted; Bookkeeper may route the bounded implementation task without changing `rework_count`.

## Errata (append-only)

（无。）

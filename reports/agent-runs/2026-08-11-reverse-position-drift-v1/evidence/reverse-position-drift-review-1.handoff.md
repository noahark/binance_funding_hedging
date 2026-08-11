# Task Handoff: reverse-position-drift-review-1

## Source Report (author-only; immutable after task end)
- task_id: `reverse-position-drift-review-1`
- role: Reviewer（review-1，只读）
- target model: `claude_glm`（provider: `zhipu_glm`，fresh session）
- stage_id: `2026-08-11-reverse-position-drift-v1`
- created_at: 2026-08-11 17:56:41 CST
- base_sha: `7194876e61c037d238d0e3d621a094d7dd3a6e43`
- delivery_sha: `f1d929178a346026bccab8fe98d4cfa69761d8a0`

### 任务背景与结论

实现作者为 Codex/OpenAI，本评审为跨 provider（`zhipu_glm`）fresh 只读 review-1，审查固定区间 `7194876e61c037d238d0e3d621a094d7dd3a6e43..f1d929178a346026bccab8fe98d4cfa69761d8a0`。区间含 4 个提交：3 个本阶段控制提交（开阶段 / 路由计划评审 / 路由实现）与唯一交付提交 `f1d9291`（`fix: align reverse position drift with account exposure`）。控制提交仅作上下文，受审交付为 `f1d9291` 改动的 7 个具名文件。本评审未移动 HEAD，未用后续 bookkeeping 提交替换 delivery SHA。

缺陷根因成立：reverse（借币卖现货 + 开多合约）现货腿卖出后，统一账户可用余额可为零而借款本金仍为正，旧 `drift` 把「账户持有量 < 本地卖出量」误判为不一致。交付把原始 `crossMarginLocked` 投影为 additive/optional `cross_margin_locked`，reverse 按解析后账户资产聚合所有 active local reverse 行的 `spot_qty`，只消费一次账户 borrowed/free/locked，以 `A=max(B-F-L,0)` 与既有 `Decimal("0.01")` 容差回填组内统一 verdict；利息、普通现货、`totalWalletBalance` 不入公式；坏值/账户不可读/缺资产行/closed/no_task 均 fail-closed 为 `drift=false`；forward 严格 held 比较与 positions API wire 字段集逐字保留。

**评审结论：ACCEPT。** 所有阻断性 in-range 检查通过，无需 REWORK。仅一条非阻断 in-range 观察（见下，非缺陷），无 pre-existing 发现。

### 只读评审范围（实际读取）

- 权威与上游证据：`AGENTS.md`、`reports/agent-runs/ACTIVE.json`、`PROJECT_STATE.md`、`reports/agent-runs/2026-08-11-reverse-position-drift-v1/status.json`、`agents/roles.md`（Reviewer 节 + Task Handoff Evidence Contract）、`agents/skills/code-reviewer.md`、`reverse-position-drift-implement.handoff.md`、`reverse-position-drift-plan-review.handoff.md`、`10-plan.md`、`reverse-position-drift-implement.dispatch.md`。
- 受审交付源（delivery SHA `f1d9291`）：`backend/domain/snapshot.py`、`backend/hedge_open_tasks/domain.py`（`_merge_num`、`_merge_build_row` drift 段、`merge_positions` 反向聚合段、`_merge_base_asset`、`_EXPOSURE_IMBALANCE_TOLERANCE`）、`schemas/api/public-market/snapshot.schema.json`、`backend/tests/test_private_account_v1.py`、`backend/tests/test_positions_merge.py`、`backend/tests/test_hedge_api.py`、`docs/api/public-market-contract.md`。
- 原始 `git diff 7194876..f1d9291`（全 7 文件 + 控制件）与 `git show --stat f1d9291`。

### 逐项验收核查结论

1. **status.json 一致性（pass）**：`base_sha=7194876e...`、`delivery_sha=f1d92917...`、`revision=4`、`current_task.id=reverse-position-drift-review-1`、`state=dispatched`、`phase=review-1`，与 dispatch 及 Task Handoff Contract 一致；`delivery_sha` 已是固定 git rev-parse 值（非 pending/后续 bookkeeping 替换）。
2. **diff 范围与无隐藏产品行为（pass）**：`git show --stat f1d9291` 显示交付提交只改 7 个批准文件 + `reverse-position-drift-implement.handoff.md` + `status.json`（仅 `current_task.state: dispatched -> reported`，已由实现 handoff Bookkeeper 核验记录）。区间内其余 3 个提交为本阶段控制提交（dispatch/plan/status/ACTIVE.json），按 dispatch 口径作上下文非受审交付。无控制提交夹带产品代码。
3. **locked 投影 additive/optional 且不破坏旧样本（pass）**：`snapshot.py` 在 unified 行投影新增 `"cross_margin_locked": x.get("crossMarginLocked")`，上游键缺失即 `None`；不改估值/排序/总值/warning/刷新/transport。schema `balances_unified.items` 保持 `additionalProperties:false`，`cross_margin_locked` 声明为 `anyOf:[{decimal_string},{null}]`，与既有 `cross_margin_free`/`cross_margin_borrowed` 同模式；`required=['asset','total_balance','cross_margin_borrowed']` 不含新键，故 optional；schema version 未改。`test_assemble_private_account_maps_cross_margin_locked_and_schema` 断言原样投影、缺失为 None、interest 不被投影、optional（删除后仍校验）、类型强制（非 decimal 串被拒）。
4. **reverse 资产级聚合（pass）**：`merge_positions` 内反向聚合的 base-asset 解析 `spot_base_asset > asset_map[coin] > _merge_base_asset(coin)` 与现有 forward 路径（`domain.py:1949-1953`）逐字一致；仅聚合 `direction==reverse`、`match_status != "no_task"`、`cycle_closed_at is None` 的行；账户 borrowed/free/locked 每资产组只读一次（`unified_row_by_asset.get(base_asset)`），一个 verdict 回填组内每行。
5. **Decimal / sign / 有限性 / `A=max(B-F-L,0)`（pass）**：`_merge_num` 新增 `parsed.is_finite()` 守卫，使 NaN/Infinity 回 `None`；组内任一 `spot_qty` 为 None/负 → `group["valid"]=False`，B/F/L 任一为 None/负或缺资产行/账户未验证 → 跳过 verdict，行保持初始 `drift=False`，全程无异常、无部分求和、不以零替代。`actual=max(borrowed-free-locked, Decimal(0))` 纯 Decimal，无 float，不反转符号，不取绝对值，不替代 `totalWalletBalance`/普通现货/利息。
6. **利息排除 + 1% 容差边界（pass）**：利息不入公式（`crossMarginInterest` 不被投影为数量键，`borrow_interest` 不参与聚合）；复用 `_EXPOSURE_IMBALANCE_TOLERANCE=Decimal("0.01")`，不新增常量；`drift = (recorded-actual) > recorded*0.01`——`R=100,A=99`（恰好 1%）为 false，`R=100,A=98.999`（严格超过）为 true，全程 Decimal；docs 与代码的假阴性描述一致（至多 1% 短缺可被吸收，非业务许可）。
7. **forward 行为逐字保留 + positions wire 不变（pass）**：`_merge_build_row` 的 reverse 分支先置 `drift=False`，forward 落到原 `elif`/`else`（账户可读性、严格 `held < recorded_spot`、`held = real_spot + unified_balance`）逐字不变；反向聚合只过滤 `direction==reverse` 行，不触碰 forward 行。`test_merge_forward_drift_ignores_reverse_account_fields` 在 unified 放 borrowed=999/free=888/locked=777 证明 reverse 字段不泄漏进 forward。`test_positions_reverse_drift_keeps_existing_wire_keys` 断言 `set(position) == _POSITION_KEYS` 且 reverse `drift` 正确穿透 API——`cross_margin_locked/free/borrowed` 只在 merge 内消费，不是 positions 行字段，前端零改动。
8. **测试矩阵与命令（pass）**：三文件矩阵覆盖 JST 借入并卖完 / 借入未卖 / 挂单锁定 / 部分成交 / 1% 边界（含 98.999）/ 利息增长 / 同资产多行（先 A=100 后 A=70）/ forward 回归三例 / 坏 B/F/L（3×6：None/空/文本/NaN/Infinity/负）/ 坏本地 spot_qty / closed+no_task / 账户不可读 / locked 投影+schema / API wire。独立重跑 `python3 -m pytest backend/tests/test_private_account_v1.py backend/tests/test_positions_merge.py backend/tests/test_hedge_api.py` → `224 passed in 24.45s`；`git diff --check 7194876..f1d9291` exit 0。未启动服务、未调本地/实盘 API。
9. **docs 为活权威且准确（pass）**：`docs/api/public-market-contract.md` 是 API 公共契约活文档；新增 `cross_margin_locked` 登记（unified-balance 节，raw decimal string|null，PM full-cross locked，与 free/borrowed/interest 分列，optional 兼容旧样本，display/validation-only，不入总值）；drift 章节改为方向分支——forward 严格比较不变、reverse `R=Σspot_qty` 与 `A=max(B-F-L,0)`、利息排除、`R-A>R×0.01` Decimal 边界、缺/空/不可解析/非有限/负与无资产行/不可读 fail-closed、不替代 totalWalletBalance/普通现货/利息、`drift=false` 非对账证明。与代码逐项吻合。
10. **场景准入（pass）**：本评审未引入任何阻塞交付的新假设场景；下方唯一观察项不援引新假设，是已提交代码与测试可直接复核的事实，且分类为非阻断、非缺陷。

### 观察项（非阻断，in-range，非缺陷）

- **O-1（`_merge_num` 共享 helper 的非有限拒绝也收紧了 forward 路径）**：`_merge_num` 是 `_merge_build_row`/`single_leg_exposure`/forward held 等多处共用的解析函数；新增的 `is_finite()` 守卫使 NaN/Infinity 对所有调用方都回 `None`。已逐一追踪：对所有现实输入（`spot_qty` 为本地 Decimal 任务量、`unified_balance`/B/F/L 为交易所有限小数串）forward 与 `single_leg_exposure` 行为逐字节不变；唯一 verdict 变化只发生在非有限输入上（例：forward `spot_qty=+Infinity` 旧 `held<Inf`→drift=True，现 `recorded_spot is None`→drift=False），且新行为恰是 dispatch/计划规则 6 要求的 fail-closed 语义，落在正确的单一解析 seam。`test_merge_forward_drift_ignores_reverse_account_fields` 与既有 forward 用例（224 项全绿）覆盖全部现实有限输入。分类：in-range，非阻断，非缺陷（即所要求的 fail-closed 行为），无需 REWORK。

### 未完成事项

无。本评审不实现、不改交付/控制文件/status/prior evidence/plan/dispatch/docs/source，不提交，不启动/中继下一模型，不合并/push/部署，不控制服务或调任何本地/实盘 API。

### 命令与结果

```text
git rev-parse HEAD                                  -> 2737f6c91cbb34f57bebeefdfdd6cdf56f9d3dbb（review-1 路由提交，上下文非交付）
git rev-parse 7194876e61c037d238d0e3d621a094d7dd3a6e43 -> 7194876e61c037d238d0e3d621a094d7dd3a6e43（base 解析成功）
git rev-parse f1d929178a346026bccab8fe98d4cfa69761d8a0 -> f1d929178a346026bccab8fe98d4cfa69761d8a0（delivery 解析成功）
test ! -e <review-1 handoff 路径>                   -> HANDOFF_PATH_ABSENT（创建前不存在）
git log --oneline 7194876..f1d9291                  -> 4 提交：c58e718 开阶段 / 1892c8b 路由计划评审 / 4aab866 路由实现 / f1d9291 实现（唯一交付）
git show --stat f1d9291                             -> 恰 7 批准文件 + implement.handoff.md + status.json（仅状态迁移）
git diff --check 7194876..f1d9291                   -> exit 0
python3 -m pytest backend/tests/test_private_account_v1.py backend/tests/test_positions_merge.py backend/tests/test_hedge_api.py -> 224 passed in 24.45s
schema 检查                                         -> balances_unified.items: additionalProperties=false, required=['asset','total_balance','cross_margin_borrowed'], cross_margin_locked optional 且与 free/borrowed 同 anyOf 模式
```

### Required Reading for the Next Task
- 读取路径及顺序：`reports/agent-runs/2026-08-11-reverse-position-drift-v1/evidence/reverse-position-drift-review-1.handoff.md`、`reports/agent-runs/2026-08-11-reverse-position-drift-v1/status.json`
- 执行：Bookkeeper（codex）同文件核验本评审交接（源区块 SHA-256、verified_status_revision 4、ACCEPT 闭合行、create-only 路径与 task_id/role/stage/base_sha 一致性），封存后准备独立 review-2 dispatch packet（HIGH_RISK 需 review-1+review-2；review-2 默认 `sonnet5`/anthropic，须与全部实现/修复 author 跨 provider）
- 关卡：Bookkeeper 核验通过后由 Human 启动独立 review-2；本 review-1 ACCEPT 不授权任何合并、部署、实盘或账户动作
- 不能假设的事实：`drift=false` 不是对账证明；forward 对现实有限输入逐字不变、`_merge_num` 非有限拒绝是所要求的 fail-closed 而非 forward 回归；reverse 仅在合并层消费 B/F/L，不新增 positions 行字段；review-2 须独立审查需求/实际效果/证据/运营风险/发布就绪

## Human Brief / Console Receipt Source (author-only; immutable after task end)

```text
[TASK_RESULT v2]
任务 ID: reverse-position-drift-review-1
执行结果: completed（完成）
结果摘要: 跨 provider fresh review-1 ACCEPT。交付 f1d9291 仅 7 批准文件：locked additive/optional 投影；reverse 按解析资产聚合本地 spot_qty，A=max(B-F-L,0) 配复用 1% Decimal 容差判 drift，坏值/利息/不可读 fail-closed；forward 逐字保留、positions wire 键集不变。224 测试与 diff --check 通过。
产物: [reports/agent-runs/2026-08-11-reverse-position-drift-v1/evidence/reverse-position-drift-review-1.handoff.md]
检查结果: [status.json SHA/revision/task 一致且 delivery 固定: pass; 交付范围仅 7 文件+控制件、无隐藏产品行为: pass; locked additive/optional、旧样本兼容、总值/估值/刷新不变: pass; reverse 资产级聚合与 base-asset 三级链同 forward: pass; B/F/L/本地量 Decimal 非有限/负 fail-closed、A=max(B-F-L,0) 无 float 无替代: pass; 利息排除与 1% 严格边界(A=99 false/A=98.999 true): pass; forward 逐字保留、reverse 字段不泄漏、positions wire 键集不变: pass; 三文件矩阵全覆盖、224 passed、git diff --check exit 0、docs 活权威准确: pass]
阻塞项: [none]
本地北京时间: 2026-08-11 17:56:41 CST
下一步模型: codex（Bookkeeper，核验并封存本 review-1 交接）
下一步任务: 读取：reports/agent-runs/2026-08-11-reverse-position-drift-v1/evidence/reverse-position-drift-review-1.handoff.md、reports/agent-runs/2026-08-11-reverse-position-drift-v1/status.json；执行：Bookkeeper（codex）同文件核验本 review-1 交接（源区块 SHA-256、revision 4、ACCEPT 闭合行）并封存，随后准备独立 review-2（默认 sonnet5/anthropic）dispatch packet；关卡：Bookkeeper 核验通过后由 Human 启动独立 review-2
评审结论: ACCEPT（接受）
问题记录: none
修复要求: none
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- source_sha256: `f2520d7f05fff4484f0375228780224fe9ccd79f74616643b567ee8e6d12d704`
- verified_at: `2026-08-11 18:00:11 CST`
- verified_status_revision: `4`
- verification_result: `pass`
- identity_check: task `reverse-position-drift-review-1`, Reviewer/`claude_glm` (`zhipu_glm`), stage `2026-08-11-reverse-position-drift-v1`, base SHA `7194876e61c037d238d0e3d621a094d7dd3a6e43`, and delivery SHA `f1d929178a346026bccab8fe98d4cfa69761d8a0` match the routed packet and status.
- closure_check: Human Brief is a closed `TASK_RESULT v2` with `completed`, eight `pass` checks, no blocker, explicit `评审结论: ACCEPT（接受）`, `问题记录: none`, and `修复要求: none`.
- scope_check: routing commit `2737f6c91cbb34f57bebeefdfdd6cdf56f9d3dbb` did not contain this path; the returned worktree contained only this newly-created deterministic reviewer handoff and no delivery/state modification.
- finding_check: O-1 is explicitly in-range, non-blocking, and non-defect; it records the required non-finite fail-closed behavior and carries no repair request. No pre-existing finding or release blocker was reported.
- evidence_check: reviewer independently reported `224 passed in 24.45s` and fixed-range diff check exit 0; commands, Required Reading, and the next gate are concrete and consistent.
- subsequent_state: review-1 sealed as accepted; Human reported frontend acceptance passed; Bookkeeper may route independent review-2 without changing `rework_count`.

## Errata (append-only)

（无。）

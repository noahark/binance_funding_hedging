<!-- ============ RECEIPT（审计元数据，bookkeeper 回填；非任务内容） ============
status: pending            # pending | running | done | blocked | escalated
target_model: claude_glm (glm-5.2) 实现会话（独立于 bookkeeper/Fable5 会话）
adapter_cmd: 用户向 fresh claude-glm 实现终端发「读本文件并执行 PROMPT BODY」一行指令
started_at:
completed_at:
session_id: fresh claude-glm backend+frontend implementer（待用户中转启动）
base_sha: 5bdfc4b3dc6843a8e52aeb86896c735500ed137a（stage 分支建点；本任务 diff 自此测量，bookkeeper 做 R4 对账后串行落盘）
outputs:                   # H.impl-note.md / H.diff.patch / 测试原始输出
next_dispatch: §6 收尾段（executor: self——完成实现后必须机械执行，不得以「等待」结束）
======================================================================== -->

--- PROMPT BODY（不可变任务正文，自此行以下原样执行；设计期定稿后不得修改） ---

你是 stage `2026-07-borrow-cost-coverage-v2` 的**唯一实现者**（owner=claude_glm，后端+前端+文档+测试单一原子交付物 H）。

## 0. 权威规格与阅读顺序（先全读，再动手）

1. 本任务书（PROMPT BODY 全文）——逐文件改动清单 = 权威边界。
2. `reports/agent-runs/2026-07-borrow-cost-coverage-v2/10-design.md`（= DRAFT-4，含 §3 设计、§4 下游收口、§6 测试、§8 验收）。
3. `reports/agent-runs/2026-07-borrow-cost-coverage-v2/00-stage-plan.md` §3（逐文件防漂移拆分）、§4（测试逐条）、§5（验收）、§6（serial 收尾）。
4. Gate 证据（只读参考，不重跑）：`gate-a-live.md`、`gate-b-endpoint-recon.md §9`。

**冲突时**：本任务书 > 10-design > stage-plan。当前分支应为 `stage/2026-07-borrow-cost-coverage-v2`（**只核对，不切换**）。

## 1. 背景（一句话）

next-hourly 单次 assets 硬上限=20，服务发 50 必 HTTP500 code=2，被 `private_client.py` 静默吞成 tier② rate_history（只 1 资产）→ 大量 `-`；叠加 `borrow_check_max_calls=50` 把利率覆盖和 maxBorrowable 预算错误绑定。本任务：①分批修 next-hourly，②解耦两预算，③改契约不清空利率，④下游收口。

## 2. 防漂移总则（违反即预审 blocker）

- **只做本任务书 §3 列出的改动**；不重构相邻代码、不改无关格式/注释/命名、不加未要求的抽象/配置/错误处理/日志。
- 每一行改动必须能追溯到 §3 的某条。
- Decimal 全程，**禁 float**；key/secret 零片段；进 git 的 fixture 用脱敏值。
- **不 commit、不碰 status.json**；改动只留工作树，交 bookkeeper 串行落盘。
- 遇到 §3 未覆盖、却必须改的情况，或触及契约/schema/耦合面之外的新面 → **停手，写 escalation 交 bookkeeper（R3），禁止自行扩面或"顺手"改**。

## 3. 逐文件改动（= 交付物 H，同批交付，顺序：3.A 先行）

### 3.A `backend/services/private_client.py` — next-hourly 分批（主修）

改 `fetch_cost_leg_chain(borrow_assets)` 的 tier① 段（当前约 L304-320）：

1. 常量：文件顶部（其它模块常量旁）加 `NEXT_HOURLY_BATCH_SIZE = 15  # Gate B: 单次 assets 硬上限 20，留余量；证据 gate-b-endpoint-recon.md §9`。（**不引入新配置项**，除非你判断必须——若必须则见 §3.E，二选一，不并存。）
2. 逐批调用：把 `borrow_assets` 按 `NEXT_HOURLY_BATCH_SIZE` 切片；对每片调 `self._cached_get("GET", "/sapi/v1/margin/next-hourly-interest-rate", {"assets": ",".join(batch), "isIsolated": "false"})`。
3. 合并：成功片的结果 `.update()` 进 `merged_next_hourly: Dict[str, Optional[str]]`（key=asset，value=nextHourlyInterestRate）。
4. **部分失败语义**：某片抛 `PrivateEndpointError` → **只跳过该片**（`continue`），保留已合并内容；**不 abort、不清空 merged、不整体降级**。失败片的资产因不在 merged 而自然 rate=None（下游 resolve 返回 None）。
5. **修静默吞异常**：捕获片失败时，记录可观测诊断——追加到 `self.last_error`（形如 `next_hourly_batch_failed:{exc.reason}:{len(batch)}`）。不得静默 `pass`。
6. 合并后把 `merged_next_hourly` 传入 `_select_chain_tier(merged_next_hourly, rate_history, cross_table, vip_level)`（**合并在 tier 选择之前**）。

**缓存纪律（关键，别搞错）**：

- **保持逐片 `_cached_get`**——cache key 已含 assets 参数，成功片各自缓存 1h、失败片不写缓存，下一张快照（≤60s）自动只重试失败片。
- **禁止**把 `merged_next_hourly` 整表另存为一个缓存项。整表缓存会把「部分片失败」的残缺结果缓存 1h，破坏 60s 自愈。
- 同一快照周期不会重复调用（`get_snapshot` 已有 60s 快照缓存），**不要**加去重逻辑。

**不改**：`_select_chain_tier` 逻辑、tier②(rate_history)/③/④ 段、`fetch_max_borrowable`、`_signed_get`、`_cached_get` 签名与缓存结构、白名单。

### 3.B `backend/domain/snapshot.py` — `select_borrow_candidates` 拆集合 + coverage 重定义

当前返回 `{"probed_assets","truncated_assets","coverage"}`。改为返回：

```python
{
  "rate_probe_assets": [...],             # 全量候选（不受 cap），abs rate DESC，去重
  "borrowability_probe_assets": [...],    # 同池前 max_calls 个
  "borrowability_unprobed_assets": set(), # rate_probe - borrowability_probe
  "coverage": {
    "probed": len(borrowability_probe_assets),
    "skipped": len(borrowability_unprobed_assets),
    "reason": "rate_limit_budget" if len(borrowability_unprobed_assets) else None,
  },
}
```

- 候选口径（`daily_funding_rate<0 ∧ route_class=="MARGIN_SPOT_CANDIDATE" ∧ asset_tag=="CRYPTO"`）、去重、排序（abs DESC，symbol ASC tie-break）**完全不变**——只是把「取前 cap 个」的结果一分为二，并额外产出全量 rate 集。
- `rate_probe_assets` 默认不设上限（若你在 §3.E 引入 `borrow_rate_max_assets` 则受其限，默认 0=不限）。

**`resolve_cost_leg_rate` 不改**——它对不存在的 key 已返回 None（当前 L395-397），正是失败片/子集缺失资产的正确落点。

### 3.C `backend/domain/snapshot.py` — `assemble_borrow_validation` 契约变更

签名：把关键字参数 `truncated: bool = False` **改名为** `borrowability_truncated: bool = False`（新名，不复用旧名）。

替换当前 `if truncated:` 早返回分支（约 L713-730），三态如下：

| 情形 | verified | classic_margin 字段 | daily_interest_account | portfolio_account | error | checked_at |
|---|---|---|---|---|---|---|
| `classic_ref is None` | False | 全 null（不变） | null | 全 null | 原 error | None |
| `borrowability_truncated=True` | **False** | 按 classic_ref 正常填（pair_listed/asset_borrowable/daily_interest_vip0，同「正常」路径） | **保留传入的 daily_interest_account** | `max_borrowable=None, borrow_limit=None`（source 保留） | **`"borrowability_not_probed"`** | **保留 checked_at** |
| 正常（都不成立） | True | 正常填 | 传入值 | portfolio 值 | None | checked_at |

**铁律**：`borrowability_truncated=True` 分支**不得**把 `daily_interest_account` 置 None，只清 `portfolio_account` 的额度字段。

### 3.D `backend/services/snapshot_service.py` — 装配接线

改当前 L135-212 区间：

1. `probe = select_borrow_candidates(rows, self.config.borrow_check_max_calls)`；取三集合到局部变量。
2. `cost_leg = self._private.fetch_cost_leg_chain(probe["rate_probe_assets"])`。
3. maxBorrowable 循环只遍历 `probe["borrowability_probe_assets"]`（当前遍历 probed_assets 处改成它）。
4. 行装配：
   ```python
   if base in rate_probe_assets and cost_leg:
       rate = resolve_cost_leg_rate(base, cost_leg)
       if rate is not None:
           daily_borrow_rate = rate
           borrow_rate_source = cost_leg.get("chain_hit_source")
   ...
   row["borrow_validation"] = assemble_borrow_validation(
       row, classic_ref, portfolio_by_asset, checked_at, private_error,
       daily_interest_account=daily_borrow_rate,
       borrowability_truncated=(base in borrowability_unprobed_assets),
   )
   ```
   删掉旧的 `base not in truncated_assets` 利率门（利率解析只依赖 `rate_probe_assets`）。
5. `borrow_validation_summary` 的 coverage 用新 coverage；`coverage.skipped>0` 触发的 top-level warning 文案改为「部分资产可借额度未探测（利率仍覆盖）」。

**不改**：sort_basis 判定与 `sort_rows`（新获利率的行进入 net 排序属期望行为）；60s 快照缓存；private_account 装配。

### 3.E `backend/config.py` — 可选配置（仅当 §3.A 判断必须才引入；否则整段跳过）

若引入：`next_hourly_asset_batch_size: int = 15`（env `BINANCE_NEXT_HOURLY_ASSET_BATCH_SIZE`）、`borrow_rate_max_assets: int = 0`（env `BINANCE_BORROW_RATE_MAX_ASSETS`，0=不限）。与 §3.A/§3.B 的常量**二选一，不并存**。

### 3.F `frontend/index.html` — 徽章第六态

在 `not_probed_this_round` 分支（当前 L906）**之前**插入：

```javascript
if (bv && bv.verified === false && bv.error === 'borrowability_not_probed') {
  return `<span class="badge muted" title="PRIVATE_BORROW_VALIDATION_REQUIRED">有利率·可借性未探测</span>`;
}
```

**不改**：利率子行（L1093-1104，已能渲染利率）、其它徽章分支、任何布局/样式。

### 3.G `docs/api/public-market-contract.md` — 契约语义（§coverage/warnings，约 L447-454）

- 新增 `error` 枚举 `borrowability_not_probed` 的说明：可借额度未探测，但 `daily_interest_account`/`net_daily_yield` **仍填充**。
- `coverage` 语义改述为 borrowability 覆盖；warning 文案同 §3.D。
- 保留 `not_probed_this_round` 说明（legacy 态）。

### 3.H `schemas/api/public-market/snapshot.schema.json` — additive（仅当 error 是受约束枚举）

若 schema 对 `error` 值有 enum 约束，additive 加入 `borrowability_not_probed`；否则不动。不改字段形状。

## 4. 测试（逐条实现；测试名与断言照抄）

置于 `backend/tests/`（与既有同风格），前端置 `frontend/self-check.js`：

1. **新增** `test_borrowability_truncated_keeps_rate`：`borrow_check_max_calls=2`，4 个负费率候选，next-hourly fixture 覆盖全 4，maxBorrowable 只探前 2。断言第 3/4 资产：`borrow_rate_source=="next_hourly"` ∧ `classic_margin.daily_interest_account` 非空 ∧ `net_daily_yield` 非空 ∧ `portfolio_account.max_borrowable is None` ∧ `error=="borrowability_not_probed"`。
2. **新增** `test_next_hourly_subset_miss_no_fabrication`：next-hourly fixture 只返回 3/4。断言缺失资产 `borrow_rate_source is None` ∧ `daily_interest_account is None`（不伪造、不落 rate_history）。
3. **新增** `test_batch_merge_covers_all`：>20 资产分批，断言合并后全部命中、`chain_hit_source=="next_hourly"`。
4. **新增** `test_partial_batch_failure_partial_merge`：mock 某片抛 `PrivateEndpointError`，断言成功片资产有利率、失败片资产 rate=None、**不整体降级 tier②**、`last_error` 含 `next_hourly_batch_failed`。
5. **修改**（非保留）`test_private_account_v1.py:227 test_borrow_validation_truncated_state`：改用 `borrowability_truncated=True`，断言 `daily_interest_account` **保留** ∧ `error=="borrowability_not_probed"` ∧ `portfolio_account.max_borrowable is None`。
6. **修改** `test_private_account_v1.py` L855-859 / L869-892 coverage & warning 断言：按 §3.D 新文案 + 新 coverage 语义更新。
7. **前端** `frontend/self-check.js` 第 34 项「五文案」扩为「六文案」：新增 `borrowability_not_probed` → 断言徽章「有利率·可借性未探测」(`badge muted`) **且**利率子行显示「日借币: X.XX%」；**同时保留** `not_probed_this_round` 旧用例断言（回归，不被新态遮盖）。fixture 补一行携带利率但可借性未探测。

**既有测试零意外回归**（除 §4.5/§4.6 明确要改的两处）。

## 5. 验收自查（收尾前逐条自检，写进 impl-note）

对照 10-design §8 / stage-plan §5 十条，尤其：tier① 分批后 `chain_hit_source=next_hourly`；截断行保留利率；两态（borrowability_not_probed vs borrow_rate_source=null）可区分；bStock 仍禁用；60s 自愈成立（无整表缓存）。

## 6. R10 收尾段（实现+自测完成后必须机械执行，路径已写死，一直跑到 review-1 有 verdict 为止）

1. 自测：
   `python3 -m pytest backend/tests -q 2>&1 | tail -30`
   `node frontend/self-check.js 2>&1 | tail -20`
   未全绿 → 修（仍在 §3 scope 内）后重跑；超 scope → 步骤 7 escalation。
2. 生成 reviewer diff：
   `git diff -- backend frontend docs schemas > "reports/agent-runs/2026-07-borrow-cost-coverage-v2/H.diff.patch"`
3. 写实现说明 `reports/agent-runs/2026-07-borrow-cost-coverage-v2/H.impl-note.md`：改动文件清单 + 每条对应 §3 哪一项 + 测试原始输出摘要 + §5 自查表 + 下列统计：
   `rate_probe_assets_count / borrowability_probe_assets_count / borrowability_unprobed_assets_count / next_hourly_returned_assets_count / batches_attempted / batches_failed / rows_with_rate_count / rows_with_rate_but_borrowability_unprobed_count / chain_hit_source`
4. **机械触发 review-1（kimi 嵌入预审，只读）并落 raw output**（这一步不可跳过、不得改成口头请求用户）：
   ```
   kimi --model kimi-code/kimi-for-coding -p "$(cat 'reports/agent-runs/2026-07-borrow-cost-coverage-v2/review-1-H-by-kimi.prompt.md')" | tee "reports/agent-runs/2026-07-borrow-cost-coverage-v2/embedded-review-H-round1.raw-output.md"
   ```
5. 读 raw output 里的 review-verdict JSON 的 `verdict` 字段，按分支处理：
   - **ACCEPT** → 在结束输出报告「impl PASS + review-1(kimi) ACCEPT」，并**停下**，等 bookkeeper 做 R4 diff 对账 + 串行落盘 + promote review-1 + 派 review-2(codex)。**不 commit、不写 status.json、不自己派 review-2**。
   - **REWORK 且 `required_fixes` 全部落在 §3 file 边界内** → 按 verdict 的 `fix_start_prompt` 修，记为 round 2（`max_rounds=2` 封顶），回步骤 1 重跑（重跑含重新触发步骤 4，落 `embedded-review-H-round2.*`）。
   - **REWORK 触及 §3 边界外 / 新契约面，或 round 2 仍 REWORK，或 verdict=BLOCKED** → 停，写 `H-escalation.md`（类别 scope/contract/ambiguity + kimi findings 摘要 + 卡点），交 bookkeeper（R3）。
6. **kimi 不可用 / 命令失败 / 输出非合法 JSON** → 写 `embedded-review-H-round1.dispatch.md` 记 unavailable/command_error/invalid_output + 原始报错，置 `escalated`，停；**禁止空等用户**。
7. **触及 §3 file 边界之外、或 §2 未覆盖的必须改情形** → 立即停手，写 `H-escalation.md` 交 bookkeeper（R3），禁自行扩面。
8. **禁止**：只口头报告「等待下一步」而不落 H.impl-note / H.diff.patch / embedded-review raw-output 或 dispatch。

--- END PROMPT BODY ---

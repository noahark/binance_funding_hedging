# Borrow Cost Coverage v2 Fix Plan DRAFT-4（实现就绪）

模型：Claude (Opus 4.8)
状态：DRAFT-4，收敛 DRAFT-1..3 + 三轮 review，**实现就绪**，取代 DRAFT-3
范围：后端数据源覆盖率修复 + 由此牵动的前端徽章 / 测试 / summary 一并收口；不改交易类代码，不提交 git

历史链路：

- DRAFT-1 / review-1（REWORK）：根因诊断错误（fallback 只查第一个资产）
- DRAFT-2 / review-2（REWORK）：漏 `assemble_borrow_validation` 二次清空利率
- DRAFT-3 / review-3（ACCEPT 有条件）：后端修法正确，漏前端徽章 / 现有测试 / coverage 三个下游消费者

本版原则：**一次性把 `borrow_validation` 契约变更追穿全部下游消费者**，终结逐层 ping-pong。

关键代码证据（均已核对）：

- `backend/domain/snapshot.py`：`select_borrow_candidates` L333-382、`resolve_cost_leg_rate` L385-403、`assemble_borrow_validation` L666-755、`sort_rows` L633-663
- `backend/services/snapshot_service.py`：候选集 L135-138、cost_leg L142-145、maxBorrowable 循环 L179-187、行装配 L189-212、sort_basis L214-217、summary L219-224
- `backend/services/private_client.py`：`fetch_cost_leg_chain` L268-356、`_select_chain_tier` L409-462、`fetch_max_borrowable` L233-251
- `backend/tests/test_private_account_v1.py`：`test_borrow_validation_truncated_state` L227、coverage/warning L855-892
- `frontend/index.html`：状态徽章 L893-909、利率子行 L1089-1104
- `reports/agent-runs/private-account-v1-direction/endpoint-recon-kimi-borrow-rate-v2.md`（Kimi 主报告）

---

## 1. 根因（定稿）

UI 大量负费率资产"日借币利率 = -"的成因，按代码事实定为两条，主症状候选是 A：

- **根因 A（本阶段修）——预算连累利率覆盖。** `select_borrow_candidates(rows, borrow_check_max_calls=50)`（调用点 `snapshot_service.py:135`，定义 `snapshot.py:333`）产出单一 `probed_assets`，同时喂给 next-hourly 利率输入集**和** maxBorrowable 逐资产探测。next-hourly 是 comma-joined 调用、权重与资产数无关（Gate B 实测约 **100 IP/call**；v2 报告早前观察到的 200 疑为同分钟并发叠加，不再作预算基准）（`private_client.py:312`）；maxBorrowable 是 5/asset。用同一个由 maxBorrowable 成本驱动的 cap=50 去限制近乎免费的 next-hourly 输入集，是错误耦合。第 51+ 个候选进 `truncated_assets`，即便 Binance 能返回利率也不会被请求，行装配（`snapshot_service.py:195`）与 `assemble_borrow_validation` 的 truncated 分支（`snapshot.py:713`）双重把利率置空。

- **根因 B（本阶段不修，deferred）——next-hourly 子集缺失。** 送进 next-hourly 但响应未返回的资产（如 TSLAB）为 null；`_select_chain_tier` 是快照级单 tier（`private_client.py:424`），tier① 一旦任意命中就整表返回，缺失资产不会逐资产回退到 `interestRateHistory`。修此需把 cost leg 从"快照级单 tier"重构为"per-asset tier synthesis"，另开 `per-asset-cost-leg-v1`。

> DRAFT-1 的"fallback 只查 `borrow_assets[0]` 导致大量 -"是错误根因：稳态下 next-hourly 命中，`rate_history` 根本不参与，仅在 next-hourly 全空时才影响降级表现。

### 1.1 Gate A 实盘证据揭示的更强信号（2026-07-07 21:28，须优先处理）

Gate A live check（`borrow-cost-coverage-v2-gate-a-live.md`）确认候选 66 > 50、`coverage.skipped=16`，根因 A 成立。**但同一份快照还显示：**

```text
chain_hit_tier   = 2
chain_hit_source = rate_history
```

按 `_select_chain_tier`（`private_client.py:424`），tier② 仅在 **`next_hourly` 完全为空**时命中。即**实盘服务此刻的 next-hourly（tier①）没有出数据**，链路已降级到 `rate_history`——而 `rate_history` 只查 `borrow_assets[0]`（1 个资产）。

账重算：66 候选中截断只解释 16 个 `-`；但既然当前落在 rate_history（仅 1 资产命中），50 个被探测资产里另有 **49** 个也是 `-`。**当前主症状的主因是 next-hourly 在服务内失效（~49），截断（16）是次因。**

Kimi 独立探测脚本发 9 个资产成功，但服务 `fetch_cost_leg_chain` 发的是 50 个 comma-joined，随后 `except PrivateEndpointError: next_hourly = {}`（`private_client.py:319`）**静默吞失败、降级 tier②**。最可能解释：**next-hourly 单次 `assets` 有 ≤50 的上限，服务每次发 50 个即 400、每张快照静默退化。**

由此对本方案的三点修正：

1. **Gate B 是真正的承重门**（不是 Gate A）：必须 root-cause"为何服务内 next-hourly 返回空"，而非仅测批量大小。
2. **§3.5 分批合并大概率是必需项，非可选**：解耦后要发 66 个，单次只会更易触限；不分批会更糟。
3. **仅做预算解耦（§3）不足以修好主症状**：tier① 不出数据时，解耦只是把更多资产喂给一个正在失败的调用。实现顺序须为「先修复/分批 next-hourly 使 tier① 真正命中 → 再解耦预算」。
4. 附带：`private_client.py:319` 的静默吞异常应在 Gate B 期间加诊断（记录 Binance code / 请求资产数），否则 tier① 失效永远不可见。

---

## 2. 开发前决策门（阻塞，须落档到 `60-test-output.txt` 或实现报告）

### Gate A — 根因 A 是否真的触发

用当前 live snapshot 或只读脚本记录：

```text
negative_margin_spot_crypto_candidate_count = N
borrow_check_max_calls                       = 50
would_truncate = N > 50
```

- `N > 50`：根因 A 成立，执行本方案。
- `N <= 50`：根因 A **未触发**，大面积 `-` 另有原因（根因 B / classic reference / private channel failure / UI 映射）。**本方案不得进入实现**，退回重新诊断。

### Gate B — next-hourly 单次资产上限 **（✅ RESOLVED 2026-07-07，Kimi §9）**

**结论已定，无需再测。** Kimi 补测（`endpoint-recon-kimi-borrow-rate-v2.md §9`）确认：

```text
next-hourly 单次 assets 硬上限 = 20 个唯一资产
21+  → HTTP 500 / Binance code=2 / "The size of assets should not larger than 20"
服务发 50 → 500 → private_client.py:319 静默吞 → 每张快照降级 tier② rate_history(1 资产)
H1（计数上限）成立；H2 长度 / H3 限频 / H4 非法资产 均经 T3/T4/T5 排除
```

**锁定实现参数（Kimi T6）**：

```text
next_hourly_max_assets_per_call = 20        # 硬上限
recommended_batch_size          = 15        # 留 25% 余量
batches_to_cover_66             = 5         # ceil(66/15)
total_weight_per_snapshot       ≈ 500 IP    # 5×100，远低于 sapi 12,000/min
```

以下为原 Gate B 探测记录（已由 Kimi 完成，保留供追溯）：

```text
GET /sapi/v1/margin/next-hourly-interest-rate
  assets=<all negative MARGIN_SPOT_CANDIDATE + CRYPTO base assets>, isIsolated=false
记录：request_asset_count / returned_asset_count / missing_assets /
     HTTP status / Binance code / X-SAPI-USED-IP-WEIGHT-1M / 是否有 URL 或参数数量上限
```

- 单次成功：`rate_probe_assets` 一次请求。
- 单次失败：启用分批，合并必须发生在 `_select_chain_tier()` **之前**（合并 `next_hourly` 原始 dict，而非合并已选 tier 的 `daily_by_asset`）。

---

## 3. Immediate Fix 设计

### 3.1 拆分候选集（`snapshot.py: select_borrow_candidates`）

返回三个集合 + 重定义的 coverage：

```text
rate_probe_assets:
  全量负费率 MARGIN_SPOT_CANDIDATE + CRYPTO base assets（去重、按 abs daily rate DESC 排序）
  不受 borrow_check_max_calls 限制；可选独立上限 BINANCE_BORROW_RATE_MAX_ASSETS（0/空=不限）
  用于 fetch_cost_leg_chain 的 next-hourly 输入集

borrowability_probe_assets:
  同一候选池，受 borrow_check_max_calls 限制（保持现有 top-N 语义）
  用于 fetch_max_borrowable 逐资产探测

borrowability_unprobed_assets:
  rate_probe_assets - borrowability_probe_assets
  即"有机会拿利率，但可借额度未探测"

coverage（语义重定义为 borrowability 覆盖）:
  {"probed": len(borrowability_probe_assets),
   "skipped": len(borrowability_unprobed_assets),
   "reason": "rate_limit_budget" if skipped else None}
```

不再用单个 `truncated_assets` 同时控制利率和可借性。

### 3.2 调用链（`snapshot_service.py`）

```text
cost_leg           = fetch_cost_leg_chain(rate_probe_assets)          # 全量利率
portfolio_by_asset = { a: fetch_max_borrowable(a) for a in borrowability_probe_assets }
```

### 3.3 行装配（`snapshot_service.py:189-212`）

```text
daily_borrow_rate = None
borrow_rate_source = None
if base in rate_probe_assets and cost_leg:
    rate = resolve_cost_leg_rate(base, cost_leg)      # None 若该资产不在命中 tier 表（根因 B 情形）
    if rate is not None:
        daily_borrow_rate  = rate
        borrow_rate_source = cost_leg.get("chain_hit_source")

row["net_daily_yield"]   = compute_net_daily_yield(row["daily_funding_rate"], daily_borrow_rate)
row["borrow_rate_source"] = borrow_rate_source
row["borrow_validation"] = assemble_borrow_validation(
    row, classic_ref, portfolio_by_asset, checked_at, private_error,
    daily_interest_account=daily_borrow_rate,
    borrowability_truncated=(base in borrowability_unprobed_assets),   # 替换旧 truncated
)
```

要点：利率解析**只依赖 `rate_probe_assets`**，不再看 borrowability 截断。

### 3.4 `assemble_borrow_validation`（`snapshot.py:666`）契约变更

签名：`truncated: bool` → **`borrowability_truncated: bool`**（实现 A：新参数，不复用旧名，避免语义再次混乱）。

三态行为（最小、可被前端无歧义渲染）：

| 情形 | verified | classic_margin | daily_interest_account | portfolio_account | error |
|---|---|---|---|---|---|
| `classic_ref is None` | False | 全 null | null | 全 null | 原 error（通道禁用/失败） |
| `borrowability_truncated=True` | **False** | 按 classic_ref 正常填（pair_listed / asset_borrowable / daily_interest_vip0） | **保留传入值** | **null** | **`borrowability_not_probed`**（新枚举） |
| 正常 | True | 正常填 | 传入值 | portfolio_by_asset 值 | None |

关键：`borrowability_truncated=True` **不得**清空 `daily_interest_account`，只清空 `portfolio_account`；`checked_at` 保留（classic 侧确已校验）。新 `error` 用 `borrowability_not_probed`，与旧 `not_probed_this_round` 区分——解耦后利率随全量覆盖，`not_probed_this_round`（=利率也无）几乎不再出现，仅保留兼容。

### 3.5 分批合并（**必需**——Gate B 已确认单次上限 20）

`fetch_cost_leg_chain` 必须把 `rate_probe_assets` 按 **batch_size=15**（≤20 硬上限，留余量）切批，逐批调用 next-hourly，**合并原始 `next_hourly` dict 后再**进 `_select_chain_tier`：

```text
for batch in chunk(rate_probe_assets, 15):
    resp = GET next-hourly?assets=<batch>&isIsolated=false
    merged_next_hourly.update({x.asset: x.nextHourlyInterestRate for x in resp})
_select_chain_tier(merged_next_hourly, rate_history, cross_table, vip_level)
```

- 不得对每批分别 `_select_chain_tier` 再合并 tier 结果（会产生多套快照级 tier，语义不可校验）。
- 单批失败不得静默吞：至少记录 Binance code + 该批资产（修 `private_client.py:319` 的静默 `except`），否则 tier① 再次失效将不可见（本次 bug 的教训）。
- 权重预算：66 资产 = 5 批 × ~100 = ~500 IP/快照，1h TTL 下可忽略。

---

## 4. 下游消费者收口（本版核心，防复发）

契约变更 `borrow_validation`（rate 有 / borrowability 无）必须同时改到以下所有消费者：

### 4.1 summary / coverage / warning（`snapshot_service.py:219`、tests L869-892）

- `coverage` 语义已在 §3.1 重定义为 borrowability 覆盖。
- `coverage.skipped > 0` 触发的 top-level warning 文案须校准：从"候选被截断（无利率）"改为"部分资产可借额度未探测（利率仍覆盖）"，不得再暗示利率缺失。

### 4.2 前端徽章（`frontend/index.html:893-909`）

在通用 `not_probed_this_round` 分支**之前**新增一态：

```javascript
if (bv && bv.verified === false && bv.error === 'borrowability_not_probed') {
  return `<span class="badge muted" title="PRIVATE_BORROW_VALIDATION_REQUIRED">有利率·可借性未探测</span>`;
}
```

利率子行（L1093-1098）无需改：`borrow_rate_source != null` 时已能正确渲染"日借币: X.XX%"。改后该行呈现自洽——利率列有值、状态列明确"可借性未探测"，不再与"未探测(限速预算)"矛盾。

### 4.3 前端自检 self-check（`frontend/self-check.js:687-724`）

第 34 项"负费率状态行感知的五文案派生"当前钉死 `DUSDT → 未探测(限速预算)`。须**新增第六态用例**：`error='borrowability_not_probed'` 且 `daily_interest_account` 有值 → 断言状态列显示"有利率·可借性未探测"(`badge muted`) **且**利率子行仍展示"日借币: X.XX%"。相应 fixture（`backend/tests/fixtures/private-account-v1-design.json` / self-check 内联）补一行携带利率但可借性未探测的数据。

### 4.4 API 契约文档（`docs/api/public-market-contract.md` §coverage/warnings，L447-454）

当前文档写"截断候选 render `verified=false` / `error="not_probed_this_round"`"并隐含链路字段为空——**语义已变**，必须更新为：

- 新增 `error` 枚举 `borrowability_not_probed`：可借额度未探测，但 `daily_interest_account` / `net_daily_yield` **仍填充**。
- `coverage` 语义改为 borrowability 覆盖；`coverage.skipped>0` 的 top-level warning 文案改为"部分资产可借额度未探测（利率仍覆盖）"。
- 若涉及 `snapshot.schema.json` 的 `error` 枚举，做 additive enum update + 兼容测试。

### 4.6 排序（`snapshot_service.py:216` / `sort_rows` L646）

无需改代码，但须知晓并在验收记录：先前被截断的行现获非空 `net_daily_yield`，`sort_basis=net_daily_yield` 时会纳入 net 排序、改变行序——**期望行为**（它们确有净收益）。核对 `test_phase2_borrow_sort.py` 是否有受影响的快照断言。

---

## 5. 暂不做（deferred）

per-asset tier synthesis（根因 B）、`interestRateHistory` 逐资产补洞、maxBorrowable rotating queue、WebSocket、下单/借还/划转、bStock 负费率借币、大规模 UI 重构。若 immediate fix 后仍有大量**非 bStock** 资产缺利率，再开 `per-asset-cost-leg-v1`。

---

## 6. 测试策略

### 6.1 阻塞回归：borrowability 截断不得清空利率（本阶段最重要）

```text
构造：borrow_check_max_calls=2；4 个负费率 MARGIN_SPOT_CANDIDATE+CRYPTO 资产；
     next-hourly fixture 覆盖全部 4 个；maxBorrowable 只探测前 2 个。
断言（第 3/4 资产，穿过 assemble_private/行装配的集成断言）：
  borrow_rate_source == "next_hourly"
  borrow_validation.classic_margin.daily_interest_account 非空
  net_daily_yield 非空
  borrow_validation.portfolio_account.max_borrowable is None
  borrow_validation.error == "borrowability_not_probed"
无此测试，DRAFT-4 不得进入实现验收。
```

### 6.2 修改现有测试（不是新增——必须改）

- `test_private_account_v1.py:227 test_borrow_validation_truncated_state`：现钉死 `truncated=True → daily_interest_account is None`，与本方案冲突。改为用 `borrowability_truncated=True` 且断言 `daily_interest_account` **保留**、`error == "borrowability_not_probed"`、`portfolio_account.max_borrowable is None`。
- L855-859 / L869-892 coverage & warning 断言：按 §4.1 新文案与新 coverage 语义更新。

### 6.3 Gate A / Gate B 证据（落档）

```text
Gate A: negative_margin_spot_crypto_candidate_count / borrow_check_max_calls / would_truncate
Gate B: next_hourly_request_asset_count / returned_asset_count / missing_assets / status / weight
若 would_truncate=false → 停止实现、重新诊断。
若 Gate B 需分批 → 增分批合并测试（batch1=A/B, batch2=C/D → _select_chain_tier 收到 A/B/C/D）。
```

### 6.4 现有行为回归（保留）

next-hourly hourly×24 正确；bStock 无利率且不可借；private channel disabled 不触发私有请求；只读红线成立。

```text
python3 -m pytest backend/tests/test_private_account_v1.py -q
python3 -m pytest backend/tests/test_phase2_borrow_sort.py -q
python3 -m pytest backend/tests/test_snapshot.py -q
python3 -m pytest backend/tests -q
```

---

## 7. 代码边界

允许修改：

- `backend/domain/snapshot.py`：`select_borrow_candidates`（拆三集合 + coverage 重定义）、`assemble_borrow_validation`（`borrowability_truncated` 语义）
- `backend/services/snapshot_service.py`：两条 asset set 分别驱动 cost_leg / maxBorrowable；行装配传新参数
- `backend/services/private_client.py`：仅 Gate B 需要分批时改 `fetch_cost_leg_chain`
- `backend/config.py`：可选新增 `BINANCE_BORROW_RATE_MAX_ASSETS`、`BINANCE_NEXT_HOURLY_ASSET_BATCH_SIZE`
- `frontend/index.html`：新增 `borrowability_not_probed` 徽章态
- `frontend/self-check.js`（+ fixture）：新增第六态用例（§4.3）
- `docs/api/public-market-contract.md`：更新 coverage/warnings 契约语义（§4.4，**必改**——语义已变，非可选）
- 后端测试（含 §6.2 修改项）

谨慎修改（仅 additive）：`schemas/api/public-market/snapshot.schema.json`——若新增 `error` 枚举值 `borrowability_not_probed` 需 additive enum update + 兼容测试；不改字段形状则不动 schema。

禁止修改：`.env` / API key；交易、借币、还币、划转；WebSocket；手动开仓；bStock 负费率借币规则。

---

## 8. 验收标准

1. Gate A 显示 `count > borrow_check_max_calls` 时，top-N 外资产只要 next-hourly 命中就保留日借币利率与 `net_daily_yield`。
2. `borrow_check_max_calls` 只限制 `maxBorrowable`，不限制 next-hourly 利率覆盖。
3. `assemble_borrow_validation` 不因可借额度未探测而清空 `daily_interest_account`。
4. 可借性未探测（`borrowability_not_probed`）与利率未覆盖（`borrow_rate_source=null`）在数据与 UI 上均可区分。
5. next-hourly 未返回的资产不得伪造利率。
6. 前端对"有利率·可借性未探测"行渲染自洽（利率列有值 + 明确徽章），无"利率 vs 未探测"矛盾。
7. bStock 负费率借币套利仍禁用。
8. 全部测试通过（含 §6.1 新增、§6.2 修改、§4.3 前端 self-check 第六态）。
9. `docs/api/public-market-contract.md` 的 coverage/warnings 契约语义已同步（§4.4）；如动 schema 枚举则 additive + 兼容测试。
10. live smoke test 只读，不触发交易/借还/划转。

实现报告建议输出：

```text
rate_probe_assets_count / borrowability_probe_assets_count / borrowability_unprobed_assets_count
next_hourly_returned_assets_count / rows_with_rate_count / rows_with_rate_but_borrowability_unprobed_count
```

---

## 9. 阶段与任务

```text
stage-id: 2026-07-borrow-cost-coverage-v2
complexity: MEDIUM
owner: claude_glm
review-1: kimi
review-2: codex 或 claude/fable5（按 Harness 规则）
```

- Task A：Gate A ✅ PASS（66>50）+ Gate B ✅ RESOLVED（单次上限 20，Kimi §9）——**两门均已完成，可直接进实现**。
- **Task A2（承重·主修）：修复 tier① next-hourly**——按 §3.5 实现 batch_size=15 分批合并（合并在 `_select_chain_tier` 之前）+ 修 `private_client.py:319` 静默 `except` 加失败诊断，使 tier① 真正命中。这是主症状（~49 个 `-`）的主修。
- Task B：`select_borrow_candidates` 拆三集合 + coverage 重定义；`snapshot_service` 两链路解耦。
- Task C：`assemble_borrow_validation` 的 `borrowability_truncated` 语义 + 新 `error` 枚举。
- Task D：下游收口——summary/warning 文案、前端徽章态（§4.2）、前端 self-check 第六态用例 + fixture（§4.3）、**`docs/api/public-market-contract.md` 契约语义更新（§4.4）**、§6.2 现有测试修改。
- Task E：§6.1 阻塞回归 + Gate 证据测试 + 只读 live smoke。

顺序硬约束：**Task A2（修 next-hourly）先于 Task B（解耦）**——tier① 不出数据时解耦无效。Task B/C/D 契约变更须同阶段一并交付（不可拆层，否则重演 ping-pong）。

---

本地北京时间: 2026-07-07 21:20 CST
下一步模型: Claude-GLM（owner，实现）
下一步任务: 启动 stage 2026-07-borrow-cost-coverage-v2 实现（Gate A/B 均已完成；见 stage dispatch packet）

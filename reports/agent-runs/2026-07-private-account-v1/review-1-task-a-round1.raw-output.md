# Review-1 · Task A（后端）— first_reviewer 评审

- stage: `2026-07-private-account-v1`
- role: `first_reviewer`（fresh Kimi 只读会话）
- 对象: Task A（后端）已提交状态
- base_sha: `fce1452cbc1db652477f517c4017a13f3ffb5449`（H_intake PASS）
- head_sha: `6ca6ee1db61952c10d547aa73a79e0711b2ae64b`（H_A backend）
- diff_fingerprint（重算）: `6ca6ee1db61952c10d547aa73a79e0711b2ae64b:fdfba177950b8872b386d07c1ee02ddfff7eaa0b044307691ebbb40235b8a252`
- 对照规格: `10-design.md` §1/§2/§3 + status.json hard_constraints + 白名单 12 项
- 本地北京时间: reviewer 未附时间戳（用户中转于 2026-07-06）

> 落档说明（bookkeeper）：本文件 Kimi 原始输出经用户终端中转，表格 ASCII
> 被换行拆断失真，由 bookkeeper 重建为 markdown 表格（**文字内容与 verdict
> JSON 逐字保留**；JSON 字符串值内的中转换行已还原为完整字符串，因 JSON
> 字符串值不可跨行）。verdict JSON 块为 Kimi 应 bookkeeper 补派后追加，未
> 改动任何评审结论、未重跑评审。

---

## 1. 审计元数据核查

- 当前分支：`stage/2026-07-private-account-v1`
- 工作树：干净（`git status --short` 为空）
- Task A 提交范围：`fce1452cbc1db652477f517c4017a13f3ffb5449..6ca6ee1db61952c10d547aa73a79e0711b2ae64b`
- 重算 diff fingerprint：`6ca6ee1db61952c10d547aa73a79e0711b2ae64b:fdfba177950b8872b386d07c1ee02ddfff7eaa0b044307691ebbb40235b8a252`
- 与 prompt 给定指纹一致 ✅

## 2. 测试重放

```text
$ python3 -m pytest backend/tests/ -q
147 passed in 5.22s

$ python3 -m pytest backend/tests/test_private_account_v1.py -q
48 passed in 1.42s
```

## 3. 逐项核查（对照 10-design §1/§2/§3 + hard_constraints + 12 项白名单）

| # | 检查项 | 结论 | 关键证据 |
|---|---|---|---|
| 1 | 白名单 12 项与 `status.json.endpoint_whitelist` 完全一致；越界/非 GET 在签名构造前 raise；负向单测齐 | PASS | `backend/services/private_client.py:48-66`；`backend/tests/test_private_client.py:121-160` |
| 2 | 单一 HMAC 出口仍唯一 | PASS | `backend/services/private_client.py:118-168`；grep 断言 `test_single_hmac_exit*` |
| 3 | 四级成本腿链：命中判定/顺序正确；E2 hourly×24 归一化；source 枚举合规；E1/E1b 仅登记不被 fetcher 调用 | PASS | `_select_chain_tier:409-462`；`fetch_cost_leg_chain:268-356`；`resolve_cost_leg_rate:385-403`；`test_e1_e1b_whitelisted_but_no_fetcher_calls_them:441-451` |
| 4 | net_daily_yield 六向量（含负零归一、Decimal 禁 float） | PASS | `backend/domain/snapshot.py:302-330`；`test_compute_net_daily_yield_vectors:53-72` |
| 5 | 排序双向量：net 反超 + abs Phase 2 全序回归 | PASS | `sort_rows:560-590`；`test_sort_net_reversal_core_assertion:145-183` |
| 6 | coverage/warnings：上限 50 可配、截断 `not_probed_this_round`、顶层 warnings 追加（round1 blocker A 已修） | PASS | `assemble_snapshot:206-212`；`test_truncation_appends_top_level_warning:778-838` |
| 7 | 防重复计算：`total_value_usdt = Σ(unified 折算) + Σ(spot 折算)`；um_positions 名义价值不计入；P5 价格 map 全量一次 | PASS | `assemble_private_account:463-557`；`test_assemble_private_account_anti_double_count:242-270` |
| 8 | private_account 三态语义同 borrow_validation：classic_ref 门控（round1 blocker B 已修） | PASS | `snapshot_service.py:152-159,166-173`；`test_private_account_disabled_when_classic_ref_none_even_if_accounts_return:851-886` |
| 9 | 数值卫生/落档脱敏：diff 与新 fixture 无真实 key 片段、无真实账户数值；redaction scan 通过 | PASS | `test_redaction_scan_design_fixture:690-694`；`test_redaction_scan_captured_samples:697-718` |
| 10 | 零改动红线：classify.py/normalize.py 未改动；无 websocket/listenKey 铺垫；无 status.json/commit | PASS | `git diff -- backend/domain/classify.py`、`backend/domain/normalize.py` 为空；`test_no_websocket_listenkey_scaffolding:724-733` |

## 4. 额外核查

- Discovery 证据 sha256 抽验：抽查 `sapi-v1-margin-next-hourly-interest-rate.json`、`papi-v1-balance.json`、`api-v3-account.json`，sha256 与 `evidence-index.md` 记录一致 ✅
- 冻结预算表 vs 实测 weight 头：`10-design §2.A.1` 表与 `evidence-index.md` 实测头一致（E2=100、W3=50、E3=20、E4=25、E6=24、P5=4 等）✅
- `60-test-output.txt`：当前文件为 Task B frontend self-check 结果（9/9 PASS）；backend 测试输出以本次重放 147 passed 为准 ✅
- diff 范围：仅触碰 `backend/**`、`schemas/**`、`docs/api/**` 及 stage 报告文件，未越界 ✅

## 5. 残余风险 / 非阻塞观察

1. E2b tier② 覆盖受限：实现按 A1 假设仅对 top candidate 单资产探针；E2 已一次覆盖全部候选，此为已记录的 R3 升级口。
2. E4 position_side 推断：papi positionRisk 无直接字段，当前按 positionAmt 符号推断 LONG/SHORT，需真实持仓出现时实测复核（设计已记录）。
3. ADR-11 文件缺失：`docs/architecture/ADR/11-adr.md` 不在 Task A §3.1 允许文件内，本轮 diff 未改动，建议 bookkeeper 在阶段落盘前按 `00-task.md` 硬约束补录。

## 6. 总结论

Task A 后端实现满足 `10-design.md` §1/§2/§3 与 status.json hard_constraints；round1 两项 scope 内 blocker 已修并有回归测试覆盖；全量 147 passed 零回归；diff fingerprint 一致。review-1 结论：**ACCEPT**，推进 review-2。

## verdict JSON（Kimi 应补派后追加，逐字）

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-private-account-v1",
  "role": "first_reviewer",
  "model": "kimi",
  "verdict": "ACCEPT",
  "diff_fingerprint": "6ca6ee1db61952c10d547aa73a79e0711b2ae64b:fdfba177950b8872b386d07c1ee02ddfff7eaa0b044307691ebbb40235b8a252",
  "reviewer_prior_involvement": "none",
  "reviewed_artifacts": [
    "reports/agent-runs/2026-07-private-account-v1/review-1-task-a-by-kimi.prompt.md",
    "reports/agent-runs/2026-07-private-account-v1/status.json",
    "reports/agent-runs/2026-07-private-account-v1/10-design.md",
    "reports/agent-runs/2026-07-private-account-v1/20-implementation-backend.md",
    "reports/agent-runs/2026-07-private-account-v1/60-test-output.txt",
    "reports/agent-runs/2026-07-private-account-v1/embedded-review-a-round2.raw-output.md",
    "backend/services/private_client.py",
    "backend/domain/snapshot.py",
    "backend/services/snapshot_service.py",
    "backend/adapters/binance_public.py",
    "backend/config.py",
    "backend/tests/test_private_account_v1.py",
    "backend/tests/test_private_client.py",
    "schemas/api/public-market/snapshot.schema.json",
    "docs/api/public-market-contract.md",
    "reports/api-samples/2026-07-private-account-v1/20260705T232800Z/evidence-index.md"
  ],
  "findings": [
    {
      "severity": "P3",
      "title": "E2b rate_history tier 仅覆盖单一 top candidate",
      "file": "backend/services/private_client.py",
      "line": 326,
      "evidence": "fetch_cost_leg_chain 对 interestRateHistory 只发 asset=borrow_assets[0] 一次探针；frozen discovery 仅验证单 asset 参数。",
      "impact": "若 E2 完全失败且存在多个 borrow candidate，仅 top candidate 能命中 tier②，其余回落至 tier③/④。",
      "recommendation": "作为 R3 升级口：bookkeeper 实测 E2b 是否支持逗号 asset 参数后再扩展全候选覆盖。"
    },
    {
      "severity": "P3",
      "title": "E4 um_positions.position_side 由 positionAmt 符号推断",
      "file": "backend/domain/snapshot.py",
      "line": 446,
      "evidence": "_infer_position_side 根据 positionAmt 正负推断 LONG/SHORT；papi positionRisk 无直接 positionSide 字段。",
      "impact": "真实持仓出现时方向推断需实测复核。",
      "recommendation": "真实 UM 持仓出现后，实测 papi positionRisk 并复核推断逻辑。"
    },
    {
      "severity": "P3",
      "title": "ADR-11 文件尚未创建",
      "file": "docs/architecture/ADR/11-adr.md",
      "line": null,
      "evidence": "00-task.md 要求本 stage 记录 ADR-3/一阶近似/防重复计算/脱敏映射/预算表冻结，但文件不存在且不在 Task A §3.1 允许文件内。",
      "impact": "阶段级文档缺口，不影响 Task A 代码交付。",
      "recommendation": "bookkeeper 在阶段落盘前按 00-task.md 硬约束补录 ADR-11。"
    }
  ],
  "required_fixes": [],
  "residual_risks": [
    "E2b tier② 全候选覆盖需 R3 实测确认。",
    "E4 position_side 推断需在真实持仓场景下复核。",
    "ADR-11 需在 stage 落盘前补录。"
  ],
  "next_action": "continue"
}
```

---

## bookkeeper 标注（隔离偏差 + 实质评估；用户裁定方案 A）

**发现（偏差）**：Kimi 的 `reviewed_artifacts[]` 含
`reports/agent-runs/2026-07-private-account-v1/embedded-review-a-round2.raw-output.md`
——即 first_reviewer 读取了嵌入预审 round2 的 PASS 输出。T1 dispatch
（`review-prompts-templates.md:15-16` / `review-1-task-a-by-kimi.prompt.md`）
明确要求"与实现/设计/嵌入预审无先前关联（预审由另一 fresh 会话完成，**其结论
对你不可见**）"。此条违反 fresh 隔离契约。

**实质评估**：
- 独立性大体保持——Kimi 的指纹重算（一致）、147 passed 复现、discovery sha256
  抽验、冻结预算表抽验均为独立动作；3 项 findings（E2b / E4 / ADR-11）均带独立
  代码行号证据（`private_client.py:326` / `snapshot.py:446`），**非** round2
  fix 内容（round2 fix 的是 §1.5 截断 warning + §1.4 disabled 三态）的复述。
- anchor bias 风险存在——知道预审已 PASS 可能在"穷尽找新问题"上放松，但无法
  从输出倒推证实/证伪。
- `reviewer_prior_involvement="none"` 在 schema 语义下仍正确（该字段仅覆盖
  direction/breakdown/design；读 embedded-review 不属这三类）；违规在 dispatch
  契约层，不在 schema 字段层。

**处理（方案 A，用户 2026-07-06 裁定）**：接受本 verdict；`tasks[A].review_1
.json_schema_valid=true`（JSON 实例结构合规的事实判断，与独立性维度分开）；本
偏差升级为 review-2（T3）**必查项**——由 Codex final_reviewer 独立判定 first_
reviewer 独立性是否实质受损、ACCEPT 是否仍成立；若 review-2 判定独立性受损，
可在 review-2 阶段退回 Task A 重做。bookkeeper 不替 reviewer 改写
`reviewed_artifacts`（verbatim 原则）。

---

模型身份: kimi，fresh 只读 first_reviewer 会话
本地北京时间: reviewer 未附（用户中转 2026-07-06）
落档: bookkeeper (claude_glm，续任会话)

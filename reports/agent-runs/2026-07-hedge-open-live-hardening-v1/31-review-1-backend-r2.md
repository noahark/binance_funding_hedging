# Review-1 (round 2) — Backend — Hedge Open Live Hardening v1

角色：`first_reviewer`（后端第 2 轮）。只读评审；未改仓库、未下单、未访问凭据、未发起 Binance 写请求、未启动服务、未调用其他模型会话。

固定范围（不使用移动 HEAD）：

```text
base_sha        = 6c5b17002cab189d752177b447ff576356998f58
head_sha        = c91d2da5fe38c8b8ecf6bd3fb6c3ee9e0141a3c8
diff_fingerprint= c91d2da5fe38c8b8ecf6bd3fb6c3ee9e0141a3c8:aad2351a429714f07e759304400087c2f0a5ccc33a0111b9532153bf86c50b23
```

本机重算 `git diff --binary 6c5b170..c91d2da -- . ':(exclude)reports/agent-runs/2026-07-hedge-open-live-hardening-v1/status.json'` 的 sha256 与 status/dispatch 钉扎指纹 **逐字一致**。

本轮对照权威顺序：`00-task.md` 验收标准优先于设计措辞；`50-review-2.md` 的 P2 与 `40-fix-review-2-s5.md` 是被审证据，与代码冲突时以代码为准。

---

## 1. S5 是否真正满足验收标准（本轮核心）

**结论：满足。Review-2 P2 已实质性关闭，不是表面传参。**

### 1.1 根因描述是否属实

属实，且比 Review-2 原文更深一层：

1. **表面缺陷**（`50-review-2.md`）：`RecordTransportExecutor.execute` 调 `validate_order_params` 时未传 `step_size`/`min_qty`/`max_qty`，而 `wire_constraints.validate_order_params` 已实现这三项可选检查。
2. **更深根因**（修复者报告 + 代码）：`compute_preflight` 旧 `snapshot_record` 仅有 `spot_step`/`perp_step`，**没有**有效 min/max；即便 executor 想传 min/max 也无数据源。同时 step 虽已写入 snapshot，record transport **从不消费**，对 S5 而言是死字段。

### 1.2 修复是否真正关闭 finding

闭合链路（生产路径）：

| 环节 | 证据 |
| --- | --- |
| 有效 bounds 一次解析 | `domain._qty_bounds`（`domain.py:567-591`）与 `effective_market_step` 同一 MARKET_LOT_SIZE→LOT_SIZE 回退语义；min/max **各自独立**回退 |
| snapshot additive 写入 | `compute_preflight`（`domain.py:755-773`）写入 `spot_min_qty`/`spot_max_qty`/`perp_min_qty`/`perp_max_qty` |
| transport 消费、不二次推导 | `_leg_qty_filters`（`executor.py:367-391`）只读 `{leg}_step`/`_min_qty`/`_max_qty` |
| 校验调用 | `RecordTransportExecutor.execute`（`executor.py:305-310`）`validate_order_params(..., **_leg_qty_filters(...))` |
| 违规结果 | 两腿 `_rejected_leg`、`error_code=offline_constraint`、`constraint_violations` 入 payload、`posted: false`、**不**进入 `_simulate_leg` 成交模拟（`executor.py:311-325`） |

**没有**第二套 filter 选择规则：step 仍走 `effective_market_step`，min/max 仍走 `_qty_bounds`，只在 `compute_preflight` 执行一次。

### 1.3 测试是端到端还是只测校验器

`backend/tests/test_hedge_wire_constraints.py:252-311` 通过 **`RecordTransportExecutor.execute`**：

| 测试 | 断言 |
| --- | --- |
| `test_record_transport_rejects_quantity_violating_loaded_filters`（`0.0005` / `200`） | 两腿 `REJECTED`、`offline_constraint`、`constraint_violations` 含 step/min 或 max、`filled_qty=="0"`、`posted is False` |
| `test_record_transport_accepts_grid_aligned_quantity_with_loaded_filters` | 合法 grid 仍 `success` 并模拟 fill |
| `test_record_transport_applies_per_leg_filters_independently` | spot/perp 过滤条件不同时仅 perp 前缀违规 |

这是 **transport 端到端行为**，不是只直接调 `validate_order_params`。另有预修复 S1 形式（38 字 client id）离线必拒回归。

### 1.4 与 `00-task.md` S5 原文核对

> rejects … quantity/price precision **against the symbol filters already loaded**

- MARKET 开仓无 `price` → 不验 price 是正确的（`wire_constraints.py:67-69`）。
- step 倍数 + min/max bounds = 已加载 filter 上的 quantity 约束。
- 设计文档 §2.5 若读成「网格检查可选」，**不得压过**验收标准——本轮按验收标准判定 **通过**。

### 1.5 Additive 字段

四字段写入 JSON TEXT `preflight_snapshot`；store 不校验键集合；无 schema 迁移、无冻结 status/entries 词表变更。早期失败分支（`step_unreadable` 等）不带这四键，与「无 filter 则跳过 bounds」一致。

---

## 2. ADR-H4：wire_constraints 不得挂 live 发送路径

**结论：未破坏。**

- `wire_constraints` / `validate_order_params` 仅出现在 `wire_constraints.py` 与 `executor.py`（record transport）。
- `backend/services/live_hedge_executor.py`、`hedge_open_live_client.py` 无 import。
- 相对 `6c5b170..c91d2da`：`live_hedge_executor.py`、`hedge_open_live_client.py`、`binance_signing.py`、`scheduler.py`、`config.py` **零 diff**。

---

## 3. S1 clientOrderId 推导

**结论：满足验收。**

- 唯一推导点：`executor._client_order_ids` → `hg{attempt_id}s|p`（2+32+1=**35** ≤36）。
- 双腿互异；uuid4 hex 全局唯一支撑。
- record 与 live 共用该函数（live 从 executor 导入），ADR-2 仅凭 clientOrderId 对账仍成立。
- 测试：`test_client_order_id_derivation_within_cap_distinct_charset_unique`；预修复 38 字形式 offline 拒单。

---

## 4. S3 Start 闸门

**结论：满足验收。**

| 要求 | 证据 |
| --- | --- |
| 应用内开关、无 SQL | `POST /api/hedge-open-settings/start-gate` → `put_start_gate` |
| 显式确认 | `confirm is not True` → 400 `confirmation_required`（拒 `1`/`"true"`/`None`/`False`/`[]`） |
| version CAS | `isinstance(version, bool) or not isinstance(version, int)` 排除 bool；错 version → 409 + 当前 settings |
| CAS+审计同事务 | `store.set_start_gate_cas` 同一 `with self._lock, self._conn` 内 UPDATE + INSERT audit |
| 默认关闭 | `start_gate INTEGER NOT NULL DEFAULT 0`；API 测 fresh DB `start_gate is False` |

---

## 5. S4b 探针三态

**结论：满足。**

- `create_task` 仅 `legs.get(k) is False` 拦截；`None` 不拦截（`service.py:480-485`）。
- 测试：`test_create_does_not_block_when_probe_indeterminate`；provider 矩阵含 transport failure → `None`。

---

## 6. A-5 `fmt_decimal`

**结论：通过。** `build_spot_order_params` / `build_perp_order_params` 均用 `D.fmt_decimal(quantity)`；未见科学计数法/精度回归。

---

## 7. M-1 `start_gate_changed` 与 attempt 形状正交

**结论：通过。**

- 审计 payload 键集精确为 `{enabled, previous_enabled, version, source}`（`store.py:1756-1762`）。
- 后端：`test_m1_start_gate_audit_payload_keys_disjoint_from_attempt_shape`。
- 前端（跨 seam 观察，非本轮改前端）：`self-check.js` M-1 断言 `extractHedgeAttempts` 忽略该行。

---

## 8. 文件边界

**backend 本范围主要交付：**

`wire_constraints.py`（新）、`domain.py`、`executor.py`、`service.py`、`store.py`、`server.py`、`hedge_preflight_provider.py`、对应 tests、`reports/api-samples/.../client-order-id-cap.md`。

禁止动的 live/signing/scheduler/config：**零改动**。  
`frontend/**` 存在于同一 stage 提交历史，**不在本 gate 评审范围**；未发现后端 wire 与已 ACCEPT 前端消费的不一致（version/confirm/missing_leg/M-1 形状对齐）。

---

## 9. 冻结契约

- status / entries 词表：无语义改动。
- settings doc：additive 暴露 `version`（CAS 输入），既有键语义不变。
- `start_gate_changed` 刻意不进 entries 词表（ADR-H2），符合设计。

---

## 10. 安全

- 未把 offline 校验器挂上 live POST 路径（ADR-H4）。
- 三道实盘授权结构未削弱：`APP_HEDGE_EXECUTOR` / durable start_gate / 任务 Start。
- 本评审未触达凭据、未实盘下单。
- F-1..F-4（`18-live-acceptance-findings.md`）**按 dispatch 指示不计入本轮**。

---

## 残余风险（非阻断、非本轮必改）

1. **无单独单测断言 `compute_preflight` 产出四新键**：transport e2e 用手造 snapshot 形状覆盖消费侧；若有人删掉 `domain.py` 写入而保留 executor 测试注入，CI 仍可能绿。建议 follow-up 加一条 domain 单测（P3 级残余）。
2. **无 preflight provider 时** dry-run 仍无 filter bounds（设计如此）；有 snapshot 后才强制网格。
3. **Live 路径仍完全依赖币安** 作参数权威（ADR-H4 已闭合决策）。
4. 实盘 F-1..F-4 与裸空头属于独立 stage / 人工处置，不构成对本 fingerprint 的 REWORK。

---

## 测试证据

`60-test-output.txt`（返工合并态 bookkeeper 权威复跑）：

- backend **983 passed**（基线 979 + 本修 4）
- frontend **122 PASS**
- protocol **72 passed**
- `git diff --check` exit 0

---

## 总评

对照 `00-task.md` 的 S1/S3/S4b/S5 与 Review-2 P2：后端最终形态 **ACCEPT**。  
上一轮把 S5 网格问题降为 residual 是错误优先级；本轮代码与 e2e 测试已把「已加载 symbol filters 上的 quantity」纳入 offline transport 拒绝路径。

```text
当前 Session ID: unavailable (Grok TUI session; no provider-native id in runtime env)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-live-hardening-v1/31-review-1-backend-r2.md
本地北京时间: 2026-07-28 06:58:19 CST
下一步模型: bookkeeper
下一步任务: 归档本评审原始输出，将 backend review-1 r2 记为 ACCEPT，并推进 51-review-2-r2（可与本 gate 并行）
```

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-hedge-open-live-hardening-v1",
  "role": "first_reviewer",
  "model": "grok-4.5",
  "verdict": "ACCEPT",
  "diff_fingerprint": "c91d2da5fe38c8b8ecf6bd3fb6c3ee9e0141a3c8:aad2351a429714f07e759304400087c2f0a5ccc33a0111b9532153bf86c50b23",
  "reviewer_prior_involvement": "none",
  "reviewer_prior_involvement_notes": "This session did not design, implement, or fix delivery code for this stage. Implementer is claude_glm (zhipu_glm). Round-1 backend Review-1 was a separate grok-4.5 ACCEPT that missed S5 severity; this is a fresh re-review of the reworked range after user reroute. Dispatch packet named Opus 4.8; operator executed this packet in a Grok session — provider isolation from the implementer still holds.",
  "reviewed_artifacts": [
    "reports/agent-runs/2026-07-hedge-open-live-hardening-v1/00-task.md",
    "reports/agent-runs/2026-07-hedge-open-live-hardening-v1/10-design.md",
    "reports/agent-runs/2026-07-hedge-open-live-hardening-v1/11-adr.md",
    "reports/agent-runs/2026-07-hedge-open-live-hardening-v1/12-development-breakdown.md",
    "reports/agent-runs/2026-07-hedge-open-live-hardening-v1/50-review-2.md",
    "reports/agent-runs/2026-07-hedge-open-live-hardening-v1/40-fix-review-2-s5.md",
    "reports/agent-runs/2026-07-hedge-open-live-hardening-v1/60-fix-review-2-s5.dispatch.md",
    "reports/agent-runs/2026-07-hedge-open-live-hardening-v1/19-r4-diff-reconciliation-rework1.md",
    "reports/agent-runs/2026-07-hedge-open-live-hardening-v1/16-r4-diff-reconciliation.md",
    "reports/agent-runs/2026-07-hedge-open-live-hardening-v1/60-test-output.txt",
    "reports/agent-runs/2026-07-hedge-open-live-hardening-v1/18-live-acceptance-findings.md",
    "backend/hedge_open_tasks/domain.py",
    "backend/hedge_open_tasks/executor.py",
    "backend/hedge_open_tasks/wire_constraints.py",
    "backend/hedge_open_tasks/service.py",
    "backend/hedge_open_tasks/store.py",
    "backend/app/server.py",
    "backend/services/hedge_preflight_provider.py",
    "backend/tests/test_hedge_wire_constraints.py",
    "backend/tests/test_hedge_executor.py",
    "backend/tests/test_hedge_api.py",
    "backend/tests/test_hedge_store.py",
    "backend/tests/test_hedge_service.py",
    "backend/tests/test_hedge_preflight_provider.py",
    "git diff 6c5b17002cab189d752177b447ff576356998f58..c91d2da5fe38c8b8ecf6bd3fb6c3ee9e0141a3c8 -- backend/ reports/api-samples/",
    "schemas/review-verdict.schema.json"
  ],
  "findings": [],
  "required_fixes": [],
  "residual_risks": [
    "No dedicated unit test asserts compute_preflight emits spot_/perp_ min/max keys; transport e2e injects the snapshot shape by hand (P3 residual, non-blocking).",
    "Without a loaded preflight snapshot, dry-run still cannot enforce filter bounds (by design when no filters are available).",
    "Live send path still does not mount wire_constraints (ADR-H4 closed decision).",
    "Live-acceptance defects F-1..F-4 and the outstanding NOMUSDT naked short are out of this stage/fingerprint and must not be fixed here."
  ],
  "next_action": "continue"
}
```

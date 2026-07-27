# Review-1 后端 — `2026-07-hedge-open-live-hardening-v1`

**角色**：first_reviewer（Grok 4.5，只读）  
**实现者**：claude_glm（`zhipu_glm`）— 与本评审员 provider 隔离  
**先验参与**：none（无方向合成 / 设计 / breakdown / 实现）  
**固定范围**：`base 6c5b170` → `head 319d831`  
**指纹（已本地重算一致）**：  
`319d8317bdf180750197c95078d2ae6c60e6badc:2a457c0f559fec81cfba8b9d59602c8630bbec73d7b86b28dddab12c4e554efd`

**方法**：`git diff 6c5b170..319d831 -- backend/ reports/api-samples/` + 源码与测试原文 + `60-test-output.txt`（合并态 979 passed）。实现报告与 R4 对账仅作线索，以代码为准。

---

## 1. S1 id 推导 — **通过**

| 检查项 | 结论 | 证据 |
|--------|------|------|
| 长度恒 ≤36 | 固定 **35**（`hg`+32hex+`s\|p`） | `executor.py` `_client_order_ids`：`return f"hg{attempt_id}s", f"hg{attempt_id}p"` |
| 双腿互异 | 尾缀 `s`/`p` | 同上 + `test_client_order_id_derivation_within_cap_distinct_charset_unique`（2000 次 uuid4） |
| 全局唯一 | 随 attempt uuid4 hex | 同上 `seen` 集 |
| 推导点唯一 | 单函数；live **导入**而非复制 | `live_hedge_executor.py:45` import `_client_order_ids`；`:485` 调用。禁止文件 `live_hedge_executor.py` 在本 range **零 diff** |
| 仅凭 clientOrderId 对账（ADR-2） | 对账读持久化 leg 行，不重推 | `service.py:1118` `query_leg(..., leg["client_order_id"])` |
| 历史 38 字符不迁移 | 成立：对账不重推；旧行仍可 query | 设计 §2.1 + 上述 query 路径 |

预留推导还用于 `service.py:1471` `prepare_attempt` 与 record/live 共用同一 `_client_order_ids`，无第二套规则。

---

## 2. S3 CAS 与审计原子性 — **通过**

`store.set_start_gate_cas`（约 1723–1767 行）：

1. `with self._lock, self._conn:` 单事务  
2. `SELECT start_gate, version` → 版本不符即 `None`（无写）  
3. `UPDATE ... WHERE id=1 AND version=?` → `rowcount==0` 再 `None`  
4. 同事务 `INSERT hedge_open_log`（`kind=start_gate_changed`，`task_id="start-gate"`）  
5. 再 `get_settings()`（`RLock` 可重入，同源连接可见未提交写）

**失败窗口**：

- CAS miss：无 UPDATE、无审计（`test_set_start_gate_cas_miss_returns_none_and_writes_nothing`）  
- UPDATE 成功但 INSERT 失败：整事务回滚，不会「改了闸门没审计」  
- 锁 + `WHERE version=?`：同进程串行；跨进程以 rowcount 为准  

既有无条件 `set_start_gate` 保留给测试/内部 seam；HTTP 只走 `put_start_gate`。

---

## 3. confirm 字面量不可绕过 — **通过（已对代码，非只看测试名）**

`service.put_start_gate`：

```python
if body.get("confirm") is not True:  # → 400 confirmation_required
...
if isinstance(version, bool) or not isinstance(version, int):  # 拒 True/False 冒充 int
```

| 输入 | 行为 |
|------|------|
| `confirm: 1` / `"true"` / `[]` / `None` / 缺失 | 400（`is not True`） |
| `confirm: true`（JSON→Python `True`） | 通过 |
| `version: true` / `false` | 400 invalid_field |
| `enabled: "true"` / 多余键 | 400 invalid_field |

测试覆盖：`1`/`"true"`/`None`、`version: True`、bare `confirm:false`。`[]` 未单独 parametrize，但谓词已覆盖（P3 测试缺口，非缺陷）。

---

## 4. S4b 探针三态 — **通过**

- `_spot_leg_exists`：仅 `status==400` 且 `code==-1121` → `False`；5xx/传输失败 → `None`；2xx 且 symbol 在列表 → `True`  
- `_perp_leg_exists`：成功读全量列表后 present/absent；否则 `None`  
- `create_task`：`missing = [k for k in ("spot","perp") if legs.get(k) is False]` — **`None` 永不拦截**  
- `_read_public_with_status`：读取 `HTTPError` body，才能辨认 -1121  
- `DisabledPreflightProvider`：仅 `get_snapshot`；`assert not hasattr(..., "check_symbol_legs")`；duck-typing → dry-run 零网络  

`-1121→False` 依据：设计/api-samples + 注入式假件矩阵（非本会话实网请求）。

---

## 5. S5 校验器 — **通过**

| 项 | 结论 |
|----|------|
| regex 与 api-samples | 均为 `CLIENT_ORDER_ID_MAX=36`、`^[\.A-Z\:/a-z0-9_-]{1,36}$` |
| record 违规保留证据 | 先写 `constraint_violations` 再 append records，再双腿 REJECTED + `offline_constraint` |
| 纯度守卫 | `wire_constraints.py` 仅 `re`/`decimal`；`test_hedge_purity` 对 `hedge_open_tasks/**` `rglob("*.py")` 自动覆盖新模块 |
| pre-fix 回归 | `test_prefix_s1_derivation_fails_offline_and_new_derivation_restores`：monkeypatch 旧 38 字推导 → offline 失败 → 恢复新推导成功；钉住**缺陷类**而非只钉数字 36 |
| 严格 fake | `_FakeClient` 违规回 `-4015` 风格 400 |

**设计取舍（非 REWORK）**：`validate_order_params` 的 step/min/max 为可选；record 路径当前不传 filters（与 10-design §2.5 一致）。00-task 写得更宽，以本 stage 设计为准。

**P3 文档**：api-samples 中文写「反斜杠」，regex 字符类实际无 `\`（`\:` 是冒号转义）。系统自产 id 仅 hex+`h/g/s/p`，无运行时影响。

---

## 6. A-5 `fmt_decimal` — **通过**

- 复现：`str(Decimal("0.0000001")) == "1E-7"`  
- `build_spot/perp_order_params` 的 `quantity` → `D.fmt_decimal(quantity)`  
- `fmt_decimal` 用 `format(..., "f")` 并去尾零，**不用科学计数法**  
- `test_a5_small_decimal_quantity_is_fixed_point_not_scientific` 钉死  

live 的 `record_payload` 仍有 `str(send_qty)`（日志字段）；**下单 wire** 走 `build_*`，属既有日志形态，非本 stage 回归。

---

## 7. M-1 审计 payload 键集合 — **通过**

`test_m1_start_gate_audit_payload_keys_disjoint_from_attempt_shape` 断言 payload 恰为  
`{enabled, previous_enabled, version, source}`，与  
`{attempt_seq, pair_outcome, spot, perp}` **不相交**。

另：`start_gate_changed` **不在** `_ENTRY_EVENT_KINDS`，不进入冻结 `entries` 时间线，只经 legacy `logs`——符合 ADR-H2「不修订 entries 词表」。

---

## 8. 文件边界 — **通过**

本 range 后端/api-samples 15 文件均在 13 号 packet 允许清单内。

**禁止文件零改动**（已 `git diff --name-only` 核对）：  
`live_hedge_executor.py`、`hedge_open_live_client.py`、`binance_signing.py`、`scheduler.py`、`config.py`。

前端 diff 不在本评审范围。

---

## 9. 冻结契约 — **通过**

- `domain.py` 仅 **additive** `missing_leg_detail`；无 STATUS/PAIR/ATTEMPT 词表改动  
- settings 加 additive `version`；`start_gate_changed` 不进 entries  
- 无 real-api-v1 entries 投影 / status 状态机修订  

---

## 10. 安全 — **通过**

- 无 live client/executor/signing 改动 → 无新真实 POST 路径  
- 无凭据访问；探针为**公共无签名** GET（live 建卡时）  
- S5 故意不挂 live 发送路径（ADR-H4，不作为 REWORK）  
- 三道授权结构未合并：`APP_HEDGE_EXECUTOR=live` / durable start_gate / 首笔任务仍独立  
- `confirm:true` + CAS 写闸门 ≠ 自动开单  

测试证据：`60-test-output.txt` 合并态 **979 passed**。

---

## 总评

后端任务在固定 fingerprint 上满足 S1/S3/S4b/S5/A-5/M-1 与文件/契约/安全边界。  
**verdict: ACCEPT**，`next_action: continue`（bookkeeper 收口后进入 review-2 / 或并行等前端 review-1）。

```
当前 Session ID: unavailable (本 grok CLI 会话未向执行体暴露 provider-native session id；env 无可用 XAI/GROK session 句柄)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-live-hardening-v1/30-review-1-backend.md
本地北京时间: 2026-07-27 20:58:59 CST
下一步模型: bookkeeper
下一步任务: 将本输出原样归档为 30-review-1-backend.md，校验 JSON schema，记录 session_receipts；并行等待/归档 frontend review-1 后推进 review-2（codex）
```

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-hedge-open-live-hardening-v1",
  "role": "first_reviewer",
  "model": "grok-4.5",
  "verdict": "ACCEPT",
  "diff_fingerprint": "319d8317bdf180750197c95078d2ae6c60e6badc:2a457c0f559fec81cfba8b9d59602c8630bbec73d7b86b28dddab12c4e554efd",
  "reviewer_prior_involvement": "none",
  "reviewed_artifacts": [
    "reports/agent-runs/2026-07-hedge-open-live-hardening-v1/00-task.md",
    "reports/agent-runs/2026-07-hedge-open-live-hardening-v1/10-design.md",
    "reports/agent-runs/2026-07-hedge-open-live-hardening-v1/11-adr.md",
    "reports/agent-runs/2026-07-hedge-open-live-hardening-v1/12-development-breakdown.md",
    "reports/agent-runs/2026-07-hedge-open-live-hardening-v1/13-implementation-backend.dispatch.md",
    "reports/agent-runs/2026-07-hedge-open-live-hardening-v1/20-implementation-backend.md",
    "reports/agent-runs/2026-07-hedge-open-live-hardening-v1/16-r4-diff-reconciliation.md",
    "reports/agent-runs/2026-07-hedge-open-live-hardening-v1/60-test-output.txt",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/11-adr.md",
    "git diff 6c5b17002cab189d752177b447ff576356998f58..319d8317bdf180750197c95078d2ae6c60e6badc -- backend/ reports/api-samples/",
    "backend/hedge_open_tasks/executor.py",
    "backend/hedge_open_tasks/wire_constraints.py",
    "backend/hedge_open_tasks/store.py",
    "backend/hedge_open_tasks/service.py",
    "backend/hedge_open_tasks/domain.py",
    "backend/app/server.py",
    "backend/services/hedge_preflight_provider.py",
    "backend/services/live_hedge_executor.py",
    "backend/tests/test_hedge_store.py",
    "backend/tests/test_hedge_api.py",
    "backend/tests/test_hedge_executor.py",
    "backend/tests/test_hedge_wire_constraints.py",
    "backend/tests/test_hedge_preflight_provider.py",
    "backend/tests/test_hedge_service.py",
    "backend/tests/test_live_hedge_executor.py",
    "backend/tests/test_hedge_purity.py",
    "reports/api-samples/2026-07-hedge-open-live-hardening-v1/client-order-id-cap.md"
  ],
  "findings": [
    {
      "severity": "P3",
      "title": "api-samples 中文「反斜杠」与 regex 字符类不完全一致",
      "file": "reports/api-samples/2026-07-hedge-open-live-hardening-v1/client-order-id-cap.md",
      "line": 38,
      "evidence": "事实页写「点、大写字母、反斜杠、冒号…」；wire_constraints.CLIENT_ORDER_ID_RE 与设计一致为 ^[\\.A-Z\\:/a-z0-9_-]{1,36}$，字符类不含反斜杠字面量（\\: 仅为冒号转义）。",
      "impact": "仅文档措辞；系统自产 id 只用 hex+h/g/s/p，无运行时误拒/误放。",
      "recommendation": "后续顺手把「反斜杠」改为与正则一致的字符说明；不阻塞本 stage。"
    },
    {
      "severity": "P3",
      "title": "confirm 测试矩阵未显式覆盖 [] 等 truthy 非 True 值",
      "file": "backend/tests/test_hedge_api.py",
      "line": 248,
      "evidence": "put_start_gate 使用 body.get('confirm') is not True，语义上已拒绝 1/\"true\"/[]/None；API 测试 parametrize 了 1/\"true\"/None，未列 []。",
      "impact": "实现正确；测试覆盖略窄，回归时可能漏改谓词。",
      "recommendation": "可选：把 []、{} 加入 confirm 负例表。非必须修复。"
    }
  ],
  "required_fixes": [],
  "residual_risks": [
    "live 发送路径按 ADR-H4 不挂 wire_constraints；格式类缺陷依赖唯一推导点 + 离线/严格 fake 前移，币安仍是真钱路径最终裁决者。",
    "UM newClientOrderId 字符集 regex 未单独实测（api-samples §4）；本系统自产 id 在安全子集内。",
    "S4b None 不拦截：公共行情瞬时失败时，恰缺失的 symbol 仍可能建出空转卡（ADR-H5 已知取舍）。",
    "record transport 当前不把 symbol filter 的 step/min/max 传入 validate_order_params（与 10-design 可选网格一致；精度类网格错误仍主要依赖 preflight/q_common 路径）。"
  ],
  "next_action": "continue"
}
```

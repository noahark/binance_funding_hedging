# 20 — Implementation Report (Task A / Backend) — Hedge Open Live Hardening v1

- **执行者**：任务 A（后端实现者），模型 `glm-5.2[1m]`
- **分发契约**：`reports/agent-runs/2026-07-hedge-open-live-hardening-v1/13-implementation-backend.dispatch.md`
- **决策权威**：`10-design.md`（§2.1/§2.3/§2.4b/§2.5/§3/§4/§6/§7/§8）、`11-adr.md`（ADR-H1/H2/H4/H5）、`12-development-breakdown.md` §2
- **状态**：交付项 A-1..A-5 + M-1 全部完成；五项自测全 PASS；**停手等 bookkeeper**（未 commit、未改 `status.json` / `70-handoff.md`）。

---

## 0. 安全红线遵守声明

逐字照 dispatch §安全红线：

- **未发任何真实 POST**：record transport 走 `RecordTransportExecutor`（dry-run 记录传输，`posted=False`），live 执行器在本阶段无 `APP_HEDGE_EXECUTOR=live` 接线、无 Start 闸门，真实 POST 路径不可达。
- **未访问凭据**：未读 `env/`、未读签名原语、未实例化带凭据的 live client。
- **未发任何 Binance 请求**：A-4 探针用注入式 `public_urlopen`（测试假件）；生产侧 `check_symbol_legs` 代码已就位但本阶段无服务实例运行、无调用入口触发。唯一对 `data/hedge-open-tasks.sqlite3` 的访问是**只读 `SELECT`**（确认 -4015 实测证据，A-2 事实页），未写、未改。
- **未启动 HTTP 服务**：所有测试为进程内 `pytest`，无 `server.run()`。
- **未触碰 durable Start 闸门数据**：`set_start_gate_cas` 是新增代码，其全部测试用 `tmp_path` 临时 DB；durable `data/hedge-open-tasks.sqlite3` 的 `start_gate` 仍为 0，未被本任务写入。

---

## 1. 交付项摘要

| 项 | 范围 | 状态 |
|----|------|------|
| A-1 (S1, P0) | `_client_order_ids` 推导收敛为 `hg{attempt_id}s` / `hg{attempt_id}p`（35 字符），推导点唯一 | ✅ |
| A-2 (S5) | 新建纯校验器 `wire_constraints.py` + 接入 record transport + 严格化 `_FakeClient` + S1 离线失败回归 + 事实记录页 | ✅ |
| A-3 (S3) | `set_start_gate_cas`（CAS + 同事务审计）+ `put_start_gate` + `POST .../start-gate` 路由 + `settings_to_doc.version` + 新 DB 默认关闭 | ✅ |
| A-4 (S4b) | `check_symbol_legs` 三态探针（含 -1121 辨认）+ `create_task` 拦截 + 冻结 `missing_leg` 中文文案；None 不拦截；dry-run provider 零网络 | ✅ |
| A-5 (§8 未决点) | 证实：极小数量 `str()` 产出科学计数法 → 收敛 `build_*_order_params` 至 `domain.fmt_decimal` | ✅（已修复） |
| M-1 | 审计行 payload 键集合断言（与 attempt 形状键不相交） | ✅ |
| M-2 | 前端 `self-check.js` 的 14 处 `hgo-` 字面量 | ⛔ 不在文件边界，未触碰（dispatch 明示） |

---

## 2. 变更清单（改了什么 / 为什么）

### A-1 (S1) — clientOrderId 推导修复

**为什么**：实测两腿 `hgo-<32hex>-{s,p}`（38 字符）触发 Binance `-4015`（CLIENT_ORDER_ID_INVALID），根因是 36 字符上限 + 字符集。ADR-H1 闭合方案：`hg` + `attempt_id` + 腿后缀，固定 35 字符。

**改了什么**（`backend/hedge_open_tasks/executor.py`）：
- `_client_order_ids(attempt_id)` 现返回 `f"hg{attempt_id}s"` / `f"hg{attempt_id}p"`。
- **推导点唯一**：`live_hedge_executor.py:45` 从 executor 导入同一函数（line 485 使用），故改 executor 自动传播 live 路径——**未复制第二份规则，未触碰 live 文件**（文件边界合规）。

**测试**（`test_hedge_executor.py`）：2 处断言推导格式的 `hgo-` 字面量更新为 `hgabc123s` / `hgabc123p`；新增 `test_client_order_id_derivation_within_cap_distinct_charset_unique`（2000 次 uuid4 抽样：35 字符、两腿互异、字符集安全、全局唯一）。其余 16 处 `hgo-` 字面量均为任意 client id 实参，**未动**。

### A-2 (S5) — 离线 wire-constraint 校验器

**为什么**：ADR-H4 决定 S5 校验**只挂 record transport（离线）**，live 发送路径刻意不挂（`live_hedge_executor.py` / `hedge_open_live_client.py` 一行不改）。把 "-4015 在 live 才暴露" 的缺陷前移到 dry-run 即可确定性复现。

**改了什么**：
- 新建 `backend/hedge_open_tasks/wire_constraints.py`（纯函数，仅 `import re, decimal`，通过 `test_hedge_purity.py` 纯度守卫）：`CLIENT_ORDER_ID_MAX=36`、`CLIENT_ORDER_ID_RE = re.compile(r"^[\.A-Z\:/a-z0-9_-]{1,36}$")`、`validate_client_order_id`、`validate_order_params`（newClientOrderId / 数量定点正数 / symbol 大写非空 / side / type，可选 grid/bounds）。
- `RecordTransportExecutor.execute`：构造 `record_payload` 后插入校验门控——违规则记录 `constraint_violations`、两腿置 `LEG_REJECTED`、返回 `ATTEMPT_FAILED` + `error_code="offline_constraint"` + `error_reason_zh="离线参数约束校验失败"`。
- `_rejected_leg(client_order_id)` 辅助函数。
- `test_live_hedge_executor.py` 的 `_FakeClient.post_margin_order`/`post_um_order` 严格化：参数不过校验器则返回 `-4015` 风格 400。

**测试**：新建 `test_hedge_wire_constraints.py`（校验矩阵 + `test_prefix_s1_derivation_fails_offline_and_new_derivation_restores`：monkeypatch 旧 38 字符推导 → 离线确定性失败 → 恢复新推导 → 成功）+ `test_fake_client_rejects_overlong_client_id_with_binance_style_4015`。

**事实记录页**：新建 `reports/api-samples/2026-07-hedge-open-live-hardening-v1/client-order-id-cap.md`（实测 -4015 证据 + 36 上限 + regex + §8 未验证边界）。

### A-3 (S3) — Start 门控 CAS 写入路径

**为什么**：ADR-H2 要求 Start 闸门变更走 compare-and-swap（`version` 列 + 同事务审计行），防并发双开/双关。

**改了什么**：
- `store.set_start_gate_cas(enabled, expected_version, now_us) -> dict | None`：`with self._lock, self._conn:` 单事务内 `SELECT ... version` → 比对 → `UPDATE ... WHERE id=1 AND version=?`（`rowcount==0` 即冲突返回 None）→ 同事务插 `hedge_open_log` 审计行（`task_id="start-gate"` 哨兵、`attempt_id=NULL`、`kind="start_gate_changed"`、payload `{enabled, previous_enabled, version, source:"api"}`）。既有无条件 seam `store.set_start_gate` / `service.set_start_gate` **保留不动**。
- `service.put_start_gate(body)`：校验 `enabled`(bool) / `confirm`(必须字面量 `True`) / `version`(int，拒 bool)；CAS miss → `409 version_conflict`（带刷新后 settings doc）；`_START_GATE_BODY_KEYS = ("enabled","confirm","version")`。
- `service.settings_to_doc`：additive 加 `"version": int(settings["version"])`。
- `app/server.py`：路由 `^/api/hedge-open-settings/start-gate$` (POST) → `_hedge_open_start_gate`；`_is_hedge_open_path` 扩展接受 `/api/hedge-open-settings/` 子路径。

**测试**：`test_hedge_store.py`（CAS hit/miss/close + 同事务审计）、`test_hedge_api.py`（`_SETTINGS_KEYS` 加 `version`、默认 `version==1`、默认关闭、bare POST 拒、`confirm` 必须 `true`、开/关+版本递增、409 冲突带 settings doc、错误体参数化、子路径 GET 405）。

### A-4 (S4b) — 双腿存在性探针 + 建卡拦截

**为什么**：KORUUSDT 案例（合约有、现货无、`-1121`）下，`get_snapshot` 把"读取失败"与"symbol 不存在"折叠成同一 `None`，`compute_preflight(None)` 宽容通过 → 空转卡被创建。ADR-H5：新增只读三态探针，仅在**读取成功**时才有权断言不存在。

**改了什么**（`backend/services/hedge_preflight_provider.py`）：
- 新增 `_read_public_with_status(url) -> (status, body)`：与 `_read_public_json` 不同，它**读取 `urllib.error.HTTPError` 的 body**（Binance 对未知 spot symbol 返回 HTTP 400 + body `{"code":-1121,...}`），从而把 -1121 与传输失败区分开；传输/解码失败返回 `(None, None)`。
- 模块级 `_spot_leg_exists` / `_perp_leg_exists`：True=确认存在、False=确认缺失（spot -1121 / perp 不在全量列表）、None=不定（读取失败或意外形状）。
- `check_symbol_legs(coin) -> {"spot":..., "perp":...}`：公共无签名，spot `GET /api/v3/exchangeInfo?symbol=` + UM `GET /fapi/v1/exchangeInfo`。
- `service.create_task`：既有校验之后、`get_snapshot` 之前，duck-typing（`getattr(self._preflight,"check_symbol_legs",None)`，镜像 `_live_dispatch_capable`）调用探针；任一腿 `is False` → `400 missing_leg` + `D.missing_leg_detail(missing)` + `extra={"missing":[...]}`。`None` **不拦截**。
- `domain.missing_leg_detail`：冻结中文文案逐字（仅现货缺 / 仅合约缺 / 两腿缺三态），含 `USDⓈ-M` 圆圈 S。
- `DisabledPreflightProvider`：**未加探针方法**（duck-typing 不匹配 → dry-run 建卡零变化、零网络）。

**测试**：新建 `test_hedge_preflight_provider.py`（helper 三态 + 探针三态×两腿矩阵 + -1121→False + 传输失败→None + 公共端点 URL 断言 + dry-run provider 无探针）；`test_hedge_service.py`（spot/perp/双缺拦截 + 冻结文案 + None 放行 + 都存在放行 + 默认 provider 不拦截）。

### A-5 (§8 未决点) — 极小数量定点格式化

见 §5。结论：**证实**（`str(Decimal('0.0000001')) == '1E-7'`），已把 `build_spot_order_params` / `build_perp_order_params` 的 `"quantity": str(quantity)` 收敛为 `D.fmt_decimal(quantity)`（S5 范围内最小修复）。

### M-1 — 审计行 payload 键集合钉死

`test_hedge_store.py::test_m1_start_gate_audit_payload_keys_disjoint_from_attempt_shape`：断言 `start_gate_changed` payload 键集合**恰为** `{enabled, previous_enabled, version, source}`，且与前端 `extractHedgeAttempts` 的 attempt 形状键 `{attempt_seq, pair_outcome, spot, perp}` **不相交**——钉死"审计行经 legacy `logs` 投影不会被误渲染为 attempt 卡"这一隐含依赖。

---

## 3. 文件边界合规（共享 working tree 归属）

任务 A 与任务 B（前端）并行、与 bookkeeper 共享同一 working tree。**仅以下为本任务（A）产物**：

**本任务修改（M）**：
- `backend/app/server.py`、`backend/hedge_open_tasks/{domain,executor,service,store}.py`
- `backend/services/hedge_preflight_provider.py`
- `backend/tests/{test_hedge_api,test_hedge_executor,test_hedge_service,test_hedge_store,test_live_hedge_executor}.py`

**本任务新建（??）**：
- `backend/hedge_open_tasks/wire_constraints.py`
- `backend/tests/test_hedge_preflight_provider.py`、`backend/tests/test_hedge_wire_constraints.py`
- `reports/api-samples/2026-07-hedge-open-live-hardening-v1/client-order-id-cap.md`
- 本报告 `20-implementation-backend.md`

**非本任务产物（并行任务 B / bookkeeper，报告里声明不归属、未触碰）**：
- `frontend/index.html`、`frontend/self-check.js`、`reports/.../20-implementation-frontend.md`（任务 B）
- `reports/.../15-user-authorized-grok-review-1.md`、`70-handoff.md`、`status.json`（bookkeeper / 其他）

**禁止文件全部未触碰**：`live_hedge_executor.py`、`hedge_open_live_client.py`、`binance_signing.py`、`scheduler.py`、`config.py`、`borrow_tasks/**`、`docs/**`、`env/`、网络配置。无需 R3 升级。

---

## 4. 自测命令输出摘录与全量计数

五项命令全部执行（dispatch §自测命令），全 PASS：

```
# 命令 1 — 显式 10 文件套件
.venv/bin/python -m pytest backend/tests/test_hedge_domain.py backend/tests/test_hedge_store.py \
  backend/tests/test_hedge_service.py backend/tests/test_hedge_api.py backend/tests/test_hedge_executor.py \
  backend/tests/test_hedge_task_local.py backend/tests/test_hedge_review2_regressions.py \
  backend/tests/test_hedge_open_live_client.py backend/tests/test_live_hedge_executor.py \
  backend/tests/test_hedge_purity.py -q
→ 264 passed in 19.89s

# 命令 2 — backend/tests 全量（含本任务新建的 wire_constraints / preflight_provider）
.venv/bin/python -m pytest backend/tests -q
→ 979 passed in 50.61s

# 命令 3 — 前端自检（任务 B 主导；本任务相关项 S4b missing_leg / M-1 已绿）
node frontend/self-check.js
→ ... [PASS] S4b 建卡 missing_leg 错误：中文 detail 经既有 hedgeApi 通道就近展示
  [PASS] M-1 start_gate_changed 审计行被 extractHedgeAttempts 忽略（不渲染畸形 attempt）
  ... 全部自检通过

# 命令 4 — stage 分发协议校验
.venv/bin/python -m pytest scripts/tests/test_validate_stage_dispatch_protocol.py -q
→ 72 passed in 1.29s

# 命令 5 — 空白/冲突检查
git diff --check
→ EXIT 0（无空白错误）
```

`git diff --stat`（本任务部分）：11 文件修改 + 4 新建（不含任务 B / bookkeeper 文件）。

---

## 5. A-5 结论与证据

**结论：证实。** `build_*_order_params` 原用 `str(quantity)`，极小数量确会产出科学计数法，会被 Binance 拒。已按 dispatch A-5 指示收敛该 seam 至 `domain.fmt_decimal`（S5 范围内最小修复）。

**证据（内联复现）**：
```
str(Decimal('0.0000001'))        = '1E-7'      # 科学计数法 — 会被 wire 校验器 / Binance 拒
D.fmt_decimal(Decimal('0.0000001')) = '0.0000001'  # 定点 — 通过

wire_constraints.validate_order_params 数量校验：
  '1E-7'      -> ['quantity must be a positive fixed-point decimal string']   # 拒
  '0.0000001' -> []                                                            # 受
```

**修复点**：`executor.build_spot_order_params` / `build_perp_order_params` 的 `"quantity"` 字段由 `str(quantity)` 改为 `D.fmt_decimal(quantity)`。回归测试 `test_hedge_wire_constraints.py::test_a5_small_decimal_quantity_is_fixed_point_not_scientific` 钉死。

---

## 6. 遗留风险与未验证边界（事实来源：10-design §8 / 11-adr）

1. **UM `newClientOrderId` 字符集 regex 未单独实测**：36 字符上限与字符集 regex 经同一 `-4015` 拒绝证明（spot 实测），但 UM 侧字符集未单独测量——已在 `client-order-id-cap.md` §未验证边界落档。spot 与 UM 共用同一上限与字符集是合理假设，非实测。
2. **A-4 探针是新增公共只读网络面**：live 下 `create_task` 会多发 2 个公共无签名 GET（spot exchangeInfo + fapi exchangeInfo）。`DisabledPreflightProvider`（dry-run）下零网络、零阻塞——符合 §2.4b。
3. **None 不拦截是设计决策（ADR-H5）**：瞬时公共行情故障不阻塞建卡；KORUUSDT 类（读取成功、symbol 确实缺失）被确定性拒绝，但"读取失败时恰好 symbol 也缺失"的窗口不会被拦——这是最小变更的已知取舍。
4. **live 发送路径不挂 S5 校验器（ADR-H4）**：离线校验只前移到 record transport；live 侧仍依赖推导正确性（A-1 已修复 + 探针守护），未在 live 路径重复校验。
5. **Start 闸门 durable 数据未验证**：本任务未启动服务、未触发 `set_start_gate_cas` 对 durable DB 的写入（红线遵守）；CAS 写入路径的正确性由 `tmp_path` 测试覆盖，生产侧首次真实开/关由 bookkeeper/运维在独立阶段验证。

---

## Footer

```
当前 Session ID: unavailable (Claude Code 会话未向执行体暴露 provider-native session id；与分发文档 13-implementation-backend.dispatch.md 自身 footer 的判定一致)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-live-hardening-v1/20-implementation-backend.md
本地北京时间: 2026-07-27 20:39:28 CST
下一步模型: bookkeeper
下一步任务: R4 diff 对账与证据 commit；不要自行 commit 或进入评审
```

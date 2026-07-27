# client-order-id-cap — Binance `newClientOrderId` 上限与字符集

本页是 stage `2026-07-hedge-open-live-hardening-v1`（S1 / S5 / ADR-H1 / ADR-H4）
的事实记录页，**不是契约修订**（无冻结契约字段变化）。它把 S1 逃过九轮评审的
根因——“36 字符上限这一事实从未落档”——补上，并记录本 stage 在离线侧强制该
约束的决定与未验证边界。

## 1. 实测证据：38 字符 client id 被币安以 `-4015` 拒绝

- **时间**：2026-07-27 09:00:00 +08:00（首笔真实对冲尝试）。
- **task**：`01e9a662`（COOKIEUSDT，forward）。
- **两腿 client_order_id**（持久化在 `data/hedge-open-tasks.sqlite3`
  `hedge_open_leg` 表，attempt 的两条 leg 行）：
  - spot：`hgo-760686fa67374279b08625e1c334f3d2-s`（**38 字符**）
  - perp：`hgo-760686fa67374279b08625e1c334f3d2-p`（**38 字符**）
- **币安返回**：两腿均 HTTP 400，`{"code": -4015, "msg": …}`
  （`CLIENT_ORDER_ID_INVALID`）。两腿无 `orderId`，pair `confirmed_failed`，
  `fail_count=1`，task 因计划尝试次数用尽而结算为 `done`（R2-F1 行为）。
- **持久化状态**：`hedge_open_leg.error_code='-4015'`，
  `dispatch_state='TERMINAL_RECORDED'`；`hedge_open_log` 的 record-transport
  payload 记录 `transport=live, posted=true`（请求确已发出、确被拒绝）。
- **来源**：
  - `data/hedge-open-tasks.sqlite3`（hedge_open_leg 两行 `error_code=-4015`，
    `length(client_order_id)=38`）；
  - `reports/agent-runs/2026-07-hedge-open-real-api-v1/status.json`
    `live_first_run_findings.P0_client_order_id_too_long`；
  - `reports/agent-runs/2026-07-hedge-open-real-api-v1/70-handoff.md` §First live run。

旧推导为 `f"hgo-{attempt_id}-s"` / `f"hgo-{attempt_id}-p"`，其中
`attempt_id = uuid.uuid4().hex`（32 hex），总长 `4 + 32 + 2 = 38`，超出上限 2 字符。
该缺陷与余额、权限、symbol、数量均无关——params 正确，仅 id 超长。

## 2. 文档约束：36 字符上限与字符集

Binance 下单接口对 `newClientOrderId` 的约束（现货订单文档）：

- **长度**：`1` .. `36` 字符。
- **字符集**：`^[\.A-Z\:/a-z0-9_-]{1,36}$`（点、大写字母、反斜杠、冒号、正斜杠、
  小写字母、数字、下划线、连字符）。

本系统订单 id 只用：小写 hex（`0-9a-f`）+ 字母 `h/g/s/p`，远在安全集内。

## 3. 本 stage 的决定：离线侧强制该约束（S5 / ADR-H4）

- **新推导**（ADR-H1）：`f"hg{attempt_id}s"` / `f"hg{attempt_id}p"`，固定
  `2 + 32 + 1 = 35` 字符，留 1 字符余量；双腿互异（尾字符 `s`/`p`）；全局唯一
  （uuid4 hex 每 attempt 唯一）；保留可识别前缀 `hg`。推导点保持唯一——dry-run
  record transport 与 live 执行器共用 `executor._client_order_ids` 同一函数。
- **离线校验器**（ADR-H4，新建 `backend/hedge_open_tasks/wire_constraints.py`）：
  - 常量 `CLIENT_ORDER_ID_MAX = 36`、
    `CLIENT_ORDER_ID_RE = re.compile(r"^[\.A-Z\:/a-z0-9_-]{1,36}$")`；
  - `validate_client_order_id` / `validate_order_params`（纯函数，仅 import
    `re`/`decimal`，满足 `hedge_open_tasks` 纯度守卫）。
- **三个消费点**：
  1. `RecordTransportExecutor.execute`——违规即产出两腿 REJECTED 的 outcome
     （`error_code="offline_constraint"`、`error_reason_zh="离线参数约束校验失败"`），
     record payload 记录 `constraint_violations`；dry-run 运行时不再对格式类缺陷
     “演成功”。
  2. 测试严格假件 `_FakeClient`（`test_live_hedge_executor.py`）——对收到的 params
     过同一校验器，违规回币安风格 `400 {"code": -4015, …}`。
  3. 直接单元测试 + pre-fix S1 离线失败回归（`test_hedge_wire_constraints.py`）。
- **live 发送路径刻意不挂校验器**（ADR-H4）：`live_hedge_executor.py` 与
  `hedge_open_live_client.py` 一行不改，真钱路径维持“币安是唯一参数裁决者”的已评审
  语义。格式类缺陷的失败点从“真实发送”前移到“任何一次离线测试/dry-run 派发”。

## 4. 未验证边界（10-design §8）

- **UM（USDⓈ-M 合约）侧 `newClientOrderId` 的字符集 regex 未单独实测**。现货侧有
  文档 + 实测双证据；UM 侧只有**长度上限**的实测证据——首笔真实单的 UM 腿与现货腿
  同样以 `-4015` 被拒（同一次 38 字符提交），证明 UM 侧同样执行 36 字符上限。但 UM
  侧的**字符集 regex** 是否与现货逐字一致，未有独立实测样本。
  - **影响范围**：本系统自产 id 只用 hex + 少量字母，对两侧均合法，无实际风险。
  - **潜在风险**：仅在校验器将来被复用于“手工输入的 newClientOrderId”时，若 UM 侧
    regex 实际更窄，可能放过本应拒绝的 UM id。当前无此复用面。

## 5. 关联

- 决策权威：`reports/agent-runs/2026-07-hedge-open-live-hardening-v1/10-design.md`
  §2.1（S1）、§2.5（S5）、§8（未验证点）；`11-adr.md` ADR-H1 / ADR-H4。
- 上一 stage 实测发现：
  `reports/agent-runs/2026-07-hedge-open-real-api-v1/status.json`
  `live_first_run_findings.P0_client_order_id_too_long`。

# Stage 设计 — Hedge Open Live Hardening v1

作者角色：stage designer（Claude Fable 5, anthropic）。设计-only：本文档产出过程
未修改任何产品源码、status.json、70-handoff.md 或 PRD；未访问凭据、未发起任何
Binance 请求、未启动服务。

事实来源（全部已读原文）：
`reports/agent-runs/2026-07-hedge-open-live-hardening-v1/{00-intake.md,00-task.md,status.json}`；
`reports/agent-runs/2026-07-hedge-open-real-api-v1/70-handoff.md` §First live run 与该
stage `status.json.live_first_run_findings`；
`reports/agent-runs/2026-07-hedge-open-real-api-v1/{10-design.md,11-adr.md,16-replacement-development-breakdown.md}`；
`backend/hedge_open_tasks/{domain.py,store.py,service.py,executor.py,scheduler.py}`；
`backend/services/{live_hedge_executor.py,hedge_open_live_client.py,hedge_preflight_provider.py}`；
`backend/app/server.py`；`backend/config.py`；`frontend/index.html`；
`backend/tests/test_hedge_*.py`、`backend/tests/test_live_hedge_executor.py`；
`docs/parallel-development-mode.md`；`AGENTS.md`；`agents/developer-discipline.md`。

## 1. 目标与非目标

**目标**：修复五个「只有真实发送才暴露」的运行时缺口（S1–S5，锚点与证据见
00-intake.md），使得当 human 分别打开三道实盘授权
（`APP_HEDGE_EXECUTOR=live`、durable Start 闸门、首笔真实任务）后，一笔真实订单
**能够**成功。本 stage 本身不授予任何实盘权限；intake 时服务已停、
`start_gate=0`（`status.json.live_surface_state_at_intake`）。

**非目标**（照抄 00-task.md，不复述理由）：smooth 模式；自动平仓/对冲/借币/修复；
1000x 前缀归一化；修订任何 real-api-v1 冻结契约；任何实盘激活。

## 2. 各项设计决策

### 2.1 S1 (P0) clientOrderId 推导

**现状事实**：`backend/hedge_open_tasks/executor.py:158-160`
`_client_order_ids(attempt_id)` 返回 `f"hgo-{attempt_id}-s"` / `-p"`，
`attempt_id = uuid.uuid4().hex`（32 hex，`service.py:1407`），总长 38 > 币安上限
36，两腿均 `-4015`。该函数是唯一推导点：dry-run record transport
（`executor.py:257`）与 live 执行器（`backend/services/live_hedge_executor.py:485`）
都从它取值。对账**不重新推导**：`service.py:1055` 查询用的是持久化在
`hedge_open_leg.client_order_id` 行里的值（`store.py:85`，UNIQUE 列）。产品代码
没有任何地方解析 `hgo-` 前缀（已 grep 确认；仅 `live_hedge_executor.py:509-510`
的线程名字面量含 `hgo-`，与 id 无关）。

**决策**：新推导为

```python
return f"hg{attempt_id}s", f"hg{attempt_id}p"
```

- 长度固定 2 + 32 + 1 = **35 ≤ 36**，留 1 字符余量；
- 字符集：小写 hex + `h/g/s/p`，全部落在币安文档的
  `^[\.A-Z\:/a-z0-9_-]{1,36}$` 内（见 §7 api-samples 记录义务）；
- 双腿互异（尾字符 `s`/`p`）；全局唯一（uuid4 hex 每 attempt 唯一）；
- 保留可识别前缀 `hg`，运维在币安订单历史里仍能一眼认出本系统订单。

被否决的备选与理由见 `11-adr.md` ADR-H1。

**与 ADR-2 对账路径的关系**：不变。查询/恢复只读持久化的 leg 行
（`list_non_terminal_legs_for_task` → `query_leg(…, leg["client_order_id"])`），
推导只发生在 `prepare_attempt` 之前一次（`service.py:1408`），因此新旧格式在
DB 中并存不影响任何路径。

**历史遗留 38 字符 id 兼容**：**不做迁移**。库中已知的 38 字符记录（task
`01e9a662` 两腿）全部 terminal（`error_code=-4015`，REJECTED），对账只查
non-terminal legs，永远不会再把旧 id 发往币安。`client_order_id` 的 UNIQUE 约束
与新格式（35 长、无 `-`）天然不冲突。残余风险：若存在未知的 non-terminal
38 字符 leg（当前无证据，未验证），按 origClientOrderId 查询可能被币安以参数错误
拒绝（400 非 -2013 → `classify_query_response` 返回 None → 保持查询、永不重发），
表现为该卡持续 querying——这是修复前既已存在的状态，不因本次改动恶化，不在本
stage 处理。

**测试**：直接断言两腿 id `len ≤ 36`、互异、字符集匹配、跨 attempt 唯一；断言
record payload 与 live dispatch 使用同一推导（既有 seam 不变）。注意
`backend/tests/` 中约 18 处 `hgo-` 字面量：其中作为任意 cid 实参传入的不需要动；
凡断言推导结果格式的必须随新格式更新（实现者逐个核对，不得放宽断言粒度）。

### 2.2 S2 (P1) live 新建卡无法启动

**定性结论（不两头下注）**：这是**纯前端按钮条件缺陷**，不是后端状态语义问题。

理由：后端语义是自洽的——`running` 是持久化的「已武装、允许调度」状态
（`store.py:373-374` 新卡即 running，这是 real-api-v1 冻结的状态词表；dry-run 的
`tick()` 正是按此语义自动派发 running 卡）。live 模式缺的不是一个新状态，而是
「worker 是否在跑」这个**运行时事实**，后端已经以 additive 字段
`worker_active`（tri-state：live 下 true/false，dry-run 下 null，
`service.py:508-516`）暴露了它。若为此新增一个初始状态（如 `created`），将修订
冻结的状态词表，波及 store/筛选器/前端标签/大量测试，并把一个运行时事实错误地
固化成持久状态。`post_start` 对 running 卡已是幂等正确行为：置 running +
`ensure_worker`（`service.py:521-535`），后端一行不用改。

**前端修复**：`frontend/index.html:3685` 改为

```js
const startDisabled = (
  task.status !== 'paused' &&
  task.status !== 'exposure_alert' &&
  !(task.status === 'running' && task.worker_active === false)
) ? ' disabled' : '';
```

- dry-run 行为不变：dry-run 下 `worker_active === null`，第三个分支恒为 false，
  按钮条件与今天完全一致；
- live 下：running 且 worker 未在跑 → 「启动」可点，点击即 `post_start` →
  `ensure_worker`，这是**人工动作**，不构成自动派单；running 且 worker 在跑 →
  仍然置灰（无事可做）；
- H-1 的 `tick()` no-op（`service.py:1169-1177`）与 `create_task` 不起 worker 的
  行为**都不动**。

**已知携带限制（不修）**：上一 stage 记录的 open P2 —— `post_start` 无
attempts-exhausted 检查（`70-handoff.md` §Two OPEN P2 follow-ups (a)）。正常路径
下 attempts 用尽的卡会结算为 done（Start 置灰），该 P2 需要新的用户授权才能动，
本 stage 不扩范围。

### 2.3 S3 (P2) Start 闸门写入路径（用户已决定：对称确认弹窗）

**接口契约**（本 stage 冻结，前后端并行实现的共享面）：

1. `GET /api/hedge-open-settings` 响应 **additive** 增加 `"version": <int>`
   （取自 `hedge_open_settings.version` 列，`store.py:134`；现有
   `settings_to_doc`（`service.py:169-174`）未暴露它，前端拿不到就无法做并发安全
   写）。既有字段名与语义全部不变。

2. 新路由 `POST /api/hedge-open-settings/start-gate`
   （`server.py` `_HEDGE_OPEN_ROUTES` 增一条；`_is_hedge_open_path` 需同步接受该
   子路径——当前只精确匹配 `/api/hedge-open-settings`，`server.py:98-105`）。

   请求体（拒绝未知键，镜像 `reject_unknown_keys` 纪律）：

   ```json
   {"enabled": true, "confirm": true, "version": 3}
   ```

   - `enabled`：严格 bool（开=true / 关=false，同一接口对称承载两个方向）；
   - `confirm`：必须为字面 `true`，缺失或非 true → 400
     `{"error": "confirmation_required", "detail": "开单闸门变更必须显式确认"}`——
     这是后端侧的显式确认语义，防止任意裸 POST 误开闸；
   - `version`：严格 int（排除 bool），须等于当前 settings 行的 `version`。

   响应：
   - 200 → 完整 settings doc（含新 `version`）；
   - 409 `{"error": "version_conflict", "detail": "设置已被其他会话修改，请刷新后重试", "settings": <当前 settings doc>}`
     ——CAS 未命中时返回当前 doc，前端据此刷新重试（镜像 borrow `edit_task` 的
     `version_conflict` 先例，`backend/borrow_tasks/service.py:261-267`）；
   - 400 `invalid_json` / `invalid_field` / `confirmation_required`。

3. **并发安全**：store 新增
   `set_start_gate_cas(enabled, expected_version, now_us) -> dict | None`，单条

   ```sql
   UPDATE hedge_open_settings SET start_gate=?, version=version+1, updated_at_us=?
    WHERE id=1 AND version=?
   ```

   `rowcount==0` → None → 409。既有无条件 seam
   `store.set_start_gate` / `service.set_start_gate`（`service.py:852-861`，
   测试在用）**保留不动**，additive 新增，不改签名。

4. **审计日志（与 CAS 同一事务）**：CAS 命中时在**同一** store 事务内向
   `hedge_open_log` 追加一行：`task_id="start-gate"`（sentinel；列 NOT NULL，
   闸门是全局事实无所属任务）、`kind="start_gate_changed"`、payload
   `{"enabled": <bool>, "previous_enabled": <bool>, "version": <new int>, "source": "api"}`、
   `ts_us=now_us`。该行经既有 `list_logs_page`（全量 SELECT，`store.py:1449`）自动
   出现在 `GET /api/hedge-open-logs` 的 legacy `logs` 数组里，durable 可审计。
   **刻意不加进 `_ENTRY_EVENT_KINDS`**（`service.py:56`）：冻结的 entries 投影的
   `overall_result` / `next_action` 词表（16-breakdown §5）没有适配闸门事件的取
   值，塞入会构成契约修订。「who」的保真度说明：本应用是单操作者本地应用、无
   身份体系，能记录的最高保真度是 `source: "api"`（对比历史上的直改 SQL）+ 时间
   戳——与其他 live-risk 动作（task pause/stop 事件）同级。

5. **全新安装默认关闭**：schema 默认 `start_gate INTEGER NOT NULL DEFAULT 0`
   （`store.py:129`）不动；新增测试断言全新 DB 的 settings 为关 + 未带
   `confirm:true` 的写入必被 400 拒绝。

**前端**（同一个控件管两个方向，每个方向恰好一次确认弹窗，无手输确认词）：

- 位置：对冲开单设置区的执行徽标行（`hedgeExecutionBadge`，
  `frontend/index.html:3430-3443`）旁增加一个按钮，label 随当前状态：闸门关 →
  「开启开单闸门」；开 →「关闭开单闸门」。
- 点击 → 弹一次确认弹窗（复用既有 `#hedge-modal`（`index.html:1194-1200`）扩展
  出「确认/取消」双按钮变体，或新增同构小弹窗——实现者任选，语义不变）→ 确认
  后 POST（`version` 取自最近一次 GET 缓存的 `state.hedgeSettings.version`）→
  成功后用响应 doc 刷新徽标与按钮；取消则无任何请求。
- 弹窗中文文案（冻结）：
  - 开方向：标题「开启全局开单闸门？」；正文「开启后，实盘模式（live）下被启动
    的任务可以向币安发出真实订单。此操作立即生效。」；按钮「确认开启」/「取消」。
  - 关方向：标题「关闭全局开单闸门？」；正文「关闭后，任务的 worker 将在下一轮
    检查时退出，不再发出新订单；已提交的订单仍会继续查询到终态。」；按钮
    「确认关闭」/「取消」。
- 409 `version_conflict` → 重新 GET settings 刷新显示，并提示「设置已被其他会话
  修改，已刷新，请重试」；其他错误按既有 hedgeApi 错误路径就近展示中文 detail。

### 2.4 S4 两条欠账

**(a) 前端展示 `worker_active` / `last_worker_exit_reason`**（字段后端已产出：
`task_to_doc`，`service.py:151-152`；从未展示）。任务卡 `borrow-task-lines` 内新
增一行，按既有 `hedgeText` 约定缺失降级「—」：

- `worker_active`：`true` →「运行中」，`false` →「未运行」，`null`/缺失 →「—」
  （dry-run 恒为 null，即恒显示「—」，不误导）；
- `last_worker_exit_reason` 中文映射（enum 见 `domain.py:193-200`）：
  `stopped_event` →「收到停止信号」；`task_missing` →「任务记录缺失」；
  `task_not_running` →「任务已非运行态」；`start_gate_off` →「全局开单闸门未开
  启」；`target_reached` →「计划尝试次数已用完」；`preflight_incomplete` →「预检
  数据不完整（安全退出）」；`preflight_fatal` →「预检发现致命问题」；
  `worker_error` →「worker 异常退出」；未知值原样经 `hedgeText` 展示。
- 展示形如：`执行线程：<运行中|未运行|—> · 上次退出原因：<中文|—>`。

**(b) 建卡时双腿存在性校验**（参照案例 KORUUSDT：合约有、现货无，`-1121`）。

现状事实：live 下 `create_task` 走 `HedgePreflightProvider.get_snapshot`，该方法
把「读取失败」与「symbol 不存在」合并折叠成 `None`
（`hedge_preflight_provider.py:146-164` + `get_snapshot` 任一缺口即 None），
`compute_preflight(None)` 宽容通过（`domain.py:700` `no_preflight_snapshot`），
于是空转卡被创建。要指明「缺哪条腿」必须新增一个能区分三态的探针。

**决策**：`HedgePreflightProvider` 新增只读探针
`check_symbol_legs(coin) -> {"spot": True|False|None, "perp": True|False|None}`：

- spot：`GET /api/v3/exchangeInfo?symbol=<coin>`（公共无签名）。2xx 且 symbol 在
  响应中 → True；**显式 `-1121`**（币安对未知 symbol 返回 HTTP 400 body code
  -1121，实测证据见 live_first_run_findings）→ False；传输失败/其他 → None。
  注意：现有 `_read_public_json` 把 HTTPError 一并吞成 None，探针需要一个能读取
  HTTP 错误 body（辨认 -1121）的读取变体——这是必须改动的既有离线代码之一。
- perp：`GET /fapi/v1/exchangeInfo` 全量列表（与既有 `_read_perp_filters` 同一
  来源与做法）。读取成功且 symbol 在列 → True；读取成功且不在列 → False；读取
  失败 → None。
- `DisabledPreflightProvider` 不提供该探针（或恒 None）→ dry-run 建卡行为不变，
  离线测试零网络。

`create_task`（`service.py:445-495`）在既有校验之后、preflight 之前：provider 具
备探针（duck-typing，镜像 `_live_dispatch_capable` 风格）时调用；任一侧为
**False** → 400：

```json
{"error": "missing_leg", "detail": "<中文>", "missing": ["spot" 和/或 "perp"]}
```

中文 detail（冻结）：仅现货缺 →「该交易对在币安现货市场不存在（缺少现货腿），
无法创建对冲任务」；仅合约缺 →「该交易对在币安 USDⓈ-M 合约市场不存在（缺少合
约腿），无法创建对冲任务」；两侧都缺 →「该交易对在币安现货与 USDⓈ-M 合约市场
均不存在，无法创建对冲任务」。

**Indeterminate（None）不拦截**：探针只在**读取成功**时才有权断言不存在；读取失
败时保持现状（允许建卡），不把公共行情接口的瞬时故障升级为建卡故障。这是最小
变更；KORUUSDT 类案例（读取成功、symbol 确实缺失）会被确定性拒绝。仅存在性校
验，不做 1000x 前缀归一化。前端只需确认建卡错误路径能展示 `missing_leg` 的中文
detail（既有 hedgeApi 错误通道已携带 detail）。

### 2.5 S5 离线 transport 参数约束

**落点决策：独立纯校验器模块**，不塞进任何 transport 内部，也不加进 live 发送
路径。新模块 `backend/hedge_open_tasks/wire_constraints.py`（纯函数，仅 import
`re`/`decimal`，满足 hedge_open_tasks 纯度守卫）：

- 常量：`CLIENT_ORDER_ID_MAX = 36`；
  `CLIENT_ORDER_ID_RE = re.compile(r"^[\.A-Z\:/a-z0-9_-]{1,36}$")`（来源与证据
  记录义务见 §7）；
- `validate_client_order_id(value) -> str | None`：长度 1..36 + 字符集，违规返回
  违规描述字符串；
- `validate_order_params(params, *, step_size=None, min_qty=None, max_qty=None) -> list[str]`：
  校验 `newClientOrderId`（如上）；`quantity` 为正的**普通定点** decimal 字符串
  （无科学计数法 `E`/`e`）；提供 step/min/max 时校验网格整除与上下界；`symbol`
  非空大写；`side`/`type` 在枚举内。MARKET 单不含 `price`，故价格精度仅在参数
  出现时校验。

**三个消费点**：

1. `RecordTransportExecutor.execute`（`executor.py:248-299`，必须改动的 dry-run
   代码）：构造两腿 params 后先过校验器；违规 → record payload 记录
   `constraint_violations` 列表，返回两腿 REJECTED 的 outcome（`error_code=
   "offline_constraint"`、`error_reason_zh="离线参数约束校验失败"`），走既有
   `classify_attempt` → confirmed_failed。dry-run 运行时从此不再对格式类缺陷
   「演成功」。
2. 测试的严格假件：`backend/tests/test_live_hedge_executor.py` 的 `_FakeClient`
   （行 42）在 `post_margin_order` / `post_um_order` 内对收到的 params 过同一校验
   器，clientOrderId 违规时返回币安风格 `400 {"code": -4015, "msg": …}` 响应——
   离线测试面从此与真实交易所同型拒绝。
3. **不进 live 路径**：`live_hedge_executor.py` 与 `hedge_open_live_client.py`
   一行不改。理由与被否决备选见 ADR-H4。

**「修复前 S1 推导会离线失败」的回归测试**（S5 验收核心）：

- 单元层：`validate_client_order_id(f"hgo-{uuid4().hex}-s")` 必须返回长度违规；
- 端到端层：monkeypatch `executor._client_order_ids` 回旧推导，驱动 dry-run
  record transport 派发一组 → 断言 attempt 两腿 REJECTED、
  `error_code="offline_constraint"`、record payload 含 `constraint_violations`；
  恢复新推导 → 同一路径回到 balanced fill。该测试固定住「这类缺陷永远在离线
  失败」的性质，而不只是钉住 36 这个数字。

**api-samples 补记：需要。**在
`reports/api-samples/2026-07-hedge-open-live-hardening-v1/client-order-id-cap.md`
落一页事实记录：实测 `-4015` 证据（2026-07-27，task `01e9a662` 两腿，38 字符被
拒；来源 `data/hedge-open-tasks.sqlite3` 与 live_first_run_findings）、币安文档的
36 上限与字符集 regex、以及「离线 transport 自此强制该约束」的决定。这不是契约
修订（无冻结契约字段变化），是把 S1 逃过九轮评审的根因——事实从未落档——补上。

## 3. 文件边界

**后端任务允许**：
`backend/hedge_open_tasks/{executor.py,service.py,store.py,domain.py}`（domain 仅
错误码/文案等最小增量）、`backend/hedge_open_tasks/wire_constraints.py`（新建）、
`backend/services/hedge_preflight_provider.py`、`backend/app/server.py`（仅路由
接线）、`backend/tests/test_hedge_*.py`、
`backend/tests/test_live_hedge_executor.py`、
`reports/api-samples/2026-07-hedge-open-live-hardening-v1/client-order-id-cap.md`
（新建）、本 stage 的原始实现报告。

**后端任务禁止**：`frontend/**`、`backend/services/hedge_open_live_client.py`
（冻结 allowlist 面）、`backend/services/live_hedge_executor.py`（S1 经由共享推导
函数自动生效，无需改动；若实现中发现必须改，R3 升级给 bookkeeper，不得自行
修改）、`backend/services/binance_signing.py`、`backend/hedge_open_tasks/scheduler.py`、
`backend/config.py`、`backend/borrow_tasks/**`、`docs/**`、既有
`reports/**`、env/凭据文件、任何网络配置。

**前端任务允许**：`frontend/index.html`、`frontend/self-check.js`、本 stage 的原
始实现报告。**禁止**：其余一切。后端字段缺失/改名 → 升级 bookkeeper，不得发明。

## 4. API 与数据契约汇总（并行实现的冻结面）

1. settings doc：`{"executor_mode", "start_gate", "interval_seconds"}` +
   **新增** `"version": <int>`。
2. `POST /api/hedge-open-settings/start-gate`：请求/响应/错误码全形见 §2.3。
3. task doc：`worker_active`（true|false|null）与 `last_worker_exit_reason`
   （§2.4a 枚举|null）——字段已存在，本 stage 零改动，仅前端消费。
4. `POST /api/hedge-open-tasks` 新错误：
   `400 {"error": "missing_leg", "detail": "<中文>", "missing": ["spot"|"perp", …]}`。
5. 冻结的 entries 投影（16-breakdown §5）字段与词表**零改动**。

以上字段名冻结；任何一侧觉得要改，都是 bookkeeper 升级事项，不是本地修复。

## 5. 兼容与迁移

- **无 DB 迁移**。schema 零改动（audit 复用 `hedge_open_log`；CAS 复用既有
  `version` 列）。
- 旧 38 字符 clientOrderId：并存不迁移（§2.1）。
- settings doc 与 create_task 错误码均为 additive，旧前端读新后端不受影响。
- dry-run/离线行为变化点（刻意的、且是本 stage 的目的）：**参数违规时**
  record transport 从「演成功」变为 REJECTED——对现有测试无影响（现有推导修复
  后合法），只对未来的格式类缺陷有影响。

## 6. 测试策略

既有套件必须保持全绿：`backend/tests/test_hedge_store.py`、`test_hedge_service.py`、
`test_hedge_task_local.py`、`test_hedge_executor*.py`（含
`test_hedge_review2_regressions.py`）、`test_hedge_open_live_client.py`、
`test_live_hedge_executor.py`、`test_hedge_purity.py`、全量
`backend/tests`、`node frontend/self-check.js`。

新增（对应 00-task.md 验收）：

- S1：长度/互异/字符集/唯一性直接断言；改坏推导必须挂。
- S2：前端 self-check 断言四象限：dry-run running（disabled）、live running +
  `worker_active:false`（enabled）、live running + `worker_active:true`
  （disabled）、paused（enabled）。
- S3：后端——CAS 命中/未命中（409 带当前 doc）、confirm 缺失 400、未知键 400、
  version 非 int 400、全新 DB 默认关、audit 行与闸门写同事务落库、settings doc
  含 version；前端 self-check——按钮 label 随状态、确认后才发请求、取消零请求、
  409 刷新路径。
- S4：后端——探针三态（True/False/None）×两腿的建卡行为矩阵、`-1121` 判 False、
  传输失败判 None 放行、dry-run provider 零网络零拦截；前端 self-check——
  worker 行渲染三态与退出原因中文映射、`missing_leg` detail 展示。
- S5：校验器单元矩阵（长度/字符集/定点格式/网格/上下界）；record transport 违规
  → REJECTED 端到端；严格 `_FakeClient` 返回 -4015；**pre-fix S1 推导离线失败**
  回归（§2.5）。

**硬性约束**：所有测试不发真实 POST、不访问凭据、不发任何私有请求、不启动
HTTP 服务；网络一律注入假件。

## 7. 必须改动的既有 dry-run / 离线代码清单

1. `backend/hedge_open_tasks/executor.py` `_client_order_ids`（S1 推导）。
2. `backend/hedge_open_tasks/executor.py` `RecordTransportExecutor.execute`
   （S5 校验器接入）。
3. `backend/services/hedge_preflight_provider.py`（S4b 探针 + 可辨认 -1121 的
   公共读取变体）。
4. `backend/hedge_open_tasks/service.py`（`settings_to_doc` 加 version；
   `create_task` 探针拦截；新 `put_start_gate`）。
5. `backend/hedge_open_tasks/store.py`（`set_start_gate_cas` + 同事务 audit 行）。
6. `backend/app/server.py`（start-gate 路由 + `_is_hedge_open_path`）。
7. `backend/tests/test_live_hedge_executor.py` `_FakeClient`（严格化）及各测试文
   件中断言旧 id 格式的用例（约 18 处 `hgo-` 字面量逐个核对）。
8. `frontend/index.html`（S2 按钮条件、S3 控件+弹窗、S4a 展示行、S4b 错误展示
   确认）与 `frontend/self-check.js`。

## 8. 风险与未决点

- **（未验证）`str(Decimal)` 科学计数法**：`build_*_order_params` 用
  `str(quantity)`（`executor.py:130,151`）；极小 q_common 理论上可能产出 `1E-7`
  形式（`domain.fmt_decimal` 明确避免这一点但该 seam 未使用它）。S5 校验器会把
  这类值判违规。实现者必须补一个探测测试；若确能发生，把该 seam 收敛到
  `fmt_decimal`（属 S5 范围内的最小修复）；若不能发生，落一行证据即可。
- **（未验证）UM 合约侧 clientOrderId regex 与现货完全一致**：现货 regex 有文档
  与实测双证据；UM 侧长度上限有实测（-4015 来自 UM 腿同拒），字符集 regex 未单
  独实测。校验器采用两侧交集（本系统 id 只用 hex+字母，远在安全区内），风险仅
  在校验器将来被复用于手工 id 时。api-samples 记录页须写明该未验证边界。
- live 建卡延迟：探针增加 ≤2 次公共读（fapi 全量 exchangeInfo 较大），与既有
  per-preflight 读取同型，属已知成本，不新增网络面。
- `version_conflict` 竞态 UX：双窗口同时操作时后写者收 409 刷新重试；无数据
  风险（CAS 单行原子）。
- S2 使 Start 在 running 卡上可点后，上一 stage 的 post_start 无 exhaustion 检查
  P2 略更易触达（§2.2 已述，display-only，不在本 stage 修）。
- 审计「who」上限为 `source:"api"`（无身份体系），已在 §2.3 声明为本应用可达的
  最高保真度。

当前 Session ID: 9c443dac-2917-4801-bd93-94db85d27de0
Session ID 来源: runtime_env (harness scratchpad path; navigation only)
原始输出路径: reports/agent-runs/2026-07-hedge-open-live-hardening-v1/10-design.md, 11-adr.md, 12-development-breakdown.md
本地北京时间: 2026-07-27 17:59:40 CST
下一步模型: bookkeeper
下一步任务: 归档三份原始设计产物，不要实现代码

Identity:
- task_id: `asset-transfer-live-t1-backend`
- target_role: `Implementer`
- target_model: `opus5`
- provider: `anthropic`
- status_revision: `1`
- required_skill: `agents/skills/senior-developer.md`

Goal

交付资产互转真实划转的**后端**（开发文稿 `00-intake.md` 任务 2 的后端部分；T2 前端由后续 dispatch 覆盖，本任务不接前端）。范围：新建 `asset_transfer` 幂等存储、新增 `POST /api/asset-transfer` 端点（校验 → 幂等 → 调用既有 `universal_transfer` → 落库 → 结构化返回），并给既有 `universal_transfer` 加一条受控的对外通路。

权威契约：`reports/agent-runs/2026-08-06-asset-transfer-live-v1/00-intake.md` §4.2（请求体）、§4.4（幂等）、§4.6（错误回显）、§5（T1）。

**Human 2026-08-06 决定（O-1/O-2，优先级高于开发文稿 §4.3 的推荐方案）：不实现独立 `transfer_gate`、不实现 `TRANSFER_MAX_USDT` 单笔上限**——资产互转在套利中使用频繁，无需特别开关与限制，按正常需求开发。动钱约束收敛为：`confirm: true` 必填（防止误调用与 CSRF 式误触发）+ 全量落库审计 + 幂等防重。开发文稿 §4.3 的闸门/上限文字不再适用，不得实现。

**1. 存储层（新建 `backend/asset_transfer/` 包）**：`asset_transfer` 表，`client_request_id` 唯一索引（幂等键），最小字段按 §4.4：`client_request_id`(UNIQUE)、`from_account`、`to_account`、`asset`、`amount`、`status`(`pending`/`succeeded`/`failed`/`unknown`)、`tran_id`（币安返回，可空）、`error_code`、`error_message`、`created_at_us`、`updated_at_us`。库路径由构造参数注入（生产为独立库 `data/asset-transfer.sqlite3`，测试用临时库），连接模式沿用既有 store（`sqlite3.connect(path, check_same_thread=False)` + `threading.RLock`，参照 `backend/borrow_tasks/store.py`）；表结构经 `_SCHEMA`/`_migrate` 幂等建表（参照 `HedgeOpenStore` 既有惯例）。金额列一律 `TEXT`，任何查询不得对金额列做 `SUM`/`AVG`/算术运算；`amount` 以十进制字符串原样落库。幂等语义：请求先 INSERT `pending` 记录，唯一索引冲突即返回**已有记录**的结果而不重发币安；同一 `client_request_id` 的并发/重复请求由唯一约束挡住，返回首次请求的当前状态。

**2. 端点 `POST /api/asset-transfer`**（`backend/app/server.py` 按既有 `_Handler` + `do_POST` 路由模式新增）：

- 请求体全部必填，缺一即 400：`client_request_id`（UUID 格式校验）、`from_account`/`to_account`（仅 `"unified"`/`"spot"`，两者必须不同，其余组合一律 400）、`asset`（白名单：必须出现在当前快照对应账户余额里，杜绝任意币种注入与打字错误）、`amount`（正十进制字符串：**先字符串正则拒绝负号、科学计数法（`e`/`E`）、空白，再 `Decimal` 解析**，解析失败即 400；不做本地余额充足性预判）、`confirm`（必须为 `true`，否则 400）。
- 方向映射在服务端完成，请求体不得直接传币安 transfer type：`unified→spot` → `PORTFOLIO_MARGIN_MAIN`、`spot→unified` → `MAIN_PORTFOLIO_MARGIN`；映射后调用既有 `universal_transfer`（`backend/services/hedge_open_live_client.py:474`，冻结枚举 + one-shot 写语义）。**不得修改 `universal_transfer` 本体。**
- 结果处理：成功 → `succeeded` + `tran_id`（从返回响应解析）；币安业务拒绝（4xx，如 `-2015`/`-4015`/精度错误）→ `failed` + `error_code`/`error_message` 原样回传，不吞不改写；超时/5xx/网络异常 → **不重试**，状态显式 `unknown`（超时不等于失败，钱可能已转），`error_code`/`error_message` 记录事实。
- 返回结构化结果：`client_request_id`、`from_account`、`to_account`、`asset`、`amount`、`status`、`tran_id`（可空）、`error_code`（可空）、`error_message`（可空）。
- **不内嵌快照刷新**（§4.5：划转成功后由前端调用既有 `POST /api/public-market/cache-refresh`，保持端点单一职责）。

**3. 单元测试（新建 `backend/tests/test_asset_transfer.py`，全离线：桩客户端 + 临时 SQLite）**：两方向映射正确、同账户拒绝、`confirm=false` 拒绝、非法金额（负号/科学计数法 `1e3`/空白/零/非数字）、白名单外币种拒绝、UUID 格式拒绝、幂等重放（同一 `client_request_id` 第二次请求**不产生第二次外发**，以桩调用计数断言）、超时→`unknown` 不重试、失败→`failed` 原样回显错误码、成功→`succeeded` 带 `tran_id`。

不改快照 schema、不改 60 秒调度、不改 cache-refresh、不改开单/平仓/借币链路、不改任何前端文件、不启动任何线程。不做下单/借还/凭证/部署/实盘操作。

Allowed Files

- `backend/asset_transfer/__init__.py`（新建，仅包 docstring）
- `backend/asset_transfer/store.py`（新建）
- `backend/app/server.py`（仅新增路由与 handler；不得改动既有 handler 行为）
- `backend/tests/test_asset_transfer.py`（新建）
- `docs/api/public-market-contract.md`（若端点纳入既有契约文档范围则同步；否则在 handoff 说明并给出端点记录位置）
- `reports/agent-runs/2026-08-06-asset-transfer-live-v1/evidence/asset-transfer-live-t1-backend.handoff.md`（create-only；Bookkeeper 路由前预检 `test ! -e` 结果：`PASS(absent)`；按 `agents/roles.md` 的 Task Handoff Evidence Contract 创建唯一交接件）
- `reports/agent-runs/2026-08-06-asset-transfer-live-v1/evidence/asset-transfer-live-t1-backend.pytest.txt`（测试原始输出）
- `reports/agent-runs/2026-08-06-asset-transfer-live-v1/status.json`（仅可将本任务 `current_task.state` 从 `dispatched` 改为 `reported`；不得改动任何其他字段）

**不得修改**：`backend/services/hedge_open_live_client.py`（`universal_transfer` 本体）、`frontend/` 任何文件、`AGENTS.md`、`agents/roles.md`、`PROJECT_STATE.md`。

Inputs

- `AGENTS.md`
- 本 dispatch（`reports/agent-runs/2026-08-06-asset-transfer-live-v1/20-opus5-t1-backend.dispatch.md`）
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`（重点：Live Risks——应用服务当前停止、launchd 服务损坏、start_gate 常开为既定前提；本任务不得启动服务或触实盘）
- `reports/agent-runs/2026-08-06-asset-transfer-live-v1/status.json`
- `reports/agent-runs/2026-08-06-asset-transfer-live-v1/00-intake.md`（§1 三条实盘事实、§4、§5 T1、§6、§7 Human 决定、§8 评审拓扑——本阶段 Bookkeeper 兼任 review-1 且无 review-2，属 Human 越门记录，不得因此放松自测标准）
- `agents/roles.md` 的 Implementer 章节与 Task Handoff Evidence Contract 章节
- `agents/developer-discipline.md`
- `agents/skills/senior-developer.md`
- `backend/services/hedge_open_live_client.py`（`universal_transfer` :474 起，只读复用）
- `backend/borrow_tasks/store.py`（连接/锁/幂等建表模式参照）
- `frontend/index.html`（只读：资产互转区现有字段名与交互，用于对齐请求字段名，为 T2 接线铺路；不得修改）

Acceptance Checks

1. 全量离线回归：`PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider -q backend/tests` 全绿，且不低于当前基线（开发文稿 §5 记录 1468 passed；若有新增/减少在 handoff 记录前后数字与原因）。不启动服务、不访问网络、不读凭据、不写 `data/`。
2. 幂等有测试证明：同一 `client_request_id` 第二次请求**不产生第二次外发**（桩调用计数断言），且返回首次请求的当前状态。
3. 超时/5xx 路径有测试证明：**不重试**，状态显式 `unknown`（不得显示成失败诱导用户重试），`error_code`/`error_message` 如实记录。
4. 请求校验全覆盖测试：两方向映射、同账户 400、`confirm!=true` 400、非法金额（含科学计数法 `1e3`）400、白名单外币种 400、非法 UUID 400、缺字段 400。
5. 金额精度红线：`amount` 列 `TEXT`，无 SQL 金额聚合，`Decimal` 解析后以十进制字符串原样透传/落库。
6. Human 决定落实：代码中**不存在** `transfer_gate` 与 `TRANSFER_MAX_USDT` 相关实现；动钱约束仅 `confirm: true` + 落库审计 + 幂等。
7. 边界未越过：`universal_transfer` 本体零改动；无任何前端文件改动；未新增除 `POST /api/asset-transfer` 外的路由；未合并、未部署、未做任何实盘/划转/下单/借还/凭证操作。
8. 契约/文档：若端点纳入既有契约文档与 schema 体系则同步；否则在 handoff 给出端点行为记录位置。
9. 基线前提：Human 启动本终端前应已执行 O-4 的一次性基线提交（A/B 两组）；开工时若 `git status --porcelain` 仍有未提交的产品改动，**停止并报告**，不得在脏基线上交付。

Stop

只在 Allowed Files 内修改。创建 handoff（`reports/agent-runs/2026-08-06-asset-transfer-live-v1/evidence/asset-transfer-live-t1-backend.handoff.md`），用其 Human Brief 生成合规 `[TASK_RESULT v2]`；将本任务 `current_task.state` 标为 `reported`。在一个 delivery commit 中提交允许的代码、测试、测试输出、status 与 handoff；handoff 的 `delivery_sha` 写 `pending`（或已知的 `git rev-parse` 值）。不得自行启动 T2、Reviewer、Bookkeeper，不得合并、部署或执行任何实盘/网络/凭据/下单操作。

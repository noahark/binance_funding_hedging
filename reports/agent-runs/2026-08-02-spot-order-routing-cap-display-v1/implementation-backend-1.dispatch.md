Identity:
- task_id: implementation-backend-1
- target_role: Implementer（Backend / HIGH_RISK）
- target_model: claude_glm
- provider: zhipu_glm
- status_revision: 4
- required_skill: agents/skills/senior-developer.md

Goal

实现已通过独立计划评审的后端部分：

1. 正费率现货 `BUY` 在每次预检中以新鲜的、仅带 API key 不签名的
   `GET /sapi/v1/margin/restricted-asset` 读取 `maxCollateralExceededAsset`；命中解析后的
   spot base asset 或 bStock 时走普通现货。负费率现货 `SELL` 不读该名单，始终保留 PAPI。
2. 普通现货 route 覆盖预检、标准 Spot 余额与限频、下单、按 client ID 查单、错误分类、
   endpoint 持久化与 reconciliation；合约腿始终 PAPI UM。`hedge_open_leg.endpoint` 是唯一
   查询权威。普通现货无 `sideEffectType`，且不得新增数据库迁移。
3. 保留 HedgeOpenLiveClient 的 deny-by-default 机制，将下列 exact 路径硬绑定
   `https://api.binance.com`：
   `("GET", "/sapi/v1/margin/restricted-asset")`、
   `("POST", "/api/v3/order")`、`("GET", "/api/v3/order")`、
   `("GET", "/api/v3/account")`、`("GET", "/api/v3/rateLimit/order")`。
   未登记路径必须在发出请求前被拒绝；不得让调用方传入 host。
4. 在现有 SnapshotService 缓存节奏内读取同一名单，发射独立
   `collateral_cap: { exceeded: true|false|null, checked_at }` 与对应 `ui_flags`。命中判断仅用
   已解析现货 base asset（含 bStock B-suffix），不使用合约 `base_asset`；展示高亮不按费率方向
   过滤。展示缓存绝不得被预检读取；失败必须发射未知（`exceeded: null`），不能伪装成未满。
5. 按方案 §7 写入公共快照契约 v0.9 amendment、schema 与后端测试。解除 no-key 限制后保留
   三条闸门；`margin_public.source` 的原因改为本轮未采用，而非禁止使用 key。

Allowed Files

- `backend/domain/normalize.py`
- `backend/domain/snapshot.py`
- `backend/services/hedge_open_live_client.py`
- `backend/services/hedge_preflight_provider.py`
- `backend/services/live_hedge_executor.py`
- `backend/services/snapshot_service.py`
- `backend/hedge_open_tasks/domain.py`
- `backend/hedge_open_tasks/service.py`
- `backend/hedge_open_tasks/store.py`
- `backend/app/server.py`
- `docs/api/public-market-contract.md`
- `schemas/api/public-market/snapshot.schema.json`
- `backend/tests/test_hedge_domain.py`
- `backend/tests/test_hedge_open_live_client.py`
- `backend/tests/test_hedge_preflight_provider.py`
- `backend/tests/test_live_hedge_executor.py`
- `backend/tests/test_hedge_service.py`
- `backend/tests/test_hedge_store.py`
- `backend/tests/test_snapshot.py`
- `backend/tests/test_background_worker.py`
- `backend/tests/test_symbol_snapshot_endpoint.py`
- `backend/tests/test_negative_schema.py`
- `backend/tests/test_service_health.py`

Inputs

- `AGENTS.md`
- `agents/developer-discipline.md`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/status.json`
- `PROJECT_STATE.md`
- `docs/planning/spot-order-routing-v1.md`（唯一详细设计）
- `docs/planning/2026-08-02-decisions-routing-and-cap-display.md`（§D、§E 为已定 Human 裁定）
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/evidence/plan-review-2.deepseek.raw.md`
- `reports/api-samples/2026-08-spot-order-routing-v1/`（只读 API 侦察证据）
- 仅为执行本任务读取上述模块直接依赖的源文件、现有对应测试与 schema 引用。

Acceptance Checks

- 一处共享的纯函数解析实际 spot symbol/base asset；预检与行情展示共同调用，普通币与 bStock
  都按实际 spot base asset 匹配。
- fake transport 覆盖正费率命中名单/bStock → 普通现货，未命中非 bStock → PAPI，负费率
  命中名单/bStock → PAPI 且不请求名单；名单读失败或普通现货余额/限频不足 → 零 attempt、零 POST。
- 普通现货 POST/GET 使用 `api.binance.com`、独立 `PRODUCT_SPOT`、无 `sideEffectType`；不确定
  POST 与后台 reconciliation 都从 leg 行 endpoint/symbol 查单。PAPI UM 合约腿不变。
- allowlist 的五条新增路径均固定到 `api.binance.com`，未登记 `(method, path)` 在 transport 前
  被拒；`restricted-asset` 读取不签名且不读取/存储 `openLongRestrictedAsset`。
- 预检每次新读名单，不消费展示缓存；展示成功命中/未命中/失败分别为已满/未满（有 checked_at）/
  未知，行级命中不按 funding 正负过滤。
- snapshot 输出通过 JSON schema 验证；契约 v0.9 明确三条带 key 闸门、字段、三态与
  `margin_public.source` 更正。现有公共接口和 Start gate 不变。
- 运行并记录：
  `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider backend/tests/test_hedge_domain.py backend/tests/test_hedge_open_live_client.py backend/tests/test_hedge_preflight_provider.py backend/tests/test_live_hedge_executor.py backend/tests/test_hedge_service.py backend/tests/test_hedge_store.py backend/tests/test_snapshot.py backend/tests/test_background_worker.py backend/tests/test_symbol_snapshot_endpoint.py backend/tests/test_negative_schema.py backend/tests/test_service_health.py -q`
  以及 `git diff --check`。
- 将仅上述 Allowed Files 中的交付改动做成一个本地提交，并在 `[TASK_RESULT v2]` 中报告提交 SHA、
  测试结果与实际改动文件。不得自行改 `status.json` 以外的 stage 状态。

Stop

- 不得调用 Binance、读取/展示凭证、启动服务、执行真实 POST、变更 Start gate、部署、合并或推送。
- 不得修改前端、fixture、阶段记录、PROJECT_STATE、路由之外的订单逻辑或任何未列文件；边界不足即
  停止报告。完成实现、测试与本地提交后停止，由 Human 将原始回执交回 Bookkeeper。

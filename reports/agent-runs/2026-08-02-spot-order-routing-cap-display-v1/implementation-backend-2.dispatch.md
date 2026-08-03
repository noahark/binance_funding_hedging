Identity:
- task_id: implementation-backend-2
- target_role: Implementer（Backend / HIGH_RISK）
- target_model: claude_glm
- provider: zhipu_glm
- status_revision: 8
- required_skill: agents/skills/senior-developer.md

Goal

实现已通过独立计划评审的**后端全部范围**（下单路由 A + 行情展示 B 的后端侧），并交付一个
可供前端消费的**固定本地提交**。本任务是本 stage 两个实现任务中的第一个；
`implementation-frontend-1`（Grok）只做静态 UI，且必须在你的提交被 Bookkeeper 固定 SHA 之后
才启动，它消费的是**你写入 `docs/api/public-market-contract.md` 的 v0.9 amendment**。

1. **路由方向**：正费率现货 `BUY` 在**每次预检**中新鲜读取
   `GET /sapi/v1/margin/restricted-asset`（只带 `X-MBX-APIKEY`、不签名、无参数），取
   `maxCollateralExceededAsset`；命中**已解析现货 base asset** → `regular_spot`
   （reason `collateral_cap_precheck`），否则 `TRADIFI_PERPETUAL` → `regular_spot`
   （reason `tradifi_regular_spot`），否则 `papi_margin`（reason `papi_default`）。
   **负费率现货 `SELL` 不读该名单、不选 `regular_spot`**，即使命中名单或为 bStock 也保留既有
   PAPI 路径。读取失败 / API-key 失败 / 限频 / 结构异常 / 缺任一所需账户读数 → 统一
   `preflight_incomplete`：零 attempt、零 POST，且预检原因能区分「普通现货余额不足」与
   「限频/读取失败」。不得因读取失败猜测路径。
2. **普通现货 route 闭环**：标准 Spot 余额与限频读数、下单、按 client ID 查单、独立
   `PRODUCT_SPOT` 错误分类、endpoint 持久化与后台 reconciliation。普通现货请求**不发送**
   `sideEffectType`，PAPI 现货保留它；合约腿始终 `papi.binance.com` `/papi/v1/um/order` 不变。
   `hedge_open_leg.endpoint` 是查单与原始响应记录的**唯一权威**，绝不得由 leg 名称或任务级
   route 反推。历史缺字段的 attempt 兼容为既有 `papi_margin`。**不新增数据库迁移**
   （`preflight_fingerprint` 与 `endpoint` 已足够）。
3. **Binance client**：保留 `HedgeOpenLiveClient` 的 deny-by-default 机制，新增下列 exact
   `(method, path)` 并硬绑定 `https://api.binance.com`：
   `("GET", "/sapi/v1/margin/restricted-asset")`、`("POST", "/api/v3/order")`、
   `("GET", "/api/v3/order")`、`("GET", "/api/v3/account")`、`("GET", "/api/v3/rateLimit/order")`。
   未登记路径必须在发出请求前被拒；host 不得由调用方传入或覆盖。
4. **SnapshotService（展示侧）**：在**已有**的三档业务缓存节奏内（建议 `GROUP_B_REFRESH_SECONDS`
   档、独立 `source_id`、独立 due 时间戳，遵循既有「只有成功才写缓存并推进时间戳」纪律）读取
   同一名单，按 `implementation-interface-v0.9.md` §2/§3/§4 发射
   `rows[].collateral_cap: { exceeded, asset, checked_at }` 与 `ui_flags`
   `COLLATERAL_CAP_EXCEEDED` / `COLLATERAL_CAP_UNKNOWN`。命中判定**只用已解析现货 base asset**
   （bStock 走 B-suffix 得 `TSLAB`），不用行顶层合约 `base_asset`；**不按费率正负过滤**。
   展示读取也必须经第 3 条的 allowlist。应用组合根使用已有 hedge API key 创建只读 client 并注入
   SnapshotService，**独立于** `APP_HEDGE_EXECUTOR` 与 private channel；创建 client 不发请求、不改变
   Start gate，SnapshotService 只可调用名单 GET。**展示缓存绝不得被预检读取，预检结果也不得回填
   展示缓存**；任意展示读取失败都必须发射未知（`exceeded: null`），即使此前有 last-good，也不得
   伪装成已满或未满。离线或 hedge API key 缺失/失效时全表未知；不新增开关或环境变量。
5. **契约与 schema**：按方案 §7 写入 `docs/api/public-market-contract.md` 的 **v0.9 amendment**
   段落（沿用 v0.8 段落形状）与 snapshot schema 字段。no-key 限制**换成三条闸门**而非仅删除：
   后端可用带 key 接口/浏览器仍从不直接调币安、默认只限 `MARKET_DATA` 类、每新增带 key 数据源
   须 Human 显式授权并记录在该 stage 内；`margin_public.source = "unverified"` 的原因文字从
   「Phase 1 禁 key」更正为「本轮未采用」。`schema_version` 保持 `public-market-snapshot/v1`，
   全部改动 additive。

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
- `backend/tests/test_hedge_api.py`
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
- `docs/planning/spot-order-routing-v1.md`（唯一详细产品设计）
- `docs/planning/2026-08-02-decisions-routing-and-cap-display.md`（§D、§E 为已定 Human 裁定）
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/implementation-interface-v0.9.md`
  （**接口约定；`collateral_cap` 形状、三态真值表、flag 值、匹配口径、缓存边界以它为准**）
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/task-breakdown-1.md`（顺序与边界）
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/evidence/plan-review-2.deepseek.raw.md`
- `reports/api-samples/2026-08-spot-order-routing-v1/`（只读 API 侦察证据）
- 仅为执行本任务读取上述模块直接依赖的源文件、现有对应测试与 schema 引用。

Acceptance Checks

- **匹配单点**：解析实际现货 symbol / base asset 的纯函数只有**一处**实现，预检路由与展示标记
  都调用它；普通币精确匹配、bStock 判定用 `TSLAB` 而非 `TSLA`；名单精确匹配（不归一化、不剥离
  倍率前缀）；`openLongRestrictedAsset` 不读不存。
- **路由（fake transport）**：正费率命中名单 → `regular_spot`/`collateral_cap_precheck`；正费率
  bStock → `regular_spot`/`tradifi_regular_spot`；正费率未命中非 bStock → `papi_margin`；
  **负费率命中名单或 bStock → `papi_margin` 且请求记录中不存在 restricted-asset 调用**；
  名单读失败 / 普通现货 USDT 不足 / 普通现货限频或账户读数失败 → 零 attempt、零 POST，
  且「余额不足」与「限频/读取失败」原因可区分。
- **执行与审计**：普通现货 POST/GET 走 `api.binance.com`、独立 `PRODUCT_SPOT`、无
  `sideEffectType`；POST 不确定时的首查与后台 reconciliation 都从 **leg 行**的 endpoint/symbol
  查单；PAPI UM 合约腿不变；PAPI 现货 `51169` 不产生任何普通现货补单。
- **allowlist 审计**：五条新增路径全部登记且硬绑定 `api.binance.com`；未登记 `(method, path)`
  在 transport 前被拒；`restricted-asset` 请求不带签名/`timestamp`/`recvWindow`，只带
  `X-MBX-APIKEY`；预检与展示两条读取都受该 allowlist 管控。
- **缓存隔离（必须有专门测试）**：展示缓存标记为「已满」而预检新读为「未满」时，路由按新读
  结果走；预检路径不持有/不读取 SnapshotService 名单缓存，预检结果不回填展示缓存。
- **三态与不适用**：命中 → `exceeded=true` + `COLLATERAL_CAP_EXCEEDED`；成功未命中 →
  `exceeded=false` + 无抵押额度 flag + 非空 `checked_at`；任意展示读取失败 → `exceeded=null`、
  `checked_at=null` + `COLLATERAL_CAP_UNKNOWN`；无可解析现货腿 → `exceeded=null`、`asset=null`
  且**无**抵押额度 flag（`checked_at` 仍与全表全局读数相同）。四字段组合一致性有测试锁定，
  表外组合不可能被发射。
- **失败覆盖输出**：先成功后失败的刷新序列中，展示必须变为未知并清空输出 `checked_at`；内部
  last-good 只能服务后续刷新重试，不能投影到页面。
- **组合根只读注入**：即使 `APP_HEDGE_EXECUTOR != live`，应用组合根也以已有 hedge API key
  构造并向 SnapshotService 注入受限 client；fake transport 证明该展示路径只发
  `GET /sapi/v1/margin/restricted-asset`，不发任何订单 POST、不改变 Start gate。
- **不按方向过滤**：同一命中资产的正费率行与负费率行都带 `COLLATERAL_CAP_EXCEEDED`。
- **契约与 schema**：新 snapshot 通过 JSON schema 校验；**不含 `collateral_cap` 键的既有冻结
  样本仍校验通过**；`symbol-snapshot` 经共享 row `$ref` 自动继承且该 schema 文件未被改动；
  v0.9 amendment 含三条带 key 闸门、字段定义、三态、`margin_public.source` 原因更正；
  `summary`/`warnings`/`schema_version` 未变；现有公共接口与 Start gate 不变；无数据库迁移。
- 运行并记录：
  `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider backend/tests/test_hedge_domain.py backend/tests/test_hedge_open_live_client.py backend/tests/test_hedge_preflight_provider.py backend/tests/test_live_hedge_executor.py backend/tests/test_hedge_service.py backend/tests/test_hedge_store.py backend/tests/test_hedge_api.py backend/tests/test_snapshot.py backend/tests/test_background_worker.py backend/tests/test_symbol_snapshot_endpoint.py backend/tests/test_negative_schema.py backend/tests/test_service_health.py -q`
  以及 `git diff --check`。
- 将仅上述 Allowed Files 中的交付改动做成**一个本地提交**，并在 `[TASK_RESULT v2]` 中报告
  **提交 SHA**、测试结果与实际改动文件清单。该 SHA 是前端任务的启动前提，务必显式给出。

Stop

- 不得调用 Binance、读取/展示凭证、启动服务、执行真实 POST、变更 Start gate、部署、合并或推送。
- 不得修改任何前端文件（`frontend/**`）、`backend/tests/fixtures/**`、阶段记录、`PROJECT_STATE.md`、
  `backend/config.py` 或未列出的任何文件。若发现必须改 `backend/config.py`、新增文件或新增环境
  变量，**停止并报告边界不足**，不得自行扩大。
- 不得改写已 ACCEPT 的产品边界；接口形状与 `implementation-interface-v0.9.md` 冲突时停止并报告。
- 完成实现、测试与本地提交后停止，由 Human 将原始回执交回 Bookkeeper。本任务不授权实盘、
  不授权开闸、不授权启动任何后续模型终端。

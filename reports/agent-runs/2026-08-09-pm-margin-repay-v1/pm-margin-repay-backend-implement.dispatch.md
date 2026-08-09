# Dispatch: pm-margin-repay-backend-implement

## Identity

- task_id: `pm-margin-repay-backend-implement`
- target_role: `Implementer`
- target_model: `claude_glm`
- provider: `zhipu_glm`
- status_revision: `2`
- required_skill: `agents/skills/senior-developer.md`

## Goal

只实现统一账户全仓杠杆还款 v1 的后端与本地审计：新增默认关闭的
`APP_MARGIN_REPAY_ENABLED`，在开启且凭证可用时提供本地
`POST /api/margin-repay` 和纯本地 `GET /api/margin-repay?client_request_id=<UUID>`，
one-shot 调用币安 `POST /papi/v1/margin/repay-debt`，固定
`specifyRepayAssets=USDT`，并用 SQLite 唯一请求号和四态记录防止重复还款。

本任务不改前端和公共文档，不部署、不启动服务、不读取真实凭证、不打开还款闸门、
不调用真实币安接口。

## Allowed Files

仅可修改或新增：

- `backend/config.py`
- `backend/margin_repay/__init__.py`（新增）
- `backend/margin_repay/store.py`（新增）
- `backend/services/hedge_open_live_client.py`
- `backend/app/server.py`
- `backend/tests/test_config.py`
- `backend/tests/test_hedge_open_live_client.py`
- `backend/tests/test_margin_repay.py`（新增）
- `reports/agent-runs/2026-08-09-pm-margin-repay-v1/status.json`，且只允许把自己的
  `current_task.state` 从 `dispatched` 改为 `reported`，其他字段不得修改
- `reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-backend-implement.handoff.md`
  （create-only，任务结束时创建）

Bookkeeper 前置检查：

`test ! -e reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-backend-implement.handoff.md`

结果为 `PASS`。若执行时该路径已存在，立即 `blocked`，不得覆盖。保留工作树中任何不在
上述清单的 Human/其他终端改动；边界不足时停止报告，不得扩文件。

允许在完成全部检查后创建一笔仅含上述文件的 delivery commit；handoff 中
`delivery_sha` 写 `pending`，由 Bookkeeper 从实际提交解析。不得 push、merge、部署、重启
服务或启动下一模型。

## Inputs

按顺序读取，读取到满足任务即可，不扫描历史 stage：

1. `AGENTS.md`
2. 本 dispatch
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-09-pm-margin-repay-v1/status.json`
6. `agents/roles.md` 的 Shared Rules、Task Handoff Evidence Contract、Implementer 章节
7. `agents/developer-discipline.md`
8. `agents/skills/senior-developer.md`（本任务唯一 skill）
9. `reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-plan-review.handoff.md`
10. `reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-plan.md`
11. `backend/config.py` 中现有布尔环境配置模式
12. `backend/asset_transfer/store.py`
13. `backend/app/server.py` 中资产划转的请求校验、POST handler、GET/POST 路由和运行时注入
14. `backend/services/hedge_open_live_client.py` 中 allowlist、签名 POST 和
    `universal_transfer`
15. `backend/tests/test_asset_transfer.py`、`backend/tests/test_config.py`、
    `backend/tests/test_hedge_open_live_client.py`、`backend/tests/test_service_health.py`
16. 币安官方契约：
    <https://developers.binance.com/zh-CN/docs/catalog/advanced-trading-derivatives-trading-portfolio-margin/api/rest-api/trade#margin-account-repay-debt>

不得读取 `.env`、打印环境变量、访问账户、启动本地服务或发网络请求。复用资产划转的
局部模式，但不要抽象通用资金操作框架。

## Acceptance Checks

1. **默认关闭与注入 fail closed**：`APP_MARGIN_REPAY_ENABLED` 沿用现有布尔配置解析，
   缺省为 false；只有显式开启、`offline=false` 且还款所需 key/secret 均存在时才注入
   client，否则 POST 返回 503 且零上游。启动提示清楚区分启用/未启用且不泄露凭证；
   不受 `APP_HEDGE_EXECUTOR` 控制。
2. **交易所出口唯一且固定**：allowlist 只新增
   `("POST", "/papi/v1/margin/repay-debt") -> https://papi.binance.com`；client 方法
   one-shot 使用既有签名 form POST，只接收负债资产和可选 amount，内部始终添加
   `specifyRepayAssets=USDT`。禁止 `/papi/v1/repayLoan`、重试和可注入 host/path/偿还资产。
3. **金额与请求校验**：本地 POST 只接受 JSON 对象中的 UUID、非空资产、普通无符号
   十进制字符串 amount 和严格 `confirm is true`。只有精确字符串 `"0"` 表示全部并在
   币安请求中完全省略 `amount`；`0.0`、`0.00`、负数、科学计数法、空白和非字符串均
   拒绝。正数按原始字符串透传且全程不用 float。客户端提交 `specifyRepayAssets` 或
   其他偿还资产字段必须被拒绝。
4. **借款资产白名单**：asset 必须精确命中当前统一账户快照中
   `cross_margin_borrowed > 0` 的资产；快照未就绪返回 503，未借款或未知资产返回 400，
   两类都零上游。不用缓存负债额或价格预判部分还款数量/50,000 USD 上限。
5. **本地幂等审计**：新增独立 SQLite 表/Store，以 `client_request_id` 为主键，金额存
   TEXT，先短事务写 pending、释放锁后外发、再短事务 resolve；重复或并发同 UUID 只
   回放第一笔记录，不二次外发。记录至少包含请求号、负债资产、请求 amount、固定 USDT、
   status、可信的实际还款 amount/updateTime、错误 code/message 和微秒时间；不得记录
   key、secret、signature 或签名 payload。
6. **严格四态**：仅 HTTP 200 + JSON 对象 + `success is True` + 响应 asset 与请求一致
   归 `succeeded`；明确普通 4xx 拒绝归 `failed`；网络/超时/无 HTTP、408、418、429、
   5xx、非 JSON、200 缺字段/字段矛盾/`success` 不严格为 true 均归 `unknown`。任何
   上游结果都落终态，不自动重试，不把 HTTP 200 本身当成功。
7. **纯本地恢复 GET**：GET 只接收一个合法 UUID，查询 SQLite，存在返回记录、不存在
   404、非法/缺失/重复参数 400；不得调用快照或币安。POST 的业务四态沿用资产划转模式
   返回 HTTP 200，只有请求校验/通道问题使用 4xx/503。
8. **回归与证据**：新增测试覆盖 `0` 省略 amount、正数原样、固定 USDT、默认关闸、
   allowlist/签名 POST、白名单、幂等并发、GET 零上游和四态全集；保持资产划转与服务
   健康测试通过。测试只能使用 fake client、临时 SQLite 和离线配置。

必须依次运行并在 handoff 记录原始命令与结论：

```text
python3 -m pytest -q backend/tests/test_config.py backend/tests/test_hedge_open_live_client.py backend/tests/test_margin_repay.py backend/tests/test_asset_transfer.py backend/tests/test_service_health.py
python3 -m pytest -q backend/tests
git diff --check
```

若全套后端测试出现与本任务无关的既有失败，不得修改范围外文件；保存完整失败节点和最小
复现命令，返回 `blocked` 或 `failed`，不得把失败写成 pass。

## Stop

完成后按 Task Handoff Evidence Contract 创建唯一 handoff，列清实际改动、未完成项、
测试命令/结果、`base_sha`、`delivery_sha: pending`、下一任务必须读取的具体路径和 Human
Brief；把 `status.json.current_task.state` 仅改为 `reported`，创建一笔 delivery commit，
然后输出与 Human Brief 完全一致的 `[TASK_RESULT v2]` 并停止。

不得修改前端或 docs，不得实盘测试、部署、开闸、读取凭证、push、启动 Reviewer/T2 或
宣称交付已接受。若任一资金语义不确定，fail closed 并在 handoff 具名阻塞。

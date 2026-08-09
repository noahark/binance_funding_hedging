# Task Handoff: pm-margin-repay-backend-implement

## Source Report (author-only; immutable after task end)

- task_id: `pm-margin-repay-backend-implement`
- role: `Implementer`
- target model: `claude_glm`（provider `zhipu_glm`）
- stage_id: `2026-08-09-pm-margin-repay-v1`
- created_at: `2026-08-09 23:10:10 CST`
- base_sha: `ee0d5320b319a5bacc708eb8680e8156328db338`
- delivery_sha: `pending`（由 Bookkeeper 从 delivery commit 解析；见下「Delivery 范围」）
- status_revision: `2`
- required_skill: `agents/skills/senior-developer.md`

### 任务背景与实际改动范围

实现统一账户全仓杠杆还款 v1 的后端与本地审计：默认关闭的 `APP_MARGIN_REPAY_ENABLED`、
本地 `POST /api/margin-repay` 与纯本地 `GET /api/margin-repay?client_request_id=<UUID>`、
one-shot 调用币安 `POST /papi/v1/margin/repay-debt`（固定 `specifyRepayAssets=USDT`）、
独立 SQLite 唯一请求号 + 四态记录防重复还款。全程离线、未读凭证、未触实盘、未部署、未开闸。

复用资产划转（`asset_transfer`）的局部模式（store/handler/dispatch/分类），**未**抽象通用资金框架。
未改前端、未改公共文档、未改开单/平单/借款/划转/仓位/风险参数。

改动文件（全部为本任务产物，工作树无其他 Human/终端改动）：

| 文件 | 性质 | 说明 |
|---|---|---|
| `backend/config.py` | 修改 | 新增 `margin_repay_enabled: bool = False`，`from_env` 解析 `APP_MARGIN_REPAY_ENABLED`/`FUNDING_HEDGING_MARGIN_REPAY_ENABLED`（沿用 `_env_bool`），默认 false。复用 hedge 凭证，不加新凭证字段。 |
| `backend/margin_repay/__init__.py` | 新增 | 包 docstring（仅存储层；外发在 server handler，本体复用 `HedgeOpenLiveClient.repay_margin_debt`）。 |
| `backend/margin_repay/store.py` | 新增 | `margin_repay` 表（`client_request_id` PK / `asset` / `amount` TEXT / `repay_asset` / `status` / `repaid_amount` TEXT / `update_time` TEXT / `error_code` / `error_message` / `created_at_us` / `updated_at_us`）；`begin/resolve/get`；金额 TEXT、微秒时间、单连接+RLock、外发不在持锁期；不记 key/secret/signature。 |
| `backend/services/hedge_open_live_client.py` | 修改 | ALLOWLIST 新增 `("POST","/papi/v1/margin/repay-debt")->papi.binance.com`；新增 `MARGIN_REPAY_DEBT_PATH`/`REPAY_SPECIFY_ASSET="USDT"` 常量与 `repay_margin_debt(asset, amount, *, timestamp_ms, recv_window_ms=None)`：内部固定 `specifyRepayAssets=USDT`，`amount=None` 省略 amount（全部），非空透传；one-shot 签名 POST；签名不接受也不暴露偿还资产/host/path。 |
| `backend/app/server.py` | 修改 | 导入 `MarginRepayStore`；`_REPAY_*` 常量与 `_parse_margin_repay_request`（UUID/复用划转的无符号十进制形状正则/精确 `"0"`=全部/正数原样/拒绝 `0.0`·`00`·科学计数法·非字符串·偿还资产字段与任何未知字段）；`_handle_margin_repay_post`（闸门 503→校验→白名单 `cross_margin_borrowed>0`→begin 幂等→`_dispatch_margin_repay` 四态→resolve，业务结论一律 HTTP 200）；`_handle_margin_repay_get`（纯本地，单一 UUID，存在 200/缺失 404/非法·缺失·重复参数 400，零上游）；`_margin_repay_borrowed_assets`；do_GET/do_POST 路由；`_build_margin_repay_client`（`enabled and not offline and key and secret` 才注入，否则 None→POST 503 零上游，不受 `APP_HEDGE_EXECUTOR` 控制）；`run()` 注入 store（总注入，GET 恢复零上游）+ client + 启用/未启用两分支启动提示（不泄露凭证）。 |
| `backend/tests/test_config.py` | 修改 | 还款闸门默认关/覆盖/别名/非法布尔。 |
| `backend/tests/test_hedge_open_live_client.py` | 修改 | allowlist 精确路径 + `repay_margin_debt`（`None` 省略 amount、正数透传、固定单一 USDT、签名在最后、one-shot）。 |
| `backend/tests/test_margin_repay.py` | 新增 | 0 省略、正数透传、固定 USDT、白名单（borrowed>0）、幂等顺序+并发、GET 零上游、四态全集（200 严格成功/asset 一致/success 严格 true、明确 4xx failed、408·418·429·5xx·transport unknown）、请求校验全集（含 `0.0`/`00`/科学计数法/偿还资产字段/未知字段拒绝）、存储层红线。全离线 fake client + 临时 SQLite。 |
| `backend/tests/test_hedge_purity.py` | 修改（**Human 授权扩入范围**，见下「边界裁决与授权」） | 冻结白名单守卫机械更新：`_FROZEN_ALLOWLIST`/`_PAPI_KEYS` 加 `repay-debt` 条目，`len(ALLOWLIST) 15→16`、`len(_PAPI_KEYS) 9→10`、注释更新。 |

### 边界裁决与授权（test_hedge_purity.py）

验收检查 2 要求新增 `repay-debt` 白名单条目，必然把 `backend/tests/test_hedge_purity.py`
的冻结白名单防扩散守卫从 15 条撑到 16 条（PAPI 键 9→10）而失败。该文件**不在** dispatch 的
Allowed Files。本书keeper 前置 `test ! -e <handoff>` 为 PASS；工作树无其他终端改动。

按 `AGENTS.md` §3.3 与 dispatch「边界不足时停止报告，不得扩文件」「delivery commit 仅含上述文件」，
模型不得自扩 Safety Kernel 文件边界。本书implementer 已向 Human（本终端操作者）具名该越界守卫
与最小机械修法（镜像同文件已记录的 `/papi/v1/um/leverage` 先例：加 1 条目 + 计数 + 注释）。

**Human 2026-08-09 明确授权**（§10：Human 为范围与风险授权的最高决定者；dispatch 文件清单约束
*模型*自扩，不约束 *Human* 授权）：把 `backend/tests/test_hedge_purity.py` 加入本任务范围，做该
最小守卫更新以完成 T1。本授权仅限本次合并所需的最小机械守卫更新（使冻结集合如实反映 dispatch
已批准的第 16 个端点）；不改变守卫语义、不放宽防扩散逻辑、不涉资金/实盘/部署/开闸。Bookkeeper
封存时可据此把该文件视为本次授权范围的一部分。

### 命令与结果（dispatch Acceptance Checks 末尾三命令，原始记录）

```text
python3 -m pytest -q backend/tests/test_config.py backend/tests/test_hedge_open_live_client.py backend/tests/test_margin_repay.py backend/tests/test_asset_transfer.py backend/tests/test_service_health.py
=> 181 passed in 57.73s   （守卫更新前即已全过；更新后重跑同结果）

python3 -m pytest -q backend/tests
=> 守卫更新前：1 failed (test_allowlist_is_exactly_the_frozen_allowlist), 1676 passed
=> 守卫更新后：1677 passed in 154.60s (0:02:34)

git diff --check
=> 干净，exit 0
```

最小复现（守卫更新前的失败节点，仅供 Bookkeeper 核验授权修法）：

```text
python3 -m pytest -q backend/tests/test_hedge_purity.py::test_allowlist_is_exactly_the_frozen_allowlist
```

### 未完成事项

- 无。8 项验收检查全部满足；`delivery_sha` 由 Bookkeeper 解析。
- 明确不做（非目标 / 后续关卡）：前端接线、公共文档同步、部署、开启 `APP_MARGIN_REPAY_ENABLED`、
  真实币安还款、凭证读取——均不在本阶段授权内。

### 不能假设的事实（供下一任务）

- 本交付**未**部署、**未**开闸（`APP_MARGIN_REPAY_ENABLED` 默认 false）、**未**触真实币安。
- 币安 `repay-debt` 无客户端幂等键、无按本地请求号查结果的公开接口；幂等仅靠本地 `client_request_id`。
- 跨资产转换价格/手续费/滑点未知；同币资产仍优先于 `specifyRepayAssets=USDT`。
- 复用 hedge API 凭证（PAPI TRADE，与开单同 key）；`repay-debt` weight 3000。
- 当前服务仍以手动前台进程运行；本交付合入并重启前，运行中服务无还款能力。

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-backend-implement.handoff.md`
  2. `reports/agent-runs/2026-08-09-pm-margin-repay-v1/status.json`
  3. `reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-plan.md`
  4. `reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-plan-review.handoff.md`
- 执行：Bookkeeper 核验本 handoff、解析 `base_sha..delivery_sha` 范围、确认 Human 授权的
  `test_hedge_purity.py` 守卫更新、把 `current_task.state` 由 `reported` 推进为 `verified`，
  再准备 review-1 dispatch（HIGH_RISK：repayment/资金含义，须跨 provider 只读评审）。
- 关卡：T1 经 Bookkeeper 核验前不得派发前端 T2；任何部署、开启 `APP_MARGIN_REPAY_ENABLED`、
  真实币安还款仍须 Human 单独授权；review-2 ACCEPT 只交 Human 决策，不授权合并/部署/开闸/实盘。
- 不能假设的事实：本 ACCEPT-free 实现交付须经 review-1（代码/契约/测试/接缝）+ 独立 review-2
  （真实效果/操作风险/发布准备）双评审；`specifyRepayAssets=USDT` 首版固定，同币资产仍优先。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

```text
[TASK_RESULT v2]
任务 ID: pm-margin-repay-backend-implement
执行结果: completed（完成）
结果摘要: T1 完成：默认关闭 APP_MARGIN_REPAY_ENABLED + 本地 POST/GET /api/margin-repay + 独立 SQLite 幂等审计 + one-shot repay-debt（固定 USDT）+ 严格四态。定向 181、全套 1677 测试全过，git diff --check 干净；未触凭证/实盘/部署/开闸。test_hedge_purity.py 经 Human 授权做最小守卫更新（白名单 16 条）。
产物: [reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-backend-implement.handoff.md, backend/config.py, backend/margin_repay/__init__.py, backend/margin_repay/store.py, backend/services/hedge_open_live_client.py, backend/app/server.py, backend/tests/test_config.py, backend/tests/test_hedge_open_live_client.py, backend/tests/test_margin_repay.py, backend/tests/test_hedge_purity.py]
检查结果: [1.默认关闭+fail-closed注入(offline/key/secret/独立闸门不受HEDGE_EXECUTOR控制) pass；2.出口唯一固定(allowlist仅repay-debt→papi、固定USDT、禁repayLoan与重试与注入) pass；3.金额与请求校验(0省略/正数透传/拒0.0·00·科学计数法·偿还资产字段·未知字段) pass；4.借款资产白名单(cross_margin_borrowed>0、快照未就绪503、未借/未知400、零上游) pass；5.本地幂等审计(独立表/UUID主键/短事务/不记密钥签名) pass；6.严格四态(200严格成功+asset一致、明确4xx failed、408·418·429·5xx·transport·非JSON·矛盾 unknown、不重试) pass；7.纯本地GET(单一UUID、存在200/缺失404/非法400、零上游) pass；8.回归与证据(定向181+全套1677全过、git diff --check干净、仅fake client+临时SQLite+离线配置) pass]
阻塞项: [none]
本地北京时间: 2026-08-09 23:10:10 CST
下一步模型: codex（Bookkeeper；核验本 handoff 与 delivery 范围）
下一步任务: 读取：reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-backend-implement.handoff.md、reports/agent-runs/2026-08-09-pm-margin-repay-v1/status.json、reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-plan.md、reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-plan-review.handoff.md；执行：Bookkeeper 核验本 handoff、解析 base_sha..delivery_sha、确认 Human 授权的 test_hedge_purity.py 守卫更新并把 state 推进 verified，再准备 review-1 dispatch；关卡：T1 核验前不得派前端 T2，部署/开 APP_MARGIN_REPAY_ENABLED/真实还款仍须 Human 另授
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

（由 Bookkeeper 核验后追加：源区块 SHA-256、核验时间、核对的 status revision、通过或拒收依据、
可复现命令与后续状态。）

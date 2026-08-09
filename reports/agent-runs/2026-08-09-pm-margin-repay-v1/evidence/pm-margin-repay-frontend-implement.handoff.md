# Task Handoff: pm-margin-repay-frontend-implement

## Source Report (author-only; immutable after task end)

- task_id: `pm-margin-repay-frontend-implement`
- role: `Implementer`
- target model: `kimi`（provider `moonshot`）
- stage_id: `2026-08-09-pm-margin-repay-v1`
- created_at: `2026-08-10 00:09:59 CST`
- base_sha: `64bd81188a94a9e600c3e315ebaf1130d2a8a3b2`
- delivery_sha: `pending`（由 Bookkeeper 从 delivery commit 解析）
- status_revision: `3`
- required_skill: `agents/skills/senior-developer.md`

### 任务背景与实际改动范围

T2：把统一账户借款资产卡上已有的还款输入框/按钮接到 T1 已核验的本地后端
`POST /api/margin-repay` 与纯本地恢复 `GET /api/margin-repay?client_request_id=<UUID>`。
只做前端接线与文档，未改后端、未启动服务、未读凭证、未部署、未开
`APP_MARGIN_REPAY_ENABLED`、未调用真实币安接口。沿用现有单文件架构与划转局部模式，
未引入依赖或通用状态框架。

改动文件（全部在 dispatch Allowed Files 内；工作树无其他 Human/终端改动）：

| 文件 | 性质 | 说明 |
|---|---|---|
| `frontend/index.html` | 修改 | 新增 `MARGIN_REPAY_PENDING_STORAGE_KEY`；state 新增 `marginRepay{submitting,pending,results}`（pending 是 localStorage 未决记录的内存镜像，本身就是锁）；`onCacheRefresh` 补兼容 boolean（仅 complete 返回 true，既有按钮/提示/调用方行为不变）；新增还款函数组（`readRepayPendingStorage`/`setRepayPending`（持久化失败不外发）/`clearRepayPending`/`validateRepayAmount`（镜像后端 `^\d+(\.\d+)?$`，首尾空白不修剪，精确 `"0"`=全部，拒 `0.0`/`00`/负/科学计数法，不转 float）/`requestMarginRepayConfirm`（诚实二次确认）/`submitMarginRepay`（确认后才 `newTransferRequestId()`，先持久化再 POST，body 恰四字段）/`finalizeMarginRepaySuccess`（complete 才清记录解锁，否则留锁+再次刷新）/`recoverMarginRepay(All)`（同一 UUID 本地 GET 一次，不轮询；404/请求层错误不清 ID 不宣称未还款）/`acknowledgeRepayUnknown`（纯本地零请求）/`renderRepayStatus` 四态回显）；资产卡按钮加 submitting/未决双重禁用；`confirmMarketAction` 新增 `margin_repay` 分发；事件委托替换预览弹窗为真实确认流并新增 `data-repay-ack/recheck/refresh` 三按钮；启动调 `recoverMarginRepayAll()`；删除「后端尚未接入」旧预览文案与注释。 |
| `frontend/self-check.js` | 修改 | mock 新增 `marginRepayPostResponse`/`marginRepayGetResponse`/`marginRepayPostThrow`（传输错误注入）/`marginRepayPostPendingSnapshot`（POST 瞬间抓取 localStorage，为「发送前持久化」取证）；新增「统一账户还款 T2 接线」断言块（校验镜像后端/确认文案诚实/取消零请求/body 恰四字段原始字符串/同号持久化取证/成功强制刷新解锁/failed 结束/unknown 锁+人工核对/查询结果同号恢复/刷新失败留锁+再次刷新/传输错误留锁/GET404 不清 ID/启动恢复一次 GET/全局防连点/请求层失败撤销）；第 76 项白名单新增 `/api/margin-repay`（POST）与 `/api/margin-repay?`（GET）路径+方法规则、localStorage 键 `funding_hedging_margin_repay_pending`。 |
| `backend/tests/test_frontend_field_binding.py` | 修改 | 新增三条绑定测试：POST body 键集恰等于后端 `_REPAY_REQUIRED_FIELDS`（支持 shorthand 解析，含扫描失效守卫）；`renderRepayStatus` 消费的记录字段 ⊆ `MarginRepayStore` 真实记录键（本地标记 `request_error`/`transport_unknown`/`recovery_error`/`refresh_failed` 显式排除，引用数下限防正则失效）；违禁字符串（`specifyRepayAssets`/`repayLoan`/`papi.binance.com`/`binance.com`）在前端缺席。 |
| `docs/api/public-market-contract.md` | 修改 | 新增「Margin Repay Amendment (v0.17)」：冻结本地 POST/GET 请求响应、精确 `0` 语义（外发省略 amount）、固定 USDT 但同币优先、四态、SQLite 幂等、默认关闸、unknown/pending 人工核对、费用/滑点未知、前端确认/持久化/防连点/恢复/强制刷新解锁行为，并明确部署/开闸/真实还款不由本交付授权；同步 Status 行与 v0.13–v0.16 枚举、Backend API 段。「后端尚未接入」旧说法在前端代码内删除（契约文档从未含该说法，v0.17 取代预览状态）。 |
| `reports/agent-runs/2026-08-09-pm-margin-repay-v1/status.json` | 修改 | 仅 `current_task.state`：`dispatched`→`reported`，其他字段未动。 |

### 关键设计决定（对齐验收检查）

- 未决记录即锁：`pending` 镜像 + localStorage 双写，仅 failed、succeeded+complete 刷新、
  人工「我已核对」三条路径清除；传输错误/GET404/查询失败一律保留并锁定，绝不换号重发。
- 请求层错误分两类：带 HTTP status（4xx/503）= 后端外发前拒绝，钱没动，撤销未决；
  无 status（网络中断/响应丢失）= 结果未知，保留未决并锁定。
- `onCacheRefresh` 仅 complete 判 true（partial/not_attempted/202/错误均 false）——
  部分刷新可能仍留旧负债显示，不能解锁。
- 金额校验不修剪空白，严格镜像后端正则；发送的 amount 是用户输入原字符串。

### 命令与结果（dispatch 规定三命令，原始记录）

```text
node frontend/self-check.js
=> 全部自检通过，EXIT=0（含新增「统一账户还款 T2 接线」断言块 PASS；资产划转、
   任务日志、资产卡既有断言全部不回归）

python3 -m pytest -q backend/tests/test_frontend_field_binding.py
=> 10 passed in 0.09s，PYTEST_EXIT=0

git diff --check
=> 干净，DIFFCHECK_EXIT=0
```

测试全部离线自包含（mock fetch/localStorage、`:memory:` SQLite），未调用本地服务或真实后端。

### 未完成事项

- 无。8 项验收检查全部满足；`delivery_sha` 由 Bookkeeper 解析。
- 明确不做（非目标/后续关卡）：部署、开启 `APP_MARGIN_REPAY_ENABLED`、真实币安还款、
  凭证读取、合并 main——均须 Human 另行授权。

### 不能假设的事实（供下一任务）

- 本交付未部署、未开闸（运行中服务仍是手动前台进程，未加载还款代码）。
- 币安 repay-debt 无客户端幂等键、无按本地请求号查结果的公开接口；幂等仅靠本地
  `client_request_id`；跨资产转换价格/手续费/滑点未知，同币资产仍优先于 USDT。
- `onCacheRefresh` 的 boolean 是兼容补充：仅 complete 为 true；其他既有调用方忽略返回值。
- 前端金额校验不接受首尾空白（不修剪），比划转输入更严，与后端正则一致。

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-frontend-implement.handoff.md`
  2. `reports/agent-runs/2026-08-09-pm-margin-repay-v1/status.json`
  3. `reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-backend-implement.handoff.md`
- 执行：Bookkeeper 同文件核验本 handoff（源 SHA-256、身份、范围、三命令结论）、从
  delivery commit 解析 `delivery_sha`、把 `current_task.state` 推进 `verified`，封存完整
  delivery（`base_sha..delivery_sha` 含 T1+T2），再准备 review-1 dispatch（HIGH_RISK，
  跨 provider 只读评审）。
- 关卡：T2 核验前不得派 review-1；任何合并、部署、开启 `APP_MARGIN_REPAY_ENABLED`、
  真实还款仍须 Human 单独授权；review-2 ACCEPT 只交 Human 决策。
- 不能假设的事实：review 范围含本阶段自身控制提交（dispatch/status），它们是上下文
  而非受审交付；T1 的 `test_hedge_purity.py` 扩入是 Human 2026-08-09 明确授权（见 T1
  handoff 授权段与 Bookkeeper 核验记录）。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

```text
[TASK_RESULT v2]
任务 ID: pm-margin-repay-frontend-implement
执行结果: completed（完成）
结果摘要: T2 完成：还款控件已接本地 POST/GET /api/margin-repay——诚实二次确认、确认后才生成 UUID、发送前持久化请求号（POST 瞬间存储取证）、全局防连点、四态展示、纯本地恢复、unknown/pending 人工核对锁、成功后 complete 刷新才解锁。契约 v0.17 同步。self-check 全绿、字段绑定 10 过、diff --check 干净；未改后端/未部署/未开闸/未触实盘。
产物: [reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-frontend-implement.handoff.md, frontend/index.html, frontend/self-check.js, backend/tests/test_frontend_field_binding.py, docs/api/public-market-contract.md, reports/agent-runs/2026-08-09-pm-margin-repay-v1/status.json]
检查结果: [1.展示条件不漂移(控件仍只在已借>0出现、提示与已借/净价值规则不变、60s重渲染不清输入与未决) pass；2.输入校验与确认前零请求(精确"0"或正十进制、拒空白/0.0/00/负/科学计数法、取消零请求零请求号零记录) pass；3.确认文案诚实(负债资产+全部/指定数量、同币优先、USDT后备、费用滑点未披露、60s缓存滞后、无"只扣USDT") pass；4.请求体冻结(确认后才生成UUID、body恰四字段、原始amount、无specifyRepayAssets/repay asset/float/repayLoan/交易所URL、只认body.status) pass；5.发送前持久化+全局防连点(POST前同UUID落localStorage并经mock瞬间取证、提交期间全部按钮禁用、传输错误保留同一未决不换号重试) pass；6.纯本地恢复与四态(启动逐条GET一次不轮询、failed展示code/msg并结束、pending/unknown锁+人工核对解锁、GET404/请求层错误不清ID不宣称未还款、解锁纯本地零请求) pass；7.成功后先刷新再解锁(展示实际偿还资产/数量、complete才清记录解锁、partial/失败留锁+再次刷新/重载路径、onCacheRefresh补兼容boolean不改既有行为) pass；8.公共契约与回归(v0.17记录POST/GET/0语义/固定USDT同币优先/四态/幂等/默认关闸/人工核对/费用滑点未知/部署开闸真实还款未授权；self-check与字段绑定覆盖红线、既有断言不回归) pass]
阻塞项: [none]
本地北京时间: 2026-08-10 00:09:59 CST
下一步模型: codex（Bookkeeper；核验本 handoff 与完整 delivery）
下一步任务: 读取：reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-frontend-implement.handoff.md、reports/agent-runs/2026-08-09-pm-margin-repay-v1/status.json、reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-backend-implement.handoff.md；执行：Bookkeeper 同文件核验本 handoff、解析 delivery_sha、把 T2 state 推进 verified 并封存完整 delivery（含 T1+T2），再准备 review-1 dispatch（HIGH_RISK 跨 provider）；关卡：T2 核验前不得派 review-1，合并/部署/开 APP_MARGIN_REPAY_ENABLED/真实还款仍须 Human 单独授权
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

（由 Bookkeeper 核验后追加：源区块 SHA-256、核验时间、核对的 status revision、通过或
拒收依据、可复现命令与后续状态。）

## Errata (append-only)

（任何更正均追加，说明日期、作者、改动原因与不改变的事实；不得改写 Source Report 或
Human Brief。）

## Bookkeeper Verification (Bookkeeper append-only, actual)

- source_sha256: `757af6249dc1edf152f65756d6062eb4a6d07d7efeb21aa40df50018d544cecf`
- verified_at: `2026-08-10 00:17:09 CST`
- verified_status_revision: `3`
- verifier: `codex`（Bookkeeper）
- task_base_sha: `64bd81188a94a9e600c3e315ebaf1130d2a8a3b2`
- delivery_sha: `5a81bdc1c40238053a07736faa64b34cab294987`
- complete_delivery_base_sha: `ee0d5320b319a5bacc708eb8680e8156328db338`
- result: `accepted for review-1 dispatch`
- identity_and_commit: task、Implementer/moonshot、stage、revision、task base SHA 与
  `status.json` 一致；`delivery_sha: pending` 已从唯一 T2 delivery commit 解析；task base
  是 delivery 祖先。
- file_scope: T2 实现提交只含 `frontend/index.html`、`frontend/self-check.js`、
  `backend/tests/test_frontend_field_binding.py`、`docs/api/public-market-contract.md`、本 handoff
  和允许的 reported 状态更新；没有后端实现、凭证、运行或部署文件改动。
- source_contract: marker 前来源 SHA-256 如上；身份、实际范围、三条原始检查、八项 pass、
  Human Brief 与下一关卡完整。实现者预留的 Bookkeeper/Errata 占位字节保持不变，本核验在
  文件末尾追加。
- independent_checks:
  - `node frontend/self-check.js` → 全部自检通过，exit 0
  - `python3 -m pytest -q backend/tests/test_frontend_field_binding.py` → `10 passed in 0.10s`
  - `git diff --check 64bd81188a94a9e600c3e315ebaf1130d2a8a3b2..5a81bdc1c40238053a07736faa64b34cab294987` → pass
  - T2 implementation commit 文件集合精确匹配 Allowed Files，`status.json` 只改
    `dispatched`→`reported`，工作区无未提交改动
- seam_check: 前端请求体与后端四字段一致；确认后生成 UUID、POST 前 localStorage、四态只
  信 `body.status`、同号 GET 恢复、unknown/pending 人工锁、complete 刷新后解锁均有代码与
  自包含测试证据；v0.17 公共契约同步。
- fixed_review_range: 完整 T1+T2 产品交付固定为
  `ee0d5320b319a5bacc708eb8680e8156328db338..5a81bdc1c40238053a07736faa64b34cab294987`；
  区间内 stage dispatch/status/Bookkeeper 提交是评审上下文，不是产品交付。
- safety_effect: 核验未启动服务、未读取凭证、未访问币安、未部署、未开闸。T2 核验只允许
  派发 review-1，不授权合并、发布或资金操作。

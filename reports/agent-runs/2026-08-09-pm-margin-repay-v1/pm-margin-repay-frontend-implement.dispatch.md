# Dispatch: pm-margin-repay-frontend-implement

## Identity

- task_id: `pm-margin-repay-frontend-implement`
- target_role: `Implementer`
- target_model: `kimi`
- provider: `moonshot`
- status_revision: `3`
- required_skill: `agents/skills/senior-developer.md`

## Goal

把统一账户借款资产卡上已有的还款输入框/按钮接到已核验的本地后端
`POST /api/margin-repay` 与纯本地恢复 `GET /api/margin-repay?client_request_id=<UUID>`。
实现二次确认、发送前持久化请求号、全局防连点、四态展示、刷新恢复、unknown/pending
人工核对锁和成功后的强制账户快照刷新；同步公共 API 契约。

只做前端接线与文档，不改后端，不启动服务，不读取凭证，不部署，不开启
`APP_MARGIN_REPAY_ENABLED`，不调用真实币安接口。

## Allowed Files

仅可修改：

- `frontend/index.html`
- `frontend/self-check.js`
- `backend/tests/test_frontend_field_binding.py`
- `docs/api/public-market-contract.md`
- `reports/agent-runs/2026-08-09-pm-margin-repay-v1/status.json`，且只允许把自己的
  `current_task.state` 从 `dispatched` 改为 `reported`，其他字段不得修改
- `reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-frontend-implement.handoff.md`
  （create-only，任务结束时创建）

Bookkeeper 前置检查：

`test ! -e reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-frontend-implement.handoff.md`

结果为 `PASS`。若执行时该路径已存在，立即 `blocked`，不得覆盖。保留工作树中任何不在
上述清单的 Human/其他终端改动；边界不足时停止报告，不得扩文件。

允许在完成全部检查后创建一笔仅含上述文件的 delivery commit；handoff 中
`delivery_sha` 写 `pending`，由 Bookkeeper 从实际提交解析。不得 push、merge、部署、重启
服务、开启还款闸门或启动下一模型。

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
9. `reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-backend-implement.handoff.md`
10. `reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-plan-review.handoff.md`
11. `reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-plan.md`
12. `frontend/index.html` 中 `state.repayAmounts`、借款资产卡、资产划转四态 UI、
    `newTransferRequestId`、`showHedgeConfirm`/确认分发、`hedgeApi`、`onCacheRefresh` 和事件委托
13. `frontend/self-check.js`
14. `backend/tests/test_frontend_field_binding.py`
15. `docs/api/public-market-contract.md` 中统一账户余额卡、缓存刷新与资产划转契约
16. 已核验后端契约（只读）：`backend/app/server.py` 的 `_parse_margin_repay_request`、
    `_handle_margin_repay_post/get` 和 `_dispatch_margin_repay`；`backend/margin_repay/store.py`

不得修改后端实现、读取 `.env`、打印环境变量、启动服务或发网络请求。前端与测试应沿用
现有单文件架构，不引入依赖或通用状态框架。

## Acceptance Checks

1. **现有展示条件不漂移**：还款控件仍只在统一账户卡
   `cross_margin_borrowed > 0` 时出现；保留输入框提示 `0 自动还所有`、已借/净价值/可转余额
   的现有显示规则。60 秒重渲染不得清空未提交输入或未决状态。
2. **输入校验与确认前零请求**：只接受精确字符串 `"0"` 或严格大于零的普通十进制；
   拒绝空值、`0.0`、`0.00`、`00`、负数、科学计数法和空白。点击还款先进入二次确认，
   取消确认零请求、零请求号、零 localStorage 未决记录。
3. **确认文案诚实**：确认框必须明确负债资产和“全部/指定数量”；币安会先使用负债同币
   资产，之后才使用指定 USDT；跨资产转换价格、手续费和滑点未披露、本页面无法预估；
   账户数据约 60 秒缓存且可能滞后。不得写成“只扣 USDT”或保证 USDT 一定足够。
4. **请求体冻结**：Human 确认后才生成合法 UUID（复用已验证的
   `newTransferRequestId` 格式，不用 `crypto.randomUUID()`），发送
   `POST /api/margin-repay`，body 恰含 `client_request_id`、`asset`、原始 `amount`、
   `confirm:true`；不得发送 `specifyRepayAssets`、repay asset、float、`/repayLoan` 或
   交易所 URL。前端只认 body `status`，不得把 HTTP 200 当成功。
5. **发送前持久化与全局防连点**：在 POST 之前，把按负债资产关联的同一 UUID、asset、
   amount 写入专用 `localStorage`；同一页面任一还款提交期间，所有还款按钮禁用。浏览器到
   本机服务报错或响应丢失时保留同一未决请求，绝不生成新 UUID 自动重试。
6. **纯本地恢复与四态**：启动/重载时读取所有未决记录并按同一 UUID 调用本地 GET 一次，
   不轮询。`failed` 明确显示交易所 code/msg 并结束该请求，下一次仍需重新确认；
   `pending`/`unknown` 锁定对应资产，不生成新请求，并提供“我已到币安核对”的人工解锁；
   GET 404/请求层错误不得擅自宣称未还款或清除未决 ID。人工解锁只清本地状态，不发请求。
7. **成功后先刷新再解锁**：`succeeded` 展示实际还款资产/数量（字段存在时），立即调用
   现有强制账户快照刷新；刷新成功后才清除该资产的未决记录并允许新还款。刷新失败则保留
   成功结果和锁，提供再次刷新/页面重载恢复路径，防止旧负债卡诱导重复还款。现有
   `onCacheRefresh()` 没有成功返回值；可在同文件内为它补兼容的 boolean 结果供还款流程判断，
   但不得改变既有按钮状态、提示或其他调用方行为。
8. **公共契约与回归**：`docs/api/public-market-contract.md` 删除“后端尚未接入”旧说法，
   记录本地 POST/GET 请求响应、精确 `0` 语义、固定 USDT但同币优先、四态、幂等、默认关闸、
   unknown/pending 人工核对和费用/滑点未知；明确部署/开闸/真实还款不由本交付授权。
   self-check 与字段绑定测试覆盖上述红线，且资产划转、任务日志和资产卡既有断言不回归。

必须依次运行并在 handoff 记录原始命令与结论：

```text
node frontend/self-check.js
python3 -m pytest -q backend/tests/test_frontend_field_binding.py
git diff --check
```

测试不得调用本地服务或真实后端；只能做静态、自包含前端检查。若检查失败且修复需要范围外
文件，返回 `blocked` 或 `failed`，不得扩范围或把失败写成 pass。

## Stop

完成后按 Task Handoff Evidence Contract 创建唯一 handoff，列清实际改动、未完成项、
测试命令/结果、`base_sha`、`delivery_sha: pending`、下一任务必须读取的具体路径和 Human
Brief；把 `status.json.current_task.state` 仅改为 `reported`，创建一笔 delivery commit，
然后输出与 Human Brief 完全一致的 `[TASK_RESULT v2]` 并停止。

不得修改后端、实盘测试、部署、开闸、读取凭证、push、启动 Reviewer 或宣称交付已接受。
若任何状态可能导致重复还款或把结果不明说成失败，fail closed 并在 handoff 具名阻塞。

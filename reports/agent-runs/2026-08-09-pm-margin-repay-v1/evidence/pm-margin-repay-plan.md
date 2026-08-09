# 统一账户全仓杠杆还款 v1：实现计划

## 1. Human 已确认的目标

- 在现有“统一账户余额”借款资产卡上接通真实还款能力。
- 只接入币安 `POST /papi/v1/margin/repay-debt`，不接入
  `POST /papi/v1/repayLoan`，也不接入 BNB 划转接口。
- 页面输入 `0` 表示偿还该币种的全部负债；正十进制表示仅偿还指定数量。
- 首版以 USDT 作为指定偿还资产，覆盖“欠 BNB、账户只有 USDT”等跨资产还款场景。

本阶段只开发、离线测试并评审代码。部署、开启还款闸门、真实还款、凭证变更均不在
本阶段授权内，仍须 Human 另行明确授权。

## 2. 币安官方契约与产品语义

权威来源：
<https://developers.binance.com/zh-CN/docs/catalog/advanced-trading-derivatives-trading-portfolio-margin/api/rest-api/trade#margin-account-repay-debt>

勘误（2026-08-09）：上一版仅将文档链接锚点误写为
`#margin-account-repay`，现更正为 `#margin-account-repay-debt`。计划正文冻结的端点始终是
`POST /papi/v1/margin/repay-debt`，本次只修正引用，不改变接口、范围或验收语义。

- 端点为签名 `TRADE` 请求，IP 权重 3000。
- `asset` 是被偿还的负债资产；`amount` 可选；`specifyRepayAssets` 是逗号分隔的
  指定偿还资产。
- 省略 `amount` 才表示在偿还资产足够时偿还全部负债。因此页面的 `0` 只作为本地
  “全部还款”信号，外发时必须完全省略 `amount`，绝不把字面量 `0` 发给币安。
- 页面输入正数时，外发 `amount=<原始十进制字符串>`，数量单位是负债资产单位。
- 外发固定 `specifyRepayAssets=USDT`。但币安明确说明：只要账户中有负债同币资产，
  系统仍会优先使用同币资产，之后才使用指定资产；界面不得宣称“只扣 USDT”。
- 单次还款价值不超过 50,000 USD，由交易所作最终校验；本地不使用缓存价格作错误的
  硬性额度判断。
- 官方契约没有披露跨资产转换价格、手续费或滑点，也没有提供客户端幂等键或按请求号
  查询结果的接口。确认框必须如实提示无法预估转换成本。

## 3. 冻结的本地 API 契约

新增 `POST /api/margin-repay`，JSON 请求体：

```json
{
  "client_request_id": "UUID",
  "asset": "BNB",
  "amount": "0",
  "confirm": true
}
```

- 四个字段均必填；拒绝多余的偿还资产字段，服务端始终固定 USDT。
- `asset` 必须精确命中当前统一账户快照中 `cross_margin_borrowed > 0` 的资产。
- `amount` 必须是无符号普通十进制字符串；拒绝空白、负数、科学计数法和非数字；
  `0` 是“全部”，其余必须严格大于零。不得用二进制浮点处理金额。
- 不用缓存负债额限制部分还款数量，因为负债和利息会变化；交易所负责最终拒绝。
- `confirm` 必须严格为 `true`；未配置或未开启还款通道时返回 503，绝不静默降级。

成功或业务失败均返回本地审计记录，前端只认 `status`：

- `pending`：已登记但尚无终态，不得用新请求号重发。
- `succeeded`：仅限 HTTP 200、JSON 对象、`success is true`，且响应负债资产与请求一致。
- `failed`：仅限交易所明确的普通 4xx 拒绝；保留交易所 `code`/`msg`。
- `unknown`：网络错误、超时、5xx、418/429、非 JSON、200 响应缺字段/字段矛盾或
  `success` 不严格为 true。资金可能已变化，禁止自动重试。

审计记录至少包含请求号、负债资产、请求金额（`0` 保持可审计）、固定偿还资产、四态、
交易所返回的实际还款金额/更新时间（若可信）、错误码与错误信息。不得记录密钥、签名或
完整签名请求。

新增纯本地 `GET /api/margin-repay?client_request_id=<UUID>`，只查询 SQLite 记录，
不访问币安。它用于页面重载或浏览器到本机服务的响应丢失后恢复同一请求状态；不存在
返回 404，非法 UUID 返回 400。

## 4. 资金安全边界

1. 新增 `APP_MARGIN_REPAY_ENABLED`，默认关闭；仅当它明确开启、非离线模式且还款 API
   凭证存在时才构造客户端。开启/关闭都打印不含密钥的醒目启动状态。
2. UI 每次外发前弹二次确认，明确负债资产、指定数量/全部、同币资产优先、USDT 作为
   后续偿还资产、转换成本未知，以及页面快照可能滞后。
3. 本地 `client_request_id` 为 SQLite 唯一键；第一次请求先写 `pending`，重复请求只回放
   已有记录，绝不第二次调用币安。
4. 对币安写请求 one-shot，不做自动重试。`unknown` 和 `pending` 在页面锁定对应资产，
   必须先查询本地记录；仍无法确定时由 Human 到币安核对后手动解除。
5. 浏览器在发送前把未决请求号按负债资产写入 `localStorage`；刷新页面后先用本地 GET
   恢复，不生成新请求号。明确 `failed` 可结束该次请求；`succeeded` 必须先完成一次
   强制账户快照刷新再允许新的还款；`unknown` 只能经“我已到币安核对”解除。
6. 同一页面同一时间只允许一笔还款提交，防止权重 3000 的端点被连点并发打满；不新增
   后台轮询、定时自动还款或跨资产自动回退。

## 5. 最小任务拆分

### T1：后端与本地审计（`claude_glm` / `zhipu_glm`）

允许文件：

- `backend/config.py`
- `backend/margin_repay/__init__.py`（新增）
- `backend/margin_repay/store.py`（新增）
- `backend/services/hedge_open_live_client.py`
- `backend/app/server.py`
- `backend/tests/test_config.py`
- `backend/tests/test_hedge_open_live_client.py`
- `backend/tests/test_margin_repay.py`（新增）

实现本地 POST/GET、固定参数映射、默认关闭的配置闸门、SQLite 幂等审计、one-shot
外发和四态分类。复用现有资产划转链路的简单模式，不抽象出通用“资金操作框架”。

最低离线证据：

- `0` 外发时没有 `amount`；正数按原字符串外发；外部无法覆盖
  `specifyRepayAssets=USDT`。
- 重复/并发同 UUID 只外发一次；不同请求号彼此独立。
- 200 严格成功、明确 4xx、418/429、5xx、网络异常、非 JSON、矛盾响应全部按冻结
  规则归类并落库。
- 快照未就绪、无借款资产、非法金额/UUID/confirm、闸门关闭均 fail closed 且零外发。
- GET 只读恢复记录且零上游请求。
- allowlist、签名 POST、配置默认值和启动注入有回归测试。

### T2：前端接线与公共契约（`kimi` / `moonshot`）

允许文件：

- `frontend/index.html`
- `frontend/self-check.js`
- `backend/tests/test_frontend_field_binding.py`
- `docs/api/public-market-contract.md`

把现有预览按钮改成真实确认/提交/状态恢复流程；复用现有划转 UI 的状态措辞和强制快照
刷新能力，不改变资产卡展示条件。文档同步本地 API、前端确认、四态和未知结果处理。

最低离线证据：

- 输入为空/非法不提交；`0` 与正十进制请求体准确；按钮只在已借大于零时出现。
- 确认文案不承诺只扣 USDT，并明确转换成本未知、数据可能滞后。
- 提交期间全局防连点；UUID 在发送前持久化；刷新后用 GET 恢复同一请求。
- `succeeded` 强制刷新账户快照后再解锁；`failed` 可结束；`pending/unknown` 不生成新
  请求，`unknown` 有明确人工核对解锁动作。
- 页面不出现定时还款、自动重试、`/repayLoan` 或可编辑的偿还资产参数。

T1 经 Bookkeeper 核验后再派发 T2；两个任务不得并行修改共享工作树。

## 6. 评审与完成关卡

- 这是还款/资金含义的 `HIGH_RISK` 交付。实现前必须由不同 provider 的只读模型完成
  本计划评审并明确 `ACCEPT`；否则不派发 T1。
- T1、T2 都完成并形成一个固定 `base_sha..delivery_sha` 后，进行跨 provider
  review-1（代码、契约、测试和接缝）与独立 review-2（真实效果、操作风险和发布准备）。
- 所有验证均使用 fake client、临时 SQLite 和静态前端检查；不得向币安发真实还款请求。
- review-2 `ACCEPT` 只表示可交给 Human 决策，不授权合并、部署、开启闸门或真实还款。

## 7. 非目标

- 不实现 `/papi/v1/repayLoan`、BNB 划转、自动买币、后台自动还款或周期轮询。
- 不让用户选择多个偿还资产，不在 v1 估算手续费、滑点或转换价格。
- 不根据 60 秒缓存余额预判 USDT 一定足够，也不声称交易所一定使用 USDT。
- 不顺带改开单、平单、借款、划转、仓位或风险参数。

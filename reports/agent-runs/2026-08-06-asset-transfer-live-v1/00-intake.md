# 00-intake — 资产互转接入真实划转（2026-08-06-asset-transfer-live-v1）

Planner: opus5（anthropic）。本文是 Planner 产物，供 Bookkeeper 开阶段、
Implementer 实现、Reviewer 评审共同引用。Human 只需读第 1、2、7 节。

## 1. 背景：已经交付了什么

费率行情页私有账户面板，在「统一账户余额」与「现货账户余额」之间已有一行
资产互转 UI，**当前是「数据真实 + 划转未接后端」**：

- 资产/可用/净值全部读真实快照缓存；
- 后端快照 `balances_unified[]` 已新增 `cross_margin_free`（PAPI
  `crossMarginFree`），并同步 schema、契约文档、测试；
- 点「划转」弹二次确认，确认后**零请求**，只写一条行内预览回显。

Human 已对上述交付做**显示验收通过**（2026-08-06，含重启后真实数据回显核对）。
这批改动在开阶段前需先提交，作为本阶段 `base_sha`（见 §6）。

实盘实测三条事实（写进设计前提，勿再推翻）：

1. `cross_margin_free` **可能大于** `total_balance`（实测 USDT 383.59254168 >
   383.38976664）。两者基数不同：total 含全仓+UM+CM 三个子钱包，free 只是全仓
   杠杆钱包可动用额。根因未证实，**Human 已决定忽略不追**。
2. `cross_margin_free` **不扣借款负债**：XLM 可用 100 / 已借 200，这 100 能划走，
   划走后负债仍在。
3. 账户 16 项统一账户资产中 13 项余额为 0；**Human 已决定下拉不过滤零余额资产**。

## 2. 本阶段目标与非目标

### 目标

把资产互转从「零请求预览」接成**真实可用的划转能力**，覆盖 Human 点名的两项：

- **任务 2**：后端划转接口，含四个缺口——动钱授权、幂等、划转后刷快照缓存、
  币种精度/交易所错误回显；前端接线到真实端点。
- **任务 3**：私有账户未读取空态里那句「系统不会执行交易或划转」，接口上线后
  不再成立，须改。

### 非目标（本阶段明确不做）

- 不做「最大可划转额」计算或 uniMMR 预演算。`cross_margin_free` 只是可用额，
  转出还要过账户保证金约束，本阶段以交易所返回的拒绝为准，不在本地预测。
- 不追 §1 事实 1 的根因（Human 已决定忽略），不新增
  `umWalletBalance`/`crossMarginAsset` 映射。
- 不做划转历史列表页、不做定时/自动划转、不做多笔批量划转。
- 不改动划转以外的账户面板行为。

## 3. 风险分级与评审拓扑（含越门记录）

**风险分级：`HIGH_RISK`**。依据 `AGENTS.md` §8——`transfer`（划转）明示在
HIGH_RISK 清单内。HIGH_RISK 的标准拓扑是 review-1 **加** review-2。

**本阶段实际拓扑（Human 2026-08-06 决定，属越门，如实记录不粉饰）：**

| 环节 | 标准要求 | 本阶段实际 | 性质 |
|---|---|---|---|
| Implementer | 默认后端 `claude_glm` / 前端 `kimi`；Claude 默认非实现者 | opus5 | Human 显式覆盖默认路由（`roles.md` 允许 Human 覆盖） |
| Bookkeeper | 不得兼任 implementer / reviewer | deepseek，**兼任 review-1** | **越门**：违反 `roles.md` Bookkeeper Purpose |
| Review-1 | 跨 provider，非实现作者 | deepseek（`deepseek` ≠ `anthropic`） | 合规 |
| Review-2 | HIGH_RISK 必须有，且与全部实现作者跨 provider | **无** | **越门**：违反 `AGENTS.md` §8 |
| 计划评审 | HIGH_RISK 实现前须独立跨 provider 只读计划评审 | 见 §7 开放项 O-3 | 待 Human 定 |

**越门原因（Human 陈述）**：其余模型配额耗尽，可用模型仅剩 opus5 与 deepseek。

**越门的实际后果，供 Human 决策时权衡**：

1. Bookkeeper 兼 review-1 意味着「核验状态的人」与「评审代码的人」是同一个会话
   来源，两道独立闸门塌成一道。若 deepseek 在评审中漏判，没有第二个视角能在封存
   前拦住。
2. 无 review-2 意味着无人独立核查「需求是否真被满足、实盘风险是否可接受、是否
   可发布」。本阶段是**动钱路径**，这一层缺失由 Human 的显示验收承担。
3. 建议的补偿措施（不新增角色、不消耗额外模型）：本阶段**先不合并 main**，
   Human 在实盘小额试划转（例如 1 USDT）验证后再决定合并，把「真实效果核验」
   放到 Human 手里。

## 4. 设计

### 4.1 已有能力（不重复造）

`backend/services/hedge_open_live_client.py:474` 的 `universal_transfer` 已实现
`POST /sapi/v1/asset/transfer`，冻结枚举恰好双向齐全：

- `PORTFOLIO_MARGIN_MAIN`：统一账户 → 普通现货账户
- `MAIN_PORTFOLIO_MARGIN`：普通现货账户 → 统一账户

已具备 one-shot 写语义（超时/5xx 不重试）、非 200 抛错并带交易所响应详情。
目前仅被平仓流程内部调用，**没有对外 API**。本阶段是给它加一条受控的对外通路，
不是重写划转能力。

### 4.2 端点

```
POST /api/asset-transfer
```

请求体（全部必填，缺一即 400）：

| 字段 | 类型 | 说明 |
|---|---|---|
| `client_request_id` | string(UUID) | 前端生成，幂等键，见 §4.4 |
| `from_account` | `"unified"` \| `"spot"` | 转出账户 |
| `to_account` | `"unified"` \| `"spot"` | 转入账户，必须与 `from_account` 不同 |
| `asset` | string | 币种，服务端做白名单校验（见下） |
| `amount` | string | 十进制字符串，服务端不做浮点解析 |
| `confirm` | bool | 必须为 `true`，否则拒绝 |

**方向映射在服务端完成**，请求体不允许直接传币安枚举——外部不得注入
transfer type。`from/to` 组合只有两种合法值，其余一律 400。

**`asset` 白名单**：必须出现在当前快照的对应账户余额里。杜绝任意币种注入，
也避免打字错误把资产转进一个不存在的币种。

**`amount` 校验**：正十进制字符串；不接受负号、科学计数法、空白。服务端用
`Decimal` 解析，解析失败即 400。**不做本地余额充足性预判**（缓存 60 秒可能过期），
余额不足交由币安返回错误码，原样回显。

### 4.3 动钱授权（Safety Kernel §3.1）

划转与「自动开单」性质不同：开单由 worker 自主发起，所以需要 `start_gate`
这类常开闸门；划转**每一笔都由人点击发起**，二次确认弹框本身就是那次授权。

因此推荐 **不新增独立闸门**，改用三道硬约束：

1. `confirm: true` 必填——防止误调用与 CSRF 式误触发；
2. **单笔上限**：按快照估值折算，单笔超过 `TRANSFER_MAX_USDT` 直接拒绝，
   不发往币安。默认值待 Human 定（见 §7 开放项 O-1）；
3. 全部划转**落库审计**（§4.4），事后可查。

替代方案（若 Human 认为需要）：新增 `transfer_gate`，与 `start_gate` 同构，
默认关闭，开启后才接受划转请求。代价是每次划转前多一步开关操作。

**本项是产品决策，Planner 不自行拍板**，见 §7 开放项 O-1。

### 4.4 幂等

`/sapi/v1/asset/transfer` **没有** `clientOrderId` 之类的幂等键——这是它与下单
接口的关键差异。重复提交会**真的转两次**。

三层防护：

1. **前端**：提交期间按钮禁用 + loading 态，响应回来前不可再点；
2. **服务端幂等表**（权威层）：新建 `asset_transfer` 表，`client_request_id`
   建唯一索引。收到请求先插入「进行中」记录，唯一索引冲突即返回**上一次的结果**
   而不重复发往币安；
3. **one-shot**：沿用既有约定——超时或 5xx **不重试**，标记为「结果未知」并
   要求人工核对，绝不自动重发。

`asset_transfer` 表最小字段：`client_request_id`(UNIQUE)、`from_account`、
`to_account`、`asset`、`amount`、`status`(`pending`/`succeeded`/`failed`/`unknown`)、
`tran_id`（币安返回）、`error_code`、`error_message`、`created_at_us`、`updated_at_us`。

**「结果未知」必须是一个显式状态**：超时不等于失败，钱可能已经转了。前端对该
状态的文案必须明确提示「请到币安核对后再操作」，不得显示成失败诱导用户重试。

### 4.5 划转后刷新快照缓存

划转成功后账户余额立刻变了，但快照缓存 TTL 60 秒，不刷新的话用户会看到旧数字，
误以为没转成功而重复操作——这与 §4.4 的幂等风险直接相关。

方案：复用既有的 `POST /api/public-market/cache-refresh`（`private_client` 的
`force=True` 单键逐出，已在用）。**由前端在划转成功后调用**，后端划转端点不
内嵌刷新——保持划转端点单一职责，且刷新失败不应影响划转结果的记录。

### 4.6 错误回显

币安错误原样回传，不吞不改写。前端按三类展示：

| 类别 | 处理 |
|---|---|
| 业务拒绝（余额不足 -4015、精度错误、币种不可划转等） | 原样显示错误码 + 中文说明，行内展示，不弹框 |
| 参数/校验失败（本地 400） | 行内展示具体哪个字段不合法 |
| 结果未知（超时/5xx） | **醒目警示**，文案要求人工去币安核对，禁止「重试」按钮 |

**精度**：币安对每个币种有划转精度限制，超精度会被拒。本阶段**不在本地预判精度**
（快照没有该元数据），以交易所拒绝为准并把错误清楚回显。

## 5. 任务拆分

按 `AGENTS.md` §6.2，后端与前端边界清晰、可安全拆分：

### T1（后端）

- 新建 `asset_transfer` 表与存储层（幂等唯一索引）；
- 新增 `POST /api/asset-transfer`：校验 → 幂等 → 调用既有 `universal_transfer`
  → 落库 → 返回结构化结果；
- 单笔上限与 `confirm` 门；
- 错误分类与原样回传；
- 单元测试：两方向映射、同账户拒绝、非法金额、白名单外币种、幂等重放、
  超时→`unknown` 不重试、上限拒绝。

**Allowed Files（预期）**：`backend/services/`、`backend/app/server.py`（路由）、
新增 store 模块、`backend/tests/`。**不改** `hedge_open_live_client.py` 的
`universal_transfer` 本体（既有实盘验证过的写路径，不动）。

### T2（前端）

- 划转按钮接线到真实端点（生成 `client_request_id`、提交中禁用、三类结果回显）；
- 空态文案「系统不会执行交易或划转」改写（Human 点名的任务 3）；
- 成功后调用 cache-refresh 并重渲染；
- `frontend/self-check.js` 断言：提交前零请求、确认后恰好一次 POST、
  重复点击不产生第二次 POST、三类结果文案、未知态无重试按钮。

**Allowed Files（预期）**：`frontend/index.html`、`frontend/self-check.js`。

### 验收标准（两个任务共同）

1. 后端全量 `python3 -m pytest backend/tests -q` 全绿（当前基线 1468 passed）；
2. `node frontend/self-check.js` 全绿；
3. 幂等有测试证明：同一 `client_request_id` 第二次请求不产生第二次外发；
4. 超时路径有测试证明：不重试，状态为 `unknown`，文案不诱导重试；
5. 契约变更同步 `schemas/` 与 `docs/api/`（若端点纳入契约文档范围）；
6. **不合并 main、不部署**——合并需 Human 单独授权（`AGENTS.md` §9）。

## 6. 阶段基线（base_sha）

开阶段前工作区有未提交改动，`base_sha` 必须是 committed HEAD
（`roles.md` SHA Discipline）。当前 HEAD = `bb47d02`。

待提交的改动分两组：

- **A 组（本次互转交付，已 Human 显示验收）**：`backend/domain/snapshot.py`、
  `schemas/api/public-market/snapshot.schema.json`、`docs/api/public-market-contract.md`、
  `backend/tests/test_private_account_v1.py`、`frontend/index.html`、
  `frontend/self-check.js`；
- **B 组（更早的在途改动，非本次产出）**：资产卡 `<10 USDT` 过滤、
  `DISABLED_SPOT_ONLY` 借币操作列。

两组混在同一工作区。建议**分两次提交**（A 组、B 组各一次），使
`base_sha..delivery_sha` 的评审范围干净。提交由 Human 授权后执行。

## 7. 待 Human 决定的开放项

| 编号 | 事项 | Planner 建议 |
|---|---|---|
| **O-1** | 动钱授权形态：`confirm` + 单笔上限（推荐） vs 独立 `transfer_gate` | 推荐前者。划转由人手动发起，二次确认即授权；独立闸门与手动性质不匹配且增加操作负担 |
| **O-2** | `TRANSFER_MAX_USDT` 单笔上限取值 | 建议先设保守值（如 2000 USDT）。当前账户总资产量级约数百 USDT，保守上限不影响正常使用，却能挡住 UI bug 导致的异常大额 |
| **O-3** | 是否执行 §8 要求的实现前跨 provider 计划评审 | 建议**做**，由 deepseek 在开阶段任务里一并完成（只读评审本文，verdict 返回 Planner）。它不消耗 `rework_count`，也不占用 Human 说的「1 轮 review」——那 1 轮指实现后的 review-1 |
| **O-4** | A/B 两组改动是否分两次提交 | 建议分开提交，理由见 §6 |

O-1 与 O-2 不定，T1 无法开工（它们决定服务端拒绝逻辑）；O-3、O-4 不阻塞设计，
但影响开阶段任务的内容。

## 8. 角色路由（本阶段）

| 角色 | 模型 | provider |
|---|---|---|
| Planner | opus5 | anthropic |
| Bookkeeper | deepseek | deepseek |
| Implementer（T1/T2） | opus5 | anthropic |
| Review-1 | deepseek | deepseek |
| Review-2 | 无（Human 越门豁免，见 §3） | — |

Human 从准备好的 packet 启动模型终端；任何模型不得启动、调用、转交或冒充另一个
模型会话（`AGENTS.md` §3.2）。

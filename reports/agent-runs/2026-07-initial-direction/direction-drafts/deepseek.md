# DeepSeek 阶段设计方向稿

> 模型：DeepSeek V4
> 角色：独立设计方向评审者，非最终拍板者
>
> 已读文件：`docs/product/PRD.md`（完整）、`docs/harness-design.md`（完整）、
> `docs/README.md`、`prototypes/fake-ui/index.html`（扫描结构）、
> `币安套费率策略，逐仓杠杆.js`（扫描结构，3448 行）。
> `docs/architecture/ARCHITECTURE.md` 和 `docs/development/DEVELOPMENT_GUIDE.md`
> 目前为 TBD 骨架，无实质内容。
> `llms-full.txt`（约 193K 行）已确认 PRD 中引用的所有端点均在其中存在。

## 1. Baseline 理解

这是一个 Binance 统一保证金（Portfolio Margin）下的资金费率对冲**操作台**，
不是自动交易机器人。它继承了旧 FMZ 逐仓杠杆策略验证过的对冲模式，但换到了
Portfolio Margin 账户和自建 Python/TypeScript 技术栈。

核心约束链（缺一不可）：

1. **全手动触发**：开仓、平仓一概由人在 UI 操作，系统不因费率变化自动决策。
2. **腿不匹配只告警**：高亮差异、记录日志、推送到 UI，但不自动补腿、不平仓、
   不追加订单。
3. **成本全口径**：资金费、手续费（含 BNB 抵扣折扣）、返佣（默认 40%）、借币
   利息、预估滑点，全部进入净收益计算。
4. **USDT 单一计价 + 单向持仓**，不做多币种和多向持仓。
5. **bStocks 单边**：只做正费率（做空永续+买现货），负费率不做，因为假设其不
   支持借币。
6. **API key 不开提币权限**；HTTP 503 未知状态不重试，先查再断。
7. **适配层基于实测 JSON**，不是基于文档推测。

Harness 治理约束：本稿为五模型方向草稿之一，经 GPT/Codex 合成后由用户批准才能
进入开发。我的角色是提供独立技术判断，不是代替用户做产品决策。

## 2. 你认为当前 PRD 已经明确的内容

以下事项边界清晰，不需要方向性讨论，可以直接进入实现设计：

| # | 事项 | 依据 |
|---|------|------|
| 1 | 五种资产分类 + 8 小时刷新机制 | PRD §Asset Classification |
| 2 | 正/负费率两种对冲模式及对应腿构成 | PRD §Hedge Modes |
| 3 | 现货路由优先级：PM 杠杆优先，普通现货兜底 | PRD §Hedge Modes |
| 4 | 执行计划的数学：总名义/轮次、最小值 2% uplift、尾轮合并 | PRD §Manual Execution Flow |
| 5 | 接口清单（PAPI/UM/杠杆/现货/行情 REST + WebSocket 流） | PRD §Interface Discovery |
| 6 | 记账公式：`net = funding - futures_fee_adj - spot_fee_adj - borrow_int - slippage`，返佣×0.6 | PRD §Fee and Profit Accounting |
| 7 | 资金费账本字段构成（时间/方向/费率/名义/签名金额/收入 ID/原始引用） | PRD §Fee and Profit Accounting |
| 8 | 风控清单：无提币、可配置上限、借币失败停执行 | PRD §Risk Controls |
| 9 | 技术栈：Python asyncio + TypeScript React + SQLite 候选 | PRD §Technology Direction |
| 10 | 前端四大页面：Overview / Opportunities / Manual Open / Profit & Fees | PRD §UI Requirements |
| 11 | 三阶段验收节奏 | PRD §Phase 1-3 Acceptance Criteria |
| 12 | 503/未知执行状态处理准则 | PRD §Interface Discovery |

## 3. 你认为当前 PRD 仍不明确或有风险的内容

### 3.1 借币→现货卖出的中间态无保护

- **问题**：负费率对冲流程是"先借币→卖出→开合约多单"。借币完成后、现货卖出
  前存在时间窗口，若价格快速下跌，借到的币值可能已不够覆盖计划合约名义金额。
- **为什么重要**：这会导致开仓后双腿名义金额不对等，暴露裸露的方向风险。
- **建议**：借币后立即做"市值检查"：`借币数 × 最新价 ≥ 目标名义 × 0.98`，
  不满足则弹窗警告并暂停执行，由用户决定继续或取消。

### 3.2 "平滑开仓后立即对冲兜底"缺乏定量定义

- **问题**：PRD 只提了概念，没定义超时阈值和兜底行为。实现者将自行脑补，导致
  不同实现行为不一致。
- **为什么重要**：没有统一口径，Phase 3 实盘测试时兜底行为可能就是事故本身。
- **建议**：明确默认 30 秒等待，超时后以当前最优价下市价单，执行前再次弹窗
  显示新价差并要求用户最终确认。30 秒应为可配置参数。

### 3.3 现货路由降级逻辑缺失

- **问题**：PRD 说"优先 PM 杠杆现货"，但没定义"不可用"的判定条件，也没定义
  保证金路由失败后是否自动降级到普通现货。
- **为什么重要**：保证金路由可能因单币种借币额度满而失败，若没有降级，用户
  看到的是"执行失败"但不知道自己有替代路径。
- **建议**：Phase 2 设计路由矩阵，按顺序尝试：PM 杠杆 → 普通现货。每一步
  失败记录原因并告知用户当前走的是什么路由。

### 3.4 bStocks 假设未验证

- **问题**：bStocks 被标记为 `BSTOCK_LONG_SPOT_ONLY`，"不支持借币"是假设。
  真实性需要 Binance 实测验证。
- **为什么重要**：如果 bStocks 在 PM 账户下实际行为与假设不同（例如某些
  bStocks 可借币、或有特殊交易过滤器），分类逻辑需要修正。
- **建议**：Phase 2 接口发现阶段单独列一个 bStocks 验证任务：① 列举可用
  bStocks；② 逐对测试现货和保证金可用性；③ 测试借币接口返回值。

### 3.5 腿不匹配容差阈值空缺

- **问题**：PRD 说"Quantity difference exceeds configured tolerance"时告警，
  但 tolerance 默认值未定义，也未说明是绝对偏差还是百分比。
- **为什么重要**：阈值太紧→小数精度误报淹没真异常；太松→漏掉实质性不匹配。
- **建议**：默认 `max(名义金额差异 1%, $5 USDT)`，分两级：精度级（静默标记）
  和实质性偏差（红色高亮+推送告警）。

### 3.6 执行规划器的边缘 case 未处理

- **问题**：末轮余量合并逻辑只覆盖了"余量低于最小值"一种情况。以下边缘 case
  均未提及：① 只有一轮且低于最小值；② 合并后前一轮超单笔上限；③ 所有轮次
  名义金额都为 0。
- **为什么重要**：边界输入在真实交易中会被触发，届时执行器行为不可预测。
- **建议**：Phase 2 计划器覆盖全部边界：① 单轮低于最小值→整轮按 min×1.02；
  ② 合并后超上限→不合并，新增一轮；③ 零/负值输入→拒绝并报错。

### 3.7 实时数据流向未确定

- **问题**：盘口 WebSocket 数据如何到达前端？前端直连 Binance 还是后端中转？
- **为什么重要**：前种方案 API 凭证暴露在前端网络栈中；后种需要设计后端→前端
  推送协议。两种方案的后端架构差别很大。
- **建议**：采用后端中转。理由：① 凭证不离开后端；② 后端可归一化/缓存；
  ③ 便于录制流数据做审计回放。前端通过后端 WebSocket 或 SSE 接收推送。

### 3.8 SQLite 在并发写入场景下的适配性未评估

- **问题**：WebSocket 事件（盘口更新、订单状态、账户变化）可能产生高频并发写入，
  SQLite 单写者模型可能成为瓶颈。
- **为什么重要**：如果写入拥塞导致事件丢弃，持仓监控和会计账本的数据完整性受损。
- **建议**：Phase 2 测实际吞吐后决策。若压力大，分离高频流数据（内存缓存+定期
  快照）和低频事件数据（SQLite）。WAL 模式是第一步尝试，不行再评估 PostgreSQL。

### 3.9 资金费率刷新周期与资产分类刷新不该一致

- **问题**：PRD 说资产扫描"每 8 小时"，费率也搭车 8 小时。但费率在结算周期间
  会波动，用户在机会表上可能看过期数据做决策。
- **为什么重要**：8 小时前的费率对当前决策几乎没有参考价值。
- **建议**：资产分类（交易对可用性）保持 8 小时；资金费率独立用 5-15 分钟周期
  刷新，UI 标注数据时间。用户进手动开仓流程时强制拉取一次最新费率。

### 3.10 平仓流程完全缺失

- **问题**：PRD 无平仓设计。Phase 3 实盘测试时，用户开了仓不知道怎么平。
- **为什么重要**：开仓+平仓构成完整闭环。缺一个，Phase 3 无法归因净收益。
- **建议**：Phase 2 开始前补充平仓 PRD 章节。Phase 3 前至少要有与开仓对称的
  反向执行流程：① 人工输入平仓计划；② 同时下市价单平两腿；③ 记录平仓费用；
  ④ 归还借币。

### 3.11 PRD 与 Harness 流程的桥接缺失

- **问题**：PRD 定义了产品需求，Harness 定义了开发治理，但没人说"Phase 2 具体
  哪个模块由哪个实现模型负责"。
- **为什么重要**：如果开发时不清楚自己处于 Harness 的哪一环，可能跳过 review。
- **建议**：在 `DEVELOPMENT_GUIDE.md` 填充时写入 Harness 阶段映射：Phase 1
  → Direction Freeze；Phase 2 → Implementation + Review-1 + Review-2；
  Phase 3 → 重复 Implementation Loop。

## 4. 关键技术设计建议

### 4.1 后端分层架构

```text
backend/
├── main.py                    # FastAPI 应用入口
├── config.py                  # YAML 配置 + 环境变量
├── models/                    # Pydantic 数据模型（整个系统的类型基础）
│   ├── symbol.py              # SymbolMeta, Classification
│   ├── execution.py           # ExecutionPlan, Round, HedgeRequest
│   ├── position.py            # HedgePosition, LegState
│   ├── accounting.py          # FundingEntry, FeeRecord, ProfitSummary
│   └── mismatch.py            # MismatchType, MismatchEvent
├── scanner/
│   ├── classifier.py          # 资产分类引擎
│   ├── normalizer.py          # 交易规则归一化
│   └── opportunity.py         # 机会表
├── executor/
│   ├── planner.py             # 执行计划构造器（纯函数）
│   ├── state_machine.py       # 对冲执行状态机
│   ├── hedge.py               # 对冲编排器
│   └── smoother.py            # 平滑开仓 + 兜底
├── monitor/
│   ├── watcher.py             # 持仓周期性检测
│   └── mismatch.py            # 不匹配判定
├── accounting/
│   ├── funding_ledger.py      # 资金费账本
│   ├── fee.py                 # 手续费+BNB折扣+返佣
│   └── profit.py              # 收益归因
├── adapters/
│   └── binance/
│       ├── rest.py            # HMAC 签名、限流、重试策略
│       ├── papi.py            # Portfolio Margin REST 封装
│       ├── spot.py            # 现货 REST 封装
│       ├── futures.py         # 合约 REST 封装
│       ├── ws.py              # WebSocket 连接管理
│       └── orderbook.py       # 本地订单簿维护
└── api/                       # FastAPI 路由层（薄层，只做参数校验和调用转发）
    ├── routes/
    └── ws_endpoints.py
```

核心设计原则：

- **适配层零业务逻辑**：`adapters/` 只封装 HTTP 调用、签名、限流、重试策略。
  策略层不 import Binance URL，只依赖抽象接口。
- **状态机外显**：执行器不以隐式 async 协程管理状态，而是维护显式状态枚举 +
  转换表，每个转换有 on_enter/on_exit 钩子和超时定时器。
- **所有外部 IO 可记录**：rest.py 的 `request()` 返回 `(data, raw_json, headers)`
  三元组，raw_json 落盘（脱敏后的）。用于审计和回放测试。
- **金额全 Decimal**：不允许 float 出现在任何金额计算路径中。

### 4.2 适配层具体设计

- **REST 客户端**：
  - 三 base URL 切换：`papi` / `api` / `fapi`。
  - HMAC SHA256 签名，recvWindow 默认 5000ms。
  - 解析 `X-MBX-USED-WEIGHT-1M` 做本地令牌桶限流。
  - 写下单请求时，HTTP 503 / 超时统一定义为 `UNKNOWN` 状态，由调用方决定是否
    通过订单查询去确认，不在适配层自动重试。
- **WebSocket 客户端**：
  - listenKey 生命周期管理（创建/30 分钟 keepalive/关闭）。
  - 盘口流仅在手動开仓期间订阅，执行完成后主动取消。
  - 本地订单簿：初始化时拉 depth snapshot → 增量 WebSocket 更新 → 维护
    bids/asks。对外暴露 `best_bid` / `best_ask` / `spread` / `weighted_avg_price(qty)`。

### 4.3 资产分类器

- 输入：`/fapi/v1/exchangeInfo` + `/api/v3/exchangeInfo` + Margin 可用性。
- 输出：`List[SymbolMeta]`，每条包含 symbol、base_asset、classification、
  路由信息、min_notional_by_leg、step_size、borrowable。
- 实现要点：并行拉取两个 exchangeInfo 节省启动时间；USDT 计价过滤在扫描阶段
  完成；Margin 可用性可以取交换信息里的 `isMarginTradingAllowed` 字段。
- 单元测试用 fixture JSON 覆盖 5 种分类 + PERP_ONLY 和 SPOT_ONLY 排除逻辑 +
  交易对下架/暂停的过滤。

### 4.4 执行规划器（纯函数，可独立测试）

```python
def build_plan(
    total_notional: Decimal,
    rounds: int,
    min_notional: Decimal,
    max_notional: Decimal | None,
) -> ExecutionPlan:
    """Returns plan with corrected per-round amounts and final round count."""
```

覆盖的边界：单轮低于 min → 上调；合并后超 max → 拆轮；最终余量 < min →
并入前一或新增轮；rounds ≤ 0 或 total ≤ 0 → ValueError。

这是一个纯函数，不依赖 IO，可以在 Phase 1 写好完整的单元测试集。

### 4.5 对冲执行状态机

```text
IDLE → PREFLIGHT → (BORROWING → BORROWED)? → SUBSCRIBING_DEPTH
→ SHOWING_SPREAD → AWAITING_CONFIRM → OPENING_BOTH
→ (AWAITING_FILLS → NEXT_ROUND)* → COMPLETE
```

每个状态的超时和失败分支：

- `PREFLIGHT` 失败 → `ABORTED`，提示原因
- `BORROWING` 失败 → `ABORTED`，记录借币失败原因，不重试
- `OPENING_BOTH` 一腿成功一腿失败 → `DEGRADED`，高亮不匹配
- `OPENING_BOTH` 超时 → 先查订单状态再决定 → `DEGRADED` 或重试
- 任何非终态收到用户取消 → `CANCELLED`

### 4.6 会计模型

- 资金费：REST `GET /papi/v1/um/income`（incomeType=FUNDING_FEE），按
  `tranId` 去重幂等拉取。
- 手续费：从 fill 数据提取 commission + commissionAsset。若为 BNB，按
  实时 BNB/USDT 价折算，同时检查 feeBurn 状态确定折扣生效。
- 返佣：`fee_after_bnb_discount × (1 - rebate_rate)`，默认 rebate_rate=0.4。
- 借币利息：`GET /papi/v1/margin/marginInterestHistory`，按小时均摊。
- 滑点：`|avg_fill_price - pre_trade_mid_price| × qty`。

所有金额以 USDT 为基准单位，非 USDT 计价费用通过实时汇率折算。

### 4.7 前端建议

Fake UI 原型已有良好基础。建议方向：

- Phase 1 保持假数据但**结构对齐后端模型**：JSON 结构名与 Pydantic model 字段
  名一致，避免后续集成时字段名映射混乱。
- 增加一个 System Status 横幅或侧栏组件：API 连接灯号、listenKey 剩余时间、
  上次扫描时间。
- Manual Open 页面增加执行日志滚动区，每轮执行状态用颜色标记（等待中/执行中/
  成交/失败）。

### 4.8 测试分层

| 层 | 内容 | 开始时间 |
|----|------|----------|
| 单元 | 分类器、归一化器、规划器（纯函数）、会计公式 | Phase 1 |
| 单元 | 状态机全路径（mock 适配层） | Phase 2 |
| 集成 | 适配层对录制 JSON 的回放测试 | Phase 2 |
| E2E | 小资金实盘（$10-50 USDT/笔，人工逐笔确认） | Phase 3 |

## 5. 第一阶段开发范围建议

Phase 1 目标：验证架构骨架的合理性，所有产物是文件级可验收产物，零 API 调用。

具体范围（按优先级）：

1. **Python 项目骨架**
   - `backend/` 目录结构 + `pyproject.toml`（dependencies: pydantic, httpx, websockets, pyyaml）
   - `backend/config.py`：配置类和 YAML 加载
   - `backend/models/` 下全部 Pydantic 模型定义

2. **资产分类器 + 单元测试**
   - 从 `llms-full.txt` 构造至少两个 exchangeInfo fixture（正常 + 极端）
   - 实现 `classifier.py`，输出分类表
   - `pytest` 覆盖 5 种分类路径 + PERP_ONLY/SPOT_ONLY 排除 + 暂停交易对过滤

3. **规则归一化器 + 单元测试**
   - 解析 LOT_SIZE / MARKET_LOT_SIZE / MIN_NOTIONAL / NOTIONAL filters
   - 覆盖 stepSize=0（防御）、NOTIONAL filter 存在/不存在分支

4. **执行规划器 + 单元测试**
   - 纯函数：输入 total/rounds/min_notional/max_notional → ExecutionPlan
   - 测试边界：0 轮、负金额、单轮低于 min、合并超 max、末轮余量

5. **状态机骨架**
   - 状态枚举 + 转换表 + 超时参数定义
   - Phase 1 不需要真实执行，只需要枚举和接口签名

6. **API Discovery Plan 文档**
   - `reports/agent-runs/2026-07-initial-direction/api-discovery-plan.md`
   - 列出每个端点的 HTTP 方法、URL、签名要求、预期响应字段、对应用例

7. **文档补齐**
   - `docs/architecture/ARCHITECTURE.md`：填写分层架构图和技术决策
   - `docs/development/DEVELOPMENT_GUIDE.md`：填写环境搭建、命令、编码规范

8. **Fake UI 数据对齐**
   - 确保 fake-ui 的静态数据结构与后端 Pydantic model 字段名一致
   - 不需要 React 迁移，只需要字段名对齐

## 6. 不建议第一阶段做的内容

| 事项 | 理由 |
|------|------|
| 真实 API 调用 | 接口发现应文档先行，且 Phase 1 不引入 API Key |
| WebSocket 连接/订单簿 | 复杂度是 REST 的 3-5 倍，Phase 2 再做 |
| 数据库建表 | 先用 Pydantic 模型验证字段，Phase 2 再落库 |
| 前后端联调 | Phase 1 各自独立验证 |
| 平仓流程 | PRD 未定义，Phase 2 前补充 PRD 再开发 |
| React 迁移 | 当前 fake UI 够用，React 迁移是 Phase 2 的事 |
| 并发执行/多交易对 | 先打通单交易对路径 |
| 收益归因完整计算 | 需要真实 fill 数据，Phase 2 用样本验证 |

## 7. 验收标准建议

### 文件级产物（必须存在且内容完整）

- `backend/pyproject.toml`：可 `pip install -e .`
- `backend/models/*.py`：全部 Pydantic 模型定义
- `backend/scanner/classifier.py` + `tests/test_classifier.py`
- `backend/scanner/normalizer.py` + `tests/test_normalizer.py`
- `backend/executor/planner.py` + `tests/test_planner.py`
- `backend/executor/state_machine.py`：状态枚举+转换表
- `reports/agent-runs/2026-07-initial-direction/api-discovery-plan.md`
- `docs/architecture/ARCHITECTURE.md`：非 TBD
- `docs/development/DEVELOPMENT_GUIDE.md`：非 TBD

### 测试验收

- `pytest` 全部通过，覆盖上述单元测试要求的所有路径和边界
- 终端输出存档为 `60-test-output.txt`

### UI 验收

- Fake UI 四个页面可正常渲染、无 JS 报错
- 手动点击导航切换流畅
- 静态数据字段名与后端 Pydantic model 对齐（人工 code review 确认）

### 验收约束

- 不可仅凭口头声明。必须有 git diff、测试输出文本/截图、UI 截图。
- 所有产物需在一个 git commit 中落地。

## 8. 与现有 PRD 的冲突或修订建议

| # | 原问题 | 建议改成 | 理由 |
|---|--------|----------|------|
| 1 | SQLite "likely first candidate"（§Technology Direction） | "Phase 2 基于实测吞吐量评估 SQLite WAL 模式；若不满足则评估双存储或 PostgreSQL。Phase 2 结束前写入 ADR。" | 决策点后移不可无限推迟，需要一个截止时间 |
| 2 | 平滑开仓兜底无定量定义（§Execution Rules） | "默认等待 30 秒（可配置），超时后以当前最优价市价单执行，弹窗显示新价差和预估滑点，用户确认后生效。" | 实现口径必须统一 |
| 3 | 资产分类刷新与资金费率刷新同周期（§Asset Classification） | "资产分类 8h；资金费率 5-15min 独立刷新，UI 标注更新时间。" | 费率时效性要求远高于交易对可用性 |
| 4 | 缺少 System Status 页面（§UI Requirements） | 增加状态组件：API 连接灯号、WS 状态、listenKey 剩余时间、限流使用率 | 运维可见性是操作台的基本要求 |
| 5 | 平仓流程完全缺失（全文） | 在 Non-Goals 中声明"平仓流程在 Phase 2 前作为独立 PRD 章节补充" | 缺口要显式声明，而非沉默 |

## 9. 需要用户拍板的问题

### Q1：Phase 1 前端策略

- **A**：保持单文件 HTML，Phase 2 再 React 迁移 → 快但返工
- **B**：Phase 1 直接 React + TypeScript 项目骨架 → 慢但后续无缝
- **C**：Vite + vanilla TS 轻量版 → 中间路线

> 建议 B。当前 fake UI 的复杂度（表格+表单+四屏）已不适合单文件维护。

### Q2：后端 Web 框架

- **A**：FastAPI → 成熟、Swagger 文档、WS 原生支持
- **B**：纯 asyncio + aiohttp → 轻量、无框架侵入
- **C**：Phase 1-2 只用 CLI，Phase 3 加 Web 层 → 最快但可能重构

> 建议 A。FastAPI 的 Pydantic 模型复用和 WebSocket 管理能力与项目需求高度匹配。

### Q3：Phase 3 实盘风险上限

- **A**：$10/笔，$50/天 → 极低风险但可能不触发最小名义金额
- **B**：$50/笔，$200/天 → 更真实但风险提升
- **C**：用户自设，系统只提供可配置上限字段

> 建议 C。系统定义配置项和默认值（$50/$200），用户可调，Phase 3 开始前必须显式确认。

### Q4：bStocks 优先级

- **A**：Phase 2 与普通币种并行 → 全面但可能拖慢主路径
- **B**：Phase 3 独立调研 → 主路径快但后期返工风险
- **C**：Phase 2 最小验证（能否交易+借币），不深入执行路径

> 建议 C。折中方案，回答关键问题但不阻塞主流程。

### Q5：平仓 PRD 补充时机

- **A**：Phase 1 现在补充 → 早对齐但分散资源
- **B**：Phase 2 开始前补充 → 刚好在实盘前完成
- **C**：Phase 3 前补充 → 太晚

> 建议 B。平仓不阻塞 Phase 2 的接口发现和核心开发，但 Phase 3 实盘需要它。

## 10. 最终建议

1. **Phase 1 的目标不是"做东西"，是"验证骨架"**：资产分类器+归一化器+规划器
   三件套是后续所有模块依赖的基础，Phase 1 把它们写好、测透，Phase 2 才能跑起来。
2. **Amount = Decimal，不做商量**：这是交易系统的铁律。写在 DEVELOPMENT_GUIDE 里
   作为编码规范第一条。
3. **显式状态机，不要隐式 async**：对冲执行流程中有太多分支（借币失败、单腿成交、
   HTTP 503），隐式协程管理状态是不可调试的。用枚举+转换表，每个状态有 on_enter/
   on_exit 钩子和超时。
4. **适配层和策略层之间用抽象接口隔离**：Binance API 会变，策略逻辑不应该因为
   API 变了就要改。适配层只做 HTTP 封装，策略层只依赖抽象接口。
5. **接口发现文档先行**：Phase 2 开工前写好 API Discovery Plan 并由人审阅。
   盲写适配器代码的调试成本是事前规划的好几倍。
6. **记账模型 Phase 1 定义函数签名和测试向量**：即使 Phase 1 不算真实费用，
   也要用已知的示例数据写出会计函数的预期输出。Phase 2 拿真实 fill 数据验证。
7. **WebSocket 留给 Phase 3**：Phase 2 先通过 REST 接口确认所有账户和订单行为
   正确，Phase 3 才引入 WS 实时推送。REST 行为错了，WS 推送的数据也一定错。
8. **Fake UI 现在就要对齐后端数据模型**：Phase 1 不做 React 迁移可以，但静态
   数据的 JSON 字段名必须与 Pydantic model 的字段名一致。避免 Phase 2 集成时
   才发现前端和后端各说各话。
9. **平仓 PRD Phase 2 前补充**：不补充的话 Phase 3 实盘测试无法闭环，因为没有
   退出路径。
10. **本稿为独立方向稿，不是最终结论**：按 Harness 流程，五份方向稿经 GPT/Codex
    合成为一份方向文档，用户批准后才进入开发。我对上述判断负责，但最终由用户拍板。

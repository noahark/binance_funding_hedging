# 平仓任务建卡与发单前预检瘦身方案（v1，待 Opus 5 计划评审）

- **日期**：2026-08-09
- **状态**：仅方案，未实现、未授权实盘代码改动
- **触发现象**：平仓任务卡 `a93405ae-2874-4e77-84eb-c0204e42cc7c` 创建后等待了一段时间
- **目标**：平仓建卡不再等待交易所只读 API；缓存充足时，发单前也不产生额外实时查询
- **风险路由**：`HIGH_RISK`。本方案改变订单发送前的安全边界，实施前必须先通过独立、跨 provider 的只读计划评审
- **计划作者**：Codex / OpenAI
- **计划评审目标**：Opus 5 / Anthropic，由 Human 启动独立终端
- **源码基线**：`dc356cd7f6acdc8502cd6caa44a48f6e3c760cac`

---

## 1. 一句话结论

采用“**建卡零外部 API，发单前最小缓存门，交易所失败暂停作最后兜底**”：删除平仓创建路径的实时探测和重复余额读取；保留缓存交易规则、方向性余额、合约持仓三项发单前事实；只有正向平仓确实需要从统一账户补币到普通现货账户时，才允许发生必要的实时查询和划转。

不采用“完全裸发两腿、任一腿失败后再暂停”作为默认方案，因为两腿并发而非原子提交，一腿可能已经成交，暂停无法撤销该腿。

## 2. Human 目标与本方案边界

Human 的目标：

1. 点击平仓来自已展示的活跃持仓周期，建卡不必重复证明两腿存在。
2. 正向平仓卖现货，不需要 USDT，不应查询无关余额。
3. 单双向持仓模式是固定运行前提，不在每张平仓卡重复查询。
4. 限频预读、无意义估价和前后端重复校验应删除。
5. 尽量把异常交给任务卡暂停，降低资源和时间成本。

本方案接受这些目标，但保留一个安全边界：**缓存读取不是昂贵的实时 API，也不是对浏览器的重复信任；它是在两腿并发发送前避免明显单腿拒单的最低成本。**

## 3. 已确认的当前事实

### 3.1 建卡路径会串行进入多个可能退化为实时 API 的读取

`backend/hedge_open_tasks/service.py::create_task` 当前顺序是：

1. 参数、本地活跃周期校验；
2. `check_symbol_legs`；
3. `get_snapshot`；
4. `compute_preflight`；
5. 落库并返回任务卡。

`get_snapshot` 会组合：现货/合约交易规则、统一账户余额、持仓模式、PAPI 限频、现货价格；正向平仓固定走 `regular_spot` 时还会读取普通现货 USDT、普通现货限频、普通现货 base free。缓存未命中、过旧或数据形状不合格时，读取会按顺序退化为实时 API；单次网络超时上限是 10 秒。

`check_symbol_legs` 与后续过滤器读取在缓存未命中时还可能重复取得 exchangeInfo。

### 3.2 两腿并发，不是原子事务

`backend/services/live_hedge_executor.py::dispatch` 用两个线程同时发送现货腿和合约腿，任一腿不等待另一腿结果。合约平仓腿带 `reduceOnly=true`，只能防止合约反向开仓，不能保护现货腿。

因此：

- 现货腿成交、合约腿因超量或参数错误被拒时，任务暂停后仍留下现货单腿变化；
- 合约腿成交、现货腿因余额或路由问题被拒时，任务暂停后仍留下合约单腿变化；
- “失败后暂停”只能阻止下一次尝试，不能回滚已经成交的一腿。

### 3.3 正向和反向平仓的资金要求不同

| 持仓方向 | 平仓现货腿 | 路由 | 发单前真正需要的资金事实 |
|---|---|---|---|
| `forward` | SELL base | `regular_spot` | 普通现货账户 base free；不足时可能需要统一账户→普通现货划转 |
| `reverse` | BUY base | `papi_margin` | 统一账户 USDT `crossMarginFree` |

所以“平仓不需要 USDT”只对 `forward close` 成立；`reverse close` 仍需要 USDT。

### 3.4 当前前端检查不能替代正确的钱包检查

`frontend/index.html::requestHedgeCloseConfirm` 目前只在 `direction === 'forward'` 时检查：

- `unified_balance >= single_amount × target_n`；
- `abs(um_position_amt) >= single_amount × target_n`。

存在三个口径差异：

1. `reverse close` 当前完全没有前端余额和合约持仓检查；
2. 前端 `unified_balance` 来自 base 资产的 `total_balance`，不是正向平仓实际卖币钱包的普通现货 `free`；
3. 浏览器快照可能过期，也可以绕过页面直接调用创建接口。

因此前端检查只作为交互提前提示，不作为服务端订单安全事实。

### 3.5 当前正向平仓余额门已经有“缓存充足即零网络”能力

`backend/hedge_open_tasks/service.py::_ensure_close_spot_balance` 当前在普通现货缓存显示单次卖量充足时直接放行，不调用交易所；不足或未知时才实时确认，并在需要时划转。

这项既是余额门，也是必要的资产备位动作，不能与纯展示校验一起机械删除。但它与 `get_snapshot` 中的普通现货 base free 读取重复，且当前只按 `single_amount` 备位，没有覆盖 `target_n` 的计划总量。

### 3.6 已知 1000x 合约自动平仓不安全

`PROJECT_STATE.md` 已记录：1000x 乘数合约的现货数量与合约张数不是同一量纲，当前执行器却向两腿发送同一个 `q_common`。本方案不实现换算，也不得因“平仓自由化”把这类任务发送到交易所。

## 4. 问题 3—9 的处置结论

| 编号 | 当前检查 | 整改结论 | 实时 API | 最终保留位置 |
|---|---|---|---|---|
| 3 | 两腿存在性探测 | 平仓建卡删除独立探测 | 删除 | 发单前从同一份缓存 exchangeInfo 取得两腿记录；缓存确认缺腿则不发单 |
| 4 | 状态、step、min/max qty、minNotional | 不删除纯计算；删除平仓实时回退 | 删除 | 发单前缓存过滤器计算 `q_common` 并校验两腿 |
| 5 | 统一账户余额 | `forward close` 删除 USDT 检查；`reverse close` 保留服务端缓存 USDT 检查 | 缓存命中时删除 | 仅反向平仓发单前 |
| 6 | 单双向持仓模式 | 平仓不再逐卡/逐次查询；继承原开仓任务固化值，缺失时按已批准的一向仓前提使用 `BOTH` | 删除 | 平仓任务固化字段 |
| 7 | PAPI/Spot 限频预读 | 平仓路径完全跳过；真实 429/418 和 `Retry-After` 继续由发单结果处理 | 删除 | 交易所真实响应后的既有暂停/退避 |
| 8 | 现货估价 | 删除实时价格读取；缓存价格只用于 minNotional 和反向平仓 USDT 需求计算 | 删除 | 发单前 `price_map` 缓存 |
| 9 | 普通现货 USDT、限频、base free | 删除普通现货 USDT和限频；删除 snapshot 的重复 base free 读取 | 仅必要备币分支允许 | `forward close` 首次发单前 `_ensure_close_spot_balance` 成为唯一 base 余额/划转入口 |

说明：本轮只改变 `close` 路径。`open` 路径的持仓模式、余额、路由和其他既有安全合同不顺手修改；全局未消费的限频字段/客户端方法可在行为稳定后另做机械删除，避免把开仓变化夹进本次资金路径评审。

## 5. 目标流程

### 5.1 创建平仓任务卡：零外部请求

顺序固定为：

1. JSON、字段白名单、币种、方向、模式、正数数量、整数次数校验；
2. SQLite 查询活跃周期；
3. 从周期首个开仓任务继承 `spot_symbol`、`spot_base_asset`、`symbol_match_type`、`position_side_mode`；
4. 创建 `running` 任务并立即返回。

明确跳过：

- `check_symbol_legs`；
- `get_snapshot`；
- 余额、价格、持仓模式、限频实时读取；
- 创建阶段的 `q_common` 计算。

现有 schema 已允许任务的 `q_common`、`position_side_mode` 和 preflight snapshot 暂为空；真正发单前仍由 fresh preflight 生成 attempt 的不可变值，不新增 schema、状态或恢复链。

### 5.2 真正发单前：缓存优先的最小门

仅在任务实际准备发送下一对订单时执行，顺序为：

1. **已知不支持类型**：`symbol_match_type == multiplier_strip_alias` 时暂停且零 POST，维持人工去交易所平仓的现行限制；
2. **缓存市场事实**：从 `group_b_public` 读取两腿记录和过滤器，从 `price_map` 读取价格；close 路径禁止退化为实时 exchangeInfo/ticker；
3. **数量计算**：使用 Decimal 计算两腿共同合法的 `q_common`，校验交易状态、step、min/max qty、minNotional；
4. **缓存合约持仓**：从 `um_positions` 读取该 symbol 的一向仓 `positionAmt`，确认绝对持仓量不少于本任务尚未发送的计划总量；
5. **方向性资金门**：
   - `forward close`：进入唯一的普通现货 base 备位入口；
   - `reverse close`：使用 `unified_balances` 缓存的 USDT `crossMarginFree` 校验剩余计划买入需求；
6. **持久化 attempt**：写入本次 `q_common`、position mode、过滤器/路由快照和两个 client order ID；
7. **并发发送两腿**；
8. **结果兜底**：拒单、限频、状态未知继续沿用现有暂停和 reconcile；不自动补腿、不自动反向修复。

缓存缺失、过期或形状错误时，任务在任何 POST 前按既有 `preflight_incomplete` 语义暂停并写中文根因；**不为了补齐预检而同步请求交易所**。缓存新鲜度沿用 SnapshotService/现有 preflight 的单一 TTL 语义，不新增第二套“60 秒”魔法数字。

### 5.3 正向平仓唯一允许的必要实时动作

`forward close` 固定从普通现货账户卖 base。首次发单前：

1. 计划备位量按 `q_common × 尚未发送次数` 计算；若重排实现困难，可使用更保守的 `single_amount × target_n`，但评审必须确认多转零头的可接受性；
2. 普通现货缓存显示 free 足够计划总量：直接放行，零网络；
3. 缓存不足或未知：允许实时确认普通现货 free；
4. 实时仍不足：确认统一账户同币可划转量并只划差额；
5. 任一步失败：发单前暂停，零订单 POST。

这不是为了“多做校验”，而是让普通现货账户实际具备可卖资产。删除它会把已知的 `spot insufficient / perp filled` 单腿风险重新暴露出来。

本轮不改变划转端点、方向、异常不重试、Human 授权边界和审计日志；只消除重复读取并把备位量与计划总量对齐。

### 5.4 平仓完成核实保持不变

尝试次数用完后，`_verify_close_flat` 仍实时查询交易所 UM 持仓：

- 合约已归零：关闭周期并写结算日志；
- 合约仍有仓：部分平完成，周期保持开启；
- 查询失败：暂停，不把“查不到”当成“已平完”。

该读取决定不可逆的周期关闭事实，不属于本次性能瘦身范围。

## 6. 前端策略

前端继续负责：

- 周期已关闭/无周期时禁用按钮；
- `single_amount` 正数格式；
- `target_n >= 1` 整数；
- 确认弹框展示方向、单次量和计划次数。

当前 forward-only 的余额/合约持仓检查不再被文档描述为“后端同口径权威校验”。实施有两个可选最小方案，计划推荐 A：

- **A（推荐）**：保留现有页面检查作为提前提示，但后端不信任其结果；修正文案和注释，明确它是约 60 秒缓存、可能过期。
- **B**：删除页面的资金硬拦截，只保留服务端正确钱包缓存门。仅当实际出现前端误拦时再做，当前不扩大本轮文件范围。

本轮不新增前端 API、不增加新的账户字段、不做前端防重。

## 7. 预计实现边界

### 必须修改

| 文件 | 最小职责 |
|---|---|
| `backend/hedge_open_tasks/service.py` | close 建卡跳过外部预检；继承 position mode；把 close 最小缓存门和 forward 备位放在 attempt/POST 前；计划总量对齐；1000x 暂停 |
| `backend/services/hedge_preflight_provider.py` | close 使用 cache-only 数据装配；跳过 position-mode/rate-limit/无关钱包读取；禁止 close 缓存 miss 后实时回退 |
| `backend/hedge_open_tasks/domain.py` | 复用现有过滤器和 `q_common` 计算；允许 forward close 的资金门由 service 唯一负责，避免 snapshot 重复 base 检查 |

### 按测试落点修改

| 文件 | 验证范围 |
|---|---|
| `backend/tests/test_hedge_service.py` | close create 零网络、open 行为不变、暂停语义 |
| `backend/tests/test_hedge_preflight_provider.py` | close cache-only、方向性数据读取、零实时回退 |
| `backend/tests/test_hedge_cycle_close.py` | forward/reverse、总量备位、UM 持仓门、1000x 零 POST、最终 flat 核实保持 |

### 实施收口时同步

- `docs/product/PRD.md`：把“每对订单前实时验证 account/position mode/rate limit”改为 open/close 分流后的真实合同；
- `docs/planning/DECISIONS.md`：记录 Human 接受的 close 缓存与固定 position-mode 前提；
- `docs/planning/hedge-open-position-cycle-v1.md`：对 §12 增加被新决定取代的指针，不重写历史设计记录；
- 若 API 响应字段和状态不变，`docs/api/public-market-contract.md` 无需修改，但收口模型必须重新核对。

### 明确不改

- open 任务预检、开仓 USDT 预划转和路由核验；
- SQLite schema、任务状态词汇、scheduler、client order ID；
- 两腿并发模型；
- 自动补腿、自动回滚、自动借币/还币；
- 1000x 腿量换算；
- final flat 的实时交易所核实；
- 实盘 gate、凭据、服务进程和 live DB。

## 8. 验收标准

### 8.1 建卡

1. close create 的所有 public/private 网络读取 mock 均设置为“调用即失败”时，已有活跃周期仍返回 `201`；
2. close create 的网络读取调用数为 0；
3. 无活跃周期、非法数量、非法次数仍由后端拒绝；
4. open create 的既有预检、划转和测试行为逐字不变；
5. close 继承原任务的现货身份和 position mode；origin 缺失沿用现有 warning/fallback，不新增恢复链。

### 8.2 缓存充足的发单前路径

1. forward close：group_b、price、um_positions、spot_balances 缓存充足时，除两笔订单 POST 外无 preflight GET；
2. reverse close：group_b、price、um_positions、unified_balances 缓存充足时，除两笔订单 POST 外无 preflight GET；
3. 不调用 position-mode、PAPI rate-limit、Spot rate-limit、Spot USDT API；
4. attempt 持久化的 `q_common`、position mode、route、filter fingerprint 完整且在 POST 前写入。

### 8.3 发单前暂停

以下每一项都必须断言：任务暂停/停止语义正确、attempt 数不增加、两腿 POST 都是 0：

1. 市场缓存缺失/过期/坏形状；
2. 任一腿不存在或不在 `TRADING`；
3. 数量低于最小量、高于最大量或不满足 minNotional；
4. 合约缓存持仓小于剩余计划平仓量；
5. reverse close 缓存 USDT 不足；
6. forward close 必要备位查询或划转失败；
7. 1000x multiplier close。

### 8.4 forward 备位

1. 普通现货 free 足够 `q_common × target_n`：零查询、零划转；
2. 普通现货不足、统一账户 base 足够：只划差额一次，然后允许发单；
3. 统一账户 base 不足：暂停，零订单；
4. `target_n > 1` 时备位覆盖计划总量，不再只覆盖第一笔；
5. paused/resume 不重复盲划转，沿用实时确认后只补差额的既有语义。

### 8.5 交易所结果和最终核实

1. 任一腿拒单/限频/状态未知：沿用现有 reconcile 和暂停；不得自动发送补偿订单；
2. 合约 `reduceOnly=true` 保持；
3. 次数用完后仍仅执行一次实时 UM flat 核实；
4. flat/open/failed 三分支和周期关闭语义不变。

### 8.6 回归证据

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests -q -p no:cacheprovider
node frontend/self-check.js
git diff --check
```

另需一组可计数 fake client 测试，直接证明 close 创建和“缓存充足的首次派发”没有任何预检 GET；仅断言耗时不足不能替代网络调用计数。

## 9. 已接受取舍与剩余风险

1. **接受缓存窗口**：余额、价格和合约持仓可能落后于交易所；Human 不在建卡到发单间手动改仓位/钱包/position mode 是运行前提。
2. **不接受明显可预防的单腿风险**：缓存已经显示数量/余额不足时，不把订单发出去试错。
3. **交易所状态仍可能在缓存后变化**：即使缓存通过，一腿仍可能因市场变化或权限问题被拒；任务暂停但可能已有另一腿成交，Human 必须在交易所核对并人工处理。
4. **position mode 不再逐卡确认**：若 Human 改为双向持仓，合约腿可能拒单而现货腿成交；恢复这项查询的 reopen trigger 是任何 position-mode 配置变更或相关交易所拒单。
5. **缓存读取失败不再同步自愈**：任务会快速暂停而不是等待 API；Human 可等待后台快照刷新后恢复。
6. **forward 必要划转仍可能等待**：这是让普通现货账户具备可卖资产的执行步骤，不是可删除的展示校验。
7. **1000x 不自动平仓**：在腿量换算完整落地并经独立高风险评审、最小额度实盘验证前保持零 POST。

## 10. Opus 5 计划评审任务

请作为独立、只读的 `HIGH_RISK` 计划 Reviewer，核对源码基线和本方案，不修改代码、既有文档、配置、数据库、服务、gate 或凭据，不运行任何实盘请求。

重点回答：

1. close create 跳过整个 snapshot 后，现有 nullable 字段和 dispatch fresh-preflight 是否足以安全承接，是否存在 worker 使用建卡快照的遗漏入口；
2. cache-only close 是否真的能封住所有 public/private 实时回退，包括 `check_symbol_legs`、position mode、两个 rate-limit 和 regular-spot 三项读取；
3. forward/reverse 的钱包、方向反转、路由和 `required` 口径是否正确；
4. 把 forward base 余额/划转收敛为单一 service gate 是否存在绕过或重复，计划总量是否应使用 `q_common × remaining`；
5. `um_positions` 缓存门能否覆盖两腿并发下最危险的“合约 reduceOnly 拒绝、现货成交”，且不会把一向仓正负号读反；
6. 缓存缺失即暂停、禁止同步 API 回退是否会造成无法恢复的卡死，现有恢复入口是否足够；
7. 1000x close 零 POST 边界是否完整；
8. 文件范围、测试和活文档更新是否是最小充分集合，是否误改 open 行为。

若方案可实施，返回明确 `ACCEPT（接受）`；若存在会导致错误订单、单腿敞口、错误钱包/数量、不可恢复暂停或必要证据缺失的问题，返回 `REWORK（返工）`，给出源码锚点和最小修改要求。新假设场景须满足 `AGENTS.md` §1 Scenario Admission。

评审完成后只允许**新建**结果文件：

`docs/planning/close-task-preflight-simplification-2026-08-09.review-opus5-result.md`

若该文件已存在，不得覆盖。结果文件应包含：Reviewer/provider 隔离披露、逐项结论、源码证据、发现及范围分类、明确 verdict 和最小修复要求。计划评审不授权实现、提交、推送、部署或实盘操作。

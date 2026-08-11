# Reverse Position Drift — 最小修复计划

## 结论与关卡

- 缺陷成立：`reverse`（借币卖现货 + 开多合约）的现货腿卖出后，统一账户可用余额可为零，但借款本金仍为正；现有 `drift` 把“账户持有量小于本地卖出量”误当成不一致。
- 修复限定为后端展示/校验计算与其数据契约，不改变订单、借币、还款、划转、预检、闸门、凭据、部署、服务控制或任何实盘行为。
- 本任务按 `HIGH_RISK` 处理，因为它改变持仓与借款含义。实现前必须由 fresh Kimi（provider `moonshot`）完成跨 provider 只读计划评审并明确 `ACCEPT`；当前不得实现。
- 证据基线：`status.json.base_sha = 7194876e61c037d238d0e3d621a094d7dd3a6e43`。当前 `HEAD` 相对该 SHA 仅增加本阶段控制文件，产品代码相同。

## 当前链路与根因

| 环节 | 代码锚点 | 当前事实 |
| --- | --- | --- |
| 原始账户读取 | `backend/services/private_client.py:584-606` | `fetch_unified_balances()` 原样返回 `GET /papi/v1/balance` 列表；无需改 transport。原始账户字段集合已有 `crossMarginBorrowed`、`crossMarginFree`、`crossMarginLocked`、独立的 `crossMarginInterest`（`backend/tests/test_private_account_v1.py:1136-1145`）。 |
| 快照刷新/组装 | `backend/services/snapshot_service.py:1430-1450`、`:934-944` | worker 缓存原始统一账户列表并交给 `assemble_private_account()`；无需增加请求、缓存或刷新状态。 |
| 私有账户投影 | `backend/domain/snapshot.py:1268-1297` | 目前只投影 `crossMarginBorrowed -> cross_margin_borrowed` 与 `crossMarginFree -> cross_margin_free`；`crossMarginLocked` 在这里丢失。 |
| 快照契约 | `schemas/api/public-market/snapshot.schema.json:540-580` | `balances_unified[]` 已允许 borrowed/free，但 `additionalProperties: false`，所以新增投影必须声明 `cross_margin_locked`。 |
| 持仓合并 | `backend/hedge_open_tasks/domain.py:1944-1967`、`:2042-2102` | 任务固化现货资产身份优先，随后用已发布的 spot/unified 行建立账户索引；借款仍是账户级字段。 |
| 错误判定 | `backend/hedge_open_tasks/domain.py:1992-2022` | 所有方向都逐行比较 `普通现货 free+locked + unified total_balance < 本地 spot_qty`。该口径适合现有 forward 弱告警，却不代表 reverse 已卖出的借款数量。 |
| API 输出 | `backend/app/server.py:1322-1343`、`:1449` | `GET /api/hedge-open-positions` 零上游读取快照，调用纯函数 `merge_positions()`，原样返回既有 `drift` 布尔字段；server 无需改。 |
| 前端消费 | `frontend/index.html:5270-5275`、`:6361-6380` | 前端从独立 positions API 读行，只在 `p.drift` 为真时显示“本地记录与实际不一致”；无需读取新字段或改 UI。 |

根因不是余额抓取失败，而是方向语义错配：forward 的本地 `spot_qty` 表示应仍持有的现货，reverse 的本地 `spot_qty` 表示已卖出的现货数量，不能用同一“持有量”公式判断。

## 唯一 reverse 实际现货敞口口径

对同一解析后现货基础资产 `a`，定义：

```text
B_a = cross_margin_borrowed(a)                 # 借款本金
F_a = cross_margin_free(a)                     # 借入后仍可用、尚未卖出的数量
L_a = cross_margin_locked(a)                   # 已锁定、尚未成交卖出的数量
R_a = Σ active local reverse rows' spot_qty(a) # 本地填单账本的剩余卖出数量
A_a = max(B_a - F_a - L_a, 0)                  # reverse 实际现货空头敞口
reverse_drift_a = (R_a - A_a) > R_a × 0.01
```

规则如下：

1. `B_a/F_a/L_a/R_a` 全部用 `Decimal`，禁止 float。原始账户量和本地 `spot_qty` 都是非负基础资产数量；`position_qty` 的方向符号不参与计算，也不得对坏值取绝对值。
2. `crossMarginInterest` 与持仓行的 `borrow_interest` 均不进入公式。当前原始契约把利息与 `crossMarginBorrowed` 分列；开仓数量只比较借款本金，利息增长不得制造持仓漂移。
3. `F_a` 与 `L_a` 都从本金中扣除：借到但仍 free，或挂卖单后仍 locked，均尚未形成已卖空敞口；成交后两者下降，`A_a` 才增加。差值小于零只钳到零，不反转符号。
4. `R_a` 按账户资产聚合，而不是逐行拿同一账户借款重复比较。聚合对象是所有 `direction=reverse`、未关闭且有本地记录的 merged 行，资产解析顺序保持现状：任务固化 `spot_base_asset` > snapshot `asset_map` > `_merge_base_asset` 回退。一个资产组只得一个 verdict，并回填到该组每一条本地 reverse 行；`no_task` 行没有本地数量，不参与聚合且 `drift=false`。不把账户借款臆造分配到具体周期。
5. 精度带复用现有 `_EXPOSURE_IMBALANCE_TOLERANCE = Decimal("0.01")`，不新增数值常量。只有短缺严格大于本地聚合量的 1% 才报警；等于或小于 1% 不报警。它仅吸收数量精度/舍入，代价是最多 1% 的短缺可能成为假阴性，不代表业务允许 1% 不平衡。
6. 任一必要账户字段缺失、空、不可解析、非有限或为负，任一本地组内 `spot_qty` 无效，账户未验证，或没有对应统一账户资产行时，该 reverse 资产组 `drift=false`，不以零代替、不部分求和、不抛异常。这沿用当前“未知时不制造不一致声明”的 fail-closed 语义；`drift=false` 只表示“本轮没有可证明的告警”，不表示已经对账，可能产生假阴性。
7. forward 完全保留当前路径和严格比较：`held = regular spot (free+locked) + unified total_balance`，仅当账户可读、`spot_qty > 0` 且 `held < spot_qty` 时 `drift=true`。不得把 reverse 公式、1% 带或 locked 字段扩散到 forward。

当前字段足以区分本任务要求的三态：借款本金由 `crossMarginBorrowed` 给出，未卖出的可用量由 `crossMarginFree` 给出，挂单锁定但未成交量由 `crossMarginLocked` 给出，利息另列。若实现或计划评审发现 Binance 当前响应不再提供其中任一字段，或这些字段不能证明上述含义，则停止实现；缺失证据具体为同一次 `GET /papi/v1/balance` 对目标资产返回的 borrowed/free/locked 字段及其官方字段语义，不得用 `totalWalletBalance`、普通现货余额或利息猜测替代。

## 最小实现步骤与文件边界

1. `backend/domain/snapshot.py`
   - 在现有 unified row 投影中加入原样 `crossMarginLocked -> cross_margin_locked`；上游键缺失时明确为 `None`。
   - 不改变估值、排序、总资产、借款价值或 warning 逻辑。
2. `schemas/api/public-market/snapshot.schema.json`
   - 在 `balances_unified[].properties` 声明 additive/optional 的 `cross_margin_locked`（decimal string 或 null），说明它是 PM full-cross locked quantity、只供展示校验、不进入总值。
   - producer 每行都发该键；schema 保持 optional，避免破坏同一 v1 契约下已冻结、缺该 additive 字段的旧样本。不得改 schema version。
3. `backend/hedge_open_tasks/domain.py`
   - 保持 `_merge_build_row` 的 forward 分支逐字等价；reverse 先不做逐行 held 比较。
   - 在现有 `merge_positions()` 内、merged 行齐备后、排序前，直接建立 reverse 资产组的本地总量/有效性和账户实际敞口 verdict，再回填既有 `drift`。不新增 service、模块、类、状态或通用抽象。
   - 不把 free/locked 新增为 positions 行字段；它们只在 merge 内消费。因此 positions API 字段集合与前端均不变。
4. 测试文件：
   - `backend/tests/test_private_account_v1.py`：locked 原样投影、缺失为 null、snapshot schema 正/反例及 interest 分离。
   - `backend/tests/test_positions_merge.py`：公式、聚合、容差、符号、无效输入与 forward 回归的纯函数矩阵。
   - `backend/tests/test_hedge_api.py`：至少一条 reverse 场景穿过 `GET /api/hedge-open-positions`，证明 API 输出既有 `drift` 布尔值且 `_POSITION_KEYS` 不增加字段。
5. `docs/api/public-market-contract.md`
   - 在 private-account unified-balance 章节登记 `cross_margin_locked`；在 hedge-position/drift 章节固化方向分支、账户级 reverse 公式、1% 精度带、利息排除、无效数据语义和 `drift=false` 非对账保证。

实施只可修改以上 7 个文件。明确不修改 `backend/services/private_client.py`、`backend/services/snapshot_service.py`、`backend/app/server.py`、`frontend/index.html`，也不新增 endpoint、依赖、兼容层、数据库字段、状态、恢复流程或文件。

## 可执行测试矩阵

以下案例均用同一 base asset，除 forward 回归外均为 active local reverse 行；预期 `drift` 是 positions API 最终布尔值。

| 场景 | 关键输入 | 预期 |
| --- | --- | --- |
| JST-style 借入并卖完 | `R=100, B=100, F=0, L=0` | `A=100`，`drift=false`。这是本缺陷的主回归。 |
| 借入但未卖 | `R=100, B=100, F=100, L=0` | `A=0`，`drift=true`。 |
| 已挂卖单、仍锁定 | `R=100, B=100, F=0, L=100` | `A=0`，`drift=true`；证明 locked 不能算已卖。 |
| 部分成交 | `R=100, B=100, F=30, L=0` | `A=70`，短缺 30%，`drift=true`。 |
| 容差边界 | `R=100, A=99`；另测 `A=98.999` | 恰好 1% 为 false；严格超过 1% 为 true，全程 Decimal。 |
| 利息增长 | 保持 `B/F/L/R`，只把 raw `crossMarginInterest` 或统计 `borrow_interest` 从 0 改为正数 | verdict 不变；利息不进入开仓数量。 |
| 同资产多行 | 两个 reverse 行 `R1=60,R2=40`；先给 `A=100`，再给 `A=70` | 首次两行均 false；第二次两行均 true，证明只比较账户级 `ΣR=100`，不重复消费账户借款。 |
| forward 回归 | 现有 regular spot + unified total 与 forward `spot_qty` 的大于、等于、小于三例；同时放入任意 B/F/L | 结果与当前严格 held 比较完全一致，reverse 字段不影响。 |
| 缺失/坏字段 | 分别令 B/F/L 缺失、空、文本、NaN/Infinity、负数；另测组内 `spot_qty` 无效和账户未验证 | 不抛异常，相关 reverse 组全部 `drift=false`，不以零或部分输入计算。 |
| API/前端契约 | 通过 server endpoint 取得 reverse 行；静态确认 `frontend/index.html:6379` 仍只读 `p.drift` | positions 行键集不变，bool 正确，frontend 零改动。 |

实现者的验证命令：

```text
python3 -m pytest backend/tests/test_private_account_v1.py backend/tests/test_positions_merge.py backend/tests/test_hedge_api.py
```

若仓库已有针对 snapshot schema 的更窄测试选择器，可先跑窄集，但交付前仍须跑上面三文件全量；不得启动服务或调用 live API。

## 非目标与停止条件

- 不修 reverse 自动平仓组合保证金风险，不改任何 close/open 执行、borrow/repay/transfer 或 preflight 路径。
- 不把 `drift` 升级为交易所对账，不新增 unknown 枚举、提示、端点、轮询、日志、恢复或操作职责。
- 不处理 1000x 腿量换算；现有冻结身份只用于资产对齐。
- 不做实盘验证、部署、服务重启、闸门或凭据操作。
- Kimi 计划评审未明确 `ACCEPT`、状态未由 Bookkeeper 正式转入实现任务、或评审认定 B/F/L 语义证据不足时，均停止，不准备/启动实现。

下一关任务包：`reports/agent-runs/2026-08-11-reverse-position-drift-v1/reverse-position-drift-plan-review.dispatch.md`。

# 20-fake-ui-implementation —— fake-ui-positions-and-cards-v1 实现报告

- task_id: `fake-ui-positions-and-cards-v1`
- target_model: `claude_glm`（zhipu_glm）
- base_sha: `87ff428a22052a050f3a2b0b86a5650e62bda110`
- 实现：2026-07-31 21:00 CST
- 状态：`dispatched` → `reported`（未提交、未合并、未推送；本 dispatch 未授予提交职责）

## 0. 边界与改动范围

仅改动 dispatch 允许的两个文件；后端目录 `backend/` 全程零改动。

```text
 frontend/index.html    | 454 ++++++++++++++++++++++++++++++++++++++++++++++++-
 frontend/self-check.js |  36 +++-
 2 files changed, 488 insertions(+), 2 deletions(-)
```

`git diff --name-only | grep backend` → 无输出（后端未触碰）。

## 1. 打开预览的点击路径（acceptance #1）

1. 进入「开单任务」视图（侧栏点 `开单任务`，即 `nav-hedge-tasks`）。
2. 滚到 `开单任务` 面板底部（位于「任务列表 / 开单 attempt 时间线」之下、「开单日志」tab 之外）。
3. 点击按钮 `🧪 假数据 · 预览（设计探针，默认关闭）`。

点击后：按钮文案变为「收起假数据 · 预览」；其下展开虚线红框区块，顶部带 `假数据 · 预览` 红色徽标与「本区块所有数字均为脚本内假数据常量，不发起任何网络请求，不代表任何真实账户」说明。再次点击收起。

**关闭状态下与改动前一致**：区块默认 `hidden`；页面上唯一新增的常驻元素是那一个开关按钮（带「假数据」「默认关闭」字样，不可能被误读为真实数据）。预览内容（合并持仓表 / 任务卡 / 六场景）仅在展开时才进入 DOM。

## 2. 两个真实渲染函数逐字未变（acceptance #2）

预览全部由新增独立函数渲染，不复用、不包裹、不修改这两个真实函数：

- 新增合并表：`renderHedgeFakeMergedPositionsTable(scenario)`
- 新增任务卡预览：`renderHedgeFakeTaskCardPreview()`
- 新增体组合：`renderHedgeFakePreviewBody()`
- 新增开关/场景绑定：`bindHedgeFakePreview()`

逐字核验（base_sha 与工作树函数体 `diff`，空输出 = 一致）：

```text
$ diff <(git show 87ff428:frontend/index.html | sed -n '/^      function renderHedgeTaskCard(task) {/,/^      }$/p') \
       <(sed -n '/^      function renderHedgeTaskCard(task) {/,/^      }$/p' frontend/index.html)
（空）→ renderHedgeTaskCard 逐字一致 ✓

$ diff <(git show 87ff428:frontend/index.html | sed -n '/^      function renderHedgePositionsSection() {/,/^      }$/p') \
       <(sed -n '/^      function renderHedgePositionsSection() {/,/^      }$/p' frontend/index.html)
（空）→ renderHedgePositionsSection 逐字一致 ✓
```

## 3. 零网络请求（acceptance #3）

假数据全部为脚本内常量（`HEDGE_FAKE_PREVIEW_SCENARIOS` / `HEDGE_FAKE_PREVIEW_51169_TEXT` / `HEDGE_FAKE_PREVIEW_PAUSE_REASON_ZH`）。开关、场景切换、渲染均不调用 `fetch` / `XMLHttpRequest`。自检第 98 块以 `fetchCallLog.length` 前后断言「打开预览零网络请求」通过；最末全局白名单块扫描全部 fetch 仍只含既有同源路由。

## 4. 合并持仓表与六场景（acceptance #4 / #5）

合并表以**真实合约持仓为骨架**（`um[]`），一行一个合约标的；任务记录中无对应持仓的标的单独追加成行。每行横向拼三源数据。点开预览后，顶部一排 6 个场景按钮可切换：

| 场景按钮 | key | 触发后能看到 |
|---|---|---|
| (a) 正常对冲仓 | `normal` | BTCUSDT/ETHUSDT：真实 SHORT 持仓 + 现货余额 + 全仓借款 + 任务两腿均价 + 价差率，三者对得上，含合计行 |
| (b) 真实有仓·无任务记录 | `no_task` | `1000PEPEUSDT`（1000x，手工 LONG）与 SOLUSDT：有真实持仓但无任务记录，成本类留空而非填零；1000PEPE 的现货余额挂在 `PEPE` 资产上、与 `1000PEPE` 不自动对齐（暴露倍率前缀不对齐） |
| (c) 有记录·交易所无仓 | `no_um` | BTCUSDT 仅来自任务记录，无 UM 持仓行 → 标「交易所无持仓（可能已强平/手工平）」，持仓事实列全 `—`，仅留任务腿均价 |
| (d) 单腿敞口 | `single_leg` | ETHUSDT：现货腿已成交、合约腿无持仓 → 行高亮（红底）+ 危险标记「单腿敞口：现货腿已成交，合约腿无持仓」 |
| (e) 数据拿不到 | `missing` | BTCUSDT 单行同时出现：合约均价 `—`（缺失）、强平价 `0`（币安无值返回）、全仓借款 `null`，三个「拿不到」标记并排 |
| (f) 完全空仓 | `empty` | 无 UM、无任务，空态文案 |

场景按钮含 1000x 倍率符号行（acceptance #5b 要求），位于场景 (b) 的 `1000PEPEUSDT`。

## 5. 占位零三分类（acceptance #6）

按 dispatch「关于占位零」实现，视觉上三类可区分：

| 分类 | 视觉 | 覆盖列 | 数据来源 |
|---|---|---|---|
| 真值 | 正常数字（盈亏带红绿色） | 未实现盈亏、仓位价值、数量、开仓价、标记价、强平价（非 0 时）、现货余额、全仓借款（非 null）、两腿均价、价差率、合计 | 真实合约持仓（A）/ 账户资产（B/C）/ 任务记录（D） |
| 暂无数据源 | 灰色斜体「暂无」 | 累计资金费、借币利息（行尾两列） | 后端为字面量 `"0"`（store.py:2050-2053），本轮不接数据源，**不画成 0.00** |
| 拿不到 | 淡灰 `—`（或忠实显示 `null`） | 合约均价缺失 → `—`；全仓借款 `null` → `null`；强平价币安返回 `"0"` → 显示 `0`（带 title「该仓当前无强平价」） | 真实契约缺失/币安 sentinel |

**注**：`price_pnl` / `net_pnl` 后端也是占位零 `"0"`，本预览未单列（与现有真实持仓表口径一致：净盈亏本轮不接）；合并表的「净盈亏」口径在真实实现时需 Human 决定是否单列——见 §9 风险。

## 6. 任务卡新规则预览（acceptance #7）

`② 任务卡预览（新规则·假数据）` 区块含：

1. **六原因对照表**：`consecutive_submission_failure` / `rate_limited` / `insufficient_balance` / `insufficient_margin` / `insufficient_available_qty` / `collateral_cap_full` 六行，每行标注「新规则：自动软删除（不再进入暂停）」与「旧行为：暂停 + 显示原因」。
2. **四张示例卡**（用新增 `fk-card` 形态，**非** `renderHedgeTaskCard`）：
   - `ORDIUSDT` collateral_cap_full → 已删除（虚线红框）+ 自动删除原因逐字冻结全文。
   - `SOLUSDT` rate_limited → 已删除 + 现行原因文案 + 「新规则下直接软删除」。
   - `BTCUSDT` 人工暂停 → `暂停` 徽标、无 pause_reason，与新规则自动删除可区分。
   - `ETHUSDT` 完成变体 → `完成` 徽标 + 在「已调度/已受理」基础上追加「**计划 10 次 · 实际成功 7 次**」。

**纯展示试画，不新增任何状态值，不改后端 done 语义**（Human 已决定本轮不处理 done 语义，此项仅供其决定要不要）。

## 7. 51169 文案逐字冻结（acceptance #8）

`collateral_cap_full` 的中文原因 = 后端 `COLLATERAL_CAP_FULL_REASON_ZH_TEMPLATE`（domain.py:1315-1324），`{asset}` 填 `ORDI`。程序化逐字比对（Python 渲染后端模板 vs 前端常量）：

```text
VERBATIM MATCH
```

未替换为「保证金不足」假事实——冻结文案中唯一含「保证金不足」之处是否定句「并非本账户保证金不足」，属逐字原文。自检第 98 块断言特征句段「已达币安平台级抵押金额上限」「追加资金无效」「并非本账户保证金不足」均存在。本预览未对该文案做任何追加（dispatch 允许追加但非必须）。

## 8. 前端自检（acceptance #9）

`node frontend/self-check.js` → `EXIT=0`，130 行全绿，原始输出存于同目录 `60-fake-ui-test-output.txt`（未改写为叙述）。新增断言块第 98：

```text
[PASS] 假数据·预览：默认关闭 + 开关可切 + 51169 冻结文案逐字渲染 + 打开零网络请求
```

**self-check.js 改动逐条说明**（dispatch 限定仅 a/b 两类，未放宽任何既有断言）：

- (b) 修复因新增 DOM 导致的既有断言失配：在静态 `ids` 列表追加 4 个 id（`hedge-fake-preview-toggle` / `-panel` / `-scenarios` / `-body`）。原因：脚本为 IIFE，`eval(script)` 时 `els` 构造与 `bindEvents()` 立即执行并对这些新元素调 `getElementById`，而 mock 的 `getElementById` 对未注册 id 抛 `未 mock 的元素` → 整个 eval 崩溃。注册为静态元素后既有断言全部恢复通过。**未删除/跳过/放宽任何既有断言。**
- (a) 为预览开关追加断言：新增第 98 块，核验默认 `hidden=true`、click 后 `hidden=false`、再 click 收起、51169 冻结文案逐字渲染、打开零网络请求、预览 body 不含真实任务卡 `data-hedge-task-id` 属性。全部为新增断言。

## 9. 真实接线时最可能出问题的地方（acceptance #10）

1. **符号/base asset 对齐（最高风险）**：合并表需把 `um_positions[].symbol`（`BTCUSDT` / `1000PEPEUSDT`）↔ 任务 `coin` ↔ 现货/统一账户 `asset`（`BTC` / `PEPE`）三方对齐。1000x 六币的 UM 符号带 `1000` 前缀而现货资产名不带，`normalize.py` 当前不做前缀剥离（scope-decisions §2.3 follow-up）。真实接线必须定一个权威的 base-asset 归一函数并在三处共用，否则会出现「有仓却对不上资产/任务」的假象。本预览用 `fkBaseAsset` 仅做 `去 USDT`，**刻意不剥离 1000**，以在场景 (b) 暴露该问题。
2. **`position_side` 大小写**：见下方 packet 勘误——真实契约是大写 `LONG/SHORT`，现有 `directionForPosition` 已按大写判。真实接线若新写合并逻辑，务必复用 `directionForPosition`，勿按 dispatch §A 的小写假设。
3. **占位零的口径**：后端 `accrued_funding` / `borrow_interest` / `price_pnl` / `net_pnl` 是字面量 `"0"`。真实接线若直接渲染会回到「全 0.00」假象。必须在前端按「有数据源才显示数字、否则暂无」分支，且后端补数据源时改的是真值而非占位零语义（关联 `PROJECT_STATE.md` DEC-2026-07-30-001 money-zero tripwire）。
4. **`liquidation_price` 的 `"0"` sentinel**：币安无强平时返回字符串 `"0"` 而非空/null。真实接线须把 `"0"` 当「无强平价」处理，勿当成价格为 0 参与任何计算或告警。
5. **全仓 vs 逐仓**：本项目是统一账户全仓，**没有**逐仓每币清算价/逐仓账户价值（scope-decisions §2.1）。真实接线不得为对齐参考脚本而虚构这些列；现货/杠杆腿的清算风险只能用账户级 `uniMMR`，且不得用账户级数值冒充每币数值。
6. **单腿敞口判定**：本预览按「forward 任务 + 现货均价存在 + 合约腿无 UM 持仓」判定单腿。真实接线的权威判定在后端 `pair_outcome=single_leg` 与 `leg_exposure`（见现有 `renderHedgeTaskCard` 的 `exposureLine`），前端合并表应消费后端判定而非自行重推，避免双源口径不一致。

## 10. 与参考脚本刻意不同之处

Human 参照的 `币安套费率策略，逐仓杠杆.js` 是**逐仓杠杆**（每币独立子账户），本项目是**统一账户全仓**。本预览因此刻意不照抄：

- 不画「逐仓账户价值 / 逐仓未实现盈亏」列（本项目无对应概念）。
- 清算价只给合约腿（`liquidation_price`）；现货/杠杆腿不给每币清算价，全仓风险只反映在账户级（本预览未画账户级 `uniMMR`，因合并表聚焦每币行；真实实现时账户级风险率建议放表外摘要，不冒充为某币的列）。
- 借币利息不挂在行上（本项目利息按资产查历史接口、未实时挂行；参考脚本的逐仓利息列无对应实时数据源）。

## 11. packet 勘误（dispatch §A 与真实契约的未记录冲突）

dispatch §A 把 `position_side` 标为 `"long" | "short"`（小写）。后端真实契约（`backend/domain/snapshot.py:894-895` `_infer_position_side`）返回**大写** `"LONG"` / `"SHORT"`，现有真实前端 `directionForPosition`（index.html:2106）也按大写 `'LONG'`/`'SHORT'` 判定，再退回 `position_amt` 符号。本预览按**真实契约的大写值**造假数据（如 `position_side: 'SHORT'`），以避免随后的 fake→真实接线漂移；dispatch §A 的小写写法是文档笔误，建议 Bookkeeper 在真实实现 dispatch 中更正。此为字段事实层面的对齐，未扩大实现范围、未触碰后端。

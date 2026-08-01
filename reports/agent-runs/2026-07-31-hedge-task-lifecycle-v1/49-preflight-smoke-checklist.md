# 49-preflight-smoke-checklist —— Task 1 合并前的只读真机冒烟清单

- 对象：交付 `ef53a025114933e8c472d9ae89f8ebfb35d19513`（Task 1 最终版）
- 依据：review-2 的发布就绪结论「**可合并，但须先完成本项**」（`48-` §3）
- 性质：**只读**。不下单、不碰凭证记录、不改开关、不写任务库
- 执行者：**Human**。按 `PROJECT_STATE.md` 的 live-risk 条款，任何 agent 不得控制服务
- 授权：本清单的执行需 Human 明确授权（`AGENTS.md` §3）

## 0. 执行前的安全前提（Bookkeeper 已核实，执行前请再确认一次）

| 项 | 当前事实 | 为什么重要 |
|---|---|---|
| 运行中任务 | **0 个**（`done` 14 / `paused` 6 / `stopped` 4 / `deleted` 1） | 调度只对 `running` 任务动作。零个 → 不派单、不消耗计划次数、不写新尝试记录 |
| `.env` 执行器 | `APP_HEDGE_EXECUTOR=live` | **必须显式覆盖为 `disabled`**，否则下单通道会被拉起 |
| 覆盖顺序 | `source .env` **之后**再覆盖 | 顺序反了会被 `.env` 盖回 `live` |
| 分支 / 代码 | `stage/2026-07-31-hedge-task-lifecycle-v1`，工作区代码即 `ef53a02` | 上次曾因分支被切走导致读不到文件 |

确认命令：

```bash
cd "/Users/ark/Desktop/ai code/funding_hedging"
git branch --show-current            # 应为 stage/2026-07-31-hedge-task-lifecycle-v1
git diff --stat ef53a02 HEAD -- backend/ frontend/   # 应为空
python3 -c "import sqlite3;c=sqlite3.connect('file:data/hedge-open-tasks.sqlite3?mode=ro',uri=True);print(list(c.execute(\"select count(*) from hedge_open_task where status='running'\")))"   # 应为 0
```

## 1. 运行 A —— 正常账户路径（私有通道开启）

```bash
cd "/Users/ark/Desktop/ai code/funding_hedging" && set -a && source .env && set +a && APP_HEDGE_EXECUTOR=disabled ./.venv/bin/python -m backend.app.server
```

打开 `http://127.0.0.1:8787`，看**对冲开单持仓**表，逐项核对：

| # | 检查 | 期望 | 对应 |
|---|---|---|---|
| A-1 | `RSRUSDT 正向` 的**合约均价** | **`0.001246`**（不是上次那个 `0.000623`） | G5 修复 |
| A-2 | 同行的**开单价差率** | 约 `+0.3%` 量级（不再是 `-100.0000%`） | G5 修复 |
| A-3 | 同行的**标记**列 | 出现「**均价不完整**」；均价单元格悬停有说明 | G5 标记 |
| A-4 | `MUUSDT` / `NOMUSDT`（交易所有仓、本地无记录）的**标记**列 | 出现「**无任务记录**」；悬停说明「手工单或任务卡已删」 | F3 修复 |
| A-5 | 同两行的**现货均价 / 合约均价 / 价差率** | 显示 `—`，**不再是 `0`** | F3 修复 |
| A-6 | `RSRUSDT 正向`（本地有记录、交易所无对应仓）的**标记**列 | 出现「**交易所无仓**」；悬停说明「可能已强平或手工平仓」 | F3 修复 |
| A-7 | **均价小数位** | 统一 8 位有效数字（不再出现 27 位那种） | G7 |
| A-8 | `RSRUSDT` 两行的**全仓借款** | 首行显示数值，另一行显示「同↑」并带悬停说明 | G6 |
| A-9 | **累计资金费 / 借币利息 / 净盈亏** | 一律「暂无」，**不是 `0.00`** | F2 |
| A-10 | 页面上有无**重复的持仓表**（旧 UM 子表是否已消失） | 只有一张合并表 | 验收 10 |

## 2. 运行 B —— 账户未就绪路径（关掉私有通道）

先停掉运行 A，然后：

```bash
cd "/Users/ark/Desktop/ai code/funding_hedging" && APP_HEDGE_EXECUTOR=disabled BINANCE_PRIVATE_CHANNEL_ENABLED=false ./.venv/bin/python -m backend.app.server
```

（不 source `.env`，因此不加载凭证、私有通道关闭 —— 这正是 `verified: false` 的路径。）

| # | 检查 | 期望 | 对应 |
|---|---|---|---|
| B-1 | 个人账户面板是否**整个消失** | **不应消失**。应显示「私有账户未读取」**并在其下方仍然渲染合并持仓表** | F1 修复（上一轮的阻塞项） |
| B-2 | 合并表里**本地记账行是否还在**（币种、现货均价、合约均价） | **在**。这是 D15 保住的成本基 | F1 + D15 |
| B-3 | 表内是否出现「**账户数据未就绪**」横幅 | 出现 | N2 |
| B-4 | 各**账户派生列**（仓位价值 / 持仓数量 / 开仓价 / 标记价 / 强平价 / 现货余额 / 全仓借款） | 显示 `—` 或空，**不显示编造的数字** | N2 |
| B-5 | **未实现盈亏** | 「暂无」，不是 `0.00` | F2 |
| B-6 | **标记列是否出现「交易所无仓」** | **会出现 —— 这是已接受的限制 F4。** 请确认它与 B-3 的横幅**同时出现**，记住这就是"不可信"的组合形态 | 限制 F4 |

**B-6 不是失败项**，是让你亲眼确认 F4 在界面上长什么样，以便日后辨认。Task 2 会修掉它。

## 3. 快照陈旧性（运行 A 期间观察）

| # | 检查 | 期望 |
|---|---|---|
| C-1 | 个人账户面板上的**更新时间**是否随刷新前进 | 前进 |
| C-2 | 若时间明显停滞（例如私有读中途失败），页面是否仍宣称数据为最新 | 记录实际表现。**这是评审列出的已知证据边界**，`verified: true` 只代表"曾成功获取过"，无过期闸门 |

## 4. 零交易副作用（两次运行结束后核对）

```bash
python3 -c "
import sqlite3
c=sqlite3.connect('file:data/hedge-open-tasks.sqlite3?mode=ro',uri=True)
print('任务状态:',list(c.execute('select status,count(*) from hedge_open_task group by status')))
print('尝试数:',list(c.execute('select count(*) from hedge_open_attempt'))[0][0])
print('腿数:',list(c.execute('select count(*) from hedge_open_leg'))[0][0])
"
```

| # | 检查 | 期望 |
|---|---|---|
| D-1 | 任务状态分布 | 与执行前一致（`done` 14 / `paused` 6 / `stopped` 4 / `deleted` 1），**无新增 `running`** |
| D-2 | 尝试数 / 腿数 | 与执行前一致，**无新增** |
| D-3 | 币安账户 | 无新订单（可自行在币安端确认） |

## 5. 统一账户现货余额匹配（限制 B 的实际表现）

| # | 检查 | 说明 |
|---|---|---|
| E-1 | 正向对冲行（现货买入）的**现货余额**列 | 很可能显示 `—`，因为对冲的现货腿买入的是**统一账户**，而该列读的是**经典现货账户**（限制 B）。**这不是本轮要修的**，请确认它的实际表现并记住：该列不能读作"这个对冲持有多少现货" |
| E-2 | 真实持有量在哪看 | 个人账户面板的**统一账户余额**部分 |

## 6. 结论如何提交

看完把结果告诉 Bookkeeper 即可，**不需要写文件**。请说明：

1. 上表哪些项**不符合期望**（尤其 A-1 / A-2 / B-1 / B-2 / D-1 / D-2 —— 这几项若不符即为真问题）；
2. 有没有清单之外你觉得不对劲的地方；
3. 是否授权合并到 `main`。

Bookkeeper 会把结果落盘为运行时验证证据，并据此更新发布就绪状态。

**若 D-1 / D-2 出现任何新增记录 —— 立即停止并告知**，那意味着调度在你不知情的情况下动了任务库。

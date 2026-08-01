# 26 —— 请求独立复核 Bookkeeper 的 Task 3 核验结论

> **v2（2026-08-01 21:5x 更新，作者 `opus5`）。** 第一版只请你复核「拒收裁定」。
> 此后 Human 与 Bookkeeper 的对话**改变了本轮的交付方向**：`100ms` 被 Human 主动
> 放弃，改为 `500ms` + 查不到订单的重试容忍。§1-§2 的原文保持不动（仍需复核），
> **新增 §5 记录方向变更与新增的判断五、六，并重写了判断四**（其前提已变）。
>
> **若你读过 v1，请直接从 §5 开始，再回看被重写的判断四。**

**致复核者（`deepseek`）**：本文件请你复核 **Bookkeeper（`opus5`）自己的核验结论**，
不是复核实现者的代码。

**读取位置**（v1 曾有复核者报告「文件不存在」）：本仓库有 **4 个 worktree**。本文件
只存在于**主工作区** `/Users/ark/Desktop/ai code/funding_hedging` 的
**`stage/2026-07-31-hedge-task-lifecycle-v1`** 分支。`main` 上该 stage 目录停在
`49-`，其余 worktree（`codex/bstock-*`、`codex/harness-v2-*`、detached）均无。
开始前请确认 `pwd` 与 `git branch --show-current`。

## 0. 这不是什么

- **不是 `AGENTS.md` §8 的 review-1 或 review-2。** 那两道仍待走（review-1 `grok` →
  review-2 `codex`），本次复核不替代、不预判、不消耗任何评审轮次。
- **不产生 `ACCEPT` / `REWORK` verdict**，也不写 `status.json`。
- 你的产出是一份**对下列判断的独立意见**（v1 四条 + v2 新增两条），供 Human 决定
  是否推翻 Bookkeeper。

## 1. 背景（最小集）

- 仓库：`funding_hedging`，分支 `stage/2026-07-31-hedge-task-lifecycle-v1`
- stage：`2026-07-31-hedge-task-lifecycle-v1`
- 任务：`hedge-leg-requery-cadence-v1`（把对冲任务的在途腿重查间隔 1s → 100ms，
  外加三道护栏：亚秒显示、读取处夹下限、worker 节流加抖动）
- 实现者：`claude_glm`；交付提交 `aac779d`，base `9faa716`
- 实现者自报：八项验收全 pass，`backend/tests/` **1140 passed**
- **Bookkeeper 裁定：拒收**（`current_task.state` 保持 `reported`，未写 `verified`）

设计权威：`11-adr.md` ADR-003（已过计划评审，`40-`，`deepseek` ACCEPT——即你自己
上一轮的结论，这与本次复核第 2 点直接相关）。

派工单：`hedge-leg-requery-cadence-v1.dispatch.md`
拒收记录：`24-bookkeeper-rejection-task3.md`
修复派工单（已备好，未投递）：`fix-cadence-existing-db-v1.dispatch.md`

## 2. 请你复核的四个判断

### 判断一（核心）：拒收依据 BK-T3-001 是否成立

**Bookkeeper 的主张**：`aac779d` 的默认值下调**对既有数据库完全无效**，交付目标在
真实部署上零效果。

**理由链**：

1. `DEFAULT_INTERVAL_US`（`domain.py:513-515`）只被**建库时的种子插入**引用
   （`store.py:337-350`），插入条件是
   `SELECT COUNT(*) FROM hedge_open_settings WHERE id = 1` 返回 `0`；
2. `_migrate()`（`store.py:351`）不触碰 `hedge_open_settings` 表；
3. `hedge_open_settings.interval_us` **没有任何运行时写入途径**——`store.py` 内除
   种子插入外无 `SET interval_us` / `set_interval*`；设置端点只有 start-gate 的 CAS
   更新（`service.py:1030-1045`）；
4. 因此既有库的 `interval_us` 永远停在建库当时写入的 `1_000_000`。

**Bookkeeper 的实测**（复制实盘库到临时目录，未写原库）：

```bash
cp data/hedge-open-tasks.sqlite3 /tmp/live-copy.sqlite3
sqlite3 /tmp/live-copy.sqlite3 \
  "SELECT id, interval_seconds, interval_us, version FROM hedge_open_settings;"
# 实测输出: 1|1|1000000|4
```

```python
from backend.hedge_open_tasks.store import HedgeOpenStore
from backend.hedge_open_tasks.service import settings_to_doc
import backend.hedge_open_tasks.domain as D
st = HedgeOpenStore("/tmp/live-copy.sqlite3", executor_mode_snapshot="disabled", now_us=0)
print(D.DEFAULT_INTERVAL_US, st.get_interval_us(),
      settings_to_doc(st.get_settings(), "live")["interval_seconds"])
```

| 库 | 代码常量 | `get_interval_us()` | 接口 `interval_seconds` |
|---|---|---|---|
| 实盘库副本 | `100_000` | **`1_000_000`** | **`1.0`** |
| 全新空库 | `100_000` | `100_000` | `0.1` |

**1140 个测试全绿，因为测试一律用 `tmp_path` 新建空库。**

**请你查**：

- 上述 1-4 步有没有事实错误？特别是第 3 步「无任何运行时写入途径」——请自己搜一遍，
  Bookkeeper 可能漏了某条路径（例如别的模块直连 sqlite、某个未被 grep 命中的写法、
  或运维脚本）。**只要存在任何一条合法途径能把该值改成 100ms，本拒收就不成立。**
- 「拒收」相对于「记为已接受限制并放行」是否过当？

### 判断二（最需要被挑战）：`rework_count` 不递增的裁定

**Bookkeeper 的裁定**：`rework_count` 保持 `0`，不因本次拒收递增。

**Bookkeeper 的理由**：依 `AGENTS.md` §8「缺陷在 packet 不在交付，不消耗返工预算」
的原则，本缺陷根在上游：

- ADR-003 Decision 第 2 条只写「把默认值从 1s 下调到 100ms」，未提迁移——**而该 ADR
  已过你（`deepseek`）的计划评审并获 ACCEPT**；
- `12-development-breakdown.md` Task 3 的文件边界与验收标准同样未涉及迁移；
- Bookkeeper 自己的 packet 照抄「下调默认值」，且把验收 2 写成了「用 `_pump_worker`
  或可控时钟确定性断言」——一个**在新建库上即可满足**的形式。

**利益冲突声明**：**这条裁定是 Bookkeeper 对「缺陷是不是自己造成的」所做的自我
判断，直接决定实现者是否被扣返工额度。请你带着敌意审视它。**

**请你查**：

- 「缺陷在 packet」的定性是否成立？还是说，一个称职的实现者本就应当知道
  「种子插入不会回溯更新既有行」，因而属于实现缺陷、应当计数？
- Bookkeeper 是否在用「packet 缺陷」豁免一个本应由交付承担的问题？
- 实现者在 `23-cadence-implementation.md:46-47` 写「种子插入引用常量，**自动生效**，
  无需改 `store.py` 种子」——把未验证的推断当作事实陈述。这一条本身够不够构成
  独立的交付缺陷（从而应当计数）？
- 注意你自己上一轮 ACCEPT 了 ADR-003。**这不该让你倾向于任何一方**：若你认为
  ADR-003 本就该覆盖迁移，请直说（那意味着计划评审也漏了）；若你认为迁移属于实现
  细节、不该由 ADR 承担，也请直说（那意味着责任更偏向交付）。

### 判断三：「七项通过」的结论是否被限定得足够

Bookkeeper 判定八项验收中七项 pass。但**所有测试都跑在新建空库上**，因此严格说
应为「在新库前提下通过」。

**请你查**：这个限定是否被充分说明？其中是否有哪一项，在真实库（`interval_us`
仍为 1 秒）下结论会不同、从而不该记为 pass？Bookkeeper 认为不会（显示逻辑对 1 秒
同样正确、下限与抖动同样工作，只是标称值不同），请独立判断。

### 判断四：抖动整件事——来源、有效性、是否应当移除

> **v2 提示：本条的前提已变。** 节奏由 `100ms` 改为 `500ms` 后，抖动所声称防护的
> 「10 worker 挤成脉冲」场景进一步弱化。**下面的溯源表仍然有效，请照常复核；但在
> 给结论前先读 §5.4。**

**（本条在 Human 质疑「抖动我没答应加，是谁加的」之后重写，请重点看。）**

**溯源（Bookkeeper 已核实）**：

| 文件 | 是否出现「抖动」 | 作者 |
|---|---|---|
| `01-intake-brief.md:74-83`（Human 对 ③ 的原始诉求） | **无**。Human 提的是「1 秒 → 100ms」；所附建议为「拆分两间隔、加下限、考虑 429 退避而非暂停」 | Human 诉求记录 |
| `02-` `03-` `04-`（Human 决策文件） | **无** | Human |
| `PROJECT_STATE.md`（历史 follow-up） | **无** | — |
| `10-design.md` P6 / `11-adr.md` ADR-003 | **首次出现** | `claude_glm`（D12） |
| `40-plan-review-deepseek-v2.md` | 计划评审 **ACCEPT**（含抖动） | `deepseek` |
| 本任务 packet 要点 4 / 验收 4 | 原样承接 | `opus5`（Bookkeeper） |

即：**抖动由方案作者 `claude_glm` 引入，经计划评审放行，Bookkeeper 未加质疑地写进
packet。Human 从未要求，也从未单独批准。** 同时，Human 自己提的三条建议中「拆分两
间隔」被 ADR-003 以事实 8 为据否决——**一条 Human 提的被砍，一条 Human 没提的被加。**

**Bookkeeper 现在的技术质疑（请你独立判断对错）**：

1. 抖动声称解决「10 个 worker 对齐成 100 req/s **脉冲**」。但币安限的是**权重总量**
   （ADR-003 自述 ~1200/min ≈ 20/s），而 10 任务 × 10 次/秒 = **100 次/秒的总量不因
   抖动而减少**——抖动只是把同样的总量摊平。**对「总量超限约 5 倍」这个真实风险，
   抖动基本无效。**
2. 实现取 `[0.75, 1.0]`，平均实际间隔 `87.5ms` < 标称 `100ms`，**总请求量反而比标称
   高约 14%**。方向选择源自 Bookkeeper packet 验收 4 的原文（要求抖动「不会……超过
   标称间隔」），实现者照做无误。
3. 真正对应该风险的手段是 429 退避（ADR-002），而它属 Task 2、**本轮明确不做**。

**请你查**：

- 上述技术质疑 1 是否成立？抖动对本场景是否确有 Bookkeeper 未看到的实际价值
  （例如避免瞬时突刺触发更严格的限流档位）？请给出你的判断而非折中表述。
- 按 `AGENTS.md` §1（「不要为假设场景添加防御性机制」），抖动属于**对已批准目标的
  正当技术手段**，还是属于**未经要求的范围扩张**？
- 建议 Human 选哪一项：**整个移除抖动** / **保留但改为保守方向（如 `[1.0, 1.25]`）**
  / **原样保留**？请给出理由与代价。
- 附带：`deepseek` 是上一轮计划评审的 ACCEPT 方（即你自己）。若你现在认为抖动本不
  该进方案，请直说；这属于计划评审的遗漏，如实记录即可。

## 3. 你可以核实的与只能采信的

- 若你能读取本仓库：上述所有行号、命令、测试结果均可自行复跑核实。**请优先自己
  验证，不要采信本文件的转述。** 全量回归命令：`python3 -m pytest backend/tests/ -q`。
- 若你读不到仓库：请明确区分你的结论中哪些基于本文件给出的事实（无法独立验证）、
  哪些基于逻辑一致性分析，并在结论中标注。

## 4. 请返回

1. 对**六个**判断逐条给出：**同意 / 不同意 / 证据不足**，并给理由；
2. 你发现的、本文件未提及的问题（尤其是 Bookkeeper 核验遗漏的检查项）；
3. 一句话总体意见：Bookkeeper 的拒收裁定应当**维持、推翻、还是修改**；
4. 对 §5 的新方案（`500ms` + 重试容忍）：**成立 / 有缺陷 / 需要改**。

不要写 `status.json`，不要修改任何仓库文件，不要启动其他模型会话。

---

# 5. v2 —— 交付方向已被 Human 改变（2026-08-01）

## 5.1 起因：Bookkeeper 发现「查不到订单」会被一次判死

拒收（§2 判断一）之后，Human 追问「原 JS 策略下单后有没有等待再查」。Bookkeeper
据此实测了原策略脚本与后端，发现了**一个 §1 拒收之外的、更严重的问题**。

### 原 JS 策略（仓库根目录 `币安套费率策略，逐仓杠杆.js`，3447 行）实测

| 路径 | 下单后到**首次**查询 | 查不到怎么办 |
|---|---|---|
| 现货买入 `marginBuy` | **`Sleep(500)`**（活跃） | `getSpotOrderInfo(id, 10)`：查不到 → `Sleep(500)` → 重试，**最多 10 次** |
| 现货卖出 `marginSell` | `//Sleep(500)` **被注释掉** | 同上 |
| 合约开仓 `shortSell`/`longBuy` | 无独立 sleep | `checkOrder` 循环**首行即 `Sleep(500)`**，等效先等后查 |
| 合约平仓 `makerCloseFutrue` | 同上 | 同上 |

**原作者的容忍窗口 = 10 次 × 500ms ≈ 5 秒**，且按 `orderId` 查。

### 后端实测（交付 `aac779d`，直接调用分类器 + `_query_verdict_terminal`）

查询响应 → 腿的下场：

| 查询返回 | `dispatch_state` | `error_category` | 腿的下场 |
|---|---|---|---|
| **404 查不到** | `TERMINAL_RECORDED` | `absent` | **一次判死，停止查询** |
| **-2013 订单不存在** | `TERMINAL_RECORDED` | `absent` | **一次判死，停止查询** |
| 200 FILLED | `ACCEPTED_OR_QUERYING` | — | 正常终态 |
| 200 NEW（挂着） | `ACCEPTED_OR_QUERYING` | — | 继续查 |
| 200 但无 `orderId` | `UNKNOWN_QUERYING` | — | 继续查 |
| 5xx / 超时 | `None`（无结论） | — | 继续查 |

**关键差异**：后端对 404/-2013 **没有原作者那层 10 次重试容忍**，一次即判「订单从未
被接受」。而首查延迟由同一个 `interval` 决定——原本 1 秒，若降到 100ms（含抖动 75ms）
则**比原作者的 5 秒窗口小约 50 倍**。

风险形状：**下单成功 → 100ms 后查 → 币安尚未落库返回 -2013 → 该腿被判定为「从未被
接受」，而它可能真实挂在交易所上。** 属资金可见性错误，非性能问题。

注：设计者对同类风险**已有意识**——`test_query_2xx_without_order_id_stays_unknown`
的注释明写「畸形 2xx 不是确认不存在的信号，**只有明确的 404 / -2013 才是**……绝不把
一个可能已被接受的订单误判为不存在」。即：保护存在，但**未覆盖「查得太早」这一路径**。

## 5.2 Human 的方向决策（D17-D20，已定，请勿重新论证选型）

| # | 决策 |
|---|---|
| **D17** | 100ms 足够币安落库返回数据（业务判断）。**后被 D19 取代。** |
| **D18** | 请求频率由 Human **控制开单标的数量**间接管理，不引入程序级全局限流器 |
| **D19** | **放弃 100ms，统一改为 500ms**（首查与重查同一个旋钮），与原 JS 一致 |
| **D20** | **查不到订单不再一次判死**：除返回 200 外，其余情况继续按间隔查询，累计约 5 秒（等价于原 JS 的 10 次 × 500ms）仍无 200 才判 `absent` |

**本轮目标因此改变**：由「1s → 100ms，提速 10 倍」变为
**「1s → 500ms，提速 2 倍 + 消除订单误判为不存在的风险」**。

Human 在选择时已被明确告知「本轮 1s→100ms 的提速目标被放弃」，仍作此选择。

### D19 带来的连锁效果（Bookkeeper 计算，请复核算术）

| | 100ms 方案 | 500ms 方案 |
|---|---|---|
| 每任务请求速率 | 约 10 次/秒 | **约 2 次/秒** |
| 按币安约 20 次/秒 可并发任务数 | 约 2 个 | **约 10 个** |
| 首查延迟 vs 原作者 500ms | 早 5～6.7 倍 | **一致** |

## 5.3 Human 追加的约束及 Bookkeeper 的实测回应

**Human 原话**：「查询次数只对当前下单的订单号有效，而且进入查询的前提是下单成功
返回了订单号，不能下单提示了资金不足等其他问题没下单成功去查订单，打满 10 次
500ms 的查询毫无意义。」

Bookkeeper 实测下单响应分类（`classify_leg_response`）：

| 下单返回 | `dispatch_state` | `order_id` | 是否进查询循环 |
|---|---|---|---|
| 成功，有 `orderId` | `ACCEPTED_OR_QUERYING` | 有 | 是 |
| 资金不足 `-2010` | `TERMINAL_RECORDED` | 无 | **否，已终态** |
| 保证金不足 `-2019` | `TERMINAL_RECORDED` | 无 | **否，已终态** |
| 抵押额度满 `51169` | `TERMINAL_RECORDED` | 无 | **否，已终态** |
| 数量非法 `-1013` | `TERMINAL_RECORDED` | 无 | **否，已终态** |
| 签名/时间戳 `-1021` | `UNKNOWN_QUERYING` | **无** | **是** |
| 限频 `-1003` | `UNKNOWN_QUERYING` | **无** | 是（随后暂停任务） |
| 超时（无响应） | `UNKNOWN_QUERYING` | **无** | **是** |
| 5xx | `UNKNOWN_QUERYING` | **无** | **是** |

**Bookkeeper 的回应**（请复核，这是判断六）：

- 约束的前半段**后端已满足**：资金不足等明确失败一律 `TERMINAL_RECORDED`，不进循环，
  不存在「打满 10 次」。
- 约束的后半段**建议不予采纳**：超时 / 5xx / `-1021` 这三类**恰恰没有 `orderId`，
  却必须查满**——它们的共同点是「不知道单到底下没下出去」，响应未回不等于交易所未
  收到。若因「无 `orderId`」而不查，一个真实成交的腿将永不被发现，比多查几次严重。
- 之所以能这样做，是因为**后端按 `clientOrderId` 查，而非 `orderId`**。
  `clientOrderId` 在下单前本地生成，故「一个订单号都没拿到」仍可查。**原 JS 按
  `orderId` 查，做不到这一点**——Human 的直觉源自 JS 模型，后端模型更强。

## 5.4 新的交付范围（Bookkeeper 拟定，未投递）

原 `fix-cadence-existing-db-v1.dispatch.md`（只补迁移）**已不足**，将重写为新任务：

1. 默认间隔 `1s → 500ms`（**不是** `aac779d` 里的 `100ms`）；
2. **404 / -2013 不再一次判死**：改为继续重试，累计约 5 秒仍无 200 才判 `absent` 终态；
3. **移除抖动**（`_PACING_JITTER_MIN`、`paced_wait_seconds` 及其单测）；
4. 补迁移，使默认值在既有库上真正生效（原 §1 的 BK-T3-001）。

Bookkeeper 已自行决定的两处实现约束：

- **重试计数不新增数据库字段**（项目红线），改用「距下单时间满约 5 秒」的时间窗口，
  语义等价于 10 次 × 500ms；
- 保留 `MIN_INTERVAL_US = 50_000` 下限（防误配）。

**风险等级**：第 2 项改动的是「这条腿是否成交」的判定，属资金可见性，**高于**原任务
（纯数值调整）。`rework_count` 将按「Human 同意的新交付范围」重置为 0（`AGENTS.md` §8）。

## 5.5 新增判断五：`500ms` + 重试容忍方案本身是否成立

**请你查**：

- 5.1 的风险链条（下单 → 过早查询 → -2013 → 误判为从未被接受）**是否真实存在**？
  尤其：币安 PAPI 在 POST 成功返回后，按 `origClientOrderId` 立即 GET，是否可能
  返回 -2013？**Bookkeeper 无法验证这一点**（需真机、且属实盘操作），这是整个方案
  最关键的未验证前提。若该前提不成立，第 2 项改动即为无证据的防御性机制
  （违反 `AGENTS.md` §1）。
- 「累计 5 秒仍无 200 才判 absent」的**上限**是否合理？窗口耗尽后判 `absent` 终态
  （即现行行为，只是推迟 5 秒）是否是正确的收口？还是应留非终态交人工？
- **一个 Bookkeeper 发现但尚未处理的不一致**：现行「继续查」的分支（5xx / 超时 /
  畸形 2xx）**没有任何次数或时间上限**，只要腿非终态且任务 RUNNING、闸门开，worker
  就无限重查（`_worker_loop` 无 `max_rounds`；`_pump_worker` 的 64 轮上限仅是测试缝）。
  加窗口后 404 反而比它们更有纪律。**这个不一致是否应在本轮一并收口？**
- 用时间窗口替代次数计数以规避新增字段——是否恰当，还是次数语义更该被显式持久化？

## 5.6 新增判断六：Human 的「无 orderId 不该查」约束是否应被采纳

见 §5.3。Bookkeeper 判定「前半段已满足、后半段不予采纳」。

**请你查**：这个判定是否正确？Bookkeeper 是否在用「clientOrderId 更强」的说法，
回避一个 Human 提出的合理约束？是否存在既尊重该约束、又不丢失「不知道下没下成」
场景的第三种做法？

## 5.7 判断四（抖动）在新前提下的重述

在 `500ms` 下，抖动所防的「多 worker 挤成脉冲」场景对应的请求量已降至约 1/5，且
Human 已明确以「控制开单标的数量」（D18）作为频率手柄。此外 Human 要求的行为是
**「下单后等 100ms（现为 500ms）再查」这一确定值**，而抖动会使其变为
`0.75×～1.0×` 的随机值——**首查等待正是防落库延迟的安全边界，抖动在削减该边界**。

Bookkeeper 建议：**整体移除**。请给出独立意见（同意移除 / 应保留并说明理由 /
应保留但改保守方向）。

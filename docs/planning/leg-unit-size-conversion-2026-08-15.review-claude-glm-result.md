# 评审结论：REWORK

- 评审对象：`docs/planning/leg-unit-size-conversion-2026-08-15.opus5.md`（设计稿，基线 `main` @ `b075c56`，代码一行未改）
- 评审方式：只读计划评审（跨 provider），全部发现基于基线代码逐行核对
- 日期：2026-08-15
- 结论：**REWORK**

设计主体成立：量纲选「现货个数」、面值入表并固化、唯一出口换算、§4.1.1 禁退路、§8 拆拦截顺序——这些都对。**但 §4 完整性清单有硬遗漏，且 §5.1 的事实陈述有误。** 按发现范围三分类，以下 F1–F4 均为 in-range（设计稿即本轮交付物，其完整性声明是交付内容的一部分）。

---

## 发现清单

### F1（硬遗漏 · close 守门路径 · 阻塞）`_close_um_position_error` 拿「张」比「个」

- `backend/hedge_open_tasks/service.py:2608`：`if available < required_qty`
- `available` 来自 UM `positionAmt`（`live_hedge_executor.py:540-565`，**张**）；`required_qty = fresh.q_common × remaining_attempts`（`service.py:2442`，方案钉死为**个**）
- 后果：乘数币恒判「合约可平数量不足」→ close **永远 fail-closed 拒发**。这不是裸空，是「开了仓平不掉」——本方案的目标能力（6 币恢复对冲）在平仓侧被直接断路。立即平仓与平滑平仓都走这道门（`service.py:2443`）。
- 修复要求：比较前 `available × 任务固化面值`（或 `required_qty ÷ 面值`），面值读开仓固化列（与 §3.3 同源），并加 §9.2 用例：「现货 100 万个 + UM 持仓 1000 张 + 剩余 1 次」必须放行。
- 关联核对：`_is_close_flat`（`service.py:2403-2406`）用 `qty == 0` 判平，0 无量纲问题，**不用改**，请在方案中写明以免误伤。

### F2（硬遗漏 · smooth 路径 · 阻塞）smooth 门对乘数币系统性失真

`evaluate_smooth_gate`（`backend/hedge_open_tasks/domain.py:1566`）两处量纲错位，open 与 close 的 smooth 模式共用（`service.py:2035`、放行判定 `2040`）：

- **spread**（`domain.py:1588/1591`）：`compute_opening_spread_pct(perp.bid, spot.ask)` = (每张价 − 每个价)/每个价。1000x 币恒得 ≈ +99900% → `spread_pass` **恒真**，价差保护失效。
- **coverage**（`domain.py:1595-1596`）：`perp_coverage = perp_qty / q_common` = **张 ÷ 个** → 系统性**低估 1000 倍**，`SMOOTH_COVERAGE_MIN=0.80`（`domain.py:96`）基本恒不过。
- 净效果：`market_pass` 恒假 → 每笔都等满 5 分钟窗口后按 `PASS_REASON_TIMEOUT` 放行（`service.py:2042-2043`）。**smooth 门的全部市场条件保护对乘数币不存在**，且每笔白等 5 分钟。
- 修复要求：perp 盘口价 ÷ 面值、盘口量 × 面值后再参与两式（面值 = 1 恒等，零分支），加 §9.2 用例。

### F3（范围遗漏 · 用户可见资金安全项）close 输入框与 §4.7 同构，未纳入

- `frontend/index.html:5719` 「单次平仓币量」（及 5704 整段 close 列模板）与 §4.7 指出的开单列（`5671/5672`）是**同一段生成的同构 UI**，乘数币同样差 1000 倍。§4.7 只改开单列。开仓能力恢复的同一轮，close 列必然被用到——必须同批改（同一段模板代码，增量成本≈0）。§9.2 第 8 条的自检断言也要覆盖 close 列。

### F4（§5.1 事实错误 · 结论侥幸成立）est_price 消费者是三个，不是两个

- §5.1 称「est_price 在代码中只有两个消费者」。**错**：`backend/hedge_open_tasks/service.py:997-999` 是第三个——open+forward+regular_spot 的预划转金额 `q_common × N × est_price × 1.03`。这正是问题清单点名要查的**划转备料路径**，方案通篇未提。
- 验算：个数 × 现货价 = 正确 USDT 需求，与 §5.2 同构，**「不用改」结论仍成立**——但净减项的核对方法漏扫了一处，§5.1 必须更正为三处并补验算，§9.1 行号校验表应加 `service.py:998`。一处幸存不能反推「查全了」。

### 低级别观察（不阻塞，建议记入方案取舍）

- **O1**：`service.py:3097` collateral-cap 暂停文案用 `D.base_asset(task["coin"])`，乘数币会显示 `1000BONK`（§4.5 修 `domain.py:1342` 时顺带，或写明不动）。
- **O2**：`backend/domain/snapshot.py:698-699` 行级开单价差列对乘数币会展示 ≈ +99900%（每张价 vs 每个价）。展示错值不伤资金，但乘数币入池后此列对它们是误导，方案应写明归一或标 N/A 的取舍。

---

## 五问正面回答

**问题 1（§5 三条推导）**：**结论全部成立，但 §5.1 的论证过程有事实错误（F4）。** 独立验算：

- `domain.py:1083`：合约腿名义 = (个数÷1000 张) × (现货价×1000/张) = 个数×现货价，与现货腿同一数；两腿下限均以 USDT 计，一个 notional 比两边正确。✅
- `domain.py:1344`：个数×次数×现货价 = 买现货的 USDT 需求。✅
- `domain.py:1352`：个数×次数 vs `balances[base]`（个），前提 §4.5 修 base。✅ close 反转方向也走同一分支（`service.py:961-963`），`spot_account_base_free` 同为个。✅
- `hedge_preflight_provider.py:862`：`_read_est_price`（`463-492`）取**现货 symbol** 的 `/api/v3/ticker/price`，配「个数」正确。✅

净减项本身站得住，但 §5.1 须改为「三个消费者」并补 `service.py:998` 的验算，否则这个净减项的核对基础不完整。

**问题 2（单位面值 vs 倍率）**：**值得，非过度设计。** `SPOT_SYMBOL_MAP`（`normalize.py:111`）本来就以合约 symbol 为键、按腿组织，给每条腿挂自己的面值与表形状天然一致；「倍率」列反而要把「分母是现货腿」这一隐含契约编进公式。成本相同（一个整数列），退回倍率省不下任何代码，将来跨所还要改表语义+公式两处。维持 §3.1。

**问题 3（§4 是否完整）**：**不完整。** F1（close 守门）、F2（smooth 门）两处硬遗漏，F3（close 前端列）一处范围遗漏。其余路径已逐一核对无误：划转 `_ensure_close_spot_balance`（`service.py:2518-2549`，个口径、base 用固化值 ✅）、预划转 `service.py:998`（✅ 不用改）、USDT 回流（cumulative_quote，USDT ✅）、持仓聚合 `domain.py:2122`（§4.4 已列，bucket 的 perp_qty 确为张、来自腿行成交 `store.py:2807`，改法方向正确）、drift（`domain.py:2147` 用 spot_qty 个 ✅）。§9.1 行号校验本次实跑 **13/13 全 OK**。

**问题 4（容差）**：**±5% 偏紧，建议 ±30%（或对数判定）。** 护栏要抓的是数量级错误（≥10 倍）；memecoin 永续在剧烈行情/价格发现期，基差加资金费率预期完全可以推标记价偏离现货超 5%。误拦的代价是 fail-closed 拒开仓 + 告警疲劳（狼来了之后人会想关护栏，那才是真风险）。任何小于 2 倍的偏离都不该拦——取 30% 对 10 倍错误仍有 7 倍余量，对基差免疫。另建议做两层：在线发单前（§6 原设计）+ 离线建表校验（见问题 5 第 1 条）。

**问题 5（验收是否足够）**：框架对，可再补三条更早更便宜的：

1. **护栏前移到建表校验**：`check-spot-symbol-map.py --verify` 加一步——拉两个**公开** ticker（无鉴权），算比值反推面值 vs 表声明。表错在建表/校验时被抓，早于任何发单。脚本已存在，增量几行。
2. **断言写在交易所原始参数层**：§9.2 第 1 条的断言对象应是 `perp_order_params["quantity"] == "1000"`（发出去的原始字符串），不是换算后的内部值——避免「断言与实现共用同一换算函数」的自证。这是对「两边同错全绿」最便宜的针对性防线。
3. **实盘核对自动化**：最小额度那笔成交后，程序读两腿 order response 的 `executedQty`，断言 `现货 executedQty ≈ 合约 executedQty × 面值` 并写任务日志。Human 仍在场授权，但把「到币安页面肉眼看」变成可留档、可复核的机器断言。

---

修复对象是设计稿文档本身：F1/F2/F3 补入 §4（清单变 10 处）、§5.1 更正为三处、§6 容差定为 ±30%、§9 按问题 5 补三条。改完可直接再审。

```text
[TASK_RESULT v2]
任务 ID: review-leg-unit-size-conversion-2026-08-15（只读计划评审，无 packet）
执行结果: completed（完成）
结果摘要: 设计主体成立但清单不完整。REWORK 4 项：F1 close守门service.py:2608张比个致乘数币恒拒平仓；F2 smooth门domain.py:1588-1596价差恒真+覆盖低估1000倍致门失明每笔超时放行；F3 frontend/index.html:5719平仓输入框单位歧义未纳入§4.7；F4 §5.1 est_price实为三个消费者漏service.py:998（结论侥幸成立须更正）。§5其余推导验算成立，§3.1维持，容差建议±30%。
产物: [docs/planning/leg-unit-size-conversion-2026-08-15.opus5.md（受审对象，未改动）]
检查结果: [§9.1行号校验13/13 pass；est_price取价口径核验 pass；bucket持仓记账口径核验 pass；close划转路径量纲核验 pass；§5.2/§5.3独立验算 pass；§4清单完整性 fail（F1/F2/F3）]
阻塞项: [none]
评审结论: REWORK（返工）
问题记录: docs/planning/leg-unit-size-conversion-2026-08-15.review-claude-glm-result.md
修复要求: F1-F4 补入设计稿§4/§5并更正表述（见本文件正文）
本地北京时间: 2026-08-15 14:50:02 CST
下一步模型: Human（决策者）
下一步任务: 读取：docs/planning/leg-unit-size-conversion-2026-08-15.review-claude-glm-result.md 正文F1-F4；执行：将四项发现批注给Planner修订设计稿；关卡：修订稿重新过一次跨provider只读计划评审后放行实现
[/TASK_RESULT]
```

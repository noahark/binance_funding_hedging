# Review-2（kimi）：展示层诚实性四项修复 + 1000x 乘数币 fail-closed

- 日期：2026-08-07
- 受审区间：`dd0b3e3..c0190a6`（d7057e3 实现 + cae52a1 文档订正 + 4e488f3 评审请求 +
  c0190a6 review-1 三条观察收编）
- review-1：deepseek，ACCEPT + 三条非阻塞观察（已收编）
- 本评审：review-2，独立复跑与逐行核实

## 核实结果（全部亲自复核，非转述）

- 后端全量 **1587 passed**（本机复跑，111.7s），与文稿一致。
- 前端 self-check **EXIT=0**（本机复跑，含 Q4 新断言组「读不到显示未知不回退可用额」）。
- P0 五处清单行号逐行精确：`live_hedge_executor.py:873`（两腿共用 `send_qty`）、
  `hedge_preflight_provider.py:832`（`est_price` 取现货价）、`domain.py:1183`
  （`grid = decimal_lcm(spot_step, perp_step)`）、`domain.py:1267/1273`（`required`）、
  `domain.py:1952` 附近（持仓表两腿比较）——全部属实。
- 拦截位置正确：`service.py:805` 一带，在 `check_symbol_legs` 之后、`get_snapshot`/
  `compute_preflight` 之前，纯查表零 IO，只拦 open。
- 实盘库只读核实：`hedge_open_task` 状态分布 deleted|9 / done|12 / stopped|1，
  **无 exposure_alert 行**（删除零迁移风险成立）；`coin LIKE '1000%'` **0 行**
  （「从未开过、无实际损失」成立）。
- `exposure_alert` 后端无写入方残留（仅剩删除说明注释）；`?status=exposure_alert`
  现返回 400，行为正确。
- 终态结算 `order_state_unknown_final`：静态 sticky 测试与并发删除测试**都**切到了
  新 kind（不只慢路径），sticky 状态/腿非终态/永不重发三条行为未动——属实。
- 表外乘数币双保险成立：`1000000MOGUSDT` 不在 `SPOT_SYMBOL_MAP`，
  `resolve_spot_identity` 表外返回 `(None,None)` → `check_symbol_legs` 探测不到现货腿
  → `missing_leg` 拦截，与 P0 拦截互补。
- `_allow_multiplier_open` 机制核实：patch `service_mod.SPOT_MATCH_MULTIPLIER` 使相等
  比较永不成立从而关掉拦截；若拦截失效（被测路径意外地不再触发 400），相关测试会
  **抛错而非静默绿**——fail-loud 方向正确。c0190a6 已把 docstring 的「逃生口」旧措辞
  改为「守的是资产名这一层」，我在 §6 的措辞疑虑已消解。

## 对评审请求六个重点问题的结论

**§0(a) 拦 open 放行 close —— 接受，但补充一条关键事实。** 在「close 同样错 1000 倍」
的订正之后，「平仓逃生口」的原始理由确实塌了；但放行的结论仍成立，理由是：
(1) 实盘库已核实无此类仓位，拦住 close 不增加任何现实安全；
(2) 若真出现这种仓位，正确处置本来就是人工去交易所平 + 人工补账（COOKIE 周期先例），
系统自动 close 无论放行与否都不该被依赖；
(3) 一个值得记录的细节：若仓位由同一套错误代码开出（现货 N 个、合约 N 张），close 用
**相同数量**发两腿时，错误是对称的——现货卖 N、合约买 N 张=1000N，两腿恰好各自归零。
但这是**巧合不是性质**：close 数量由操作员按记账值输入，任何不对称（部分平仓、人工在
交易所正确开过的仓、preflight 量纲错乱导致的误拦/误放）都会打破它。所以措辞应止于
「放行是不额外添堵」，不得延伸为「系统能平」。将来若真发现此类仓位，届时可考虑把同一
拦截扩到 close（一行改动，属资金闸门变更，须 Human 单独授权）。

**§0(b) 清单遗漏 —— 有，第六处。** 这是本轮唯一阻塞发现，见下「发现 1」。

**§2(a) drift 求和 vs 按路由选账户 —— 接受求和。** 保守方向的论证成立：求和可能假阴性，
但（在负债不参与的前提下）不会凭空造持仓；按路由选要把 per-task 动态路由带进聚合桶，
改动面不成比例。c0190a6 已把「有报警必真少成立、无报警即相符不成立」写死进代码注释与
PROJECT_STATE，分寸正确。另有一个他们未写到的边界，见下「发现 2」（非阻塞）。

**§6 测试关闸门 —— 可接受，不必改成构造 DB 行。** 三个受影响测试里有两个
（身份固化 ×2）被测的就是 `create_task` 本身的行为，构造 DB 行恰恰绕过了被测对象；
第三个（平仓划转资产名）用 DB 行可行但无必要——monkeypatch 是 fail-loud 的，且注释已
写明意图。真正的问题是 docstring 的旧「逃生口」措辞，c0190a6 已修。

**§1 1% 阈值与不改字段名 —— 都接受。** 两腿发同一 `q_common` 本应逐位相等，1% 只吸收
舍入的论证成立；绝对量阈值在 BTC(0.001) 到 SHIB(1000000) 跨 9 个数量级下确实不可行。
边界是严格大于（恰好 1.000/0.990 不报），方向正确。不改名避免波及 API 契约/前端/测试，
注释已承担语义说明。测试五形态（裸空/部分失衡/容差内/no_task/原裸多）核实均在。

**§8.6 新口子排查 —— 未发现新的资金口子。** 新端点只读、`asset` 经 alnum 校验、
不碰下单路径；两处白名单改动是 deny-by-default 守卫的正常用法（必须显式承认才能加），
非绕过；Q4 失败文案无数字回退有断言守。唯一残留是一处过时注释（发现 3，琐碎）。

## 发现

### 发现 1（in-range，阻塞，修复范围极小）：「必须一次改齐」清单漏了第六处——`_check_common_quantity`

`backend/hedge_open_tasks/domain.py:1004`（在 `compute_preflight` 内 :1232 调用）：

```python
def _check_common_quantity(q_common, spot_filters, perp_filters, est_price):
    ...
    for filters in (spot_filters, perp_filters):
        min_qty, max_qty = _qty_bounds(filters)
        if min_qty is not None and q_common < min_qty: return REJECT_BELOW_MIN_QTY
        ...
    notional = q_common * est_price          # 一个现货价估两腿的名义额
    for filters in (spot_filters, perp_filters):
        floor = min_notional(filters)
        if floor is not None and notional < floor: return REJECT_BELOW_MIN_NOTIONAL
```

它拿**同一个** `q_common` 去对两腿各自的 min/max 数量边界，并用**同一个现货价**估两腿
的 minNotional——与清单第 3/4 条同处于 `compute_preflight`，但是独立函数、独立失效模式：
换算落地后两腿数量与价格都拆开，这里必须跟着拆成每腿各查各的（现货量对现货边界、
合约量对合约边界、合约名义额用合约价）。评审请求 §0 的叙述提到过 minNotional 错 1000 倍，
但归给了 est_price（清单第 2 条）；**数量边界那一半（perp min_qty=1 张 vs 现货量纲的
q_common）在五处清单里没有任何一条覆盖**。该条目自己写了「改一半比不改更危险」，而
_missing 的恰好是一个容易被当作「已包含在 preflight 里」而跳过的 helper_，必须点名。

**修复要求**：PROJECT_STATE 的「1000x 腿量换算」条把清单扩为六处，新增
`domain.py:1004`（`_check_common_quantity`，:1232 调用点）——每腿数量边界与每腿
minNotional 各按各的量纲与价格校验；可同时在该函数处留一行指针注释。纯文档/注释改动，
不改任何逻辑。

### 发现 2（in-range，非阻塞，建议同轮记录）：drift 求和的假阳性来源——同资产借币负债

c0190a6 写死的保证是「有报警必真少」。有一个该保证不覆盖的场景：统一账户里同资产的
**借币负债**会净减 `total_balance`。本系统反向开仓就是要借基础币卖出的——若同一币种
同时存在正向任务（现货腿在统一账户，记账 0.5）与反向头寸（借 0.3 已卖），统一账户该
资产净额 = 0.2，正向行 `held = 0 + 0.2 < 0.5` → **没有任何人工减仓也会报警**。
O-1 后续项明确同币双向共存是可能的，所以这不是纯理论。「报警 ⇒ 人工减过仓」在这类
币上不成立，报警可信度受损（该标记无自动动作，无资金后果）。
**建议**：在同一注释/PROJECT_STATE 条目里补一句此假阳性来源（与 totalWalletBalance 那句
并列），或在换算轮一并评估改用不含负债净减的口径。不要求本轮改代码。

### 发现 3（琐碎）：过时注释

`frontend/index.html:4624`「敞口告警无专属筛选，仅在『全部』可见」——`exposure_alert`
已删除，该句成了死文字，可随发现 1 的修复轮顺手删。

## 评审结论

**REWORK**（窄发现，仅文档/注释级修复）。按 §8，窄 review-2 发现修复 + 新提交后直接回
review-2，无需再过 review-1。代码交付本身（P0 拦截 + B2/B3/B4/Q4 + 测试）核实无误，
1587 passed 与 self-check EXIT=0 本机复跑一致；修复仅涉及 PROJECT_STATE 清单补第六处、
发现 2 的一句话记录、发现 3 的死注释删除。

---

[TASK_RESULT v2]
任务 ID: review-2-display-truth-and-multiplier-block-2026-08-07-kimi
执行结果: completed
结果摘要: 对 dd0b3e3..c0190a6 做 review-2：文稿声明全部核实属实（1587 passed 与 self-check EXIT=0 本机复跑一致；P0 五处行号逐行精确；实盘库无 1000x 币与 exposure_alert 行；拦截位置/范围正确）。六个重点问题逐一给出结论：放行 close 接受（附对称抵消是巧合非性质的澄清）、drift 求和接受、monkeypatch 可接受、1% 阈值与不改名接受、未发现新资金口子。唯一阻塞发现：「必须一次改齐的五处」清单漏了第六处 _check_common_quantity（domain.py:1004，每腿数量边界与 minNotional 同样量纲错乱）；另有两条非阻塞观察。评审结论 REWORK（窄发现，纯文档/注释修复）。
产物: [docs/planning/display-truth-and-multiplier-block-2026-08-07.review-kimi.md]
检查结果: [后端 1587 passed 本机复跑 pass; 前端 self-check EXIT=0 本机复跑 pass; P0 五处行号逐行核实 pass; 拦截位置在存在性探测后/preflight 前纯查表 pass; 实盘库只读核实无 1000x 币且无 exposure_alert 行 pass; 终态新 kind 静态+并发两路径均覆盖 pass; monkeypatch 机制 fail-loud 且 docstring 已订正 pass; 五处清单完整性 fail（漏 _check_common_quantity）]
阻塞项: [发现 1：PROJECT_STATE「1000x 腿量换算」清单补第六处 domain.py:1004 _check_common_quantity（纯文档修复，修复后直接回 review-2）]
评审结论: REWORK
问题记录: docs/planning/display-truth-and-multiplier-block-2026-08-07.review-kimi.md
修复要求: docs/planning/display-truth-and-multiplier-block-2026-08-07.review-kimi.md（发现 1 必修；发现 2/3 建议同轮顺手处理）
本地北京时间: 2026-08-07 20:04:32 CST
下一步模型: Bookkeeper（核验本评审结果并安排修复轮）
下一步任务: 读取：docs/planning/display-truth-and-multiplier-block-2026-08-07.review-kimi.md；执行：Bookkeeper 核验后按窄发现路由修复轮（opus5 修 PROJECT_STATE 清单补第六处 + 建议同轮处理发现 2/3，新提交后直接回 review-2 kimi 复评）；关卡：review-2 ACCEPT 后由 Human 决定合并与是否授权 1000x 换算轮
[/TASK_RESULT]

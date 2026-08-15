# 评审结论：REWORK

评审对象:`docs/planning/duplicate-concept-consolidation-2026-08-15.opus5.md`(方案稿,基线 main @ 27cbcaf)。改动一(§3 发单数量收敛)核实通过;**改动二(§4)的验收论据与实现契约存在 3 处必须返工的缺陷**,全部集中在「等价性证据」与「字段契约」上,取舍本身(问题 1)正确。

---

## 五问逐答

### 问题 1:§4「就地计算 vs 复用 cycle_slippage_pct」——**取舍正确,三点差异全部属实**

| 方案主张 | 核对结果 |
|---|---|
| 持仓均价分母是 priced qty + incomplete 标记 + 全未知回退 0 | 属实,`store.py:2826-2836`(回退 `Decimal(0)` 并置标记,注释 G5) |
| 滑点任一腿不可定价/非正返回 `None` | 属实,`store.py:2585-2594`(`None`/非有限/`<=0` 全部 `return None`) |
| 分桶键不同 | 属实,持仓 `(coin, direction, cycle_id)`(`store.py:2774,2825`)vs 滑点 `(cycle_id, task_type)`(`store.py:2563`) |

复用确实会让「当前显示数字、均价不完整」的行降为 `—`,是行为变化。附加差异(同向支持就地计算):`cycle_slippage_pct` 的均价经 `_cycle_leg_basis_locked` 的 `fmt_decimal` 序列化再回读(`store.py:2559`),与持仓页前端直接解析 `spot_avg` 字符串的精度路径也不同。**就地计算是正确选择。**

### 问题 2:§3 `resolve_send_qty`——**确实零行为变化**

- `AttemptContext.single_amount` 注解为 `Decimal`(`backend/hedge_open_tasks/executor.py:45`);
- 唯一生产构造点 `service.py:3639` 传 `D.Decimal(task["single_amount"])`——与 `service.py:3570` 同源同值;
- 全部 5 处测试构造点(`test_hedge_executor.py:47,159`、`test_hedge_wire_constraints.py:45,243`、`test_hedge_review2_regressions.py:350`、`test_live_hedge_executor.py:115`)均传 `Decimal`;
- 统一函数内 `Decimal(single_amount)` 对已是 `Decimal` 的输入是幂等精确拷贝,不触发 context 舍入,也不引入新异常路径(`Decimal(Decimal)` 永不抛)。

### 问题 3:第三个候选——**未发现符合标准的,同意不扩**

已独立排查:`compute_opening_spread_pct` 是单一实现(`snapshot.py:613`),前端只读后端字段做格式化(`index.html:2497` 注释、`2549-2561`),无第三份;历史页滑点列(`index.html:5398-5399`)读后端 `open_slippage`/`close_slippage` 字段,不现算;`_client_order_ids` 三处调用共享单一实现(`fakes.py:29` 已 import);前端 `direction === 'forward'` 均为纯标签/配色,无后端对应重复。腿加权均价在 `_cycle_leg_basis_locked`(`store.py:2530-2561`)与 `aggregate_positions` 各有一份,但口径差异正是问题 1 论证的核心(刻意不同),且无实证漏改证据——按方案自己的标准不入选,**不列为候选**。

### 问题 4:§5 边界——**大体划得住,「不动公式 A」正确,但 no_task 行处理语焉不详**(见阻塞项 3)

公式 A 无重复可合(见问题 3),且是冻结契约(`snapshot.py:613` 注释)、平滑门资金判定(`domain.py:1588,1591`),不动正确。`merge_positions` 对 bucket 是 `dict(bucket)` 整行透传(`domain.py:2246` 附近),新字段值自动流过,边界无遗漏——**除阻塞项 3**。

### 问题 5:§6 验收——**不充分,核心证据自相矛盾**(见阻塞项 1、2)

---

## 问题清单

**[R1|in-range|阻塞] §4/§6.1 的「等价性证据」与 fixture 事实矛盾——两条硬编码断言改后必然失败**
`frontend/self-check.js:5075` fixture AUSDT 行 `open_basis_rate: 0.00233`、`:5081` RSR 行 `open_basis_rate: 0`,与各自均价现算值(forward `(102.3333−101.3333)/101.3333 = 0.009868`、reverse `(0.00125−0.001246)/0.001246 = 0.003210`)**不相等**——fixture 里是随意占位数,现版前端现算时被忽略。改动二删掉 `computeHedgeOpenBasisRate` 改读字段后,渲染变为 `+0.2330%` / `0.0000%`,`self-check.js:5113/5116` 的 `+0.9868%` / `+0.3210%` 断言**必挂**。方案 §4 称「这两条断言必须原样继续通过——正是零行为变化的现成证据」,该论据不成立;且与 §6.1「不得修改任何既有断言以适配改动」自相矛盾:保住断言字符串的唯一途径是把 fixture 的 `open_basis_rate` 更新为与均价一致的值,而方案未授权也未提及此更新(第二组 fixture `self-check.js:5176,5186` 同值,需同步;`self-check.js:8799` 的 `'0'` 所在测试无价差断言,不受影响)。方案必须改写:明示 fixture 数据随新契约更新、断言字符串不动,并把「零行为变化」证据改为 §6.2 的改前/改后逐字符比对。

**[R2|in-range|阻塞] `open_basis_rate` 的单位契约未定义——仓库内两种口径并存,实现者各抄一份就是事故**
前端 `formatHedgeBasisRate` 链路期望**小数比率**(0.01 = 1%,`index.html:5262-5266` 先 `×100` 再 `toFixed(4)`);而同族后端字段 `cycle_slippage_pct` 输出**百分数字符串**(`store.py:2603`,`f"{...:.4f}"`,前端历史页直接 `Number(x).toFixed(4)+'%'`,`index.html:5398`)。方案 §4 伪代码不带 `×100` 但未写明序列化形态与前端渲染路径(`formatHedgeBasisPct` 改后是否仍适用)。若实现者参照滑点口径填百分数,前端会二次放大 100 倍。须在方案中定死:字段单位、字符串/数值形态、量化方式(建议显式 `ROUND_HALF_UP` 对齐 JS `toFixed(4)` 的显示语义;Python 默认 `ROUND_HALF_EVEN` 与 JS 在 `x.xxxx5` 边界可能差一位)。

**[R3|in-range|阻塞] `domain.py:2000` no_task 兜底行「占位同步处理」不足——照字面实现就是行为变化**
该行 `spot_avg`/`perp_avg` 均为 `None`(`domain.py:1994-1995`),改前前端 `computeHedgeOpenBasisRate(null, null, …)` → `NaN` → 渲染 `—`;若改后仍填 `"0"`,前端读字段经 `formatHedgeBasisPct(0)` 渲染 `0.0000%`——可见输出变化。方案须明确 no_task 行及「任一均价非正/非有限」时的序列化形态(应为 `null`,前端 `hedgeNum(null)` → `NaN` → `—`,与现状逐字符一致)。

**[O1|观察] §2 现状描述经核实全部属实**:公式 A 单一共享无重复、前端只读字段;公式 B 真重复仅 Python(`store.py:2563`)/JS(`index.html:5249`)一处;公式 C 三处字面重复(`service.py:3570`、`live_hedge_executor.py:828`、`fakes.py:152`,与乘数轮 r3 §3.1 清单完全一致)。更正成立。

**[O2|观察] 后端既有测试不受改动二破坏**:`open_basis_rate` 在后端测试中均为构造输入(`test_positions_merge.py:30`、`test_hedge_cycle_core.py:373-386`)或字段存在性集合(`test_hedge_api.py:69`),无对输出值 `"0"` 的断言;merge 层 `dict(bucket)` 透传。§6.1 的「现有测试原样通过」对后端成立,冲突只在前端 fixture(即 R1)。

---

## 修复要求(下一版方案稿)

1. 改写 §4 末段与 §6.1/§6.2:删除「self-check 断言原样通过是零行为变化证据」的说法;明示需将 `self-check.js` 两组 fixture(`5075/5081`、`5176/5186`)的 `open_basis_rate` 更新为新契约下与均价一致的值,断言字符串不动;等价性证据以改前/改后逐字符比对为准。
2. 在 §4 增加「字段契约」小节:单位(小数比率 vs 百分数,二选一并说明前端渲染路径如何对应)、序列化形态、量化方式(显式舍入模式)、空值形态(`null`)。
3. 在 §4 明确 `domain.py:2000` no_task 行输出 `null`(或其他能渲染 `—` 的形态),并纳入 §6.4 边界测试。

改动一(§3)无需修改,可原样保留。R1–R3 均为方案文本修订,不涉及扩大代码范围。

---

```text
[TASK_RESULT v2]
任务 ID: review-duplicate-concept-consolidation-2026-08-15
执行结果: completed（完成）
结果摘要: 只读评审收敛方案稿。改动一(发单数量)核实零行为变化通过;改动二取舍正确但验收证据与字段契约有 3 处阻塞缺陷,REWORK。
产物: [docs/planning/duplicate-concept-consolidation-2026-08-15.opus5.md]
检查结果: [五问逐一核对 pass, 问题1 取舍正确 pass, 问题2 类型等价核实 pass, 问题3 独立搜索无第三候选 pass, 问题4 边界核实(no_task 行缺口) pass, 问题5 发现 fixture 矛盾与单位契约缺失 pass]
阻塞项: [none]
评审结论: REWORK（返工）
问题记录: none
修复要求: none
本地北京时间: 2026-08-15 17:05:20 CST
下一步模型: Human（决策者）
下一步任务: 读取：本回复问题清单 R1-R3；执行：将三条阻塞项反馈给方案作者修订方案稿；关卡：Human 确认修订后再评
[/TASK_RESULT]
```

只读评审任务。不要修改仓库任何文件，不要实现代码。

对象：docs/planning/duplicate-concept-consolidation-2026-08-15.opus5.md
仓库：/Users/ark/Desktop/ai code/funding_hedging，分支 main，提交见下
状态：方案稿，代码一行未改。Human 已决定：改动小，不开 stage。

背景：乘数换算方案（同目录 leg-unit-size-conversion-2026-08-15.opus5.md，现 r3）
连续三轮被评审挑出同一类遗漏——同一个概念散在多处实现，按文件打补丁必然漏。
本方案是它的前置铺垫：把两个已被实证漏改过的概念各自收敛到一处，均为纯重构、
零行为变化。做完之后乘数轮的改动点各减一个。

请按仓库 AGENTS.md 的评审口径给出 ACCEPT 或 REWORK，逐条列出问题并附路径与行号。
以下五问必须逐一正面回答（即方案 §7）：

【问题 1，最高优先级】§4 的「就地计算 vs 复用 cycle_slippage_pct」取舍是否正确？
本方案主张在 aggregate_positions 内、spot_avg/perp_avg 算出的同一处就地计算
open_basis_rate，而不复用 store.py:2563 的 cycle_slippage_pct。理由是二者取数口径
不同：前者分母是 priced qty 并带 incomplete 标记、全未知时回退 0（store.py:2826-2836
注释 G5）；后者在任一腿不可定价时返回 None（store.py:2585-2593）；分桶键也不同
（(coin,direction,cycle_id) vs (cycle_id,task_type)）。请核对该差异是否属实。
若二者实际等价，则复用是更好的选择，请明确指出。

【问题 2】§3 的 resolve_send_qty 是否真的零行为变化？
service.py:3570 用 D.Decimal(task["single_amount"])，而 live_hedge_executor.py:828
与 tests/fakes.py:152 用 ctx.single_amount。二者类型是否等价？若 ctx.single_amount
已是 Decimal 而 task 列是字符串，统一转换是否可能改变精度或异常行为？

【问题 3】是否还有第三个「同一概念多处实现」值得一并收敛？
请独立搜索。判定标准：该概念已被实证漏改过，或跨语言/跨层重复实现。
不要列出仅仅「看起来可以抽象」的候选——本方案刻意不做广义重构，列出投机性候选
会被视为范围蔓延。

【问题 4】§5 的边界是否划得住？
有无遗漏的、不做会导致本方案不完整的项？特别核对：不动 compute_opening_spread_pct
（冻结契约、平滑门资金判定）这个决定是否正确。

【问题 5】§6 的验收是否足够证明零行为变化？
特别是改动二：前端 JS 用 Number（float64）算，后端 Python 用 Decimal 算。是否存在
精度或格式化差异路径，会让同一份持仓数据在改前改后渲染出不同的百分比字符串？
frontend/self-check.js:5110-5117 有两条硬编码断言（+0.9868% / +0.3210%），本方案
把它们当作等价性证据——这个用法是否可靠？

另请留意：本方案 §2 更正了我早前一处错误描述（曾称「两腿价差有三份彼此独立的实现」，
实际是 compute_opening_spread_pct 已是单一共享函数无重复，真重复只有 Python/JS 一处）。
若你发现 §2 的现状描述仍有不准确处，请指出。

约束：只读；不要改任何文件；不要实现；结论写在你的回复里。

只读评审任务。不要修改仓库任何文件，不要实现代码。

对象：docs/planning/leg-unit-size-conversion-2026-08-15.opus5.md
仓库：/Users/ark/Desktop/ai code/funding_hedging，分支 main，提交 b075c56
状态：设计稿，代码一行未改。

背景：6 个 1000x 乘数币（BONK/FLOKI/LUNC/PEPE/SHIB/XEC）当前被 fail-closed 挡住、无法对冲，因为执行链两腿发同一个 q_common 而 1 张合约 = 1000 个币。本方案设计两腿数量换算，让这 6 个币恢复对冲能力。

请按仓库 AGENTS.md 的评审口径给出 ACCEPT 或 REWORK，逐条列出问题并附文件路径与行号。以下五问必须逐一正面回答：

【问题 1，最高优先级】§5 的三条「不用改」推导是否成立？
方案选定「现货币的个数」为全系统唯一量纲后，声称 est_price、minNotional、required 两分支这三处无需改动。核心论据是「USDT 名义价值在换算下是不变量」：
  现货腿 = 个数 × 现货价
  合约腿 = (个数 ÷ 面值) × (现货价 × 面值) = 个数 × 现货价（同一个数）
请独立验算，并核对以下真实代码：
  backend/hedge_open_tasks/domain.py:1083（notional）
  backend/hedge_open_tasks/domain.py:1344（forward required）
  backend/hedge_open_tasks/domain.py:1352（reverse required）
  backend/services/hedge_preflight_provider.py:862（est_price 取现货价）
任一条推导不成立，请明确指出该处必须加回改造清单。这是本方案相对 PROJECT_STATE 旧清单的净减项（8 处降为 7 处），是最大单点风险。

【问题 2】§3.1 存「每条腿的单位面值」而不是「这一对的倍率」，是否值得？
理由是不焊死「必有一腿是现货、面值恒为 1」这个假设，为将来合约对合约留形状。若你认为这是过度设计（YAGNI），请说明退回「表加一列倍率」的实际代价。

【问题 3】§4 的 7 处改造 + §4.1.1 的 fail-closed 是否完整？
请独立搜索是否存在方案遗漏的、涉及数量或价格的计算点。特别注意 close 路径、smooth 路径、划转备料路径、持仓聚合路径。遗漏一处就可能造成单腿敞口。

【问题 4】§6 价格比值护栏的容差取多少合适？
用合约标记价 ÷ 现货价反推面值，与表中声明值比对，不符则拒绝发单。需要一个既能抓数量级错误、又不会被基差与资金费率误触的值。方案暂定 ±5%。

【问题 5】§9 的验收是否足够？
PROJECT_STATE 明确指出：这是量纲错误，单元测试很容易两边用同一个错误假设而全绿。方案的对策是价格比值护栏（外部真值）加最小额度实盘核对交易所实际持仓数量。是否还有更早、更便宜就能发现错误的手段？

约束：只读；不要改任何文件；不要实现；结论写在你的回复里，不要写进仓库。

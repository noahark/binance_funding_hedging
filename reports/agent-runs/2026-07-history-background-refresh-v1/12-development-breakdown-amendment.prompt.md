# Development Breakdown Amendment Prompt

你是本阶段原 development breakdown（开发拆解）作者 Claude Opus 4.8。
继续使用当前同一会话，并继续应用 `task_planner`（任务规划）skill。

只修改：

`reports/agent-runs/2026-07-history-background-refresh-v1/12-development-breakdown.md`

不得修改 intake、task、design、ADR、status、handoff、源码、测试或其他文件；不得提交、
推送、合并、调用其他模型或开始实现。保留现有拆解内容，只做以下最小修订：

1. 消除 30 秒超时后的发布竞态。当前 §4.3 的 `RefreshSymbolCommand` 没有 deadline
   （截止时间）或取消字段，但 §10 又同时写“worker 继续”和“超时不替换已发布状态”。
   按冻结契约补成可实现规则：命令创建时记录共享的 monotonic deadline（单调时钟截止
   时间，默认创建后 30 秒）；同 symbol 的并发 waiter（等待者）共享该命令和截止时间；
   worker 可以完成已开始的上游 I/O，但必须把选中行结果暂存在本地，并在写 domain
   cache（领域缓存）及替换 `PublishedState` 前再次检查 deadline。若已过期，则不得提交
   本次 history/domain-cache 变更、不得发布新版本，只完成命令并让端点返回上次已发布
   行的 `refresh_status:"timeout"`。PrivateClient transport cache（私有客户端传输缓存）
   可能已被签名请求自身更新，这不构成 domain publication（领域发布），但必须明确该
   区别。增加对应确定性测试：用可控 monotonic clock（单调时钟）证明第 31 秒完成不会
   发布，而截止前完成只发布一次。不要引入每个 waiter 独立取消、通用取消框架或新线程。

2. 把用户已经裁定的点击规则写清：v1 必须包含前端“点击后该行 1 秒不可点击”以及
   “同 symbol 命令 in-flight（执行中）时忽略再次激活”。完成后再次刻意点击仍触发一条
   新命令。只有 worker 侧“完成后的额外 cooldown（冷却窗口）/结果复用”留到 v1.1，
   不再把前端 1 秒防连点列为剩余人类决策。删除 §14 中对应待决项，并修正 §13.10，
   不得新增 watched set（关注集合）、interest TTL（关注时效）或优先级状态。

3. 把 actual-rate（真实借币利率）的 force-TTL（强制绕过时效缓存）精确键落实到现有
   API 形状：点击路径调用 `fetch_cost_leg_chain([asset], force=True)`，因此 E2 的
   params 必须是单资产 `{"assets": asset, "isIsolated": "false"}`，E2b 是
   `{"asset": asset}`；只 evict（移除）这两个本次单资产精确键以及 maxBorrowable 的
   `{"asset": asset}` 精确键。不得删除 scheduled refresh（定时刷新）形成的多资产
   batch（批次）键，不得清空共享缓存，不得强刷 account info/crossMarginData/classic/VIP。
   测试需覆盖“单资产键刷新、多资产批次键仍保留”。

4. 将 offline（离线）同步旧路径明确限定为测试/离线兼容例外；live server（在线服务）
   即使 kill switch（紧急开关）关闭，也不得让 `/api/public-market/snapshot` 回退到请求
   路径同步上游抓取。若 kill switch 关闭且没有已发布状态，返回 503；若已有状态，继续
   返回 last-good（最近成功）发布状态。相应修正 §4.6、§5 与请求路径测试，确保符合
   `00-task.md` 的“在线 full snapshot 零上游请求”验收。

完成后在回复中只报告：修改的文件、四项修订落点、READY/BLOCKED、当前 Claude session
ID。不要改 bookkeeper（台账员）文件。

本地北京时间: 2026-07-12 23:41:11 CST
下一步模型: Claude Opus 4.8
下一步任务: 最小修订 12-development-breakdown.md，消除超时发布竞态及三处实现歧义

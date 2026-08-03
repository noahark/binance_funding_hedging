四份规划产物已完成。先用大白话说清楚这轮拆了什么、Human 需要知道什么：

做了什么
把已通过评审的方案，拆成两个不重叠的实现任务，并在动手前先把两边必须一致的「数据长什么样」写死：

- 后端（Claude-GLM）：下单路由 + 行情页数据 + 契约/schema + 后端测试，最后交一个本地提交。
- 前端（Grok）：只做页面上的标记，等后端提交并被固定编号后才开工，读的是后端已提交的正式契约。

三个可能影响你判断的点

1. 接口层我替方案补了两处它没写死的边界：一是「接口临时读失败但之前读到过 → 继续显示上次结果并标出截至时间」，未知只留给「从头到尾没读成功过」；二是「这一行根本没有现货腿 → 显示为不适用，而不是未满」。两条都遵循「不知道就不许说没满」的原则，也都不放宽下单预检每次必须重新读的要求。已具名列出，交给评审复核。
2. 这张名单要用 API key 才能读。所以后端离线或私有通道关掉时，行情页这一列会整列显示「未知」——这是诚实降级，不是坏了，但你会看到一整列未知。
3. 评审人选比平时窄：Grok 这轮是前端作者，所以它不能再当 review-1（平时的备选就是它）。建议 review-1 用 Kimi、review-2 用 DeepSeek；如果 review-2 想用 Opus5 也合规，但因为方案和这份拆分都是 Opus5 写的，必须在评审里说明这一点。

另外提醒：两份 dispatch 里的 status_revision 我预填了 6 和 7，Bookkeeper 投递前按当时实际编号核一下。

[TASK_RESULT v2]
任务 ID: task-breakdown-1
执行结果: completed（完成）
结果摘要: 四份规划产物落盘。接口约定 v0.9 冻结 rows[].collateral_cap {exceeded, asset, checked_at}、三态+不适用真值表、两个 ui_flags、匹配单点与缓存硬边界；backend-2(claude_glm) 与 frontend-1(Grok) 的 Allowed Files 零交集，前端须待后端提交并固定 SHA 后启动；review-1 建议 Kimi（Grok 因是前端作者不可用），review-2 建议 DeepSeek。未改方案、契约、schema、代码、状态或既有 dispatch。
产物: [reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/implementation-interface-v0.9.md, reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/implementation-backend-2.dispatch.md, reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/implementation-frontend-1.dispatch.md, reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/task-breakdown-1.md]
检查结果:
1. [pass] 仅新增上述四份产物；方案、契约、schema、代码、状态、证据、implementation-backend-1.dispatch.md 均未改动（git status 无越界项）。
2. [pass] 接口未另造产品规则：collateral_cap 独立于 margin_public 与 negative_funding_status；展示命中不看费率符号；未知/缺键/表外组合一律不得渲染为未满；展示缓存与开单预检不共用且要求专门隔离测试。
3. [pass] 共享 JSON 形状只在 implementation-interface-v0.9.md 详述，对外最终权威明确指向后端交付写入的 docs/api/public-market-contract.md v0.9 amendment。
4. [pass] 两份 Allowed Files 零交集（task-breakdown-1.md §3 边界表）；backend/tests/fixtures/** 两侧都禁改，前端沿用 self-check 内存注入先例。
5. [pass] backend-2 覆盖路由方向（负费率不读名单）、五条 exact allowlist 硬绑定、leg 行 endpoint 审计、契约/schema v0.9、fake transport 后端测试；frontend-1 覆盖资产列高亮、三态+截至时间、fixture、self-check，且不改后端代码。
6. [pass] frontend-1 启动前提写明为 backend-2 本地提交 + Bookkeeper 固定 SHA，禁止基于臆测或未提交字段开发。
7. [pass] 两份 dispatch 各恰好一个 agents/skills/senior-developer.md，含明确测试命令、单次本地提交边界，Stop 含无凭证、无 Binance、无真实 POST、不改 Start gate。
8. [pass] 五项接口裁定 I-1..I-5 已具名并附方案依据；其中 last-good 与「不适用」两项列为评审须核对项，未运行时联调的覆盖缺口已原样记入风险。
阻塞项: [none]
本地北京时间: 2026-08-03 00:39:27 CST
下一步模型: Bookkeeper（codex）
下一步任务: Human 将本原始回执交回 Bookkeeper（codex）；Bookkeeper 核验四份产物后校对 status_revision（backend-2 预填 6、frontend-1 预填 7），先投递 implementation-backend-2.dispatch.md（claude_glm），待其本地提交 SHA 固定后再投递 implementation-frontend-1.dispatch.md（Grok），两个终端均由 Human 启动。之后按固定 1a55781..<前端提交> 走 review-1（建议 Kimi）与 review-2（建议 DeepSeek）。本拆分不授权实现、合并、开闸或实盘。
[/TASK_RESULT]

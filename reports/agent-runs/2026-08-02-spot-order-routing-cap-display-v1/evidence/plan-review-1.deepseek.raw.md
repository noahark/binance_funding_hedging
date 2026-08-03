[TASK_RESULT v2]
任务 ID: plan-review-1
执行结果: completed（完成）
结果摘要: HIGH_RISK 独立计划评审完成。六项接缝核验通过；两项 in-range 缺陷需返工（§3 路由缺方向限定、restricted-asset 未登记 allowlist）。修复方向已经 Human 两项裁定定稿：负费率方向不读名单不走普通现货，平仓留以后；保留 allowlist 机制，新接口照常登记。
产物: [none（只读评审未写文件；发现与修复要求均在本回执内）]
检查结果:
1. [pass] §D 六项 Human 裁定均忠实进入方案，未重述为未决问题；§10 问题未重开 A-1/A-2/A-3/B-1/B-2/B-6。
2. [pass] Bookkeeper 注记化解字面 SPOT blocker 矛盾且自限范围；PROJECT_STATE.md 具备事实/影响/接受理由/观察方式/重审条件。
3. [pass] attempt 权威链完整：hedge_open_leg.endpoint 唯一权威、PRODUCT_SPOT、普通现货 host/endpoint/参数/查单/限频分离、合约腿 PAPI 边界（代码核验 domain.py:569-570/625-644、service.py:48/2181、store.py:86/153、live_hedge_executor.py:385/713-721、hedge_open_live_client.py:57-65/277 一致）。
4. [pass] 展示三态（已满/未满+截至时间/未知含鉴权失败）、独立 collateral_cap 块、资产高亮、明确不进 negative_funding_status 借贷列。
5. [pass] §6.4 硬边界+验收 #11 缓存隔离测试、#12 匹配规则单点，足以防实现期打通。
6. [pass] 契约三闸门、margin_public.source 原因更正、v0.9 amendment 形状明确（现契约 v0.8 于 :989）。
7. [fail] §3 路由决策未限定方向：负费率方向存在现货 SELL 腿（domain.py:625-644），步骤 4 无条件选 regular_spot 与 §1「普通现货 SELL 降级」边界冲突。Human 裁定：负费率方向不受名单约束、不选 regular_spot、维持既有 PAPI 路径，平仓留以后（A-6 P1-1 已闭环不重开）。修复：§3 增写方向限定句 + §9 新增「负费率命中名单/bStock 仍走既有 PAPI 路径」验收。
8. [fail] restricted-asset 读取通道未纳入 deny-by-default allowlist：§4 枚举仅含下单/查单/账户/限频；hedge_preflight_provider.py:14-18/286/311/333 私有读取全经 HedgeOpenLiveClient，其 ALLOWLIST（hedge_open_live_client.py:57-65）现仅 PAPI，照 §4 实现即全量开单静默 fail-closed 或诱导绕过。Human 裁定：保留 allowlist 机制，新接口照常登记。修复：§4/§8 显式登记 ("GET","/sapi/v1/margin/restricted-asset")、("POST","/api/v3/order")、("GET","/api/v3/order")、("GET","/api/v3/account")、("GET","/api/v3/rateLimit/order") 至 api.binance.com，声明预检与展示两路读取均受 allowlist 管控且 host 硬绑定；§9 新增「allowlist 含上述路径、未登记路径调用被拒」断言。
阻塞项: [none（返工项见检查结果 7/8，修复方向已经 Human 裁定定稿）]
评审结论: REWORK（返工）
问题记录: docs/planning/spot-order-routing-v1.md
修复要求: docs/planning/spot-order-routing-v1.md（按检查项 7/8 所列 Human 裁定修法修订：§3 方向限定句 + §4/§8 allowlist 登记 + §9 两条新验收；修订后重新提交跨 provider 计划评审，按 §8 计划评审豁免不触碰 rework_count）
本地北京时间: 2026-08-02 23:57:11 CST
下一步模型: Bookkeeper（codex）
下一步任务: Human 将本原始回执交回 Bookkeeper（codex）；Bookkeeper 核验后把检查项 7/8 转 Planner 修订方案，修订完成后重新准备计划评审 dispatch（DeepSeek 或另一 provider，保持跨 provider 独立性），由 Human 启动下一终端。ACCEPT 前不授权实现、开闸或实盘。
[/TASK_RESULT]

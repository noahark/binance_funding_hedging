# 11-adr：设计决策草稿

## ADR-1 固定阈值 0.03%，不做可配置输入

本阶段只实现用户指定的单个默认选中选项：隐藏 `≤0.03%` 日费率。避免引入阈值输入、localStorage 偏好和额外校验复杂度。

## ADR-2 阈值按绝对日费率比较

日费率有正负；低价值噪音应同时覆盖 `+0.03%` 与 `-0.03%`。草稿按 `abs(daily_funding_rate) <= 0.00030000` 过滤。`null` 不由该过滤器隐藏。

## ADR-3 余额数量保留原始精度，折算值保留 2 位

数量是资产原始余额，展示应保留精度；`value_usdt` 是估值展示，沿用现有 `formatUsdt2` 的 2 位 ROUND_HALF_UP。两者拆成独立行，避免 `【: ...】` 语义不清。

## ADR-4 贵金属标签命名为 METAL

新增 `asset_tag=METAL`，覆盖 `XAU/XAG/COPPER/XPT/XPD`。使用 baseAsset 精确匹配，优先于 `PERPETUAL -> CRYPTO` 默认规则。初版不新增 `negative_funding_status` 禁用态。

## ADR-5 serial 单轨

该需求跨 backend/schema/docs/frontend/tests，但规模小且不可拆成中间态。采用 serial 单轨，用户确认草稿后由一个实现者完成单批 diff，再走 review-1 / review-2。

本地北京时间: 2026-07-08 02:23:15 CST
下一步模型: human
下一步任务: 确认 ADR 草稿，尤其 ADR-2 和 ADR-4。

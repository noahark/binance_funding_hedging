# 11-adr：设计决策草稿

## ADR-1 固定阈值 0.03%，不做可配置输入

本阶段只实现用户指定的单个默认选中选项：隐藏 `|日费率| <= 0.03%`。避免引入阈值输入、localStorage 偏好和额外校验复杂度。

## ADR-2 阈值按绝对日费率比较

日费率有正负；低价值噪音应同时覆盖 `+0.03%` 与 `-0.03%`。草稿按 `abs(daily_funding_rate) <= 0.00030000` 过滤。`null` 不由该过滤器隐藏。

## ADR-3 余额数量保留原始精度，折算值保留 2 位

数量是资产原始余额，展示应保留精度；`value_usdt` 是估值展示，沿用现有 `formatUsdt2` 的 2 位 ROUND_HALF_UP。两者拆成独立行，避免 `【: ...】` 语义不清。

## ADR-4 金属标签命名为 METAL，且不禁用借币

新增 `asset_tag=METAL`，覆盖 `XAU/XAG/COPPER/XPT/XPD`。使用 baseAsset 精确匹配，优先于 `PERPETUAL -> CRYPTO` 默认规则。因集合包含 `COPPER`，前端显示为 `METAL(金属)`，`asset_tag_source` 使用 `base_asset_metal_symbol`。

用户裁定：金属产品不一定禁止借币，部分品种可能可借，具体以接口返回为准。因此本阶段不新增 `DISABLED_METAL`，不改变 `negative_funding_status` enum；`METAL` 若满足 `MARGIN_SPOT_CANDIDATE` 和负日费率，应进入只读 borrow validation 候选，最终可借性、可借额度和成本由接口结果决定。`asset_tag_for(contract_type, base_asset="")` 保留默认参数，兼容既有单参数调用。

## ADR-5 低费率过滤测试不破坏默认 self-check 基线

低费率过滤需要边界样本 `0.00030000`、`-0.00030000`、`0.00030001`，但不能把现有默认 6 行 self-check 场景改成新的默认行数基线。实现应使用独立 fixture/deep-copy 场景断言过滤行数差值。

## ADR-6 serial 单轨

该需求跨 backend/schema/docs/frontend/tests，但规模小且不可拆成中间态。采用 serial 单轨，用户确认草稿后由一个实现者完成单批 diff，再走 review-1 / review-2。

本地北京时间: 2026-07-08 09:28:44 CST
下一步模型: codex
下一步任务: 生成实现任务书并进入 serial implementation。

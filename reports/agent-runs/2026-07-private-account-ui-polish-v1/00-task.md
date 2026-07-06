# Task: Private Account UI Polish V1

## Objective

在 `2026-07-private-account-v1` 已交付契约之上,对个人账户与借币信息做四项前端展示
打磨,提升可读性与透明度。**不改后端公开契约、不新增交易能力。**

## Scope

1. 净收益行展示日借币利率数值:在净收益列旁展示
   `rows[].borrow_validation.classic_margin.daily_interest_account`(账户档);无账户档时
   回落 `daily_interest_vip0`(VIP0 参考档)并标注其为参考。
2. `negative_funding_status` 派生文案:保留原始结构字段不动,前端按 `borrow_validation`
   派生展示文案:
   - verified=true + pair_listed=true + asset_borrowable=true → "已验证可借"
   - verified=true + pair_listed=false → "杠杆交易对未列出"
   - verified=true + asset_borrowable=false → "资产不可借"
   - verified=false + error=not_probed_this_round → "未探测(限速预算)"
   - 私有通道关闭/失败 → "需私有验证"
3. 个人账户面板上移:将 private_account 面板从页面底部移动到市场表(费率行情表)上方。
4. 持仓每资产折算 USDT:个人持仓每个资产行新增该资产折算成 USDT 的价值(数量 × 价格)
   展示注明。优先用现有 payload 估值;若需后端补逐资产折算字段,在 design 阶段界定边界。

## Non-Goals

- 不修改公开 snapshot 契约(schema)。若第 4 项确需后端字段,须走契约变更判定,默认避免。
- 不新增/改动 order、borrow、repay、transfer、websocket 等任何交易或写行为。
- 不改动净收益算法、成本腿链、排序语义(sort_basis)。
- 不改动私有通道开关、鉴权、TTL 等后端读取逻辑。
- 不改部署基础设施。

## Acceptance Criteria

- 净收益行在有借币利率数据时展示数值;缺失时展示占位(—),不白屏。
- `negative_funding_status` 五种派生文案按上表正确映射;结构字段本身不变。
- 个人账户面板渲染在市场表之上;private_channel 关闭/失败时仍优雅降级不白屏。
- 持仓每资产展示折算 USDT 值;无价格时展示占位,不报错。
- 前端 self-check(`frontend/self-check.js`)覆盖上述展示分支并全绿。
- UI 中文优先(见 memory `ui-chinese-first`)。

## Follow-up 溯源

- memory: `followup-borrow-rate-on-row`（第 1 项）
- memory: `followup-negative-funding-status-ui-labels`（第 2 项）
- memory: `followup-private-account-panel-ui`（第 3、4 项）

本地北京时间: 2026-07-06
下一步模型: 待用户确认(设计/实现派 GPT/Codex;Fable5 做 review-2)
下一步任务: stage-design（跳过 direction panel）

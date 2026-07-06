# Stage Intake And Complexity

## User Discussion Summary

用户验收 `2026-07-private-account-v1`(在线模式)后,提出四项**个人账户 / 借币展示**的
前端打磨需求,全部为已交付功能的展示层增量,不改后端契约、不新增接口、不涉及交易行为。
命名沿用仓库惯例(`2026-07-<slug>-v1`),定位为 private-account 线的 UI 打磨。

四项需求(均见对应 memory follow-up):

1. **净收益行补借币利率数值**:净收益列已减去借币成本,但页面只有成本来源徽标
   (`borrow_rate_source` 枚举),看不到被减掉的日借币利率。展示
   `rows[].borrow_validation.classic_margin.daily_interest_account`(账户档)/
   `daily_interest_vip0`(VIP0 参考档)。
2. **`negative_funding_status` 派生文案**:`PRIVATE_BORROW_VALIDATION_REQUIRED` 是
   结构分类字段(非私有验证结果),页面误当"需验证"展示。前端按 `borrow_validation`
   派生直观文案,冻结契约不动。
3. **个人账户面板上移**:个人账户信息从页面最下面 → 提到市场表(费率行情表)之上。
4. **持仓每资产折算 USDT 注明**:个人持仓每个资产行新增"折算成 USDT 价值"
   (数量 × 价格)的展示注明。

## Classification

- Complexity: `LOW`
- Direction panel required: `false`
- Existing synthesis covers this work: `true`（private-account-v1 契约与净收益/borrow
  语义已冻结,本 stage 仅在其展示层增量;四项均为该 stage 验收时的 follow-up）
- User approved lightweight route: `true`（用户 2026-07-06 明确批准以此命名起草并推进）
- Lightweight skip allowed: `true`

## Rationale

- Reason: 四项全部是**已交付 payload 字段的前端展示**——补数值、改文案、调布局、加折算列。
  无公开契约变更、无新后端端点、无交易/借币/下单/撤单/转账/websocket 行为变化、无排序
  语义变化。风险面局限在前端渲染,LOW 合理。
- 折算 USDT 所需估值后端 P5 已用 public ticker `price_map` 完成(`assemble_private_account`);
  若 payload 未逐资产给出折算值,可能需要极小的后端派生字段补充(设计阶段界定)。

## Human Gates

- Gate: 模型派发待用户确认——设计/实现应由实现模型(GPT/Codex)承担;Fable5 保持
  bookkeeper + review-2 干净身份,不做设计/实现。
- Gate: 若第 4 项需要新增后端派生字段(逐资产折算 USDT),涉及 payload/契约边界,
  需在 design 阶段判定是否触发契约变更门(冻结契约优先,尽量纯前端计算)。

## Routing Decision

- Next node: `stage-design`（跳过 direction panel;LOW + 用户批准 lightweight route +
  既有 synthesis 覆盖）

## Bookkeeper

- Provider/model/session: Claude / Fable5（续任 bookkeeper + 预定 review-2）
- Independent from implementers: `true`（设计/实现将派给 GPT/Codex,Fable5 不实现）
- If not independent, disclosure: N/A（bookkeeper≠implementer;reviewer≠implementer 红线不破）

## Parallel Mode

- Uses `docs/parallel-development-mode.md`: `false`（单前端任务,不拆双端）
- R10 dispatch tail required: `false`
- R4 diff reconciliation required: `false`

## Evaluator

- Provider: （待用户确认模型派发）
- Model: （待确认）
- Skill: complexity_evaluator

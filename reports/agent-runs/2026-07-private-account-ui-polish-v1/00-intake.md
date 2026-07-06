# Stage Intake And Complexity

## User Discussion Summary

用户验收 `2026-07-private-account-v1`(在线模式)后,提出四项**个人账户 / 借币展示**的
打磨需求。第 1~3 项为已交付功能的纯展示层增量;第 4 项(逐资产折算 USDT)经核实当前
payload 不暴露单资产价格,需 additive 契约变更(后端补逐资产估值/价格字段),故本 stage
为前端为主 + 一处 additive 后端/契约变更。不新增接口、不涉及交易行为。命名沿用仓库惯例
(`2026-07-<slug>-v1`),定位为 private-account 线的展示打磨。

四项需求(均见对应 memory follow-up):

1. **净收益行补借币利率数值(仅成本腿命中行)**:净收益列已减去借币成本,但页面只有
   成本来源徽标(`borrow_rate_source`),看不到被减掉的日借币利率。**仅当 `borrow_rate_source`
   非 null**(负费率借币候选、成本腿产出费率)时展示 `daily_interest_account`(账户档)/
   `daily_interest_vip0`(参考档);正费率行无借币腿,显示占位。
2. **`negative_funding_status` 派生文案**:该字段有契约结构优先级
   (PERP_ONLY / BSTOCK / SPOT_ONLY 优先于 PRIVATE_BORROW_VALIDATION_REQUIRED)。派生须
   先判结构禁用状态、保持结构文案;**仅 PRIVATE_BORROW_VALIDATION_REQUIRED 行**才按
   `borrow_validation` 细分,避免结构禁用行被误标"需私有验证"。冻结契约字段不动。
3. **个人账户面板上移**:个人账户信息从页面最下面 → 提到市场表(费率行情表)之上。
4. **持仓每资产折算 USDT**:个人持仓每资产行新增折算 USDT(数量 × 价格)。当前 payload
   只有聚合 `total_value_usdt`、不暴露单资产价格,**无法纯前端计算**。用户裁决允许
   additive 契约变更:后端按 `price_map` 补逐资产估值/价格字段传前端(字段形态 design 阶段
   界定)。触发**契约变更门**。

## Classification

- Complexity: `LOW`
- Direction panel required: `false`
- Existing synthesis covers this work: `true`（private-account-v1 契约与净收益/borrow
  语义已冻结,本 stage 仅在其展示层增量;四项均为该 stage 验收时的 follow-up）
- User approved lightweight route: `true`（用户 2026-07-06 明确批准以此命名起草并推进）
- Lightweight skip allowed: `true`

## Rationale

- Reason: 第 1~3 项是**已交付 payload 字段的前端展示**——补数值、改文案、调布局;第 4 项
  为一处 **additive 契约变更**(后端补逐资产估值/价格字段),仅加字段、不改既有语义。
  无新后端端点、无交易/借币/下单/撤单/转账/websocket 行为变化、无排序语义变化。风险面
  局限在前端渲染 + 一个可派生的 additive nullable 字段,仍判 LOW;但第 4 项须过契约变更门。
- 折算 USDT 所需估值后端 P5 已用 public ticker `price_map` 完成(`assemble_private_account`
  内部逐资产 `_usdt_value` 已计算,仅未逐行吐出);第 4 项即把该内部值/价格以 additive
  字段暴露到 payload,字段形态(后端算好 vs 传价格前端算)在 design 阶段界定。

## Human Gates

- Gate: 模型派发已裁决(2026-07-07)——**designer=Codex → implementer=Kimi →
  review-2=Claude/Fable5**。Codex 因 designer 身份依 Hard Gates ineligible 任 final
  reviewer;Fable5 兼 bookkeeper + final reviewer,均非 implementer,reviewer≠implementer
  红线不破。
- Gate: 第 4 项(逐资产折算 USDT)已裁决触发**契约变更门**——后端补 additive 逐资产估值/
  价格字段。design 阶段须产出 schema + 契约文档 + 测试同步方案,只加字段、不改既有语义。

## Routing Decision

- Next node: `stage-design`（跳过 direction panel;LOW + 用户批准 lightweight route +
  既有 synthesis 覆盖）

## Bookkeeper

- Provider/model/session: Claude / Fable5（bookkeeper + final reviewer/review-2）
- Independent from implementers: `true`（designer=Codex、implementer=Kimi;Fable5 不做设计/实现）
- If not independent, disclosure: N/A（bookkeeper≠implementer;reviewer≠implementer 红线不破）

## Parallel Mode

- Uses `docs/parallel-development-mode.md`: `false`（单特性、顺序执行,不拆双端）
- R10 dispatch tail required: `false`
- R4 diff reconciliation required: `false`
- Base 注:分支已 merge main@4549227(Harness v0.4)于 REWORK 裁决后并入,须重跑 checkpoint。

## Evaluator

- Provider: complexity 由 bookkeeper(Fable5)裁定 LOW,用户已批准 lightweight route
- Model: N/A（LOW + lightweight skip,未另派 evaluator 模型）
- Skill: complexity_evaluator

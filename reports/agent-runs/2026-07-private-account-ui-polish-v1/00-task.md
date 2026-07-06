# Task: Private Account UI Polish V1

## Objective

在 `2026-07-private-account-v1` 已交付契约之上,对个人账户与借币信息做四项展示打磨,
提升可读性与透明度。第 1~3 项为纯前端;**第 4 项(逐资产折算 USDT)需 additive 契约
变更(后端补逐资产估值/价格字段),走契约变更门。不新增交易能力。**

## Scope

1. 净收益行展示日借币利率数值(**仅成本腿命中行**):契约中正费率行
   `net_daily_yield = daily_funding_rate` 无借币腿,`borrow_rate_source` 仅负费率借币
   候选且成本腿产出费率时才有值。故**仅当该行 `borrow_rate_source` 非 null 时**,在净
   收益列旁展示被扣除的日借币利率 `rows[].borrow_validation.classic_margin.daily_interest_account`
   (账户档);无账户档时回落 `daily_interest_vip0`(VIP0 参考档)并标注为参考。正费率
   行 / 无成本腿行显示占位(—),不展示借币成本子行。
2. `negative_funding_status` 派生文案:保留原始结构字段不动。派生**先按契约结构优先级**
   (docs/api/public-market-contract.md「Priority for negative_funding_status」):
   `DISABLED_PERP_ONLY` / `DISABLED_BSTOCK` / `DISABLED_SPOT_ONLY` 为结构禁用状态,保持
   各自的结构文案;**仅 `PRIVATE_BORROW_VALIDATION_REQUIRED`(即 MARGIN_SPOT_CANDIDATE)
   行**才再按 `borrow_validation` 细分:
   - verified=true + pair_listed=true + asset_borrowable=true → "已验证可借"
   - verified=true + pair_listed=false → "杠杆交易对未列出"
   - verified=true + asset_borrowable=false → "资产不可借"
   - verified=false + error=not_probed_this_round → "未探测(限速预算)"
   - 私有通道关闭/失败 → "需私有验证"
   结构禁用行**不得**派生成"需私有验证"。各状态最终中文文案在 design 阶段按
   memory `ui-chinese-first` 定稿;本 task 冻结的是派生逻辑(优先级 + 驱动字段)。
3. 个人账户面板上移:将 private_account 面板从页面底部移动到市场表(费率行情表)上方。
4. 持仓每资产折算 USDT:个人持仓每个资产行新增该资产折算成 USDT 的价值(数量 × 价格)。
   已确认当前 payload 不暴露单资产价格(仅聚合 `total_value_usdt`,后端 `assemble_private_account`
   内部逐资产估值但未逐行吐出),**无法纯前端计算**。本 stage 允许 additive 契约变更:
   后端按交易标的 `price_map` 补逐资产估值/价格字段(如 `balances_*[].value_usdt`,或
   暴露 `price_map`)。「后端算好折算值 vs 传单资产价格前端算」的字段形态在 design 阶段
   界定,须走**契约变更门**(schema + 契约文档 + 测试同步)。无价格资产展示占位(—)。

## Non-Goals

- 除第 4 项逐资产折算所需的 **additive 契约字段**外,不修改公开 snapshot 契约语义;
  第 4 项 additive 变更须走契约变更门,只加字段、不改既有字段/枚举语义。
- 不新增/改动 order、borrow、repay、transfer、websocket 等任何交易或写行为。
- 不改动净收益算法、成本腿链、排序语义(sort_basis)。
- 不改动私有通道开关、鉴权、TTL 等后端读取逻辑。
- 不改部署基础设施。

## Acceptance Criteria

- 净收益行**仅在 `borrow_rate_source` 非 null(成本腿命中)时**展示日借币利率数值;
  正费率行 / 无成本腿行 / 缺失数据展示占位(—),不白屏。
- `negative_funding_status` 派生先按契约结构优先级;仅 `PRIVATE_BORROW_VALIDATION_REQUIRED`
  行再按 `borrow_validation` 细分;结构禁用行保持结构文案;结构字段本身不变。
- 个人账户面板渲染在市场表之上;private_channel 关闭/失败时仍优雅降级不白屏。
- 持仓每资产展示折算 USDT 值(经 additive 契约字段);无价格时展示占位,不报错。
- 第 4 项 additive 契约变更过契约变更门:schema + 契约文档 + 后端/前端测试同步全绿。
- 前端 self-check(`frontend/self-check.js`)覆盖上述展示分支并全绿。
- UI 中文优先(见 memory `ui-chinese-first`)。

## Follow-up 溯源

- memory: `followup-borrow-rate-on-row`（第 1 项）
- memory: `followup-negative-funding-status-ui-labels`（第 2 项）
- memory: `followup-private-account-panel-ui`（第 3、4 项）

本地北京时间: 2026-07-06(H_intake REWORK 修订 2026-07-07)
角色链: designer=Codex → implementer=Kimi → review-2=Claude/Fable5
        (Codex 因 designer 身份 ineligible 终审;Fable5 兼 bookkeeper + final reviewer,非 implementer)
下一步任务: stage-design(跳过 direction panel;含第 4 项 additive 契约变更门界定)

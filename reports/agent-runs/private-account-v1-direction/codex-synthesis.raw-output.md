# Codex 合成裁定原文（用户中转，逐字落档）

落档时间：2026-07-05 23:20 CST（Fable5 簿记）
用户批准：同轮消息末尾「批准 DRAFT-3」（2026-07-05）

---

# Codex 合成裁定：private-account-v1 DRAFT-3

披露：我是 round-1 五评审之一，也参与了用户 8 点问答；本次转任方向合成者。

## Verdict

ACCEPT-FREEZE

DRAFT-3 已完整吸收两轮输入：五模型评审的 P1/P2、DRAFT-2 合成裁定、以及用户 8 点反馈。可冻结为「私有账户数据接入 v1」方向基线，等待用户批准后进入 stage design。

## 核验要点

- 成本腿 / net_daily_yield 已明确定位为展示、决策参考、未来开仓规划输入，不是本轮实际开单结算。
- 借币利率来源已闭环：E2 → E2b → crossMarginData + VIP 档位 → VIP0 显式降级。
- 净收益排序已作为 ADR-3 显式修订提案，不是静默推翻 Phase 2。
- 用户要求的综合资产视图已吸收：统一账户余额 + 现货账户余额 + UM 持仓敞口，并写了防重复计算规则。
- 隐私要求已按用户反馈降级为自用工程卫生：只约束进 git 的样本、报告、fixture；运行时页面可真实展示。
- 限速解释已改正：限制的是私有签名探测调用量，不减少页面全市场展示。
- websocket 已记录为后续路线，但本轮仍不解禁 websocket/listenKey/user data stream 开发；需要独立修正轮。

## 用户批准提示

你如果批准 DRAFT-3，批准范围包含：

1. 私有账户数据接入 v1 方向冻结；
2. ADR-3 排序基准修订：从 abs_daily_funding_rate 优先，改为 net_daily_yield 优先 + 降级回退；
3. 综合资产视图纳入本轮方向；
4. 隐私要求按"自用系统工程卫生"执行。

非阻塞提醒：stage design 里要把 E6 /api/v3/account 同时引用 endpoint spec 与 omitZeroBalances changelog，并冻结现货估值 price source。

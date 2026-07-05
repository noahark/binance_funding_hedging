# GPT/Codex 独立评审：private-account-v1-direction DRAFT-1

## 逐节结论

§1 背景与目标：AGREE
目标方向成立，GET-only 账户级数据是 Phase 2 后合理增量；但“账户真实档位利率”必须先由 discovery 证明，不能先承诺。

§2 与冻结基线关系：REWORK
本轮禁止 websocket 是对的；但 §8 写“解禁 listenKey + 只读数据流”与 Phase 2 的“永久禁止 listenKey/user data stream/websocket”冲突，需要改成“未来如需修改永久禁令，必须独立 MILESTONE + 用户显式批准”。

§3 功能范围：REWORK
净收益方向语义正确：负费率 = 做多永续收资金费 + 借币卖出现货，`abs(funding) - borrow_interest` 成立；正费率 = 现货多 + 永续空，`funding` 成立。但 E2 `/sapi/v1/margin/next-hourly-interest-rate` 只在 Margin borrow-repay 文档下明确存在，统一账户适用性未证实，fallback 不能声称“账户真实档位利率”。

§4 契约草案：REWORK
字段方向可接受，但 `private_account` 真实余额/持仓进入什么 API、是否进入 public snapshot、如何禁止日志/样本/测试落真实值，需要写死。否则“真实数值只允许出现在本地页面渲染”与后端 JSON 响应边界不清。

§5 安全与隐私：REWORK
白名单、GET-only、单一 HMAC 出口方向正确；缺少账户级响应的落档脱敏细则。余额、持仓 symbol、positionAmt、walletBalance、unRealizedProfit 等都可能泄露真实仓位，必须规定 capture-time redaction、access log 禁字段、fixture 只能用脱敏/合成。

§6 复杂度与执行方式：AGREE
MILESTONE、并行模式试运行 #2、stage 分支制首跑都合理。Task A/B 需要以 v0.3 contract fixture 冻结后再并行。

§7 开放问题：REWORK
O1-O5 都是正确问题，但 O5 不能留成实现期自由裁量，必须作为冻结前 required fix。

§8 后续方向：REWORK
开仓规划后置合理；websocket 方向措辞必须避开“解禁永久禁令”的默认语义。

## O1-O5 建议答案

O1：改为 `net_daily_yield` 降序，但仅在私有通道可用且成本来源为账户级/已验证时启用；否则保留 Phase 2 的 `abs(daily_funding_rate)` 降序。`null` 末尾，symbol 升序 tie-break。

O2：需要隐私模式，默认隐藏金额/仓位数量，点击后本地显示；报告、样本、日志永远脱敏，不受开关影响。

O3：本轮展示 `/papi/v1/balance` 余额与 `/papi/v1/um/positionRisk` UM 持仓；不做现货余额折算，除非另开估值契约。

O4：按 base asset 去重后全覆盖；建议 TTL 1h、单轮上限可配置，默认 50-80 个资产，429/-1003 退避。若超过预算，暴露 coverage 状态，不能静默假装全覆盖。

O5：当前 fallback 不成立。E2 若未证实适用于统一账户，不能 fallback 成“账户真实利率”；只能降级为 VIP0/reference rate，并将 `net_daily_yield` 标为 null 或 `reference_estimate`，等待用户拍板。

## Findings

P1 - E2/fallback 无法支撑“账户真实借币利率”
`docs/private-account-v1-direction-draft.md §3.1/§7 O5`：`/sapi/v1/margin/next-hourly-interest-rate` 在文档中是 Margin borrow-repay 端点（llms-full.txt:189205；changelog:151129），未证明适用于统一账户 `/papi`。修法：H_intake 必须实测 E2；失败时不得用 VIP0/crossMarginData 冒充账户真实档位，需新增 `borrow_rate_source` / `net_yield_status` 并降级为 null/reference。

P1 - 账户真实数值的 API/日志/落档边界不完整
`§4/§5`：`private_account` 余额/持仓真实值如何从后端到前端、是否进入 public snapshot、如何避免测试 fixture/access log/report 落真实值，没有可执行约束。修法：定义私有本地通道或受保护块；禁止持久化真实数值；所有证据样本 capture-time 脱敏；新增负向测试扫描 raw/report/log 不含金额、仓位数量、账户标识。

P2 - websocket 后续“解禁”措辞冲突永久禁令
`§2/§8`：Phase 2 基线把 listenKey/user data stream/websocket 列为跨阶段 permanent invariant。修法：改成“未来若用户决定修改永久禁令，需独立 MILESTONE 修订”，不要默认称为解禁方向。

P2 - E1 只能做事后校验，不是净收益成本输入
`§3.1`：`/papi/v1/margin/marginInterestHistory` 存在于 Portfolio Margin REST（llms-full.txt:186218），但语义是已发生利息。修法：明确 E1 只用于 reconciliation，不参与开仓前净收益排序。

P2 - “负费率全覆盖”缺预算与覆盖状态
`§3.2/O4`：全覆盖与调用上限/限频会冲突。修法：按资产去重、TTL、批量上限、coverage 字段、超限处理写入契约，不允许静默跳过。

P3 - 契约版本口径需统一
`§4`：写“schema 升 v0.3”，但现行 schema `schema_version` 仍是 `public-market-snapshot/v1`。修法：明确是 contract doc v0.3 但 wire schema_version 是否保持 v1；若改 wire version，前端兼容规则要写清。

## Verdict

REWORK。

必改清单：

1. 修正 E2/fallback：未实测统一账户适用前，不得承诺账户真实利率或净收益排序。
2. 补账户隐私硬约束：API 边界、日志禁字段、样本脱敏、默认隐私模式、负向测试。
3. 修正 websocket 后续方向措辞，避免与永久禁令冲突。
4. 明确 O4 覆盖预算与 coverage 状态。
5. 统一 contract v0.3 与 wire `schema_version` 口径。

模型身份：GPT-5 / Codex
本地北京时间：2026-07-05 21:27:54 CST

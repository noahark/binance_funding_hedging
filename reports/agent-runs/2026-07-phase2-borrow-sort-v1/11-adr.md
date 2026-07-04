# ADR — 2026-07-phase2-borrow-sort-v1

本 stage 的架构/设计决策记录。完整规格与论证见 `10-design.md`；本文件
记录决策点、状态与后果。按 stage-delivery required-file 约定落档。

## ADR-1：单一 HMAC 出口（`private_client.py`）

- **决策**：仓库级 HMAC-SHA256 签名仅经 `private_client.py`；deny-by-default
  `(method, exact-path)` 白名单 = status.json `endpoint_whitelist` 四项；
  GET-only；门控在签名构造**之前** raise；凭据清理审计日志。
- **状态**：ACCEPTED（hard_constraint；交易语义端点永久禁止）。
- **后果**：未来任何私有端点须在此扩展白名单；grep 单测锁定单一出口。

## ADR-2：daily_funding_rate 用 decimal.Decimal（禁 float）

- **决策**：`Decimal(last) × (24/interval)`，`quantize(1E-8)`，负零归一化
  `0.00000000`；缺失/空/非数值 → `null`。
- **状态**：ACCEPTED（decimal-string 纪律）。
- **后果**：前端展示仅 string-shift（parseFloat/Number×100 禁止）。

## ADR-3：rows 由后端按 abs(daily) 降序预排序

- **决策**：后端排序；前端不得重排。全序 = abs(daily) 降序 + null 末尾 +
  symbol 升序 tie-break。
- **状态**：ACCEPTED（耦合面）。
- **后果**：排序确定性与 null 位点在设计期冻结，双端契约。

## ADR-4：borrow_validation 三态 + bounded portfolio

- **决策**：`classic_margin`（市场级，全候选行）+ `portfolio_account`
  （bounded top-N `MARGIN_SPOT_CANDIDATE`+`CRYPTO`，bStock 排除，VIP0 取档）；
  三态语义（disabled / verified-not-listed / verified-listed），并列输出，
  不改 classify。
- **状态**：ACCEPTED，bounded 选样策略见 ADR-5。

## ADR-5：bounded portfolio 选样策略（OPEN）

- **观察**（live）：bounded top-N（abs daily 降序）当前实抓全为高费率小币
  （OGN/MIRA/VANRY/TLM/RE/BEL/AIGENSYN/STG/GUN/HEI），在 Portfolio Margin
  不可借；可借大币（BTC/ETH）费率低不在 bounded 集 → `portfolio_account`
  在当前市场对所有行 null。
- **判定**：实现严格遵循 §3.4（**非实现 bug**；fetch 路径、classic_margin
  均正常）。
- **决策**：DEFERRED。是否调整 bounded 策略（可借性优先 / 扩大 N / 其他）属
  耦合面之外的 design 决策，按红线停手上报 review/用户（R3），不在本 stage
  自行 fix。
- **后续**：留 review-1 / review-2 / 用户决策。

---

本地北京时间: 2026-07-04 23:24 CST
作者: bookkeeper (claude_glm)，决策依据见 10-design.md + 实现报告

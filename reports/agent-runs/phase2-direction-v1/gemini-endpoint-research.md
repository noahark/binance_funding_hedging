# Gemini 端点族考证（用户转达）+ Fable5 原文核验

Provenance: 用户令 Gemini 检索仓库根目录 `llms-full.txt`（Binance 官方 API
文档转储，7.4MB，2026-07-02 抓取）后于 2026-07-04 转达结论；下半部分为
Fable5 对该转储原文的独立核验。用于裁决 GPT 与 GLM 在 round-1 评审中关于
「统一账户（非专业版）端点族」的事实冲突。

## Gemini 结论（转述原文要点）

- `/papi`（Portfolio Margin API）→ 统一账户（Portfolio Margin 账户）专属
  端点，涵盖统一账户下 U 本位合约（um）、杠杆借贷、自动算法订单等；
  另有 `/papi/v2/b402/...` 用于 Binance Connect 支付结算。
- `/sapi` → 综合系统/资金服务端点：经典杠杆账户（`/sapi/v1/margin`，
  全仓/逐仓借还币与账户查询）、钱包资产管理、理财/借贷、母子账户。

## Fable5 对 llms-full.txt 原文的核验（2026-07-04）

1. L48419: 区块标题 `**Portfolio Margin (/papi)**` —— `/papi` 族归属明确。
2. L186278: `GET /papi/v1/margin/maxBorrowable` = 「查询账户最大可借贷额度」
   （Operation ID `marginMaxBorrow`），位于 Portfolio Margin 端点区块内。
3. L186286: `GET /papi/v1/um/apiTradingStatus` 中文描述「**统一账户**UM合约
   交易量化规则指标」，Operation ID `portfolioMarginUm...` ——官方中文文档
   将「统一账户」与 Portfolio Margin 直接等同。
4. L48499-48501: 「**统一账户专业版**新增穿仓借贷偿还记录查询」位于
   `Portfolio Margin Pro` 标题下 ——「专业版」= PM Pro。
5. `/sapi/v1/margin/maxBorrowable` 同样存在（L36814/L37263 等），属经典
   杠杆账户族；两族同名端点并存，语义按账户体系区分。

## 裁决结论

用户账户「统一账户模式（非专业版）」= Portfolio Margin（普通版）→
Phase 2b 账户级验证走 `/papi`（首选 `GET /papi/v1/margin/maxBorrowable`）。

- GPT round-1 观点（/papi 为账户级来源）：**证实**。
- Gemini 考证：**证实**（与原文一致）。
- GLM round-1 P1（「非专业版统一账户走 /sapi、/papi 为专业版专用」）：
  **被官方文档原文否定**——「专业版」对应 PM Pro，普通「统一账户」即 PM，
  `/papi` 正是其端点族。GLM 其余 P2/P3 findings 不受此影响，仍然有效。

残余验证：设计层结论已定，但 H_intake 仍保留一次 controller 持用户 key 的
只读 discovery 实抓（脱敏落档）作为运行时确认（账户可访问性、响应结构），
符合 Hard Gates「raw evidence over model claims」。

本地北京时间: 2026-07-04（Fable5 落档）

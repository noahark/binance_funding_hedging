# Follow-up: borrowability 业务错误（51061 等）应映射为可借数量 0，而非 null

- 来源 stage: `2026-07-ui-filter-balance-metal-v1`（用户验收期间发现）
- 建议 stage-id: `2026-07-borrowability-error-zero-mapping-v1`（bookkeeper 核定）
- 复杂度初判: MEDIUM（跨 backend/frontend/schema/docs/tests，但改动面集中）
- 落档人: claude_glm / zhipu_glm（当前 stage 实现者；本问题独立于该 stage）
- 落档时间: 2026-07-08 15:25:08 CST

## 与当前 stage 的关系（重要）

`2026-07-ui-filter-balance-metal-v1` 已 `stage_accepted_waiting_user`（review-1 Kimi ACCEPT + review-2 Claude ACCEPT，diff 指纹 `2e966904…` 已冻结）。**本问题不得混入该已冻结交付物**，由 bookkeeper 创建独立新 stage 启动。

## 问题陈述

`borrow_validation.portfolio_account.max_borrowable` 当前在两种语义截然不同的情况下都返回 `null`，前端与下游无法区分：

1. **未探测**（borrowability 截断，候选排名 > `max_calls`）：`error="borrowability_not_probed"`，`max_borrowable=null` —— 这是真正的「未知」。
2. **已探测但 Binance 返回业务错误**（如 51061「可借资产不足/借光」）：`error=null`，`verified=true`，`max_borrowable=null` —— 实际是「确定的 0」，却被当成 null。

用户判断：51061（池子借光）是**确定的业务状态**，应映射为 `max_borrowable="0"`，而非 null / 前端「—」。`null` 应专属于「未探测」。当前混用导致：
- 「已验证可借」badge 误导：SPELLUSDT 顶着绿色「已验证可借」，但 Binance 实际明说「借不出来，明天再试」。
- 丢失错误码本身：`last_error` 留在 PrivateClient 实例上，未进 row，前端拿不到「为什么是 0」。

## 根因

`fetch_max_borrowable`（`backend/services/private_client.py:240-258`）对 Binance 非 2xx 一律 `raise PrivateEndpointError`（`_signed_get:170-174`），`except` 捕获后返回 `None`（`:252-254`）。`snapshot_service.py:188-192` 把 `None` 落成 `{"max_borrowable": None, "borrow_limit": None}`。`assemble_borrow_validation`（`snapshot.py:769-773`）照搬 null，且 `verified=true`（`:761`，判定**不看** `max_borrowable`）。

`_is_rate_limited`（`private_client.py:177-187`）只把 `code=-1003` 当限速重试；51061 不重试、直接 raise。Binance `/papi/v1/margin/maxBorrowable` 的业务错误（51061 等）被当成「请求失败」处理，丢失「可借=0」的确定语义与错误码。

## 实盘证据

SPELLUSDT（abs 负费率第 1，`daily_funding_rate=-0.04677708`，必在前 50 probed 集）—— 实际签名调用（只读 GET，凭据已脱敏）：

```
请求: GET https://papi.binance.com/papi/v1/margin/maxBorrowable?asset=SPELL&recvWindow=5000&timestamp=…&signature=<REDACTED>
返回: HTTP 400
{
  "code": 51061,
  "msg": "Due to high borrowing demand, there are currently insufficient loanable assets for SPELL. Please adjust your borrow amount or try again tomorrow."
}
```

快照结果：`verified=true`，`portfolio_account.max_borrowable=null`，`borrow_limit=null`，`source="papi_max_borrowable"`，`error=null` → 前端 badge 绿色「已验证可借」。

链路：`400(code=51061, ≠-1003)` → 不重试 → `raise PrivateEndpointError` → `fetch_max_borrowable` 返回 `None` → `max_borrowable=null` → `verified` 仍 `true`（classic_ref 可用 + 在 probed 集 + 未截断）。

业务洞察：SPELL 日费率 -4.68%（年化 1700%+），套利需求极大 → 可借池子被借光 → Binance 返回 51061。其余高 abs 候选（EPICUSDT 等）`max_borrowable=null`，疑为同类，需在修复 stage 逐资产确认。

## 建议修法（供 bookkeeper/design 评估，非最终方案）

1. **错误分类**：`fetch_max_borrowable` 区分「业务错误（可借=0 类）」与「系统错误（真未知）」。业务错误（51061 可借不足等）返回 `{"max_borrowable": "0", "borrow_limit": <原值或 null>, "error_code": "51061"}`；系统错误（网络/5xx/限速 -1003）仍返回 `None`。
2. **assemble_borrow_validation**：透传 `max_borrowable="0"`，`verified` 语义保持不变（classic_ref 可用 + pair_listed + asset_borrowable）；`portfolio_account` 可新增 `error_code` 字段（additive），区分「借光(0)」「有额度(>0)」「未探测(null)」三态。
3. **前端**：`max_borrowable="0"` 显示明确文案（如「可借: 0（已借完）」），区别于 `null` 的「—/未探测」。可顺带处理用户另一提议——展示可借数量 + ≈USDT 价值（`price_map` 已有 `{asset}USDT` 价格可折算）。
4. **schema/contract/self-check 同步**：`portfolio_account` 加 `error_code`（additive，不破坏现有形状）；self-check 覆盖 51061→0 分支；contract 文档更新三态语义。

### 需 design/product 定的点

- 哪些 Binance code 算「可借=0」类（51061 可借不足；是否还有其他）。需枚举，最好附 raw 样本（`reports/api-samples/<stage>/`）。
- 「账户未开借币权限」类错误（若存在对应 code）是否也映射 0，还是单独状态——product 决策。
- `borrow_limit` 在 51061 时取值（原返回值或 null）。
- 是否同步落地「可借数量 + USDT 价值」展示（用户已表意向，可并入本 stage 或拆分）。

## 影响范围（预估）

- `backend/services/private_client.py`（`fetch_max_borrowable` 错误分类）
- `backend/domain/snapshot.py`（`assemble_borrow_validation` 透传 0 + `error_code`）
- `backend/services/snapshot_service.py`（`portfolio_by_asset` 落值；注意 `:132/:182` 两处 CRYPTO-only 陈旧注释可顺带补正为 `{CRYPTO, METAL}`——见 ui-filter-balance-metal-v1 residual risk #1）
- `schemas/api/public-market/snapshot.schema.json`（`portfolio_account.error_code`，additive）
- `docs/api/public-market-contract.md`（`portfolio_account` 三态语义 + `error_code`）
- `frontend/index.html`（badge / 可借数量展示 / 可能的 ≈USDT 价值）
- `frontend/self-check.js`（51061→0 用例）
- `backend/tests/test_snapshot.py` / `backend/tests/test_private_account_v1.py`（错误分类单测）
- 可能需 raw 样本：`reports/api-samples/<stage>/`（多资产 maxBorrowable 返回，含 51061 与正常值）

## 验收标准建议

- 51061 类业务错误 → `max_borrowable="0"`（非 null），`error_code="51061"`
- 截断未探测 → `max_borrowable=null` + `error="borrowability_not_probed"`（保持不变）
- 系统错误（网络/5xx/限速）→ `max_borrowable=null`（真未知，保持）
- 前端能区分三态：「借光(0)」「有额度(>0)」「未探测(—)」
- SPELLUSDT 实盘：badge 不再误导为「已验证可借」，改为反映「可借 0 / 已借完」
- `pytest backend/tests -q` 全绿 + `node frontend/self-check.js` 全绿
- schema/contract additive，不破坏现有契约

---

本地北京时间: 2026-07-08 15:25:08 CST
下一步模型: bookkeeper（用户指示放下个 stage 修复）
下一步任务: bookkeeper 核定 stage-id + 复杂度，创建 `reports/agent-runs/<stage-id>/00-intake.md`，启动 stage-delivery 流程（design → breakdown → 实现 → review-1 → review-2）。

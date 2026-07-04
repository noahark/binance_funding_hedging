# GPT/Codex Review Round 1 - Phase 2 Direction Draft

Review object: `docs/phase2-direction-draft.md` DRAFT-1.2, commit `f1297a5`
Review mode: read-only; no code edits; no private/signed API calls
Reviewer model identity: Codex / GPT-5
Review timestamp: 2026-07-04 19:17:52 CST

## Scope

This review evaluates Phase 2 direction: private read-only data channel
for margin borrowability and borrow rates, plus frontend funding-rate sorting.

Background consulted:

- `AGENTS.md`
- `docs/api/public-market-contract.md`
- `docs/parallel-development-mode.md`
- `backend/domain/classify.py`
- `backend/services/snapshot_service.py`
- Binance public documentation for margin and portfolio-margin endpoint semantics.

No private API key, signed request, account endpoint, order, borrow, repay,
transfer, listenKey, websocket, or user-data stream was used.

## 1. Safety Redline Assessment

Conclusion: REWORK.

The direction is right, but under the accepted premise that the user keeps a
full-permission API key with IP whitelist, the proposed baseline is not strong
enough. Endpoint whitelist inside `private_client` is necessary but not
sufficient.

Required additions:

- Private channel must be disabled by default and enabled only by explicit config
  plus env credentials.
- The low-level signed HTTP transport must enforce a method/base_url/path
  allowlist before signing.
- Any non-GET request must fail before signature creation.
- Any endpoint outside the allowlist must fail before signature creation.
- Tests must prove POST/PUT/DELETE, unknown paths, unknown bases, and direct
  bypass attempts are rejected.
- Add a static or test-level guard that product code does not call
  `requests`/`httpx` directly for Binance private endpoints outside the private
  adapter.
- Add redacted audit logs for every signed request attempt: timestamp, logical
  endpoint id, method, sanitized path, status/error, latency, and request id if
  available. Never log key, secret, signature, full query string, or headers.

Residual risk remains: IP whitelist reduces stolen-key abuse from elsewhere,
but it does not constrain buggy or compromised code running on the whitelisted
machine. Therefore the code whitelist is the primary defense and must be tested
as a hard gate.

## 2. Unified Account vs Classic SAPI Signal

Conclusion: classic `/sapi` endpoints cannot directly validate unified-account
borrowability.

`GET /sapi/v1/margin/allPairs` is a classic cross-margin trading-pair list. It
can say whether a pair exists in the classic margin universe, but it does not
prove the operator's unified-account borrowability.

For the user's unified account, account-level borrowability must be verified via
Portfolio Margin endpoints, especially `GET /papi/v1/margin/maxBorrowable`,
which returns the account's current max borrowable amount and borrow limit.

Therefore Phase 2a should not upgrade `PRIVATE_BORROW_VALIDATION_REQUIRED` to an
account-verified state based only on `/sapi/v1/margin/allPairs`. The safer split
is:

- `classic_margin_reference`: evidence from `/sapi` allPairs/allAssets/
  crossMarginData.
- `portfolio_account_borrow`: evidence from `/papi/v1/margin/maxBorrowable`.
- Only the PAPI account-level result can produce a user-account borrowability
  conclusion.

## 3. Borrow Rate Endpoint Selection

Conclusion: the draft needs an explicit endpoint matrix before implementation.

Recommended candidates:

- `GET /sapi/v1/margin/allPairs`: classic cross-margin pair reference.
- `GET /sapi/v1/margin/allAssets`: classic margin asset reference, including
  `isBorrowable` and `isMortgageable`.
- `GET /sapi/v1/margin/crossMarginData`: classic cross-margin fee/rate data,
  including `dailyInterest`, `yearlyInterest`, `borrowLimit`, and
  `marginablePairs`.
- `GET /papi/v1/margin/maxBorrowable`: unified-account actual max borrowable
  amount for an asset. This is the key account-level validation source.
- `GET /papi/v1/margin/marginInterestHistory`: historical borrow/loan interest
  records only; not a current expected-rate source.
- Optional verification candidate:
  `GET /sapi/v1/margin/available-inventory`, as a system inventory reference if
  needed later.

The implementation stage should freeze, for each endpoint: source family,
security type, signed/public status, input parameters, raw JSON paths,
frontend-safe fields, sensitive fields, redaction rule, TTL, and failure mode.

## 4. Contract Evolution

Conclusion: add an independent field block now; do not immediately split
`negative_funding_status`.

Changing `negative_funding_status` now has a high blast radius because it is an
execution-support status already consumed by schema, UI, tests, and bStock
priority logic. The lower-cost path is to keep the existing enum and add an
independent block such as `borrow_validation` or `margin_private`.

Recommended shape:

```json
{
  "borrow_validation": {
    "verified": false,
    "classic_margin": {
      "pair_listed": null,
      "asset_borrowable": null,
      "daily_interest": null,
      "source": "sapi_reference"
    },
    "portfolio_margin": {
      "max_borrowable": null,
      "borrow_limit": null,
      "source": "papi_max_borrowable"
    },
    "checked_at": null,
    "error": null
  }
}
```

Later, after PAPI account-level evidence is stable, the backend can derive a new
negative-funding execution status from this field.

## 5. Funding-Rate Sorting

Conclusion: numeric comparator is acceptable; display-layer string discipline
must remain unchanged.

The frontend may compare funding rates using numeric values or a decimal-string
comparator. The UI must still render from the canonical string field and must
not mutate the backend decimal strings for display.

Default sort recommendation: signed funding rate descending, not absolute-value
descending.

Reason: absolute-value descending would surface large negative funding rows
first even when negative-funding execution is still gated by borrowability.
Signed descending prioritizes immediately useful positive-funding candidates.
Add an explicit "absolute value" sort option later if useful.

## 6. Parallel Mode vs Serial Split

Conclusion: do not use the full parallel frontend/backend mode for the whole
Phase 2 private-channel work yet.

The private channel and contract semantics are not frozen, and the distinction
between classic margin reference and unified-account borrowability affects the
frontend meaning. This is too much coupling for the first parallel-mode trial.

Recommended split:

1. Backend discovery/contract stage first, serial:
   freeze security guards, endpoint matrix, redacted samples, schema contract,
   and offline fixtures.
2. Frontend funding-rate sorting can run as a separate lightweight UI stage now,
   because it does not depend on private fields.
3. Frontend private-validation display should wait until the backend contract is
   frozen.

If parallel mode is used anyway, Task B should be limited to funding-rate
sorting only and must not integrate `margin_private`/`borrow_validation` fields.

## 7. Other Issues

- The phrase "Phase 2a market-level data is mostly account-type independent" is
  misleading. Classic `/sapi` data may be useful reference data, but unified
  account execution depends on `/papi` evidence.
- bStock negative funding must remain hard-disabled unless there is a later
  explicit product decision and evidence that borrowing or equivalent shorting is
  possible. Classic margin/collateral signals must not automatically override
  `DISABLED_BSTOCK`.
- Raw private samples need a stricter sensitivity taxonomy. Some apparently
  market-like responses may still be user-specific when signed and must be
  reviewed before being committed.

## Findings

- P1 - Unified-account borrowability source is wrong - Classic `/sapi` margin
  lists cannot verify unified-account borrowability. Fix by treating SAPI as
  `classic_margin_reference` only and using `/papi/v1/margin/maxBorrowable` for
  account-level borrowability.
- P1 - Full-permission API key defense is under-specified - A `private_client`
  whitelist alone does not prevent direct signed request bypass. Fix with
  deny-by-default signed transport, method/base/path allowlist, default-off
  private channel, direct HTTP guard, redacted audit logs, and negative tests.
- P2 - `negative_funding_status` should not be split yet - Immediate enum
  expansion increases schema/UI/test churn before account-level evidence is
  settled. Fix by adding independent `borrow_validation`/`margin_private` fields
  and deriving statuses later.
- P2 - Borrow-rate endpoint semantics are mixed - `crossMarginData` is current
  fee/rate reference, while PAPI interest history is historical ledger data.
  Fix by freezing an endpoint matrix with purpose and source semantics.
- P2 - Full parallel-mode trial is too risky here - Private key handling and
  contract semantics are not frozen. Fix by serializing backend discovery first
  and letting frontend sorting run as a separate lightweight stage.
- P3 - Default absolute-value funding sort is not ideal - It promotes negative
  rows before negative execution is validated. Fix by defaulting to signed
  funding-rate descending and adding absolute-value sort as explicit option.

## Verdict

REWORK.

Required fixes:

1. Rewrite the Phase 2a/2b split so SAPI is only classic-reference evidence and
   PAPI is required for unified-account borrowability.
2. Strengthen full-permission key safety requirements into concrete technical
   hard gates and tests.
3. Replace immediate `negative_funding_status` enum split with an independent
   borrow-validation contract block.
4. Freeze a signed endpoint matrix before implementation.
5. Split frontend funding-rate sorting from private-validation display, or limit
   any parallel-mode trial to the sorting-only frontend task.

## Revision Prompt For Fable5

```text
请修订 docs/phase2-direction-draft.md 到 DRAFT-1.3。保留用户决定：统一账户模式、保留全权限 API key、IP 白名单已绑定。必须吸收以下 required fixes：

1. 改写 Phase 2a/2b：/sapi classic margin 只能作为 classic_margin_reference，不能证明统一账户可借；统一账户账户级可借结论必须来自 /papi/v1/margin/maxBorrowable 或等价 PAPI 证据。
2. 安全红线补强：默认私有通道关闭；signed transport method/base_url/path deny-by-default；禁止绕过 private_client 的直连 HTTP；负向测试覆盖白名单外路径、POST/PUT/DELETE、直接 requests/httpx；脱敏审计日志入验收。
3. 契约演进改为新增 borrow_validation/margin_private 独立块，暂不细化 negative_funding_status；现有枚举保持不变，直到 PAPI 账户级验证闭环。
4. 端点矩阵写清：allPairs/allAssets/crossMarginData/maxBorrowable/marginInterestHistory/available-inventory 的用途、语义、敏感级别、脱敏要求和验证样本。
5. 流程改为：后端私有 discovery/contract 先串行冻结；前端资金费率排序可独立轻量阶段；私有验证展示等契约冻结后再做。
6. 默认排序改为签名资金费率降序，绝对值排序作为显式选项。

修订后输出变更摘要，并把仍需用户拍板的问题单独列出。
```

## Sources

- Binance Get All Cross Margin Pairs:
  `https://developers.binance.com/docs/zh-CN/margin_trading/market-data/Get-All-Cross-Margin-Pairs`
- Binance Get All Margin Assets:
  `https://developers.binance.com/docs/margin_trading/market-data/Get-All-Margin-Assets`
- Binance Query Cross Margin Fee Data:
  `https://developers.binance.com/docs/margin_trading/account/Query-Cross-Margin-Fee-Data`
- Binance Portfolio Margin Max Borrow:
  `https://developers.binance.com/docs/derivatives/portfolio-margin/account/Margin-Max-Borrow`
- Binance Portfolio Margin Borrow/Loan Interest History:
  `https://developers.binance.com/docs/derivatives/portfolio-margin/account/Get-Margin-BorrowLoan-Interest-History`

## Footer

Reviewer model identity: Codex / GPT-5
Local Beijing time: 2026-07-04 19:17:52 CST
Suggested next model/task: Fable5 to revise `docs/phase2-direction-draft.md` to DRAFT-1.3.

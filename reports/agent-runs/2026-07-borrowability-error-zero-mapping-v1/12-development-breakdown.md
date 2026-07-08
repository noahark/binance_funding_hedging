# 12-development-breakdown：2026-07-borrowability-error-zero-mapping-v1

单 serial owner（`claude_glm`）。一个原子 diff，可被 bookkeeper 冻结直送 review-1。
顺序建议：backend → schema/contract → frontend → fixtures/tests → 全量校验。

## S1. Backend 错误分类（ADR-1/2）

- [ ] `private_client.py`：`PrivateEndpointError.__init__` 加 `code=None`；`_signed_get`
      raise 前解析 body 业务码填入 `code`。
- [ ] `private_client.py`：加 `BORROW_ZERO_BUSINESS_CODES = frozenset({51061})`；
      `fetch_max_borrowable` except 三分支（0 映射 / 未知业务码 distinct 日志 / 系统错误）；
      成功路径补 `error_code=None`。
- verify: 新增单测 51061→"0"、未知码→None+`max_borrowable_business_error:`、系统错误→None+`max_borrowable_failed:`、成功→error_code None。

## S2. Backend 透传 + 折算（ADR-3/4）

- [ ] `snapshot.py`：加 `_max_borrowable_value_usdt`（8dp `_quantize_rate`，null/缺价→None）。
- [ ] `snapshot.py`：`assemble_borrow_validation` 加 `price_map=None` kwarg；三个 portfolio_account
      出口补 `error_code` + `max_borrowable_value_usdt`（verified 分支透传/折算，另两分支 None）。
- [ ] `snapshot_service.py`：portfolio_by_asset None 兜底补 `error_code`；调用点传 `price_map=price_map`。
- verify: assemble_borrow_validation 单测覆盖三分支 additive 字段；折算单测。

## S3. 注释补正（residual R1，机械）

- [ ] `snapshot_service.py:132` `+ CRYPTO,` → `+ {CRYPTO, METAL},`；`:182`
      `asset_tag != CRYPTO` → `asset_tag not in {CRYPTO, METAL}`。仅注释。
- verify: `rg -n "CRYPTO-only\|!= CRYPTO" backend/services/snapshot_service.py` 无残留旧措辞。

## S4. Schema + 契约

- [ ] `snapshot.schema.json` `portfolio_account`：+`error_code`、+`max_borrowable_value_usdt`
      （`["string","null"]`），二者加入 `required`。
- [ ] `docs/api/public-market-contract.md`：三态语义表 + 字段说明 + verified 不变说明。
- verify: schema 合法；所有仓库快照 fixture 形状同步（S6）后 self-check/backend schema 校验通过。

## S5. Frontend

- [ ] `index.html` `badgeForNegativeFundingStatus`：verified success 分支前插入
      `max_borrowable==='0'` → 「可借 0(已借完)」warn badge。
- [ ] `index.html` borrowSubline：`portfolio_account.max_borrowable != null` 时追加「可借」子行，
      ≈USDT 用 `formatUsdt2(max_borrowable_value_usdt)`，"0" 加「已借完」标。
- verify: self-check 三态断言（借光/有额度/未探测）。

## S6. Fixtures + tests + 全量校验

- [ ] `rg -n "portfolio_account" frontend backend/tests` 逐个补 additive 形状（default 快照补 null；
      新增/独立场景放借光 "0"/"51061"/"0.00000000" 与有额度样本）。
- [ ] `self-check.js` 断言（S5）。
- [ ] backend 单测（S1/S2）。保持既有 borrowability_not_probed/truncated/bStock 测试不放松。
- [ ] 运行：`python3 -m pytest backend/tests -q`、`node frontend/self-check.js`、`git diff --check`。
- verify: 全绿；additive；`rg -n "portfolio_account"` 无遗漏形状。

## 完成契约

留工作区未提交（含 `20-implementation.md`），不动 `status.json`/`70-handoff.md`。bookkeeper
冻结 diff、算 fingerprint、`scripts/validate-stage.py ... --phase pre-review`、派 review-1。

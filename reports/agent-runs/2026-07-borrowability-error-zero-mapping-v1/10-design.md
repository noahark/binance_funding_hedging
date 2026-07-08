# 10-design：2026-07-borrowability-error-zero-mapping-v1

单 serial diff 的详细设计。实现须与 `11-adr.md` 一致。所有新增字段 additive，不破坏现有契约形状。

## 0. 根因回顾（实盘 SPELLUSDT）

`GET /papi/v1/margin/maxBorrowable?asset=SPELL` → HTTP 400 `{"code":51061,"msg":"...insufficient loanable assets..."}`
→ `_signed_get` 丢弃 body、`raise PrivateEndpointError(reason="HTTP 400")` → `fetch_max_borrowable`
`except` 返回 `None` → `portfolio_account.max_borrowable=null`，而 `verified` 仍 `true`（classic_ref
可用 + 在 probed 集 + 未截断）→ 前端绿色「已验证可借」。修复目标：51061 → `max_borrowable="0"` +
`error_code="51061"`，badge 反映「借光」。

## 1. Backend

### 1.1 `backend/services/private_client.py`

**(a) `PrivateEndpointError` 携带业务 code（ADR-1）**

`__init__` 增加可选 `code`：

```python
def __init__(self, logical_path, status, reason, code=None):
    self.logical_path = logical_path
    self.status = status
    self.reason = reason
    self.code = code            # Binance business code parsed from JSON body, or None
    super().__init__(f"{logical_path} failed: status={status} reason={reason}")
```

`_signed_get` 的 raise 处（当前 `:173-174`）在 raise 前解析 body 的业务码：

```python
if status is None or status >= 400:
    biz_code = None
    if body:
        try:
            biz_code = json.loads(body).get("code")
        except (ValueError, TypeError):
            biz_code = None
    raise PrivateEndpointError(path, status, err or "unknown", code=biz_code)
```

- 不改白名单/签名/`_is_rate_limited`/重试。`_is_rate_limited` 的 -1003 判定仍在此 raise 之前。
- body 为空（网络层无响应，status None）→ `code=None`。

**(b) `fetch_max_borrowable` 业务错误分类（ADR-2）**

模块级常量（放在 fetcher 附近或类常量区）：

```python
# Binance business codes that mean "confirmed 0 borrowable" (pool exhausted).
# Extend only with codes confirmed by a raw sample; see reports/follow-ups.
BORROW_ZERO_BUSINESS_CODES = frozenset({51061})
```

`except` 分支：

```python
except PrivateEndpointError as exc:
    if exc.code in BORROW_ZERO_BUSINESS_CODES:
        # confirmed 0: pool exhausted, not "unknown"
        return {"max_borrowable": "0", "borrow_limit": None,
                "error_code": str(exc.code)}
    if exc.code is not None:
        # unknown business error: distinct log path so a real sample surfaces
        self.last_error = f"max_borrowable_business_error:{asset}:{exc.code}"
        return None
    self.last_error = f"max_borrowable_failed:{asset}:{exc.reason}"
    return None
```

成功路径 `return` 补 `error_code=None`（形状统一）：

```python
return {"max_borrowable": data.get("amount"),
        "borrow_limit": data.get("borrowLimit"),
        "error_code": None}
```

> 注：`BORROW_ZERO_BUSINESS_CODES` 用 int 成员（Binance code 为整数）；`exc.code` 也是 int。
> 返回的 `error_code` 转 `str`（契约/前端按字符串消费，与其它 code 字段一致）。

### 1.2 `backend/domain/snapshot.py`

**(a) ≈USDT 折算 helper（ADR-4）**

**口径对齐（重要）**：balance 的 `value_usdt` 后端存 **8dp**（`_quantize_rate(value)`，
`quantize(Decimal("1E-8"))`），2dp 的 `≈ … USDT` 由**前端** `formatUsdt2`（`:824`，
2dp ROUND_HALF_UP）渲染。本折算**必须同口径**：后端存 8dp 串，前端用 `formatUsdt2` 展示。
**不要**在后端直接 2dp，否则两处折算口径漂移。

新增（紧邻 `_usdt_value_optional`，复用其 stable-asset/缺价/坏值处理风格，但**无 warnings 参数**——
借币折算缺价不算账户告警；末尾用 `_quantize_rate` 与 balance 完全一致）：

```python
def _max_borrowable_value_usdt(asset, max_borrowable, price_map):
    """≈USDT value of max_borrowable (additive, 8dp string like balance
    value_usdt). None when amount is null/blank or price unavailable;
    "0.00000000" when amount is a valid zero. Frontend renders 2dp via formatUsdt2."""
    if max_borrowable is None or max_borrowable == "":
        return None
    try:
        amt = Decimal(str(max_borrowable))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if asset in _STABLE_USD_ASSETS:
        value = amt
    else:
        price = price_map.get(f"{asset}USDT")
        if price is None or price == "":
            return None
        try:
            value = amt * Decimal(str(price))
        except (InvalidOperation, ValueError, TypeError):
            return None
    return _quantize_rate(value)   # 8dp string, identical to balance value_usdt
```

> `_quantize_rate` 已存在（`:277`）。不引入新 rounding 常量。前端负责 2dp（`formatUsdt2`）。

**(b) `assemble_borrow_validation` 透传 error_code + 折算**

签名新增 `price_map`（默认 `None` 便于既有测试单参调用；实际由 snapshot_service 传入）：

```python
def assemble_borrow_validation(row, classic_ref, portfolio_by_asset, checked_at,
                               error, *, daily_interest_account=None,
                               borrowability_truncated=False, price_map=None):
```

三个 `portfolio_account` 出口（`:713` classic_ref None、`:742` truncated、`:759` verified）
统一补齐 additive 字段：

- classic_ref None 分支、truncated 分支：`"error_code": None, "max_borrowable_value_usdt": None`。
- verified 分支（`:768-772`）：
  ```python
  "portfolio_account": {
      "max_borrowable": portfolio.get("max_borrowable"),
      "borrow_limit": portfolio.get("borrow_limit"),
      "error_code": portfolio.get("error_code"),
      "max_borrowable_value_usdt": _max_borrowable_value_usdt(
          base, portfolio.get("max_borrowable"), price_map or {}),
      "source": "papi_max_borrowable",
  },
  ```

> `base = row.get("base_asset","")` 已在函数内取到（`:710`）。折算按 base 资产取 `{base}USDT` 价。

### 1.3 `backend/services/snapshot_service.py`

**(a) portfolio_by_asset 落 error_code（None 兜底也补字段）** `:184-192`：

```python
res = self._private.fetch_max_borrowable(asset)
portfolio_by_asset[asset] = res or {
    "max_borrowable": None, "borrow_limit": None, "error_code": None,
}
```

**(b) 调用点传 price_map** `:210-218`：给 `assemble_borrow_validation(...)` 增加
`price_map=price_map`。注意 `price_map` 在 classic_ref None 分支被设为 `{}`（`:157`），
verified 折算天然拿不到价 → 折算 None，安全。

**(c) 注释补正（residual R1，机械）**：
- `:132` `# ... MARGIN_SPOT_CANDIDATE + CRYPTO,` → `+ {CRYPTO, METAL},`
- `:182` `# bStock rows are excluded upstream (asset_tag != CRYPTO);` →
  `(asset_tag not in {CRYPTO, METAL});`
  仅注释；行为已由有测试覆盖的 `select_borrow_candidates` 驱动，不改逻辑。

## 2. Schema 与契约文档

### 2.1 `schemas/api/public-market/snapshot.schema.json`

`portfolio_account`（`:365-378`）`properties` 增加两字段，**并加入 `required`**（后端三个出口
都稳定输出这两个字段，故 required 保证契约一致）：

```jsonc
"error_code": { "type": ["string", "null"] },
"max_borrowable_value_usdt": { "type": ["string", "null"] }
```

`required` 从 `["max_borrowable","borrow_limit","source"]` 改为
`["max_borrowable","borrow_limit","error_code","max_borrowable_value_usdt","source"]`。

> 若担心 fixture/其它样本未同步会 schema 校验失败：实现须同步更新所有仓库内快照 fixture 的
> `portfolio_account` 形状（见 §4）。

### 2.2 `docs/api/public-market-contract.md`

在 `borrow_validation` / `portfolio_account` 段补三态语义表（同 ADR-3 表），并说明：
- `max_borrowable="0"` + `error_code="51061"` = 已探测确定借光；
- `null` + `borrow_validation.error="borrowability_not_probed"` = 未探测；
- 系统/未知业务错误 → `null`（`error_code=null`），未知业务码在后端 `last_error` 以
  `max_borrowable_business_error:<asset>:<code>` 记录以便发现样本；
- `max_borrowable_value_usdt` = 后端用 `{asset}USDT` price_map 折算的 ≈USDT，缺价/未探测为 null；
- `verified` 语义**不变**（不看 max_borrowable）。

## 3. Frontend `frontend/index.html`

### 3.1 badge：借光态（`badgeForNegativeFundingStatus` :920-931）

在 `verified===true` 且 `pair_listed && asset_borrowable` 的 success 分支**之前**插入借光判定：

```js
const pa = bv.portfolio_account || {};
if (cm.pair_listed === true && cm.asset_borrowable === true) {
  if (pa.max_borrowable === '0') {
    return `<span class="badge warn" title="PRIVATE_BORROW_VALIDATION_REQUIRED · code ${escapeHtml(pa.error_code||'')}">可借 0(已借完)</span>`;
  }
  return `<span class="badge success" ...>已验证可借</span>`;
}
```

- 用 `warn`（非 danger、非 success）样式：不是「资产不可借」的结构性禁止，而是「暂时借光，明天再试」。
- 其余分支（pair_listed false / asset_borrowable false / 未探测）不变。

### 3.2 可借数量 + ≈USDT（表格 net-yield 列 borrowSubline，:1144-1156）

在现有「日借币」子行之后追加「可借」子行——**仅当** `borrow_rate_source != null`（已在借币候选语境）
且 `portfolio_account.max_borrowable != null` 时展示：

```js
const pa = row.borrow_validation && row.borrow_validation.portfolio_account;
if (pa && pa.max_borrowable != null) {
  const usdt2 = formatUsdt2(pa.max_borrowable_value_usdt);   // 8dp -> 2dp, or null
  const val = usdt2 != null ? ` (≈ ${usdt2} USDT)` : '';
  const zeroTag = pa.max_borrowable === '0' ? ' <span class="badge compact warn">已借完</span>' : '';
  borrowSubline += `<br/><span class="muted small">可借: ${escapeHtml(pa.max_borrowable)}${val}${zeroTag}</span>`;
}
```

- ≈USDT 用 `formatUsdt2(pa.max_borrowable_value_usdt)`（8dp→2dp，与 balance 一致；null→不展示 ≈ 段）。
- `max_borrowable==="0"` → 「可借: 0 (≈ 0.00 USDT) [已借完]」。
- `null`（未探测/系统错误）→ **不展示可借子行**（保持现状，不误导）。
- 隐私遮蔽：可借数量属公开市场侧（非私有账户余额），沿用现有 row 展示，不走 maskAmount。

### 3.3 self-check `frontend/self-check.js`

新增/更新断言：
- `max_borrowable="0"` + `error_code="51061"` → badge 文案含「可借 0(已借完)」、非 success class；
- 借光行 net-yield 子行含「可借: 0」与「已借完」；
- 有额度行（`max_borrowable=">0"`）→ badge「已验证可借」、子行含「可借: <值> (≈ … USDT)」；
- 未探测行（`max_borrowable=null`）→ 无可借子行，badge 保持「有利率·可借性未探测」；
- 保持既有默认基线行数不被破坏（如需借光/有额度样本，用独立/deep-copy 场景，勿改默认 6 行语义）。

## 4. Fixtures 与 tests

### 4.1 backend/tests

- `backend/tests/test_private_account_v1.py` 或 `test_snapshot.py`（就近，勿重写无关用例）：
  - **51061→0**：mock `_signed_get`/urlopen 返回 400 `{"code":51061}` → `fetch_max_borrowable`
    返回 `{"max_borrowable":"0","borrow_limit":None,"error_code":"51061"}`；
  - **未知业务码**：400 `{"code":99999}` → 返回 `None` 且 `last_error` 以
    `max_borrowable_business_error:` 开头；
  - **系统错误**：5xx 或网络异常（无 code）→ `None` 且 `last_error` 以 `max_borrowable_failed:` 开头；
  - **成功**：正常 amount → `error_code=None`；
  - **折算** `_max_borrowable_value_usdt`（8dp 串）：`"0"`→`"0.00000000"`；有价 `"10"`×price →
    8dp `_quantize_rate` 值；缺价→None；null/""→None；stable(USDT)→amt 的 8dp；
  - **assemble_borrow_validation**：verified 分支 portfolio 带 `error_code`/折算透传正确；
    truncated / classic_ref None 分支 additive 字段为 None。
- 不放松既有 borrowability_not_probed / truncated 测试。

### 4.2 快照 fixtures（schema required 变更连带）

因 §2.1 把两字段加入 `required`，**所有含 `portfolio_account` 的仓库内快照 fixture 与硬形状断言必须同步**。
实现前先 grep 定位：`rg -n "portfolio_account" frontend backend/tests`，逐个补
`"error_code": null, "max_borrowable_value_usdt": null`（或对应借光样本 `"0"/"51061"/"0.00000000"`）。
保持各 fixture 的 summary counts 准确。

全仓波及清单（2026-07-09 bookkeeper 核对）：
- `backend/tests/fixtures/private-account-v1-design.json`（含 portfolio_account → 补形状）。
- **`backend/tests/test_phase2_borrow_sort.py:230`（严格集合断言，scope amendment 加入允许列表）**：
  `set(bv["portfolio_account"]) == {"max_borrowable","borrow_limit","source"}` →
  `== {"max_borrowable","borrow_limit","error_code","max_borrowable_value_usdt","source"}`。走 offline
  classic_ref None 分支（两新字段 None），实现 §1.2b 后即通过。`:222` 顶层 `set(bv)` 5 键**不变**（勿动）。
- `frontend/fixture/public-market-snapshot.json`：**不含** portfolio_account/borrow_validation 明细 → 无需改。
- `docs/phase2-direction-draft.md:123`：历史方向草案里的旧 3 字段示意，**非规范契约、out-of-scope、勿动**；
  规范三态只更新 `docs/api/public-market-contract.md`。

## 5. 验收标准（review 对齐 follow-up）

- 51061 类业务错误 → `max_borrowable="0"`，`error_code="51061"`；
- 截断未探测 → `max_borrowable=null` + `error="borrowability_not_probed"`（不变）；
- 未知业务码/系统错误 → `max_borrowable=null`，`error_code=null`，未知业务码进 distinct `last_error`；
- 前端三态可区分：借光(0) / 有额度(>0) / 未探测(—)；借光 badge 非绿色「已验证可借」；
- SPELLUSDT 语义：badge 反映「可借 0(已借完)」；
- `max_borrowable_value_usdt` 后端折算正确（8dp 串；借光 "0.00000000"，缺价 null；前端 formatUsdt2 显 "0.00"）；
- `python3 -m pytest backend/tests -q` 全绿 + `node frontend/self-check.js` 全绿；
- schema/contract additive（+2 字段），所有 fixture 形状同步，`git diff --check` clean；
- R1 两处注释补正为 `{CRYPTO, METAL}`。

## 6. 硬约束

- 不改私有签名/白名单/下单/借币/还币/划转逻辑；本 stage 仅**读**路径的错误分类与展示。
- 不臆测枚举业务码：`BORROW_ZERO_BUSINESS_CODES` 仅含 51061；未知码走 distinct 日志。
- 折算不得引入 float：Decimal + ROUND_HALF_UP，与既有 value_usdt 口径一致。
- 权限类错误、第四态：out-of-scope，不实现。
- additive only：不改 `max_borrowable`/`borrow_limit`/`source`/`verified` 现有形状与语义（除
  51061 由 null→"0" 的 bug 修正）。

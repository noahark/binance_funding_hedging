# 20-implementation — 2026-07-borrowability-error-zero-mapping-v1

| field | value |
|---|---|
| implementer | `claude_glm` / `zhipu_glm`（glm-5.2） |
| role | implementation author only |
| branch | `stage/2026-07-borrowability-error-zero-mapping-v1` |
| start HEAD | `a851708`（freeze design + GLM dispatch packet） |
| bookkeeper scope amendments | `2f31408`（SCOPE-001：allowlist `test_phase2_borrow_sort.py`） · `125e496`（SCOPE-002：ADR-2 收窄按码正负分类 + allowlist `test_private_client.py`） |
| current HEAD | `125e496`（本实现 11 文件改动**未提交**于其上） |
| commit | **NONE** — 按 Hard Rules §0「Do not commit」，留给 bookkeeper |
| 实现依据 | `10-design.md` + `11-adr.md`（含 SCOPE-001/002 收窄口径）+ `reports/follow-ups/2026-07-borrowability-51061-zero-mapping.md`（根因 + 实盘证据） |

## 1. Files changed（11，全部在允许列表内）

```
 backend/domain/snapshot.py                         |  35 ++++++
 backend/services/private_client.py                 |  35 +++++-
 backend/services/snapshot_service.py               |   6 +-
 backend/tests/fixtures/private-account-v1-design.json | 12 +--
 backend/tests/test_phase2_borrow_sort.py           |   5 +-
 backend/tests/test_private_account_v1.py           | 120 ++++++++++++++++
 backend/tests/test_private_client.py               |  34 +++++-
 docs/api/public-market-contract.md                 |  62 +++++++++++
 frontend/index.html                                |  16 +++
 frontend/self-check.js                             |  94 ++++++++++++++++
 schemas/api/public-market/snapshot.schema.json     |   4 +-
 11 files changed, 406 insertions(+), 17 deletions(-)
```

无 untracked、无越界。两个允许文件**未改动**（见 §5）。

## 2. Implementation summary（S1..S6）

### S1 — backend 错误分类 `private_client.py`（ADR-1/2 · design §1.1）
- `PrivateEndpointError.__init__` 增 `code: Optional[int] = None` 字段。
- `_signed_get` raise 前解析 body 的 Binance 业务 `code`（JSON 解析失败/无 body → `None`）注入异常；**未动**白名单/签名/`_is_rate_limited`/重试。
- 模块常量 `BORROW_ZERO_BUSINESS_CODES = frozenset({51061})`（仅一根因样本确认的码，不臆测）。
- `fetch_max_borrowable` except **三分支，分界 = 码的正负号**（ADR-2 收窄）：
  1. `exc.code in BORROW_ZERO_BUSINESS_CODES` → `{"max_borrowable":"0","borrow_limit":None,"error_code":str(exc.code)}`（400 body 无 `borrowLimit`）。
  2. `isinstance(exc.code, int) and exc.code > 0`（正数业务码）→ `self.last_error = f"max_borrowable_business_error:{asset}:{exc.code}"`；`return None`。
  3. else（负数系统/鉴权码 -1003/-2014/-2015、无 code 网络/5xx）→ 现状 `max_borrowable_failed:{asset}:{exc.reason}`；`return None`。
- 成功路径 return 补 `"error_code": None`。

### S2 — backend 透传+折算 `snapshot.py` / `snapshot_service.py`（ADR-3/4 · design §1.2/§1.3）
- 新增 `_max_borrowable_value_usdt(asset, max_borrowable, price_map)`：8dp 串，末尾 `_quantize_rate(value)`；null/""/坏值/缺价 → `None`；stable(USDT/USDC) → amt；口径与 balance `value_usdt` 完全一致，但**不发 warning**（借币估值缺口不是账户告警）。
- `assemble_borrow_validation` 增 `price_map=None` kwarg；三个 `portfolio_account` 出口（classic_ref None / truncated / verified）统一补 `error_code` + `max_borrowable_value_usdt`：verified 分支透传 `portfolio.get("error_code")` 并折算；另两分支均为 `None`。
- `snapshot_service.py`：`portfolio_by_asset` 的 `res or {...}` 兜底补 `"error_code": None`；`assemble_borrow_validation(...)` 调用增 `price_map=price_map`。

### S3 — 注释补正 `snapshot_service.py`（residual R1）
`:132` `+ CRYPTO,` → `+ {CRYPTO, METAL},`；`:182` `asset_tag != CRYPTO` → `asset_tag not in {CRYPTO, METAL}`。**仅注释**，逻辑不变。

### S4 — schema + 契约（design §2）
- `snapshot.schema.json`：`portfolio_account.required` 加 `error_code` / `max_borrowable_value_usdt`（均 `{"type":["string","null"]}`）；`schema_version` 保持 `public-market-snapshot/v1`。
- `docs/api/public-market-contract.md`：追加「Borrowability Zero-Mapping Amendment (v0.6)」段——三态语义表（借光 0 / 有额度 / 未探测 / 系统错误）+ 字段说明 + verified 语义不变说明 + 未知业务码 `max_borrowable_business_error:` discovery log 说明 + 回归红线。

### S5 — frontend（design §3）
- `badgeForNegativeFundingStatus`：在 verified 绿色 success badge **之前**插入 `portfolio_account.max_borrowable==='0'` → `warn`「可借 0(已借完)」（title 带 `error_code`）。前端不再把借光误显示为绿色「已验证可借」。
- borrowSubline：`max_borrowable != null` 时追加「可借」子行，≈USDT 用 `formatUsdt2(max_borrowable_value_usdt)`（null → 不展示 ≈ 段），`"0"` 加 compact「已借完」标；`null` → 不展示可借子行。
- `self-check.js`：新增断言 #41「借币三态（51061 借光/有额度/未探测）」——deep-copy 独立场景，不破坏默认基线行数语义。

### S6 — fixtures + tests + 全量校验（design §4）
- `private-account-v1-design.json`：6 行 portfolio_account 形状同步为 5 键。
- `test_phase2_borrow_sort.py:230`：5 字段严格集合断言 + classic_ref None 分支两新字段为 None；`:222` 顶层 `set(bv)` **未动**。
- `test_private_client.py`：成功路径 `:216/:225/:262` 机械追加 `, "error_code": None`；`:238`（-2015→`max_borrowable_failed`）**金标准原样未动**；新增 3 用例（51061→"0" / 未知正数码 59999→None+distinct log / 系统 5xx→None+`max_borrowable_failed:`）。
- `test_private_account_v1.py`：import `_max_borrowable_value_usdt`；新增折算 9 向量 + assemble 三分支（classic_ref None / truncated / verified×3：51061 zero-mapping / quota+折算 / 缺价 null）共 14 用例。

## 3. 三点显式说明

### 3.1 51061 → **确定**的 `max_borrowable="0"`
51061「可贷资产不足」是 HTTP 400 body `{code,msg}`、**无 `borrowLimit` 字段**——即「池子借光、已确认 0」，不是「未知」。修正前被 `_signed_get` 当成普通失败映射为 `null`，前端于是显示绿色「已验证可借」，误导。修正后：命中 `BORROW_ZERO_BUSINESS_CODES` → `max_borrowable="0"` + `error_code="51061"`，前端 badge 转 `warn`「可借 0(已借完)」。`BORROW_ZERO_BUSINESS_CODES` **仅含 51061**（唯一经实盘样本确认的码），不臆测枚举。

### 3.2 未知**正数**业务码 → distinct discovery log
按 ADR-2 收窄，业务/系统边界 = Binance code 的**符号**，而非「是否有 code」：
- **正数**码（5xxxx，含 51061）= 业务错误；
- **负数**码（-1xxx/-2xxx，如 -1003/-2014/-2015）= 系统/鉴权失败 → 归 `max_borrowable_failed`（既有约定，`test_private_client.py:238` 金标准）。

因此分支 2 = `isinstance(exc.code, int) and exc.code > 0` 且不在零集合 → `None` + `max_borrowable_business_error:<asset>:<code>`。这条 distinct log（与 `max_borrowable_failed` 区分）让真实正数业务码样本日后能在 last_error / 审计里浮现，再由 follow-up 决策是否加入零集合——**不臆测**。

### 3.3 折算口径 — **全程无 float**
- 后端：`_max_borrowable_value_usdt` 全程 `Decimal`，末尾 `_quantize_rate(value)`（8dp，负零归一 `"0.00000000"`），与 balance `value_usdt` 同源同口径。
- 前端：可借子行的 ≈USDT 仅用 `formatUsdt2(max_borrowable_value_usdt)`，该函数为**纯 `BigInt` + `parseInt` + 字符串切片**实现 ROUND_HALF_UP（2dp 显示），无 `Number()`/`parseFloat()` 参与折算或金额比较。
- 审计确认 `frontend/index.html` 的 `Number(`/`parseFloat(` 5 处命中均为**预先存在**的千分位格式化(817/820/846)、费率正负号样式(846)、um 方向展示(1091)或注释(1030/1031)，**本次改动未新增任何 float 折算/比较路径**。

## 4. Tests

```
$ python3 -m pytest backend/tests -q
........................................................................ [ 37%]
........................................................................ [ 75%]
..............................................                           [100%]
190 passed in 4.59s
```

```
$ node frontend/self-check.js
... (全部 PASS，含) ...
[PASS] 借币三态（51061 借光/有额度/未探测）
[PASS] 余额卡片三行折算值与隐私遮蔽
全部自检通过
```

```
$ git diff --check
(empty, exit 0 — 无空白错误)
```

### 审计 grep 结果
- `BORROW_ZERO_BUSINESS_CODES`：仅 `private_client.py:94`(def) + `:267`(use)，共 2 处，全在该文件。
- `max_borrowable_business_error`：`private_client.py:276`(last_error) + `test_private_client.py:279/283`(注释+断言)。
- `error_code`：`private_client.py`(256/257/271/284)、`snapshot.py`(753/784/804)、`snapshot_service.py:192`、`snapshot.schema.json`(368/382)、`index.html:928`、`self-check.js`(899/901/904/919/931/942/956)、`contract.md`(624/635/642/644/651/656/667)、fixture×6 — 分布合理。
- `max_borrowable_value_usdt`：`snapshot.py`(489 def/754/785/805)、`schema`(368/383)、`index.html:1167`、`self-check.js`(919/931/942)、`contract.md:637`、`test_private_account_v1.py`(import + 断言)、fixture×6。
- `parseFloat(|Number(` in `frontend/index.html`：5 处（817/820/846/1030/1091）均预先存在，无新增；`formatUsdt2` 折算入口无 float（见 §3.3）。
- `portfolio_account` in `frontend backend/tests`：40 处，分布在 `self-check.js`/`test_phase2_borrow_sort.py`/`index.html`/`test_private_account_v1.py`/fixture —— **无形状遗漏**。

## 5. 偏离允许列表 / 未改动说明

- **`backend/tests/test_snapshot.py`**（在允许列表）：检查后**未改**。该文件**无** `portfolio_account` 严格集合断言；offline 全快照 portfolio_account 形状已由 `test_phase2_borrow_sort.py:230`（5 字段断言）覆盖，新字段对 `test_snapshot.py` 用例为 additive optional，全量 190 用例 PASS。
- **`frontend/fixture/public-market-snapshot.json`**（在允许列表）：按 design §5 **不含** `portfolio_account` 明细 → **无需**改形状（未改）。
- **`docs/phase2-direction-draft.md`**：历史方向草案，非规范契约，按 design §5 **out-of-scope**（未动）。
- **两次 SCOPE 扩展**（`2f31408` SCOPE-001、`125e496` SCOPE-002）：由 **bookkeeper** 提交，非本实现者改动；本实现严格按 SCOPE 收窄后的口径（ADR-2 按码正负分类）落地。

无任何静默扩面、无 blocker。

## 6. Residual risk

- **`BORROW_ZERO_BUSINESS_CODES` 仅 51061**。其余正数业务码（如 51099）当前走 `max_borrowable_business_error:` distinct log + `return None`（即被当作「未知」处理，前端显示「未探测」）。这是**设计意图**（不臆测枚举）：待真实正数业务码样本在 last_error / 审计中浮现，由后续 follow-up 决策是否扩集合。非缺陷。
- **`max_borrowable_value_usdt` 依赖 `price_map`**（与 balance `value_usdt` 同源）。缺价 → `None`，前端不展示 ≈ 段（已由 self-check CUSDT「未探测」+ 缺价场景覆盖）。stable 资产按 1 定价。
- 未触碰任何私有写端点 / 签名 / 白名单 / 下单 / 借还划转 / 密钥管理代码（本 stage 仅读路径错误分类与展示）。`verified` 判定逻辑未改（仍不看 `max_borrowable`）。

---

本地北京时间: 2026-07-09 06:46:41 CST
下一步模型: bookkeeper（anthropic 会话）
下一步任务: 冻结实现 diff，计算 fingerprint，validate-stage --phase pre-review，派 review-1（Kimi）。

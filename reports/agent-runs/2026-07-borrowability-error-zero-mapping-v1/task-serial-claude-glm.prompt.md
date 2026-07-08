# Serial implementation prompt — 2026-07-borrowability-error-zero-mapping-v1

你是 `stage/2026-07-borrowability-error-zero-mapping-v1` 的 serial implementer。

Provider identity: `claude_glm` / `zhipu_glm`。
角色: implementation author only。
Bookkeeper/Designer: Claude Opus 4.8（anthropic）当前会话。
Review-1: fresh Kimi session（`moonshot_kimi`）；Review-2: Codex（`openai`）。

## 0. Hard Rules

先读并遵守：

- `AGENTS.md`
- `agents/developer-discipline.md`
- `reports/agent-runs/2026-07-borrowability-error-zero-mapping-v1/00-intake.md`
- `reports/agent-runs/2026-07-borrowability-error-zero-mapping-v1/11-adr.md`
- `reports/agent-runs/2026-07-borrowability-error-zero-mapping-v1/10-design.md`
- `reports/agent-runs/2026-07-borrowability-error-zero-mapping-v1/12-development-breakdown.md`
- `reports/follow-ups/2026-07-borrowability-51061-zero-mapping.md`（根因 + 实盘证据）

**Do not commit.** bookkeeper 会 inspect diff、rerun tests、commit、算 fingerprint、派 review-1。

不得修改：

- `reports/agent-runs/2026-07-borrowability-error-zero-mapping-v1/status.json`
- `reports/agent-runs/2026-07-borrowability-error-zero-mapping-v1/70-handoff.md`
- review 文件
- 私有签名/白名单/下单/借币/还币/划转/密钥管理代码（本 stage 仅**读**路径的错误分类与展示）

允许改动的 product/report 文件：

- `backend/services/private_client.py`
- `backend/domain/snapshot.py`
- `backend/services/snapshot_service.py`
- `schemas/api/public-market/snapshot.schema.json`
- `docs/api/public-market-contract.md`
- `frontend/index.html`
- `frontend/self-check.js`
- `frontend/fixture/public-market-snapshot.json`
- `backend/tests/test_snapshot.py`
- `backend/tests/test_private_account_v1.py`
- `backend/tests/test_phase2_borrow_sort.py`（**scope amendment 2026-07-09**：`:230` 有
  `set(bv["portfolio_account"]) == {"max_borrowable","borrow_limit","source"}` 严格集合断言，
  schema 形状变更必然波及，须同步为 5 字段。见 §5。）
- `backend/tests/fixtures/*`（凡含 `portfolio_account` 者，形状同步）
- `reports/agent-runs/2026-07-borrowability-error-zero-mapping-v1/20-implementation.md`

超出此列表的文件：停手，在 `20-implementation.md` 写明精确原因，不得静默扩面。

Red lines：
- 不下单、不借/还/划转、不调私有写端点、不打印凭据/环境。
- 不臆测枚举业务码：`BORROW_ZERO_BUSINESS_CODES` 仅含 `51061`。
- 折算不得用 float（`Number()`/`parseFloat()` 不用于金额/折算计算）；用 Decimal + `_quantize_rate`。
- 不改 `verified` 判定逻辑（仍不看 max_borrowable）。

## 1. Goal

一个可被 bookkeeper 冻结直送 review-1 的 serial diff：让 Binance 借币业务错误 51061「池子借光」
从被误当 `null` 修正为**确定的 `max_borrowable="0"` + `error_code="51061"`**，前端 badge 不再
误导为绿色「已验证可借」，并落地「可借数量 + ≈USDT 价值」展示。**严格按 `10-design.md` 实现**——
下面是要点，细节与代码片段以 design 为准。

## 2. Backend

### 2.1 `private_client.py`（ADR-1/2 · design §1.1）
- `PrivateEndpointError.__init__` 加 `code=None` 字段。
- `_signed_get` raise 前解析 body 的业务 `code` 传入（无 JSON body → None）。不改白名单/签名/`_is_rate_limited`/重试。
- 加 `BORROW_ZERO_BUSINESS_CODES = frozenset({51061})`。
- `fetch_max_borrowable` except 三分支：
  1. `exc.code in BORROW_ZERO_BUSINESS_CODES` → `{"max_borrowable":"0","borrow_limit":None,"error_code":str(exc.code)}`
  2. `exc.code is not None` → `self.last_error = f"max_borrowable_business_error:{asset}:{exc.code}"`；return None
  3. else → 现状 `max_borrowable_failed:{asset}:{exc.reason}`；return None
- 成功路径 return 补 `"error_code": None`。

### 2.2 `snapshot.py`（ADR-3/4 · design §1.2）
- 新增 `_max_borrowable_value_usdt(asset, max_borrowable, price_map)`：**8dp 串**，末尾 `_quantize_rate(value)`；
  null/""/坏值/缺价 → None；stable(USDT/USDC) → amt；**口径必须与 balance `value_usdt` 完全一致**。
- `assemble_borrow_validation` 加 `price_map=None` kwarg；三个 `portfolio_account` 出口
  （classic_ref None / truncated / verified）统一补 `error_code` + `max_borrowable_value_usdt`
  （verified 分支透传 `portfolio.get("error_code")` 并折算；另两分支 None）。

### 2.3 `snapshot_service.py`（design §1.3）
- portfolio_by_asset 的 `res or {...}` 兜底补 `"error_code": None`。
- 调用 `assemble_borrow_validation(...)` 增 `price_map=price_map`。
- **注释补正（residual R1）**：`:132` `+ CRYPTO,`→`+ {CRYPTO, METAL},`；`:182`
  `asset_tag != CRYPTO`→`asset_tag not in {CRYPTO, METAL}`。仅注释，不改逻辑。

## 3. Schema + 契约（design §2）
- `snapshot.schema.json` `portfolio_account`：加 `error_code`、`max_borrowable_value_usdt`
  （`{"type":["string","null"]}`），二者加入 `required`。
- `docs/api/public-market-contract.md`：补三态语义表（借光0/有额度/未探测/系统错误）+ 字段说明 +
  「verified 语义不变」说明 + 未知业务码 `max_borrowable_business_error:` 日志说明。

## 4. Frontend（design §3）
- `badgeForNegativeFundingStatus`：verified success 分支**之前**插入 `portfolio_account.max_borrowable==='0'`
  → `warn` 样式「可借 0(已借完)」（title 带 error_code）。其余分支不变。
- borrowSubline（net-yield 列）：`portfolio_account.max_borrowable != null` 时追加「可借」子行，
  ≈USDT 用 `formatUsdt2(max_borrowable_value_usdt)`（null→不展示 ≈ 段），"0" 加「已借完」compact 标；
  `max_borrowable==null` → 不展示可借子行。
- `self-check.js`：三态断言（借光/有额度/未探测），保持默认基线行数语义不被破坏（用独立/deep-copy 场景）。

## 5. Fixtures + tests（design §4）
- `rg -n "portfolio_account" frontend backend/tests` → 逐个补 additive 形状
  （default 快照补 `null`；借光场景 `"0"/"51061"/"0.00000000"`；有额度场景真实值）。summary counts 保持准确。
- **`test_phase2_borrow_sort.py:230`（严格集合断言，必改）**：
  `set(bv["portfolio_account"]) == {"max_borrowable","borrow_limit","source"}` →
  `== {"max_borrowable","borrow_limit","error_code","max_borrowable_value_usdt","source"}`。
  这是 offline 全量快照（走 classic_ref None 分支，两新字段均 None）；实现 §1.2b 后 5 字段断言即通过。
  可选：顺带断言该分支 `error_code is None` 与 `max_borrowable_value_usdt is None`。**`:222` 顶层
  `set(bv)` 5 键不变**（error_code 在 portfolio_account 内，不加到 borrow_validation 顶层）——勿动。
- **`frontend/fixture/public-market-snapshot.json` 不含 `portfolio_account`**（当前无 borrow_validation
  明细）→ 本 fixture **无需**改 portfolio_account 形状；除非你有意新增 borrow_validation 明细（不建议，超范围）。
- **`docs/phase2-direction-draft.md` 是历史方向草案（非规范契约）→ out-of-scope，勿动**其 :123 的旧 3 字段示意；
  规范三态语义只更新 `docs/api/public-market-contract.md`。
- backend 单测（就近 `test_private_account_v1.py`/`test_snapshot.py`，勿重写无关用例）：
  51061→"0"·未知码→None+`max_borrowable_business_error:`·系统错误→None+`max_borrowable_failed:`·
  成功→error_code None·折算 8dp（"0"→"0.00000000"/缺价 None/stable)·assemble 三分支 additive 透传。
- 不放松既有 borrowability_not_probed / truncated / bStock 测试。

## 6. Tests To Run Before Reporting Done

```text
python3 -m pytest backend/tests -q
node frontend/self-check.js
git diff --check
```

审计：
```text
rg -n "BORROW_ZERO_BUSINESS_CODES|max_borrowable_business_error|error_code|max_borrowable_value_usdt" backend frontend schemas docs
rg -n "parseFloat\(|Number\(" frontend/index.html   # 确认不用于新增折算/金额比较
rg -n "portfolio_account" frontend backend/tests    # 确认无 fixture 形状遗漏
```

## 7. Required Report

写 `reports/agent-runs/2026-07-borrowability-error-zero-mapping-v1/20-implementation.md`：
- implementer identity `claude_glm / zhipu_glm`；branch + 起始 HEAD；files changed；
- 按 S1..S6 的实现摘要；51061→0 / 未知码 distinct 日志 / 折算口径 三点显式说明；
- tests 精确 PASS/FAIL 输出 + 审计 grep 结果；
- 任何偏离允许文件的说明；residual risk（若有）。

Footer：
```text
本地北京时间: <date 命令输出>
下一步模型: bookkeeper（anthropic 会话）
下一步任务: 冻结实现 diff，计算 fingerprint，validate-stage --phase pre-review，派 review-1（Kimi）。
```

## 8. Completion Contract

完成后留工作区你的实现改动 + `20-implementation.md` **未提交**。不动 `status.json`/`70-handoff.md`。
bookkeeper 会：inspect `git diff` → rerun tests → commit → 计算标准 Harness fingerprint →
`scripts/validate-stage.py 2026-07-borrowability-error-zero-mapping-v1 --phase pre-review` →
派 review-1（Kimi/moonshot）。若无法安全完成，把 blocker 写进 `20-implementation.md` 并停手。

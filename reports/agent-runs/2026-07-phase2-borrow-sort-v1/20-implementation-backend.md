# Task A Implementation Report — 2026-07-phase2-borrow-sort-v1

Author: claude_glm (backend implementer; dual-hat with controller/bookkeeper,
disclosure per `status.json`).
Scope: `backend/services/private_client.py`（新）+ `backend/domain/snapshot.py` +
`backend/adapters/binance_public.py` + `backend/services/snapshot_service.py` +
`backend/config.py` + `schemas/api/public-market/snapshot.schema.json` +
`docs/api/public-market-contract.md` + `backend/tests/**`.
Date: 2026-07-04.
Stage: `2026-07-phase2-borrow-sort-v1` Task A.
Authority: `10-design.md` §1/§2/§3（H_intake discovery 字段冻结附录 §2.A）。

---

## 1. 改动清单

### 1.1 `backend/services/private_client.py`（新）— 单一 HMAC 出口
仓库唯一 HMAC-SHA256 签名通道。deny-by-default `(method, exact-path)` 白名单
（与 `status.json` `endpoint_whitelist` 四项严格一致），GET-only，门控在签名构造
**之前** raise（`PermissionError`）。出站审计日志仅含
`{logical_endpoint, method, http_status, error, latency_ms}`（无
key/secret/signature/query/headers）。1h TTL 缓存；429/`-1003` 单次退避重试；env
缺失 → `enabled=False` + `last_error` → `verified=false` 降级。raw camelCase →
snake_case 映射（`assetName`/`coin` 键名严格遵守 §2.A）。

### 1.2 `backend/config.py`
新增 `sapi_base_url`/`papi_base_url`、`borrow_check_top_n=10`、
`private_channel_ttl_seconds=3600`、`private_recv_window=10000`。

### 1.3 `backend/domain/snapshot.py`
- `compute_daily_funding_rate(last, interval)`：`Decimal(last) × (24/interval)`，
  `quantize(1E-8)`，负零归一化，缺失/空/非数值 → `None`。禁 float。
- `sort_rows(rows)`：`abs(daily)` DESC、null 末尾、symbol 升序 tie-break，确定性全序。
- `assemble_borrow_validation(...)`：三态块（disabled / verified-not-listed /
  verified-listed），并列输出，不改 classify。
- `build_rows` 加 keyword `funding_interval_by_sym`，row 新增
  `funding_interval_hours` + `daily_funding_rate`。
- `assemble_snapshot` 加 keyword `private_channel_status`，snapshot 新增 `private_channel`。

### 1.4 `backend/adapters/binance_public.py`
`fetch_raw`（live + offline）新增 `funding_interval_by_sym`：live GET
`/fapi/v1/fundingInfo`（公开匿名）按 `symbol → fundingIntervalHours`；offline 返回
`{}`（无 frozen 样本 → 全 8h 默认）。

### 1.5 `backend/services/snapshot_service.py`
`build_snapshot` 装配：fundingInfo → build_rows → sort_rows → private_client
`fetch_classic_reference`（市场级全候选行）+ bounded top-N
`fetch_max_borrowable`（`MARGIN_SPOT_CANDIDATE`+`CRYPTO`，bStock 排除）→
每行 `borrow_validation` → `assemble_snapshot(private_channel_status)`。
`__init__` 持有 `PrivateClient`；**offline 模式强制 private disabled（不读 env、不触网）**。

### 1.6 `schemas/api/public-market/snapshot.schema.json`（v0.2）
root 新增 `private_channel`（enum enabled/disabled，optional）；row 新增
`funding_interval_hours`（enum [1,4,8]）、`daily_funding_rate`（decimal_string|null）、
`borrow_validation`（`$ref #/$defs/borrow_validation`），均 optional（向后兼容 v0.1
frozen fixture）。`$defs/borrow_validation` 定义三态可空结构。

### 1.7 `docs/api/public-market-contract.md`（v0.2 amendment）
Status 升 v0.2；末尾追加 "Phase 2 Amendment (v0.2)"：新公开字段、rows 有序性、
三态语义、bounded portfolio 规则、raw→snake_case 映射、回归红线；引用 H_intake
discovery 证据路径 + 10-design §2.A。

### 1.8 测试
- `backend/tests/test_private_client.py`（新，A1）：16 项安全门负向单测。
- `backend/tests/test_phase2_borrow_sort.py`（新，A4）：daily-rate 向量 + 排序全序 +
  三态语义 + 三态 schema + offline 完整 schema + 降级 + 默认 8h + v0.1 向后兼容。

---

## 2. 测试结果

`python3 -m pytest backend/tests/ -v` → **95 passed**（既有 54 + A1 16 + A4 25），
零回归。原始可重放输出见同目录 `60-test-output.txt`。

daily-rate 6 向量（10-design §3.3）全 PASS，含负零归一化（`-0.00000000` →
`0.00000000`）与缺失→`None`。

---

## 3. Live smoke（受控，仅摘要，无额度/key 落档）

`SnapshotService(Config(offline=False)).build_snapshot()` + jsonschema 校验：
`private_channel=enabled`；648 行全部 `verified=true`（classic_ref 成功）；358
`pair_listed=true` / 290 `pair_listed=false`（三态分布正常）；schema VALID（live）；
rows 非空前缀 abs-daily 单调 DESC。

### 3.1 上报：`portfolio_filled=0`（设计层发现，非实现 bug）

诊断确认 **fetch 路径完全正确**：`fetch_max_borrowable("BTC")` 直接返回非 None
（`max_borrowable`+`borrow_limit` 两键齐全），`last_error=None`。

根因 = 设计 §3.4 bounded 策略 + 市场现实：
- bounded 集 = abs(daily) DESC 前 10 个 `MARGIN_SPOT_CANDIDATE`+`CRYPTO`，实抓为
  OGN/MIRA/VANRY/TLM/RE/BEL/AIGENSYN/STG/GUN/HEI（高费率小币）；
- 这些高费率小币在 Portfolio Margin **不可借**（papi 拒绝 → 降级 None）；
- 可借的大币（BTC/ETH）费率低，排序靠后，**不在 bounded 集** → 不做账户级探测。

后果：`portfolio_account` 在当前市场对所有行均为 null（bounded 内不可借、bounded
外未检查）。`borrow_validation.classic_margin` 仍正常工作（市场级，全候选行）。

**这是设计 §3.4 bounded 选样策略的直接结果，不是实现缺陷。** 是否调整 bounded
策略（如改为"可借性优先"或扩大 N）属耦合面之外的 design 决策，按 PROMPT BODY
红线**停手不自行调整，上报 controller/用户/review 决策**（R3）。实现严格按 §3.4
完成，schema/降级/三态均正确。

---

## 4. 自查表（硬边界对照 10-design §3.1 + task-a PROMPT BODY）

| # | 检查项 | 状态 |
|---|---|---|
| 1 | 仅改允许文件（private_client 新 + snapshot/binance_public/snapshot_service/config + schema + contract + tests + 本 stage 报告） | ✅ |
| 2 | `classify.py` / `normalize.py` / `frontend/**` 零触碰（git 核查通过） | ✅ |
| 3 | 枚举与优先级零改动；route_class/negative_funding_status 不受 borrow_validation 影响 | ✅ |
| 4 | 单一 HMAC 出口（grep 单测：hmac/hashlib/signature 仅 private_client.py） | ✅ |
| 5 | deny-by-default `(method, exact-path)` 白名单 = status.json 四项；GET-only；门控先于签名 | ✅ |
| 6 | key/secret 任何片段不进代码/日志/报告/fixture（审计日志凭据清理单测） | ✅ |
| 7 | daily-rate Decimal 运算禁 float；6 向量 + 负零归一化 + null PASS | ✅ |
| 8 | rows 有序性：abs daily DESC + null 末尾 + symbol 升序 tie-break（确定性全序） | ✅ |
| 9 | borrow_validation 三态语义 + bounded portfolio（top-N MARGIN_SPOT_CANDIDATE+CRYPTO，bStock 排除） | ✅ |
| 10 | schema v0.2 对 live/offline 双模式产物 jsonschema PASS；v0.1 frozen fixture 向后兼容 | ✅ |
| 11 | offline 模式 private disabled（不触网、不读 env）；`request_log()=={}` 不破坏 | ✅ |
| 12 | 耦合面三项（interval/日费率/有序性）按 §1 实现，无自行变更 | ✅ |
| 13 | 既有 54 测试零回归；新增 41 测试全绿（95 passed） | ✅ |
| 14 | 未 commit、未碰 status.json；改动只留工作树 | ✅ |

---

## 5. 文件列表

修改：`backend/config.py`、`backend/domain/snapshot.py`、
`backend/adapters/binance_public.py`、`backend/services/snapshot_service.py`、
`schemas/api/public-market/snapshot.schema.json`、`docs/api/public-market-contract.md`。
新增：`backend/services/private_client.py`、`backend/tests/test_private_client.py`、
`backend/tests/test_phase2_borrow_sort.py`、`60-test-output.txt`、本报告。

---

## 6. 等待事项

- 等待 bookkeeper 统一提交（H_A）与指纹绑定。
- 等待嵌入预审 round 1（fresh Kimi 只读会话复审 Task A）。
- **设计层待决**：bounded portfolio 选样策略（§3.1 上报），留 review/用户决策。

---
本地北京时间: 2026-07-04 22:08 CST
下一步模型: kimi（嵌入预审 Task A，fresh 只读）‖ claude_glm（嵌入预审 Task B，fresh 只读）
下一步任务: bookkeeper 生成 embedded-review-a-round1.diff.patch + 调度双嵌入预审

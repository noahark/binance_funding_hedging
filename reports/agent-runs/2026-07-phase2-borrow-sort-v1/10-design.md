# Design & Breakdown — 2026-07-phase2-borrow-sort-v1

Author: Fable5（designer/breakdown；review-2 默认避让）。
一切与 `docs/phase2-direction-draft.md`（FROZEN @ 11dec26）冲突处以基线为准。

## 1. 契约冻结（v0.1 → v0.2 amendment，Task A 落文档，B 端依此并行）

### 1.1 row 新增公开字段（Task B 依赖，设计期冻结）

```json
{
  "funding_interval_hours": 8,
  "daily_funding_rate": "0.00030000"
}
```

- `funding_interval_hours`: int ∈ {1,4,8}。来源 `GET /fapi/v1/fundingInfo`
  （公开匿名）：在响应中列出的 symbol 用其 `fundingIntervalHours`；未列出
  的按 Binance 默认 **8**。禁止硬编码符号清单。
- `daily_funding_rate`: string（8 位小数，与 lastFundingRate 同格式）。
  计算 = `Decimal(lastFundingRate) × (24 / interval)`（×3/×6/×24，整数倍
  无舍入），**Python decimal.Decimal 运算，禁 float**；输出定点字符串
  （`quantize(Decimal('1E-8'))`，无科学计数法）。lastFundingRate 缺失/空
  → 字段为 `null`。

### 1.2 rows 有序性约定（Task B 依赖，设计期冻结）

快照 `rows` 按 `abs(Decimal(daily_funding_rate))` **降序**返回；
`daily_funding_rate=null` 的行排末尾；同值 tie-break 按 `symbol` 升序
（确定性排序，测试可断言）。前端**不得重排**（筛选只隐藏不重排）。

### 1.3 row 新增私有块（本阶段前端不消费）

```json
{
  "borrow_validation": {
    "verified": false,
    "classic_margin": {
      "pair_listed": null,
      "asset_borrowable": null,
      "daily_interest_vip0": null,
      "source": "sapi_reference"
    },
    "portfolio_account": {
      "max_borrowable": null,
      "borrow_limit": null,
      "source": "papi_max_borrowable"
    },
    "checked_at": null,
    "error": null
  }
}
```

三态语义（契约文档必须原文记载）：
- 私有通道未启用/请求失败：`verified:false`，数据字段全 null，`error` 注明；
- 已验证、经典清单不在列：`verified:true, pair_listed:false`，数据字段 null；
- 已验证、在列：`verified:true, pair_listed:true` + 数据字段。
`checked_at` = 请求成功时刻（非数据生效时刻）。字符串数值字段一律 string。
`portfolio_account` 仅对 bounded 候选集填充（见 §3.4），其余行 null。

### 1.4 枚举与既有逻辑零改动（回归红线）

`negative_funding_status`/`route_class`/`asset_tag` 枚举值、优先级序列、
`classify.py`、`normalize.py` 逻辑**零改动**；既有 54 项后端测试全部保持
通过。快照 schema（`snapshot.schema.json`）按 §1.1-1.3 扩展，其余不动。

## 2. 端点矩阵（H_intake discovery 实抓后冻结字段列）

| # | endpoint | 签名 | 用途 | 敏感级 | TTL | 失败模式 |
|---|---|---|---|---|---|---|
| E1 | `GET /fapi/v1/fundingInfo` | 否(公开) | 结算间隔 | 无 | 1h | 缺省全 8h + warning |
| E2 | `GET /sapi/v1/margin/allPairs` | 是 | classic 在列参考 | 市场级 | 1h | verified:false+error |
| E3 | `GET /sapi/v1/margin/allAssets` | 是 | isBorrowable 参考 | 市场级 | 1h | 同上 |
| E4 | `GET /sapi/v1/margin/crossMarginData` | 是 | VIP0 日利率 | 市场级(表) | 1h | 同上 |
| E5 | `GET /papi/v1/margin/maxBorrowable` | 是 | 账户级可借(bounded) | **账户级** | 1h | 同上；H_intake 失败=BLOCKED |
| — | `GET /sapi/v1/margin/interestRateHistory` | 是 | E4 fallback（仅 E4 不可用时启用并补白名单） | 市场级 | — | — |

签名白名单 = {(GET,E2),(GET,E3),(GET,E4),(GET,E5)}（E1 公开不走签名通道；
fallback 端点仅在 discovery 证实 E4 不可用后经簿记补入）。raw JSON path、
字段名、单位由 discovery 实抓样本冻结进本文件的附录（controller 在
H_intake 补写，属 intake 范畴）。E5 响应为账户级：落档前按脱敏规则处理。

## 3. Task A 实现要点（backend，claude_glm）

### 3.1 允许/禁止文件

允许：`backend/services/private_client.py`（新）、
`backend/services/snapshot_service.py`、`backend/domain/snapshot.py`、
`backend/config.py`、`backend/tests/**`、
`schemas/api/public-market/snapshot.schema.json`、
`docs/api/public-market-contract.md`、本 stage 目录报告文件。
禁止：`backend/domain/classify.py`、`backend/domain/normalize.py`、
`frontend/**`、`reports/api-samples/**`（只读）、其他 stage 目录。

### 3.2 private_client 安全门（全部为 review 必查项 + 负向单测）

1. 全仓库**唯一 HMAC 出口**；grep 单测：`hmac|HMACSHA256|signature`
   命中仅 `private_client.py`（测试文件的断言字符串除外，用精确规则）。
2. 白名单 = `(method, exact-path)` 常量元组，deny-by-default；白名单外
   path、非 GET method，在**签名构造前** raise；仅实现 GET 代码路径。
3. 直连守卫单测：产品代码除 private_client 外不得对
   `binance.com` 私有域发起带签名参数的 HTTP。
4. 出站审计日志：`(logical_endpoint_id, method, sanitized_path,
   timestamp, http_status/error, latency_ms)`；禁 key/secret/signature/
   完整 query/headers。
5. 降级：env 缺失 → `private_channel:disabled`，snapshot 正常产出
   （borrow_validation 全 `verified:false`）；该分支有测试。
6. 限频：签名请求独立 1h TTL 缓存；429/-1003 指数退避且不阻塞公开快照；
   timestamp/recvWindow 按 Binance 规范处理。

### 3.3 fundingInfo + 排序

- fundingInfo 公开 GET 走既有公开客户端路径，1h TTL。
- daily rate 计算与排序按 §1.1/§1.2；实现处单元测试向量（必测）：

| lastFundingRate | interval | daily_funding_rate |
|---|---|---|
| `"0.00010000"` | 8 | `"0.00030000"` |
| `"0.00010000"` | 4 | `"0.00060000"` |
| `"-0.00005000"` | 4 | `"-0.00030000"` |
| `"0.00002000"` | 1 | `"0.00048000"` |
| `"-0.00000000"` | 8 | `"0.00000000"`（负零归一化） |
| 缺失/`""` | any | `null`（排末尾） |

- 排序测试：构造混合 interval fixture，断言全序 + tie-break + null 末尾。

### 3.4 borrow_validation 装配

- E2/E3/E4 市场级数据对全部 MARGIN_SPOT_CANDIDATE 行装配 classic_margin；
  `daily_interest_vip0` 取 crossMarginData **VIP0 档**（取档规则契约注明）。
- E5 账户级仅对 **bounded 候选集**调用：abs(日费率) 降序前
  `Config.borrow_check_top_n`（默认 10）个 `MARGIN_SPOT_CANDIDATE` 且
  `asset_tag=CRYPTO` 的 baseAsset（bStock 保持 DISABLED_BSTOCK 拦截，
  不做账户级借币探测）；其余行 portfolio_account 全 null。
- 装配层不改 classify：borrow_validation 是**并列输出块**，不影响
  route_class/negative_funding_status 取值。

### 3.5 测试与证据

pytest 全绿（既有 54 + 新增）；`60-test-output.txt` 含可重放原始输出；
discovery 样本 + evidence-index（sha256）；schema v0.2 对 live/offline
双模式产物 jsonschema 校验 PASS。offline 模式：frozen raw 目录无
fundingInfo/私有样本 → 全 8h 默认 + `verified:false`，测试断言不崩溃。

## 4. Task B 实现要点（frontend，kimi）

### 4.1 允许/禁止文件

允许：`frontend/index.html`、`frontend/self-check.js`、本 stage 目录
报告文件。禁止：`backend/**`、`schemas/**`、`docs/api/**`、
`reports/api-samples/**`、其他 stage 目录。

### 4.2 改动清单

1. **拆列**：删除「资金费率/结算时间」合并列，恢复独立「资金费率」列与
   「结算时间」列（沿用既有 formatFundingRate / formatBeijing* 输出，
   两函数逻辑不动，可复用调用）。
2. **新列「日费率」**：渲染 `daily_funding_rate`（string-shift 百分比
   格式化，复用 formatFundingRate；null → `—`）。
3. **结算间隔标注**：`funding_interval_hours` 以列头注或行内徽标展示
   （`8h/4h/1h`），形态自定，原则=排名键可见。
4. **零排序逻辑**：无排序按钮/比较器/排序状态；按 payload 顺序渲染；
   既有筛选只隐藏不重排；60s 自动刷新照常。
5. **不消费** `borrow_validation` 任何字段；不引入新依赖；单文件红线不变；
   中文口径沿用（枚举「英文(中文)」三列不变，其余纯中文）。
6. 契约校验（validateContract）同步接受新字段；新字段缺失时优雅降级
   （旧后端联调不白屏，日费率列显示 `—`）。

### 4.3 设计期 fixture（B 端并行开发/自测用，与 §1.1-1.2 一致）

```json
{"rows":[
 {"symbol":"AUSDT","futures":{"last_funding_rate":"0.00010000"},
  "funding_interval_hours":4,"daily_funding_rate":"0.00060000"},
 {"symbol":"BUSDT","futures":{"last_funding_rate":"0.00015000"},
  "funding_interval_hours":8,"daily_funding_rate":"0.00045000"},
 {"symbol":"CUSDT","futures":{"last_funding_rate":"-0.00005000"},
  "funding_interval_hours":4,"daily_funding_rate":"-0.00030000"},
 {"symbol":"DUSDT","futures":{"last_funding_rate":"0.00002000"},
  "funding_interval_hours":8,"daily_funding_rate":null}
]}
```
（有序性示例：A > B > C > D；注意 A 单期费率低于 B 但日费率更高——
self-check 断言渲染顺序 == payload 顺序，且不因单期费率重排。）

### 4.4 self-check 新增断言

拆列存在且合并列消失；日费率列 string-shift 格式正确（含 null→—）；
间隔标注渲染；无排序控件 DOM；渲染顺序 == fixture 顺序；
formatFundingRate/formatBeijing* 函数体未变（哈希或字符串比对）。

## 5. 并行流程（mode doc 映射）

1. **H_intake（bookkeeper=GLM controller）**：提交本 packet 全部文件 +
   discovery 实抓证据 + status.json → base_sha 锚定。E5 失败 → BLOCKED。
2. **并行实现**：Task A（GLM）‖ Task B（Kimi），实现终端不 commit、
   不碰 status.json。
3. **嵌入交叉预审**（checkpoint，非评审门，不计 rework_count，封顶 2 轮）：
   A→fresh Kimi 只读会话；B→fresh GLM 只读会话。每轮落
   `embedded-review-<a|b>-round<N>.diff.patch`（reviewer 所见工作树 diff，
   非 fingerprint）+ dispatch + raw output + fix 说明，bookkeeper 单写。
4. **串行落盘**：bookkeeper 跑测试 → H_A → H_B 提交 → 算指纹 →
   status=review_1（validate-stage checkpoint/pre-review 门）。
5. **正式 review-1**（committed 指纹）：A→fresh Kimi；B→fresh GLM。
6. **review-2**（单轮，Codex，disclosure=direction_synthesis）。
7. `stage_accepted_waiting_user` → Fable5 外部复核 → 用户验收。

任何 R1-R9 红线突破：bookkeeper 记录 breach → 回退串行模式完成本阶段。

本地北京时间: 2026-07-04 21:05 CST（Fable5 预写；§2 附录由 controller
在 H_intake 据实抓补写）

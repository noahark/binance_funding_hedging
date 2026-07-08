# 00-intake：2026-07-borrowability-error-zero-mapping-v1

## 用户原始需求（来源）

承接上个 stage `2026-07-ui-filter-balance-metal-v1` 验收期间发现、归入下个 stage 的
遗留问题（`reports/follow-ups/`）：

1. **51061→0 映射**（`2026-07-borrowability-51061-zero-mapping.md`，主线）
   `borrow_validation.portfolio_account.max_borrowable` 目前把两种语义完全不同的
   情况都返回 `null`：
   - **未探测**（borrowability 截断）：真正的「未知」；
   - **已探测但 Binance 返回业务错误 51061「可借资产不足/借光」**：实际是「确定的 0」，
     却被落成 `null`，且 `verified=true` → 前端顶着绿色「已验证可借」，误导。
   用户裁定：51061 类池子借光是**确定业务状态**，应映射 `max_borrowable="0"`（非 null），
   `null` 专属「未探测」。并顺带落地「可借数量 + ≈USDT 价值」展示。

2. **R1 陈旧注释**（`2026-07-ui-filter-balance-metal-v1-residuals.md`）
   `backend/services/snapshot_service.py:132`、`:182` 两处注释仍写 "CRYPTO-only"，
   而 `select_borrow_candidates` 已扩为 `{CRYPTO, METAL}`。随本 stage 顺手机械补正。

## 初步归类

- complexity: `MEDIUM`
- mode: `serial`（单 owner 串行）
- reason: 跨 backend（private_client 错误分类 + snapshot 透传/折算）/ schema / 契约文档 /
  frontend（三态 badge + 可借数量+USDT）/ tests，改动面集中但跨层契约耦合。
- **不采用独立 task-branch（双 owner）试跑模式**：本 stage **修改 schema 与 API contract**，
  触发 DEC-2026-07-08-002 硬门 **D4**（首轮试跑禁止 schema/contract/共享 fixture 变更，
  否则回落单 owner 串行）。故走标准 `stage-delivery.yaml` 单 owner。

## 用户已确认的裁定（本会话 2026-07-09）

1. **展示范围**：「可借数量 + ≈USDT 价值」展示**并入本 stage**（非拆分）。
2. **权限类错误 out-of-scope**：除 51061（池子借光）外，「账户无借币权限」等错误**暂不处理**
   （目前无 raw 样本、无已知 code）。对**未知业务 code** 走「distinct 日志」路径以便日后
   捕获真实样本，**不臆测枚举**（Simplicity First）。
3. **实现派发**：Claude 仅任 bookkeeper + design（冻结执行文档 + 产出 GLM dispatch packet）；
   **实现派发给 `claude_glm`/`zhipu_glm`**（Claude/GPT 不做开发、不派子 agent）。

## bookkeeper 裁定的设计口径（详见 10-design.md / 11-adr.md）

- **三态语义**（`portfolio_account`）：
  - 「借光(0)」：`max_borrowable="0"`，`error_code="51061"`（已探测、确定为 0）；
  - 「有额度(>0)」：`max_borrowable=">0 字符串"`，`error_code=null`；
  - 「未探测(null)」：`max_borrowable=null`，`borrow_validation.error="borrowability_not_probed"`；
  - 「系统错误(null)」：网络/5xx/限速 -1003 → `max_borrowable=null`（真未知，保持）。
- **`verified` 语义不变**：仍 = classic_ref 可用 + pair_listed + asset_borrowable。SPELLUSDT
  仍 `verified=true`，但 `max_borrowable="0"` + `error_code="51061"`。
- **前端 badge 不再误导**：`verified=true` 且 `max_borrowable="0"` 时 badge 改为「可借 0(已借完)」
  的非 success 样式，而非绿色「已验证可借」。
- **`borrow_limit` 在 51061 下为 `null`**：51061 是 HTTP 400 错误响应，body 只有 `{code,msg}`，
  无 `borrowLimit` 字段可取（非选择题）。
- **≈USDT 折算在后端**：复用 `price_map[{asset}USDT]`（与 balance `value_usdt` 一致的
  「后端算、前端渲染」哲学），新增 additive `max_borrowable_value_usdt`。

## Out-of-scope（本 stage 明确不做）

- R2（METAL 借币候选缺 live sample）：产品事实局限，无代码可改，挂等公开接口出现金属现货腿。
- R3（报告行尾空格）：证据卫生小项，忽略。
- 「账户无借币权限」等非 51061 业务错误的具体映射：无样本，走 distinct 日志发现路径，不实现映射。

## 当前状态

本文件记录需求 intake 与已确认裁定。实现须按 `10-design.md` / `11-adr.md` /
`12-development-breakdown.md` 当前口径执行。

本地北京时间: 2026-07-09 05:45:31 CST
下一步模型: claude_glm（serial implementer）
下一步任务: 按冻结设计实现单 serial diff，产出 20-implementation.md，交 bookkeeper 冻结 → review-1。

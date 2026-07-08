# 11-adr：借币业务错误分类与三态可借语义

Stage: `2026-07-borrowability-error-zero-mapping-v1`
状态: PROPOSED（bookkeeper 冻结，待 review-1/review-2 确认）

## 背景

`fetch_max_borrowable`（`backend/services/private_client.py:240-258`）对 Binance
`/papi/v1/margin/maxBorrowable` 的任何非 2xx 响应一律 `raise PrivateEndpointError`，
`except` 后返回 `None`。`PrivateEndpointError`（`:76-87`）只携带 `status` 与
`reason`（形如 `"HTTP 400"`），**在 raise 前丢弃了 body 里的业务 code**（`_signed_get:154`
读到 body，但 `:173-174` 只用 `err` raise）。

结果：51061「可借资产不足/借光」与真正的系统错误（网络/5xx）产生**同一个 `None`**，
下游无法区分「确定的 0」与「未知」。实盘 SPELLUSDT 因此顶着绿色「已验证可借」，而 Binance
实际返回 51061 明说借不出来。

## 决策

### ADR-1：让业务 code 上浮到 fetcher 层（最小侵入）

给 `PrivateEndpointError` **新增可选字段 `code`**（Binance 业务码，解析自 JSON body 的
`"code"`；无 JSON body 时 `None`）。在 `_signed_get` raise 处解析一次 body、填入 `code`。

- 不改签名/白名单/重试逻辑，不改 `reason`/`status` 现有语义（additive）。
- `_is_rate_limited` 已有的 body 解析保持不变（-1003 仍先于 raise 被重试）。

**拒绝的替代**：在 `fetch_max_borrowable` 内重新发请求或重新解析——无 body 可用，做不到。
在 audit_log 里塞 code——audit_log 是脱敏路径，且非返回通道。

### ADR-2：业务错误分类，仅显式映射 51061

`fetch_max_borrowable` 的 `except PrivateEndpointError` 分三支：

1. `exc.code in BORROW_ZERO_BUSINESS_CODES`（初值 `{51061}`）→ 返回
   `{"max_borrowable": "0", "borrow_limit": None, "error_code": str(exc.code)}`（**确定 0**）。
2. `exc.code is not None`（有业务码但不在零集，如未知借币业务错误）→ **distinct 日志路径**：
   `self.last_error = f"max_borrowable_business_error:{asset}:{exc.code}"`，返回 `None`。
   目的是**日后从 last_error/审计发现真实样本**，而非现在臆测枚举（Simplicity First）。
3. 其余（无业务码：网络/5xx/超时/-1003 重试后仍失败）→ 现状 `max_borrowable_failed`，返回 `None`。

`BORROW_ZERO_BUSINESS_CODES` 是**单点常量集**，未来新增确认的「借光」类码 = 加一个元素，
不改结构。

**拒绝的替代**：把「账户无借币权限」等一并映射 0——无样本、无已知 code，属臆测（用户裁定 out-of-scope）；
新增独立第四态——同样无样本，先不实现结构。

### ADR-3：三态由 `max_borrowable` + `error_code` 表达，`verified` 语义不变

`portfolio_account` 新增 additive 字段 `error_code`（`str|null`）与 `max_borrowable_value_usdt`
（`str|null`，≈USDT 折算）。`verified` 判定**继续只看** classic_ref 可用 + pair_listed +
asset_borrowable，**不看** `max_borrowable`。

三态读法（下游/前端）：
| 语义 | max_borrowable | error_code | borrow_validation.error |
|---|---|---|---|
| 借光(确定 0) | `"0"` | `"51061"` | `null` |
| 有额度 | `">0"` 字符串 | `null` | `null` |
| 未探测(截断) | `null` | `null` | `"borrowability_not_probed"` |
| 系统错误/未配置 | `null` | `null` | 对应系统错误串 或 `null`（verified 分支下） |

**拒绝的替代**：把 51061 也压成 `verified=false`——会丢失「classic 参考确实验证成功」这一
真实信息，且与「未探测」再次混淆。三态用数据字段区分，不动 verified 布尔。

### ADR-4：≈USDT 折算在后端，复用 price_map

新增 `portfolio_account.max_borrowable_value_usdt`：后端用 `price_map[{asset}USDT]` 折算
（与 `assemble_private_account` 的 `value_usdt` 同一「后端算」哲学，前端零计算）。
**口径与 balance value_usdt 完全一致**：后端存 8dp 串（`_quantize_rate`），前端由 `formatUsdt2`
渲染 2dp ROUND_HALF_UP。`max_borrowable` 为 `null`/缺价 → 折算 `null`；为 `"0"` → `"0.00000000"`
（前端显 "0.00"）。

## 影响

- backend：`private_client.py`（异常 +code、fetcher 分类）、`snapshot.py`
  （`assemble_borrow_validation` 透传 error_code + 折算、null 分支补 additive 字段）、
  `snapshot_service.py`（portfolio_by_asset 落 error_code + 传 price_map 折算；:132/:182 注释补正）。
- schema/contract：`portfolio_account` 加 `error_code` + `max_borrowable_value_usdt`（additive）。
- frontend：badge 借光态 + 可借数量/USDT 展示。
- tests：51061→0、未知业务码→null+distinct、系统错误→null、折算、前端三态。

## 契约兼容性

全部 additive：`error_code` / `max_borrowable_value_usdt` 为新增字段，`max_borrowable`
由「51061 时 null」变为「51061 时 '0'」是**语义修正**（bug fix），形状不变。现有消费者若把
`max_borrowable==null` 当「不可借」处理，修复后 51061 反而更准确（"0" 明确）。

# 00-task：2026-07-borrowability-error-zero-mapping-v1

## 任务陈述

修正 Binance 借币业务错误 51061「池子借光」被误映射为 `null` 的问题，使其成为**确定的
`max_borrowable="0"` + `error_code="51061"`**，并让前端不再误导为绿色「已验证可借」，同时落地
「可借数量 + ≈USDT 价值」展示。承接 `reports/follow-ups/2026-07-borrowability-51061-zero-mapping.md`
主线 + `2026-07-ui-filter-balance-metal-v1-residuals.md` 的 residual R1。

## 交付范围（DoD）

1. **后端错误分类**：`PrivateEndpointError` 携带业务 code；`fetch_max_borrowable` 区分
   「借光(0)」/「未知业务码(distinct 日志→null)」/「系统错误(null)」；`BORROW_ZERO_BUSINESS_CODES={51061}`。
2. **三态透传 + 折算**：`portfolio_account` 新增 additive `error_code` + `max_borrowable_value_usdt`
   （8dp，口径同 balance value_usdt）；`verified` 语义不变。
3. **schema + 契约**：`portfolio_account` 加两字段（含 required）；契约文档补三态语义。
4. **前端**：`verified` 且 `max_borrowable="0"` → badge「可借 0(已借完)」（非 success）；net-yield
   列追加「可借: <值> (≈ … USDT)」子行；self-check 三态断言。
5. **residual R1**：`snapshot_service.py:132/:182` 注释补正 `{CRYPTO, METAL}`。
6. **测试**：`pytest backend/tests -q` + `node frontend/self-check.js` + `git diff --check` 全绿；additive。

## 明确不做（out-of-scope）

- 权限类/非 51061 业务错误的具体映射（无样本，走 distinct 日志发现）。
- 独立第四态。
- residual R2（METAL 借币候选 live sample，挂等接口）、R3（行尾空格，忽略）。

## 约束

见 `11-adr.md` / `10-design.md` / `12-development-breakdown.md` 与 status.json.hard_constraints。
核心：仅**读**路径的分类与展示；不改私有写/签名逻辑；不臆测枚举业务码；折算不用 float。

本地北京时间: 2026-07-09 05:45:31 CST
下一步模型: claude_glm（serial implementer）
下一步任务: 按冻结设计实现单 serial diff。

# Fixture 迁移表（golden 基线 → v2 终态）

基线：`63-fixture-baseline-funding.{json,txt}` + `63-fixture-baseline-template.{json,txt}`，
由**现行（v1 链式）validator** 经 `scripts/validate-all-stages.py`（模板仓，记录级模式）
对两仓全部 stage 生成。基线时刻：模板仓 `harness/d3-v2-direct` @ T0 提交后；
funding_hedging `stage/2026-07-red-gate-greening-v1` @ 第 0 步提交后。

验收口径：**无未登记的红、无未登记的判定翻转、无未登记的错误集变化**。
检查点：(B) = T2b（T1 之后、T3 之前）；(F) = 终态复跑（T3/T4 之后，收口）。

## funding_hedging（基线 12 green / 11 red）

### 预期翻转（red → green / green_with_exception）

| stage | 基线红因 | (B) T2b | (F) 终态 | 依据 |
|---|---|---|---|---|
| bookticker-open-columns-v1 | review_1 尾随 + 4×链断 | **仍红**，仅剩 review_1 尾随一条（链断消失、覆盖由 review-2 j=n 担保） | **green_with_exception**（class-1 scope=review_1，T3 写入） | v2 规则 1 j=n + T3 例外 |
| funding-annualized-history-v1 | 5×链断 | **green**（v2 预期战果：review-2 全量指纹==status，零添加转绿） | 同 (B) | v2 规则 1 j=n |
| phase2-borrow-sort-v1 | 2×链断（task 无 sha 字段） | **green**（链式删除；review-2 全量==status） | 同 (B) | v2 规则 1 j=n |
| private-account-v1 | 2×task own-review provider 缺失 | **green**（own-review 担保路径整体删除，嵌套记录退化为簿记；review-2 全量==status） | 同 (B) | v2 删 own-review 路径 |

### 维持红（known_red，错误集可能收窄， verdict 不变）

| stage | 基线红因 | (B)/(F) 预期 | 登记原因 |
|---|---|---|---|
| docs-truth-sync-v1 | review_1 尾随 + review_2.verdict≠ACCEPT | **维持红**（两条均在；verdict 不可降级、class-2 不收） | class-2, pending user decision D-i |
| env-startup-v1 | 缺 diff_fingerprint、缺 30/50 review 文件、review verdict/身份多条 | **维持红**（全部与 D3 无关，原样保留） | legacy 记录不完整（早期手工流程），非本弧范围 |
| harness-flow-optimization-v1 | status 值 ∉ 词表 + 缺指纹/文件/verdict 多条 | **维持红**（原样） | legacy status 值 `accepted_and_merged_to_main`；可选补救=一词迁移（用户另拍，见 T6 台账） |
| local-service-launchd-v1 | review_1 尾随 | **维持红** | class-1 形（可例外转绿）但本弧未授权该 stage 的例外；登记待用户决定是否比照 bookticker |
| public-market-bstock-alias-v1 | 缺 12-development-breakdown.md + 3×链断 | **维持红**，错误集收窄为仅剩缺文件一条 | 缺必需文件（与 D3 无关）；legacy |
| public-market-impl-v1 | 缺 12-development-breakdown.md + 1×链断 | **维持红**，收窄为仅剩缺文件一条 | 同上 |
| public-market-ui-cn-v1 | task B 指纹重算不符 ×2 + 2×链断 | **维持红**，收窄为仅剩 task B 指纹不符 | task 级指纹记录缺陷（validate_tasks，与 D3 覆盖无关）；legacy |

### 维持绿（12 个，不得翻转）

auto-review-pipeline-v1、borrow-cost-coverage-v2、borrowability-error-zero-mapping-v1、
cache-refresh-scheduler-v2、harness-friction-fixes-v1、harness-hardening-followups-v1、
harness-manifest-itbm-sync-v1、history-background-refresh-v1、history-refresh-ahead-v1、
private-account-ui-polish-v1、public-market-contract-v2、ui-filter-balance-metal-v1。

## 模板仓（基线 1 green / 0 red）

- harness-authorized-exception-v1：green（T0 后 status=accepted）→ **维持绿，不得翻转**。

## 注记

- 规则 3（例外盖尾随段）对现存真实数据**零使用**：唯一 review_2 也尾随的 docs-truth-sync
  因 verdict 不可降级依然红。规则 3 的存在价值由 A 系对抗用例证明（未来 review_2 尾随场景）。
- `_template/` 占位 status.json 已排除（两仓）。
- 本表之外的任何红/翻转/错误集变化 = 阻断，回查实现。

# 11-adr：关键决策记录

## ADR-1 next-hourly 分批 batch_size=15
Gate B 实测单次 assets 硬上限 20（21+ → HTTP500 code=2）。选 15 留 25% 余量；66 候选=5 批 ×~100 IP=~500 IP/快照，1h TTL 下可忽略。合并 `next_hourly` dict 后再进 `_select_chain_tier`（不得按批分别选 tier）。

## ADR-2 部分批失败 = 部分合并（不整体降级）
某批失败仅跳过该批、保留已合并；失败批资产 rate=None（不伪造）。修 `private_client.py:319` 静默 except 为 `next_hourly_batch_failed` 诊断。吸收 Opus 4.6 §1。

## ADR-3 禁止 merged_next_hourly 整表缓存
保持逐片 `_cached_get`（各缓存 1h）+ 快照级 60s 缓存防同周期重复。整表缓存会把"部分失败批"的残缺结果钉死 1h，破坏"失败批下张快照 60s 自愈"。**未采纳** Opus 4.6 §3 的整表缓存建议——review-2(codex) 复核确认该决策正确。

## ADR-4 预算解耦
`select_borrow_candidates` 拆 `rate_probe_assets`（全量，喂 next-hourly）/`borrowability_probe_assets`（受 cap，喂 maxBorrowable）/`borrowability_unprobed_assets`；coverage 语义改 borrowability。利率解析只依赖 rate set。

## ADR-5 契约新态 borrowability_not_probed
`assemble_borrow_validation` 的 `truncated`→`borrowability_truncated`；截断保留 `daily_interest_account`、只清 `portfolio_account`、`error="borrowability_not_probed"`。schema `error` 为 `string|null` 非枚举约束 → 无需改 schema（review-2 确认）。契约变更全下游同批：backend↔docs↔frontend↔self-check↔tests。

## ADR-6 serial 单轨模式
非 parallel_development（原子契约变更不可拆层）。不跑 parallel 的 `--phase dispatch-ready` 门；但 **stage-delivery 通用 `--phase pre-review` 门仍适用**（review-2 round-1 指出，bookkeeper 已补齐 checkpoint/fingerprint/status）。

## ADR-7 根因B defer
next-hourly 子集缺失（15 CRYPTO 实盘）需换源（interestRateHistory 按单币）→ 另开 `per-asset-cost-leg-v1`。本阶段诚实留空不伪造。

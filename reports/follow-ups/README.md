# Follow-Up Index

> **【已停止维护 2026-07-31，仅作历史参考】**
> 本目录与本索引是 Harness v1 时期的 follow-up 登记处。活跃契约
> （`AGENTS.md`、`agents/**`、`PROJECT_STATE.md`）与 canonical 文档（`docs/**`）
> 对本文件**零引用**——只有已归档的 stage 证据和本目录内的兄弟文件在指它。
>
> **当前唯一的跨阶段待办登记处是 `PROJECT_STATE.md`。**
>
> 2026-07-31 全量审计结论（逐条核验记录见归档
> `archive/2026-07-harness-v2-trial-hardening-v1` 文件 `22-` §24）：
> - 本目录 11 份内容文件中，**没有已确认的当前生产代码问题**。
>   原 R2 是条件性测试覆盖说明：当前币安金属标的没有现货腿，生产分类为
>   `PERP_ONLY_EXCLUDED`，借币入口正确显示 `—`；只有测试人为构造现货腿时，
>   才验证未来可能出现的 METAL 候选路径。它不是当前开放风险，不写入
>   `PROJECT_STATE.md`；未来真实出现现货腿时再补 live sample 并复核。
> - 其余均为**已解决**（51061 映射；R1 注释漂移已实测修复，
>   `snapshot_service.py` 现用 `{CRYPTO, METAL}`）、**已退役**
>   （auto-review-pipeline，DEC-2026-07-14-002）、**已执行完**（docs-hygiene
>   Batch A1/A2/B，2026-07-12）、或**随 v1 机制一并失效**
>   （`2026-07-harness-known-issues-registry.md` 的 K1–K7 与
>   `2026-07-harness-mechanical-gates.md` 全部建立在 v2 已删除的
>   `validate-stage.py` / `stage-delivery.yaml` / `docs/harness-design.md` 之上）。

The source follow-up files remain authoritative. This index records whether an
item is resolved or remains open without rewriting the original follow-up
evidence.

## 2026-07-borrowability-51061-zero-mapping

Status: resolved.

Resolved by stage `2026-07-borrowability-error-zero-mapping-v1`, merged in
commit `c880a554721321c083136e6899027435a1bf4552`.

Source: `2026-07-borrowability-51061-zero-mapping.md`.

## 2026-07-ui-filter-balance-metal-v1-residuals

- R1: resolved by `2026-07-borrowability-error-zero-mapping-v1`; the
  `snapshot_service.py` comments now use `{CRYPTO, METAL}`.
- R2: conditional test-coverage note, not an open production issue. Current
  live METAL rows have no spot leg, are classified `PERP_ONLY_EXCLUDED`, and
  correctly stay out of the borrow-candidate path. The synthetic test covers
  only the future case where a real margin-spot leg appears; then a live sample
  and review are required.
- R3: ignored by the original disposition. The report-artifact trailing
  whitespace requires no action.

Source: `2026-07-ui-filter-balance-metal-v1-residuals.md`.

## 2026-07-auto-review-pipeline

Status: **retired** by DEC-2026-07-14-002. The pipeline's cache-refresh pilot
produced no delivery-code changes and exposed write-authorization, empty-diff,
blocker-routing, seal-ordering, and stale-state defects, so
`auto-review-pipeline/v1` was retired. `docs/auto-review-pipeline.md` and
`scripts/auto-review-runner.py` have been **deleted**; they are no longer a
live contract or runner. The canonical Harness files were restored from the
existing `540513d` DRAFT-2 baseline (not a product-history reset); only the
lightweight `ACTIVE.json` plus Recovery Header startup fast path were kept as a
post-baseline usability addition.

| Artifact | Role |
|---|---|
| `2026-07-auto-review-pipeline-design-note.md` | **Historical** original design note (pre-delivery) |
| `2026-07-auto-review-pipeline-review-fable5.md` | **Historical** Fable5 review of design note (stale model/wall-clock claims may remain in body) |
| `reports/agent-runs/2026-07-auto-review-pipeline-design-review/` | **Historical** decision freeze evidence (`40-operator-decision-table.md`) |
| `reports/agent-runs/2026-07-auto-review-pipeline-v1/` | **Historical** delivery stage (accepted + merged pre-retirement); process evidence under `history/` |

Design archaeology (historical only — not a live contract):

`reports/agent-runs/2026-07-auto-review-pipeline-design-review/40-operator-decision-table.md`

## 2026-07-post-main-docs-hygiene-and-semantic-conflicts

Status: **proposed plan** under cross-model review (not yet an approved fix
stage). Treat the unamended S1–S9 list as **superseded for execution** by the
cross-review synthesis until the operator decides otherwise.

Source: `2026-07-post-main-docs-hygiene-and-semantic-conflicts.md`.

Contains: post-accept history archive record, scatter inventory, semantic
conflict table (C1–C7 + leave-alones), and original priority fix plan S1–S9.

### Cross-model review set (2026-07-12)

| Artifact | Role |
|---|---|
| `2026-07-post-main-docs-hygiene-codex-semantic-sync-plan.md` | Codex: layering, A1/A2 commit split, Batch B nav scope |
| `2026-07-docs-sync-method-opus4.8.md` | Opus 4.8: single-home SoT, accept ritual, A1/A2 vs original plan |
| `2026-07-post-main-docs-hygiene-and-semantic-conflicts-glm52-counterproposal.md` | GLM-5.2: authority-order fidelity, C4 split, P0/P1/P2 + lint stage |
| `2026-07-post-main-docs-hygiene-grok-cross-review.md` | **Grok cross-review synthesis** — verdicts, amendments, Batch 0→A→B→C→D |

**Execution authority:** operator only. Cross-review files do not authorize
commit, push, or model dispatch.

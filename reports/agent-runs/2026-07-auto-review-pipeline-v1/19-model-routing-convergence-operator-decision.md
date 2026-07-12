# Operator decision — include model routing convergence

## Decision

The human operator confirmed that the concurrent model-version changes were an
intentional Grok Fast task and explicitly authorized their inclusion in the
current auto-review-pipeline v1 upgrade.

This expands the T4 reviewed scope to include:

- Codex Harness default and schema-review model:
  `gpt-5.5` → `gpt-5.6-sol`;
- Grok development, direction, and auto review-1 model:
  `grok-build` / `grok-composer-2.5-fast` → `grok-4.5`;
- matching command templates and normative descriptions in `AGENTS.md`,
  `agents/registry.yaml`, `workflows/templates/stage-delivery.yaml`,
  `docs/model-adapters.md`, `docs/auto-review-pipeline.md`, and
  `docs/harness-design.md`.

`docs/harness-design.md` is therefore explicitly re-enabled for this amendment
despite the original T4 boundary. The historical
`direction_panels.2026_07_initial_direction` model/output identity remains
unchanged because it records the panel actually used. The locally observed
`grok-composer-2.5-fast` catalog entry may remain discovery evidence, but it is
not a Harness default.

## Authorship and review isolation

- Serial-v1 runtime/schema implementation and C1-C4 correction author:
  Claude-GLM / `zhipu_glm`.
- Model-routing convergence author: Grok Fast / `xai_grok`, as confirmed by the
  human operator.
- Review-1 remains Kimi / `moonshot_kimi` in a fresh read-only session.
- Review-2 remains Opus 4.8 / `anthropic`, isolated from both authors.

This is an operator-approved scope amendment, not an undeclared GLM boundary
violation and not a new formal rework charge. The combined committed diff and
full verification evidence must be reviewed together.

本地北京时间: 2026-07-12 14:06:35 CST
下一步模型: Codex bookkeeper
下一步任务: 复验合并范围、创建 evidence commit、重算 fingerprint、准备 Kimi review-1

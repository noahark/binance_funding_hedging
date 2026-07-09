# Review-2 Reviewer Fallback Evidence

Stage: `2026-07-harness-hardening-followups-v1`

## 决定

Review-2 由 anticipated primary `codex` / `gpt` fallback 到 `claude` / `claude-fable-5`。

## 触发原因（fallback trigger）

- `codex` / `GPT` 当前 `quota_exhausted`（限额 / rate-limited），user-confirmed 2026-07-09。
- 符合 `workflows/templates/stage-delivery.yaml` review-2 `fallback_only_on: [quota_exhausted, ...]`。
- Adapter 可用性参考：`agents/registry.yaml` codex `availability_check_command: "command -v codex"`（binary 存在，但服务侧配额耗尽属于 runner-level availability 失败，落入 quota_exhausted）。

## Provider isolation 分析（本 stage 参与方）

| Role | id | provider_identity |
| --- | --- | --- |
| designer + bookkeeper | `codex_gpt5` | `openai` |
| implementer | `claude_glm` | `zhipu_glm` |
| review-1 | `kimi` | `moonshot_kimi` |
| review-2（本次选定） | `claude` | `anthropic` |

- direction synthesis: skipped；development breakdown: skipped（本 stage 无 breakdown author）。
- `claude` / `anthropic` 对本 stage **无** design / breakdown / synthesis / implementation / fix 参与。
- 因此 `reviewer_prior_involvement = "none"`，**无需** design-conflict / strong-reviewer disclosure override。
- `reviewer_provider_must_differ_from_implementer_provider`: `anthropic` ≠ `zhipu_glm` ✓
- `reviewer_provider_must_differ_from_fix_author_provider`: 无 fix author ✓
- `reviewer_provider_should_differ_from_designer_provider`: `anthropic` ≠ `openai` ✓（designer 是 openai）

## 结论

此次 fallback 不仅合法（quota_exhausted 触发），而且相比 anticipated primary `codex`（本 stage 的 designer，provider `openai`）**提升**了 reviewer 隔离度：`claude` / `anthropic` 是本 stage 唯一的 unrelated strong reviewer。

`design_conflict_override.used = false`。

本地北京时间: 2026-07-09 22:11:13 CST

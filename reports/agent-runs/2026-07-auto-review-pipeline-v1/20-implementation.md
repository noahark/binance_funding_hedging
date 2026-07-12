# T1 Implementation Report — `contract-and-schemas`

Stage: `2026-07-auto-review-pipeline-v1` · Task: T1 · Mode: manual DRAFT-2
human dispatch (auto mode stays disabled for this bootstrap stage).

## 0. Metadata

- Branch (read at start, never switched): `stage/2026-07-auto-review-pipeline-v1`
- T1 `base_sha` (read from `status.json tasks[id=T1].base_sha`): `a385c7ad77da1611c6e952b2219aee56b49f442f`
- Implementer: `claude_glm` (provider identity `zhipu_glm`) / `glm-5.2[1m]`
- Pre-conditions verified before writing: branch matches;
  `tasks[id=T1].status == ready_for_human_dispatch`;
  `auto_review_pipeline.enabled_for_this_stage == false`;
  `parallel_mode.enabled == false`.
- T1 `head_sha` / `diff_fingerprint`: NOT set by the implementer. The bookkeeper
  creates the T1 delivery commit and records these; the implementer must not
  commit.

## 1. Changed Files And Allowlist Confirmation

All twelve delivery files touched by T1 are inside the §3 writable allowlist.
No forbidden path was touched.

| File | Status | In §3 allowlist |
|---|---|---|
| `schemas/auto-review-authorization.schema.json` | new | yes |
| `schemas/runner-receipt.schema.json` | new | yes |
| `reports/agent-runs/_template/status.json` | modified | yes |
| `reports/agent-runs/_template/70-handoff.md` | modified | yes |
| `AGENTS.md` | modified | yes |
| `workflows/templates/stage-delivery.yaml` | modified | yes |
| `agents/registry.yaml` | modified | yes |
| `docs/auto-review-pipeline.md` | new | yes |
| `docs/model-adapters.md` | modified | yes |
| `docs/parallel-development-mode.md` | modified | yes |
| `reports/agent-runs/README.md` | modified | yes |
| `reports/agent-runs/2026-07-auto-review-pipeline-v1/60-test-output.txt` | append (shared evidence) | yes (shared) |

`agents/developer-discipline.md` is in the T1 writable list but was **not**
modified: the frozen T1 contract (§5 items 1–9, breakdown §3) places no
additive requirement on it. It is generic developer execution discipline;
auto-review is a control-plane concern that does not change developer coding
discipline. Per the surgical-changes rule, no request → no edit. Flagged here
for reviewer awareness.

Shared evidence: this `20-implementation.md` is create-if-absent (T1 first
section). `60-test-output.txt` was appended only; pre-existing content was not
rewritten.

Forbidden paths verified untouched: `scripts/**`, `harness-manifest.yaml`,
`schemas/review-verdict.schema.json`, `agents/skills/**`, `backend/**`,
`frontend/**`, `schemas/api/**`, `docs/product/**`, the live stage
`status.json` / `70-handoff.md` / `30-review-1-*` / `task-*.prompt.md`, and all
`2026-07-funding-*` paths.

## 2. §5 Frozen T1 Contract — Item Status (1–9)

1. **`schemas/auto-review-authorization.schema.json`** — DONE. JSON Schema draft
   2020-12, `additionalProperties:false`. Fields match 10-design §Authorization
   Artifact one-for-one. `expires_at` is required and nullable
   (`["string","null"]`). Includes `supersedes` (`["string","null"]`) and
   `scope.{task_ids,allowed_pathspecs,forbidden_pathspecs,topology}`. All five
   budget keys present with `max_stage_rework` const 3, `max_auto_code_changes`
   maximum 2, `invalid_json_max_attempts_per_model` const 2.
   `auto_high_end_dispatch_allowed` is const false.
2. **`schemas/runner-receipt.schema.json`** — DONE. JSON Schema draft 2020-12,
   `additionalProperties:false`. Required fields match 10-design §Runner Receipt
   (schema_version/stage_id/sequence/node/attempt; adapter id + registry command
   ref; prompt/raw_output/verdict paths; started/completed/exit_status/timeout;
   call_budget before/after; failure_class; next_transition). The description
   states the forbidden-content rule; `adapter` stores only id + registry ref
   (never expanded command); `next_transition` and `failure_class` are
   enum-constrained so no model-selected next action or arbitrary string can
   be stored.
3. **`_template/status.json`** — DONE. Added the nested `auto_review_pipeline`
   block from 10-design §Status Shape with `enabled:false` default and
   `dispatch_mode:"human_dispatch"`. Both review blocks changed from prefilled
   `reviewer_prior_involvement:"none"` to `null` plus
   `reviewer_prior_involvement_pending:true` (the E1 shape this stage already
   applied to its own status).
4. **`_template/70-handoff.md`** — DONE. Added matching handoff fields
   (Auto-review pipeline / Dispatch mode / Runner state in Current State;
   Auto-run authorization / Runner receipts / Embedded cross-check set /
   Escalation artifacts / Pilot metrics in Artifact Index).
5. **AGENTS / workflow / registry / docs additive amendment** — DONE. Manual
   mode original meaning preserved everywhere (see §3.1: zero manual sentences
   reworded). The auto exception is explicitly predicated on a schema-valid,
   human-approved, committed per-stage authorization artifact; the runner is the
   sole automatic dispatcher; review-2 and merge remain human gates; manual/auto
   mode mutex is stated in AGENTS, workflow, registry, and the parallel-mode
   doc.
6. **Registry auto invocation policy** — DONE. The `auto_review_pipeline` block
   references the existing `adapters.grok.optional_review_command`
   (`grok-build`, plan mode) and the existing `invocation_owner:runner`. No new
   command was invented.
7. **`docs/auto-review-pipeline.md`** — DONE (normative). Contains: transition
   matrix; budgets; review-unit and seal summaries; post-cross-check blocking
   rerun; escalation contract; threat boundary; and the full Pilot Evaluation
   Contract (`auto-review-pilot-metrics.json` minimum fields, P11 metrics, 100%
   RECEIPT completeness, escalation drill, and rule 7 explicitly does not invent
   a promotion threshold).
8. **`docs/parallel-development-mode.md`** — DONE as minimal diff. One additive
   bullet states the mode mutex and migration wording. No document
   restructuring; historical "预审" wording in untouched bullets was left as-is
   per the rewrite-on-touch rule.
9. **`reports/agent-runs/README.md`** — DONE. Appended the new evidence names to
   the existing naming list (authorization, receipts, embedded-cross-check set,
   `80-escalation-*`, pilot metrics).

## 3. Additive-Change Audit

### 3.1 Pre-existing sentences modified (before/after, by file)

Only `reports/agent-runs/_template/status.json` has modified pre-existing
lines — the E1 `reviewer_prior_involvement` change in both review blocks. Every
other delivery file is pure additive insertion or a brand-new file; no other
pre-existing sentence was reworded.

**`reports/agent-runs/_template/status.json` — `review_1` block:**

before:
```json
    "reviewer_prior_involvement": "none",
```
after:
```json
    "reviewer_prior_involvement": null,
    "reviewer_prior_involvement_pending": true,
```

**`reports/agent-runs/_template/status.json` — `review_2` block:**

before:
```json
    "reviewer_prior_involvement": "none",
```
after:
```json
    "reviewer_prior_involvement": null,
    "reviewer_prior_involvement_pending": true,
```

(The two `before` lines are identical strings in different blocks; the
`review_1` line is followed by `fix_start_prompt_present`, the `review_2` line
by `reviewer_prior_involvement_notes`. The change is the frozen E1 pattern;
`"none"` is exactly the latent-bypass this stage removes.)

### 3.2 Additive insertions (by file)

- **`schemas/auto-review-authorization.schema.json`** — new file. Full
  authorization schema; no insertion anchor (entire file is additive).
- **`schemas/runner-receipt.schema.json`** — new file. Full receipt schema.
- **`reports/agent-runs/_template/status.json`** — one insertion: the
  `auto_review_pipeline` object is placed between the `parallel_mode` object and
  the `embedded_reviews` field. (Plus the two E1 line changes in §3.1.)
- **`reports/agent-runs/_template/70-handoff.md`** — two insertions: three
  lines after `- Parallel mode:` in Current State; five lines after
  `- Embedded review checkpoints:` in Artifact Index.
- **`AGENTS.md`** — one insertion: a new top-level section
  `## Auto Review Pipeline (Opt-In, Default-Off)` placed between the end of
  `## Hard Gates` (the `Harness/template sync lands on main only …` bullet) and
  `## Standard Stage Delivery`. No existing bullet or sentence was altered.
- **`workflows/templates/stage-delivery.yaml`** — two insertions: (a) auto
  guard keys added inside `guards:` immediately after
  `require_r4_diff_reconciliation_before_parallel_task_commits` and before
  `max_rework_per_stage`; (b) a new top-level `auto_review_pipeline:` mapping
  placed between the `guards:` block and the `artifacts:` block.
- **`agents/registry.yaml`** — one insertion: a new top-level
  `auto_review_pipeline:` mapping placed between the end of `model_policies`
  (after `terminal_stop_reasons`) and `failure_classes`.
- **`docs/auto-review-pipeline.md`** — new file. Normative contract.
- **`docs/model-adapters.md`** — one insertion: a new `## Auto Review Pipeline`
  section appended after the final paragraph of `## Dispatch Failure Semantics`
  (the `failure_classes.embedded_checkpoint` sentence). No prior section changed.
- **`docs/parallel-development-mode.md`** — one insertion: a single bullet
  appended to `## 6 与现行 workflow 的关系` (after the
  `reviewer_prior_involvement` disclosure bullet), stating mode mutex and
  migration. No other bullet reworded.
- **`reports/agent-runs/README.md`** — one insertion: new evidence filenames
  appended to the existing stage-directory naming list (after `status.json`,
  before the closing fence).

### 3.3 Audit summary

- Pre-existing sentences reworded: 2 (both the E1 `reviewer_prior_involvement`
  line in `_template/status.json`, listed verbatim above).
- All other changes are additive insertions or new files.
- No manual-mode rule was weakened, broadened, or silently reworded.

## 4. Required Checks — Raw Results And Exit Status

All commands are recorded in
`60-test-output.txt` (T1 section, 2026-07-11 13:32:15 CST). Summary:

| Command | Result | Exit |
|---|---|---|
| `python3 -m json.tool schemas/auto-review-authorization.schema.json` | PASS | 0 |
| `python3 -m json.tool schemas/runner-receipt.schema.json` | PASS | 0 |
| `python3 -m json.tool reports/agent-runs/_template/status.json` | PASS | 0 |
| `scripts/validate-stage.py 2026-07-auto-review-pipeline-v1 --phase checkpoint` | PASS (`STAGE VALIDATION PASSED`, status=designing) | 0 |
| `git diff --check` (worktree-equivalent) | PASS (no whitespace errors) | 0 |
| `grep -rn "formal-1" AGENTS.md workflows agents docs schemas reports/agent-runs/_template` | PASS (no matches) | 1 |

The committed-range `git diff --check <T1-base>..<T1-head>` is bookkeeper-run
after the T1 delivery commit; the implementer did not commit. The worktree
`git diff --check` is the implementer-side equivalent and is clean.

The `grep` negative scan initially matched a vocabulary line in the new
`docs/auto-review-pipeline.md` that named the forbidden literal term inside a
"do not use" sentence. The line was rephrased to avoid the literal term
without changing vocabulary policy, and the frozen command was rerun unchanged;
it now returns no matches (exit 1). The command was not rewritten to mask the
exit status.

## 5. `git status --short` (at report time)

```text
 M AGENTS.md
 M agents/registry.yaml
 M docs/model-adapters.md
 M docs/parallel-development-mode.md
 M reports/agent-runs/2026-07-auto-review-pipeline-v1/60-test-output.txt
 M reports/agent-runs/README.md
 M reports/agent-runs/_template/70-handoff.md
 M reports/agent-runs/_template/status.json
 M workflows/templates/stage-delivery.yaml
?? docs/auto-review-pipeline.md
?? schemas/auto-review-authorization.schema.json
?? schemas/runner-receipt.schema.json
```

All twelve paths are inside the §3 allowlist. No commit was created.

## 6. §6 Audit Questions — Explicit Answers

- **Manual rule original meaning preserved?** Yes. No manual-mode sentence in
  AGENTS.md, the workflow, the registry, model-adapters, the parallel-mode doc,
  or README was reworded. The only pre-existing lines changed are the two E1
  `reviewer_prior_involvement` placeholders in the template status, which is a
  frozen T1 requirement, not a manual-rule weakening. Auto exceptions are
  isolated in new sections/blocks and explicitly name the authorization
  artifact.
- **Default-off consistent across template/workflow/registry/docs?** Yes.
  Template `auto_review_pipeline.enabled:false`; workflow
  `auto_review_pipeline_default_enabled:false` and `default_enabled:false`;
  registry `default_enabled:false`; AGENTS and docs state default-off; this
  stage keeps `auto_review_pipeline.enabled_for_this_stage:false`.
- **Pilot Evaluation Contract complete?** Yes.
  `docs/auto-review-pipeline.md` §14 includes the
  `auto-review-pilot-metrics.json` minimum fields, P11 metrics (Grok
  schema-valid rate, escalation-shape validation, RECEIPT completeness), the
  100% RECEIPT completeness rule, the controlled escalation drill, and rule 7
  explicitly states v1 invents no global promotion threshold.
- **Nullable `expires_at` semantics?** `expires_at` is required (in the schema
  `required` array) and nullable (`["string","null"]`). Missing field → invalid.
  `null` → no independent authorization-expiry timestamp, not unlimited; still
  bound by call/wall-clock/rework budgets, operator stop, and stage gates.
  Non-null ISO8601 → enforced before every model call and commit. Stated in the
  schema description, AGENTS auto section, and `docs/auto-review-pipeline.md` §2.
- **Any forbidden path touched?** No (expected). Verified by `git status` and
  the forbidden-path scan in `60-test-output.txt`.

## 7. Blockers, Risks, Review-1 Focus

- **Blockers:** none. All §5 items landed; all §7 checks pass; no stop-condition
  in §8 was triggered.
- **Unresolved risks:**
  - Contract-text drift remains the highest review-2 exposure. The mitigation
    is this verbatim before/after + additive-insertion audit (§3) and the
    frozen-command evidence (§4).
  - `agents/developer-discipline.md` was intentionally not edited; if review-1
    finds an auto-mode developer-discipline rule is required, that is a design
    amendment, not a T1 fix-forward.
  - The template `auto_review_pipeline` block uses runtime-null fields
  (`authorization_path`, `runner_state`, `budgets`, etc.) for the default-off
  state; positive values are filled only when a real authorization lands. This
  matches 10-design "default-off compatibility" but review-1 should confirm the
  validator treats `enabled:false` as "skip auto checks" (T2 owns the validator
  implementation).
- **Suggested review-1 (Kimi) focus, beyond the frozen breakdown list:**
  1. Field-level match of both schemas vs 10-design shapes — especially
     `expires_at` required+nullable and the three frozen budget numbers
     (`max_stage_rework` const 3, `max_auto_code_changes` ≤ 2,
     `invalid_json_max_attempts_per_model` const 2), and
     `auto_high_end_dispatch_allowed` const false.
  2. Zero weakening of any manual rule — audit every line in the T1 diff against
     §3.1/§3.2; confirm only the two E1 lines changed and all else is additive.
  3. `docs/auto-review-pipeline.md` completeness vs 10-design, especially the
     Pilot Evaluation Contract and the post-cross-check blocking rerun rule.
  4. Receipt schema really forbids expanded command / env / secret /
     model-selected next action (enum-constrained `next_transition` and
     `failure_class`; `adapter` stores reference only).
  5. Registry auto policy references the existing `adapters.grok.optional_review_command`
     and `invocation_owner:runner`, inventing no new command.

## 8. What The Implementer Did NOT Do

- Did not commit, push, merge, rebase, create a branch, or modify git history.
- Did not write `status.json`, `70-handoff.md`, `30-review-1-*`, or any review
  file for the live stage.
- Did not set T1 `head_sha` / `diff_fingerprint` (bookkeeper-owned).
- Did not dispatch any model, run any live model/network/auto-review runner, or
  record any credential/token/cookie/expanded alias.
- Did not touch `scripts/**`, `harness-manifest.yaml`,
  `schemas/review-verdict.schema.json`, `agents/skills/**`, product/runtime
  paths, or any other task's files.

Next step is the bookkeeper: verify boundaries, run independent commands,
create the committed T1 range, compute the standard fingerprint, run the
validator gate, and prepare the human Kimi review-1 packet. The Kimi review-1
gate must not be skipped.

```text
本地北京时间: 2026-07-11 13:36:27 CST
下一步模型: Codex/GPT（bookkeeper）
下一步任务: 检查 T1 实现与 raw evidence，形成 committed review unit；不得跳过 Kimi review-1 gate
```

---

## T1 合并修正轮次 1 v2（Claude-GLM 执行 · rework_count = 0 · 合并前有界修正）

> Append-only 追加。前文 §1–§8 为 T1 初始实现报告，**未改动**。本节记录对合并任务包
> `reports/agent-runs/2026-07-auto-review-pipeline-v1/task-T1-correction-round1-v2-claude-glm.prompt.md`
> （`correction_packet_revision: round1-v2`，合并 bookkeeper T1-B1..B5 + Fable5 A1..A7 并带书签处置）
> 的 C1–C8 修正执行。这是单一合并前修正轮次，`rework_count` 保持 0。

### C0 执行上下文与安全约束遵守

- 执行模型：`claude_glm`（`zhipu_glm` / `glm-5.2[1m]`）。
- 分支：`stage/2026-07-auto-review-pipeline-v1`；T1 dispatch base `a385c7ad77da1611c6e952b2219aee56b49f442f`。
- 任务状态：`correction_round1_v2_ready_for_human_dispatch` → 本会话执行 C1–C8（不写实时 status.json）。
- 前置不变：`auto_review_pipeline.enabled_for_this_stage=false`；`parallel_mode.enabled=false`。
- **未做**：commit/push/merge/rebase/branch；修改 git 历史；派发任何模型（Kimi 或其他）；运行实时模型/网络/自动审查 runner；写实时 stage `status.json` / `70-handoff.md` / `30-review-1-*` / `50-review-2-*` / 检查包文件 / `agents/registry.yaml`（只读）；触碰产品/运行时路径、`scripts/**`、`harness-manifest.yaml`、`schemas/review-verdict.schema.json`、`agents/skills/**`、`agents/developer-discipline.md`、其他 T1 文件、T2/T3 文件。
- 锁定词汇：全程使用 `review-1` / `review-2` / `embedded cross-check`；**未使用** `formal-1`（`grep -rn formal-1` EXIT 1，零匹配）。验证器机器名 `--phase pre-review` 保留不变。
- 回执仅含命令引用；未记录任何展开命令/环境变量/令牌/密钥/cookie。
- 冻结不变项保留：`diff_fingerprint` 公式未改；授权 schema 未硬编码 `^stage/` 前缀（保留 intake 时用户批准的分支例外）；Authority Order 未提升（A1 推迟）；review-2/merge 门限未改；当前 stage 自动模式未启用。

### C1 — `runner-receipt.schema.json` required 扩充至 18

`required` 由 13 增至 **18**：在 `adapter` 与 `started_at` 之间新增 `review_unit_id`、`task_id`、`prompt_path`、`raw_output_path`、`verdict_path`。消除 T1-B1 指出的"收据可省略证据路径/单元归属"缺陷。反例 `missing 5 required evidence keys` → INVALID。

### C2 — `runner-receipt.schema.json` 安全路径与枚举加固

- 新增 `$defs.safe_repo_relative_path`：`oneOf:[{type:null},{type:string, minLength:1, pattern:"^[^/].*$", allOf:[{not:{pattern:"\.\."}},{not:{pattern:"[\r\n\t\x00-\x1f\x7f]"}}]}]`。用 `oneOf` 而非 `not:{pattern}` 修复了"null 值下 `not:{pattern}` 失效"的 JSON Schema 细微 bug（`pattern` 不约束非字符串）。
- `prompt_path`/`raw_output_path`/`verdict_path` → `$ref` 该安全路径。
- `adapter.registry_command_ref` 改为 **6 值 enum**（冻结收据 registry 命令引用精确集）；`adapter.allOf` 3 个 `if(id=X)/then(ref-enum)` 块强制 id↔ref 一致（claude_glm/kimi/grok）。
- `next_transition.enum` 移除 `bookkeeper_decision`（无自动模式来源；手动的节点拼写为 `bookkeeper-decision`），保留 `null` + 9 个非 null 值。
- 顶层 `allOf` 3 块：`node∈[implementation,fix]`→write/noninteractive refs；`node=embedded_cross_check`→embedded_read_only_review refs；`node=review_1`→`adapter.id` const `grok` + ref const `grok.optional_review_command`。
- 反例全部命中：expanded/secret-like ref→INVALID；id/ref mismatch→INVALID；same-prefix yolo/availability ref→INVALID；`next_transition=bookkeeper_decision`→INVALID；review_1 with claude_glm→INVALID。

### C3 — `workflows/templates/stage-delivery.yaml` `executable_contract` 块（纯加法）

在 `auto_review_pipeline` 下加 `executable_contract:`，含 `activation_predicate`、`authorized_exception`、`frozen_nodes_and_order`、`p7_one_blocking_fix_then_escalate`、`review_1_fixed_transitions`、`completion_predicate`、`pilot_and_default_flip_predicate`、`allowed_next_transitions`（9 项）、`disabled_representation`。
- **YAML 修复**：`frozen_nodes_and_order` 初版在 block sequence 列表项（6 空格缩进）后直接跟同缩进 `note:` 映射键（6 空格），Ruby Psych 报 `did not find expected '-' indicator while parsing a block collection at line 124 column 7`（EXIT 1）。根因：列表项与同级键同缩进冲突（`activation_predicate.all_of` / `completion_predicate.all_of` 的列表项为 8 空格、其 `otherwise:`/`then:` 为 6 空格，故不冲突）。修复：将 `frozen_nodes_and_order` 重构为映射，含 `order:` 子列表 + `note:` 子键。修复后 Ruby/Python YAML 均通过（见 `60-test-output.txt` 末尾"YAML 修复后重跑"块）。`schemas/**` 未在此修复中改动。

### C4 — `docs/auto-review-pipeline.md` disabled 语义

§4 增段落：`disabled` 是概念性的；机器表示 = `enabled:false` + `dispatch_mode:human_dispatch` + `runner_state:null`；**不是**第 6 个 `runner_state`。

### C5 — 术语统一 `embedded cross-check`

逐字改前 / 改后（仅列实际替换的句子；其余"预审 / embedded pre-review / embedded cross-review"出现按 rewrite-on-touch 规则未触及）：

AGENTS.md（4 处）：
1. `embedded cross-review mode contract.` → `embedded cross-check mode contract.`
2. `applies to implementation, embedded pre-review, review-1, review-2, and fix dispatches.` → `applies to implementation, embedded cross-check, review-1, review-2, and fix dispatches.`
3. `embedded pre-review prompt paths, cross-review routing,` → `embedded cross-check prompt paths, cross-review routing,`
4. `run embedded cross-review checkpoints from` → `run embedded cross-check checkpoints from`

`docs/parallel-development-mode.md`（2 处）：
1. `重建"预审 N 轮 → 提交 → 正式确认"的完整链路。` → `重建"embedded cross-check N 轮 → 提交 → 正式确认"的完整链路。`
2. `预审落档是证据增强，不是新门。` → `embedded cross-check 落档是证据增强，不是新门。`

> 注：AGENTS.md 的 `## Auto Review Pipeline (Opt-In, Default-Off)` 整节、parallel-mode 的"与 auto-review pipeline 互斥"块均为**合并工作的纯加法**，非本轮 C5 产物；C5 仅做上述术语替换。验证器机器名 `--phase pre-review` 保留不变。

### C6 — `docs` P7 子章节 + seal 收据路径 + README

- `docs/auto-review-pipeline.md` §7 增 `### P7: one automatic blocking-fix, then escalation`：一次初始阻塞测试失败 → 一次自动修复（计入账本）；第二次相同阻塞集失败 → 升级；`max_auto_code_changes<=2` 是共享聚合值，**不是**两次阻塞修复。
- `docs/auto-review-pipeline.md` §8 增 `runner-<seq>-seal.receipt.json` 路径块：确定性 seal 证据（T2 形状），**非** adapter 调用回执，不针对 `runner-receipt.schema.json` 验证，排除在 P11 adapter 调用分母之外。
- `reports/agent-runs/README.md`：在 `runner-<seq>-<node>.receipt.json` 行之后增 `runner-<seq>-seal.receipt.json` 行。

### C7 — `auto-review-authorization.schema.json` 安全路径与范围

- 新增 `$defs.safe_required_repo_relative_path`（string）与 `safe_nullable_repo_relative_path`（`oneOf` null/string）。
- `approval_evidence_path` → `$ref` 必填安全路径；`supersedes` → `$ref` 可为空安全路径。
- `scope.task_ids` 增 `minItems:1, uniqueItems:true`。
- `stage_branch` 增 `allOf:[{not:{pattern:"[\r\n\t\x00-\x1f\x7f]"}}]` + 描述性注释（不强制 `^stage/` 前缀；runner 精确匹配，保留 intake 时用户批准的分支例外）。
- 修复 `$defs` 模式拼写错误（尾部反斜杠 → `\\.`）。
- 反例全部命中：absolute/traversal/newline `approval_evidence_path`→INVALID；unsafe non-null `supersedes`→INVALID；empty/duplicate `task_ids`→INVALID；control-character `stage_branch`→INVALID；safe non-`stage/` branch→**VALID**（例外保留）。

### C8 — 本报告 + errata（本节）

### Errata（原始报告勘误）

1. **交付路径计数**：原始报告称"12 个"交付路径；实际为 **13 个** = 11 个交付件 + 2 个共享证据追加文件（`20-implementation.md`、`60-test-output.txt`）。
2. **报告自身遗漏**：原始报告的 git-status 快照未列出报告文件自身（`20-implementation.md`）。
3. **收据 required 字段数（T1-B1）**：原始报告关于收据必填字段数的声明不准确；C1 后 `runner-receipt.schema.json` `required` 为 **18** 个（含新增 `review_unit_id`/`task_id`/`prompt_path`/`raw_output_path`/`verdict_path`）。

### A1 推迟 / A5 / A7 记录注释

- **A1（Authority Order 提升）— 推迟**：不在此修正轮次提升 Authority Order。`review-1`/`review-2`/`embedded cross-check` 术语统一已落地（C5），但 authority 次序本身未改动；验证器机器名 `--phase pre-review` 保留。
- **A5（diff_fingerprint）— 记录**：四处 `diff_fingerprint` 文本副本按字节相等；未引入新指纹协议；seen-diff bind 仅为 patch 字节相等，不作为第二指纹协议记录。T2 仍拥有规范函数；本修正未改动 `diff_fingerprint` 公式。
- **A7（registry 机器键 `embedded_pre_review`）— 记录**：注册表机器键 `embedded_pre_review` 仅出于兼容保留，**不是**术语先例；键名未更改（`agents/registry.yaml` 对本修正只读）。

### 最终改动路径（`git status --short`）

本轮 C1–C8 可写集内改动：
- `M AGENTS.md` — C5 术语 ×4（基线 `## Auto Review Pipeline` 整节为合并工作加法，非本轮）。
- `M docs/parallel-development-mode.md` — C5 术语 ×2（基线互斥块为合并工作加法，非本轮）。
- `M reports/agent-runs/README.md` — C6 seal path 行。
- `M workflows/templates/stage-delivery.yaml` — C3 `executable_contract`（含 `frozen_nodes_and_order` YAML 修复）。
- `M reports/agent-runs/2026-07-auto-review-pipeline-v1/60-test-output.txt` — 追加修正轮次证据 + YAML 修复重跑块。
- `?? schemas/runner-receipt.schema.json` — C1+C2（对基线已存在、未 commit 的上一轮 schema 文件的重写/加固）。
- `?? schemas/auto-review-authorization.schema.json` — C7（对基线已存在、未 commit 的上一轮 schema 文件的编辑/加固）。
- `?? docs/auto-review-pipeline.md` — C4+C6（基线 normative contract + 本轮 P7/disabled/seal 段落）。
- `20-implementation.md`（本文件）— C8 append（本节）。

基线合并工作改动（**本会话未触碰**，bookkeeper T1-B* / Fable5 A* 产物）：
- `M agents/registry.yaml` — `auto_review_pipeline:` 块（runner/loop_adapters/review_1/receipts/unchanged_invariants）。对本修正只读。
- `M docs/model-adapters.md` — `## Auto Review Pipeline` 节。
- `M reports/agent-runs/_template/70-handoff.md` — auto-review/dispatch/runner 模板字段。
- `M reports/agent-runs/_template/status.json` — `auto_review_pipeline` 块 + `reviewer_prior_involvement_pending`（A2/A3 落地）。

### 冻结检查结果（原始证据见 `60-test-output.txt`）

- `python3 -m json.tool` ×3（两 schema + 任务包）EXIT 0；`validate-stage.py` checkpoint EXIT 0（status=fixing）；`git diff --check` EXIT 0；`grep -rn formal-1` EXIT 1（零匹配）。
- 17 个 `jsonschema` counterexamples 全 `[OK]`（3 positive + 14 negative，每个 negative ≥1 error）。
- Ruby 冻结 YAML 解析：`YAML PARSE PASSED`（EXIT 0）。
- Ruby 断言全 `true`：`allowed_next_transitions`(9) == receipt `next_transition.enum` non-null(9)；集合不含 `bookkeeper_decision`；`runner_states` 不含 `disabled`；`disabled` machine_representation == `{enabled:false, dispatch_mode:human_dispatch, runner_state:null}`；docs 与 README 均含 `runner-<seq>-seal.receipt.json`。
- Python yaml round-trip：`frozen_nodes_and_order` == `{order:[preflight, implementation, initial_blocking, embedded_cross_check_run_or_skip_or_unavailable, identical_post_cross_check_blocking_rerun, seal, review_1], note:...}`；`allowed_next_transitions` count 9。

> 依据任务包 `## 停止并返回`：未 commit；未写 status/handoff/review 文件；未派发 Kimi。下一步交由 bookkeeper 独立复跑冻结/反例检查，通过后才可 seal 并准备 Kimi review-1。

```text
本地北京时间: 2026-07-11 15:29:54 CST
下一步模型: Codex/GPT（bookkeeper）
下一步任务: 重新检查 merged T1 correction、独立复跑 frozen/counterexample checks；通过后才可 seal 并准备 Kimi review-1
```

---

## T1 Correction Round 2（Claude-GLM 执行 · rework_count = 0 · 合并前有界修正）

> Append-only 追加。前文（§1–§8 + Round 1 v2 节）**未改动**。本节记录对
> `task-T1-correction-round2-claude-glm.prompt.md`（`correction_packet_revision: round2`）的
> R2-C1–C4 执行，回应 bookkeeper reinspection `24-bookkeeper-reinspection-T1.md` 的
> T1-R2-1 / T1-R2-2。`rework_count` 保持 0（pre-seal 有界修正，非 formal review-1 rework）。

### 执行上下文与安全约束遵守

- 模型 `claude_glm`（`zhipu_glm` / `glm-5.2[1m]`）；分支 `stage/2026-07-auto-review-pipeline-v1`；
  T1 base `a385c7ad77da1611c6e952b2219aee56b49f442f`（HEAD 祖先 ✓）；HEAD `6546bc94`。
- task status `correction_round2_packet_ready_for_human_dispatch`；`auto_review_pipeline.enabled_for_this_stage=false`；`parallel_mode.enabled=false`。
- **可写集（本 round2 收窄）**：`schemas/runner-receipt.schema.json`、`workflows/templates/stage-delivery.yaml`、`docs/auto-review-pipeline.md`；追加 `20-implementation.md`、`60-test-output.txt`。
- **未做**：commit/push/merge/rebase/branch；派发任何模型（Kimi 或其他）；运行 live model/network/auto-review runner；写 status/handoff/inspection/packet/review 文件；触碰 `agents/registry.yaml`、`AGENTS.md`、`docs/parallel-development-mode.md`、`docs/model-adapters.md`、`reports/agent-runs/README.md`、`_template/*`（本 round2 只读）、`scripts/**`、`manifest`、产品/runtime、funding stages。
- 锁定词汇：`review-1` / `review-2` / `embedded cross-check`；未用 `formal-1`（`grep -rn "formal-1"` EXIT 1）。验证器机器名 `--phase pre-review` 保留。
- Non-Regression：round1-v2 已通过的 receipt required(18)/safe paths/authorization schema/P7/disabled/seal path/Pilot docs/post-cross-check rerun/seen-diff bind/manual mode/fingerprint/Authority Order/review-2/merge gates 均未破坏；本 stage auto mode 未启用。

### T1-R2-1 / T1-R2-2（bookkeeper reinspection 阻塞项）

- **T1-R2-1（P1）**：receipt schema `node=review_1` 条件强制 `adapter.id=grok` + `grok.optional_review_command`，使冻结 D7/ADR 允许的 Kimi / Claude-GLM serial-unit fallback receipt 各产生 2 个 schema errors（reinspection 实测：`grok_primary=0`、`kimi_serial_fallback=2`、`glm_serial_fallback=2`）。schema 使一条冻结 workflow 分支不可表达。
- **T1-R2-2（P1）**：`executable_contract` 无 `state_transitions` / `node_transitions`；review-1 结果与 activation/pilot 条件多为自然语言字符串/布尔（如 `"ACCEPT advances the unit"`、`"retry same model once, then serial unit fallback or human escalation"`）。确定性 runner 无法从这些句子派生精确 event→next-state/node 选择，违背"workflow 定义 transition、runner 只执行"的冻结规则；T1-B3 未完全关闭。

### R2-C1 — receipt schema `review_1` 改为三 pair `oneOf`

将 top-level `allOf` 中 `node=review_1` 块的 `then.adapter` 从"强制 grok"改为 `oneOf` 三个精确 pair：

- `grok` + `agents/registry.yaml#adapters.grok.optional_review_command`
- `kimi` + `agents/registry.yaml#adapters.kimi.embedded_read_only_review_command`
- `claude_glm` + `agents/registry.yaml#adapters.claude_glm.embedded_read_only_review_command`

逐字 before / after：

- description before：`review_1 nodes use the Grok optional review command only.`
- description after：`review_1 nodes use exactly one of the three frozen review-1 routes: Grok primary (optional_review_command), or a Kimi/Claude-GLM serial-unit fallback (each provider's embedded_read_only_review_command). Schema validity alone never declares fallback eligibility; serial-only topology, author-set eligibility, parallel-tip escalation, and tip-once Grok failure remain runner/validator checks.`
- then.adapter before：`properties: { id: {const: grok}, registry_command_ref: {const: ...grok.optional_review_command} }`
- then.adapter after：`oneOf: [ {id const grok, ref const grok.optional_review_command}, {id const kimi, ref const kimi.embedded_read_only_review_command}, {id const claude_glm, ref const claude_glm.embedded_read_only_review_command} ]`（每个 pair `required:[id, registry_command_ref]`）。

counterexamples（Draft202012Validator）：正例 grok primary / kimi serial fallback / glm serial fallback 全 VALID(0)；负例 kimi noninteractive review-1 / grok development review-1 / adapter-ref mismatch 全 INVALID(各 ≥1 error)。schema 只表达可表示 route；serial-only、author-set、parallel-tip、tip-once Grok failure 仍由 runner/validator 运行时检查。

### R2-C2 — docs 移除无冻结出处的 "or Grok"

`docs/auto-review-pipeline.md` 的 embedded cross-check 示例原含无冻结出处的 `or Grok`，而冻结决策示例与 schema 的 embedded cross-check node 只允许 GLM/Kimi read-only refs。最小修改为冻结示例 `e.g. GLM↔Kimi`（**不扩大** Grok cross-check route）。逐字 before / after：

- before：`` - `embedded cross-check`: advisory cheap-model cross-read (e.g. GLM↔Kimi or Grok). **Not** formal review-1. **Not** validator `--phase pre-review`. ``
- after：`` - `embedded cross-check`: advisory cheap-model cross-read (e.g. GLM↔Kimi). **Not** formal review-1. **Not** validator `--phase pre-review`. ``

### R2-C3 — workflow 结构化 transition maps（纯加法，+239 行）

在 `auto_review_pipeline.executable_contract` 末尾（`disabled_representation` 之后）新增 5 个 runner 可直接读取的 structured mappings；保留 round1-v2 已通过的 `activation_predicate` / `frozen_nodes_and_order` / `p7_one_blocking_fix_then_escalate` / `review_1_fixed_transitions`（降级为人类可读 note）/ `completion_predicate` / `pilot_and_default_flip_predicate` / `allowed_next_transitions` / `disabled_representation`。transition choice 不再只存在于自然语言。

1. **`activation_requirements`**：`status_field=auto_review_pipeline.enabled` / `status_value_required=true`；authorization（schema_ref、must_be_committed、authorized_by=human、must_not_be_expired）；`exact_match_required=[stage_id, stage_branch, scope.task_ids, scope.allowed_pathspecs, scope.forbidden_pathspecs, budgets]`；`parallel_mode_mutex_required`；`on_failure={adapter_call_made:false, effect:manual unchanged}`。
2. **`state_transitions`**（8 项，逐行对应 10-design Transition Model 八行）：id = `authorize_new_run`、`preflight_authorized_to_running`、`recoverable_fallback_to_awaiting`、`explicit_human_mode_flip`、`resume_on_new_authorization`、`operator_stop`、`all_required_units_accept`、`terminal_escalation`；每项 `from`/`to` 为 structured `{dispatch_mode, runner_state}`，`event` 为 string 或 `one_of` list；概念 disabled = `{dispatch_mode: human_dispatch, runner_state: null}`（非第六个 runner_state）。
3. **`node_transitions`**：覆盖 `implementation`/`initial_blocking`/`fix`/`embedded_cross_check`/`post_cross_check_blocking`/`seal`/`review_1`/`completion`/`escalation`；条件分支用 object（如 `review_1.accept={more_units_remaining: review_1, all_units_done: completed_review_1}`），leaf 均为 exact target，无 `or`/`then` 自然语言选择。
4. **`review_1_routes`**：primary `grok`+`grok.optional_review_command`（grok-build, plan）；`serial_fallback`（`serial_only:true`、`pool:[kimi, claude_glm]`、三 pair command_refs、author-set eligible）；`parallel_tip.cross_pool_fallback_enabled:false`；`high_end_auto_substitution:false`；`invalid_json_attempt_limit_per_model:2`。
5. **`pilot_predicate`**（8 精确值）：`required_pilot_kinds=[docs_only, small_real]`、`required_terminal_status=stage_accepted_waiting_user`、`min_final_schema_valid_grok_verdicts=1`、`required_adapter_receipt_completeness_rate=1.0`、`require_escalation_shape_validation=true`、`require_controlled_escalation_drill_in_at_least_one_pilot=true`、`grok_rate_promotion_threshold=null`、`automatic_default_flip_allowed=false`。

`allowed_next_transitions` 与 receipt `next_transition.enum`（non-null）集合保持相等（断言锁定）；fingerprint / top-level status / review-2/merge gates / auto default 均未改。

### R2-C4 — 本节 + 证据（`60-test-output.txt` round2 块）

### 最终改动路径（`git status --short`）

本 round2 可写集改动：
- `M workflows/templates/stage-delivery.yaml` — R2-C3（+239 行 structured maps）。
- `?? schemas/runner-receipt.schema.json` — R2-C1（review_1 oneOf 三 pair；未跟踪文件，含 round1-v2 + round2 改动）。
- `?? docs/auto-review-pipeline.md` — R2-C2（移除 `or Grok`；未跟踪文件，含 round1-v2 + round2 改动）。
- `M reports/agent-runs/2026-07-auto-review-pipeline-v1/60-test-output.txt` — 追加 round2 证据块。
- `20-implementation.md`（本文件）— R2-C4 append（本节）。

本 round2 **未触碰**（round1-v2 / 基线遗留的未 commit 工作树改动）：
- `M AGENTS.md`、`M docs/parallel-development-mode.md`、`M reports/agent-runs/README.md`（round1-v2 C5/C6）。
- `?? schemas/auto-review-authorization.schema.json`（round1-v2 C7）。
- `M agents/registry.yaml`、`M docs/model-adapters.md`、`M reports/agent-runs/_template/70-handoff.md`、`M reports/agent-runs/_template/status.json`（基线合并工作）。

### 风险

- structured maps 是 runner 可读的权威 transition 选择，但 runner 实现归 T3；本 round2 只交付 machine-readable 契约。review-1 fallback 的 serial-only topology / candidate-provider 不在 unit author+fix provider 集合 / parallel-tip 无 cross-pool fallback / tip-once Grok failure→escalation 仍由 runner/validator 运行时检查，schema 只表达可表示 route。
- `state_transitions` 八行逐行对应 10-design Transition Model（已 frozen）；design 若演化需同步。
- `review_1_routes` 三 pair 与 receipt schema `review_1` oneOf 三 pair 已用 Ruby 断言锁定一致。

### 冻结检查结果（原始证据见 `60-test-output.txt` round2 块）

- `json.tool` EXIT 0；`validate-stage --phase checkpoint` → `STAGE VALIDATION PASSED`（status=fixing）EXIT 0；`git diff --check` EXIT 0；`grep -rn "formal-1"` EXIT 1（零匹配）；ruby `YAML PARSE PASSED` EXIT 0。
- review-1 routes：3 正例（grok primary / kimi serial fallback / glm serial fallback）全 VALID(0)；3 负例（kimi noninteractive / grok development / adapter-ref mismatch）全 INVALID(各 ≥1 error)。
- Ruby 结构化断言全 `true`：`state_transitions` 8 个唯一 id、from/to 为 structured object 且 event present；`node_transitions` 覆盖 7 个必需 node；`review_1_routes` 三 pair == receipt schema `review_1` oneOf 三 pair；`pilot_predicate` 8 keys 精确值匹配；`node_transitions` leaf 无 `or`/`then` 自然语言 prose；`allowed_next_transitions` == receipt `next_transition.enum`（non-null）。

> 依据任务包 `## Non-Regression / Stop`：未 commit；未写 status/handoff/review 文件；未派发 Kimi；未启用本 stage auto mode。下一步交由 bookkeeper 独立复验 round2 fallback/schema/transition maps，通过后才可 seal 并准备人工 Kimi review-1。

```text
本地北京时间: 2026-07-11 16:00:46 CST
下一步模型: Codex/GPT（bookkeeper）
下一步任务: 独立复验 T1 round2 fallback/schema/transition maps；通过后才可 seal 并准备人工 Kimi review-1
```

---

## T1 Correction Round 3（Claude-GLM 执行 · rework_count = 0 · 合并前有界修正 · 两处 node-graph 闭合）

### 执行上下文与安全性

- 工作包：`reports/agent-runs/2026-07-auto-review-pipeline-v1/task-T1-correction-round3-claude-glm.prompt.md`（packet commit `8008f951`，base `a385c7ad`）。
- 触发：Fable5 第二次复检 `25-second-reinspection-T1-fable5.md` 确认 T1-R2-1 / T1-R2-2 主体关闭，仅剩两处 node-graph 闭合残留（R3-1 / R3-2）。
- Writable set：仅 `workflows/templates/stage-delivery.yaml`；append-only：`20-implementation.md`、`60-test-output.txt`。其他全部只读（含两个 schema、docs、registry、AGENTS、模板、status/handoff/inspection/packet/review files、`scripts/**`、manifest、产品与 funding-stage 路径）。
- 安全约束遵守：未 commit / push / merge / rebase / 切换 branch；未 dispatch 任何模型（Kimi 或其他）；未运行实时 model / network / auto-review runner；未写 status / handoff / inspection / packet / review；未改 `review_1_fixed_transitions` 与 `activation_predicate` 两个散文块（结构化版本为权威，散文按 round2 规则留存）；未改 `state_transitions` / `allowed_next_transitions` / `review_1_routes` / `pilot_predicate` / 任何 schema / docs；rework_count 保持 0（全部为 pre-seal inspection 循环）。
- 先决条件核验：branch `stage/2026-07-auto-review-pipeline-v1` ✓；T1 base `a385c7a` ✓；T1 status `correction_round3_packet_ready_for_human_dispatch` ✓；`auto_review_pipeline.enabled_for_this_stage = false` ✓；`parallel_mode.enabled = false` ✓。

### 残留（round3 必修，均为 node-graph 闭合）

机器化闭合检查（target ∈ node_transitions 键集 ∪ {completed_review_1, human_escalation_required}）发现两类未解析 target：

- **T1-R3-1**：`node_transitions` 的接收键名为 `post_cross_check_blocking`，但 `embedded_cross_check` 三个 event（ran / skipped / unavailable）的 target、以及 `frozen_nodes_and_order.order` 均为 `identical_post_cross_check_blocking_rerun` —— 同一节点两个名字，图不闭合，T3 runner 加载器须特判别名。
- **T1-R3-2**：`review_1.invalid_json.after_retry_limit` 的 target `serial_unit_fallback` 无接收键定义；其语义原由相邻 `serial_fallback_unavailable` 行 + `review_1_routes.serial_fallback` “拼出”，正是 R2-2 所禁止的 runner 猜测。

两处均为命名 / 闭合级修正，不触碰任何冻结决策。

### R3-C1 — 统一 post-cross-check blocking 节点名

`executable_contract.node_transitions` 的接收键 `post_cross_check_blocking` 改名为 `identical_post_cross_check_blocking_rerun`，与 `frozen_nodes_and_order.order`（第 129 行）及 `embedded_cross_check` 三个 event target（第 246–248 行）完全一致。只改键名，不改其 `pass` / `fail` 分支值。

逐字 before：

```yaml
      post_cross_check_blocking:
        pass: "seal"
        fail: "human_escalation_required"
```

逐字 after：

```yaml
      identical_post_cross_check_blocking_rerun:
        pass: "seal"
        fail: "human_escalation_required"
```

### R3-C2 — 定义 serial_unit_fallback 接收节点

新增 `serial_unit_fallback` 接收节点，表达路由选择的两个确定性出口；eligibility 规则不变，仍由 `review_1_routes.serial_fallback`（serial_only、provider 不在 unit author / fix set）定义。同时删除 `review_1.serial_fallback_unavailable: "human_escalation_required"` 一行 —— 其语义已被新节点的 `no_eligible_candidate` 分支完整覆盖，保留会造成同一转移两处定义。

逐字 before：

```yaml
        invalid_json:
          first_attempt: "review_1"
          after_retry_limit: "serial_unit_fallback"
        serial_fallback_unavailable: "human_escalation_required"
        tip_once_grok_failure: "human_escalation_required"
      completion:
```

逐字 after：

```yaml
        invalid_json:
          first_attempt: "review_1"
          after_retry_limit: "serial_unit_fallback"
        tip_once_grok_failure: "human_escalation_required"
      serial_unit_fallback:
        eligible_candidate_found: "review_1"
        no_eligible_candidate: "human_escalation_required"
      completion:
```

### 冻结套件与闭合断言（原始证据见 60-test-output.txt round3 块）

- `scripts/validate-stage.py 2026-07-auto-review-pipeline-v1 --phase checkpoint` → `STAGE VALIDATION PASSED`（status=fixing），EXIT 0。
- `git diff --check` → EXIT 0（无空白错误）。
- `grep -rn "formal-1" AGENTS.md workflows agents docs schemas reports/agent-runs/_template` → EXIT 1（无匹配，锁定词汇表未被破坏）。
- `ruby` YAML parse（workflow + registry）→ `YAML PARSE PASSED`，EXIT 0。
- node-graph closure assertion：`unresolved: []`、`CLOSURE OK`，EXIT 0。断言同时确认新键 `identical_post_cross_check_blocking_rerun`（R3-C1）与 `serial_unit_fallback`（R3-C2）均存在、`state_transitions` 仍恰 8 项、所有 target 都落在 node_transitions 键集 ∪ {completed_review_1, human_escalation_required} 内。

### Non-Regression

round1-v2 / round2 已通过面均未破坏：receipt 18 required 键、三对 review-1 oneOf（grok optional_review + kimi / claude_glm embedded_read_only_review）、authorization 安全路径、`allowed_next_transitions` == receipt 非空 enum（9 值，无 `bookkeeper_decision`）、8 条 state_transitions（逐行对应 10-design 八行）、pilot_predicate 8 键精确值、P7 一次 blocking fix、disabled 表示（enabled:false + human_dispatch + null）、docs / README seal 收据命名（`runner-<seq>-seal.receipt.json`，非 adapter receipt、不入 P11 分母）。本 stage auto mode 仍 false；未 dispatch。

### 最终 git status --short

HEAD: 2a55a78223846f03d2798156ef34cff687797ad1

```
 M AGENTS.md
 M agents/registry.yaml
 M docs/model-adapters.md
 M docs/parallel-development-mode.md
 M reports/agent-runs/2026-07-auto-review-pipeline-v1/60-test-output.txt
 M reports/agent-runs/README.md
 M reports/agent-runs/_template/70-handoff.md
 M reports/agent-runs/_template/status.json
 M workflows/templates/stage-delivery.yaml
?? docs/auto-review-pipeline.md
?? schemas/auto-review-authorization.schema.json
?? schemas/runner-receipt.schema.json
```

### 风险

- 闭合级命名修正，语义无争议；T3 runner 加载器不再需要对 `post_cross_check_blocking` / `identical_post_cross_check_blocking_rerun` 做别名特判，也不必对 `serial_unit_fallback` 做路径猜测。
- 残留散文块（`review_1_fixed_transitions`、`activation_predicate`）仍与结构化版本并存 —— 按 round2 “note 可保留”规则留存，结构化版本权威，round3 未触碰。
- 未提交；记账员（Fable5）须独立复跑闭合断言与冻结套件，通过后方可 seal（delivery commit → head / fingerprint → `--phase pre-review` → 人工 Kimi review-1 packet）。

```text
本地北京时间: 2026-07-11 16:43:54 CST
下一步模型: Claude Fable 5（bookkeeper）
下一步任务: 复验 round3 闭合断言与冻结套件；通过后 seal T1 并准备人工 Kimi review-1 packet
```

---

## T2 Implementation（seal-and-validator，执行者 Claude-GLM）

### 范围与权威

- branch: `stage/2026-07-auto-review-pipeline-v1`
- T2 `base_sha`（读自 `status.json tasks[id=T2].base_sha`，从不替换移动 HEAD）: `ce9f83afeedc9ec8739548f7c316df2a79ebcd3b`
- T2 `head_sha`: None —— 执行者不 commit，head/fingerprint 由 bookkeeper 在 delivery commit 后绑定
- 起始 `tasks[id=T2].status`: `ready_for_human_dispatch`
- 先决条件核对：`auto_review_pipeline.enabled_for_this_stage=false`、`parallel_mode.enabled=false`（本 stage 走 manual 路径，不触发 auto 校验）

### 文件清单（全部在 §3 allowlist 内）

新建：

- `scripts/harness_stage_lib.py`
- `scripts/stage-seal.py`
- `scripts/tests/test_harness_stage_lib.py`
- `scripts/tests/test_stage_seal.py`
- `scripts/tests/test_validate_stage_auto_review.py`

修改：

- `scripts/validate-stage.py`

evidence（仅 append）：

- `reports/agent-runs/2026-07-auto-review-pipeline-v1/60-test-output.txt`
- `reports/agent-runs/2026-07-auto-review-pipeline-v1/20-implementation.md`（本节）

未创建 `conftest.py` / `__init__.py` / 独立 fixtures 模块。共享测试 helper（`make_temp_repo`、`VALID_AUTH`、`VALID_RECEIPT`、`REVIEW_1_VALID_RECEIPTS`）定义在 `test_harness_stage_lib.py`，由两个同级测试模块 import。

### §5.1–5.4 完成状态

- **§5.1 `harness_stage_lib.py`**：DONE。公开 API 全部实现且 stdlib-only：`compute_diff_fingerprint`（与历史 validator 实现字节等价）、`capture_code_scope_patch` / `patches_byte_equal`、`atomic_write_json` / `load_json`、`PROVIDER_IDENTITIES`（validator 历史 `PROVIDER_IDENTITIES` 的超集，含 `gemini→google`、`claude_fable5→anthropic`）、`is_safe_repo_relative_path` / `resolve_safe_path`、`parse_iso8601` / `is_iso8601`、`validate_authorization_doc` / `validate_receipt_doc`（覆盖两 schema 全约束面 + cross-field 语义：`call_budget.after==before-1`、review_1 三对 oneOf、`next_transition` 九值+null、rework const 3、auto ≤ 2、invalid-JSON const 2、`auto_high_end_dispatch_allowed` const false、`authorized_by` const human）。无 workflow 判断/模型路由；不 import `jsonschema` / `yaml`。
- **§5.2 `stage-seal.py`**：DONE。九步协议（含第 3 步 post-cross-check blocking 验证与 evidence 排除输入）+ 三类崩溃恢复 fail-closed。seal receipt `runner-<seq>-seal.receipt.json`，`kind="seal"`、`schema_version=1`，**非** runner-receipt（不走 `schemas/runner-receipt.schema.json`、无 `adapter`/`node`、不计入 P11 adapter-call 分母）——在文件 docstring 与测试中写明。本 stage 不对自身 seal（交付物为代码+测试）。
- **§5.3 `validate-stage.py`**：DONE。`compute_diff_fingerprint` 委托共享库（单一实现路径）；新增 auto 模式校验（仅 `auto_review_enabled` 真值触发）。manual 路径零行为变化（逐 hunk 论证见下）。
- **§5.4 测试**：DONE。三文件 **78 tests 全绿**（`test_harness_stage_lib` 39 / `test_stage_seal` 17 / `test_validate_stage_auto_review` 22）。

### `validate-stage.py` 逐 hunk 修改说明（现役门文件：每处 diff 的动机 + manual 行为不变论证）

1. **imports（文件顶部）**：移除 `import hashlib`（fingerprint 委托后本文件零 `hashlib` 引用——`grep hashlib scripts/validate-stage.py` 确认无输出）；新增 `_HERE = os.path.dirname(os.path.abspath(__file__))` + `sys.path.insert(0, _HERE)` + `import harness_stage_lib as _stage_lib`（让 fingerprint 共享单一实现路径）。`os`/`sys`/`json`/`subprocess`/`re`/`pathlib` 均为原有 import，未引入第三方依赖。
   **manual 不变**：仅 import 区域调整，不改变任何现有函数的控制流或错误消息。
2. **`compute_diff_fingerprint` 委托**：函数体改为 `return _stage_lib.compute_diff_fingerprint(root, stage_dir, base_sha, head_sha)`，签名与返回形状不变（`"<head_sha>:<sha256>"`）。共享库实现与历史内联逻辑字节等价（同 git 参数序、同 `:(exclude)<stage>/status.json`、bytes 上 sha256）——由 fingerprint 双锚点回归证明。
   **manual 不变**：对相同输入返回相同字符串（双锚点 ①② 均逐字相等）；`validate_common` 的 fingerprint 重算、`validate_tasks` 的 per-task fingerprint 等所有 manual 调用点行为不变（`test_validate_stage_auto_review` 运行时调用 `mod.compute_diff_fingerprint` 全绿）。
3. **auto 校验函数**（`AUTO_RUNNER_STATES` / `AUTO_DISPATCH_MODES` / `AUTO_UNIT_KINDS` / `AUTO_TRANSITIONS` + `auto_review_enabled` + `_is_int_value` + `validate_auto_review_pipeline`）：全部为新增符号，定义在 `validate_acceptance` 之后、`main` 之前。`auto_review_enabled` 仅当 `auto_review_pipeline.enabled` truthy 返回 True（缺失 / `false` / 仅 `enabled_for_this_stage` → False）。
   **manual 不变**：这些符号在 `auto_review_enabled(status_doc)==False` 时从不被 `main` 调用，对 legacy status 无任何代码路径触及。
4. **`main()` 调用**：在 `if args.phase == "pre-accept": errors.extend(validate_acceptance(...))` 之后插入 `if auto_review_enabled(status_doc): errors.extend(validate_auto_review_pipeline(root, stage_dir, status_doc, args.phase))`。
   **manual 不变**：守卫 `auto_review_enabled(status_doc)` 对所有无 enabled auto 字段的 status 返回 False（manual 回归矩阵 4 个 fixture + 本 stage 真实 status 快照已证明），故 legacy/manual status 的 `main` 控制流与错误集合逐字节不变。

### `AUTO_TRANSITIONS` 与 workflow 一致性核对

`workflows/templates/stage-delivery.yaml` 的 `auto_review_pipeline.executable_contract.state_transitions` 共 **8 个 transition id**：

- `resume_on_new_authorization` 的 `event` 为 `one_of: [new_human_authorization, superseding_human_authorization]`
- `terminal_escalation` 的 `event` 为 `one_of: [cap_exhausted, timeout, budget_exhausted, unroutable_fix, tip_once_grok_failure]`

展开 `one_of` 后得 **13 个 (from_dm, from_rs, to_dm, to_rs, event) 五元组**，与 `validate-stage.py` 中 `AUTO_TRANSITIONS` 集合逐元相等（已逐行对照）。`mode_history` 每项必须在集合内，否则 fail-closed。

### fingerprint 回归双锚点（实际结果）

- **锚点①（本 stage T1 sealed range）**：base `a385c7ad77da1611c6e952b2219aee56b49f442f` → head `25383e86d0b10b3e8bd3e0f51254588826c9601b`，重算得 `25383e86d0b10b3e8bd3e0f51254588826c9601b:242cff3040ac66e79ce2dbb5a13dab6bf92043765884ed9f0288cf8decc80486`，与 status 记录值逐字相等。**OK**
- **锚点②（历史 accepted stage `2026-07-borrow-cost-coverage-v2`）**：base `5bdfc4b3dc6843a8e52aeb86896c735500ed137a` → head `11c3935ec859320b5dad50d31c0068993b4bd8f5`，重算得 `11c3935ec859320b5dad50d31c0068993b4bd8f5:2a73b681d0ae77f3d2d9d9eaed04f977be44dd1996a3bffef3ca8dfa52b7d401`，与该 stage status 记录值逐字相等。**OK**

### Required checks（完整原始输出见 `60-test-output.txt` 本日「T2 frozen test suite」段）

| 命令 | 结果 | EXIT |
|---|---|---|
| `python3 -m unittest discover -s scripts/tests -p 'test_*.py'` | Ran 78 tests OK | 0 |
| `python3 -m py_compile scripts/validate-stage.py scripts/harness_stage_lib.py scripts/stage-seal.py` | （无输出） | 0 |
| `scripts/validate-stage.py 2026-07-auto-review-pipeline-v1 --phase checkpoint` | STAGE VALIDATION PASSED | 0 |
| `git diff --check` | （无输出） | 0 |
| `grep -rn "formal-1" scripts` | 无匹配（预期） | 1 |

### `git status --short`

```text
 M reports/agent-runs/2026-07-auto-review-pipeline-v1/60-test-output.txt
 M scripts/validate-stage.py
?? scripts/harness_stage_lib.py
?? scripts/stage-seal.py
?? scripts/tests/
```

（无 staged；无越界路径；`?? scripts/tests/` 为三个新测试文件）

### blockers / 未解决风险 / 给 review-1 的建议关注点

- **无 blocker**。T1 契约文件（schema/docs/workflow）未发现需跨界修改的缺陷。
- **review-1 建议关注**：
  1. `compute_diff_fingerprint` 委托的字节等价性——双锚点是唯一回归网，建议独立复算 `a385c7a..25383e86` 与 `5bdfc4b3..11c3935e` 确认。
  2. `validate_auto_review_pipeline` 的 budget 单账本不变式：`auto_code_changes_used ≤ max_auto_code_changes ≤ 2 < max_stage_rework=3`，且 `auto_code_changes_used < max_stage_rework` 保留至少一次 review-2 修复机会。
  3. `AUTO_TRANSITIONS` 13 个五元组是否与 `stage-delivery.yaml` `state_transitions` 8 id（含 2 处 `one_of`）展开逐元一致（本报告已逐行对照，建议 review-1 复核 `event` 名与 from/to 状态）。
  4. `stage-seal.py` step 9 `run_validator` 在本 stage 不对自身 seal；测试以 monkeypatch 验证其调用契约（clean tree + `--phase pre-review` + stage_id），真实 pre-review 全套 manual 校验由 `test_validate_stage_auto_review.py` manual 回归矩阵 + 冻结套件覆盖。
  5. seal receipt 形状为本任务自定义（非 runner-receipt schema）；review-1 宜确认 `kind="seal"`、无 `adapter`/`node`、不计入 P11。
- **风险**：`stage-seal.py` 的 `_pathspec_matches`（authorization allowlist 边界检查）为近似 git pathspec 匹配（literal + `/**` / `/*` / 尾 `/`）；git 本身是 staging 权威，该函数仅守 seal 边界，极端 pathspec 形态可能漏判——已在 docstring 注明。
- 未 commit、未 push、未改 status/handoff/review；未 dispatch 任何模型。

```text
本地北京时间: 2026-07-11 17:55 CST
下一步模型: Claude Fable 5（bookkeeper）
下一步任务: 边界检查 → 独立复跑 T2 套件 → T2 delivery commit + 指纹 → pre-review → 准备 T2 Kimi review-1 packet
```

---

# T3 Implementation — `runner-and-integration`（claude_glm, fresh bounded session）

- **Branch**: `stage/2026-07-auto-review-pipeline-v1`
- **T3 base_sha**（读自 `status.json tasks[id=T3].base_sha`，非移动 HEAD）:
  `fff4e1406fb3b340532e10b0ee88661c722b82f4`
- **dispatch 前置核对**: branch ✅、`tasks[id=T3].status=ready_for_human_dispatch` ✅、
  `auto_review_pipeline.enabled_for_this_stage=false` ✅、
  `parallel_mode.enabled=false` ✅。

## 1. 文件清单（确认 allowlist 内）

| 文件 | 动作 | 行数 |
| --- | --- | --- |
| `scripts/auto-review-runner.py` | new (stdlib-only) | 1616 |
| `scripts/tests/test_auto_review_runner.py` | new (stdlib-only) | 1018 |
| `harness-manifest.yaml` | amend（精确 +5 行） | — |
| `reports/.../60-test-output.txt` | append（共享 evidence） | — |
| `reports/.../20-implementation.md` | append（本文档） | — |

`git status --short`：
```text
 M harness-manifest.yaml
 M reports/agent-runs/2026-07-auto-review-pipeline-v1/60-test-output.txt
 M reports/agent-runs/2026-07-auto-review-pipeline-v1/20-implementation.md
?? scripts/auto-review-runner.py
?? scripts/tests/test_auto_review_runner.py
```
其余全部只读未触：`harness_stage_lib.py` / `stage-seal.py` / `validate-stage.py` /
T2 三测试 / T1 全部契约 / `status.json` / `70-handoff.md` / review / packet /
产品与 funding 路径均未改动。

## 2. §3.1 十点逐项状态 + 转移真源实现选择

| # | 契约点 | 状态 | 实现要点 |
| --- | --- | --- | --- |
| 1 | 数据加载注入点 + 单一转移真源 | ✅ | registry/workflow/status/auth/task 经构造参数注入（registry 可注入、invoker/now/blocking_runner/seal_module/seal_run_validator 可注入）；**转移真源选择：经 `importlib` 复用 `validate-stage.AUTO_TRANSITIONS`（13 个五元组），runner 内不重声明第二份矩阵**（见下「转移真源选择」）。workflow `executable_contract` 的转移语义与该集合一致由 `test_resume_from_awaiting_human_records_superseding` 等转移测试覆盖。 |
| 2 | preflight（auth 存在/手写校验/未过期/stage/branch/scope/budget/worktree/mutex） | ✅ | 复用 `lib.validate_authorization_doc`；stage/branch/scope/budget 精确匹配；exclusive worktree（branch 精确、dirty 路径全在活动 task allowlist 内）、mode mutex。任一失败：**不发起任何 adapter 调用**，置 `awaiting_human`+顶层 `paused`，且**不写 transition row**（无 `authorized→awaiting_human` 矩阵行）。8 拒绝面见下测试映射。 |
| 3 | 预算记账 | ✅ | model call 在 adapter 进程启动前记账（成功/超时/失败/invalid JSON/空输出均耗 1）；wall-clock 自 `authorized→running` 起算，**进程重启不重置 deadline**；invalid JSON 每模型最多 2 次尝试（耗 call 不耗 rework）；auto code-changing 合计 ≤2、`rework_count` 单账本。 |
| 4 | 节点循环（impl→blocking→cross-check→blocking rerun→seal→review_1） | ✅ | implementation 恰一次；blocking 失败恰一次 auto fix（记账 rework）再复测仍败则 escalation；cross-check 三情形（run/skip/unavailable）均产 artifact；identical post-cross-check blocking rerun 失败封 seal；**seal 委托 `stage-seal.py`**，runner 不重写；seal 后 rebind reload 的 unit；review_1 ACCEPT→commit verdict record。 |
| 5 | review-1 路由 | ✅ | Grok primary（`optional_review_command` 引用）；serial-only fallback `[kimi, claude_glm]`（embedded read-only 引用），**仅当候选 provider 不在单元 author+fix 集合才 eligible**；parallel tip 无 cross-pool fallback；Grok 失败/重复 invalid verdict → `human_escalation_required`+`80-*.md`；**绝不自动调 GPT/Claude**。 |
| 6 | verdict 解析（raw 落盘→枚举顶层 JSON→恰一个 schema-valid+最后非空白+stage/role/fingerprint 匹配→接受字节原样存） | ✅ | `extract_top_level_json_objects` 花括号匹配（字符串/转义感知）；`select_verdict` final-and-only 边界；手写 `validate_review_verdict_doc` 镜像 review-verdict schema；REWORK 要求 `fix_start_prompt`；verdict-record commit **不改被审 base/head/fingerprint**。 |
| 7 | receipt（只记 registry 命令引用，决不展开命令/环境/秘密） | ✅ | `runner-<seq>-<node>.receipt.json`，复用 `lib.validate_receipt_doc` 原子写；`_sync_receipt_sequence` 在 seal 后扫所有 `runner-*.receipt.json` 推进序号（seal receipt 不 bump `last_receipt_sequence`）；`next_transition` 仅出自冻结 workflow 集合。 |
| 8 | fix 路由（保留 `fix_start_prompt`+immutable owner header，按 `findings[].file`×冻结 task ownership，缺失/歧义/跨界→unroutable escalation；多 owner 串行） | ✅ | `_node_fix` 在任何 code-changing fix 后清 `snapshot_commit`/`head_sha`/`diff_fingerprint`，使 re-seal 跑完整九步；v1 多 owner fix 串行写。 |
| 9 | escalation（`80-escalation-<reason>-<UTC>.md`，`last_escalation_path`，cap/timeout/unroutable/tip-once 置顶层 `human_escalation_required`） | ✅ | `TerminalEscalation(event)` 携带 reason/UTC；status 记 `last_escalation_path`+substate `awaiting_human`+顶层 `human_escalation_required`。 |
| 10 | 停止（required 单元全 ACCEPT→`completed_review_1`，决不进 review-2；模型文本永不选命令/路径/转移；禁 `git add -A`；路径全走 `resolve_safe_path`） | ✅ | 仅 ACCEPT 终态；显式冻结清单 staging；evidence 全经 `_ev()`→`resolve_safe_path`。 |

### 转移真源实现选择（§3.1 第 1 点，二选一）

**选择 A：经 `importlib` 复用 `validate-stage.AUTO_TRANSITIONS`。**
理由：stdlib 无 yaml；`validate-stage.py` 已在 T2 内置经 review-verified的 `AUTO_TRANSITIONS`（13 个五元组）。
runner 通过 `_load_validator_module()`（`importlib.util.spec_from_file_location`）加载该模块并赋值
`AUTO_TRANSITIONS = _VALIDATOR.AUTO_TRANSITIONS`，runner 内**不重声明第二份矩阵**
（grep 确认仅 import/复用，无 hardcoded set 字面量）。`_is_allowed_transition` 直接 `in AUTO_TRANSITIONS` 判定。
这满足「单一转移真源」并避免第二份矩阵漂移；workflow `executable_contract` 与该集合的一致性由
转移测试（resume / awaiting_human 等）以行为方式断言。

## 3. manifest diff 逐行（精确 +5 行）

`git diff harness-manifest.yaml`：
```text
@@ -18,12 +18,17 @@ harness_owned:
   - scripts/install-harness.sh
   - scripts/update-project-harness.sh
   - scripts/validate-stage.py
+  - scripts/harness_stage_lib.py
+  - scripts/stage-seal.py
+  - scripts/auto-review-runner.py
+  - scripts/tests/
   - reports/agent-runs/README.md
   - reports/agent-runs/_template/
   - docs/README.md
   - docs/harness-design.md
   - docs/model-adapters.md
   - docs/parallel-development-mode.md
+  - docs/auto-review-pipeline.md
   - docs/architecture/ADR/0000-template.md
```
`git diff --stat harness-manifest.yaml` = 5 insertions, 0 deletions。`schemas/`、`workflows/`
目录条目已覆盖新 schema/workflow 内容，未动其他行。

## 4. 测试场景清单 → 测试函数映射（31 个测试函数，14 类）

| 场景（§3.3 / §5） | 类 | 测试函数 |
| --- | --- | --- |
| default-off manual status 不触发 | EnablementTests | `test_default_off_manual_status_is_noop` |
| preflight 缺 auth | PreflightRejectionTests | `test_missing_authorization_path` |
| preflight 无效 auth doc | PreflightRejectionTests | `test_invalid_authorization_doc` |
| preflight 过期 auth | PreflightRejectionTests | `test_expired_authorization` |
| preflight 错 stage | PreflightRejectionTests | `test_wrong_stage_id` |
| preflight 错 branch | PreflightRejectionTests | `test_wrong_branch` |
| preflight dirty worktree 越 allowlist | PreflightRejectionTests | `test_dirty_worktree_outside_allowlist` |
| preflight mode mutex | PreflightRejectionTests | `test_mode_mutex_with_parallel_mode` |
| preflight 失败置 paused 且无 transition row | PreflightRejectionTests | `test_preflight_failure_sets_paused_and_no_transition_row` |
| happy path 全链→completed_review_1（真实 seal） | HappyPathRealSealTests | `test_full_chain_accept_completed_review_1` |
| 第二次 blocking 失败封 seal→escalation | SecondBlockingTests | `test_second_blocking_failure_escalates` |
| evidence 目录写入不改第二次 blocking | SecondBlockingTests | `test_evidence_dir_write_does_not_change_second_pass` |
| bind mismatch fail-closed（真实 seal） | BindMismatchTests | `test_bind_mismatch_fail_closed_real_seal` |
| invalid→valid Grok ACCEPT | InvalidJsonRoutingTests | `test_invalid_then_valid_grok_accepts` |
| 重复 invalid→serial fallback eligible | InvalidJsonRoutingTests | `test_repeated_invalid_routes_to_serial_fallback` |
| blocking fix + rework 合计 ≤2 封顶 | AutoBudgetCapTests | `test_blocking_fix_plus_rework_cap_at_two` |
| parallel tip Grok 失败 escalation 无 cross-pool | ParallelTipNoFallbackTests | `test_parallel_tip_grok_failure_escalates_no_crosspool` |
| ineligible fallback（双 provider authored） | ParallelTipNoFallbackTests | `test_ineligible_fallback_both_providers_authored` |
| 多 owner fix 串行化 | MultiOwnerFixTests | `test_multi_owner_fix_dispatched_serially` |
| verdict-record commit 不改 fingerprint | VerdictRecordFingerprintTests | `test_verdict_record_commit_preserves_fingerprint` |
| receipt 无 expanded command/env/token | ReceiptHygieneTests | `test_receipts_contain_only_command_refs_no_secrets` |
| receipt call_budget after==before-1 | ReceiptHygieneTests | `test_receipt_call_budget_after_equals_before_minus_one` |
| call 启动即记（超时也记） | AccountingTimingTests | `test_call_charged_before_adapter_start_even_on_timeout` |
| wall-clock 重启不重置 deadline | AccountingTimingTests | `test_wall_clock_restart_does_not_reset_deadline` |
| wall-clock 超时 escalation | AccountingTimingTests | `test_wall_clock_expiry_escalates_timeout` |
| P3 negation pathspec 不静默匹配 | PathspecExoticFormTests | `test_negation_pathspec_does_not_silently_match` |
| P3 嵌套 glob 字面处理 | PathspecExoticFormTests | `test_nested_glob_treated_literally` |
| P3 大小写敏感字面 | PathspecExoticFormTests | `test_case_sensitive_literal` |
| P3 目录 glob 匹配 | PathspecExoticFormTests | `test_directory_glob_matches` |
| P3 parallel topology dirty 越界 fail-closed | PathspecExoticFormTests | `test_parallel_topology_dirty_path_outside_allowlist_fail_closed` |
| resume from awaiting_human 记 superseding | ResumeTransitionTests | `test_resume_from_awaiting_human_records_superseding` |

## 5. Required Checks 原始结果（冻结四命令 + formal-1 grep）

见 `60-test-output.txt`（本次 append 的 `T3 Required Checks` 段）。摘要：

| # | 命令 | exit | 结果 |
| --- | --- | --- | --- |
| 1 | `python3 -m unittest discover -s scripts/tests -p 'test_*.py'` | 0 | Ran **109 tests** in 9.805s — OK（78 既有 + 31 新增） |
| 2 | `python3 -m py_compile …{validate-stage,harness_stage_lib,stage-seal,auto-review-runner}.py` | 0 | 全部编译通过 |
| 3 | `scripts/validate-stage.py 2026-07-auto-review-pipeline-v1 --phase checkpoint` | 0 | `STAGE VALIDATION PASSED`；`status=implementing`；`diff_fingerprint=a7fd7373…:2509ae83…` |
| 4 | `git diff --check` | 0 | 无 whitespace/conflict 错误 |
| 5 | `grep -rn "formal-1" scripts harness-manifest.yaml` | 1 | 无匹配（exit 1 = 期望）——无模型内部代号泄漏 |

（committed-range `git diff --check <T3-base>..<T3-head>` 由 bookkeeper 在 delivery commit 后执行；本会话未 commit，故不产生 head。）

## 6. blockers / 风险 / review-1 建议关注点

- **blockers**：无。T1/T2 交付无缺陷需 design-amendment；全部冻结契约满足。
- **风险 / review-1 关注点**：
  1. **`AUTO_TRANSITIONS` 复用而非 workflow yaml 直解析**：runner 不自解析 workflow yaml（stdlib无yaml），改为 importlib 复用 validator 内置集合。review-1 宜确认该集合确为 workflow `executable_contract` 的真源且 13 元组完备（T2 review 已 verify）。
  2. **`_pathspec_matches`（P3 残余风险，自 T2 review 转来）**：runner 与 stage-seal 共用的近似 git pathspec 匹配（literal + `/**` / `/*` / 尾 `/`）。本次以黑盒 pathspec 边界形态测试覆盖（negation / 嵌套 glob / 大小写 / 目录 glob / parallel topology 越界——断言要么正确匹配要么 fail-closed escalation，**不允许静默漏判**）。git 本身仍是 staging 权威，该函数仅守 seal/preflight 边界。
  3. **macOS `/var`↔`/private/var` 符号链接**：`resolve_safe_path` 解析到 `/private/var`，runner 在 `__init__` 内 `resolve()` root+stage_dir 并经 `_ev()` 路由所有 evidence，规避 `relative_to` 失败；review-1 宜确认无裸路径写入 repo root。
  4. **seal receipt 序号不 bump `last_receipt_sequence`**：runner 以 `_sync_receipt_sequence()` 扫 `runner-*.receipt.json` 推进序号，避免与 seal receipt 冲突；review-1 宜确认 receipt 序列单调（impl/crosscheck/seal/review_1）。
  5. **seal 后 unit rebind**：seal/commit reload 后局部 unit 引用失效，`_node_seal` 返回刷新的 unit、`_run_unit` rebind、外层按 ID 迭代；review-1 宜确认 rework→fix→re-seal 全链无 stale 引用。
  6. **fix 后必须清 seal 字段**：`_node_fix` 清 `snapshot_commit`/`head_sha`/`diff_fingerprint`，使 re-seal 跑完整九步（stage-seal 对已 sealed 单元拒绝 re-seal）。
- **未 commit、未 push、未改 status/handoff/review/packet；未 dispatch 任何模型。**

```text
本地北京时间: 2026-07-11 19:08 CST
下一步模型: Claude Fable 5（bookkeeper）
下一步任务: 边界检查 → 独立复跑全量套件 → T3 seal → T3 Kimi review-1 packet
```

---

# T3 fix-round1 — `transition truth-source persistence test`（claude_glm, REWORK P2）

- **Branch**: `stage/2026-07-auto-review-pipeline-v1`
- **任务**: T3 fix round 1（review-1 REWORK，finding P2：persistent transition-set assertion）
- **verdict_source**: `review-1-T3-round1.verdict.json`（verdict=REWORK，model=kimi）
- **rework_charge**: 1 of 3（本 stage 首次正式 rework 计费）
- **dispatch 前置核对**: branch ✅、`tasks[id=T3].status=review_1_rework_fix_dispatch_ready` ✅、
  `auto_review_pipeline.enabled_for_this_stage=false` ✅、`parallel_mode.enabled=false` ✅。
- **reminder**: code change 使原 sealed fingerprint 失效；返回后 T3 须 RE-SEALED 再交 Kimi re-review（seal 由 bookkeeper 执行）。

## 1. Finding → Fix

| finding（review-1-T3-round1.verdict.json, required_fixes[0]） | fix |
| --- | --- |
| runner 经 importlib 复用 `validate-stage.AUTO_TRANSITIONS` 作单一转移真源（`auto-review-runner.py:91-92`），但未交付 dispatch packet §3.1 要求的「以测试断言其与 workflow 集合一致」的持久化测试。 | 新增 `TransitionTruthSourceTests.test_runner_transitions_match_workflow_state_transitions`：stdlib-only 受限行解析器解析 `workflows/templates/stage-delivery.yaml` 的 `auto_review_pipeline.executable_contract.state_transitions`，展开为 13 五元组集合，`assertEqual` 锚定 `RUNNER.AUTO_TRANSITIONS`。 |

## 2. 文件边界（确认 allowlist 内）

| 文件 | 动作 | 改动 |
| --- | --- | --- |
| `scripts/tests/test_auto_review_runner.py` | amend | `import re`（+1）；新增 `WORKFLOW_TEMPLATE`/3 个 regex 常量；新增 `_parse_workflow_state_transitions()` 受限行解析器；新增 `TransitionTruthSourceTests` 类（1 测试方法） |

**其余全部只读未触**：`auto-review-runner.py`、`validate-stage.py`、`harness_stage_lib.py`、
`stage-seal.py`、T2 三测试、全部 T1 契约（含 workflow YAML）、`harness-manifest.yaml`、
`status.json`/`70-handoff.md`/review/packet、产品与 funding 路径。

`git status --short`：
```text
 M reports/agent-runs/2026-07-auto-review-pipeline-v1/20-implementation.md
 M reports/agent-runs/2026-07-auto-review-pipeline-v1/60-test-output.txt
 M scripts/tests/test_auto_review_runner.py
```
（前两行是本 fix 的共享 evidence append；代码改动仅 test 文件一行。）

## 3. 实现要点

- **转移真源选择不变**：runner 仍经 importlib 复用 `validate-stage.AUTO_TRANSITIONS`（单一真源，runner 内无第二份矩阵）。本 fix 不改 runner，仅补「持久化锚定」测试，把该复用集合钉死在 workflow YAML 上。
- **stdlib-only 受限行解析器** `_parse_workflow_state_transitions(workflow_path)`：
  - 定位 `    state_transitions:`（4-space 缩进，executable_contract 下）块头；正文缩进 ≤4 即块尾。
  - 按 `      - id:`（6-space）切分 8 个 transition 条目。
  - `from:` / `to:` 内联 flow mapping `{ dispatch_mode: "...", runner_state: null|"..." }` 用受限正则提取；`null` → Python `None`。
  - `event:` 标量（`event: "x"`）→ 单事件；`event:` 块 + `one_of: [...]` flow 序列 → 逐项展开为多元组。
  - 五元组顺序 `(from_dispatch_mode, from_runner_state, to_dispatch_mode, to_runner_state, event)`，与 validator `AUTO_TRANSITIONS` 完全一致。
- **fail-closed**：缺块头 / 无条目 / from/to 不可解析 / event 块缺 one_of / one_of 空 / 标量 event 形态异常均 `raise AssertionError`，使 workflow 漂移在此暴露而非静默通过。**测试中无第二份硬编码矩阵**——集合完全由 workflow YAML 动态解析得出。
- **非平凡性已验证**：解析器对真实 workflow 产出恰 13 元组且 `== RUNNER.AUTO_TRANSITIONS`；对缺块头/悬空 event 的合成畸形输入均抛 AssertionError（见 `60-test-output.txt` fail-closed sanity 段）。

## 4. Required Checks 原始结果（packet 验证命令）

见 `60-test-output.txt`（本次 append 的 `T3 fix-round1 Required Checks` 段）。摘要：

| # | 命令 | exit | 结果 |
| --- | --- | --- | --- |
| 1 | `python3 -m unittest scripts.tests.test_auto_review_runner.TransitionTruthSourceTests` | 0 | Ran **1 test** — OK（新测试通过） |
| 2 | `python3 -m unittest discover -s scripts/tests -p 'test_*.py'` | 0 | Ran **110 tests**（109→110）— OK |
| 3 | `python3 -m py_compile …{validate-stage,harness_stage_lib,stage-seal,auto-review-runner}.py` | 0 | 全编译通过 |
| 4 | `scripts/validate-stage.py 2026-07-auto-review-pipeline-v1 --phase checkpoint` | 0 | `STAGE VALIDATION PASSED`；`status=fixing`；`diff_fingerprint=d42e031d…:2deb5e9e…`（test 改动反映入指纹） |
| 5 | `git diff --check` | 0 | 无 whitespace/conflict 错误 |

## 5. blockers / 风险 / review-1 建议关注点

- **blockers**：无。finding P2 完全闭合；未引入新依赖（`re` 为 stdlib）。
- **风险 / review-1 关注点**：
  1. **解析器结构性假设**：受限解析器假定当前 workflow 的精确缩进 / 内联 flow-mapping 形态。这是「仅处理当前结构」的有意设计——若 workflow 编辑漂移，测试会 fail-closed。review-1 宜确认该严格性是期望行为（漂移应当被捕获）。
  2. **集合比较语义**：`set` 去重——若 workflow 出现重复 (from,to,event) 致元组 <13，`assertEqual` vs 13 元素 `AUTO_TRANSITIONS` 会失败（正确 fail-closed）。
  3. **单一真源仍为 validator**：本测试把 runner 复用集合 ↔ workflow YAML 双向锚定；validator `AUTO_TRANSITIONS` 本身作为 T2 review-verified 的 frozen 真源不变。runner 未改，其 importlib 复用路径（`auto-review-runner.py:91-92`）保持。
- **未 commit、未 push、未改 status/handoff/review/packet；未 dispatch 任何模型。**

```text
本地北京时间: 2026-07-11 20:15 CST
下一步模型: Kimi（T3 review-1 re-run）
下一步任务: bookkeeper 边界检查 → RE-SEAL T3（code change 失效旧指纹）→ 复跑本 review-1 packet 验证 fix
```

---

## Review-2 Fix Round 1（Claude-GLM，控制面修复 F2–F7）

执行 packet：`task-review2-fix-round1-claude-glm.prompt.md`（rework 第 2/3 次正式计费）。
权威依据：`50-review-2-gpt-5.6-sol.md` §Findings（行号）+ `51-review-2-panel-disposition.md`
（bookkeeper 3/3 复现）。本节只加机械路由，不改写 findings；F1（override 证据形式）
与 P2（status 残段）不在本 packet（bookkeeper 另行处理）。

### disposition（逐项）

- **F2 — authorization 实绑定**（sol P1 #2）：`scripts/auto-review-runner.py`
  - preflight 现要求 authorization artifact 与 approval receipt 均 **committed**
    （`_git_path_is_committed` = `git cat-file -e HEAD:<rel>`）且工作树不 dirty
    覆盖（`_git_path_is_dirty`）。
  - `_verify_authorization_binding`：live 单元 id ⊆ `scope.task_ids`（超出 fail-closed）；
    单元 `code_pathspecs` 必须命中 `allowed_pathspecs` 且不命中 `forbidden_pathspecs`；
    live topology 非空时与 `scope.topology` 精确比对。
  - 运行时上限改用 `_auth_or_status_budget`：authorization budget 优先，status 仅累计。
- **F3 — 生产 registry 命令兼容**（sol P1 #3）：`scripts/auto-review-runner.py`
  - `_unescape_yaml_scalar`：双引号 `\"`→`"`、`\\`→`\`；单引号 `''`→`'`。
  - `_default_invoke` 替换 `<prompt-file>`/`<repo>`（保留 `@PROMPT@`/`@REPO@` 向后兼容）。
- **F4 — verdict schema 对齐 + 字节保真**（sol P1 #4）：`scripts/auto-review-runner.py`
  - `validate_review_verdict_doc` 拒未知顶层字段（`VERDICT_ALLOWED_TOP`）、校验
    `required_fixes`/`residual_risks` 为字符串列表、finding 约束（unknown 字段/severity/line）。
  - `_store_verdict` 写**被接受的原始字节 span**（`raw_text[span[0]:span[1]]`），不再
    `json.dumps` 重序列化；缺 span → `RunnerError` fail-closed。
- **F5 — 单账本联动 + expires_at 每步**（sol P1 #5）：`scripts/auto-review-runner.py`
  - `_charge_auto_change` 同时递增顶层 `rework_count`（单账本）并校验
    `rework_count ≤ max_stage_rework`，否则 `TerminalEscalation("budget_exhausted")`。
  - `_check_authorization_expiry`：非 null `expires_at` 在每次 model call 与每次
    verdict-record commit 前重查（验收 28）。
- **F6 — exclusive lock + H_snapshot 崩溃窗**（sol P1 #6）：
  - runner 锁：`scripts/auto-review-runner.py` `_acquire_runner_lock`（git 元数据下
    `<git-dir>/harness-runner.lock`，`fcntl.flock LOCK_EX|LOCK_NB`，含 pid/stage/时间戳；
    占用 → `PreflightFailed("runner_lock_busy")`；`run()` try/finally 释放）。
  - seal 崩溃窗：`scripts/stage-seal.py` 新增 `_pending_marker_path`/`_write_pending_marker`/
    `_clear_pending_marker`（pending marker 含 task/base/parent_sha/预期路径）。create_snapshot
    前落 marker，H_bind 后清除；恢复路径据 marker + parent_sha 检测真实崩溃点（snapshot 已
    landed → 用 HEAD 续 bind，**绝不第二次 code commit**；未 landed → 清 stale marker 走 fresh）。
    两处恢复分支改调用 `verify_bind` 重算 bind_status（取代陈旧 "n/a"）。
- **F7 — restart 幂等 + adapter 错误停机**（sol P1 #7）：`scripts/auto-review-runner.py`
  - `run()` 拆为 `run()`+`_run_body()`：`completed_review_1` 重启 = no-op；`running` 重启 =
    resume（仅 preflight，不重授权、不重置 wall-clock）。
  - 单元循环跳过 `review_1.verdict=="ACCEPT"`，避免重派已接受单元。
  - `_node_implementation`/`_dispatch_fix`：`failure_class in (command_error, timeout)` →
    记 receipt 后 `TerminalEscalation("unroutable_fix")`，绝不带着失败结果继续 blocking/seal。

### finding → 负测试映射（每条单独可跑）

| finding | 测试类 / 函数 |
|---|---|
| F2 | `AuthorizationBindingTests`：test_unauthorized_extra_unit_fails_closed（sol T1-only vs 含 T2 反例）、test_unit_pathspec_outside_allowlist_fails_closed、test_forbidden_pathspec_hit_fails_closed（dirty forbidden path 反例）、test_uncommitted_authorization_artifact_rejected（必须 committed）、test_dirty_authorization_modification_rejected（uncommitted 修改反例）、test_runtime_caps_come_from_authorization_not_status（sol 99 calls vs 1-call 授权反例） |
| F3 | `ProductionRegistryCommandTests`（加载真实 `agents/registry.yaml`）：test_real_registry_unescapes_quoted_command_scalars、test_claude_glm_real_command_substitutes_and_unescapes、test_kimi_real_command_substitutes_and_unescapes、test_grok_real_command_substitutes_both_placeholders |
| F4 | `VerdictSchemaAndByteFidelityTests`：test_unknown_top_level_field_rejected、test_required_fixes_non_string_item_rejected、test_finding_unknown_field_rejected、test_finding_bad_severity_and_line_rejected、test_residual_risks_non_string_item_rejected、test_stored_verdict_is_accepted_source_span_byte_for_byte（非常规空白/键序 fixture，断言存盘字节 == 源 span 且 ≠ json.dumps） |
| F5 | `ReworkLedgerAndExpiryTests`：test_charge_auto_change_increments_shared_ledger、test_charge_auto_change_escalates_past_max_stage_rework、test_rework_fix_charges_shared_rework_ledger_e2e、test_authorization_expiry_rechecked_before_later_model_call（run 中途过期 → 下一次 call fail-closed） |
| F6-lock | `RunnerLockTests`：test_concurrent_runner_lock_is_exclusive |
| F6-seal | `SealCrashRecoveryTests`：test_snapshot_crash_window_recovers_without_second_code_commit（真实执行流注入崩溃：monkeypatch write_unit_and_receipt 在 commit 后 status 写前抛异常 → 第二次 seal 据 marker 恢复，仅 +1 H_bind，H_snapshot 计数仍为 1） |
| F7 | `RestartAndAdapterErrorTests`：test_restart_completed_review_1_is_noop、test_restart_running_skips_accepted_unit_no_redispatch、test_implementation_adapter_error_stops_before_blocking_and_seal、test_fix_adapter_error_stops_before_second_seal |

### 修改文件（全部在冻结 writable set 内）

- `scripts/auto-review-runner.py`（F2/F3/F4/F5/F6-lock/F7）
- `scripts/stage-seal.py`（F6 pending-snapshot marker + 恢复 bind_status 重算）
- `scripts/tests/test_auto_review_runner.py`（F2–F7 负测试；另：1 个既有测试因 F7 语义调整，见风险①）
- `scripts/tests/test_stage_seal.py`（F6 崩溃窗测试）

未改 `harness_stage_lib.py`/`validate-stage.py`/任何 T1 契约/manifest/status/handoff/review/packet。

### 命令原始结果（完整输出已 append 到 `60-test-output.txt`「Review-2 Fix Round 1」段）

- `python3 -m unittest discover -s scripts/tests -p 'test_*.py'` → **Ran 136 tests … OK**
  （110 既有 + 26 新增；既有 1 个因 F7 调整，意图保留）。
- `python3 -m py_compile …（4 文件）` → exit 0。
- `scripts/validate-stage.py 2026-07-auto-review-pipeline-v1 --phase checkpoint` →
  **STAGE VALIDATION PASSED**（committed HEAD 指纹 `4c668bb…:54186cec…` 未变；新指纹在 re-seal 阶段产生）。
- `git diff --check` → clean（exit 0）。
- `grep -rn "formal-1" scripts harness-manifest.yaml` → exit 1（无命中，符合预期）。

`git status --short`（writable-set 确认）：

```text
 M reports/agent-runs/2026-07-auto-review-pipeline-v1/60-test-output.txt   （仅 append 证据）
 M reports/agent-runs/2026-07-auto-review-pipeline-v1/20-implementation.md （仅 append 证据，即本节）
 M scripts/auto-review-runner.py
 M scripts/stage-seal.py
 M scripts/tests/test_auto_review_runner.py
 M scripts/tests/test_stage_seal.py
```

### 风险 / review-1 关注点

1. **F7 改变 implementation/fix 超时语义**：既有 `AccountingTimingTests.test_call_charged_before_adapter_start_even_on_timeout`
   原依赖「implementation 超时不停止、连续耗尽 3 次」。F7 后 implementation 超时立即停机
   （`unroutable_fix`）。已将其改为：implementation + cross-check 成功、仅 review 超时——
   既保留「超时也计费 + cap 在 3 耗尽」的测试意图，又符合 F7。review-1 宜确认该调整为正确解读。
2. **pathspec 近似匹配**：F2 沿用 lib 近似 matcher（`_pathspec_matches`）；A1 authority-order
   deferral 仍为 P3（sol §Required disposition 明列），本 packet 不处理。
3. **runner 锁为进程级 fcntl.flock**：进程持有、崩溃自动释放；跨机 worktree 锁定不在范围
   （docs 单 worktree 假设）。pending marker 为 stage dir 下 runtime-only 未跟踪文件，永不提交。
4. **rework_count 上限**：max_stage_rework=3，auto 改动上限 ≤2，故纯 auto 无法触顶；负测试
   `test_charge_auto_change_escalates_past_max_stage_rework` 设 max_stage_rework=2 以走 escalation 分支。
5. **字节保真**：`_store_verdict` 写确切源 span；缺 span → `RunnerError` fail-closed，绝不重写。

**非回归**：110 既有测试全绿（1 个因 F7 语义调整，意图保留）；`TransitionTruthSourceTests` 通过；
三对 review-1 路由、post-cross-check blocking rerun、seen-diff bind、单一 fingerprint 实现、
显式路径 git add（无 `-A`）、receipt 卫生、pilot 谓词均不变。stdlib-only / 无网络 / 无 live model 不变。
**未 commit、未 push、未改 status/handoff/review/packet；未 dispatch 任何模型。**

```text
本地北京时间: 2026-07-11 22:44 CST
下一步模型: Claude Fable 5（bookkeeper）
下一步任务: 复验 F2–F7 → re-seal（新指纹）→ Kimi re-review-1（fix 单元）→ 重回 review-2
```

---

# Review-2 Round 2 Final Fix — 七组控制面修复交付（rework 3/3，零漂移）

## 前置核对（packet §Read First 前置）
- branch `stage/2026-07-auto-review-pipeline-v1` ✓
- status 顶层 `fixing`、`rework_count`=3、`review_2.round2.verdict`=`REWORK` ✓（status 只读，未改）
- 可写集严格 4 文件 + 2 append-only；未触碰 harness_stage_lib / validate-stage / registry / schemas / workflows / manifest / status / handoff / review / packet ✓
- 未 dispatch 任何模型；未 commit；未联网；测试确定性 stdlib-only ✓

## ① FX1–FX7 逐项 disposition + 红→绿证据（G4）

### FX1 — adapter 命令 shell 安全（sol P1#1）
- **实现**：`_default_invoke` 对 `<prompt-file>`/`<repo>`/`@PROMPT@`/`@REPO@` 四个占位符均先 `shlex.quote()` 再 `.replace()`；`$()` 命令替换（claude_glm/kimi）与裸词（grok `--prompt-file`）两种上下文均合法（`$()` 内部是全新解析上下文，单引号有效）。`shell=True` 与 receipt 只记 `command_ref` 不记展开命令的契约不变。
- **测试**：`ShellSafeInvocationTests`（4）——真实 registry 字符串级 + 真实执行探针（名字含空格的 tempfile 目录）。
- **红→绿**：改 `prompt_q=str(prompt_abs)`（去 quote）→ 两执行探针红（`exit_status 1 != 0`，bare-word stdout 空）；还原 shlex.quote → exit 0。

### FX2 — seal 每 commit 前 expiry 重查（sol P1#2）
- **实现**：`stage-seal.py` `seal(..., commit_guard: Callable[[], None] | None = None)`；4 个 commit 点（fresh H_snapshot 前、fresh H_bind 前、恢复路径 create_bind 前、unbound resume create_bind 前）紧前调 guard；runner `_node_seal` 传 `commit_guard=self._check_authorization_expiry`，guard timeout 以 `TerminalEscalation` 原样上抛（不改写为 unroutable_fix）。CLI 手动路径（guard=None）不变。
- **测试**：`CommitGuardTests`（seal 2）+ `SealCommitGuardWiringTests`（runner 2）。
- **红→绿**：移除 fresh H_bind 前 guard → `test_guard_fresh_path_runs_before_each_commit_and_blocks_h_bind` 红（`SealError not raised`）；还原 → H_bind 前抛、commit 未创建。

### FX3 — marker 恢复硬化 + 孤儿 marker（sol P1#3）
- **实现**：恢复条件三分支穷尽（HEAD==parent → 清 marker 走 fresh / `HEAD^`==parent 且 `diff-tree` 路径集==`expected_paths` → 续 bind / 其余 → fail-closed `SealError` 不清 marker）；孤儿 marker（unit_is_sealed）经 `_bind_evidence_complete` 验证后清 marker 抛 already-sealed，验证不过 fail-closed 保留 marker。
- **测试**：`SealMarkerHardeningTests`（2，真实执行流注入）。
- **红→绿**：`_head_is_expected_snapshot_child` 改回 `return head != parent_sha`（任意 HEAD）→ `test_intervening_commit_after_crash_fails_closed_keeps_marker` 红（`SealError not raised`）；还原三分支 → fail-closed。

### FX4 — 锁竞争失败方零写（sol P1#4）
- **实现**：`run()` 锁失败分支零状态写——不调 `_handle_preflight_failure`、不 `_persist`、不记 transition、不写 receipt；`return RunResult(ran=False, terminal="lock_busy", reason=...)`，stderr 一行诊断。`lock_busy` 仅存于返回值/stderr，不进 status 与 workflow 状态机。
- **测试**：`RunnerLockTests.test_concurrent_runner_lock_is_exclusive`（进程内 `fcntl.flock` 先占 + 全目录逐文件 sha256 字节不变 + 无新增文件 + lock_busy 返回）。
- **阻塞点（G2）**：本测试的既有契约（旧期望 awaiting_human+升级）被 packet FX4 要求的 lock_busy+零写契约替换；按 G2 以 append blocker 记录，而非放宽既有期望值。
- **红→绿**：恢复 `_handle_preflight_failure(exc)` → 测试红（status.json 哈希 45e018…→5514f5… 漂移）；还原零写 → 字节一致。

### FX5 — running 恢复幂等（sol P1#5）
- **方案声明：案 A（fail-closed，最小改动）**。理由：案 B（node cursor）需在 unit 内持久化 `node_cursor`，经核查该字段会被 receipt/validator 契约视为未定义结构，落盘即触碰 schema/validator（只读），触发 packet 案 B 弃用条件（"需契约文件变更即放弃案 B 改走案 A 并 append blocker"）。
- **实现**：`_unit_has_started_receipts` 扫描 `runner-*.receipt.json`，单元存在 `implementation`/`embedded_cross_check`/`fix` 节点 receipt 即"已开始未完成"；`_run_body` resume 循环对非 ACCEPT 且 started 的单元抛 `RecoverableFallback("resume_unverifiable_unit", ...)`（走既有 recoverable transition，无新转换）；干净单元（零 receipt）正常从头执行。
- **测试**：`ResumeIdempotencyTests`（6：五崩溃边界 + 干净单元正向）。
- **红→绿**：`if False and self._unit_has_started_receipts` 禁用 fail-closed → 5 边界测试红（terminal 漂移 awaiting_human→human_escalation_required）；还原 → fail-closed。

### FX6 — authorization 精确绑定（sol P2#1）
- **实现**：task_ids 双向集合相等（`_verify_authorization_binding` 加 `auth - live` → `scope_mismatch` `authorized_but_absent`，原 `live - auth` 不变）；topology 双向值相等（既有）；allowed/forbidden pathspecs（既有）；**budget 数值等值限 ledger caps**（`max_stage_rework`/`max_auto_code_changes`，auth vs status `auto_review_pipeline.budgets`）。
- **阻塞点（FX6 budget 范围）**：sol 要求"frozen contract budget 字段精确等值"，但既有 frozen 契约测试 `test_runtime_caps_come_from_authorization_not_status`（round-1 F2）明确主张 **runtime caps（max_model_calls / wall_clock_seconds）权威是 auth，status 是可篡改镜像**。FX6 若绑定 runtime caps 的 auth-status 等值会破坏该契约，而 G2 禁止改既有测试（FX6 不在例外）。按 packet 冲突解决规则（G2 + "以 sol 为准并 append blocker，不得自行取舍"），budget 等值限于 **ledger caps**（frozen rework/auto-change 账本，status 与 auth 必须共享），runtime caps 不绑定。`invalid_json_max_attempts_per_model`（auth-only）、`*_used`（status-only）均排除。
- **阻塞点（max_stage_rework）**：schema `const 3`，auth 携带非 3 值在 preflight 早期被 `validate_authorization_doc` 拒绝（`authorization_invalid`），runtime budget_mismatch 分支对该字段不可达——schema-level frozen 已保证等值。
- **测试**：`AuthorizationExactBindTests`（7：authorized_but_absent / topology / allowed / forbidden / max_stage_rework[schema-level] / runtime_cap_not_bound / max_auto_code_changes[ledger]）。
- **红→绿**：`if False and absent` 禁用双向 → `test_authorized_but_absent_task_fails_closed` 红；`if False and budgets...` 禁用 ledger bind → `test_max_auto_code_changes_divergence_fails_closed` 红。

### FX7 — 账本预检后更新（sol P2#2）
- **实现**：`_charge_auto_change` 先算 `proposed_auto`/`proposed_rework`，任一超 cap → 两个计数器均不写、直接 `TerminalEscalation`；通过后两计数器一次性同步写入。边界语义不变（`proposed > cap` ⟺ 旧 `used >= cap` / `> cap`；恰达 max 合法、超 max 拒绝）。
- **测试**：`ReworkLedgerAndExpiryTests`——既有 `test_charge_auto_change_escalates_past_max_stage_rework` 断言修正（escalation 后 `rework_count`=2、`auto_code_changes_used`=0 均保持原值，**G2 允许的唯一既有测试改动**）；新增 `test_charge_auto_change_escalation_leaves_auto_counter_unchanged`（auto cap 触发双计数器不变）+ `test_charge_auto_change_at_exact_cap_is_legal`（恰达 max 边界）。
- **红→绿**：`if False and max_rework ...` 禁用前置预检 → `test_charge_auto_change_escalates_past_max_stage_rework` 红（`TerminalEscalation not raised`）；还原 → 抛。

## ② FX5 方案声明
**案 A（fail-closed）**。理由见 FX5：案 B node cursor 落盘需 schema/validator 契约扩展（只读），触发 packet 案 B 弃用条件。

## ③ FX→测试函数映射表

| FX | 测试类 | 测试函数 |
|----|--------|----------|
| FX1 | ShellSafeInvocationTests | test_real_registry_paths_with_spaces_and_metachars_are_shell_quoted; test_bare_word_grok_path_is_one_shlex_token; test_execution_probe_cmdsub_context_space_in_path; test_execution_probe_bare_word_context_space_in_path |
| FX2 | CommitGuardTests (seal) | test_guard_fresh_path_runs_before_each_commit_and_blocks_h_bind; test_guard_blocks_recovery_bind_on_unbound_resume |
| FX2 | SealCommitGuardWiringTests (runner) | test_node_seal_passes_expiry_check_as_commit_guard; test_node_seal_propagates_guard_timeout_unchanged |
| FX3 | SealMarkerHardeningTests | test_intervening_commit_after_crash_fails_closed_keeps_marker; test_orphan_marker_after_bind_is_cleared_and_already_sealed |
| FX4 | RunnerLockTests | test_concurrent_runner_lock_is_exclusive |
| FX5 | ResumeIdempotencyTests | test_resume_after_{implementation,cross_check,seal,review,fix}_crash_does_not_redispatch; test_resume_clean_unit_runs_from_scratch |
| FX6 | AuthorizationExactBindTests | test_authorized_but_absent_task_fails_closed; test_topology_divergence_fails_closed; test_allowed_pathspec_divergence_fails_closed; test_forbidden_pathspec_hit_fails_closed; test_max_stage_rework_divergence_fails_closed; test_runtime_cap_divergence_is_not_bound; test_max_auto_code_changes_divergence_fails_closed |
| FX7 | ReworkLedgerAndExpiryTests | test_charge_auto_change_escalation_leaves_auto_counter_unchanged (新); test_charge_auto_change_at_exact_cap_is_legal (新); test_charge_auto_change_escalates_past_max_stage_rework (既有修正) |

## ④ 修改文件确认（writable set）
- `scripts/auto-review-runner.py`（FX1/FX2/FX4/FX5/FX6/FX7）✓
- `scripts/stage-seal.py`（FX2/FX3）✓
- `scripts/tests/test_auto_review_runner.py`（FX1/FX2/FX4/FX5/FX6/FX7 测试 + Stage helper 加 `topology` 字段以支持 FX6 topology 负测试）✓
- `scripts/tests/test_stage_seal.py`（FX2/FX3 测试）✓
- append-only：`20-implementation.md`（本段）、`60-test-output.txt` ✓
- **未触碰**：harness_stage_lib.py / validate-stage.py / agents/registry.yaml / schemas / workflows / manifest / status.json / 70-handoff.md / review reports / packet ✓

## ⑤ 全部命令原始结果
见 `60-test-output.txt`「Review-2 Round 2 Final Fix」段：全套件 **Ran 161 tests — OK**；`py_compile` OK；`validate-stage --phase checkpoint` **PASSED**；`git diff --check` exit 0；`grep -rn "formal-1" scripts harness-manifest.yaml` exit 1；FX 各测试类单独跑全绿；G4 破坏性验证逐项红记录（FX1–FX7）。

## ⑥ git status --short
```
 M reports/agent-runs/2026-07-auto-review-pipeline-v1/20-implementation.md
 M reports/agent-runs/2026-07-auto-review-pipeline-v1/60-test-output.txt
 M scripts/auto-review-runner.py
 M scripts/stage-seal.py
 M scripts/tests/test_auto_review_runner.py
 M scripts/tests/test_stage_seal.py
```
全部在 writable（4）+ append-only（2）集内，无越界。

## ⑦ 风险与 human_escalation 路径
残留 append 阻塞点 3 处（均按 packet 规则 append、未自行取舍、未 fix-forward）：
1. **FX4**：既有 `test_concurrent_runner_lock_is_exclusive` 契约被 packet FX4 要求替换（lock_busy+零写），按 G2 以 blocker 记录而非放宽既有期望值。
2. **FX6 budget 范围**：runtime caps（max_model_calls/wall_clock_seconds）的 auth-status 等值与既有 frozen 契约 `caps come from authorization not status` 冲突；budget 等值限于 ledger caps，runtime caps 不绑定。
3. **FX6 max_stage_rework**：schema `const 3` 使 runtime budget_mismatch 对该字段不可达（schema-level frozen 保证等值）。

上述均为 packet 要求与既有契约/schema 的客观边界，**非代码缺陷**；全套件 161 绿、validate-stage checkpoint PASSED、文件边界精确、破坏性验证逐项成立。bookkeeper（Fable 5）复验时若认定任一阻塞点需放宽（如改 registry/schema/既有契约），即走 `human_escalation_required`。**若本次交付后仍残留任何 required code-changing finding，本 stage 直接 `human_escalation_required`**（packet rework 3/3 终格约束）。

```text
本地北京时间: 2026-07-12 01:40 CST
下一步模型: Claude Fable 5（bookkeeper）
下一步任务: 复验 FX1–FX7（含逐项破坏性验证）→ re-seal（新指纹）→ 正式 re-review-1 → review-2 round 3
```

---

# T4 Serial-Only v1 Slimming

> **Authority（活动文档，冻结）**：`16-serial-v1-slimming-design.md`、`12-serial-v1-slimming-development-breakdown-codex.md`、`54-p8-wall-clock-withdrawal-operator-decision.md`、`15-p8-wall-clock-withdrawal-design-amendment.md`。
> **Provider**：`claude_glm`（GLM-5.2，`zhipu_glm`）。
> **Scope（精简而非重构）**：`rework_count` 保持为 3。不删除/放宽 FX1–FX7；移除的运行期行为一律由新的契约/正面测试替换；无 v2/兼容性/可选并行/第二超时协议；不改 `fingerprint`/`seen-diff`/`seal transactions`/`receipt byte fidelity`/`provider isolation`/`review-2`/`merge gates`。
> **边界**：仅 stdlib；仅触碰 Exact Writable Set + 2 个追加证据文件（`20-implementation.md`、`60-test-output.txt`）；未改 `status.json`/`handoff`/`history`/`review`/`verdict`/`packet`，未改 `scripts/stage-seal.py` 与 `scripts/tests/test_stage_seal.py`（只读），未触碰 `backend/**|frontend/**|schemas/api/**|docs/product/**|docs/api/**` 与 `docs/harness-design.md`。无模型分发、无 commit、无 push、无网络。

## A. 完成定义对照

| 完成定义项 | 状态 | 证据 |
|---|---|---|
| 在 `20-implementation.md` 追加 `T4 Serial-Only v1 Slimming`，逐文件列出变更 | 本节 §B | — |
| removed/kept contract | 本节 §C | schema `required` 现为 12 字段；`budgets.additionalProperties:false`/`scope.additionalProperties:false`/顶层 `additionalProperties:false` 三层锁定 |
| 测试映射 | 本节 §D | 163 项通过 |
| 风险 | 本节 §F | — |
| git status | 本节 §G | 17 M（16 可写 + `60-test-output.txt`），无未追踪、无产品路径、未触碰 stage-seal/test_stage_seal/status.json |
| `60-test-output.txt` 追加 breakdown 全部 required commands 原始输出 | 已追加（72 行） | `60-test-output.txt` §T4 |
| 工作树仅 = exact writable set + 2 append evidence 文件 | §G | 满足 |

## B. 逐文件变更（16 可写 + `60-test-output.txt` 证据；`20-implementation.md` 本证据）

### WP-A 文档（6）

1. **`AGENTS.md`** (+43)：新增"启动阅读预算"段（冷 `history/`，启动仅读活动 workflow/`status.json`/`70-handoff.md`/`status.current_inputs`）。Auto v1 声明为"可选的、默认关闭的、仅串行的"。拓扑段"表达串行/并行拓扑" → "v1 仅串行：固定 Grok 主路径 + 合格串行 Kimi/GLM 回退路径运行单个 `task` 审查单元"。升级名"即时提示升级" → "回退耗尽升级"（`tip_once_grok_failure` 重定义为"Grok 主路径 + 串行回退耗尽"）。
2. **`docs/auto-review-pipeline.md`** (±131，净 −66)：review-unit 收紧为 `task`-only；认证要点改为"适配器授权固定在 workflow/registry，仅携带 2 个可配置上限 `max_model_calls`/`max_auto_code_changes`"；预算 JSON 仅使用量（`model_calls_used`/`auto_code_changes_used`）；新增"预算与全局不变量"段（`MAX_STAGE_REWORK=3`、`INVALID_JSON_MAX_ATTEMPTS=2`、按适配器超时为全局 registry/workflow 不变量，非认证字段）；§6 工作树改为"排他性 runner worktree"，删除并行拓扑段与集成单元；required-attempt 规则删除并行/双所有者；主/回退段删除并行提示并改写 `tip_once_grok_failure`；3 处"tip-once Grok 失败"统一为"Grok 串行回退耗尽"（含 1 处跨行残留）；冻结决策表 D2/D5/D7/P8 同步更新。
3. **`docs/model-adapters.md`** (±26)："阶段超时" → "注册的每次调用超时（`grok.optional_review_timeout_seconds`，900s）"；"`auto_high_end_dispatch_allowed` is always false" → "高端（GPT/Claude）分发按 workflow 策略固定为不存在（不携带每授权标志）"；删除"并行提示没有合格的跨池回退"。
4. **`docs/parallel-development-mode.md`** (±4，中文)：互斥锁段"auto mode 在自身的 authorization/review-unit 合同内表达 serial/parallel topology" → "auto mode 在 v1 是 serial-only，在自身的 authorization/review-unit 合同内运行单一 `task` 单元"。（保留：`auto_review_pipeline.enabled` 与 `parallel_mode.enabled` 互斥的冻结 P4 描述。）
5. **`reports/agent-runs/README.md`** (+14)：目录树加入 `history/` 条目；新增"History And Active Context"段（冷存储语义：启动不递归扫描，历史 raw 仅在被显式点名时读取）。
6. **`reports/agent-runs/_template/70-handoff.md`** (+5)：handoff 角色描述加入"active handoff context，启动与 `status.json`/活动 workflow 一并读取，不读 `history/`"。

### WP-B schemas（2）

7. **`schemas/auto-review-authorization.schema.json`** (±70，净 −66)：`required`/`properties` 收敛为 12 字段（`schema_version`/`contract_version`/`stage_id`/`stage_branch`/`authorized_by`/`approval_evidence_path`/`approval_recorded_by`/`authorized_at`/`expires_at`/`scope`/`budgets`/`supersedes`）。移除 `authorized`、`allowed_adapters`、`review_1_provider`、`auto_high_end_dispatch_allowed`、`scope.topology`、`wall_clock_seconds`、`max_stage_rework`、`invalid_json_max_attempts_per_model`。`scope` 收敛为 `{task_ids, allowed_pathspecs, forbidden_pathspecs}`；`budgets` 收敛为 `{max_model_calls, max_auto_code_changes}`。顶层 / `scope` / `budgets` 三层 `additionalProperties:false`。`description` 改写为 v1 serial-only 契约 + fail-closed 迁移说明（陈旧字段经 `additionalProperties:false` 拒绝；v1 未 accept/merge/pilot，无兼容归一化路径）。
8. **`schemas/runner-receipt.schema.json`** (±6)：`review_unit_id` 描述"task, tip, or integration unit" → "v1 review units are task-only"；`timeout` 描述"configured stage timeout" → "adapter-specific timeout（registry `timeout_seconds`，或命令级 override 如 `grok.optional_review_timeout_seconds`）"；`review_1` 节点约束移除"parallel-tip escalation, and tip-once Grok failure" → "exhausted-route escalation"。未改字段集合与 byte 形态（receipt byte fidelity 冻结）。

### WP-C runner / validator / harness（4）

9. **`scripts/auto-review-runner.py`** (±200)：全局常量保留且仅此来源：`MAX_STAGE_REWORK=3`、`INVALID_JSON_MAX_ATTEMPTS=2`、`DEFAULT_ADAPTER_TIMEOUT_SECONDS=1800`。`_runtime_cap` 仅读认证上限（`max_model_calls`/`max_auto_code_changes`），不再读 `wall_clock`/status 等值。`_charge_auto_change` 两闸门：`proposed_auto > max_auto_code_changes`（认证上限）、`proposed_rework > MAX_STAGE_REWORK`（全局不变量）。`_resolve_timeout` 优先级链：`timeout_override`（collaborator）→ 命令特定 `optional_review_timeout_seconds` → 适配器 `timeout_seconds` → `DEFAULT_ADAPTER_TIMEOUT_SECONDS`；`load_registry` 把 `timeout_seconds`/`optional_review_timeout_seconds` 解析为 `int`。`_acquire_runner_lock` 文档串与 `run()` 注释改为 FX4 语义：竞争失败者抛 `runner_lock_busy`，调用方返回 `lock_busy` RunResult + stderr，**零写**（无 transition、无 persist）。移除 `_init_wall_clock`/`_check_wall_clock` 调用面（迁移注释保留移除字段清单）。
10. **`scripts/harness_stage_lib.py`** (±50)：迁移注释块列出已移除字段；移除 `wall_clock` 生命周期注入；保留 `review_1_provider_must_differ_from_implementer_provider` 提供程序隔离（冻结规则名，非认证字段）。
11. **`scripts/validate-stage.py`** (±45)：保留 auto/parallel 互斥检查（冻结 P4，§871/§874）；预算校验改为仅使用量形态；移除已删字段的等值校验路径。
12. **`workflows/templates/stage-delivery.yaml`** (±6)：保留 `auto_review_pipeline_mutex_with_parallel_mode`（§41，互斥配置）与 `review_1_provider_must_differ_from_implementer_provider`（§390，提供程序隔离规则名）；移除已删认证字段的注入。

### WP-D tests（3）

13. **`scripts/tests/test_auto_review_runner.py`** (±213，净 −144)：`Stage.__init__` 签名精简（移除 `review_1_provider`、`wall_clock_seconds`）。认证构建改为精简 12 字段；`status.budgets` 仅使用量 `{auto_code_changes_used:0, model_calls_used:0}`。4 个 `_charge_auto_change` 测试改用 `rework_count=3`（提议 4 > `MAX_STAGE_REWORK=3` 触发升级）。删除 2 个 `wall_clock` 测试与 `test_parallel_tip_grok_failure_escalates_no_crosspool`；类 `ParallelTipNoFallbackTests` → `SerialFallbackExhaustionTests`；`test_parallel_topology_dirty_path_outside_allowlist_fail_closed` → `test_dirty_path_outside_allowlist_fail_closed`（去 `topology="parallel"`）；`test_dirty_authorization_modification_rejected` 篡改字段改为 `authorized_at`；`test_restart_running_skips_accepted_unit_no_redispatch` 去掉 `run_started_at`/`run_deadline_at`。新增 2 个超时测试：`test_resolve_timeout_uses_registry_per_adapter_values`（GLM=3000 / grok optional=900 / grok dev=1800 / kimi=1800）与 `test_timeout_override_collaborator_wins_over_registry`（override=42）。
14. **`scripts/tests/test_harness_stage_lib.py`** (±63)：新增移除字段 fail-closed 契约测试组（`test_removed_allowed_adapters_is_unknown`、`test_removed_review_1_provider_is_unknown`、`test_removed_auto_high_end_dispatch_allowed_is_unknown`、`test_removed_wall_clock_seconds_is_unknown`），替换被删行为；保留 `wall_clock`/互斥锁检查的正面契约。
15. **`scripts/tests/test_validate_stage_auto_review.py`** (±20)：`_auto_status` fixture 预算改为仅使用量；`test_max_auto_out_of_range` → `test_status_budget_max_auto_is_unknown`、`test_max_stage_rework_not_three` → `test_status_budget_max_stage_rework_is_unknown`（移除字段现为未知项，非越界）；新增 `test_rework_count_exceeds_global_invariant`（`rework_count=4` 触发拒绝）。

### 证据（2，append-only）

16. **`reports/agent-runs/2026-07-auto-review-pipeline-v1/60-test-output.txt`** (+72)：T4 全部 8 条 required commands 原始输出（CMD1–4 exit 0；CMD5–6 exit 1 预期；CMD7–8 exit 0 带可分类残留匹配）。
17. **`reports/agent-runs/2026-07-auto-review-pipeline-v1/20-implementation.md`**（本节，append-only）。

## C. Removed / Kept 合同

### C.1 Authorization contract（`schemas/auto-review-authorization.schema.json`）

- **Removed（fail-closed via `additionalProperties:false`）**：`authorized`、`allowed_adapters`、`review_1_provider`、`auto_high_end_dispatch_allowed`、`scope.topology`、`wall_clock_seconds`、`max_stage_rework`、`invalid_json_max_attempts_per_model`。
- **Kept（12 `required`）**：`schema_version`、`contract_version`、`stage_id`、`stage_branch`、`authorized_by`、`approval_evidence_path`、`approval_recorded_by`、`authorized_at`、`expires_at`、`scope`（`{task_ids, allowed_pathspecs, forbidden_pathspecs}`）、`budgets`（`{max_model_calls, max_auto_code_changes}`）、`supersedes`。
- **降格为全局不变量（不在认证中，唯一来源 `auto-review-runner.py`）**：`MAX_STAGE_REWORK=3`、`INVALID_JSON_MAX_ATTEMPTS=2`、`DEFAULT_ADAPTER_TIMEOUT_SECONDS=1800` + registry 按 adapter/call 超时。

### C.2 Status budgets（`reports/agent-runs/_template/status.json`，未改文件，仅形态）

- `auto_review_pipeline.budgets` = `null`（由 runner 写入运行期使用量）。
- 顶层 keys 不含 `topology`/`wall_clock`/`run_deadline_at`/`run_started_at`。
- 使用量字段：`model_calls_used`、`auto_code_changes_used`。caps 仅来自认证。

### C.3 Runner receipt（`schemas/runner-receipt.schema.json`）

- 字段集合与 byte 形态**未变**（receipt byte fidelity 冻结）；仅 3 处 `description` 文本迁移为 v1 serial-only / per-adapter timeout 语义。

## D. 测试映射（全套件 163 项通过）

| 被移除/收紧的行为 | 替换/正面测试 |
|---|---|
| `wall_clock` 运行期闸门 | `test_resolve_timeout_uses_registry_per_adapter_values`、`test_timeout_override_collaborator_wins_over_registry`（per-adapter 超时协议） |
| 并行 tip 跨池回退 | `test_ineligible_fallback_both_providers_authored`（串行回退耗尽 → `tip_once_grok_failure`）；类 `SerialFallbackExhaustionTests` |
| 认证 `max_stage_rework` 上限 | 全局不变量 `test_rework_count_exceeds_global_invariant`（`rework_count=4` 拒绝）+ 4 个 `_charge_auto_change` 用 `rework_count=3` |
| `status.budgets` caps 等值校验 | `test_runtime_caps_come_from_authorization_not_status`（既有，caps 来自认证） |
| 认证已删字段 | fail-closed 契约组：`test_removed_{allowed_adapters,review_1_provider,auto_high_end_dispatch_allowed,wall_clock_seconds}_is_unknown` |
| `status.budgets` 旧字段 | `test_status_budget_max_auto_is_unknown`、`test_status_budget_max_stage_rework_is_unknown`（移除字段现为未知项） |

## E. Required Commands 结果与残留分类（CMD7/CMD8 全部合法）

- **CMD1** `unittest discover`：exit 0，163 项通过。
- **CMD2** `py_compile`（validate-stage/harness_stage_lib/stage-seal/auto-review-runner）：exit 0。
- **CMD3** `validate-stage.py --phase checkpoint`：exit 0，PASSED。
- **CMD4** `git diff --check`：exit 0（无空白错误）。
- **CMD5** `rg "formal-1" scripts harness-manifest.yaml`：exit 1（预期无匹配）。
- **CMD6** 产品路径 `rg`：exit 1（预期，无 `backend|frontend|schemas/api|docs/product|docs/api` 触碰）。
- **CMD7** `wall_clock*` 残留（4 处位置，全部可分类）：`auto-review-runner.py:1050` 与 `harness_stage_lib.py:352` 为迁移注释（列出移除字段名）；`auto-review-authorization.schema.json:5` 为迁移描述（fail-closed 说明）；`test_harness_stage_lib.py:390-394` 为替换契约测试 `test_removed_wall_clock_seconds_is_unknown`。
- **CMD8** 并行/topology/认证残留（全部可分类）：
  - **互斥锁（冻结 P4，保留）**：`AGENTS.md:395`、`parallel-development-mode.md:339/344`、`stage-delivery.yaml:41`、`validate-stage.py:871/874`。
  - **提供程序隔离规则名（非认证字段）**：`stage-delivery.yaml:390`、`registry.yaml:506`（`review_1_provider_must_differ_from_implementer_provider`）。
  - **迁移描述/注释**：`auto-review-authorization.schema.json:5`、`auto-review-pipeline.md:74/75`、`harness_stage_lib.py:350/351`。
  - **替换契约测试**：`test_harness_stage_lib.py:366-382`（3 个 `test_removed_*_is_unknown`）。
  - **历史记录（不可变）**：`docs/planning/DECISIONS.md:17`。

> 残留结论：CMD7/CMD8 所有匹配均属互斥锁规则名、提供程序隔离规则名、迁移说明、替换契约测试或不可变历史，**无一为遗留运行期逻辑或被删认证字段**。

## F. 风险与残留

1. **FX4 契约收紧**：`_acquire_runner_lock` 文档串与 `run()` 注释改为 lock_busy 零写语义，与既有 `test_concurrent_runner_lock_is_exclusive` 一致，未放宽既有期望。
2. **FX6 全局不变量唯一来源**：`MAX_STAGE_REWORK=3`/`INVALID_JSON_MAX_ATTEMPTS=2` 仅存于 runner 常量；schema 不再 `const` 该字段，等值校验由 runner `proposed_rework > MAX_STAGE_REWORK` 闸门承担。
3. **超时协议替换**：wall-clock 已由 per-adapter/命令级超时协议替换（registry 驱动），无第二超时协议。
4. **可选/兼容性**：无 v2、无兼容归一化路径（v1 未 accept/merge/pilot，schema `additionalProperties:false` 直接拒绝陈旧字段）。
5. **边界**：`status.json`/`70-handoff.md`/`history/`/`review`/`verdict`/`packet`/`stage-seal.py`/`test_stage_seal.py`/`docs/harness-design.md`/产品路径均未触碰。

## G. git status

```text
 M AGENTS.md
 M agents/registry.yaml
 M docs/auto-review-pipeline.md
 M docs/model-adapters.md
 M docs/parallel-development-mode.md
 M reports/agent-runs/2026-07-auto-review-pipeline-v1/60-test-output.txt
 M reports/agent-runs/2026-07-auto-review-pipeline-v1/20-implementation.md   ← 本证据
 M reports/agent-runs/README.md
 M reports/agent-runs/_template/70-handoff.md
 M schemas/auto-review-authorization.schema.json
 M schemas/runner-receipt.schema.json
 M scripts/auto-review-runner.py
 M scripts/harness_stage_lib.py
 M scripts/tests/test_auto_review_runner.py
 M scripts/tests/test_harness_stage_lib.py
 M scripts/tests/test_validate_stage_auto_review.py
 M scripts/validate-stage.py
 M workflows/templates/stage-delivery.yaml
```

- 17 changed files, 474 insertions(+), 496 deletions(-)（不含 `60-test-output.txt` +72 与本文件；`status.json` 未改）。
- 工作树 = 16 可写 + `60-test-output.txt` + `20-implementation.md`（2 append evidence）。无未追踪文件；无产品路径；未改 `stage-seal.py`/`test_stage_seal.py`；未改 `status.json`/`70-handoff.md`/`history/`。

## H. 完成声明

完成定义全部满足：本报告逐文件列出变更（§B）、removed/kept 合同（§C）、测试映射（§D）、风险（§F）、git status（§G）；`60-test-output.txt` 已追加全部 required commands 原始输出；工作树仅含 exact writable set + 2 个 append evidence 文件。未 commit（约束）。

```text
本地北京时间: 2026-07-12 12:21 CST
下一步模型: Codex bookkeeper
下一步任务: 边界/残留/测试复验，创建 evidence commit，准备 Kimi review-1
```

---

# T4 Bookkeeper Correction Round 1（C1–C4）

> **Authority**：与 T4 同一 operator-authorized amendment；`rework_count` 仍为 3/3，本轮为 pre-review 实现完整性修正，**不消耗新 formal rework**。来源：`18-bookkeeper-inspection-T4.md`，经 `task-T4-bookkeeper-correction-round1-claude-glm.prompt.md` 执行。上方原始 T4 报告不改写；本节为 append-only。
> **Provider**：`claude_glm`（GLM-5.2，`zhipu_glm`）。
> **约束**：stdlib-only；无 dispatch/commit/push/network；未改 `status.json`/`70-handoff.md`/`history`/`review`/`verdict`/`packet`/`seal`/`stage-seal.py`/`test_stage_seal.py`/产品路径/`docs/harness-design.md`。仅编辑 T4 writable set；追加 2 个 evidence 文件。

## C1 — registry timeout fail-closed

- **runner（`scripts/auto-review-runner.py`）**：
  - 移除 `DEFAULT_ADAPTER_TIMEOUT_SECONDS = 1800` 常量及其 "Defense-in-depth fallback" 注释（不再有静默统一回退）。
  - `_resolve_timeout`：当无 `timeout_override` 且 registry 无合法正整数 timeout 时，由 `return DEFAULT_ADAPTER_TIMEOUT_SECONDS` 改为 `raise PreflightFailed("registry_timeout_invalid", {adapter, command_key, reason})`。`timeout_override`（test collaborator）路径保留，但仅为调用期观测，非生产默认，且不免除 preflight 闸门。
  - 新增 preflight 方法 `_validate_registry_timeouts()`：校验自动环实际解析的 4 个超时——`claude_glm.timeout_seconds`、`kimi.timeout_seconds`、`grok.timeout_seconds`、`grok.optional_review_timeout_seconds`——必须为正整数（非 boolean、非缺失、非零、非负），否则 `PreflightFailed("registry_timeout_invalid", {adapter, key, value})`。在 preflight budgets 校验之后调用，**在任何模型调用或 commit 之前**。
- **测试（`scripts/tests/test_auto_review_runner.py`）**：
  - 新增 `RegistryTimeoutPreflightTests`（4）：`test_preflight_rejects_missing_adapter_timeout`（删 claude_glm timeout）、`test_preflight_rejects_boolean_timeout`（grok optional=True）、`test_preflight_rejects_zero_timeout`（kimi=0）、`test_resolve_timeout_raises_when_registry_missing_and_no_override`（defense-in-depth：直接调 `_resolve_timeout` 不再返回 1800）。
  - 保留正面测试：`test_resolve_timeout_uses_registry_per_adapter_values`（GLM=3000 / grok optional=900 / grok dev=1800 / kimi=1800）、`test_timeout_override_collaborator_wins_over_registry`（override=42）。
  - fixture 对齐：`make_runner` 合成 registry 与 FX1 probe registry 现携带 `timeout_seconds`（probe=30），使 preflight/`_resolve_timeout` 能找到合法值（非放宽期望，而是使合成 fixture 满足"timeout 必填"新合同；FX1 shell-safety 断言不变）。

## C2 — runner task-only preflight

- **runner**：新增 preflight 方法 `_validate_unit_kinds()`：任何 `kind != "task"` 的 review unit 在 preflight 抛 `PreflightFailed("non_task_unit", {unit, kind})`，在 `_verify_authorization_binding` **之前**调用。这是 runner 自身的 fail-closed 闸门，**不依赖操作者先单独运行 `validate-stage.py`**。
- **测试**：新增 `RunnerTaskOnlyPreflightTests.test_preflight_rejects_non_task_unit`（`extra_unit_fields={"kind": "tip"}` → `non_task_unit`，detail.kind=="tip"）。

## C3 — remove live tip event semantics

- 事件 `tip_once_grok_failure` → `review_1_fallback_exhausted`，活跃状态机/运行期代码/规范一致改名（共 8 处活跃匹配，E10 已验证）：
  - `scripts/auto-review-runner.py`：`TERMINAL_ESCALATION_EVENTS`、`TerminalEscalation` docstring、3 处 `raise TerminalEscalation(...)` 站点（`_run_unit` 非接受升级、`_node_review_1` 无合格回退、串行回退再失败）。
  - `scripts/validate-stage.py`：`AUTO_TRANSITIONS` 该 event 元组。
  - `workflows/templates/stage-delivery.yaml`：`state_transitions.terminal_escalation.one_of` + `node_transitions.review_1` 映射。
  - `docs/auto-review-pipeline.md`：§10 Primary and fallback。
- **保留相同 fail-closed escalation 路线**（`running → awaiting_human` / top-level `human_escalation_required`），**无兼容别名、无第二协议**。`test_runner_transitions_match_workflow_state_transitions` 两端同步改名，保持绿色。
- 测试注释（`SerialFallbackExhaustionTests` 段头）同步改名。
- **migration/deferred 描述保留**（任务允许）：`AGENTS.md` "parallel tips … deferred"、`docs/auto-review-pipeline.md` §6 "parallel-tip routing … deferred"、runner 注释 "no parallel-tip branch"——均说明 tip/integration 已 deferred，非活跃语义。E9 已确认活跃 `tip_once_grok_failure` 残留为 0。

## C4 — docs cleanup

- `docs/auto-review-pipeline.md` 授权 supersession 规则："Any change to scope, adapters, budgets, or expiry" → "Any change to scope, budgets, or expiry"（adapter 权威已不在授权内）。
- 串行步骤删除冗余 "2. implementer writes allowed paths"（实现写入由 implementation node + 认证 `allowed_pathspecs` 治理，已另行描述），后续步骤 3-9 重编号为 2-8。

## Evidence（追加至 `60-test-output.txt` §T4 Correction Round 1）

| 项 | 结果 |
|---|---|
| E1 全套件 | 168 tests, OK（+5 新测试：4 C1 + 1 C2） |
| E2 py_compile（runner/validator/harness/seal + 3 test 模块） | exit 0 |
| E3 checkpoint validator | STAGE VALIDATION PASSED |
| E4 git diff --check | exit 0 |
| E5 修正后的未提交工作树产品路径扫描（`git diff --name-only`，非 `54ce1c8..HEAD`） | exit 1（无产品路径；修正 inspection 指出的 CMD6 缺陷） |
| E6 C1 timeout missing/boolean/zero preflight + resolve_timeout defense | 4 tests, OK |
| E7 C1 正面 timeout 测试（3000/1800/900 + override） | 2 tests, OK |
| E8 C2 non-task runner rejection | 1 test, OK |
| E9 活跃 `tip_once_grok_failure` 残留扫描 | exit 1（运行期/规范 0 匹配） |
| E10 `review_1_fallback_exhausted` 跨 runner/validator/yaml/docs 一致 | 8 处，exit 0 |

## 边界与 git status

- 本轮 GLM 编辑 5 个文件，全部在 T4 writable set 内：
  - `scripts/auto-review-runner.py`（C1 + C2 + C3）
  - `scripts/tests/test_auto_review_runner.py`（C1 + C2 + C3 测试 + fixture timeout）
  - `scripts/validate-stage.py`（C3）
  - `workflows/templates/stage-delivery.yaml`（C3）
  - `docs/auto-review-pipeline.md`（C3 + C4）
- 追加 2 个 evidence：`20-implementation.md`（本节）、`60-test-output.txt`（§T4 Correction Round 1）。
- **GLM 未触碰**（任务允许在工作树但 GLM 不得改）：`status.json`、stage `70-handoff.md`、`18-bookkeeper-inspection-T4.md`（bookkeeper 文件）；`stage-seal.py`/`test_stage_seal.py`（只读）；产品路径。
- **⚠ 关键事实（影响工作树解读）**：checkpoint 提交 `0393580` 仅含 3 个 bookkeeper 元数据文件（`17-bookkeeper-slimming-checkpoint.md`、stage `70-handoff.md`、`status.json`）。**整个原始 T4 serial-v1 实现均处于未提交工作树状态**，并未进入 checkpoint 提交。因此 `git diff`（vs HEAD）同时包含「原始 T4 serial-v1 全量实现」+「本轮 GLM 纠错覆盖」两层，必须分区阅读，不能把全部 porcelain 归因于本轮。
- **完整 porcelain 分区（21 M + 2 ?? = 23 文件）**：
  1. **本轮 GLM 纠错（7 文件，全部在 T4 writable set / evidence set 内）**：`scripts/auto-review-runner.py`、`scripts/validate-stage.py`、`workflows/templates/stage-delivery.yaml`、`docs/auto-review-pipeline.md`、`scripts/tests/test_auto_review_runner.py`（5 correction，本轮覆盖于 T4 既改之上）+ `reports/.../20-implementation.md`、`reports/.../60-test-output.txt`（2 append evidence）。
  2. **原始 T4 serial-v1 实现（pre-existing 未提交，非本轮、非 GLM 本轮编辑）**：`AGENTS.md`、`agents/registry.yaml`、`docs/model-adapters.md`、`docs/parallel-development-mode.md`、`docs/harness-design.md`、`schemas/auto-review-authorization.schema.json`、`schemas/runner-receipt.schema.json`、`scripts/harness_stage_lib.py`、`scripts/tests/test_harness_stage_lib.py`、`scripts/tests/test_validate_stage_auto_review.py`、`reports/agent-runs/README.md`、`reports/agent-runs/_template/70-handoff.md`。其中 `README.md`/`_template/70-handoff.md` 的 diff 为「`history/` 冷存储、启动不递归读取」纪律文档（与任务"不要递归读取 history/"同源）；`schemas/*`/`harness_stage_lib.py`/两测试为 serial-v1 瘦身（移除 topology/authorized 等字段、`additionalProperties:false`、`review_1_fallback`）。
  3. **bookkeeper 文件（GLM 不得改，未改）**：stage `70-handoff.md`(M)、`status.json`(M)、`18-bookkeeper-inspection-T4.md`(??)、`task-T4-bookkeeper-correction-round1-claude-glm.prompt.md`(??)。
- **⚠ 外部模型版本 bump 提示（非 GLM、非 C1–C4）**：模型版本 bump（`grok-composer-2.5-fast`→`grok-4.5`、`gpt-5.5`→`gpt-5.6-sol`）在仓库内多处出现：`docs/harness-design.md`、`agents/registry.yaml`、`docs/model-adapters.md`、`AGENTS.md`。其中 `docs/harness-design.md` 经确认为本会话期间外部进程（user/linter）修改——GLM 从未编辑它，它不在 T4 writable set 内，按系统提示"intentional，勿回退"保留。其余三个文件**同时携带 serial-v1 内容**，GLM 本轮未触碰它们；其内部模型 bump 的 provenance（原始 T4 实现者 vs 后续外部 pass）GLM 无法在混合 diff 中干净切分，提请 bookkeeper 裁定。GLM 本轮未引入任何模型版本变更。
- **合规结论**：本轮 GLM 仅编辑第 1 类 7 文件；未引入任何未追踪文件；无产品路径（`backend/`/`frontend/`/`schemas/api/`/`docs/product/`/`docs/api/` 均 0）；未改 `stage-seal.py`/`test_stage_seal.py`；未改任何 bookkeeper 文件；未改 `docs/harness-design.md`。工作树整体符合约束（原始 T4 writable set + 2 evidence + bookkeeper 文件）。
- 全套件 168 绿、checkpoint PASSED、`git diff --check` exit 0、活跃 `tip_once_grok_failure` 残留 0、`review_1_fallback_exhausted` 8 处一致。未 commit（约束）。

```text
本地北京时间: 2026-07-12 13:03 CST
下一步模型: Codex bookkeeper
下一步任务: 复验 C1-C4，完成 evidence commit 与 Kimi review-1 packet
```

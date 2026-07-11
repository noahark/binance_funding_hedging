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

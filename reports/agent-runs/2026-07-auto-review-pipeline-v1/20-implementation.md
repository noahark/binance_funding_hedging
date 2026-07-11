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

# Implementation Report — Task H1 (Fable5 clean-room)

## Result

**PASS.** Clean-room implementation from committed baseline `2eae7bd`
(branch `stage/2026-07-harness-review-dispatch-fast-fix-v1`). No Grok source
was recovered, reused, or patched. All frozen requirements are implemented; no
requirement had to be weakened, so no BLOCKER is raised. Stopping here for the
Codex bookkeeper; formal Review-1 was not launched and no other model or
adapter was invoked.

## Changed Files (all inside Allowed Files)

- `scripts/review_artifacts.py` — **new** shared stdlib-only protocol-v1
  module + human-invoked capture CLI.
- `scripts/tests/test_review_artifacts.py` — **new** focused fixture suite
  (86 tests, includes optional `jsonschema` oracle which runs locally on
  jsonschema 4.25.1).
- `scripts/validate-stage.py` — protocol-v1 gate, phase timing, pair binding,
  identity/fingerprint cross-checks, human-operator dispatch-ready rules,
  conditional embedded review.
- `scripts/validate-all-stages.py` — user-authorized integration: the
  aggregate sweep now calls the protocol gate with ACTIVE.json evidence.
- `AGENTS.md` — actor-neutral dispatch authority, protocol-v1 hard gate,
  embedded-review opt-in, footer exemption for protocol-v1 review stdout.
- `docs/parallel-development-mode.md` — v0.5: single dispatch authority,
  embedded review opt-in, R9/R10 rewritten without model-side self-launch,
  protocol-v1 artifact names, per-round PASS|BLOCKER result.
- `workflows/templates/stage-delivery.yaml` — actor-neutral guards, protocol
  default, protocol-aware Review-1/2 writes and output contracts with an
  explicit legacy branch, opt-in embedded checkpoint node.
- `docs/model-adapters.md` — actor-neutral dispatch rule plus the
  "Review Output Capture (Protocol v1)" runbook (producer exit captured
  separately; pipefail required for any pipeline example).
- `harness-manifest.yaml` — registers `scripts/review_artifacts.py`,
  `scripts/validate-all-stages.py`, and
  `scripts/tests/test_review_artifacts.py` under `harness_owned`.
- `reports/agent-runs/_template/status.json` — protocol v1 default-on,
  `parallel_mode.embedded_review` default-off, `raw_output_path`/
  `verdict_path` fields on review records.
- This stage's `20-implementation.md` (this file; the original text
  mis-named itself `20-implementation-fable5.md` — corrected 2026-07-20 in the
  authorized follow-up below) and appended `60-test-output.txt`.

Not touched, per role boundary: `status.json`, `70-handoff.md`,
`reports/agent-runs/ACTIVE.json`, product/backend/frontend/API/sample files,
completed-stage artifacts, `schemas/review-verdict.schema.json` (no
clarification was needed; verdict meaning unchanged). Nothing was committed or
pushed.

## Key Design Decisions

1. **Canonical verdict bytes** = `json.dumps(obj, ensure_ascii=False,
   sort_keys=True, separators=(",", ":"))` in UTF-8, no surrounding bytes, no
   terminal newline. Deterministic regardless of raw key order; any byte
   difference fails (R4 fixed).
2. **Atomic no-clobber publication** uses temp file + flush + fsync +
   `os.link` — the hard link itself is the atomic no-clobber step, so there is
   no check-then-replace window (R7 fixed); temp file is always cleaned.
3. **Active-stage evidence** is `reports/agent-runs/ACTIVE.json` (explicit,
   no date heuristic). Missing protocol fails closed at dispatch-ready
   always, and at pre-review/pre-accept for the active stage; cold historical
   stages without the field stay legacy (R1 fixed). A malformed ACTIVE.json
   itself fails closed.
4. **Fingerprint semantics**: the verdict file is authoritative; the status
   review record's `model`/`verdict`/`diff_fingerprint` are derived cache and
   must equal the parsed verdict. Task pairs are additionally bound to the
   committed task fingerprint. The serial/top-level review-vs-status
   fingerprint equality stays in `validate_acceptance`, preserving RC4
   authorized-exception semantics unchanged.
5. **Review-1 isolation granularity**: task pairs isolate against that task's
   own implementer/fix author (cross-review pairs review each other by
   design); serial Review-1 and Review-2 isolate against all stage
   implementer/fix identities. Isolation uses the normalized status reviewer
   provider (`PROVIDER_IDENTITIES`), and the verdict `model` must equal the
   status-recorded reviewer model, closing the alias evasion (R5 fixed).
6. **Embedded review** requires `parallel_mode.embedded_review.enabled: true`
   plus non-empty `reason`; each enabled round requires dispatch, patch, raw
   output, integer `round`, and a non-formal `result: PASS|BLOCKER` (distinct
   from the formal verdict schema; R6 fixed). Legacy recorded entries are
   still artifact-validated without the new requirements, keeping history
   green.

## Requirement-to-Code Mapping

Prompt criteria 1–12 → implementation and proof:

1. Human-only external dispatch: `AGENTS.md` (dispatch authority paragraph +
   Hard Gates), `docs/parallel-development-mode.md` v0.5 (Phase 2, R9, R10),
   `workflows/templates/stage-delivery.yaml` (guards + implementation/
   review/embedded nodes), `docs/model-adapters.md` General Rules;
   `scripts/validate-stage.py` `validate_dispatch_ready` rejects executor
   `self` and requires `human_operator`. Tests:
   `TestDispatchReady.test_executor_self_rejected` /
   `test_executor_other_value_rejected` /
   `test_manual_user_handoff_false_rejected`;
   `TestHarnessTextContracts.test_no_surviving_self_dispatch_tokens`.
2. Embedded default-off + mandatory R4/Review-1:
   `validate_parallel_mode` (embedded conditional; r4 flag still required),
   AGENTS Hard-Gates parallel bullet, parallel-mode v0.5 Phase 2/3/4. Tests:
   `TestEmbeddedReviewConditional.test_default_off_requires_no_embedded_entries`,
   dispatch-ready default packet test.
3. Protocol default-on/live-mandatory/cold-legacy via ACTIVE.json:
   `validate_review_artifact_protocol` + `active_stage_id`;
   `_template/status.json`; this stage's status already carries v1. Tests:
   `TestProtocolResolutionAndPhaseTiming.test_missing_protocol_*`,
   `test_unknown_protocol_fails_closed_every_phase`,
   `test_active_stage_id_reads_pointer`,
   `test_malformed_active_pointer_fails_closed`.
4. Phase timing without deadlock: `require_review_1 = pre-accept or
   (pre-review and status==review_2)`; `pre-review+review_1` requires no
   pair. Tests: `test_pre_review_status_review_1_requires_no_pair`,
   `test_pre_review_status_review_2_requires_serial_pair`,
   `test_pre_accept_requires_review_2_pair`,
   `test_pre_accept_with_both_pairs_passes` (R2 fixed).
5. Raw/verdict same object + exact canonical bytes:
   `review_artifacts.load_and_parse_pair` / `canonical_verdict_bytes`.
   Tests: `TestCanonicalPairBinding` (trailing newline, leading whitespace,
   pretty-print, unsorted keys, object mismatch, fenced raw).
6. Stage containment + frozen names + positive `-retry-N`:
   `resolve_stage_local_artifact` / `match_protocol_filename`; raw and
   verdict must select the same attempt. Tests: `TestArtifactNames` (13
   cases incl. absolute/traversal/foreign-stage/subdir/narrative names,
   retry-0 and retry-01 rejected), `test_attempt_mismatch_rejected`,
   `test_retry_pair_selected_by_status_passes`.
7. Identity binding: `_protocol_pair_errors` cross-checks verdict
   `stage_id`, role (`first_reviewer` vs `final_reviewer|reality_checker`),
   model equality, recorded fingerprint, normalized provider isolation.
   Tests: `test_verdict_stage_id_mismatch_rejected`,
   `test_wrong_role_rejected`, `test_model_mismatch_rejected`,
   `test_missing_reviewer_provider_rejected`,
   `test_provider_alias_self_review_rejected` (fable5↔claude alias),
   `test_fingerprint_cache_mismatch_rejected`,
   `test_task_pair_fingerprint_must_match_task`.
8. Embedded rounds need dispatch/patch/raw/round/reason + non-formal
   PASS|BLOCKER: `validate_parallel_mode`. Tests:
   `test_enabled_requires_reason`, `test_enabled_requires_entries_at_pre_review`,
   `test_enabled_complete_round_passes`,
   `test_enabled_round_missing_result_fails`,
   `test_enabled_round_formal_verdict_value_rejected` (ACCEPT rejected as a
   round result), `test_legacy_recorded_entries_without_opt_in_still_validated`.
9. Capture helper boundary: `scripts/review_artifacts.py` — stdlib-only, no
   subprocess import, consumes an existing raw file, requires
   `--producer-exit-status` (non-zero fails, raw retained), schema sanity
   check, refuses overwrite, atomic no-clobber publish. Tests:
   `TestCaptureCLI` (7 cases) + `TestAtomicNoClobber` (3 cases incl.
   collision without damage and failed publish leaving no partial file) +
   `TestHarnessTextContracts.test_capture_helper_never_dispatches`.
10. Workflow Review-1/2 protocol-v1 pairs + JSON-only stdout, footer only in
    legacy branch: `stage-delivery.yaml` review-1/review-2 `writes` +
    `output_contract` protocol/legacy branches, session_receipts rules,
    `artifacts.review_artifact_protocol_v1` block.
11. Fixture corpus + optional `jsonschema` oracle: `schema_corpus()` covers
    every schema-v1 constraint (all required keys, types, enums, consts,
    minLength/minItems, additionalProperties at both levels, finding fields,
    line null/minimum, conditional `fix_start_prompt`);
    `TestJsonschemaOracle.test_parity` compares stdlib vs
    `Draft202012Validator` on the canonical schema file (ran, not skipped).
    All `21-bookkeeper-reconciliation.md` R1–R7 negative cases have direct
    fixtures (mapping above).
12. Manifest distribution: `harness-manifest.yaml` now ships the helper, the
    aggregate validator, and the focused tests. Test:
    `TestHarnessTextContracts.test_manifest_registers_helper_and_tests`.

`00-task.md` acceptance criteria 1–14 are covered by the same mapping
(1→#1, 2→#1, 3→#2, 4→#9, 5→#6, 6→#5/#7, 7→#10 + AGENTS footer exemption,
8→#3, 9→#4, 10→#2/#8, 11→#11, 12→#12, 13→#11 corpus + negative fixtures,
14→ docs/workflow/validator/helper/tests describe the single flow above).

## Test Evidence

Appended to `60-test-output.txt`
(`=== Fable5 clean reimplementation evidence 2026-07-20 07:05:13 CST ===`):

- `python3 scripts/tests/test_review_artifacts.py` — **Ran 86 tests … OK**
  (includes live `jsonschema` parity, all phase-timing, live-vs-cold
  protocol, canonical-byte, containment/name, identity, conditional
  embedded, and atomic collision fixtures).
- `python3 -m py_compile scripts/review_artifacts.py scripts/validate-stage.py
  scripts/validate-all-stages.py` — PASS.
- `python3 scripts/validate-stage.py 2026-07-harness-review-dispatch-fast-fix-v1
  --phase checkpoint` — PASSED; `--phase dispatch-ready` — PASSED (protocol
  v1 present on this stage).
- `python3 scripts/validate-all-stages.py --repo-root .` — 18 green,
  1 green_with_exception, 9 red over 28 stages: identical verdict counts to
  the pre-change committed baseline. Baseline compare shows **zero drift on
  all 27 historical stages**; the single ERRDRIFT is this in-flight stage
  swapping legacy narrative-file errors for protocol-pair errors (9 → 9),
  the intended migration for the protocol-introducing stage.
- `python3 scripts/test-validate-all-stages-compare.py --help` — OK; full
  sentinel run 11/11 passed.
- `git diff --check` — PASS. YAML/JSON parse of edited config files — PASS.
- Residual-token sweep: no `executor: self` / `executor:self` /
  `manual_user_handoff_allowed: false` semantics survive in AGENTS,
  parallel-mode, adapters, workflow, template, or validator; the only
  `manual_user_handoff_allowed` hit is the validator line that rejects it.

## Residual Notes For The Bookkeeper

- The `-retry-N` grammar requires N ≥ 1 without leading zeros.
- Review-2 verdict `role` accepts `final_reviewer` or `reality_checker`
  (both appear in historical evidence and the schema enum); Review-1 requires
  `first_reviewer`.
- The all-stages compare exits 1 solely because of this stage's expected
  ERRDRIFT; record it in the migration judgment when creating the evidence
  commit.
- Next step per the dispatch receipt: Codex bookkeeper reconciliation; no
  reviewer was invoked by this session.

当前 Session ID: 81560638-a8c5-456b-ad9a-68714587b413
Session ID 来源: runtime_env (CLAUDE_CODE_SESSION_ID)
原始输出路径: reports/agent-runs/2026-07-harness-review-dispatch-fast-fix-v1/20-implementation.md （原文误写为 20-implementation-fable5.md，2026-07-20 授权 follow-up 更正；见下方追加段）
本地北京时间: 2026-07-20 07:05:57 CST
下一步模型: human_operator → Codex bookkeeper
下一步任务: 按 23-implementation-fable5.prompt.md 收尾要求进行 bookkeeper 对账（R4）；不派发 Review-1

---

# Follow-up — 2026-07-20 用户授权的五项 Kimi 非阻断项（同 stage 续做）

## Scope And Authority

本节是 2026-07-20 追加的实现续做，不是新的一轮评审，也不构成合并授权。
上文（原始 clean-room 实现报告、作者身份、86 测试证据）全部保留未改，唯一
的原地更正是把误写的自引用路径 `20-implementation-fable5.md` 改为实际规范
路径 `20-implementation.md`（Changed Files 一节与页脚各一处，均带更正说明）。

授权来源：`00-task.md#Human Gates` 2026-07-20 条目 —— 用户显式把 Kimi 的五项
非阻断 follow-up 接受进本 stage，实现仍指派 Fable5。派发依据：
`34-implementation-followup-fable5.prompt.md`（`executor: human_operator`）。

边界遵守：未提交、未推送、未合并；未触碰 `status.json`、`70-handoff.md`、
`reports/agent-runs/ACTIVE.json`；未触碰产品/后端/前端/API/样本/已完成 stage
文件；未调用任何其他模型或 adapter。prompt 明确排除的三项残留设计风险
（provider alias 覆盖面、密码学溯源、可变历史比较）未实现。

## Changed Files（本次 follow-up，均在新授权范围内）

- `docs/harness-design.md` — 重写 Parallel Development Mode 段落。
- `AGENTS.md` — 收紧 dispatch-ready 硬门表述。
- `workflows/templates/stage-delivery.yaml` — 裸 review 文件名 legacy 限定。
- `scripts/validate-stage.py` — `active_stage_id()` 结构化 fail-closed。
- `scripts/tests/test_review_artifacts.py` — 新增 ACTIVE.json 形状用例，并把
  `docs/harness-design.md` 纳入残留 token 扫描列表。
- `reports/agent-runs/.../20-implementation.md` — 本节 + 自引用路径更正。
- `reports/agent-runs/.../60-test-output.txt` — 追加本轮证据段。

## Requirement-To-Code Mapping

**1. `docs/harness-design.md` 陈旧的 Parallel Development Mode 段落**
原步骤 3 教导「每个实现终端在标记 `executor: self` 时立即执行自己的
`next_dispatch`，通过 prompt 里的 adapter 命令拉起对面模型的嵌入式预审」——
这正是本 stage 要根除的模型侧自派发。改写后：步骤 1 把预写 cross-review
prompt 变为「若 stage opt-in 才同时预写」；步骤 3 整段替换为 default-off +
显式 `parallel_mode.embedded_review.enabled: true` 加非空 reason + 仅人工
操作员执行 + 任何模型会话遇到外部 `next_dispatch` 一律停下返回 packet 路径；
步骤 4 补上「永不替代已提交的正式 Review-1」；步骤 5 补上「无论嵌入式评审
开关如何，R4 对账与正式 Review-1 都保持强制」。`executor: self` 语义在本文件
已无残留（见证据段 grep exit=1）。

**2. workflow 里每处裸 `30-review-1.md` / `50-review-2.md`**
逐处审计并显式限定，未改变 legacy 行为，也未改变 validator 预期
（`validate_required_files` 仍只对非 v1 stage 追加这两个文件）：
- `artifacts.required_files` 两行：行内注释标注为 legacy-only 要求，并在上方
  说明 pre-accept 仅对无 `review_artifact_protocol` 的 stage 强制，v1 下权威
  是 `review_artifact_protocol_v1` 的 raw/verdict 对；
- `review-1.writes.legacy` / `review-2.writes.legacy`：括注 legacy 前协议叙事
  输出、v1 下非权威；
- `fix.reads`：新增一条 v1 分支（status 选定的 raw/verdict 对 +
  `fix_start_prompt`），两条裸文件降级为 legacy/兼容叙事输入；
- `review-2.requires_raw_artifacts` 的 `30-review-1.md`：同样拆成 v1 分支
  与 legacy 兼容输入两行。
`artifacts.review_artifact_protocol_v1` 注释块（第 85–86 行）本就已经写明裸
文件在 v1 下是非权威兼容叙事，保持原样。YAML 仍可解析（证据段已记录）。

**3. AGENTS dispatch-ready 硬门**
原文把「embedded pre-review prompt paths」和「failure escalation branches」与
R10、路由并列为无条件检查项，与 `validate_dispatch_ready` 的实际行为不符 ——
该函数在 `if not embedded_enabled: continue` 之后才检查嵌入式字段、
`max_rounds`、`unavailable_branch`。改写后分两句：R10 checklist、task prompt
路径、cross-review 路由、human-operator 派发字段对所有并行 stage 生效；
embedded pre-review prompt、轮次上限、失败升级分支仅在
`parallel_mode.embedded_review.enabled == true` 时适用。

**4. 实现报告自引用路径**
`Changed Files` 末条与页脚 `原始输出路径` 两处由
`20-implementation-fable5.md` 改为 `20-implementation.md`，各自带日期更正说明；
原始 PASS 结论、作者身份、设计决策、需求映射、86 测试证据一律保留。

**5. `active_stage_id()` 对结构合法但语义非法的 ACTIVE.json fail-closed**
原实现 `doc.get("active") if isinstance(doc, dict) else None` 会把标量/列表
根、缺 `active` 键、标量/列表 `active`、缺失或空白 `stage_id` 一律静默降级为
`None`——即「无活动 stage 证据」，于是活动 stage 会悄悄走 legacy 协议路径，
绕过 v1 的 missing-protocol fail-closed。改写后：文件不存在仍返回 `None`
（缺指针本就可能意味着无活动 stage 证据，此语义按 prompt 要求保留）；文件
存在则依次要求对象根、存在 `active` 键、`active` 为 `null`（返回 `None`）
或对象、且对象内 `stage_id` 为非空字符串，否则抛 `ValidationError`。
未要求任何无关可选元数据字段（`phase`/`handoff`/`updated_at`/`last_completed`
/`note` 都不参与判定）。

**6. 焦点测试**
`TestProtocolResolutionAndPhaseTiming` 新增三个测试：
- `test_missing_active_pointer_means_no_evidence` —— 缺指针返回 `None`；
- `test_structurally_invalid_active_pointer_fails_closed` —— 10 个 subTest
  覆盖标量字符串根、标量数字根、列表根、缺 `active` 键、标量 `active`、
  列表 `active`、缺 `stage_id`、非字符串 `stage_id`、空 `stage_id`、
  纯空白 `stage_id`，逐一断言抛 `ValidationError`（即浮出校验错误，而不是
  静默选中 legacy 协议路径）；
- `test_active_pointer_extra_metadata_not_required` —— 合法对象形式即使带
  额外元数据也正常返回 stage id。
两种合法形式的另一半（`active: null`）由既有
`test_active_stage_id_reads_pointer` 覆盖，非法 JSON 由既有
`test_malformed_active_pointer_fails_closed` 覆盖。另把
`docs/harness-design.md` 加入 `TestHarnessTextContracts.NORMATIVE_FILES`，
使该文件此后也受 `executor: self` / `manual_user_handoff_allowed: false`
残留 token 扫描保护（这是需求 1 的回归防线）。

## Test Evidence

全部追加在 `60-test-output.txt` 的
`=== Fable5 authorized five-item follow-up evidence 2026-07-20 11:23:27 CST ===`
段，含逐条命令与输出：

- `python3 scripts/tests/test_review_artifacts.py` — **Ran 89 tests … OK**
  （86 原有 + 3 个新 ACTIVE.json 形状测试；含 jsonschema oracle 实跑）。
- `python3 -m py_compile scripts/review_artifacts.py scripts/validate-stage.py
  scripts/validate-all-stages.py` — PASS。
- `python3 scripts/validate-stage.py 2026-07-harness-review-dispatch-fast-fix-v1
  --phase checkpoint` — STAGE VALIDATION PASSED（status=implementing）。
- `python3 scripts/validate-all-stages.py --repo-root .` — 18 green /
  1 green_with_exception / 9 red（28 stages），与提交基线的判定分布完全一致，
  说明 `active_stage_id()` 收紧未把任何冷历史 stage 推红。
- `python3 scripts/test-validate-all-stages-compare.py --repo-root .` —
  11/11 passed。
- `git diff --check` — PASS（无输出）。
- 焦点文本/YAML 检查：`docs/harness-design.md` 的自派发 token grep 退出码 1
  （无残留）；workflow 8 处裸 review 文件名全部带 legacy 限定；
  `stage-delivery.yaml` YAML 解析 OK。

## Residual Notes For The Bookkeeper

- 实现指纹已随本次改动变化，原
  `73752dbb…:7cf1d8d2…` 覆盖的评审范围不再对应当前工作树。按
  `00-task.md#Human Gates` 2026-07-20 条目，改变后的指纹需要一次全新的
  protocol-valid Review-1 与 Review-2 才能进入用户验收或合并。
- 本次未提交，工作树为脏；上述指纹重算与证据提交属 bookkeeper 职权。
- prompt 排除的三项残留设计风险仍未处理，保持在既有登记状态。

**Follow-up 结论：PASS。** 五项均已实现且有确定性测试与命令证据；无需削弱
任何冻结要求，故不提 BLOCKER。就此停下，交回 Codex bookkeeper。

当前 Session ID: 8e7ef534-4310-4033-8bca-5f17b79ce77a
Session ID 来源: runtime_env (CLAUDE_CODE_SESSION_ID)
原始输出路径: reports/agent-runs/2026-07-harness-review-dispatch-fast-fix-v1/20-implementation.md
本地北京时间: 2026-07-20 16:52:38 CST
下一步模型: human_operator → Codex bookkeeper
下一步任务: 对本次 follow-up 做 bookkeeper 对账并重算指纹；不派发 Review-1

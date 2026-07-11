# Operator Decision Table: Auto Review Pipeline

Status: **FROZEN — POST DUAL REVIEW (GPT + Fable5 ACCEPT-with-edits merged)**  
Date locked: 2026-07-11  
Branch: `docs/2026-07-auto-review-pipeline`  
Owner: operator (human)  
Recorder: Grok (final land after dual decision-table review)

This table is the **authoritative pre-stage decision set** for drafting
`00-intake.md` of Harness stage `2026-07-auto-review-pipeline-v1`.

This is **not** yet an accepted change to `AGENTS.md`, product code, or any
formal delivery `diff_fingerprint` gate.

## Purpose

Freeze the chosen auto-review pipeline scheme after:

1. Design note and multi-model design reviews  
2. Operator + Grok arbitration  
3. GPT/Codex and Claude Fable 5 **decision-table** reviews (both
   `ACCEPT-with-edits`)  
4. Merge of all accepted minimal patches into this document  

## Source chain

| Artifact | Path |
|---|---|
| Design note | `reports/follow-ups/2026-07-auto-review-pipeline-design-note.md` |
| Fable5 design review | `reports/follow-ups/2026-07-auto-review-pipeline-review-fable5.md` |
| Codex design review | `…/30-review-codex.md` |
| Fable5 divergence response | `…/31-divergence-response-fable5.md` |
| Decision table (this file, v1 draft) | prior revision under same path |
| Fable5 decision-table review | `…/41-decision-table-review-fable5.md` |
| GPT decision-table review | `…/42-decision-table-review-gpt.md` |
| Patch merge record | `…/43-decision-table-patch-merge.md` |

---

## Vocabulary (locked)

| Term | Meaning |
|---|---|
| **runner** | Deterministic, non-LLM local orchestrator; **only** automated dispatcher and mechanical writer (commit, mechanical status, validate, evidence land, adapter invoke) |
| **embedded cross-check** | Advisory cheap-model cross-read (e.g. GLM↔Kimi). **Not** formal review-1. **Not** validator `--phase pre-review` |
| **review-1** | Formal first gate (Grok under opt-in auto mode) |
| **review-2** | Final human-started high-end gate |
| **seal** | Clean commit of the **review snapshot** + write existing `diff_fingerprint` formula fields |
| **seen-diff bind** | **Patch byte-equality** gate: at cross-check, persist the exact `git diff --binary` patch for a fixed base/pathspec (**code-scope**); at seal, regenerate the same-range patch and compare **byte-for-byte**. Fail-closed on mismatch. **Do not** write this comparison as a hash/fingerprint into `status.json` or review verdicts (avoids a second fingerprint protocol / worktree-fingerprint smell) |
| **code-scope** | Diff pathspec excluding `reports/agent-runs/<stage-id>/` evidence paths for the bind check |
| **review unit** | One formal review-1 subject: a **task** range (`base_sha..head_sha`) or a **tip / integration** range, each with an explicit **author-provider set** |
| **validate pre-review** | `scripts/validate-stage.py --phase pre-review` only — mechanical gate before formal review status; **never** use bare “pre-review” for model activity |

**Naming rules for new docs / AGENTS revision:**

- Model advisory pass → **embedded cross-check** only.  
- Validator phase → **`--phase pre-review`** / “validate pre-review” only.  
- Do **not** use “formal-1” as a contract term.  
- Do **not** use bare “pre-review” for embedded cross-check (historical docs may still say “embedded pre-review”; rewrite on touch).

---

## A. Decisions with alternatives (final selection)

| ID | Topic | Alternatives considered | **Final selection** |
|---|---|---|---|
| D1 | Seal vs embedded cross-check order | A: seal code first, then cross-check + evidence commit; B: cross-check first, then one snapshot seal | **B** + **seen-diff bind** (patch byte-equality; capture at cross-check, assert at seal; skip cross-check → bind **N/A**) |
| D2 | Dual-task review-1 granularity | A: always per-task; B: always stage-tip; C: topology split | **C**: **serial → per-task formal review-1**; **parallel / real integration → tip-once formal review-1**; if serial tip ≠ last task head (extra integration commit), formal that **integration unit** once. Intake freezes each **review unit** and its **author-provider set**. **All** required serial task units (and integration unit if any) must **ACCEPT** before review-2. Review-1 provider must differ from **every** implementer/fix author of that unit |
| D3 | Embedded cross-check mandatory scope | A: mandatory all MEDIUM+ auto; B: optional default | **B**; mandatory **recorded attempt** for parallel / two-owner / high-contract-risk; absence fail-open with `*.unavailable` / skip artifact; does not block review-1; bind **N/A** when skipped |
| D4 | Rework ledger | A: single ledger auto≤2 reserve R2; B: auto 3 cycles no reserve | **A** + **`max_rework_per_stage = 3`** (see §C). **All** automatic code-changing retries share this ledger (including P7 test-failure auto-fix and review-1 REWORK); combined auto charge **≤2** |
| D5 | Isolation | A: read-only only; B: exclusive worktree hard preflight | **B**: exclusive stage worktree + fresh read-only review; else fail-closed / fall back to human dispatch (record mode flip in status — shape in stage design) |
| D6 | Who may invoke models | A: implementer chain; B: runner only | **B** |
| D7 | Grok as review-1 | A: global default; B: opt-in auto only | **B**; manual stages keep Kimi↔GLM cross-pool. **Fallback:** serial per-task unit may use cross-pool **only if** a candidate is isolation-eligible (not an author of that unit). **Parallel tip-once:** cross-pool is **ineligible** (both GLM and Kimi typically authored tip code); Grok unavailable or repeated invalid JSON → **`human_escalation_required`** (operator may **manually** dispatch an independent review-1); never auto high-end substitution (P9) |
| D8 | Migration | A: big-bang; B: stage opt-in | **B**, default off; ≥2 pilots before default flip |
| D9 | Design readiness | A: implement from design note raw; B: freeze then HIGH stage | **B** (this table is the freeze) |
| D10 | Dual-hat commit in auto | A: keep carve-out; B: disable | **B** disabled in auto (human mode may keep existing rules) |
| D11 | Human ack review-1 ACCEPT | A: required; B: not | **B**; human gates: scope freeze, **auto-run authorization**, review-2, merge, existing product/credential gates |
| D12 | Vocabulary | formal-1 vs review-1 | **review-1 / review-2**; advisory = **embedded cross-check** |

---

## B. Problems without binary choice → scheme to implement

| ID | Problem | Scheme to implement |
|---|---|---|
| P1 | Fingerprint formula risk | **Zero change** to existing `diff_fingerprint` formula; no worktree fingerprint; seen-diff bind is **not** a fingerprint field |
| P2 | Bookkeeper after automation | Mechanical → **runner**; narrative → templates ± optional cheap model; model sessions never authoritative on `status.json` / handoff |
| P3 | Grok lacks output-schema | Capture raw stdout; accept **only the last and only schema-valid JSON block** in that stream; persist that block **unaltered** as the verdict artifact (footer/prose may remain in raw log but must not be mined for alternate JSON); validate against `schemas/review-verdict.schema.json` before any status transition; **grok-build plan-mode**, not coding composer |
| P4 | Parallel-mode vs new advisory semantics | Mutually exclusive stage modes (or subsume); one validator path |
| P5 | Verdict dirties tree after seal | **Verdict-record commit** only; never rebind `base_sha` / `head_sha` / `diff_fingerprint`; runner checks verdict.fp == sealed snapshot fp |
| P6 | Tip-once multi-domain REWORK; single `fix_start_prompt` string | v1 **no schema change**; runner routes by findings paths + domain ownership; full prompt + “fix only your domain” header per owner; unroutable → escalation. **Write scheduling:** multi-owner fixes for one tip verdict are **serialized**, or use **isolated task worktrees then integrate** — **never** two implementers concurrent-write the same exclusive stage worktree. After all domain fixes: unified re-test → cross-check → bind → seal |
| P7 | Blocking failure unattended | Blocks review-1; **one** automatic implementer retry **charges rework ledger** (same auto ≤2 budget as review-1 REWORK); then escalation + `80-*.md` |
| P8 | Cost beyond round cap | Per-stage **call-count** and **wall-clock** budgets are **required intake config** (no global defaults frozen here); exceed → escalation |
| P9 | High-end wording | No **orchestrator-loop auto** GPT/Claude mid-pipeline; human-started short synthesis / breakdown / review-2 allowed |
| P10 | Mix with product stages | Dedicated HIGH Harness stage only; not inside funding product delivery |
| P11 | Pilot before default flip | Pilot 1 docs-only to `stage_accepted_waiting_user`; Pilot 2 small real stage; metrics: Grok schema-valid rate, escalation shape, RECEIPT completeness |
| P12 | Escalation artifact | `reports/agent-runs/<stage-id>/80-*.md` + status reason/rounds |
| P13 | Untrusted inputs and secrets | Code, reports, and model outputs are **untrusted data** and must not alter runner next-hop control flow; immutable prompt templates state this. RECEIPT records **adapter command references only** — never expanded aliases, env dumps, tokens, or credentials (`never_log_expanded_environment`) |

---

## C. Rework numbers (operator locked)

```text
max_rework_per_stage = 3
  # single ledger for the entire stage

auto code-changing budget ≤ 2
  # INCLUDES: review-1 REWORK fixes + P7 blocking auto-fix retries
  # leaves ≥1 for review-2 REWORK room

invalid_json_max_attempts_per_model = 2
  # UNCHANGED from AGENTS/registry/template (one retry, two attempts total)
  # does NOT charge rework

on cap / timeout / budget / unroutable / tip-once Grok failure
  → human_escalation_required + 80-*.md
```

---

## D. Target main path (selected)

```text
Human: freeze scope + auto-run authorization
       (adapters, call-count budget, wall-clock budget, rework cap = 3)
  → exclusive stage worktree (else fail-closed / human dispatch)
  → Implementers (GLM / Kimi) within file boundaries
  → Blocking checks
       fail → one auto-fix (charges rework) → re-block or escalate
  → Embedded cross-check (D3; advisory)
       if run: CAPTURE code-scope git diff --binary patch (seen artifact)
       if skipped: bind := N/A
  → Re-run blocking
  → Single clean snapshot SEAL
       (code + test logs + cross-check evidence if any)
       + ASSERT seen-diff bind (byte-equal patches) unless N/A
       + write base/head/diff_fingerprint (unchanged formula)
       + validate-stage (--phase pre-review when entering formal gates)
  → review-1 (Grok under opt-in auto; P3 JSON rules)
       freeze review unit + author-provider set (D2)
       serial: per-task units; all must ACCEPT before review-2
       parallel: tip-once; Grok fail → human_escalation (D7)
  → REWORK: route fix_start_prompt (P6 serial multi-owner if needed)
       → implement (charges rework; auto total ≤2) → loop from implement
  → ACCEPT → stop for human-started review-2
  → Human accept → merge to main (explicit)
```

### Serial two-owner (summary)

```text
Task A (e.g. GLM): implement → block → cross-check? → seal_A → Grok unit A
  → REWORK only A … until ACCEPT
Task B (e.g. Kimi): same for unit B
Optional integration unit if tip ≠ B head
All required units ACCEPT → human review-2
```

### Parallel two-owner (summary)

```text
Domain work (prefer isolated task worktrees) → integrate tip
  → block → mandatory cross-check attempt → seal_tip → Grok tip-once
  → REWORK: serial domain fixes or isolated worktrees → unified re-seal
  → Grok fail / no eligible auto fallback → human_escalation
  → ACCEPT → human review-2
```

---

## E. Non-goals (locked)

- No change to the committed-range `diff_fingerprint` algorithm.  
- No second fingerprint / worktree fingerprint protocol (seen-diff bind is patch byte-equality only).  
- No change to review-2 “not implementer” hard rule or merge-requires-human-acceptance.  
- No product/API/runtime delivery in the Harness revision stage.  
- No implicit enablement on in-flight product stages.  
- No implementer dual-hat commit under auto mode.  
- No automated high-end model substitution when Grok fails on tip-once.

---

## F. Harness revision stage (next after this freeze)

| Field | Value |
|---|---|
| Suggested id | `2026-07-auto-review-pipeline-v1` |
| Complexity | **HIGH** |
| Primary input | **This file** |
| Scope (illustrative) | `AGENTS.md`, `workflows/templates/stage-delivery.yaml`, `agents/registry.yaml`, `docs/model-adapters.md`, new `docs/auto-review-pipeline.md`, `docs/parallel-development-mode.md` (mutex + rename), `scripts/validate-stage.py`, new `scripts/stage-seal.py` + runner, templates/skills |
| Must implement | D1–D12, P1–P13, §C, vocabulary rules, opt-in flag |
| Deferred to intake/design (non-blocking shapes) | Exact auto-run authorization artifact fields; status field for D5 human-dispatch mode flip; numeric defaults for P8 per pilot |

---

## G. Dual review disposition (closed)

| Reviewer | Verdict | Artifact |
|---|---|---|
| GPT/Codex | ACCEPT-with-edits (6 patches + P8 note) | `42-decision-table-review-gpt.md` |
| Claude Fable 5 | ACCEPT-with-edits (3 patches) | `41-decision-table-review-fable5.md` |
| Merge | All patches absorbed into this revision | `43-decision-table-patch-merge.md` |

No further dual review of this table is required unless the operator reopens a row.

---

## H. Operator next step

1. Optional: spot-check this frozen table.  
2. Open Harness stage **`2026-07-auto-review-pipeline-v1`** with this file as requirements source (GPT bookkeeper / stage producer).  
3. Keep product work on `stage/2026-07-funding-annualized-history-v1` (or `main`) separate from this docs branch.

---

```text
本地北京时间: 2026-07-11 11:21:54 CST
Document: reports/agent-runs/2026-07-auto-review-pipeline-design-review/40-operator-decision-table.md
Status: FROZEN — POST DUAL REVIEW
Branch: docs/2026-07-auto-review-pipeline
下一步模型: human 或 GPT bookkeeper（开 2026-07-auto-review-pipeline-v1 intake）
下一步任务: 用本表起草 00-intake.md；勿混入 funding 产品 stage 交付
```

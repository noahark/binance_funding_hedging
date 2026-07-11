# Design Note: Auto Review Pipeline And Harness Flow Revision

Status: **OPEN — design discussion only**  
Date captured: 2026-07-10  
Author of this note: Grok (design capture from operator discussion)  
Audience: independent model review (e.g. GPT/Codex or Claude) before any
Harness contract change stage is opened  
Not a delivery stage. Not an accepted decision. Not authorization to change
`AGENTS.md` or product code.

Related product work (separate track):

- Funding annualization + history drawer requirements:
  `reports/follow-ups/2026-07-funding-annualized-history-drawer.md`
- Active product stage (do not mix this process redesign into it):
  `reports/agent-runs/2026-07-funding-annualized-history-v1/`

---

## 1. Why This Note Exists (前因)

### 1.1 Product context (background only)

The operator was driving a product stage for 24h/7D/30D funding annualization
and a right-side 30-day history drawer. That work produced a normal Harness
stage package and serial Task A/B dispatch under **current** DRAFT-2 rules
(human paste dispatch, independent bookkeeper, committed fingerprint before
formal review).

### 1.2 Process friction that triggered the redesign talk

While clarifying “who reports to whom after implementer finish,” the operator
asked whether the human must always relay implementer output to a Codex
bookkeeper, and whether implementers could call other models (`codex -p`,
`grok -p`) to automate seal + review-1.

That discussion surfaced a **workflow product decision**, not a funding-feature
bug:

| Operator pain | Current Harness default |
|---|---|
| Too many human paste hops between implement → seal → review-1 | `model_dispatch_execution_requires_human: true`; human executes all model dispatches |
| High-end models (GPT/Claude) are expensive if used as long sub-agent workers | Codex/Claude often sit in bookkeeper / design / review-2 paths; risk of burning them on long chains |
| Want automatic mid-pipeline review until a gate passes | Formal review requires committed `base_sha..head_sha` + `diff_fingerprint`; bookkeeper owns commits/status by default |
| Human wants to focus on **review-2 / acceptance**, not every hop | Human is currently the dispatcher for implementation, review-1, review-2, and fix |

### 1.3 What this note is for

Capture **goals, current mechanics, proposed target flow, risks, and which
documents must change** so another model can challenge or refine the design
before a Harness revision stage is opened.

---

## 2. Operator Goals (目的)

Consolidated from the operator’s statements (paraphrased, then structured):

### 2.1 Cost and model tiering

1. **GPT / Claude (high-end)** must **not** be invoked as long-running sub-agents
   for implementation or multi-round mid-pipeline work (token cost).
2. High-end models remain appropriate for **short, high-value** work the
   operator still wants: e.g. direction synthesis, **review-2 final gate**,
   human-attended acceptance narrative — not “banned from all CLI use.”

### 2.2 Development and review chain

3. **GLM and Kimi** implement (domain-routed as today: backend vs frontend).
4. After development, **GLM ↔ Kimi embedded pre-review** (cross-read).
5. Pre-review findings may be **accumulated without immediate fix** (advisory).
6. **Grok** runs **formal review-1**, reading committed diff **plus** pre-review
   artifacts, and may produce issue lists and **remediation / fix guidance**.
7. **Loop** implementer fix → re-seal → Grok again until formal review-1
   **ACCEPT** (with a hard rework cap — see §5).
8. Then human + **Claude** (or configured high-end) for **review-2 / final
   acceptance**; merge to `main` still needs explicit human acceptance.

### 2.3 Seal and fingerprint

9. Commits exist primarily to **freeze content for review targeting**
   (`base_sha` / `head_sha` / `diff_fingerprint`), not as a social “human
   blessing” ritual.
10. Computing fingerprint and writing mechanical `status.json` fields should be
    **scriptable** (deterministic), not done by a high-end model “by feel.”

### 2.4 Human attention model

11. If requirements and file boundaries are frozen up front, the operator is
    willing to **not babysit** implement → pre-review → formal-1, and only
    engage deeply at **review-2**.
12. Problems should still be discoverable at review-2 (defense in depth).

---

## 3. Current Environment (现状) — What Already Exists

### 3.1 Authority stack (relevant slices)

| Layer | Role today |
|---|---|
| `AGENTS.md` | Hard gates: human executes model dispatch; bookkeeper single writer for stage state/commits; review needs committed fingerprint; Grok not default review gate |
| `workflows/templates/stage-delivery.yaml` | `model_dispatch_execution_requires_human: true`; review-1 cross pool; review-2 GPT then Claude |
| `scripts/validate-stage.py` | Recomputes fingerprint; enforces provider isolation; clean worktree at pre-review |
| `agents/registry.yaml` | Adapter routing; review pool |
| `docs/model-adapters.md` | How to invoke models; paste-first semantics |
| `docs/parallel-development-mode.md` | Embedded pre-review (R-series) for **parallel** stages; bookkeeper not implementer by default |

Harness baseline on `main` (as of operator context): rolled back to **DRAFT-2**
decision baseline (see `AGENTS.md` / stage index notes). Paste-first and human
dispatch are intentional, not accidental.

### 3.2 Diff fingerprint protocol (already automated-capable)

Authoritative formula (must not invent a second scheme):

```text
diff_fingerprint = head_sha + ":" + sha256(
  git diff --binary <base_sha>..<head_sha> -- . \
    ":(exclude)reports/agent-runs/<stage-id>/status.json"
)
```

Properties:

- **Committed range only** — no `worktree_fingerprint`.
- **`status.json` excluded** from the hashed diff (avoids self-reference when
  status records the fingerprint).
- Written into `status.json` and into **review verdict JSON**;
  `validate-stage.py --phase pre-review` **recomputes** and must match.
- Review prompts must cite **recorded** `base_sha..head_sha`, never a moving
  uncommitted tree.

Implementation of the hash already lives in
`scripts/validate-stage.py` → `compute_diff_fingerprint`. What is **missing** is
an orchestration helper (e.g. `stage-seal`) that commits, writes status fields,
and runs validate in one step.

### 3.3 Who may do what today (simplified)

```text
Implementer (GLM/Kimi):  code + tests + implementation report
                         must NOT commit / must NOT edit status/handoff
                         must NOT execute model dispatch to other models

Bookkeeper (often Codex session):
                         commits evidence, fingerprint, status, handoff
                         prepares review prompts
                         must NOT execute model dispatch (human pastes)
                         must NOT write product code

Human:                   pastes prompts into model terminals
                         approves package, review-2 attention, merge

Review-1:                cross provider (GLM implement → Kimi review, etc.)
                         Grok is NOT default review-1

Review-2:                GPT/Codex first, Claude fallback; not implementer
```

### 3.4 Why “implementer calls codex -p for bookkeeper text” was rejected under current rules

Content-wise, “generate a handoff markdown” can equal “human pastes the same
prompt.” Control-wise, current contract treats **who starts the next model** as
a hard gate (audit, dual-hat, permission creep into commit/status). This note
proposes **changing that contract deliberately**, not claiming it already allows
auto-chain.

---

## 4. Proposed Target Pipeline (后果 / 目标态)

### 4.1 Recommended target flow (refined from operator intent)

```text
Human: freeze requirements, scope, file boundaries, acceptance
        (design/breakdown as complexity requires)
              ↓
Implementers: GLM (backend) / Kimi (frontend) — cheap coding models
              ↓
【blocking — script】
  pytest / schema / git diff --check (and stage-specific checks)
  FAIL → stop; do not enter formal review
              ↓
【seal — script preferred】
  git commit (allowlisted paths only)
  compute base_sha / head_sha / diff_fingerprint (same formula as today)
  write mechanical status fields; status → ready for formal-1
  validate-stage (post-seal / pre-review as defined)
              ↓
【embedded pre-review — advisory — cheap models】
  GLM ↔ Kimi cross-read of raw diff + tests
  findings written to stage evidence files
  default: do NOT auto-fix advisory findings before formal-1
              ↓
【formal review-1 — Grok — read-only】
  inputs: committed base..head, test logs, pre-review raw artifacts
  output: schema-valid review-verdict JSON
          REWORK ⇒ fix_start_prompt required
              ↓
  ACCEPT → proceed to review-2 scheduling
  REWORK → implementer fixes from fix_start_prompt only
           → seal again (new head, new fingerprint)
           → Grok again
  max_rounds (default 3) exceeded → human_escalation_required
              ↓
【review-2 — human starts high-end, short read-only】
  Claude preferred when design was Codex-authored (provider isolation)
  or configured high-end final reviewer
              ↓
stage_accepted_waiting_user
              ↓
Human explicit accept → merge stage branch to main
```

### 4.2 Blocking vs advisory (must not blur)

| Class | Examples | Gate effect |
|---|---|---|
| **Blocking** | failing tests, schema invalid, `git diff --check`, missing required evidence files | **Cannot** enter formal-1 |
| **Advisory pre-review** | GLM↔Kimi style/contract nitpicks, optional suggestions | May enter Grok **unfixed**; Grok weighs them |

Operator phrase “有问题先不修” applies to **advisory pre-review**, not to red
tests.

### 4.3 Model tier policy (precise wording for later AGENTS edit)

| Model tier | Intended use in target design | Not intended |
|---|---|---|
| GLM / Kimi | Implementation, advisory pre-review, fixes from formal-1 | Final sole authority without formal-1/2 |
| Grok | Default **formal review-1** (schema verdict + fix prompts) | Unlimited auto-loop without cap; writing product code in review mode |
| GPT / Claude | Direction synthesis; **review-2**; human-attended decisions | Long sub-agent implementation loops; auto mid-pipeline worker |
| Scripts | Seal, fingerprint, validate, prompt template fill, verdict schema check | Judging code quality |

### 4.4 Seal role

- Prefer **`scripts/stage-seal.py` (or equivalent)** over any LLM for:
  allowlisted `git add` / `commit`, fingerprint, mechanical `status.json` fields,
  invoking `validate-stage.py`.
- Optional: cheap model only if script cannot handle narrative handoff text;
  still must not invent fingerprints.
- Implementer dual-hat commit only if stage explicitly discloses dual-hat and
  review-2 evaluates that risk (legacy AGENTS concept, keep if needed).

### 4.5 What automation achieves

| Step | Automate with |
|---|---|
| Fingerprint + commit + validate | **Script** |
| Pre-review + formal-1 + fix loop | **Models + orchestrating script**, if AGENTS allows non-human dispatch for those roles |
| Review-2 + merge | **Human** (operator goal) |

Fingerprint automation **enables** auto-review; it does not replace review
judgment.

---

## 5. Risks And Counter-Arguments (另一模型请重点打)

1. **Infinite or expensive Grok loops**  
   Without `max_rework` / `max_formal_1_rounds`, token use may exceed today’s
   human-gated path. Cap is mandatory.

2. **Grok as sole formal-1**  
   Today Grok is explicitly **not** a default review gate. Promoting it is a
   product/Harness decision. Requires stable **schema-valid JSON** verdicts or
   fail-closed retries will thrash.

3. **Advisory pre-review bias**  
   Two cheap models may share blind spots. Mitigation: Grok formal-1 + high-end
   review-2; pre-review never substitutes formal-1.

4. **Dual task stages**  
   Backend GLM + frontend Kimi: define whether Grok formal-1 is **per-task**
   (after each seal) or **once on combined stage tip**. Serial product stages
   need an explicit rule.

5. **Dispatch permission creep**  
   “Implementer may call Grok for review” can slide into “implementer rewrites
   status and self-ACCEPT.” Contract must whitelist: who may invoke whom, and
   that formal-1 is **read-only**.

6. **Reviewer / implementer session isolation**  
   Formal-1 must remain a **fresh read-only** session relative to implementer
   tool state (provider isolation already required). Auto-chain must still spawn
   isolated review invocations.

7. **Token total vs high-end token**  
   Optimization target is **high-end token/minute**, not necessarily total
   calls. Document that explicitly so reviewers do not optimize the wrong metric.

8. **Mixing with active product stages**  
   Process redesign must land as its **own Harness stage** on `main` (or
   harness-only branch policy), not inside
   `2026-07-funding-annualized-history-v1` delivery commits.

9. **Validator / unknown status fail-closed**  
   New statuses or transitions require `validate-stage.py` + `ALLOWED_STATUSES`
   updates or the pipeline hard-stops.

10. **Operator still owns merge**  
    Even with full mid-pipeline automation, `review-2 ACCEPT` ≠ merge; human
    acceptance remains (aligns with operator intent).

---

## 6. Documents And Artifacts To Change (订正清单)

Authority order: change top-down. Minimum set for a real contract shift:

### 6.1 Must change

| Path | Change intent |
|---|---|
| `AGENTS.md` | Tiered dispatch; Grok formal-1; advisory vs blocking; seal-by-script; human gates narrowed to review-2/merge/product; high-end not long worker |
| `workflows/templates/stage-delivery.yaml` | Replace blanket human-dispatch flag with role/gate matrix; nodes for seal / pre-review / formal-1 loop |
| `agents/registry.yaml` | Grok formal-1 adapter; pre-review routing; sealer/script preference |
| `scripts/validate-stage.py` | New phases/fields if any; Grok identity as formal-1; optional pre-review artifact checks; keep fingerprint formula |
| `schemas/review-verdict.schema.json` | Only if extra fields needed (e.g. pre-review path refs); keep fingerprint + strict JSON |

### 6.2 Strongly recommended

| Path | Change intent |
|---|---|
| `docs/model-adapters.md` | Allowed auto invocations; Grok read-only formal-1; forbid high-end long worker patterns |
| **New** `docs/auto-review-pipeline.md` | Single human-readable contract for the pipeline in §4 |
| `agents/developer-discipline.md` | RECEIPT, no hand-rolled fp, fix only from formal-1 prompt |
| `agents/skills/*` | Reviewer skill for Grok formal-1; implementer completion → seal |

### 6.3 Optional

| Path | Change intent |
|---|---|
| `scripts/stage-seal.py` (**new**) | Commit allowlist + fingerprint + status mechanical write + validate |
| `reports/agent-runs/_template/*` | Status shape, RECEIPT layout |
| `docs/planning/DECISIONS.md` | DEC record after user approval |
| `docs/development/DEVELOPMENT_GUIDE.md` | Operator how-to |
| `docs/parallel-development-mode.md` | Cross-link or subsume embedded pre-review under new pipeline doc |

### 6.4 Do not change for this redesign

- Active product stage trees’ business code scope
- Historical accepted stage evidence under `reports/agent-runs/<old>/`
- Public API contract / PRD (unless a product stage needs them)

### 6.5 Suggested delivery vehicle

Open a dedicated complexity **MEDIUM/HIGH Harness stage**, e.g.
`2026-07-auto-review-pipeline-v1`, with:

- direction or operator-approved design note = this file (or its synthesis)
- no funding/runtime product scope
- implement AGENTS/yaml/registry/validator/scripts first
- pilot on a tiny no-op or docs-only stage before applying to product work

---

## 7. Relationship To “Fingerprint Script = Auto Review”

Operator question: can scripts/models replace the seal/fingerprint steps so
auto-review works?

Answer captured for reviewers:

| Layer | Replace human? | By what? |
|---|---|---|
| Commit + fingerprint + validate | Yes | **Script** (must match `validate-stage.py`) |
| Pre-review / formal-1 judgment | Yes (if policy allows) | **Models** (GLM/Kimi / Grok) |
| Review-2 + merge | No (operator goal) | **Human + high-end** |

Scripts make auto-review **possible and honest**; they do not make model review
optional.

---

## 8. Explicit Non-Goals Of This Design Note

- Not approving rewrite of `AGENTS.md` in this commit/file alone  
- Not changing the funding annualized history product stage process mid-flight  
- Not claiming Grok is already formal-1 in production Harness  
- Not defining exact CLI flags for every adapter (belongs in model-adapters)  
- Not removing provider isolation or schema-valid verdict requirements  

---

## 9. Open Questions For The Reviewing Model

Please answer explicitly in your review:

1. Is **Grok-as-default-formal-1** acceptable given quality/JSON stability risk,
   or should formal-1 remain cross-pool (Kimi↔GLM) with Grok only optional?
2. Should advisory pre-review be **mandatory** for MEDIUM+ stages or optional?
3. Per-task vs stage-tip formal-1 for dual implementer stages?
4. Minimum human gate set: is “only review-2 + merge” enough, or must human
   still acknowledge formal-1 ACCEPT?
5. May implementer sessions invoke Grok/Kimi **directly**, or only a **local
   orchestrator script** (no LLM) that calls adapters?
6. Does promoting auto-dispatch conflict with any security/compliance need to
   keep a human in every model start (operator environment-specific)?
7. Fingerprint formula: confirm **no change** (recommended) vs any extension?
8. Suggested `max_formal_1_rounds` default and escalation artifact shape?
9. Naming: keep “review-1” for Grok formal, and rename GLM↔Kimi to
   “embedded pre-review” only — any better vocabulary?
10. Migration: big-bang AGENTS edit vs feature-flag / stage opt-in
    `auto_review_pipeline: true`?

---

## 10. Conversation Trace (for audit of intent)

Rough sequence of operator ↔ assistant topics that produced this note:

1. Product requirements for funding annualization + drawer → follow-up doc for
   GPT stage production.  
2. GPT stage package review (routing, file boundaries, review-2 primary).  
3. Operator confirmed package fixes; Task A paste-to-GLM workflow.  
4. Operator asked whether GLM finish → human → GPT bookkeeper is the path;
   confirmed under current rules.  
5. Operator asked why GLM cannot call Codex only for handoff text; answer:
   content can be equivalent, **control plane** currently forbids implementer
   dispatch.  
6. Operator proposed mid-pipeline autonomy until review-1, human on review-2;
   assistant listed current intercepts (human dispatch, bookkeeper commit,
   fingerprint, isolation, validator).  
7. Operator refined: high-end not long sub-agents; GLM↔Kimi pre-review without
   immediate fix; Grok formal-1 with fix guidance; loop until pass; commit for
   fingerprint. Assistant judged direction sound with required guards.  
8. Operator asked how fingerprint/review works today → formula + seal gap.  
9. Operator asked if scripts/models can replace seal for auto-review → yes
   scripts for seal; models for judgment; AGENTS still blocks auto dispatch.  
10. Operator asked which docs to change → §6 list.  
11. Operator requested this design note for another model to cross-check.

---

## 11. Suggested Prompt For The Next Model

You can paste:

> Review `reports/follow-ups/2026-07-auto-review-pipeline-design-note.md` as a
> Harness process redesign proposal. Challenge §4–§5, answer §9 open questions,
> and produce either (a) ACCEPT-with-edits synthesis suitable for an AGENTS.md
> revision stage intake, or (b) REWORK with concrete alternative flow. Do not
> implement product code. Do not mix with
> `2026-07-funding-annualized-history-v1` delivery.

---

## 12. Footer

```text
本地北京时间: 2026-07-10 18:35:04 CST
Document: reports/follow-ups/2026-07-auto-review-pipeline-design-note.md
Status: open design note for cross-model review
Next: independent model reviews this note; operator decides whether to open
      Harness stage 2026-07-auto-review-pipeline-v1 (name TBD)
下一步模型: GPT/Codex 或 Claude（对照审阅本 note）
下一步任务: 回答 §9；给出可写入 00-intake 的修订合成或 REWORK 替代流程
```

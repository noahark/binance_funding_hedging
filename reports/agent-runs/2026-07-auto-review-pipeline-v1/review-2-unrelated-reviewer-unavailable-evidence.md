# Review-2 Unrelated-Reviewer Unavailability Evidence

Purpose: satisfy the AGENTS.md strong-reviewer disclosure override
precondition ("allowed only after the unrelated decision model fails a
runner-level availability check ... the failure evidence path must be
recorded") and the validator's `unrelated_reviewer_unavailable_evidence`
existence check.

Date: 2026-07-11
Recorded by: Fable5 bookkeeper session (anthropic), per operator statements
on 2026-07-11.

## 1. Registered decision models are both design-conflicted

Per `status.json` involvement records (machine-checked identities):

- **OpenAI/Codex**: design-review author
  (`…design-review/30-review-codex.md`), intake author, stage designer
  (`00-task.md` / `10-design.md` / `11-adr.md`), former stage bookkeeper.
  Involvement enum: `design`.
- **Anthropic/Claude**: direction patches merged into the frozen decision
  table (F1–F3 via `…/41-decision-table-review-fable5.md`), stage-design
  review (`13-stage-design-review-fable5.md`), development breakdown
  (`12-development-breakdown.md`), second inspections (`22-`/`25-`),
  **acting stage bookkeeper**. Involvement enum: `design` (plus breakdown
  and direction-synthesis-level contributions recorded in notes).

There is therefore **no registered unrelated decision model** for this
stage. This is the `anti_self_review_ineligible` / design-conflict
ineligibility branch of the allowed fallback reasons.

## 2. The only zero-involvement candidate is service-unavailable

The registry reserves one third-decision-model candidate
(`model_policies.future_review_2_fallback_candidates`: google /
Gemini 3.1 Pro; trigger includes explicit user approval). On 2026-07-11 the
operator stated that **Gemini is frequently unreachable due to network
problems** ("gemini 因为网络的问题经常调不通") and declined to route
review-2 through it. There is no local Gemini adapter in
`agents/registry.yaml`; the only invocation path would be manual external
relay, which the operator reports as unreliable in their environment.

Fallback reason class: `service_unavailable` (listed in
`model_policies.review_2_fallback_allowed_on`).

## 3. Operator routing decision

The operator directed (2026-07-11): review-2 will be dispatched by the
operator personally, selected from the high-end pool — GPT-5.6 family
(`gpt-5.6-sol` > `gpt-5.6-terra` > `gpt-5.6-luna`, descending capability
per operator) or Claude (`claude-fable-5`, `opus4.8`) — according to
cross-review principles and remaining token budget at dispatch time. The
bookkeeper prepares a provider-neutral packet; the actually used model is
recorded truthfully in the verdict `model` field and in `status.json`.

Note: `agents/registry.yaml` still records `codex.default_model: gpt-5.5`;
the GPT-5.6 family is newer than the registry snapshot. This is recorded as
a Harness follow-up (registry model refresh) and does not block the manual
dispatch path.

## 4. Consequence

Whichever provider the operator selects, review-2 proceeds under the
documented strong-reviewer disclosure override:

- `reviewer_prior_involvement` recorded truthfully (both candidates:
  `design`; Anthropic additionally discloses breakdown authorship and the
  acting-bookkeeper dual-hat, which the verdict must explicitly evaluate);
- `fallback_reason`: `service_unavailable` (Gemini) plus design-conflict
  ineligibility of both registered models;
- this file is the recorded evidence path;
- the review-2 prompt ranks the user-approved frozen decision table
  (`40-operator-decision-table.md`) as the top requirements authority.

本地北京时间: 2026-07-11 21:05:00 CST

---

## v2 Addendum (2026-07-11 22:15 CST) — basis revised per sol P1 finding

The gpt-5.6-sol review-2 correctly found that §2 above is an operator
statement, not the runner-level failure artifact AGENTS.md requires for a
`service_unavailable` claim; moreover Gemini succeeded once in the operator's
parallel panel on 2026-07-11, contradicting the standing claim. The
`service_unavailable` basis is therefore **withdrawn**.

**Revised basis — design-conflict ineligibility (no availability check
needed):**

1. The registered decision-model set is exactly {OpenAI/Codex,
   Anthropic/Claude} (AGENTS.md Reviewers; registry `review_2` rotation).
   Both are design-conflicted for this stage (§1 above, unchanged).
2. Gemini 3.1 Pro is **not** a registered decision model. It is a
   `future_review_2_fallback_candidates` entry whose enablement trigger is
   explicit user approval. On 2026-07-11 the operator **explicitly declined
   enablement** ("gemini 的测试不用进行，浪费时间" — network unreliability
   in their environment), so the trigger is not satisfied and Gemini's
   reachability is immaterial to the registered set.
3. Therefore no unrelated registered decision model exists:
   `anti_self_review_ineligible` / design-conflict ineligibility — a listed
   override basis that rests entirely on committed registry facts and the
   recorded operator instruction, requiring no availability artifact.

The one-off Gemini panel output (`50-review-2-gemini.md`) remains landed as
non-record advisory evidence; it does not alter the registered set.

本地北京时间: 2026-07-11 22:15:00 CST

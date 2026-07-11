# Review: Operator Decision Table (GPT/Codex)

Status: **DECISION-TABLE REVIEW — ACCEPT-with-edits**  
Date: 2026-07-11  
Reviewer: GPT/Codex  
Reviewed document (pre-merge draft):
`reports/agent-runs/2026-07-auto-review-pipeline-design-review/40-operator-decision-table.md`

Pre-stage design review; no delivery `diff_fingerprint`.

## Verdict

**ACCEPT-with-edits.** The table already clearly adopts single-snapshot seal
(D1), topology-split review-1 (D2), single-ledger reserve for review-2 (D4),
runner-only dispatch, Grok opt-in, worktree isolation, and no product-stage
mixing. It is usable as HIGH Harness stage direction input after the minimal
wording patches below.

## Minimal patches required

1. **D1 — seen-diff bind as patch byte equality, not a second hash.**  
   A “hash equality gate” risks looking like a forbidden worktree fingerprint
   protocol. Instead: persist the exact `git diff --binary` patch seen at
   cross-check (fixed base/pathspec); after seal regenerate the same-range
   patch and compare byte-for-byte. Do **not** write that hash/fingerprint
   into `status.json` or verdicts.

2. **D2 + D7 — review unit, completion, eligible fallback.**  
   Intake must freeze each review unit (task or tip range) and its
   author-provider set. Review-1 provider must differ from every
   implementer/fix author of that unit. All serial task units (and
   integration unit if needed) must ACCEPT before review-2.  
   Constrain D7: cross-pool fallback only when an isolation-eligible candidate
   exists. For GLM+Kimi parallel tip, Kimi/GLM are both ineligible; Grok
   unavailable or repeated JSON failure → escalate for human choice of an
   independent reviewer — do not assume cross-pool is always available.
   Existing validators collect author identity at full-stage scope; without
   this layer the gate hard-fails.

3. **D4 + P7 — all automatic code retries share one ledger.**  
   P7’s one post-test auto-fix changes code and must charge
   `max_rework_per_stage`, combined with review-1 REWORK auto budget ≤2.
   Cannot claim a single ledger if “test retry + two review-1 REWORKs”
   exceeds the stated auto cap.

4. **P6 — multi-owner REWORK write scheduling.**  
   v1 must require serial scheduling of multi-domain fixes for one tip
   verdict, or explicit isolated task worktrees then integrate. Two
   implementers must not concurrent-write the same exclusive stage worktree.
   After all fixes: unified re-test, cross-check, bind, and seal.

5. **P3 — machine-parseable verdict boundary.**  
   Raw stdout may keep narrative/navigation footer, but the runner accepts
   only the **last and only** schema-valid JSON block and persists it
   unaltered as the verdict artifact. No speculative JSON extraction from
   arbitrary prose.

6. **New P13 — untrusted inputs and credentials (Fable5 threat boundary).**  
   Code, reports, and model outputs are untrusted and must not alter runner
   next-hop. Immutable prompts must say so. RECEIPT records adapter command
   references only — never expanded aliases, env, tokens, or credentials.

## Non-blocking note

P8 call-count and wall-clock may be frozen as **required per-stage intake
config values** without choosing global numbers in this table.

## Disposition

Patches absorbed into `40-operator-decision-table.md` (post dual-review freeze)
and recorded in `43-decision-table-patch-merge.md`.

```text
本地北京时间: 2026-07-11 11:21:54 CST
下一步模型: operator / Grok land merge
下一步任务: 合并补丁进 40 表后开 Harness intake
```

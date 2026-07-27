# User Authorization — Class-1 Fingerprint Exception For The Frontend Review-1

## What is being waived, precisely

The frontend task's Review-1 returned **ACCEPT** against the round-1 range and
recorded

```text
diff_fingerprint = 319d8317bdf180750197c95078d2ae6c60e6badc:2a457c0f559fec81cfba8b9d59602c8630bbec73d7b86b28dddab12c4e554efd
```

The Review-2 REWORK fix then moved the diff, so `status.diff_fingerprint` is now

```text
c91d2da5fe38c8b8ecf6bd3fb6c3ee9e0141a3c8:aad2351a429714f07e759304400087c2f0a5ccc33a0111b9532153bf86c50b23
```

The frontend review's fingerprint therefore **trails** the status fingerprint.
This record downgrades that single assertion — `assertion_id`
`review_fingerprint_trails_status`, the only class-1 assertion in the validator's
source whitelist — for scope `task:frontend` **only**.

Nothing else is waived. Every negative-list assertion still applies in full:
the fingerprint must still recompute consistently, the worktree must still be
clean, reviewer identity separation still holds with no override, and this
record's own evidence and structure are themselves unwaivable.

## Why it is legitimate here — the mechanical fact

**The rework changed no frontend code at all.**

```console
$ git diff --stat 319d8317bdf180750197c95078d2ae6c60e6badc..c91d2da5fe38c8b8ecf6bd3fb6c3ee9e0141a3c8 -- frontend/
(empty)
```

The rework touched exactly three files, all backend:
`backend/hedge_open_tasks/domain.py`, `backend/hedge_open_tasks/executor.py`,
`backend/tests/test_hedge_wire_constraints.py` (see
`19-r4-diff-reconciliation-rework1.md` §1).

So `frontend/index.html` and `frontend/self-check.js` are **byte-identical**
between the head the frontend reviewer inspected and the head now shipping. That
gate reviewed exactly the frontend code that is being delivered; only the range's
endpoint moved beneath it, because the fingerprint seals the whole stage diff
rather than one task's files.

This is the precise situation class-1 exists for: a review whose verdict is
still materially valid but whose recorded fingerprint legitimately trails.

## The user's decision

- **Authorizer**: user
- **At**: 2026-07-28
- **Decision**: record a class-1 `review_fingerprint_trails_status` exception for
  `task:frontend` rather than re-run that gate.
- **Alternative offered and declined**: re-running the frontend Review-1 in a
  fresh read-only session. It was presented as the option needing no exception
  record at all, at the cost of another review round. The user chose the
  exception.

The backend gate was **not** given any such treatment: backend code really did
change, so its Review-1 is being re-run from scratch on the new range — and
routed to a different reviewer (Claude Opus 4.8) after grok-4.5's severity miss
on this very finding. Review-2 is likewise re-run in full.

## Authorship disclosure — read this before releasing

This file was **drafted by the bookkeeper** (Claude Opus 5) to record a decision
the user made in session, choosing "记授权例外" over "重跑前端 review-1" when
both were presented with their tradeoffs.

The validator can enforce that this file is committed, digest-sealed, pinned to
one fingerprint, and surfaced in the release banner. It **cannot** prove the text
came from a human — any bytes a model can write, a model can write. AGENTS.md is
explicit that the final guarantee is **mandatory human verification of this
evidence text, verbatim, before pre-accept release**. The banner exists to
trigger that reading.

**So: if you are the user releasing this stage, confirm the decision above is
actually yours before accepting.**

## Auto-expiry

`applies_to_fingerprint` is pinned to
`c91d2da5fe38c8b8ecf6bd3fb6c3ee9e0141a3c8:aad2351a429714f07e759304400087c2f0a5ccc33a0111b9532153bf86c50b23`.
Any further change to the diff — another rework, a doc fix inside the range —
moves `status.diff_fingerprint`, and this record **stops applying and must be
re-authorized**. That is deliberate: it prevents trading a permanent false-red
for a permanent false-green.

---

当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native session id)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-live-hardening-v1/21-user-authorized-frontend-fingerprint-exception.md
本地北京时间: 2026-07-28 00:35:00 CST
下一步模型: human operator
下一步任务: 重跑后端 review-1（Claude Opus 4.8）与 review-2（Codex），范围 6c5b170..c91d2da

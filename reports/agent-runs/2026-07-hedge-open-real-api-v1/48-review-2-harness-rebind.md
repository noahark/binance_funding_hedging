# Review-2 Harness Rebind — Hedge Open Real API v1

## Why this rebind exists

The prior final-review packet `50-review-2.dispatch.md` was deliberately not
executed because the old validator rejected two historic implementation packets
that had no R9 receipt header. The user authorized a narrow Harness correction:
an entirely headerless historical implementation packet may use its existing raw
implementation report plus a matching recorded Session ID as execution evidence.

The correction landed on `main` as `9a0fabf` and was merged into this active
stage as `01d3a4712c89efab79772ce2e5ee2ba415e1e43c`. It changes only:

- `scripts/validate-stage.py` — narrow legacy implementation-receipt fallback;
- its deterministic validator tests;
- the R9 documentation.

It does not alter trading code, the frozen order model, product risk policy,
Binance behavior, credentials, or live activation. The old `50-...` packet is
preserved as immutable audit history. `51-review-2-rebound.dispatch.md` is the
only current final-review packet.

## New final-review anchor

| Item | Value |
| --- | --- |
| Base | `28c550d87c1ca90983d5bde9c7102d42cffecd4e` |
| Reviewed stage head | `01d3a4712c89efab79772ce2e5ee2ba415e1e43c` |
| Fingerprint | `01d3a4712c89efab79772ce2e5ee2ba415e1e43c:c3368f63670e896cbe585293c4ff7261ba55c165346efd4ea27f672be1b91cff` |

The backend and frontend task Review-1 fingerprints remain unchanged. The
final reviewer must review the Harness correction as well as the original hedge
delivery, because the whole-stage anchor now includes the main-sync merge.

## Verification after merge

```text
.venv/bin/python -m pytest scripts/tests/test_validate_stage_dispatch_protocol.py -q
55 passed in 1.07s

.venv/bin/python scripts/validate-stage.py 2026-07-hedge-open-real-api-v1 --phase pre-review
STAGE VALIDATION PASSED
```

The successful pre-review uses the new fallback for only Task A and Task B:
each has a raw implementation report and an operator-recorded matching Session
ID in `status.json.session_receipts`. Any current packet with a present but bad
receipt remains rejected by tests.

No model dispatch, real Binance request, private endpoint, credential access,
live activation, or order placement occurred during this rebind.

当前 Session ID: unavailable (bookkeeper rebind evidence, not a model execution)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/48-review-2-harness-rebind.md
本地北京时间: 2026-07-24 12:45:15 CST
下一步模型: human operator
下一步任务: run only the rebound final-review packet 51-review-2-rebound.dispatch.md in a fresh read-only Codex session

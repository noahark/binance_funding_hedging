# Human Approval — Superseding Auto Review Authorization v4

The human operator explicitly rejected a manual-interactive substitute because
it would not preserve the Harness path to review-1, and directed the bookkeeper
to run the proposed PTY test again. The runner-owned PTY transport repair is
committed as `5e80e039f6b12c06f94a996b4525b64861121e1b` and passed the focused
114-test suite plus the stage checkpoint validator.

This direction authorizes the deterministic auto runner to resume the existing
`small_real` pilot through the registered PTY transport. The call is not a
manual implementation: the runner remains the call accountant and receipt
writer, and a successful implementation continues through blocking checks,
embedded cross-check, seal, and Grok review-1.

Task scope and budgets are unchanged from v3. Usage is not reset:
`model_calls_used=3` and `auto_code_changes_used=0` carry forward.

This approval does not authorize real `launchctl` installation or mutation,
private `.env` inspection, alias/environment expansion logging, private Binance
calls, public deployment, review-2, or merge to `main`.

Superseding authorization:

```text
reports/agent-runs/2026-07-local-service-launchd-v1/auto-run-authorization-v4.json
```

Superseded authorization:

```text
reports/agent-runs/2026-07-local-service-launchd-v1/auto-run-authorization-v3.json
```

本地北京时间: 2026-07-13 16:28:13 CST
下一步模型: Claude-GLM / GLM-5.2（auto runner PTY）
下一步任务: 通过 entrypoint=cli 实现 T1 并继续原 Harness review-1 流程

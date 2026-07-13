# Fix Report

No fix has been executed. Codex bookkeeper pre-review reconciliation rejected
the uncommitted manual implementation before formal review-1 because the
targeted frozen pytest command exits 1 and injected probes exposed additional
correctness, privacy, launchctl-error, bounded-tail, log-directory, and
lifecycle failures.

The same-author repair packet is ready at
`manual-fix-T1-launchd-service-pre-review.prompt.md`. It keeps the exact five
delivery paths, explicitly invokes `senior_developer`, denies Bash/real
launchctl/secret inspection, and assigns all deterministic commands back to
the bookkeeper. Because formal review-1 has not run, this does not increment
`rework_count` and is not a reviewer-generated `fix_start_prompt`.

Attempt 1 returned through the human operator and is preserved in
`manual-fix-T1-launchd-service-attempt1.operator-forwarded-output.md`. It
changed the four claimed files but self-reported an out-of-policy read-only
`py_compile` command. Bookkeeper execution found `64 passed, 6 failed` in the
targeted suite plus three uncovered negative-probe gaps. No delivery evidence
commit or formal review attempt was created.

Attempt 2 is prepared at
`manual-fix-T1-launchd-service-attempt2.prompt.md`, narrowed to
`scripts/service-control.py` and `scripts/tests/test_service_control.py` and
explicitly forbidding all commands.

Attempt 2 returned from the same `zhipu_glm` author and is preserved at
`manual-fix-T1-launchd-service-attempt2.operator-forwarded-output.md`, associated
with session `5ee354f2-d410-4de2-aee7-fdd85e8f0d1b`. It fixed the runtime
NameError, service-specific not-loaded classification, port/host validation,
and URL-userinfo diagnostic redaction. The targeted suite now passes 82 tests,
the full backend passes 301 tests, all other frozen checks pass, and the final
negative probes pass.

The attempt self-reported a second read-only Bash/grep policy deviation. Both
policy deviations remain disclosed for formal review. Because these were
bookkeeper pre-review corrections rather than a schema-valid formal reviewer
`REWORK`, they did not increment `rework_count` at that time.

## Review-2 P2 Repair — Pending Human Dispatch

Formal Opus review-2 later returned schema-valid `BLOCKED`. The human resolved
the environment-dependent P1 by accepting the current Desktop/TCC limitation:
the repository will not move, no broad privacy grant will be added, and local
startup/visible acceptance will use the human-started `scripts/run-server.sh`.
That decision is recorded in `22-human-runtime-acceptance-amendment.md`.

The independent P2 remains a required code repair. The narrow packet is:

```text
manual-fix-T1-launchd-service-review2-P2.prompt.md
manual-fix-T1-launchd-service-review2-P2.tool-policy.json
manual-fix-T1-launchd-service-review2-P2.dispatch.md
```

It assigns the same eligible `zhipu_glm` author, explicitly invokes
`senior_developer`, allows edits only to `scripts/service-control.py` and
`scripts/tests/test_service_control.py`, denies Bash/launchctl/tests/git, and
requires bounded post-bootstrap health/readiness proof for install/restart.
This formal-review repair increments `rework_count` to 1.

No P2 delivery-code change has been made yet.

本地北京时间: 2026-07-13 22:29:59 CST
下一步模型: Claude-GLM / GLM-5.2（human-dispatched fix author）
下一步任务: 执行窄范围 P2 prompt，仅修改 service-control.py 及其测试并返回 Session ID

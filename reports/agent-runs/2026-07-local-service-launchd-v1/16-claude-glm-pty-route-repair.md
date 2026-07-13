# Claude-GLM PTY Route Repair

## Operator Direction

The operator rejected a manual-interactive replacement because it cannot
preserve the auto-review path to review-1, and explicitly requested the proposed
PTY test. The test is therefore implemented as a registered runner transport,
not as an unreceipted direct model invocation.

## Route Evidence

- Manual session `fdda0f8b-8332-448e-ab92-464a4b592545` used
  `entrypoint=cli`, `promptSource=typed`, and returned from `glm-5.2` in about
  five seconds.
- Auto attempt 2 session `8f6d02c1-c12e-4762-8c4a-f42ba4404ff3` used
  `entrypoint=sdk-cli`, `bypassPermissions`, and returned a synthetic zero-token
  API 529 after about 181 seconds.
- Auto attempt 3 session `19be0bc5-7a4c-4e6d-a0e8-7b4e16ba3758` used
  `entrypoint=sdk-cli`, `acceptEdits`, and returned a synthetic zero-token API
  529 after about 186 seconds.
- The immutable runner prompt is only 453 bytes. Permission mode and prompt
  size do not explain the repeated route-specific pattern.

## Harness-Preserving Repair

`scripts/model-adapters/claude-glm-pty-wrapper` now:

1. reads the runner-owned immutable prompt file;
2. invokes the existing absolute zsh wrapper inside a real pseudo-terminal;
3. supplies the prompt positionally and never uses `-p`;
4. assigns a fresh session UUID and watches only that persisted transcript;
5. accepts success only after a final real assistant text turn records
   `entrypoint=cli`;
6. fails closed on `<synthetic>` provider errors, `sdk-cli`, missing terminal
   turns, or timeout;
7. exits the TUI and returns raw terminal bytes to the unchanged auto runner.

The runner remains the sole automatic dispatcher, call accountant, receipt
writer, seal authority, and next-hop controller. A successful implementation
still proceeds through the frozen blocking checks, embedded cross-check, seal,
and Grok review-1. No manual transcript is promoted as implementation or review
evidence.

The lower `claude-glm-wrapper` still strips the legacy alias-level bypass in
memory. Normal implementation uses `acceptEdits`; review uses `plan`; only the
explicit yolo registry route adds bypass.

## Local Verification

```text
python3 -m py_compile scripts/model-adapters/claude-glm-pty-wrapper
PASS

PTY + production registry focused suite
Ran 13 tests
OK

python3 -m unittest scripts.tests.test_auto_review_runner scripts.tests.test_validate_stage_auto_review
Ran 114 tests
OK

git diff --check
PASS
```

The fake-CLI integration covers a real PTY on stdin/stdout, `entrypoint=cli`
transcript gating, TUI exit, the lower zsh wrapper, and removal of alias-level
bypass. No real model was invoked during implementation or tests. No `.env`,
alias expansion, credential, delivery code, or real `launchctl` state was read
or changed.

本地北京时间: 2026-07-13 16:22:14 CST
下一步模型: Codex bookkeeper
下一步任务: 提交 PTY route 修复并创建 superseding authorization v4

# V3 Prerequisite Repair — Permission And Evidence Integrity

## Human Direction And Review Inputs

The operator directed the bookkeeper to absorb mandatory findings and retry
Claude-GLM. Read-only inputs included:

- Grok session `019f59c9-1145-73c2-81a0-a7e928ad11eb`;
- Claude session `d9f08990-e662-40c7-b7b9-b08d7aef7b0b`;
- committed wrapper/registry/runner code and attempt-1/attempt-2 evidence;
- the local alias classification without printing its expansion or values.

Both reviewers accepted the absolute wrapper. This repair promotes the raw-path
reuse and stderr-loss notes to mandatory pilot fixes, adds the alias-level
permission separation missed by both sessions, and repairs the discontinuous
v2 mode history detected by the bookkeeper.

## Mandatory Repairs

1. The wrapper removes a legacy alias-level
   `--dangerously-skip-permissions` token in memory. It never rewrites or logs
   the user's profile. Registry policy now supplies `acceptEdits` for normal
   implementation, `plan` for reviews, and bypass only for `yolo_command`.
2. Adapter stderr is merged into the single raw evidence pipe so provider/CLI
   failures cannot disappear when stdout is empty.
3. Raw filenames include the next runner receipt sequence. A later authorization
   can no longer overwrite an earlier attempt's bytes.
4. Terminal escalation artifacts inherit the last receipt, raw-output, and
   verdict paths when available.
5. `scripts/validate-stage.py` now checks mode-history continuity and requires
   the final transition state to match the current runner state.
6. The duplicate v2 `new_human_authorization` row was removed only after exact
   pre-repair status/handoff snapshots were placed in `history/`. Future
   superseding authorization preparation changes the authorization path only;
   while status is `awaiting_human`, the runner alone records
   `superseding_human_authorization`.

## Historical Evidence Repair

- The original attempt-1 compatibility raw path is restored to its original
  zero-byte content.
- Attempt-2 API 529 bytes move to the unique
  `runner-2-implementation-T1-launchd-service-attempt1.raw-output.md` path.
- The original pre-repair receipt and overwritten raw file remain verbatim in
  `history/`; `runner-2-implementation.receipt.json` is mechanically rebound to
  the unique attempt-2 path and revalidated.

## Verification

```text
/bin/sh -n scripts/model-adapters/claude-glm-wrapper
PASS

targeted permission/raw/stderr/history tests
Ran 44 tests
OK

python3 -m unittest scripts.tests.test_auto_review_runner scripts.tests.test_validate_stage_auto_review
Ran 111 tests
OK
```

No model was invoked during these repairs. No `.env` content, alias expansion,
credential, real `launchctl` mutation, or delivery code was touched.

本地北京时间: 2026-07-13 15:37:35 CST
下一步模型: Codex bookkeeper
下一步任务: 校验并提交 v3 前置修复，然后创建 superseding authorization v3

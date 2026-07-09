# Bookkeeper Inspection

## Result

REWORK before delivery commit. The implementation is not ready for review-1.

## Finding

### P1: `record-checkpoint --single-owner --dry-run` still mutates the repository

`12-development-breakdown.md` defines the dry-run contract as:

```text
--single-owner --dry-run # 只打印不写入（兼容旧行为）
```

and the F3 acceptance criteria say:

```text
--dry-run 模式只打印不修改文件。
```

The current implementation in `scripts/record-checkpoint` calls `git add -A`
and may create the pending content commit before it checks `args.dry_run`.
That means dry-run avoids writing `status.json`, but it can still change
`HEAD` and the index. This violates the stage acceptance criteria.

The new test in `scripts/tests/itbm_dry_run.py` only checks that
`status.json.base_sha` and `status.json.head_sha` remain `null`; it does not
check that `git rev-parse HEAD` and `git status --short` are unchanged.

## Required Fix

- Handle `--dry-run` before any `git add`, `git commit`, `status.json` write, or
  index mutation.
- Update docs that currently say dry-run keeps the older behavior
  "commit pending + print fingerprint".
- Add a regression assertion that `--dry-run` leaves both `HEAD` and
  `git status --short` unchanged.
- Rerun:

```bash
python3 scripts/tests/itbm_dry_run.py
python3 -m py_compile scripts/validate-stage.py scripts/_itbm.py
python3 scripts/tests/test_validate_stage.py
python3 scripts/validate-stage.py 2026-07-harness-friction-fixes-v1 --phase checkpoint
```

本地北京时间: 2026-07-09 17:48:05 CST
下一步模型: claude_glm
下一步任务: fix dry-run semantics and update tests/docs

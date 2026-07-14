# Manual Delivery Amendment

This amendment changes delivery mechanics only. It does not change the product
requirements in `00-task.md`, `10-design.md`, `11-adr.md`, or the implementation
contracts and test matrix in `12-development-breakdown.md`.

## Superseded V1 Process Text

The following v1-only material is non-normative in v2:

- `auto-review-pipeline/v1`, authorization budgets, receipts and runner state;
- automatic seal, empty/seen-patch binding, and Grok-primary auto review-1;
- runner-owned tests, commits, status updates, or implementation reports;
- the v1 OpenAI Harness-code-author review-2 exclusion tied to commits
  `871e546` / `dd74cd2`.

## V2 Manual Routing

- The human starts a fresh Claude-GLM implementation terminal.
- Claude-GLM may edit only the seven frozen backend source/test files and
  `20-implementation.md`.
- Claude-GLM must not edit `status.json`, `70-handoff.md`, formal review files,
  canonical `docs/**`, schemas, frontend files, or Harness files, and must not
  commit.
- The bookkeeper runs or independently reruns final tests, records raw evidence,
  creates the committed review range, and prepares review dispatch.
- Review-1 uses a fresh read-only Kimi session because the implementer provider
  is `zhipu_glm`.
- Review-2 routing is decided after review-1 under provider isolation rules.

## Frozen Write Boundary

- `backend/config.py`
- `backend/adapters/binance_public.py`
- `backend/services/private_client.py`
- `backend/services/snapshot_service.py`
- `backend/tests/test_config.py`
- `backend/tests/test_background_worker.py`
- `backend/tests/test_private_client.py`
- `reports/agent-runs/2026-07-cache-refresh-scheduler-v2/20-implementation.md`

If `backend/domain/snapshot.py`, another backend file, or any new product file
is required, stop and report the evidence instead of editing it.

## Test Contract

Focused during implementation:

- `python3 -m pytest backend/tests/test_config.py`
- `python3 -m pytest backend/tests/test_background_worker.py`
- `python3 -m pytest backend/tests/test_private_client.py`

Final blocking command:

- `python3 -m pytest backend/tests`

本地北京时间: 2026-07-14 22:41:45 CST
下一步模型: human → claude_glm
下一步任务: 在人工派发模式下实现七文件边界内的缓存刷新调度

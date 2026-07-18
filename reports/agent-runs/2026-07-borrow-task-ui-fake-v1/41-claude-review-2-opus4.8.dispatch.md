# Human Dispatch Packet — Review-2 / Opus 4.8

## Operator Command

Run this command manually from the repository root. It is read-only/plan mode; do not add write permission flags.

```bash
claude --model opus4.8 --permission-mode plan \
  --json-schema "$(cat schemas/review-verdict.schema.json)" \
  -p "$(cat reports/agent-runs/2026-07-borrow-task-ui-fake-v1/41-claude-review-2-opus4.8.dispatch.md)" \
  | tee reports/agent-runs/2026-07-borrow-task-ui-fake-v1/50-review-2.md
```

The `tee` output is the raw evidence. Do not edit, wrap, summarize, or append to `50-review-2.md` after the model finishes. If the CLI prints a provider-native Session ID separately, record it for the bookkeeper.

---

You are the final, read-only Review-2 reviewer for stage `2026-07-borrow-task-ui-fake-v1`.

You are Anthropic Opus 4.8. The Anthropic provider previously authored this stage's development breakdown (`12-development-breakdown.md`) but wrote no reviewed delivery or fix code. The reviewed code authors are Zhipu GLM (backend B1) and Moonshot Kimi (frontend F2/F3). This review is permitted only under the disclosed strong-reviewer override in `66-review-2-strong-reviewer-override.md`. Treat the approved task/amendments and product documents as requirements; treat design/breakdown as evidence under review. Disclose `reviewer_prior_involvement: "breakdown"` in the final JSON verdict.

## Fixed Review Coordinates

- Branch: `stage/2026-07-borrow-task-ui-fake-v1`
- Base: `d9c2772b7725bc794224a99c70505526eaedf295`
- Delivery head: `9d53204d450ee0dc4519f52201b575e5b71e948b`
- Required fingerprint:

```text
9d53204d450ee0dc4519f52201b575e5b71e948b:a51dccee4055065ceece4ee3cee037909c096da4cf36a55144d945e757d025f3
```

Review exactly this committed range, never moving `HEAD`:

```bash
git diff --binary d9c2772b7725bc794224a99c70505526eaedf295..9d53204d450ee0dc4519f52201b575e5b71e948b -- . ':(exclude)reports/agent-runs/2026-07-borrow-task-ui-fake-v1/status.json'
```

Later evidence commits must not be treated as delivery-code changes.

## Required Reading

Read the raw artifacts, not only this packet:

- `AGENTS.md`
- `workflows/templates/stage-delivery.yaml` (Review-2 and final-gate sections)
- `schemas/review-verdict.schema.json`
- `docs/product/PRD.md`
- `docs/architecture/ARCHITECTURE.md`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/00-task.md`
- `10-design.md`, `11-adr.md`, `12-development-breakdown.md`
- `13-scope-amendment-v2.md`, `14-user-min-borrow-contract-amendment.md`
- `20-implementation.md`, `21-implementation-backend.md`, `22-implementation-frontend-v2.md`, `23-implementation-frontend-visual-fix.md`
- `60-test-output.txt`, `61-test-output-backend.txt`, `62-test-output-frontend-v2.txt`, `64-test-output-frontend-visual-fix.txt`, `65-pre-review-validation-f3.txt`
- Valid task Review-1 raw outputs: `31-review-1-backend-retry-1.md`, `32-review-1-frontend-retry-1.md`
- Invalid first attempts retained for audit: `31-review-1-backend.md`, `32-review-1-frontend.md`
- `66-review-2-strong-reviewer-override.md`
- Relevant delivery files from the fixed diff, especially:
  - `backend/services/private_client.py`
  - `backend/domain/snapshot.py`
  - `schemas/api/public-market/snapshot.schema.json`
  - `backend/tests/test_private_client.py`
  - `backend/tests/test_private_account_v1.py`
  - `backend/tests/test_phase2_borrow_sort.py`
  - `frontend/index.html`
  - `frontend/self-check.js`

Independently run read-only deterministic checks appropriate to the fixed head, at minimum:

```bash
git diff --check d9c2772b7725bc794224a99c70505526eaedf295..9d53204d450ee0dc4519f52201b575e5b71e948b
python3 -m pytest backend/tests -q
node frontend/self-check.js
```

Do not modify files, use credentials, invoke live Binance writes, make borrow/repay/transfer/order requests, or start background loops.

## Review Focus

Verify all frozen requirements across the fixed range:

1. Fake borrow-task UI: two validated market inputs plus confirm; HOME task creation; sidebar view; no borrow `fetch`, timer/retry loop, persistence, or external write.
2. Lifecycle, task editing, soft deletion, filters, action-button disabled matrix, and green/grey/red action themes.
3. No duplicate `已借完` display; minimum-borrow placeholder behavior, including raw zero cases and escaped text.
4. Backend `userMinBorrow` raw-string mapping and matching lookup gates; exactly two-decimal `ROUND_HALF_UP` USDT value; unchanged eight-decimal max-borrow value; strict schema and test/raw-sample evidence.
5. Regression safety, factual test evidence, diff scope, and whether any reported P3/residual risks should be elevated.

Known context to assess independently:

- Task-list whole-view rerenders clear unsubmitted edits in other cards after an action; prior Review-1 classified it P3/non-blocking.
- Browser visual and DevTools Network manual checks were not performed in the implementation environment; DOM-level self-checks cover the fake behavior.
- All 409 factual `userMinBorrow` sample values are raw `"0"`; non-zero conversion is synthetic-test covered.
- The top-level Review-1 aggregation issue is a Harness-validator concern planned for a subsequent repair. It does not replace this code review or authorize omission of a code finding.

## Required Output Contract

Write a human-readable review narrative, then the required navigation footer, then one raw JSON object matching `schemas/review-verdict.schema.json` as the final bytes of the file.

- Do not put the final JSON inside Markdown fences.
- Do not add a trailing newline, Markdown fence, or commentary after the final `}`.
- JSON must use `role: "final_reviewer"`, `model: "opus4.8"`, the exact fixed fingerprint above, and `reviewer_prior_involvement: "breakdown"`.
- In `reviewer_prior_involvement_notes`, cite `66-review-2-strong-reviewer-override.md` and state that Anthropic authored the breakdown only, not reviewed delivery/fix code.
- `ACCEPT` requires no unresolved P0/P1/P2 findings. Set `next_action: "stage_accepted_waiting_user"` only if you accept.
- If `REWORK`, include every P0–P3 finding with concrete file/line evidence and include a ready-to-send `fix_start_prompt` preserving exact findings, file boundaries, test commands, and raw evidence paths.
- If the verdict cannot comply with the strict JSON contract, return `next_action: "retry"`; do not emit malformed JSON.

Your entire response will be saved verbatim to `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/50-review-2.md` by the operator.

当前 Session ID: unavailable (prepared dispatch packet; no model execution occurred in this session)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-borrow-task-ui-fake-v1/41-claude-review-2-opus4.8.dispatch.md
本地北京时间: 2026-07-19 01:36:38 CST
下一步模型: Opus 4.8（由人类操作员只读执行）
下一步任务: 审阅固定范围并将原始输出写入 50-review-2.md

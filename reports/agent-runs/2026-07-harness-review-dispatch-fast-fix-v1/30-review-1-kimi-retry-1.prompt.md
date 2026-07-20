<!-- ===== DISPATCH RECEIPT =====
status: invalid_output
target_model: kimi-code/kimi-for-coding / moonshot_kimi
executor: human_operator
resume_session: session_c18a8dee-303f-4973-8b0b-61f13d304b9a
adapter_cmd: kimi -S session_c18a8dee-303f-4973-8b0b-61f13d304b9a --model kimi-code/kimi-for-coding -p "$(cat reports/agent-runs/2026-07-harness-review-dispatch-fast-fix-v1/30-review-1-kimi-retry-1.prompt.md)"
started_at:
completed_at: 2026-07-20T10:39:00+08:00 (minute observed from raw artifact mtime)
session_id: session_c18a8dee-303f-4973-8b0b-61f13d304b9a
session_id_source: operator
producer_exit_status: 0
raw_output: reports/agent-runs/2026-07-harness-review-dispatch-fast-fix-v1/30-review-1-retry-1.raw-output.md
verdict_output: reports/agent-runs/2026-07-harness-review-dispatch-fast-fix-v1/30-review-1-retry-1.verdict.json
next_dispatch: reports/agent-runs/2026-07-harness-review-dispatch-fast-fix-v1/30-review-1-kimi-retry-2.prompt.md (executor: human_operator)
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY (immutable after dispatch) ===== -->

This is evidence-capture retry 1 for the formal Review-1 you already performed
in this same Kimi session. Attempt 1 is non-accepting only because its stdout and
producer exit status were not captured; no verdict has been recorded.

Read and follow the complete original review contract in
`reports/agent-runs/2026-07-harness-review-dispatch-fast-fix-v1/30-review-1-kimi.prompt.md`.
Reconfirm the committed range and findings as needed. Do not edit files, invoke
another model, commit, or write the raw/verdict artifacts yourself.

Your entire stdout for this retry must be exactly one JSON object matching
`schemas/review-verdict.schema.json`, with no Markdown fence, heading,
narrative, footer, or trailing commentary. Preserve the original required
stage ID, role, model, and exact diff fingerprint. If the verdict is REWORK,
include the complete schema-valid `fix_start_prompt` required by the original
contract.

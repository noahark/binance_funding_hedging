<!-- ===== DISPATCH RECEIPT（human operator fills after execution） =====
status:        pending_human_execution
target_model:  claude / anthropic / claude-fable-5
adapter_cmd:   claude --model claude-fable-5 --permission-mode plan --json-schema "$(cat schemas/review-verdict.schema.json)" -p "$(cat reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/review-2-claude.prompt.md)"
executor:      human_operator
started_at:    unavailable: pending human execution
completed_at:  unavailable: pending human execution
session_id:    unavailable: pending human execution and verification
outputs:       reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/50-review-2.md (pending verbatim capture)
next_dispatch: executor: human_operator — run Fable5 in a fresh read-only Anthropic session and return raw output/receipt; do not invoke Opus unless Fable5 returns a qualifying quota/unavailability failure
===== END RECEIPT ===== -->

# Task H Final Review-2 — Claude Human-Operator Dispatch

## Prepared Packet

- Stage: `2026-07-harness-verdict-extractor-fix-v1`
- Role: `review-2` / `final_reviewer`
- Skill: `reality_checker`
- Prompt:
  `reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/review-2-claude.prompt.md`
- Expected raw artifact:
  `reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/50-review-2.md`
- Preferred provider/model: `claude` / `anthropic` / `claude-fable-5`
- Quota fallback model: `opus4.8`, only after a recorded qualifying Fable5
  failure at an Anthropic endpoint
- Adapter references: `docs/model-adapters.md#claude`
- Local binary availability: `/Users/ark/.local/bin/claude`
- Executor: `human_operator`
- Fresh read-only/plan session required: yes
- Reviewer prior involvement: `none`
- Routing reason: Codex/GPT authored the maintenance design and acts as
  bookkeeper, so the default Codex final-review primary is anti-self-review
  ineligible; unrelated Anthropic Claude is selected.
- Base SHA: `4b1fcdd5fb0562eb00467437bf2ec9ad0286581a`
- Reviewed Head SHA: `569be63a6f467e4e5e255a4713f94a08e37cd9b8`
- Diff fingerprint:
  `569be63a6f467e4e5e255a4713f94a08e37cd9b8:397f66903914de11923195e8831f3192f725dc771fd04893a790075c9765b655`
- Status: `pre_review_passed_waiting_human_dispatch`
- Prepared at: `2026-07-21 19:43:11 CST`
- Credential/environment dump or network access authorized: no
- Repository writes by reviewer authorized: no
- Model/bookkeeper self-dispatch authorized: no

The human operator first runs the Fable5 command from the machine receipt in a
fresh Anthropic-authenticated terminal. Do not inherit the Claude-GLM/Zhipu
endpoint override. Do not execute `opus4.8` merely for a second opinion after a
valid Fable5 verdict. If Fable5 returns a qualifying quota/auth/service/timeout
failure, stop, preserve that runner output, and return it to the bookkeeper so
the Opus fallback can be recorded and routed correctly.

Capture the complete reviewer response verbatim in `50-review-2.md`, including
narrative, six-line footer, and the final strict JSON object. Do not summarize
or rewrite evidence.

## Receipt — Human Operator Fills After Execution

- Exact executed command or terminal mode:
- Anthropic endpoint/auth isolation confirmed:
- Started at:
- Completed at:
- Actual model:
- Provider-native Session ID:
- Session ID source and verification evidence:
- Raw output captured verbatim:
- Final JSON object present and nothing follows it:
- Schema validation result:
- Independently recomputed fingerprint:
- Verdict and finding summary:
- Result/notes:

当前 Session ID: unavailable (current runtime does not expose provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/review-2-claude.dispatch.md
本地北京时间: 2026-07-21 19:43:11 CST
下一步模型: human operator → fresh Claude / claude-fable-5
下一步任务: execute the final read-only review at the Anthropic endpoint, capture 50-review-2.md verbatim, fill the receipt, and return it to bookkeeper

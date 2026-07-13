# Auto v5 Interruption And Human-Dispatch Takeover

## Human Decision

The human operator explicitly directed the stage to leave auto mode, transfer
control to manual human dispatch, and finish `T1-launchd-service` before
returning to Harness hardening.

This is the frozen `explicit_human_mode_flip_decision` transition from
`auto_review/awaiting_human` to `human_dispatch/null`. Auto execution is
disabled; authorization v5 and its evidence remain historical and are not
reused.

## Interrupted Attempt 5

The first v5 runner lifetime passed preflight, wrote the updated implementation
prompt and `runner-5-implementation.tool-policy.json`, and started a real
Claude-GLM session:

```text
session_id=359a6504-9d1b-4c58-81e5-51f93c1b2948
model=glm-5.2
entrypoint=cli
permission_mode=dontAsk
Read=27
Glob=3
Edit=0
Write=0
Bash=0
tool_results=30
tool_result_errors=0
end_turns=0
```

The process ended before the adapter returned, so sequence-5 raw output and
receipt were not written. A later runner lifetime saw the unit as already
started and stopped fail-closed with `recoverable_resume_unverifiable_unit`.
No delivery file changed.

Although `status.json` still held `model_calls_used=4`, the persisted Claude
transcript proves that an adapter/model call occurred. The manual-takeover
checkpoint corrects cumulative usage to `model_calls_used=5` without inventing
a receipt or raw-output artifact.

## Preserved Evidence

- `implementation-T1-launchd-service.prompt.md`: updated immutable prompt from
  the interrupted first v5 lifetime.
- `runner-5-implementation.tool-policy.json`: exact bounded policy used by that
  lifetime.
- `runner-5-interrupted-transcript-metadata.json`: secret-free structured
  transcript metadata; the raw local Claude transcript is not copied.
- `80-escalation-recoverable_resume_unverifiable_unit-20260713T104052Z.md`:
  deterministic second-lifetime fail-closed evidence.

No missing sequence-5 receipt is fabricated. The prior sequence-4 receipt
remains the last actual runner receipt.

## Manual Implementation Route

Implementation ownership remains `claude_glm` / `zhipu_glm`. The human operator
executes the committed packet in a fresh foreground session:

- prompt: `manual-implementation-T1-launchd-service.prompt.md`;
- tool policy: `manual-implementation-T1-launchd-service.tool-policy.json`;
- command packet: `manual-implementation-T1-launchd-service.dispatch.md`.

The manual policy retains only `Read`, `Glob`, `Grep`, `Edit`, and `Write`,
keeps `Bash` unavailable, and narrows writes to the five delivery files frozen
by the development breakdown. `scripts/run-server.sh` is readable but not
writable. The bookkeeper will run all frozen tests after the model returns.

本地北京时间: 2026-07-13 18:54:53 CST
下一步模型: Claude-GLM / GLM-5.2（human dispatch）
下一步任务: 在全新前台会话执行人工实现包，完成 T1 代码但不运行测试或写 Harness 状态

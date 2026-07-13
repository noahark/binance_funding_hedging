# Claude-GLM PTY Probe Result

## Result

The runner-owned PTY route test proved the route hypothesis and removed API 529
from the call path:

- runner receipt sequence: `4`;
- Claude session: `76a8e532-1414-43f7-919e-4b57a0b28558`;
- user route: `entrypoint=cli`, `promptSource=typed`,
  `permissionMode=acceptEdits`;
- actual assistant model: `glm-5.2`;
- actual model records: `8`;
- synthetic provider errors: `0`;
- API 529 mentions: `0`;
- Bash tool uses: `4`;
- Bash tool results: `3`;
- final `end_turn`: absent.

The first real model turn arrived approximately 41 seconds after dispatch.
Three Bash calls returned tool results. The fourth, a read-oriented
`find ... -exec cat` command, remained without a tool result for more than two
minutes, consistent with an interactive permission confirmation under
`acceptEdits`.

The bookkeeper did not approve the command and did not switch to yolo. After
the route test objective was satisfied, it terminated only the stuck Claude
child process group. The PTY adapter then returned exit `143` without a final
turn; the unchanged runner charged one call, wrote a schema-valid sequence-4
receipt/raw artifact/escalation, and stopped fail-closed.

## Harness Meaning

The absolute wrapper and PTY transport are now verified. The former 529 was a
`sdk-cli` route compatibility problem, not a global `glm-5.2` outage and not an
`acceptEdits` versus bypass distinction.

The next blocker is separate: an interactive `cli` implementation session may
pause on Claude Code tool permissions. Manual approval would break unattended
auto execution and is not promoted to review-1. Before another authorization,
the stage needs an explicit permission policy that stays within the approved
scope and does not silently restore alias-level yolo.

No delivery file changed, no frozen delivery test ran, and no real
`launchctl` mutation occurred. The raw TUI bytes are preserved at
`runner-4-implementation-T1-launchd-service-attempt1.raw-output.md`; the local
structured transcript remains identified by the session UUID above.

本地北京时间: 2026-07-13 16:44:12 CST
下一步模型: human
下一步任务: 决定 PTY auto adapter 的显式工具权限策略，再决定是否签发 v5

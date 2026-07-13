# Human Dispatch Packet — Claude-GLM T1 Implementation

Use a fresh foreground terminal/session. Do not reuse the interrupted v5 Claude
session and do not run this command in the Kimi runner-host session.

The human operator executes exactly:

```bash
cd '/Users/ark/Desktop/ai code/funding_hedging' && '/Users/ark/Desktop/ai code/funding_hedging/scripts/model-adapters/claude-glm-pty-wrapper' --model glm-5.2 --policy implementation-v1 --tool-policy-file '/Users/ark/Desktop/ai code/funding_hedging/reports/agent-runs/2026-07-local-service-launchd-v1/manual-implementation-T1-launchd-service.tool-policy.json' --prompt-file '/Users/ark/Desktop/ai code/funding_hedging/reports/agent-runs/2026-07-local-service-launchd-v1/manual-implementation-T1-launchd-service.prompt.md'
```

Run it once in the foreground and allow the registered adapter timeout. Do not
background, relaunch, resume, or manually approve additional tools. The frozen
policy uses `dontAsk`, allows only the five implementation tools, and denies
`Bash`.

When it exits, return the exit code and the final
`HARNESS_PTY_SESSION_ID=<uuid>` marker to the Codex bookkeeper. Do not run tests
or commit; the bookkeeper owns deterministic verification and evidence commits.

本地北京时间: 2026-07-13 18:54:53 CST
下一步模型: Claude-GLM / GLM-5.2（fresh foreground human dispatch）
下一步任务: 完成 T1 五个允许文件的实现并返回 session id

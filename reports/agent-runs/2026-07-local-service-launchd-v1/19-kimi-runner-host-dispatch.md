# Kimi Runner-Host Dispatch — Authorization v5

你是本 stage 的 Kimi runner host（运行器宿主），不是 implementer、fix
author、reviewer 或 bookkeeper。请只启动并监看仓库内的 deterministic
runner；不要自行分析或实现任务，不要直接调用任何 model adapter，不要编辑
文件，不要运行独立测试/git/commit/status 命令，也不要写 `status.json` 或
`70-handoff.md`。所有模型调用、检查、提交、receipt 和状态转移只能由 runner
产生。

开始前，按根 `AGENTS.md` 的 `Session Bootstrap` / `Startup Read Budget` 仅做
只读恢复：读取 active workflow 的相关 auto-review 段、`ACTIVE.json` 指向的
`status.json` 与 handoff recovery header、`status.current_inputs` 和 v5 授权；
不要递归扫描 `reports/agent-runs/`，不要读取 `history/`。完成只读恢复后，
在下面的绝对路径中只执行这一条 shell 命令：

```bash
cd '/Users/ark/Desktop/ai code/funding_hedging' && python3 scripts/auto-review-runner.py 2026-07-local-service-launchd-v1
```

执行约束：

- 让 runner 自己完成 full preflight（完整前置校验）并消费已提交的
  `auto-run-authorization-v5.json`。
- 不要中断注册表内的正常 adapter timeout；runner 退出后再报告结果。
- 若 preflight 失败、runner 停在 `awaiting_human`、产生 `80-*.md` escalation
  或要求人工决定，立即停止，不做手工重试、不改成 human dispatch。
- 不要运行 `launchctl bootstrap`、`bootout`、`kickstart` 等真实 LaunchAgent
  mutation，不读取 `.env`，不打印 alias 展开或环境变量。
- 本 host session 不得复用为 Kimi implementation/review fallback；如 runner
  需要 Kimi fallback，必须由其按合同创建新隔离调用。
- runner 结束后只回报 exit code、最终 `status.json` 的
  `status`/`runner_state`/`next_action`，以及 runner 生成的最新 receipt、raw
  output、test、verdict 或 escalation 路径；不要代替 runner 修复。

本地北京时间: 2026-07-13 18:28:16 CST
下一步模型: Kimi（runner host only）
下一步任务: 执行唯一 runner 命令并等待其自行完成或安全停止

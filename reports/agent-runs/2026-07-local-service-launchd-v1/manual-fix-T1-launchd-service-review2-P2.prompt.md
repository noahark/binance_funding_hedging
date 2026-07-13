# Manual Review-2 P2 Repair — T1 launchd service

显式使用 `senior_developer` skill（高级开发者执行规范）。你是本阶段原实现/修复作者
`claude_glm` / `zhipu_glm`，负责一次窄范围 review-2 修复；你不是 reviewer，也不是
bookkeeper。

开始前读取以下原始权威与证据：

```text
AGENTS.md
workflows/templates/stage-delivery.yaml
agents/developer-discipline.md
agents/skills/senior-developer.md
reports/agent-runs/2026-07-local-service-launchd-v1/10-design.md
reports/agent-runs/2026-07-local-service-launchd-v1/13-software-architect-amendment.md
reports/agent-runs/2026-07-local-service-launchd-v1/22-human-runtime-acceptance-amendment.md
reports/agent-runs/2026-07-local-service-launchd-v1/manual-review-2-T1-launchd-service.opus.raw-output.md
reports/agent-runs/2026-07-local-service-launchd-v1/manual-review-2-T1-launchd-service.opus.verdict.json
scripts/service-control.py
scripts/tests/test_service_control.py
```

只允许编辑：

```text
scripts/service-control.py
scripts/tests/test_service_control.py
```

只使用 `Read`、`Glob`、`Grep`、`Edit`、`Write`。禁止调用 Bash、Python、pytest、
py_compile、git、launchctl、网络工具或任何其他命令；不得读取 `.env`、不得启动服务、
不得改写 stage evidence。所有命令检查、测试和提交由 Codex bookkeeper 执行。

## 必修问题

修复正式 review-2 的 P2：`install()` 与 `restart()` 当前在
`launchctl bootstrap` 返回 0 后立即打印成功，即使服务随后立刻退出或始终未就绪。

实现必须满足：

1. 在 `install()` 和 `restart()` 的 bootstrap 成功后执行一个有界、可测试的
   post-bootstrap readiness 轮询。不得使用无界循环。
2. 只有 `/healthz` 和 `/readyz` 都返回 HTTP 200，命令才可打印原成功信息并返回 0。
   `503`、连接失败或其他非 200 结果应在界限内继续等待；界限耗尽后返回非零。
3. 默认等待窗口必须是明确常量且适合真实冷启动，建议上限 60 秒、1 秒间隔；测试必须
   通过注入/monkeypatch 的 probe 与 sleeper 在零真实等待、零真实网络下完成。保持
   Python 3.9 兼容。
4. 超时时输出固定、脱敏、可操作的 stderr：说明服务未在期限内 ready，并引导操作者运行
   `status`、`doctor`，必要时执行 `stop --confirm`。不得输出 base URL、HTTP body、异常文本、
   环境变量或秘密；不得打印成功信息。
5. 不要在此修复中增加静默 repository relocation、权限请求、plist 删除或未要求的
   launchctl 清理行为。保留 plist/log，以便人工诊断；命令失败语义由非零退出明确表达。
6. 保持原有 `bootout -> bootstrap` 顺序、`--confirm` 门、argv 构造、错误分类、脱敏、
   `.env` 隔离和真实 launchctl 测试隔离不变。
7. 添加确定性回归测试，至少覆盖：
   - install 在 health/ready 最终均为 200 后成功；
   - restart 在 health/ready 最终均为 200 后成功；
   - health 永远不可达时按固定调用上限失败；
   - health=200 但 ready=503 时按固定调用上限失败；
   - 失败输出不含 dummy URL、body、exception/secret bytes，也不含成功文本；
   - 测试不真实 sleep、不真实访问网络、不调用真实 launchctl；
   - 原有 install/restart argv 顺序与日志目录断言仍成立。

不要修改 `start()` 的外部契约，除非共享私有 helper 的机械复用确有必要；不要扩大到其他
命令或文件。

完成后只返回简洁报告：实际修改的两个文件、readiness helper/界限/失败行为、增加的测试，
以及 Claude Session ID。不要声称运行过任何命令或测试。

本地北京时间: 2026-07-13 22:21:30 CST
下一步模型: Codex bookkeeper
下一步任务: 审查两文件 diff，执行冻结测试，提交修复证据并准备新的完整 review-2

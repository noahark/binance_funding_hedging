# Formal Review-2 Full Recheck — 2026-07-local-service-launchd-v1

显式使用 `reality_checker` skill（现实校验终审规范）。你是
Claude/Anthropic Opus 4.8 的 fresh read-only final reviewer。你不是实现者、修复作者或
bookkeeper；不得修改任何文件。

## 固定身份与绑定

```text
stage_id=2026-07-local-service-launchd-v1
role=final_reviewer
model=claude-opus-4-8
reviewer_prior_involvement=breakdown
base_sha=3bb253a489bf2854d8b9d81060a45ca056e1cea2
head_sha=ed7d9e0a71d05aab15cc1ecad2f8197989b54b9d
diff_fingerprint=ed7d9e0a71d05aab15cc1ecad2f8197989b54b9d:75d865afaa68b0895e8c2843d8d5fcc264a4ab1b9feddb36dd2529a9ce49100e
implementation_and_fix_provider=zhipu_glm
```

你曾通过 Anthropic/Opus 4.8 编写 `12-development-breakdown.md`，所以必须如实填写
`reviewer_prior_involvement=breakdown` 并在 notes 中披露；你没有编写任何 delivery/fix
代码，因此 provider isolation 成立。不要使用旧 prompt 中面向 Codex 的身份常量。

## 必须完整读取的证据

只有实际读取下列每一项后才允许给出 `ACCEPT`。不得用 bookkeeper 摘要替代原始文件：

```text
AGENTS.md
workflows/templates/stage-delivery.yaml
docs/product/PRD.md
docs/architecture/ARCHITECTURE.md
agents/skills/reality-checker.md
schemas/review-verdict.schema.json
reports/agent-runs/2026-07-local-service-launchd-v1/00-intake.md
reports/agent-runs/2026-07-local-service-launchd-v1/00-task.md
reports/agent-runs/2026-07-local-service-launchd-v1/10-design.md
reports/agent-runs/2026-07-local-service-launchd-v1/11-adr.md
reports/agent-runs/2026-07-local-service-launchd-v1/12-development-breakdown.md
reports/agent-runs/2026-07-local-service-launchd-v1/13-software-architect-amendment.md
reports/agent-runs/2026-07-local-service-launchd-v1/20-implementation.md
reports/agent-runs/2026-07-local-service-launchd-v1/22-human-runtime-acceptance-amendment.md
reports/agent-runs/2026-07-local-service-launchd-v1/30-review-1.md
reports/agent-runs/2026-07-local-service-launchd-v1/40-fix-report.md
reports/agent-runs/2026-07-local-service-launchd-v1/50-review-2.md
reports/agent-runs/2026-07-local-service-launchd-v1/60-test-output.txt
reports/agent-runs/2026-07-local-service-launchd-v1/70-handoff.md
reports/agent-runs/2026-07-local-service-launchd-v1/status.json
reports/agent-runs/2026-07-local-service-launchd-v1/80-escalation-real-launchd-desktop-tcc-20260713T134341Z.md
reports/agent-runs/2026-07-local-service-launchd-v1/manual-review-1-T1-launchd-service.operator-forwarded-output.md
reports/agent-runs/2026-07-local-service-launchd-v1/manual-review-1-T1-launchd-service.verdict.json
reports/agent-runs/2026-07-local-service-launchd-v1/manual-review-2-T1-launchd-service.opus.raw-output.md
reports/agent-runs/2026-07-local-service-launchd-v1/manual-review-2-T1-launchd-service.opus.verdict.json
reports/agent-runs/2026-07-local-service-launchd-v1/manual-fix-T1-launchd-service-review2-P2-attempt1.raw-output.md
reports/agent-runs/2026-07-local-service-launchd-v1/manual-fix-T1-launchd-service-review2-P2-attempt2.raw-output.md
backend/app/server.py
backend/tests/test_service_health.py
deploy/launchd/com.aoke.funding-hedging.server.plist.template
scripts/service-control.py
scripts/tests/test_service_control.py
scripts/run-server.sh
```

同时必须检查精确 committed diff：

```text
git diff --binary 3bb253a489bf2854d8b9d81060a45ca056e1cea2..ed7d9e0a71d05aab15cc1ecad2f8197989b54b9d -- . ':(exclude)reports/agent-runs/2026-07-local-service-launchd-v1/status.json'
```

不要使用移动的 `HEAD` 代替固定 `head_sha`。可以进行只读文件/git 检查；禁止写文件、
读取 `.env`、启动服务、访问私有渠道、执行真实 `launchctl` 或做任何外部副作用。

## 终审重点

1. 完整复核五个交付文件及 `scripts/run-server.sh` 未改边界，不得只看 P2 delta。
2. 核对用户人工决策：当前 Desktop checkout 不迁移、不授予广域权限；本机由人工运行
   `scripts/run-server.sh` 验收。旧 exit-126/TCC 证据必须保留为环境限制，而不是伪装成
   launchd PASS。判断该人工 scope amendment 是否足以解除旧 P1。
3. 核对 P2：`install/restart` 只有在 `/healthz` 与 `/readyz` 均为 200 后才成功；默认
   60 秒窗口为 61 次 probe/60 次 sleep；最后一次失败后不再 sleep；超时非零且固定脱敏；
   plist/log 保留；无额外 launchctl 清理。
4. 核对测试隔离：88 个目标测试、301 个 backend 测试及其他冻结检查的原始输出；fake
   executor/probe/sleeper 不接触真实 launchctl、网络或用户 LaunchAgents。
5. 核对之前所有过程偏离均如实披露，并判断是否影响代码接受性。
6. 核对没有凭据、base URL、HTTP body、异常文本或 `.env` 泄漏。

## 输出合同

先用中文给出简洁、证据化的 reality-check。然后输出一个且仅一个完整 JSON object，作为
回复最后内容；不得截断字符串，不得在 JSON 后追加文字。JSON 必须通过
`schemas/review-verdict.schema.json`，并固定使用：

```text
model=claude-opus-4-8
reviewer_prior_involvement=breakdown
diff_fingerprint=ed7d9e0a71d05aab15cc1ecad2f8197989b54b9d:75d865afaa68b0895e8c2843d8d5fcc264a4ab1b9feddb36dd2529a9ce49100e
```

- `ACCEPT`：`next_action=stage_accepted_waiting_user`，不得包含开放 P0/P1 或 required fixes。
- `REWORK`：`next_action=continue`，必须包含 schema-valid `fix_start_prompt`，原样带上发现、
  文件边界、测试命令和验收条件。
- `BLOCKED`：`next_action=human_escalation_required`，明确不可由当前代码 scope 解决的阻断。

`reviewed_artifacts` 必须列出所有实际读取的上述文件与固定 git diff。若没有完整读取，禁止
`ACCEPT`。

本地北京时间: 2026-07-13 23:09:31 CST
下一步模型: Codex bookkeeper
下一步任务: 通过 Session ID 提取原始输出、验证 verdict schema/指纹并更新 stage 状态

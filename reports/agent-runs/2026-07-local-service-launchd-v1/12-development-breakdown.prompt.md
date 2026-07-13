# Development Breakdown Dispatch — Claude Fable5

You are the development breakdown author for stage
`2026-07-local-service-launchd-v1`. This is design work only. Do not implement
or modify delivery code, do not invoke `launchctl`, do not read `.env`, and do
not start the server.

Read:

```text
AGENTS.md
workflows/templates/stage-delivery.yaml
agents/registry.yaml
agents/developer-discipline.md
reports/agent-runs/2026-07-local-service-launchd-v1/00-intake.md
reports/agent-runs/2026-07-local-service-launchd-v1/00-task.md
reports/agent-runs/2026-07-local-service-launchd-v1/10-design.md
reports/agent-runs/2026-07-local-service-launchd-v1/11-adr.md
reports/agent-runs/2026-07-local-service-launchd-v1/status.json
scripts/run-server.sh
backend/app/server.py
backend/services/snapshot_service.py
```

Write only:

```text
reports/agent-runs/2026-07-local-service-launchd-v1/12-development-breakdown.md
```

The breakdown must freeze:

1. one serial owner and exact allowed/forbidden file set;
2. plist rendering and `launchctl` command semantics;
3. external-side-effect isolation proving tests never mutate the real user
   LaunchAgent domain;
4. `/healthz` and `/readyz` fixed response/status semantics;
5. durable logging and diagnostic redaction rules;
6. exact deterministic test commands matching `00-task.md`;
7. auto-run implementation/review focus and repair routing;
8. explicit non-goals and human-only live acceptance commands.

End the artifact with the repository-required Chinese footer. Return a concise
completion note naming the written file; do not claim implementation.

本地北京时间: 2026-07-13 12:35:49 CST
下一步模型: Claude Fable5
下一步任务: 编写 12-development-breakdown.md 后交回 Codex bookkeeper 验证

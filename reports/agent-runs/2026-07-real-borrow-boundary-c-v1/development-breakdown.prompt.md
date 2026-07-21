[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务的唯一执行者。
1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令（包括但不限于
   claude-glm -p、kimi -p、codex exec、grok）。需要其他模型时，输出
   ESCALATED 及原因并停止。
2. 禁止编造未实际执行的命令结果或未实际读取的文件内容；你写下的每一条
   执行记录都必须对应你本会话内真实发生的动作。
3. 你的评审/实现依据只能是本 prompt 列出的 raw artifact 路径与你自己
   实际读取的文件。

# Boundary C — Canonical Development Breakdown

你是本阶段注册的 development-breakdown author。首选模型是
`claude-fable-5`；只有在人类操作者确认 Fable5 配额耗尽时，才由同一份 prompt
切换到 `opus4.8`。这是设计拆解任务，不是实现任务。

## 唯一目标

读取下列原始材料，将已裁决且已由公开证据闭合的 Boundary C 设计收窄成正式
`reports/agent-runs/2026-07-real-borrow-boundary-c-v1/12-development-breakdown.md`。

只允许写这一份 canonical breakdown。不得修改产品代码、测试、schema、
`00-task.md`、`10-design.md`、`11-adr.md`、`status.json`、`70-handoff.md` 或
任何 canonical `docs/` 文件；不得开始实现、review 或 live Binance 调用。

## 必读材料

1. `AGENTS.md`
2. `workflows/templates/stage-delivery.yaml` 的 `development-breakdown` 节
3. `agents/registry.yaml` 的 `development_breakdown` 与 implementation routing
4. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/00-task.md`
5. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/10-design.md`
6. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/11-adr.md`
7. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/14-design-review-synthesis.md`
8. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/design-review-round-2.opus.raw-output.md`
9. `reports/api-samples/2026-07-real-borrow-boundary-c-v1/20260720T150836Z/evidence-index.md`
10. 同目录 `raw/` 的四份公开契约切片
11. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/12-development-breakdown.draft.md`
12. 与拆解边界相关的当前源码/测试：`backend/borrow_tasks/**`、
    `backend/services/private_client.py`、`backend/config.py`、
    `backend/app/server.py`、`schemas/api/borrow-tasks/**`、
    `frontend/index.html`、`frontend/self-check.js` 及匹配测试

`12-development-breakdown.draft.md` 只是历史草案，不是 authority。发生冲突时，
以 `AGENTS.md` → workflow/registry → round-2 §3/§5 → 已修订 task/design/ADR →
公开证据的顺序为准。

## 不得重开的人类/round-2 决策

- 单一串行、backend-dominant task；parallel mode 与 embedded review 均关闭。
- 实现 owner 为 `claude_glm` / `glm-5.2[1m]`，review-1 为 fresh Kimi；Codex
  不得实现或修复。
- 每个 SQLite DB 仅一个 execution owner：
  `<borrow_db_path>.lock` + `fcntl.flock(LOCK_EX | LOCK_NB)`，scheduler 前获取，
  process lifetime 持有；非 owner 继续提供读/任务 mutation API，但无 scheduler、
  无 dispatch，状态为 `not_execution_owner`。
- 统一 execution API：`GET /api/borrow-execution/status`、
  `POST /api/borrow-execution/start`、`POST /api/borrow-execution/stop`；Start/Stop
  无 body、幂等、200 返回同一 status document。
- `execution_enabled` fresh/migrated 默认 false；invalid executor mode 启动失败；
  live 缺 credentials 时服务继续但 blocked 且零 signed traffic。
- pending insert 必须在网络前原子复查全部 gate 并设置
  `unresolved_attempt_id`；任何 failed gate 均零 attempt row、零 POST。
- unknown 永不自动 POST retry；无 HTTP force-clear/retry-anyway。
- reconciliation 固定 `+5/+15/+60/+300/+900s`，仅 unique `CONFIRMED` match
  可证明 success；operator Stop 不阻断 GET，rate cooldown 阻断所有 signed
  borrow-client traffic；exhausted 永久 blocked/visible。
- cadence floor 由已验证的 6000/min 与 POST weight 100 计算为 2s，默认 5s；
  永不 catch up 历史 tick。
- 完整 resolve matrix、Start-at-target、eligibility count gate 均已冻结。
- `in_flight_attempt_id` 为瞬态内存；`unresolved_attempt_id` 为 durable blocker；
  cooldown 不折叠进 `can_execute`。
- exact live modules：
  `backend/services/portfolio_margin_borrow_client.py` 与
  `backend/services/live_borrow_executor.py`；signer 为
  `backend/services/binance_signing.py`；全部经现有 executor seam 注入，
  `backend/borrow_tasks/**` 保持 network/signing-free。
- frozen known-rejection allowlist 仅 `-51006/-51014/-51061`；`-1003` 为
  rate-limited；其余 4xx unknown。

## Breakdown 必须闭合的内容

1. 明确一个 backend-dominant task C 的 owner、allowed files、forbidden files、
   API/data contracts、migration/transaction boundaries、fake-only test evidence、
   risk points、review focus 和 do-not-touch areas。
2. 明写 wiring：移除 `config.py` 对 `live` 的现有拒绝分支但保留 invalid enum
   hard-fail；增加两项专用 credential 配置；在 `server.run` 增加 executor
   selection、dependency injection 与 ownership-lock acquisition/start ordering。
3. 列出五个 exact static guard 及 dual assertions：single-HMAC、urlopen、
   borrow-package AST purity（不放宽）、self-check timer、self-check POST method。
4. 逐项列出 round-2 §5 要求的测试，至少覆盖：two-owner；atomic gate abort；
   success-after-delete；paused-at-target completion；Start-at-target；no catch-up；
   one-shot POST per error；双层 exception containment；`PRAGMA user_version`
   幂等 migration；recon unique/zero/multiple/cross-task/exhausted；Decimal match；
   large-int `tranId`；两个 env 名称 redaction；两项 self-check guard。
5. pre-C fixture 必须由测试内 raw SQL 创建，不增加 binary fixture。
6. 将 evidence index 中“未验证”的 `Retry-After` 格式、history propagation
   SLA、per-asset precision、其他 limit family 保持为 fail-closed defaults，
   不得描述为 Binance 保证。
7. 给出 exact deterministic test commands 与实现结束时要写回的 stage artifact
   路径，但不要生成 implementation prompt，也不要运行实现测试。
8. 明写实现结束即 stop for bookkeeper；实现者不得自行 dispatch review。

## 输出要求

- 写入 canonical `12-development-breakdown.md`，不要覆盖 `.draft.md`。
- 文档应足以让 bookkeeper 随后机械准备 implementation dispatch，不留开放的
  架构选择；若发现真正冲突，写 `ESCALATED` 并停止，不得自行改需求。
- 末尾使用 `AGENTS.md` 规定的六行 footer。Session ID 必须来自当前运行时证据，
  无法看到就写 unavailable；本地北京时间必须来自本会话 `date` 命令。
- 最终回复只总结写入路径、关键边界与任何 blocker，不得声称开始实现。

当前 Session ID: unavailable (current runtime does not expose provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-boundary-c-v1/development-breakdown.prompt.md
本地北京时间: 2026-07-20 23:08:36 CST
下一步模型: human operator → claude-fable-5 (opus4.8 only after verified Fable5 quota exhaustion)
下一步任务: execute this design-only prompt and archive the raw output; do not start implementation

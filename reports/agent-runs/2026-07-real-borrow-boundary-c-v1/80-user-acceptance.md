# User Release Authorization — Boundary C

## Verbatim Direction

> 我批准 review-2 免试通过了，现在最要紧的是让我能在线上验收通过借币的功能最重要

> 算了，先按照 BINANCE_BORROW_API_KEY="${BINANCE_API_KEY}"
> BINANCE_BORROW_API_SECRET="${BINANCE_API_SECRET}" 来吧，这样快点合并上线部署，另外把目前的借币任务全部删除，借币开关打开为线上借币模式，等下合并完代码我重新启动程序我通过借币数量和次数来控制风险

## Authorized Actions

- The user accepts the all-green Boundary C code despite waiving a fresh formal
  Review-2. This is a user release decision, not a fabricated reviewer verdict.
- The bookkeeper may merge `stage/2026-07-real-borrow-boundary-c-v1` to local
  `main` without rebase.
- The user will configure the two dedicated borrow variables as references to
  the existing private variables in their local `.env` and will restart the
  local service. The bookkeeper must not read or edit `.env` or credentials.
- After the new service is running, the bookkeeper may read the execution/task
  APIs, remove every currently persisted borrow task only after enumerating the
  exact targets, and verify the list is empty.

## Deliberate Safety Boundary

`APP_BORROW_EXECUTOR=live` selects the live adapter; it is not the same action
as the durable global Start gate. The bookkeeper must not send Start or cause a
real Binance borrow. After the user restarts the service, it must first verify
the live mode, credential readiness, stopped state and empty task list. The
user then retains control of the first real task's amount and success target,
and must explicitly authorize the Start action that enables real borrowing.

当前 Session ID: unavailable (current runtime does not expose provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-boundary-c-v1/80-user-acceptance.md
本地北京时间: 2026-07-21 23:27:09 CST
下一步模型: bookkeeper, then human operator
下一步任务: merge the accepted stage to local main; user sets the non-secret env references and restarts; bookkeeper performs read-only online preflight before task deletion

<!-- ===== DISPATCH RECEIPT（执行者/记账者填写） =====
status: completed
target_model: claude_glm/glm-5.2[1m]
adapter_cmd:
executor: human_operator
started_at: unavailable:no start timestamp was recorded by the operator or the report
completed_at: 2026-07-25T19:29:28+08:00
completed_at_source: 42-final-guardian-scanner-fix.md:footer
session_id: unavailable:the produced report's footer records that the runtime did not expose a provider-native Session ID
outputs: reports/agent-runs/2026-07-hedge-open-real-api-v1/42-final-guardian-scanner-fix.md
next_dispatch: none
supersedes: none (user-authorized final micro-fix after packet 62 reconciliation hold H-1)
receipt_backfilled_by: bookkeeper (Claude Opus 5) on 2026-07-27, closing the 74-review-2-r2.md P1 backlog. Evidence is taken ONLY from the produced report's own footer; every field without a recorded source is marked unavailable with its reason. No command, timestamp or Session ID was invented.
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（immutable） ===== -->

```text
[HARNESS-EXECUTOR-CONTRACT v1]
你是 `2026-07-hedge-open-real-api-v1` 的唯一后端修复实现者。这是用户明确批准的一次、且仅一次的极小第 4 次修复；只处理 H-1（真实模式的长期全局恢复扫描）。

禁止调用、启动、转派其他模型或 adapter。禁止读取凭据、连接 Binance、发送真实 POST、启用 live/Start、commit，或修改 `status.json`、`70-handoff.md`、`frontend/**`、`docs/**`、PRD、设计/ADR、环境/凭据文件。不要执行 git reset、checkout、clean 或任何会丢弃当前工作区的命令：工作区已包含 packet 62 的未提交正确改动，你必须在其上做增量修复。

## 先读（按此顺序）

1. `24-user-authorized-final-guardian-fix.md` — 本次唯一的额外授权与最终业务边界；
2. `23-packet-62-reconciliation-hold.md` — H-1 的准确代码证据；
3. `21-task-local-runtime-and-manual-pause-amendment.md` — 运行时最高业务合同；
4. `62-review-1-backend-r2-task-local.dispatch.md` 与 `40-fix-review-1-backend-r2.md` — packet 62 已完成、必须保留的任务本地 worker/429/余额/重启恢复语义；
5. 当前 `backend/hedge_open_tasks/service.py`、`scheduler.py`、`backend/tests/test_hedge_task_local.py`、`backend/tests/test_hedge_review2_regressions.py`。

## 已经做好的部分 — 不要破坏

每张任务卡已经有自己的有界 worker：

该任务人工 Start/recover
  -> 该 task_id 的一个 worker
  -> fresh preflight
  -> durable reserve 一组 pair
  -> 现货 + 合约两腿并发 submit
  -> 仅 query 自己的两腿到终态
  -> 只结算一次
  -> 仍在 RUNNING 才进入下一组；done/paused/stopped 则退出

已经有测试证明：A 查询慢不挡 B、同任务并发 Start 不会双 POST、429/余额只暂停本任务、同 DB 重启只按 clientOrderId 查询而不二次写入。保留这些语义和测试；不要把查询重新搬回全局线程。

## H-1：本次唯一问题

当前真实模式仍是：

service.start()
  -> HedgeOpenScheduler.start() 的常驻线程
  -> 周期 tick()
  -> _recover_workers()
  -> 反复扫描全部 RUNNING / PAUSED / STOPPED 任务
  -> 需要时拉起 worker

这个常驻线程本身不直接下单，但它持续发现全局任务、间接拉起会下单/查询的子线程。它违反用户批准的规则：真实开单只允许“一次启动恢复”或“人工恢复指定任务”，不能有长期扫描全部任务的守护进程。

## 必须实现的最小改动

1. 真实模式启动只恢复一次
   - 当真正满足 live dispatch 条件时，`service.start()` 可以一次性执行 durable recovery discovery：找到需要收尾的任务，把它们交给各自的 task-local worker 后立即返回。
   - 这个一次性恢复必须保留 packet 62 的安全性质：pending pair 只能按保存的 clientOrderId 查询，不能重发 POST；paused/stopped 但有未终态腿的任务也能得到 drain-only worker。

2. 真实模式不启动、不依赖周期全局扫描
   - live-capable 路径不得启动 `HedgeOpenScheduler` 作为 hedge-open 的长期恢复扫描器。
   - live `tick()` 必须是安全空操作（或等价地绝不调用 `_recover_workers()`、绝不列举全部任务、绝不启动任一 worker）。即便未来有人意外调用它，也不能变成守护扫描。
   - 禁止新增任何替代性的 timer、daemon、poller、全局队列消费者或长期 coordinator。

3. 人工操作仍是任务本地
   - `post_start(task_id)` / fill-once / fill-all 的 live 路径仍只 `ensure_worker(task_id)`，绝不能改回全局 dispatch。
   - 不改变 429/余额暂停、失败阈值、target_n 上限、双腿并发、单任务 pair 串行、预检、签名、wire 参数、日志、API 字段、UI 或 dry-run 的业务语义。

4. 确定性离线测试（必须新增/更新）
   - live-capable `service.start()` 恰好做一次恢复 handoff，且不启动 scheduler；
   - 连续多次直接调用 live `tick()` 不会调用 `_recover_workers()`、不枚举任务、不会拉起 worker；
   - 人工 `post_start(A)` 仍只拉起 A，不会扫描或拉起 B；
   - 保留并复跑 packet 62 的关键任务本地测试，证明这次改动没有恢复全局查询/双 POST/跨任务联动。

测试不得使用真实网络或 sleep race。可使用 fake executor、spy、Event/Barrier 或同步 test seam。

## 允许修改（只限）

- `backend/hedge_open_tasks/service.py`
- `backend/tests/test_hedge_task_local.py`
- 必要时直接相关的 `backend/tests/test_hedge_service.py`
- `reports/agent-runs/2026-07-hedge-open-real-api-v1/42-final-guardian-scanner-fix.md`（新报告）
- `reports/agent-runs/2026-07-hedge-open-real-api-v1/60-test-output.txt`（只追加真实命令输出）

禁止触碰其它源码、所有 frontend、任何 Harness/合同文档、`23`/`24`/`62`/`63` 文件、状态/交接文件。若发现必须改出此清单，停止并报告给 bookkeeper，不能自行扩范围。

## 必跑命令

.venv/bin/python -m pytest backend/tests/test_hedge_task_local.py backend/tests/test_hedge_service.py backend/tests/test_hedge_review2_regressions.py -q
.venv/bin/python -m pytest backend/tests -q
node frontend/self-check.js
.venv/bin/python -m pytest scripts/tests/test_validate_stage_dispatch_protocol.py -q
git diff --check

把真实结果追加到 `60-test-output.txt`。在 `42-final-guardian-scanner-fix.md` 写清：继承自 packet 62 的改动与本包直接改动的边界、启动恢复的精确路径、live tick 为何不会扫描、人工 Start 仍如何只启动指定任务、每项新测试和剩余风险。报告末尾加标准 Session footer。

全部完成后停止：不 commit、不派发评审、不自行宣称验收，等待 bookkeeper 做差异核对、提交证据并安排重新的 Review-1。
```

当前 Session ID: unavailable (Codex runtime does not expose a provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/63-final-guardian-removal.dispatch.md
本地北京时间: 2026-07-25 18:48:57 CST
下一步模型: human
下一步任务: run the prompt body in a fresh write-capable Claude-GLM session

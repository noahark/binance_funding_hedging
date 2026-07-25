<!-- ===== DISPATCH RECEIPT（执行者/记账者填写） =====
status: completed
target_model: claude/Claude Opus 5
adapter_cmd:
executor: human_operator
started_at: unavailable:operator did not provide a start timestamp
completed_at: 2026-07-25T20:34:50+08:00
session_id: 777ebb52-bba4-4b4d-a3b9-5879deaa4d7c
outputs: reports/agent-runs/2026-07-hedge-open-real-api-v1/64-review-1-backend-r3.md
next_dispatch: none
fallback_reason: Kimi remains unavailable by the human operator's prior quota report. The human operator selected Claude Opus 5 instead of the packet's prewritten Claude Sonnet 5 target because this review was judged critical; Anthropic remains provider-isolated from the reviewed claude_glm backend authors.
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（immutable） ===== -->

```text
[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务唯一的正式 Review-1（第一轮交叉复核）后端审查者。禁止调用、启动或转派任何其他模型会话或 adapter。只读：绝不修改文件、绝不 commit、绝不读取凭据、绝不连接 Binance、绝不发送真实 POST、绝不启用 live 或 Start。

审查身份：被审后端代码的实现/返工作者为 Claude-GLM（zhipu_glm）。你是 Claude Sonnet 5（Anthropic），供应商隔离成立。你曾在本 stage 写过前端返工，但没有写本次后端代码；只审后端及其 HTTP/entries 接缝，不审前端视觉实现。JSON 中 `reviewer_prior_involvement` 写 `none`，并在叙述中如实说明“曾写前端、未写被审后端”。

固定审查锚点（只审此已提交范围；不要改用移动的 HEAD）：
- base: 28c550d87c1ca90983d5bde9c7102d42cffecd4e
- head: ab3126d73549266a615fe43c1aeaf374b0db2d32
- fingerprint: ab3126d73549266a615fe43c1aeaf374b0db2d32:4538945aa1e6ed3ea89a4f00f60a7dc71c97cc634dcb042c45d39ecc5a6e9772

## 必须实际阅读

1. `AGENTS.md`；`workflows/templates/stage-delivery.yaml` 的 Review-1 规则；`schemas/review-verdict.schema.json`；
2. `docs/product/PRD.md`（尤其即时开单、风险、实盘门控相关段落）；
3. stage 的 `00-task.md`、`06-direction-synthesis.md`、`10-design.md`、`11-adr.md`、`15-immediate-loop-and-open-log-amendment.md`、`16-replacement-development-breakdown.md`；
4. 用户后续运行时权威：`21-task-local-runtime-and-manual-pause-amendment.md`、`24-user-authorized-final-guardian-fix.md`；
5. 原始问题与实现证据：`50-review-2.md`、`58-review-1-backend-r2.md`、`40-fix-review-1-backend-r2.md`、`23-packet-62-reconciliation-hold.md`、`42-final-guardian-scanner-fix.md`、`25-packet-63-final-reconciliation.md`、`60-test-output.txt`；
6. 实际 `git diff --binary 28c550d87c1ca90983d5bde9c7102d42cffecd4e..ab3126d73549266a615fe43c1aeaf374b0db2d32`，以及相关 `backend/hedge_open_tasks/**`、`backend/services/live_hedge_executor.py`、`backend/tests/test_hedge_*.py` 源码与测试。

## 用户冻结的业务合同（高于旧草案）

- 每张任务卡独立；同一张卡严格先让第 N 组走到终态/对账结束，才可开始第 N+1 组。一组内现货和合约腿仍并发。
- `target_n` 是计划尝试组数硬上限，不因失败或单腿结果补发超出授权数量。
- 不得到 `orderId` 的未知结果必须按 clientOrderId 查询，绝不盲目重发写请求；已受理订单继续查到终态。
- 429、余额/保证金/可用数量不足只暂停当前任务，等待人工恢复；不联动其它任务。其它明确配置错误只停止当前任务。
- 实时模式没有长期全局守护扫描器：启动时可做一次恢复交接；人工 Start/recover 只能启动指定卡；后续下单/查询由各卡自己的有界 worker 完成。
- 默认关闭。没有本次实盘、Start、凭据或真实 Binance 请求授权。

## 必查重点

1. **原 P1 是否真正修复**：正反向 `est_price` 缺失/零/负都 fail-closed；任务 A 慢查询不会阻塞 B；双重 Start/恢复不会双 POST。
2. **任务本地 worker**：同卡 pair 串行、双腿并发、只查自己的腿、429 先 client-ID 对账再本卡暂停且不计失败；余额/保证金暂停与未确认 -2010 fatal 的边界是否正确。
3. **H-1 最终修复**：live `start()` 仅一次 `_recover_workers()` 后返回、绝不启动 scheduler；live `tick()` 为安全空操作，不枚举任务、不拉 worker；`post_start(A)` 仍只启动 A。确认没有其它 timer/daemon/全局扫描替代它。
4. **持久化与安全**：target_n 原子限制、同 DB 重启只查询 clientOrderId、store 锁内不调用 executor、签名/网络纯度、real POST 的关闭门控无回归。
5. **展示/日志接缝**：entries 独立分页仍不改变旧 logs 分页；本次后端字段无破坏前端已接受的契约。
6. **测试与范围**：核对 897 后端测试、48 个本次重点测试、前端自检、Harness 测试的证据；检查实际差异无越界、无凭据、无实盘激活。

输出完整原始评审到：
`reports/agent-runs/2026-07-hedge-open-real-api-v1/64-review-1-backend-r3.md`

先写中文叙述、findings（P0/P1/P2/P3）与可核对证据，再写标准 Session footer。文件最后一个顶层 JSON 对象必须严格匹配 `schemas/review-verdict.schema.json`：`role=first_reviewer`、`model=Claude Sonnet 5`、`diff_fingerprint` 必须逐字等于上面值。若 verdict=REWORK，必须提供可直接派发的 `fix_start_prompt`，包含原始证据路径、允许/禁止文件、精确测试命令与验收条件。完成后停止等待 bookkeeper。

当前 Session ID: report provider-native ID, or unavailable:<reason>
Session ID 来源: runtime_env | hook_payload | cli_output | transcript_path | active_session_registry | operator | unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/64-review-1-backend-r3.md
本地北京时间: obtain from local date command
下一步模型: bookkeeper
下一步任务: validate this renewed backend Review-1 verdict and route it with the preserved frontend ACCEPT
```

当前 Session ID: unavailable (Codex runtime does not expose a provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/64-review-1-backend-r3.dispatch.md
本地北京时间: 2026-07-25 19:38:16 CST
下一步模型: human operator
下一步任务: run the prompt body in a fresh read-only Claude Sonnet 5 session

<!-- ===== DISPATCH RECEIPT（执行者/记账者填写） =====
status: pending
target_model: claude_glm/glm-5.2[1m]
adapter_cmd:
executor: human_operator
started_at:
completed_at:
session_id: unavailable:pending human execution
outputs: reports/agent-runs/2026-07-hedge-open-real-api-v1/44-fix-review-1-backend-r3.md
next_dispatch: none
authorization: user-authorized fifth bounded backend change; 26-user-authorized-settlement-and-pause-fix.md
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（immutable） ===== -->

```text
[HARNESS-EXECUTOR-CONTRACT v1]
你是 `2026-07-hedge-open-real-api-v1` 唯一的后端返工实现者。此次是用户明确授权的第 5 次、严格有界的修复：处理 Opus 5 Review-1 的 2 个 P1（必须修）和同批 2 个 P2（用户已选择 A：新增后端可观测字段）。禁止调用、启动或转派其它模型/adapter。

禁止读取凭据、连接 Binance、发送真实 POST、启用 live、触发 Start、commit 或修改 `status.json`、`70-handoff.md`、任何 PRD/设计/ADR/契约文档。禁止 reset/checkout/clean 或丢弃当前工作树。不得改 `frontend/**`、`backend/hedge_open_tasks/scheduler.py`、`backend/app/server.py`、环境/凭据/网络配置。不得新增全局守护、周期扫描器、timer、自动补单/撤单/平仓/借还/转账、WebSocket 或平滑开仓。

## 最高权威与原始修复指令（必须逐字读完）

1. `64-review-1-backend-r3.md`：原始 REWORK、可复现证据、末尾 schema-valid JSON verdict 与 reviewer 的完整 `fix_start_prompt`；
2. `26-user-authorized-settlement-and-pause-fix.md`：用户第 5 次授权、§4 的固定业务规格、§6 的 R1–R8 回归、§9 的完整原始修复 prompt。用户已经在 §4.4 明确选择 **A：加字段**，不需要也不允许自行选择；
3. `21-task-local-runtime-and-manual-pause-amendment.md`、`15-immediate-loop-and-open-log-amendment.md`：任务本地、对账绝不放弃、暂停错误矩阵；
4. `40-fix-review-1-backend-r2.md` 与 `42-final-guardian-scanner-fix.md`：packet 62/63 已实现且必须保留；
5. 当前相关源码、测试及 `60-test-output.txt`。

`26` §9 是本包的原始 reviewer fix_start_prompt（仅已被用户批准的「字段 A」选择被固定），不得用自己的摘要替代或漏掉其中任一强制条件。

## 必须修复的业务结果

1. 429 暂停后人工恢复：清除 `pause_reason` / `pause_reason_zh`；“本组不计失败次数”必须由 **该 attempt 自身的限频事实**决定，不能依赖任务级粘滞 pause_reason。恢复后下一组两腿 FILLED 必须正确成为 `accepted_pair`、更新 accepted/success 计数；后续 3 次确认失败仍必须触发本卡阈值暂停。
2. 人工 pause/delete：在飞订单必须只由本任务 worker 继续按 clientOrderId 查询到终态并结算，然后退出；不得开新组。DELETED 任务若带未终态腿，进程重启的一次性 recovery 也必须仅启动该任务的 drain worker。绝不借此重新引入全局 tick/扫描器。
3. `settle_attempt_no_counters`：仍不增加连续失败计数，但必须由两腿真实事实推导 accepted/single_leg/confirmed_failed；single_leg 必须写 `leg_exposure`。
4. 用户选择 A 的可观测字段：
   - `worker_active` 是后端派生三态：live 可派发时由 `_workers` 注册表得到 true/false；dry-run 必须是 `null`（不适用），不能是 false；
   - `last_worker_exit_reason` 是可空、加性 SQLite 列，稳定机器枚举，worker 各退出分支/异常路径写入，重新进入 RUNNING 时清空；
   - 两键加入 task API 冻结字段测试；不新增 entries event kind、不动前端。
5. 建议一并让 `_pump_worker` 初始化与真实 worker 相同的 stop event，以便 pause/delete 路径可用确定性测试覆盖。

## 保持不变的底线

- live `start()` 仍只做一次 `_recover_workers()` 后返回，绝不启动 `HedgeOpenScheduler`；live `tick()` 仍是安全空操作；人工 Start 仍只启动指定 task；
- 每任务只有一个有界 worker、同卡 pair 串行、两腿并发、跨卡互不阻塞；
- `target_n` 原子硬上限；无 orderId 只按 clientOrderId 查询且永不重发 write；
- 429/余额/保证金只暂停当前卡；未确认 -2010 仍 fatal stop；默认 disabled/record 不得网络写入；签名前置门、7 端点 allowlist、store 锁内不调 executor 不得回归。

## 允许修改（仅此范围）

- `backend/hedge_open_tasks/domain.py`
- `backend/hedge_open_tasks/store.py`
- `backend/hedge_open_tasks/service.py`
- `backend/services/live_hedge_executor.py`（仅 attempt 标记/分类确有必要时）
- `backend/tests/test_hedge_task_local.py`
- `backend/tests/test_hedge_review2_regressions.py`
- `backend/tests/test_hedge_store.py`
- `backend/tests/test_hedge_service.py`
- `backend/tests/test_hedge_api.py`
- `reports/agent-runs/2026-07-hedge-open-real-api-v1/44-fix-review-1-backend-r3.md`
- `reports/agent-runs/2026-07-hedge-open-real-api-v1/60-test-output.txt`（只追加实际输出）

若需要超出该清单，停止并向 bookkeeper 报告，不要自行扩范围。

## 必须新增并证明的离线确定性回归

按 `26` §6 完成 R1–R8：429 恢复后的成功/阈值、pause drain、delete drain、DELETED 重启 drain、429+单腿成交、live worker active/exit reason、dry-run `worker_active is None`。测试必须 zero network、zero sleep race；先明确旧代码缺口，再验证修复。复跑 packet 62/63 的 `test_1`–`test_6c`、`test_4b` 和迁移 review-2 用例。

## 精确自测（结果原样追加 60）

.venv/bin/python -m pytest backend/tests/test_hedge_task_local.py backend/tests/test_hedge_service.py backend/tests/test_hedge_review2_regressions.py backend/tests/test_hedge_store.py backend/tests/test_hedge_domain.py backend/tests/test_hedge_api.py backend/tests/test_hedge_purity.py backend/tests/test_hedge_open_live_client.py backend/tests/test_live_hedge_executor.py backend/tests/test_hedge_executor.py -q
.venv/bin/python -m pytest backend/tests -q
node frontend/self-check.js
.venv/bin/python -m pytest scripts/tests/test_validate_stage_dispatch_protocol.py -q
git diff --check

将实现报告写入 `44-fix-review-1-backend-r3.md`：逐项说明 changed files、R1–R8 的修复前缺口/修复后证据、迁移幂等性、H-1/packet62 不回归、剩余风险，以及 worker 字段只在后端提供、前端展示是 follow-up。末尾加标准 Session footer，然后停止。不得 commit、不得派发评审、不得自行宣称验收。
```

当前 Session ID: unavailable (Codex runtime does not expose a provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/65-fix-review-1-backend-r3.dispatch.md
本地北京时间: 2026-07-25 21:07:26 CST
下一步模型: human operator
下一步任务: run the prompt body in a fresh write-capable Claude-GLM session

# 25-cadence-500ms-implementation —— Task 3（rescoped）实现报告

```text
任务 ID:    fix-cadence-500ms-and-absent-tolerance-v1
实现者:     claude_glm（zhipu_glm）
分支:       stage/2026-07-31-hedge-task-lifecycle-v1
base_sha:   9faa716396cbbe67ebeec272ad6b3dd443bba583
delivery:   本提交（HEAD，精确 sha 见 status.json.delivery_sha）
状态:       实现 → 自测完成 → 待 review-1（grok）→ review-2（codex）
本地北京时间: 2026-08-02 00:05 CST
```

## 1. 交付目标与六件事

Human 于 2026-08-01 改变方向：1s → **500ms（提速 2 倍）**，并消除「真实挂单被判定为从不存在」的风险。

| # | 事项 | 落点 |
|---|---|---|
| 1 | 默认重查间隔 1s → 500ms（**不是** aac779d 的 100ms） | `domain.py` `DEFAULT_INTERVAL_SECONDS="0.5"` / `DEFAULT_INTERVAL_US=500_000` |
| 2 | 补迁移，使新默认在既有库生效（BK-T3-001 拒收根因） | `store.py::_migrate` 末尾回填 |
| 3 | 移除抖动（从未要求，且削减首查安全边界） | `service.py` 删 `_PACING_JITTER_MIN`/`paced_wait_seconds`/`import random`，`ev.wait(interval_s)` |
| 4 | `404 / -2013` 不再一次判死，改时间窗口内继续重查 | `service.py::_reconcile_own_legs` 窗口判定 |
| 5 | 既有无上限「继续查」分支套同一窗口，但收口方式不同（安全要害） | 同上 + 新 pause reason/signal |
| 6 | 与 `_confirm_um_figures` 既有语义统一 | 见 §3 |

`rework_count` 因 Human 同意的新交付范围重置为 0（AGENTS.md §8）。

## 2. 改动清单（均在 Allowed Files 内）

```text
backend/hedge_open_tasks/domain.py     # 默认值 500ms、ABSENT_TOLERANCE_WINDOW_US、新 pause reason/signal/zh
backend/hedge_open_tasks/store.py      # _migrate 回填（BK-T3-001）
backend/hedge_open_tasks/service.py    # 移除抖动、窗口判定、两种收口
backend/tests/test_hedge_service.py    # 默认值断言 0.1→0.5；删除两个抖动单测
backend/tests/test_hedge_api.py        # 默认值断言 0.1→0.5
backend/tests/test_hedge_task_local.py # 6 个 drain 用例推进时钟；+2 个窗口新单测
backend/tests/test_hedge_review2_regressions.py  # 仅 test_5b 推进时钟（受限授权）
```

未改：`live_hedge_executor.py`、`frontend/`、51169 文案区、429/rate_limited 逻辑、`private_client.py`、`data/` 下任何库（见 §7 的一项程序观察）。

## 3. 设计依据：把已有保护补齐到缺失的路径（第 4-6 项的正当性）

`live_hedge_executor.py::_confirm_um_figures` 的 docstring 逐字断言：

> Any other confirm outcome — inconclusive (timeout / 5xx), a malformed 2xx, or
> even a literal 404/-2013 (**a POST-just-accepted order 404-ing is
> eventual-consistency noise, NOT a real absent signal**) — leaves the leg
> ACCEPTED with `cumulative_quote=None` so it is non-terminal …

即**离下单最近的那次查询（POST 后立即 confirm）有保护**，并由测试
`test_dispatch_um_confirm_404_does_not_overturn_post_acceptance` 锁定。但 worker 的
drain 查询路径（`_reconcile_own_legs` → `classify_query_response`）把 `404/-2013` 判为
`TERMINAL_RECORDED + error_category=absent`，`_query_verdict_terminal` 立即返回 `True`，
**该腿一次判死**——同模块两路径语义相反。本任务不是新增防御，而是把该保护补到 drain 路径。

**实现约束**：窗口判定在 service 层（`classify_query_response` 不在允许清单，且它是网络
层分类器、不持有腿的下单时间）。锚点用既有的 `hedge_open_leg.dispatched_at_us`
（`store.py:97`，**未新增字段**）。

## 4. 两种收口方式（第 5 项的安全要害）

窗口（`ABSENT_TOLERANCE_WINDOW_US = 5_000_000`，约 5 秒 = 原 JS `getSpotOrderInfo` 10×500ms）
从 `dispatched_at_us` 起算。`window_elapsed = dispatched_at_us is not None and
(now_us - dispatched_at_us) >= ABSENT_TOLERANCE_WINDOW_US`（无锚点的旧行 → 视为窗口未耗尽，
保留旧行为）。

| drain 末次结果 | 窗口内 | 窗口耗尽 |
|---|---|---|
| `404 / -2013`（absent） | `terminal=False`，继续重查（**镜像 _confirm_um_figures**） | `terminal=True` 判 absent 终态（现行行为，仅推迟约 5 秒） |
| `5xx / 超时 / 畸形 2xx`（inconclusive） | 继续重查（现行行为） | **不判 absent**；腿留非终态 + 任务暂停（`order_state_unknown`），走既有 task-local pause，人工恢复 |

第二条的理由：5xx/超时/畸形 2xx **从来不是**「确认不存在」的信号；判 `absent` 等于把「不知道」
当成「确认没有」——正是 R2-F2 明令禁止的错误。窗口耗尽只改变「还要不要继续等」，不改变该腿
「是否确认不存在」的性质。

**新 pause reason / signal**（唯一一处语义新增，见 §8 的边界解释）：
- `PAUSE_REASON_ORDER_STATE_UNKNOWN = "order_state_unknown"`，zh：
  「订单状态在容忍窗口（约 5 秒）内持续不明，无法确认是否已被交易所接受，任务已暂停。请到
  交易所核对订单后手动恢复（恢复后仅按既有 clientOrderId 重查，不重发下单）」。
- `SIGNAL_ORDER_STATE_UNKNOWN`，在 `_worker_round` 单独处理（**故意不在**
  `SIGNAL_TASK_LOCAL_PAUSE` 内，与 `SIGNAL_RATE_LIMITED` 同形：暂停本任务 + 留腿非终态 +
  worker 退出，不回环继续查）。

## 5. 验收检查（逐条）

1. **既有库生效** — pass。临时副本设 `interval_us=1_000_000` 打开 →
   `get_interval_us()==500_000`、`interval_seconds==0.5`（§6 实测）。
2. **不覆盖非默认值** — pass。副本设 `250_000` 打开 → 仍 `250_000` / `0.25`。
3. **新库** — pass。全新空库 → `500_000` / `0.5`；前端 `index.html:3856` 未改，模板
   `` `调度间隔 ${doc.interval_seconds} 秒（后端调度）` `` 渲染「调度间隔 0.5 秒（后端调度）」。
4. **抖动已移除** — pass。`_PACING_JITTER_MIN`、`paced_wait_seconds`、`import random` 及两个
   抖动单测均不复存在；节流等待为 `ev.wait(interval_s)` 确定值。
5. **404 窗口容忍** — pass（独立可失败单测
   `test_absent_within_window_stays_nonterminal_then_confirms_after_window`）：窗口内 404 →
   腿非终态、`pair_outcome=None`；耗尽后 404 → `fail_count==1`。
6. **不知道 ≠ 不存在** — pass（独立可失败单测
   `test_inconclusive_past_window_pauses_for_manual_recovery_not_absent`）：窗口耗尽且末次为
   畸形 2xx（`UNKNOWN_QUERYING`）→ `status=paused`、`pause_reason=order_state_unknown`、
   `fail_count==0`、腿非终态、`dispatch_calls==1`（不重发）。
7. **语义统一** — pass，见 §3、§4。
8. **锁定回归** — pass。9 个 rate_limited 用例全绿；`test_4l` 全绿（证据落库语义，不受窗口影响）；
   `test_5b` 仅推进时钟、核心断言（absent 确认 → `fail_count==1`）不变（§6）。
9. **真实数据验证** — pass（副本），见 §6；**但有一项程序观察见 §7**。
10. **回归全绿** — pass。`python3 -m pytest backend/tests/ -q` → **1140 passed**（= 基线 1140；
    删 2 个抖动单测 + 新增 2 个窗口单测）。输出存 `63-cadence-500ms-test-output.txt`。
11. **边界** — pass（除 §7 程序观察）：未改 executor/frontend/51169 文案区/429 逻辑；未新增数据库
    字段、配置入口；新增的 pause reason/signal 见 §8 说明。

## 6. 真实数据验证（副本，可复现）

实盘库 `data/hedge-open-tasks.sqlite3` 复制到临时目录后验证（**原库只读，未由本次验证写入**，
sha256 验证前后一致 `ec63dd07…`）：

```text
DEFAULT_INTERVAL_US=500000  DEFAULT_INTERVAL_SECONDS=0.5
[legacy 1_000_000]  get_interval_us=500000  api=0.5   raw=(500000,'0.5')   # 迁移回填
[custom 250_000]     get_interval_us=250000  api=0.25  raw=(250000,'0.25')  # 非默认值保留
[copy 500_000]       get_interval_us=500000  api=0.5   raw=(500000,'0.5')
[fresh empty]        get_interval_us=500000  api=0.5   raw=(500000,'0.5')   # 种子插入
```

**破坏验证**（不采信「我测过了」，对应 24- §8 纪律 2）：临时禁用窗口逻辑后——
- 禁用 absent 窗口覆盖 → 窗口内 404 立即终态 → `test_absent_within_window…` 断言红；
- 禁用 inconclusive 收口 → 任务不暂停（仍 `running`）→ `test_inconclusive_past_window…` 断言红。
两条新单测均为真断言，随后完整还原、工作区干净。

## 7. ⚠ 程序观察（需 Bookkeeper/Human 知悉，非交付缺陷）

实盘库当前 `interval_us=500000` / `interval_seconds=0.5` / `version=4`；而 Bookkeeper 的 24-
核验（2026-08-01）记录为 `1_000_000`。`version` 未变、值恰为 `1_000_000→500_000`，与本任务迁移
签名一致。`lsof` 显示 **`python -m backend.app.server`（PID 57852，8/1 19:33 启动）持有该库**，
文件 mtime 为 8/1 23:45。

**结论**：运行中的后端服务（使用本工作区代码，含本次迁移）已把迁移应用到实盘库——值是**正确**
的（正是 BK-T3-001 的目标），但「实盘库在开发期被写入」与 packet「实盘库只读，验证须先复制到
临时目录」/ 验收 11 的精神存在张力。

- 本次验证脚本只打开副本、未打开实盘库（sha256 前后一致已证）。
- 实现者未直接、未通过验证脚本写 `data/`；写动作来自运行中的服务进程（由 Human 运维）。
- 实现者**未**停止该服务（停止实盘交易服务须 Human 授权）。

请 Bookkeeper 裁定该运行态写入是否影响验收 11 的封存判定；代码与迁移逻辑本身正确且经副本验证。

## 8. 边界解释：新增 pause reason 是否违反「未新增状态枚举」

验收 11 要求「未新增数据库字段、配置入口、状态枚举」。本任务为第 5 项的「转人工路径」新增了
`PAUSE_REASON_ORDER_STATE_UNKNOWN` + `SIGNAL_ORDER_STATE_UNKNOWN`。判断其**不在**禁止范围：

1. **reductio**：packet 第 5 项 + 验收 6 明确要求「窗口耗尽且 inconclusive 的腿不得判 absent，
   须转人工路径，须有能失败的测试」——而 pause 需要一个 reason，6 个既有 reason（rate_limited /
   insufficient_* / collateral_cap / consecutive_submission_failure）无一语义匹配「订单状态持续
   不明」。若新增 pause reason 被禁，packet 自相矛盾；packet 已过 deepseek 独立复核，不应自相
   矛盾。故新 reason 必然在允许范围。
2. **「状态枚举」的口径**：本仓库中「状态」专指 task status / leg dispatch_state /
   exchange_status（状态机词汇）；pause reason 是「暂停原因」、signal 是「信号」，均为操作面
   taxonomy，且 `pause_task` 不按 `ALL_PAUSE_REASONS` 校验。本任务**未**新增任何 task/leg 状态机
   值，亦未新增 DB 字段、配置入口。
3. **文件边界**：`domain.py` 在 Allowed Files 内；`24-` §3 的 test_hedge_api.py 教训是「不得改
   非允许文件」，新增常量属允许文件内的实现细节，不触发 AGENTS.md §3 #3。

请 review-1 独立复核此解释。

## 9. 测试改动明细

**新增（2，验收 5/6 的独立可失败测试，位于 `test_hedge_task_local.py`）：**
- `test_absent_within_window_stays_nonterminal_then_confirms_after_window`
- `test_inconclusive_past_window_pauses_for_manual_recovery_not_absent`

**既有用例推进时钟（8，核心断言不变，仅让窗口跨过以反映「drain 发生在窗口之后」）：**
- `test_5b`（review2，受限授权：仅推进时钟）
- `test_s2`、`test_r1`、`test_r2`、`test_r3`、`test_r4`、`test_r6`（task_local：drain 前推进时钟）
- `test_drain_settlement_failure_is_recorded_not_swallowed`：零时钟冲突（同一 now_us 既驱动窗口
  又驱动 `finalize_attempt` 的 `ts_us<=0` 兜底），无法推进时钟；改为把 `dispatched_at_us`
  后移过窗口（保留 absent 判定 + 零时钟 + 单腿结算异常核心），未改断言。

**默认值断言更新（2）：** `test_default_cadence_seeds_100ms→500ms`、
`test_settings_default_shape`（0.1→0.5）。

**删除（2，验收 4）：** `test_requery_wait_is_100ms_within_jitter`、
`test_pacing_jitter_is_positive_bounded_and_varies`。

## 10. 下一步

停在这里。未启动评审、未写 `verified`、未合并、未碰 `main`。后续 review-1（grok）→ review-2
（codex）。提交前已自查 `git branch --show-current=stage/2026-07-31-hedge-task-lifecycle-v1`。

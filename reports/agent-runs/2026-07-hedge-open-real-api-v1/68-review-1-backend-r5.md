# 68 — Review-1（后端，第 5 轮）· 2026-07-hedge-open-real-api-v1

**审查者**：Claude Opus 5（Anthropic），只读会话，`[HARNESS-EXECUTOR-CONTRACT v1]`。
**被审代码作者**：Claude-GLM（`glm-5.2[1m]`，provider `zhipu_glm`）——供应商隔离成立。
**dispatch**：`68-review-1-backend-r5.dispatch.md`。

## 0. 身份披露（如实）

同一模型（Claude Opus 5）此前在本 stage 产出过 **r2 / r3 / r4 三轮只读 Review-1**
（`58-review-1-backend-r2.md` / `64-review-1-backend-r3.md` / `66-review-1-backend-r4.md`，
更早还有 `30-review-1-backend.md`），并自 **2026-07-25 起兼任本 stage 的 bookkeeper**
（Codex 无额度后交接，见 `status.json.bookkeeper.dual_hat_disclosure` 与 `27-user-authorized-r4-repair.md` §6）。
**这两个角色都不是代码或修复作者**——被审的全部后端业务代码与本轮返工（packet 67）均由 Claude-GLM 编写。
因此 JSON 中 `reviewer_prior_involvement = none`（该枚举只描述 direction synthesis / breakdown / design
三项参与，我三项皆无）。

按 dispatch 硬性要求：**我没有把上一轮结论或 bookkeeper 的核对结果当成本轮已经成立的事实。**
本报告每一条判断都来自重新阅读固定 diff 与当前源码、在本机重新跑测试、以及**我自己新写的四组反向验证**
（猴补丁，未改任何仓库文件；零网络、零凭据、零真实 POST、零 live、零 Start、零 commit）。
凡是我说"确认成立"的地方，都附了本轮自己跑出来的原始输出。GLM 报告里的表格我一律当作**待验证的声明**处理。

## 1. 锚点校验

| 项 | 结果 |
| --- | --- |
| base | `28c550d87c1ca90983d5bde9c7102d42cffecd4e` |
| head | `b9e1978eaffd047b7871b8721f511307e75fde68` |
| 指纹（本机按 harness 规则独立重算） | `604caada1043e8334f33b1cc73239f1cf6bb19017db1dc68374679cf6ac99ddd` — **逐字一致** |
| `validate-stage --phase pre-review` | `STAGE VALIDATION PASSED`，`status=review_1`，指纹同上 |
| `b9e1978..HEAD`（`c643cce`） | 仅 `68-...dispatch.md` / `70-handoff.md` / `status.json` 三类簿记文件，**零业务改动** |
| `status.json` | `rework_count=6`，`max_rework=6` —— **上限已满** |

重算命令与输出（口径取自 `scripts/validate-stage.py:223-239`，排除 `status.json`）：

```text
$ git diff --binary 28c550d87c1ca90983d5bde9c7102d42cffecd4e..b9e1978eaffd047b7871b8721f511307e75fde68 \
    -- . ':(exclude)reports/agent-runs/2026-07-hedge-open-real-api-v1/status.json' | shasum -a 256
604caada1043e8334f33b1cc73239f1cf6bb19017db1dc68374679cf6ac99ddd  -
```

本轮实际返工范围（`e10b395..b9e1978`）：

```text
 backend/hedge_open_tasks/service.py                |  27 ++-
 backend/tests/test_hedge_task_local.py             |  90 +++++++++
 .../46-fix-review-1-backend-r4.md                  | 124 ++++++++++++
 .../60-test-output.txt                             | 219 +++++++++++++++++++++
```

`git diff --stat e10b395..b9e1978 -- frontend/ docs/ backend/services/ backend/app/ store.py domain.py
scheduler.py config.py` 输出为空 —— **越界为零**，与 dispatch 允许的范围逐字吻合。

## 2. 先讲人话：这轮到底修好了没有

**修好了，而且我用自己的实验从两个方向各验了一遍。**

1. **上一轮那两条"空回归"现在是真回归了。** 我把上一轮删掉的"按暂停键就打断 worker"这个老毛病用猴补丁
   原样装回去，然后跑仓库里真正的 R3/R4 —— **两条都红了**。我还换了另一种毛病形态（把"先看状态就退出、
   不管在飞订单"塞回 worker 主循环），**R3/R4 照样红**。也就是说：以后谁再把这类改动引回来，
   测试会拦住，不会像上一轮那样 905 个测试全绿地放行。

2. **打完最后一组就重启，那笔真成交不再丢了。** 我把新加的 `DONE` 从恢复名单里摘掉，
   `test_r9` 立刻红，而且红的地方和我上一轮离线复现的现象一模一样（重启后压根没人去查那条腿）。
   加回去之后，一次恢复交接就把它查到成交、**没有重发任何订单**、卡片仍然是"已完成"、成交笔数不会重复计。
   我另外确认了**用户真正看得见的那个持仓面板也跟着修好了**：修复前重启后显示成"只有现货、没有对冲"，
   修复后正确显示 `-0.5` 的对冲仓位。这一条 `test_r9` 自己没断言，是我补验的。

3. **生产语义一行没动。** `post_pause` / `post_delete` / `_worker_round` / `ensure_worker` 的正式代码
   在本轮 diff 里**一个字都没改**（`git show` 只有两个 hunk：test seam `_pump_worker` 和恢复名单元组）。

**我没有发现 P0/P1。** 新发现一条 P3（见 §4.1），它**目前在真实链路上打不通**，我把不可达的证据也一并附上，
不建议为它再花第 7 次授权。

## 3. 逐项核对 dispatch 要求的六件事

### 3.1 要求 1 —— P2-1：R3/R4 不再是空回归 ✅（我自己双向验过）

**代码侧**：`_pump_worker`（`service.py:942-966`）现在只在**首次注册**时 `self._stop_events[task_id] =
threading.Event()`（新建即 cleared），已存在则**保持原状**；`ensure_worker`（`service.py:889-894`）的生产
`ev.clear()` **完整保留**。`post_pause`（`service.py:537-548`）/ `post_delete`（`service.py:550-559`）/
`_worker_round`（`service.py:977-1034`）在本轮 diff 中**零改动**（`git show b9e1978 --
backend/hedge_open_tasks/service.py` 仅两个 hunk，均不在这三个函数内）。全仓 `_stop_events` 的写入点只剩三处：
`stop()` 的 `.set()`（进程关停）、`ensure_worker` 的 `.clear()`（生产）、`_pump_worker` 的首次创建（seam）。

**反向验证 A —— 把删掉的 `_wake_worker` 中断语义放回 `post_pause` / `post_delete`**
（补丁体逐字抄自 `ab3126d:service.py:852-857`，仅进程内 monkeypatch，未改任何仓库文件），
跑的是**仓库里真正的 R3/R4**：

```text
########## [基线] 当前代码，无补丁 ##########
2 passed, 17 deselected in 0.04s

########## [A] 缺陷放回 + 当前 seam ##########
>       assert svc._stop_events[doc["id"]].is_set() is False
E       assert True is False
FAILED test_r3_pause_drains_inflight_to_terminal_and_settles_no_new_pair
FAILED test_r4_delete_drains_inflight_to_terminal_and_settles_no_new_pair
2 failed, 17 deselected
```

**反向验证 B —— drain 断言本身是否也被 seam 修复"救活"了**（把新增的那条直接断言摘掉，
只看 R3 原有的四条 drain 断言）：

```text
--- [A] defect re-introduced + packet-67 seam (shipped) ---
  stop_event set right after post_pause : True
  [drain] query_calls >= 2              : False (0)
  [drain] both legs terminal            : False
  [drain] pair settled                  : False
  [drain] no new pair opened            : True
  [new]   stop event NOT set            : False
--- [B] defect re-introduced + PRE-packet-67 seam ---
  stop_event set right after post_pause : True
  [drain] query_calls >= 2              : True (2)      <- 上一轮空回归的原貌
  [drain] both legs terminal            : True
  [drain] pair settled                  : True
  [drain] no new pair opened            : True
  [new]   stop event NOT set            : False
--- [C] current code, no defect (shipped green path) ---
  stop_event set right after post_pause : False
  [drain] query_calls >= 2              : True (2)
  [drain] both legs terminal            : True
  [drain] pair settled                  : True
  [drain] no new pair opened            : True
  [new]   stop event NOT set            : True
```

这组数据与 GLM `46` §3.1 表格逐格一致，**我是独立跑出来的**。结论：seam 修复（a）与新断言（b）
**两层都承重**——(a) 让原有 drain 断言重新能抓（[A] 三条 False vs [B] 三条 True）；
(b) 即使有人把 seam 退回旧状，直接断言仍然抓得住（[B] 最后一行 False）。

**反向验证 C —— 另一种缺陷形态**（这一步 GLM 没做，我自己补的）。授权书 `27` §3.2 记载的 P1-2 原始形态其实
是"轮首先查状态就 `return True`、在对账之前退出"，它**根本不碰 stop event**，新增的直接断言看不见它。
我把这个形态塞回 `_worker_round`：

```text
##### [D] 早退状态检查放回（不碰 stop event）→ R3/R4 #####
>       assert exe.query_calls >= 2
E       assert 0 >= 2
FAILED test_r3_... / FAILED test_r4_...
```

**drain 断言把它抓住了。** 所以 R3/R4 现在对 P1-2 的**两种形态**都有效，护栏是完整的。

**校正一处上一轮的措辞**：R3/R4 在 packet 67 之前并非对任何缺陷都无效——它们对上面 [D] 这种形态一直有效；
真正被遮蔽的是 stop-event/`_wake_worker` 那一种（也正是当时实际删掉的那种）。这不改变 r4 的结论，
但按事实应当写准。

### 3.2 要求 2 —— P2-2：DONE 卡的重启恢复 ✅（我自己双向验过）

**代码侧**：`_recover_workers`（`service.py:1226`）兜底元组现为
`(D.STATUS_PAUSED, D.STATUS_STOPPED, D.STATUS_DELETED, D.STATUS_DONE)`。
`store.list_tasks(D.STATUS_DONE)` 走精确状态 else 分支（`store.py`），能正常返回 done 卡。

**反向验证 D —— 摘掉 `STATUS_DONE`**（补丁体逐字抄自 `9d1bac0` 的 `_recover_workers`，只删一个元素）：

```text
##### [基线] test_r9 当前代码 #####
1 passed, 18 deselected in 0.04s

##### [C] 去掉 STATUS_DONE 后 test_r9 #####
>       assert doc["id"] in ensured, "recovery launched a drain worker for the DONE card"
E       AssertionError: recovery launched a drain worker for the DONE card
E       assert 'a10dfd30-...' in []
FAILED test_r9_done_card_nonterminal_accepted_leg_recovered_on_restart

##### [C] 同一补丁下 R5(DELETED) #####
1 passed          <- 证明补丁是外科式的，只摘 DONE
```

失败点 `ensured == []` **精确复现** `66` §4.2 记录的现象（recovery 不拉 worker）。

**用户可见结果的端到端补验**（`test_r9` 只断言腿级事实，没断言面板；这一条是我加的）：

```text
--- [REGRESSED] fallback = (PAUSED, STOPPED, DELETED) — no DONE ---
  AFTER restart : status=done, query_calls=0, dispatch_calls=1
  positions     : [{... 'position_qty': '0', 'spot_avg': '50000', 'perp_avg': '0' ...}]
--- [SHIPPED]   fallback = (PAUSED, STOPPED, DELETED, DONE) ---
  AFTER restart : status=done, query_calls=1, dispatch_calls=1
  positions     : [{... 'position_qty': '-0.5', 'spot_avg': '50000', 'perp_avg': '50000' ...}]
```

即：修复前，一组**已经对冲好的**仓位在面板上显示成"只有现货腿、没有空头"；修复后正确显示 `-0.5` 的对冲仓位。
`aggregate_positions`（`store.py`）只排除 `DELETED`，**包含 `DONE`**，所以这条修复确实打通到用户界面。

**安全性四问，逐条核实**：

| 问题 | 结论 | 证据 |
| --- | --- | --- |
| 会不会重新开新组？ | 不会 | `_worker_round:1012-1013` 无在飞腿后 `status != RUNNING` 即退出；`test_r9` 断言 `dispatch_calls == posts_before == 1`；我的探针同样 `dispatch_calls=1` |
| 会不会重发写请求？ | 不会 | 恢复路径只调 `query_leg`（按 clientOrderId），ADR-2 未被触碰；`dispatch_calls` 不增 |
| `status` 是否保持 `done` sticky？ | 是 | `test_r9` 断言 + 我的探针 `status=done` |
| `finalize_attempt` 是否幂等？ | 是 | `store.py:998-1000`：`if attempt["pair_outcome"] is not None: return None`；而 `resolve_attempt`（`store.py:940-947`）在把任务推到 done 的同时必然写入 `pair_outcome`，故 done 卡的该 attempt 永远已 resolved。`test_r9` 断言 `accepted_pair_count == 1` |

### 3.3 要求 3 —— GLM 主动声明的剩余风险是否成立 ✅ 声明属实，不构成新缺陷

`46` §5 自陈"`_pump_worker` 去 clear 后，同实例先 `service.stop()` 再 `_pump_worker` 会短路"。**核实结果：属实，
且当前无害。**

- 全仓只有两个测试文件用 `_pump_worker`（`test_hedge_task_local.py`、`test_hedge_review2_regressions.py`）；
  后者**没有任何 `.stop()` 调用**。
- 前者的 4 处 `svc.stop()`（第 426 / 791 / 867 / 997 行）中，前三处紧跟 `del svc1` + **换新实例**
  （新实例 `_stop_events` 为空字典），第四处在用例末尾。**没有任何用例采用 stop→pump 模式。**
- **生产路径不受影响**：`_pump_worker` 是纯 test seam（生产走 `ensure_worker` + `_run_task_worker`），
  而 `service.stop()` 只在进程关停 / `close()` 时调用。

判定：这是 seam 的**预期新语义**（正是"让中断语义可被同步观测"所要求的），不是缺陷。
GLM 把它主动写进剩余风险，是正确的做法。

### 3.4 要求 4 —— reviewer 可选项 (c) 被拒的合理性 ✅ 可接受，记为 follow-up

`66` §4.5 与授权书 `27` §5.1(c) 都把"R3 真实线程版"标为**可选**。GLM 的理由（`46` §2）是：
真实线程路径已在 `66` §3.2 由 reviewer 用真实 worker 独立复验为正确；当前 seam 修复 + 新断言已让同步回归有效；
按最小修改原则不加。

**我的判断：可接受。** 理由是新断言与 drain 断言都是**状态观测**而非线程时序观测——
无论 worker 是同步 pump 还是真实线程，"`post_pause` 置没置位 stop event""在飞腿有没有被查到终态"这两件事
的判定逻辑完全相同（`_worker_round` 是两条路径共用的循环体）。§3.1 的 [A]/[D] 两组实验已证明这两层护栏
对两种缺陷形态都能触发。真实线程版能额外覆盖的是 `_run_task_worker` 的 pacing `ev.wait()` 分支
（`service.py:924-928`）——那一段本轮未改，且 `test_1` / `test_2` / `test_3` 已用真实线程 + Barrier 覆盖。

建议作为 **follow-up** 记录（非本轮阻塞项，且 `rework_count` 已 6/6）。

### 3.5 要求 5 —— 既有底线不回归 ✅

packet 65 四项（本轮**未触碰**其任何生产代码，`git show` 两个 hunk 均不在其中）+ 其余底线，
逐条在本机复跑确认：

| 底线 | 证据 |
| --- | --- |
| 429 恢复清粘滞 + 逐次尝试 `rate_limited` 标记 | `test_r1` / `test_r2` 绿 |
| 人工 pause/delete 由本卡 worker drain 后退出、不开新组 | `test_r3` / `test_r4` 绿（且现在真能抓缺陷，§3.1） |
| `settle_attempt_no_counters` 按两腿真实事实推导 + `leg_exposure` | `test_r6` 绿 |
| `worker_active` 三态 + `last_worker_exit_reason` | `test_r7` / `test_r8` 绿 |
| H-1：live start 一次恢复后返回 / live tick 安全空操作 / 手动 Start 只指定卡 | `test_6a` / `test_6b` / `test_6c` 绿；`service.py:392-410`、`tick()` live 分支 `return False` 复读确认 |
| 每卡有界 worker、同卡串行、双腿并发、跨卡隔离 | `test_1`–`test_4b` 绿 |
| `target_n` 原子上限 | `test_1_target_n_one_yields_at_most_one_attempt_and_one_post`（3 参数化）绿 |
| clientOrderId-only 查询且不重发（ADR-2） | `test_5` / `test_r5` / `test_r9` 绿；`dispatch_calls` 恒不增 |
| store 锁内不调 executor（Q6） | `test_hedge_purity.py` 全绿（906 全量内） |
| preflight price fail-closed / 7 端点冻结 allowlist / 签名前置门 | 所在文件本轮**零改动**；复读 `hedge_open_live_client.py:57-71`（7 条）与 `:139-142`（签名前 `PermissionError`）确认 |
| real POST 默认关闭 | `store.py:129` `start_gate INTEGER NOT NULL DEFAULT 0`，初始化 `INSERT ... VALUES (1, 0, ...)`；`config.py` 本轮零改动 |
| `_ENTRY_EVENT_KINDS` 未新增 kind | 本轮 diff 中该标识符命中数 = 0 |
| entries 独立分页兼容旧 logs | 相关文件本轮零改动 |
| `frontend/**` 零改动 | `git diff --stat e10b395..b9e1978 -- frontend/` 输出为空（frontend 最后一次改动是 `8af3f22`，远早于本轮） |
| `_wake_worker` 无残留 | 全仓 grep 只命中两处**注释**，无可执行残留 |
| 无新增全局守护 / 周期扫描器 / timer | 本轮唯一新增执行语义是恢复名单多一个状态值；无 `Thread(` / `Timer(` / `while True` 新增 |
| 零凭据 | 本轮新增行 grep `api_key\|secret\|BINANCE_\|password\|token` 为空 |

### 3.6 要求 6 —— 测试与范围 ✅ 数据逐条对得上

本机独立复跑（`.venv/bin/python`），与 packet 67 / `60-test-output.txt` 的记录一致：

| 命令 | 本轮我实测 | GLM 声称 | 上一轮基线 |
| --- | --- | --- | --- |
| 十组聚焦 | **230 passed** in 15.10s | 230 ✅ | 229（+1 = R9） |
| `pytest backend/tests -q` | **906 passed** in 45.36s | 906 ✅ | 905（+1 = R9） |
| `node frontend/self-check.js` | **全部自检通过**，exit 0 | 通过 ✅ | 通过 |
| `pytest scripts/tests/test_validate_stage_dispatch_protocol.py -q` | **55 passed** in 0.75s | 55 ✅ | 55 |
| `git diff --check` | exit 0 | exit 0 ✅ | exit 0 |
| `validate-stage --phase pre-review` | PASSED | — | PASSED |

`test_hedge_task_local.py` 19 条全绿，逐条列名核对：`test_1`–`test_4b`、`test_5`、`test_6a/6b/6c`、
`test_r1`–`test_r9` 齐备，R9 为本轮新增。工作树干净，无越界文件，无凭据，无实盘激活。

## 4. Findings

### P3-1（本轮新发现）—— `store.pause_task` 无状态守卫：恢复期 drain 信号会把非 running 卡翻成 `paused`（**目前生产不可达**）

**机制**：`_worker_round`（`service.py:998-1007`）在 `_reconcile_own_legs` 返回 drain 信号时无条件调
`_pause_task_local` → `store.pause_task`，而后者是一条**没有任何状态守卫**的
`UPDATE hedge_open_task SET status='paused', stop_reason=NULL WHERE id=?`。
本轮把 `DONE` 放进恢复名单后，"被恢复 worker 服务的非 running 卡"这个集合又扩大了一档。

**离线实测**（用一个 `rate_limited=True` 的**假想** query verdict 驱动）：

```text
--- [packet 67] DONE card, recovery query hits 429 ---
  status before restart / AFTER : done -> paused (pause_reason=rate_limited)
--- [packet 65] DELETED card, recovery query hits 429 ---
  status before restart / AFTER : deleted -> paused        <- 被删的卡"复活"成已暂停
--- [base] STOPPED card, recovery query hits 429 ---
  status before restart / AFTER : stopped -> paused, stop_reason 被清成 NULL
```

**但它在真实链路上打不通，我把不可达证据也附上**：`_reconcile_own_legs`（`service.py:1072-1075`）
只在 `verdict.error_category == "insufficient_funds"` 或 `verdict.rate_limited` 为真时产出 drain 信号；
而查询路径的唯一分类器 `classify_query_response`（`live_hedge_executor.py:288-341`）
在 429 时**直接 `return None`**（第 297-298 行），其余返回值全部走 `LegDispatch`/`_empty_dispatch` 的默认值
`rate_limited=False`，`error_category` 只可能是 `None` 或 `"absent"`——**永远不会**是
`insufficient_funds`。所以生产执行器 `LiveHedgeExecutor` 下，恢复 worker 的 drain 信号恒为 `None`，
上表现象无法发生。

**影响**：目前为零。属于**潜伏性稳健度缺口**：一旦将来有人让查询分类器surface 429 或资金不足事实
（这在"主动节流"这个已记录的 follow-up 里是很自然的一步），deleted 卡会复活成 paused、
stopped 卡会丢掉 fatal `stop_reason`、done 卡会失去 sticky。金额安全仍有 `target_n` 原子上限
与 `status != RUNNING` 退出兜住，不会越权下单。

**性质说明（对实现者公平）**：`STOPPED` 分支在 base 提交即存在，`DELETED` 由 packet 65 引入，
本轮只是把同一模式扩到 `DONE`。**这不是 packet 67 引入的回归**，`46` 报告未提及也不构成失职。

**建议（follow-up，不在本轮）**：给 `pause_task` 或 `_pause_task_local` 加一条状态守卫——
只有 `status == RUNNING` 的卡才允许被 drain 信号翻成 `paused`；非 running 卡记录事件即可。
**`rework_count` 已 6/6，此项不值得动用第 7 次授权。**

### P3-2 ～ P3-4（沿用，未在本轮修复，符合授权书 `27` §5.3）

- **P3-2**（原 `66` P3-1）：`settle_attempt_no_counters` 不落 attempt 级
  `error_category` / `error_code` / `error_reason_zh`。仅可观测性；本轮复核 `classify_query_response`
  仍只产出 `absent`，**无安全后果**。
- **P3-3**（原 `66` P3-2）：人工 Start 撞上 worker 退出窗口可能静默空转（`ensure_worker:886-888`）。
  既存、极窄，已被 `worker_active` 可见化。
- **P3-4**（原 `66` P3-3）：`post_start` 响应把派发前任务行与派发后 `worker_active` 拼在一起。纯展示层。
- **新增 follow-up**：`66` §4.5 的可选项 (c)（R3 真实线程版）经本轮判定为可接受的取舍（§3.4），
  建议记为 follow-up 而非缺陷。

## 5. 结论与理由

**verdict = ACCEPT。**

用户授权书 `27` §8 的六条验收条件，我逐条独立验证后全部达成：

1. R3/R4 在 `_wake_worker` 中断被放回时**确实失败**（§3.1 [A]），当前代码下**全绿**（基线）——
   而且我额外证明了它对另一种缺陷形态（早退状态检查）同样有效（§3.1 [D]）；
2. done 卡带受理但非终态腿 → 重启一次 recovery → 该腿被查到终态、`dispatch_calls` 不增、
   `status` 仍 `done`、`accepted_pair_count` 不重复计（§3.2），并且**用户可见的持仓面板确实被修好**；
3. `backend/tests` 906 全绿、前端自检全通过、Harness 55 全绿、`git diff --check` exit 0（§3.6，我实测）；
4. `test_6a/6b/6c` 与 `test_1`–`test_5`、`test_4b`、R1–R8 仍全绿；未新增任何全局守护 / 定时器 / 周期扫描器（§3.5）；
5. `frontend/**` 零改动；`_ENTRY_EVENT_KINDS` 未新增 kind；`store.py` / `domain.py` / `backend/services/**`
   本轮零改动（§1、§3.5）；
6. 全程零真实 POST、零私有网络、零凭据访问、零 live 启用、零 Start（§3.5、§1）。

**没有 P0/P1。** 唯一的新发现 P3-1 在生产链路上不可达（我附了不可达证据），且不是本轮引入；
其余 P3 均为已登记的 follow-up。生产语义在本轮**一行未动**，这正是有界返工应有的样子。

**关于 `rework_count` 6/6 的明确提示**：本 stage 的返工上限已经用满
（`status.json`：`rework_count=6`，`max_rework=6`）。**任何进一步的代码变更——包括本报告
§4 的全部 P3 与 follow-up——都必须先取得用户新的书面授权**，bookkeeper 不得直接派发。
本报告不建议为它们再开一轮：它们要么不可达、要么纯观测性。

前端 Review-1 的 ACCEPT 应予保留：`frontend/**` 自 `8af3f22` 之后零改动，本轮区间内同样零改动。

**实盘门未被本轮解除。** 本报告不构成开启 live / Start / 凭据 / 真实下单的任何授权。

---

当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/68-review-1-backend-r5.md
本地北京时间: 2026-07-26 07:13:04 CST
下一步模型: bookkeeper
下一步任务: validate this renewed backend Review-1 ACCEPT verdict and route it together with the preserved frontend ACCEPT toward Review-2

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-hedge-open-real-api-v1",
  "role": "first_reviewer",
  "model": "Claude Opus 5",
  "verdict": "ACCEPT",
  "diff_fingerprint": "b9e1978eaffd047b7871b8721f511307e75fde68:604caada1043e8334f33b1cc73239f1cf6bb19017db1dc68374679cf6ac99ddd",
  "reviewer_prior_involvement": "none",
  "reviewer_prior_involvement_notes": "Claude Opus 5 wrote no reviewed code and is not the fix author (the implementer and packet-67 fix author is Claude-GLM, provider zhipu_glm — provider isolation holds). Disclosure: this same model produced the prior read-only backend Review-1 reports in this stage (30-review-1-backend.md, 58-review-1-backend-r2.md, 64-review-1-backend-r3.md, 66-review-1-backend-r4.md) and, since 2026-07-25, also serves as this stage's bookkeeper after Codex ran out of quota (status.json.bookkeeper.dual_hat_disclosure, 27-user-authorized-r4-repair.md §6). Neither role is code or fix authorship, and neither involved direction synthesis, development breakdown, or design, hence the enum value 'none'. Per the dispatch, no prior-round conclusion and no bookkeeper reconciliation was carried forward as established fact: every judgement here was re-derived from the pinned 28c550d..b9e1978 diff, the current sources, locally re-run tests, and four NEW monkeypatch-only reverse-verification experiments written in this session (zero repo files modified).",
  "reviewed_artifacts": [
    "AGENTS.md",
    "workflows/templates/stage-delivery.yaml",
    "schemas/review-verdict.schema.json",
    "scripts/validate-stage.py",
    "docs/product/PRD.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/00-task.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/06-direction-synthesis.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/10-design.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/11-adr.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/15-immediate-loop-and-open-log-amendment.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/16-replacement-development-breakdown.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/21-task-local-runtime-and-manual-pause-amendment.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/24-user-authorized-final-guardian-fix.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/26-user-authorized-settlement-and-pause-fix.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/27-user-authorized-r4-repair.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/50-review-2.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/58-review-1-backend-r2.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/64-review-1-backend-r3.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/66-review-1-backend-r4.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/40-fix-review-1-backend-r2.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/42-final-guardian-scanner-fix.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/44-fix-review-1-backend-r3.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/46-fix-review-1-backend-r4.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/60-test-output.txt",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/67-fix-review-1-backend-r4.dispatch.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/status.json",
    "git diff --binary 28c550d87c1ca90983d5bde9c7102d42cffecd4e..b9e1978eaffd047b7871b8721f511307e75fde68",
    "backend/hedge_open_tasks/service.py",
    "backend/hedge_open_tasks/store.py",
    "backend/services/live_hedge_executor.py",
    "backend/services/hedge_open_live_client.py",
    "backend/tests/test_hedge_task_local.py",
    "backend/tests/test_hedge_review2_regressions.py"
  ],
  "findings": [
    {
      "severity": "P3",
      "title": "store.pause_task has no status guard, so a recovery worker's drain signal would flip a non-running card to paused (currently unreachable in production)",
      "file": "backend/hedge_open_tasks/store.py",
      "line": 1,
      "evidence": "_worker_round (service.py:998-1007) calls _pause_task_local unconditionally on a drain signal, and store.pause_task is an unguarded UPDATE hedge_open_task SET status='paused', stop_reason=NULL WHERE id=?. Reviewer offline probe (monkeypatch only, zero repo files touched, a hypothetical rate_limited=True query verdict): 'DONE card, recovery query hits 429: done -> paused'; 'DELETED card: deleted -> paused' (a deleted card resurrects as paused); 'STOPPED card: stopped -> paused, stop_reason cleared to NULL'. UNREACHABILITY PROOF: _reconcile_own_legs (service.py:1072-1075) only emits a drain signal when verdict.error_category == 'insufficient_funds' or verdict.rate_limited is true; the sole query classifier classify_query_response (live_hedge_executor.py:288-341) returns None outright on a 429 (lines 297-298) and every value it does return uses the LegDispatch/_empty_dispatch defaults rate_limited=False with error_category limited to None or 'absent'. With the production LiveHedgeExecutor the recovery drain signal is therefore always None and the probe's behaviour cannot occur.",
      "impact": "Zero today. It is a latent robustness gap: if any future query classifier ever surfaces a 429 or an insufficient-funds fact (a natural step for the already-recorded X-MBX-ORDER-COUNT-* active-throttling follow-up), a DELETED card would resurrect as paused, a STOPPED card would lose its fatal stop_reason, and a DONE card would lose its sticky status. Money safety still holds either way: the atomic target_n cap and the status != RUNNING worker exit prevent any unauthorized order. FAIRNESS NOTE: the STOPPED branch exists at the base commit and DELETED was added by packet 65; packet 67 only extended the same pattern to DONE. This is NOT a regression introduced by the reviewed change, and 46-fix-review-1-backend-r4.md is not at fault for omitting it.",
      "recommendation": "Follow-up only: guard pause_task (or _pause_task_local) so a drain signal can only move a card to paused when its status is RUNNING; for a non-running card, record the event without changing status. rework_count is already 6/6, so this must not consume a 7th authorization — it is unreachable in production today."
    },
    {
      "severity": "P3",
      "title": "settle_attempt_no_counters still does not stamp the attempt-level error_category / error_code / error_reason_zh columns",
      "file": "backend/hedge_open_tasks/store.py",
      "line": 1,
      "evidence": "Carried over from 66-review-1-backend-r4.md P3-1 and explicitly excluded from the authorization (27-user-authorized-r4-repair.md §5.3). finalize_attempt writes those three columns; settle_attempt_no_counters writes only pair_outcome. Re-verified this round: classify_query_response (live_hedge_executor.py:288-341) can still only emit error_category 'absent', never 'fatal'.",
      "impact": "Observability/audit only; no safety consequence, since a rate-limited pair cannot swallow a fatal-stop obligation.",
      "recommendation": "Follow-up: carry the same three columns through the settle path. Requires a new user authorization (rework_count 6/6)."
    },
    {
      "severity": "P3",
      "title": "A manual Start landing inside a worker's exit window can still silently no-op",
      "file": "backend/hedge_open_tasks/service.py",
      "line": 886,
      "evidence": "Carried over from 66-review-1-backend-r4.md P3-2 and excluded from the authorization (27 §5.3). ensure_worker reuses the registry entry whenever existing.is_alive(), so a post_start racing the thread's finally-block pop returns 200 without launching a worker. Unchanged this round (ensure_worker is untouched by the packet-67 diff).",
      "impact": "Narrow and pre-existing; the operator can detect it via worker_active=false together with status=running.",
      "recommendation": "Follow-up: confirm the reused thread is not already exiting, or surface a 'press Start again' hint in the frontend. Requires a new user authorization."
    },
    {
      "severity": "P3",
      "title": "post_start's response still mixes a pre-spawn task row with a post-spawn worker_active",
      "file": "backend/hedge_open_tasks/service.py",
      "line": 530,
      "evidence": "Carried over from 66-review-1-backend-r4.md P3-3 and excluded from the authorization (27 §5.3). post_start captures `updated` before ensure_worker and projects it afterwards. Unchanged this round.",
      "impact": "Cosmetic, single-response internal inconsistency; the next GET is self-consistent.",
      "recommendation": "Follow-up: re-read the task row after ensure_worker before projecting. Requires a new user authorization."
    }
  ],
  "required_fixes": [],
  "residual_risks": [
    "P3-1: store.pause_task has no status guard; unreachable in production today because classify_query_response never surfaces a 429 or an insufficient-funds fact on the query path, but it becomes live the moment any query classifier does.",
    "The reviewer's optional item (c) from 66-review-1-backend-r4.md — a real-thread variant of R3 — was declined by the implementer and is accepted as a reasonable trade-off: the new assertion and the drain assertions are state observations shared by both the pumped and the threaded path (_worker_round is common to both), and this reviewer independently proved R3/R4 now fail under BOTH shapes of the P1-2 defect (the _wake_worker/stop-event shape and the early status-check-before-reconcile shape). The pacing ev.wait() branch in _run_task_worker remains covered only by test_1/test_2/test_3. Recorded as follow-up.",
    "_pump_worker no longer clears an existing stop event, so a same-instance 'service.stop() then _pump_worker' would short-circuit. Verified harmless: no test uses that pattern (the four svc.stop() call sites in test_hedge_task_local.py are each followed by del + a fresh instance or end the test, and test_hedge_review2_regressions.py never calls stop()), and _pump_worker is a test-only seam while service.stop() runs only at process shutdown.",
    "A DONE card whose recovery drain returns a confirmed-absent verdict for a leg that had already been counted as accepted keeps accepted_pair_count at its earlier value, because finalize_attempt early-returns on an already-resolved attempt. This is inherent to the count-at-accept/reconcile-later model that predates this round and applies equally to PAUSED/STOPPED/DELETED recovery.",
    "Startup recovery now enumerates DONE tasks as well, so the one-shot handoff runs one list_non_terminal_legs_for_task query per done card. Bounded by card count; not a defect.",
    "P3-2 / P3-3 / P3-4 carried over from 66-review-1-backend-r4.md, all excluded from the authorization by 27 §5.3.",
    "Cross-process reservation guard (prepare_attempt relying on SQLite DEFERRED read-then-write) remains unaddressed by explicit user decision (26-...fix.md §4.6); only reachable if two service processes share one sqlite file, which is not the deployment.",
    "Active throttling on X-MBX-ORDER-COUNT-* response headers is still unimplemented and truthfully recorded.",
    "worker_active is an instantaneous best-effort snapshot of the _workers registry, not a strongly consistent lock — designed semantics, not a defect.",
    "aggregate_positions filters out DELETED tasks (pre-existing at base), so a deleted card's real single-leg exposure disappears from the positions panel even though the drain settles it correctly. DONE cards are NOT filtered, which is why the P2-2 fix does repair the user-visible panel (reviewer-verified end to end).",
    "rework_count is 6/6 (max_rework 6). Any further code change in this stage — including every P3 and follow-up in this report — requires a NEW written user authorization; the bookkeeper must not dispatch one on its own.",
    "This ACCEPT does not release any live gate: no real POST, Start, credential access, or Binance traffic is authorized by it."
  ],
  "next_action": "continue"
}
```

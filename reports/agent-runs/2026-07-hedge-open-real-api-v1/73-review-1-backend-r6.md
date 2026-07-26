# Review-1（第一轮交叉复核 · 后端 · r6）

结论：**ACCEPT**（0 条 P0/P1；2 条 P2；4 条 P3）。

本轮授权范围内的四项（Review-2 的 F1 / F2 / F4 + finding-6 的 validator 剩余项）在固定提交范围
`28c550d..77c75bd` 上**全部真实落地**，并且每一项我都自己重新读代码、自己跑测试、自己用离线探针做了
反向验证，没有采信实现报告或 bookkeeper 核对结果的任何声称。既有底线（H-1 三防线、每卡有界 worker、
同卡串行 / 双腿并发、跨卡隔离、`target_n` 原子上限、clientOrderId-only 查询且绝不重发、store 锁内不调
executor、preflight fail-closed、real POST 默认关闭、7 端点冻结 allowlist、`_ENTRY_EVENT_KINDS` 未新增
kind、entries 分页兼容、`R1`–`R9`）全部仍然成立，`frontend/**` 本轮零改动。

**本次 ACCEPT 不解除任何实盘门。** live 启用、Start 全局闸门、第一笔真实订单仍然各自需要独立的人类
书面授权；本报告不构成用户验收，也不授权把 stage 分支合并回 `main`。

---

## 1. 审查身份、隔离与披露

- 审查者：**Claude Opus 5**（Anthropic），角色 `first_reviewer`（后端）。
- 被审后端代码的实现/返工作者是 **Claude-GLM（`glm-5.2[1m]`，`zhipu_glm`）**；我与其供应商隔离成立，
  我未编写本 stage 的任何交付代码或修复代码，故 `reviewer_prior_involvement = none`。
- **如实披露（两项，均非代码/修复作者身份）**：
  1. 同一模型（Claude Opus 5）此前产出过后端 Review-1 的 **r2/r3/r4/r5** 四轮只读评审报告
     （`58` / `64` / `66` / `68`）。
  2. 同一模型自 **2026-07-25** 起兼任本 stage 的 **bookkeeper**（Codex 配额耗尽后接任），
     因此 `27`、`28`、`72`、`73` 等授权书与 packet 是该角色的簿记输出。
     见 `status.json.bookkeeper.dual_hat_disclosure` 与 `27-user-authorized-r4-repair.md` §6。
- 本会话是**全新的只读会话**，不是撰写 r2–r5 与 packet 的那个 bookkeeper 会话
  （`review_1_requires_fresh_read_only_session` 满足）。
- **我没有把任何既有结论当作本轮已成立的事实**：r5 的 ACCEPT、`71-fix-review-2-backend-r7.md` 的
  自述、bookkeeper 在 `status.json` 里的核对记录，本轮都只作为"待验证的声称"处理。下文每一条判断
  都附有我自己产生的可复核证据（命令、原始输出、探针输出）。
- 只读边界：全程零凭据读取、零 Binance 连接、零真实 POST、零 live 启用、零 Start、零 commit、
  零业务文件修改。唯一写入是本报告文件；探针脚本写在会话临时目录
  （`/private/tmp/.../scratchpad/probe_r6.py`），不进仓库。

---

## 2. 固定锚点与门禁核对（全部独立复算）

| 项 | 结果 |
| --- | --- |
| 分支 | `stage/2026-07-hedge-open-real-api-v1` |
| base | `28c550d87c1ca90983d5bde9c7102d42cffecd4e` |
| head | `77c75bd855c3d1a7a4c91700f9db953919df087f` |
| head 是当前 HEAD 的祖先 | 是（`git merge-base --is-ancestor` 通过） |
| 工作树 | 干净（`git status --porcelain` 空） |
| 指纹（我独立重算） | `77c75bd…:aa0406dae9cb90004d5dd15c2a936ad9a021a0c01a50f985d4efab5900e652dd` ✅ 与派发值**逐字一致** |

指纹按 `AGENTS.md:346-350` 的唯一方案独立重算：

```bash
git diff --binary 28c550d..77c75bd -- . ":(exclude)reports/agent-runs/2026-07-hedge-open-real-api-v1/status.json" | shasum -a 256
# aa0406dae9cb90004d5dd15c2a936ad9a021a0c01a50f985d4efab5900e652dd
```

**关于"用固定范围而非移动 HEAD"**：当前 `HEAD = 75b55b9`，比固定 head 晚两个提交。我核对了
`git diff --name-only 77c75bd..HEAD`，结果只有三个簿记文件（`70-handoff.md`、
`73-review-1-backend-r6.dispatch.md`、`status.json`），**零业务文件**。因此我在工作树上跑出的测试结果
可以合法地归属到固定锚点 `77c75bd`；所有业务判断均来自固定 diff 与固定范围的源码。

### 2.1 我自己复跑的自测（原始输出）

```text
.venv/bin/python -m pytest backend/tests -q
918 passed in 45.92s

node frontend/self-check.js
（13 项全部 [PASS]）全部自检通过

.venv/bin/python -m pytest scripts/tests/test_validate_stage_dispatch_protocol.py -q
67 passed in 1.14s

.venv/bin/python scripts/validate-stage.py 2026-07-hedge-open-real-api-v1 --phase pre-review
STAGE VALIDATION PASSED
stage=reports/agent-runs/2026-07-hedge-open-real-api-v1
phase=pre-review
status=review_1
diff_fingerprint=77c75bd855c3d1a7a4c91700f9db953919df087f:aa0406dae9cb90004d5dd15c2a936ad9a021a0c01a50f985d4efab5900e652dd
exit=0

git diff --check
exit=0

# 28 §5 的十组聚焦套件（我另外复跑）
.venv/bin/python -m pytest backend/tests/test_hedge_task_local.py \
  backend/tests/test_hedge_review2_regressions.py backend/tests/test_hedge_service.py \
  backend/tests/test_hedge_store.py backend/tests/test_hedge_domain.py \
  backend/tests/test_hedge_api.py backend/tests/test_hedge_open_live_client.py \
  backend/tests/test_live_hedge_executor.py backend/tests/test_hedge_purity.py -q
227 passed in 14.91s
```

`71-fix-review-2-backend-r7.md` 声称的 **227 focused / 918 backend / 67 validator / 前端自检 /
`git diff --check` 干净**，与我本机独立复跑的数字**逐项吻合**。

---

## 3. 逐项验证结论（本轮授权的四项）

### 3.1 F1 —— single_leg 计入连续失败刹车 + 计划组用尽转 done ✅（主体成立，留一处 P2 残口）

**代码事实**（`store.py:758-776`、`domain.py:916-940`）：`ATTEMPT_SINGLE_LEG_EXPOSURE` 分支现在
`new_fail = fail_count + 1`、`new_consecutive = consecutive + 1`，并把该 category 一起送进
`resolve_status_after_attempt`（该函数的判定条件由 `category == ATTEMPT_FAILED` 扩为
`category in (ATTEMPT_FAILED, ATTEMPT_SINGLE_LEG_EXPOSURE)`），达到阈值时 `pause_reason` 写
`consecutive_submission_failure`；`leg_exposure` 仍然照旧记录。

**429 免计数未回归**：`skip_counters=True`（限频组由 `settle_attempt_no_counters` 结算）在
`store.py:713-730` 提前分流，只推导真实的 `pair_outcome` 与 advisory `leg_exposure`，
**不触碰任何计数器 / 状态 / 阈值 / pause_reason**。这一点我用探针实测确认，而不是读注释。

**我的反向验证（PROBE 1 / PROBE 2，原始输出）**：

```text
PROBE 1 — 连续三组非限频 single_leg（target_n=10, threshold=3）
  round 1: status=running sched=1 fail=1 consec=1 pause_reason=None
  round 2: status=running sched=2 fail=2 consec=2 pause_reason=None
  round 3: status=paused  sched=3 fail=3 consec=3 pause_reason=consecutive_submission_failure
  round 4: status=paused  sched=3 fail=3 consec=3   ← 暂停后不再开新组
  round 5: status=paused  sched=3 fail=3 consec=3

PROBE 2 — 限频（rate_limited=True）的 single_leg 组
  status=paused fail=0 consec=0 pause_reason=rate_limited      ← 429 仍然完全免计数
```

Review-2 当时实测的 `fail_count=0 / consecutive=0 / status=running` 已不复现；单腿敞口仍被记录，
且**在阈值以下不冻结调度**（`resolve_status_after_attempt` 只在 `>= threshold` 时才返回 `paused`，
`test_resolve_single_leg_below_threshold_stays_running` 与 PROBE 1 的 round 1/2 双向证明）。

**计划组用尽转 done**：`store.py:781-796` 在"非 skip_counters + `pair_outcome` 非空 + 状态仍是
`running` + `scheduled_attempt_count >= target_n`"时置 `done`。PROBE 4 实测：崩溃缝隙组被恢复后任务
继续开完剩余计划组，最终 `sched=3/target=3 → status=done`，`attempts=3`，`dispatch_calls=2`
（硬上限未被突破）。

**残口（见 P2-1）**：该转换只发生在"结算那一刻任务仍是 running"。若最后一组是在
`paused` 下结算（例如最后一组撞 429，或刚好在阈值处被刹车暂停），任务合法地停在 `paused`；
此后**人工点 Start 恢复**，任务会被置回 `running`，而 worker 立刻以 `target_reached` 退出，
卡片就**永久停在"运行中"**。我已实测复现，详见 P2-1。

**关于 `consecutive_submission_failures` 的语义变更（派发点名要我判断的一项）**：
- **与已批准的产品语义一致**。`16-replacement-development-breakdown.md:84-90` 明确要求非致命
  `single_leg` 增加连续失败计数，Review-2 F1 亦以此为依据；`28` §2.1 是用户对该要求的书面授权。
  本轮实现与该合同一致，而**不一致的反而是改前的代码**。
- **字段集未变，前端无需改代码，`frontend/**` 零改动的前提成立**（我核对 packet 72 改动文件清单，
  `frontend/` 命中数为 0）。
- **但应记一条前端展示 follow-up（P3-1）**：`frontend/index.html:3691` 的文案是
  "连续提交失败 N / 暂停阈值 M"，`domain.py:1154` 的暂停文案是"连续提交失败达到阈值…"。
  在新语义下，这个计数会因"一条腿已被受理"的组而增长——操作者可能把"连续提交失败 2"误读成
  "两组一单未发出"，而事实上可能已经有 2 张真实成交的裸腿。建议下一个前端 stage 把文案调整为
  "连续未成对 N 组"之类的表述（纯文案，不改行为、不改字段）。

### 3.2 F2 —— 查询分类与查询阶段限频 ✅（本轮风险最高项，逐格反向验证通过，无矫枉过正）

我**没有**只看 `classify_query_response` 的注释，而是构造 14 种响应逐格实测
（`live_hedge_executor.py:288-357`）：

```text
PROBE 3 — classify_query_response 反向验证矩阵
  HTTP 200 no orderId          -> UNKNOWN_QUERYING rate_limited=False          ← 不再误闭合为"不存在"
  HTTP 200 orderId=7 FILLED    -> ACCEPTED_OR_QUERYING
  HTTP 404                     -> TERMINAL_RECORDED err=-2013/absent           ← 显式 absent 才闭合
  HTTP 400 -2013               -> TERMINAL_RECORDED err=-2013/absent
  HTTP 429 Retry-After=7       -> UNKNOWN_QUERYING rate_limited=True retry=7   ← typed 限频信号
  HTTP 418 ban                 -> UNKNOWN_QUERYING rate_limited=True
  HTTP 400 -1003               -> UNKNOWN_QUERYING rate_limited=True
  HTTP 500                     -> None（inconclusive，继续查）                  ← 未被矫枉过正
  HTTP 503 (-1008)             -> None
  transport error              -> None
  HTTP 401 auth -1022          -> None                                          ← auth 4xx 仍是 None
  HTTP 403 WAF                 -> None
  HTTP 400 其它 -1102          -> None
  HTTP 200 body=list（非 dict）-> None
```

派发点名要我自己核验的三类（**5xx / transport error / auth 4xx 是否仍然返回 `None`**）：
**三类全部仍然返回 `None`**，没有被误改成 absent，也没有被误标成 rate-limited。
唯一变成 typed 限频的就是 429 / 418 / `-1003` 三种。

**服务层链路**（`service.py:1055-1064`、`997-1006`）：查询回来带 `rate_limited=True` 时，
`_reconcile_own_legs` **在腿解析之前** `continue`，腿被原样留在非终态（未 `resolve_leg_from_query`、
未加入 `finalized`），只上抛 `SIGNAL_RATE_LIMITED`；`_worker_round` 随即
`_pause_task_local(rate_limited)` 并 **`return True` 退出**（旧代码是 `return False` 继续轮询，
正是 Review-2 指出的"按一秒节奏继续查询、可能把 429 推向 418"）。

```text
PROBE 6 — 查询阶段 429（POST 本身未限频）
  status=paused pause_reason=rate_limited
  nonterminal_legs=2        ← 未决腿被保留，未被误判终态
  dispatch_calls=1          ← 零重发 POST
  query_calls=2
```

`test_7e_query_phase_rate_limited_pauses_keeps_pending_no_resend` 是这条路径的确定性回归，
且它与 `test_7d`（POST 阶段 429）互不重叠。执行器侧的合并
（`live_hedge_executor.py:450-472`：`rate_limited = verdict.rate_limited or resolved.rate_limited`）
让"POST 未限频、best-effort 查询限频"这种组合也能把限频事实带出来，方向正确。

**发现两处非阻断问题**：查询阶段 429 的退出**没有写 `worker_exit_reason`**（P3-2），
以及限频后仍会把同组另一条腿再查一次（P3-3）。详见 findings。

### 3.3 F4 —— 两腿终态但 `pair_outcome` 为 NULL 的崩溃缝隙 ✅

**代码事实**：新增 `store.list_unsettled_terminal_attempts_for_task`（`store.py:1304-1326`，
`pair_outcome IS NULL AND NOT EXISTS(非终态腿)`，按 `attempt_seq, id` 定序，**单卡作用域**）；
`service._recover_crash_gaps`（`service.py:1111-1133`）按 `attempt.rate_limited` 分流到
`settle_attempt_no_counters` / `finalize_attempt`，两者都以 `pair_outcome is not None` 提前返回，
天然幂等；`_recover_workers`（`service.py:1268-1281`）把"存在崩溃缝隙"也纳入**一次性启动交接**的
relaunch 条件。

**零常驻扫描器**：`_recover_crash_gaps` 的全部调用点只有 `_reconcile_own_legs`（worker 轮次内）
与启动时的 `_recover_workers`；`grep` 全仓确认无第三个调用点、无 timer、无 `while True`、
无新线程（packet 72 的后端 diff 中 `Timer|threading.Thread|while True|time.sleep` 零命中）。
`test_hedge_purity.py` 与 H-1 三防线（`test_6a/6b/6c`）在 918 全绿中通过。

**我的反向验证（PROBE 4 / PROBE 8）**：

```text
PROBE 4 — running 且未达 target 的崩溃缝隙（target_n=3）
  before:        nonterminal_legs=[]  pair_outcome=None        ← 缺陷态构造成立（无腿可 drain）
  after 1 round: pair_outcome=accepted_pair status=running accepted=2 sched=2 dispatch_calls=1
  after 6 rounds: accepted=3 sched=3 status=done attempts=3 dispatch_calls=2
                 ← 真实成交被计回；不忙循环；不超发；最后一组结算后转 done

PROBE 8 — deleted 卡上的"两腿都 rejected"崩溃缝隙
  status=deleted（未被复活） pair_outcome=confirmed_failed dispatch_calls=0（零重发、零新组）
```

作者自带的回归 `test_10a`–`test_10d` 覆盖了 running / paused / stopped / deleted 与 429 免计数分支，
我逐条读过断言，**不是空跑**：`test_10b` 断言第二轮不重复计数，`test_10c` 断言状态不被复活且不开第二组，
`test_10d` 断言限频缝隙走 `settle_attempt_no_counters` 且 `fail_count == 0`。

**一个我特意去证伪但未成立的怀疑**：`NOT EXISTS(非终态腿)` 对"零条腿"的 attempt 也为真，
理论上会让一个"只有 attempt 行、没有腿"的记录被当成缝隙结算。我读了
`store.prepare_attempt`（`store.py:546-638`）——attempt 行与**两条腿在同一个事务内**插入，
所以生产路径不可能出现零腿 attempt。该怀疑不成立，不记 finding。

### 3.4 F6 —— validator 覆盖 ✅（检查正确落地，但方向性有 P2 缺陷）

`scripts/validate-stage.py` 新增 `validate_dispatch_receipt_phase`（限
`_uses_human_operator_protocol` 的 stage）：
(a) 被引用的 dispatch 回执仍为 `pending`、但其声明的 `outputs` 文件已经存在；
(b) 某轮 review 的 dispatch 文件已存在、根 `status` 却仍停在更早阶段。
`scripts/tests/test_validate_stage_dispatch_protocol.py` 从 55 增至 67 个用例，我复跑全绿。

**事实记录核对（派发要求我核对的一项）**：该 validator 首跑检出的两条漂移
（packet 59 与 69 的回执）确实是真实漂移，且 bookkeeper 的封存**没有发明任何时间或 Session ID**——
我逐条回到原始 footer 校对：

| 回执 | 回填值 | 我核对到的来源 |
| --- | --- | --- |
| `59-...dispatch.md` | `completed_at: 2026-07-24T22:02:00+08:00` | `59-review-1-frontend-r2.md:173` 的"本地北京时间: 2026-07-24 22:02 CST" ✅ |
| `59-...dispatch.md` | `session_id: unavailable:<原因>` | 同文件 footer 明确记录 runtime 未暴露 Session ID ✅ |
| `69-...dispatch.md` | `completed_at: 2026-07-26T14:07:11+08:00` | `69-review-2.md:174` 的"本地北京时间: 2026-07-26 14:07:11 CST" ✅ |
| 两处 | `started_at: unavailable:<原因>` | 无来源即标 unavailable + 原因，未编造 ✅ |

**但检查 (b) 的方向性有缺陷（P2-2）**，我实测复现，见 findings。

---

## 4. 范围与越界核对

packet 72 改动的 16 个文件我逐个比对 `28` §4 的允许/禁止清单：

- **允许清单内**：`domain.py`、`service.py`、`store.py`、`live_hedge_executor.py`、
  `scripts/validate-stage.py`（仅 §2.4 两项检查）、`test_hedge_review2_regressions.py`、
  `test_hedge_service.py`、`test_hedge_store.py`、`test_hedge_domain.py`、
  `test_live_hedge_executor.py`、`scripts/tests/test_validate_stage_dispatch_protocol.py`、
  `60-test-output.txt`（仅追加）、`71-fix-review-2-backend-r7.md`（新建）。
- **禁改项全部未被触碰**：`frontend/**`（0 文件）、`docs/**`、PRD、`10-design.md`/`11-adr.md`、
  `hedge_open_live_client.py`（**7 端点 allowlist 逐字未变**，我核对了 `ALLOWLIST` 字典）、
  `hedge_preflight_provider.py`、`scheduler.py`、`server.py`、`reports/api-samples/**`、
  `status.json`、`70-handoff.md`、任何契约文档或评审报告。
- **`_ENTRY_EVENT_KINDS` 未新增 kind**（仍是 5 个：`task_stopped` / `threshold_paused` /
  `task_paused` / `preflight_incomplete` / `rate_limited`）。

### 4.1 关于 `test_hedge_api.py` 的边界裁定（派发要求我独立复核）

**我认同 bookkeeper 的裁定**，理由是它可以被机械证明，而不是善意推定：

1. `28` §4 的允许清单**没有**列 `backend/tests/test_hedge_api.py`；
2. `28` §5 的强制自测命令**列了**它，且 §6 要求它全绿；
3. §2.1 授权的行为变更（single_leg 计入连续失败）**必然**使该文件里那句冻结断言
   `assert doc["consecutive_submission_failures"] == 0` 变假。

三者同时成立时，packet 无解——这是**授权书自身的内在矛盾**，不是实现者越界。
我核对了实际差异：该文件在 packet 72 中**只有 4 行**改动（1 行断言 `0 → 1` + 2 行解释注释 + 1 行上下文），
断言的其余部分（`leg_exposure` 逐字、"advisory 不阻塞调度、仍可继续 fill-once"）**原样保留**，
即这次改动是**把测试对齐到新合同**，不是削弱安全断言。实现者主动在 `71` 中披露而非隐瞒，
是正确行为。裁定成立。

### 4.2 一处我核对后判定为"合规但值得记录"的事实

commit `77c75bd` 同时包含了实现者的代码改动**和** bookkeeper 自己的两处回执封存
（`59` / `69` 的 `.dispatch.md` 头部）。这不违反 `28` §4（该清单约束的是实现者，且被封存的是
dispatch 回执而非 §4 禁止的评审报告 `.md`），提交信息也逐条说明了。我已把这两处封存与原始 footer
逐字对照（§3.4 表格）确认无编造。仅记录：这使得"被审 diff = 实现者产出"这一等式不再严格成立，
未来最好把簿记封存与实现提交分开落两个 commit。

---

## 5. Findings

### P2-1 —— 计划组已用尽的卡在人工 Start 后永久停在"运行中"

- **文件**：`backend/hedge_open_tasks/store.py:781`（转 done 的条件） /
  `backend/hedge_open_tasks/service.py:521-535`（`post_start` 无用尽检查）
- **证据**：新的 done 转换要求"结算那一刻 `status == running`"。若最后一个计划组在
  `paused` 下结算（撞 429 走 `skip_counters` 分支；或刚好被连续失败刹车暂停），任务合法地停在
  `paused`；`post_start` 对 `scheduled_attempt_count >= target_n` **没有任何检查**，直接
  `set_task_status(RUNNING)`，而 `_worker_round:1020` 立刻以 `WORKER_EXIT_TARGET_REACHED` 退出。
  我的实测（PROBE 5，`target_n=1`，最后一组撞 429）：

  ```text
  after 429 last group: status=paused pause_reason=rate_limited sched=1/1
  post_start -> 200 status=running
  after resume rounds: status=running  dispatch_calls=1  attempts=1
  ```

  同样的状态也可由 PROBE 1 的场景到达（`target_n=3` + 阈值 3，第三组单腿刹车暂停后恢复）。
  由于 `_entry_next_action`（`service.py:329-339`）在 `running` 且无 querying 组时返回
  `continue_next_attempt`，开单日志会显示一个永远不会发生的"继续下一组"。
- **影响**：**纯展示 / 状态一致性问题，零下单风险**——`target_n` 原子硬上限仍然生效
  （实测 `dispatch_calls` 不增、`attempts` 不增）。但操作者会看到一张"运行中"却永不动作的卡，
  与 Review-2 F1 后半段描述的症状相同（只是入口从"结算"变成了"人工恢复"）。
  我把它定为 **P2 而非 P1**：F1 的安全半边（刹车）已修复且实测生效，剩下的这半边不会产生任何订单。
- **建议（follow-up，需新的用户授权）**：在 `post_start` 里对
  `scheduled_attempt_count >= target_n` 的任务直接返回 `done`（与 `status == done` 时的幂等分支
  同构），或在 worker 以 `target_reached` 退出时把 `running` 收敛为 `done`。二选一即可，
  不涉及任何下单路径。

### P2-2 —— 新 validator 的根状态检查是单向的，且会在"Review-2 REWORK → fixing"的正常返工环上误报

- **文件**：`scripts/validate-stage.py`（`_STATUS_PHASE` / `_root_status_behind_review`）
- **证据**：我直接加载该模块并调用纯函数实测：

  ```text
  _STATUS_PHASE = {'planned':0,'designing':0,'implementing':0,'testing':0,
                   'review_1':1,'fixing':2,'review_2':3,'accepted':4,
                   'stage_accepted_waiting_user':4}
  root=fixing        vs review_2 -> "root status 'fixing' is behind the review_2 phase: ..."   ← 误报
  root=implementing  vs review_2 -> 同上误报
  root=review_2      vs review_1 -> None                                                       ← 反向盲区
  ```

  检查 (b) 把"某轮 review 的 dispatch 文件存在"等同于"stage 当前处于 ≥ 该阶段"。但本 Harness
  明确支持返工环（`max_rework` 已放到 7）：**Review-2 返回 REWORK 后根状态合法地回到 `fixing`，
  而 `review_2.dispatch_path` 仍然指向真实发生过的那次派发**——此时任何
  `--phase pre-review` / `--phase review-2` 都会被这条检查判失败。
  这不是假设：本轮 packet 73 派发时，bookkeeper 正是因为这条检查（root 回到 `review_1`
  而 `review_2.dispatch_path` 仍在）才不得不把已完成的那轮 review_2 整体降格为
  `previous_review_2_r1`、并新建一个 `dispatch_path: null` 的 review_2（commit `d5eb40a`）。
  该处置本身诚实且保全了证据（旧轮逐字保留），bookkeeper 也把该缺口写进 `blockers` 交我判断——
  但检查本身在把记账者**朝"挪走当前轮指针才能过闸"的方向推**，与"证据保全"的目标相反。
  另外它对反向漂移（根状态**超前**于正在派发的 review）完全无感，正是 bookkeeper 自陈的那个盲区。
- **影响**：Harness 门禁问题，非业务安全问题，且是 **fail-closed（吵闹而非静默）** 的方向。
  但它会在下一次 Review-2 返工时立刻发作，并持续制造"改 `status.json` 结构以过闸"的压力。
- **建议（follow-up，需新的用户授权，因 rework 已 7/7）**：把 (b) 的判据从"dispatch 文件是否存在"
  改成"该轮是否是**当前进行中**的一轮"（例如仅当 `review_k.verdict is null` 且
  `review_k.dispatch_path` 非空时才要求根状态 ≥ k），并补一条反向检查（根状态超前于当前派发的
  review 阶段同样报错）。同时为返工环补一个明确的合法状态集。

### P3-1 —— `consecutive_submission_failures` 的展示文案在新语义下会误导

- **文件**：`frontend/index.html:3691`、`backend/hedge_open_tasks/domain.py:1154`
- **证据**：文案为"连续提交失败 N / 暂停阈值 M"与"连续提交失败达到阈值…"，但该计数现在也包含
  "一条腿已被交易所受理"的组。字段集与前端代码本轮**无需改动**（`frontend/**` 零改动的前提成立）。
- **影响**：操作者可能把"连续提交失败 2"误读为"两组都没发出订单"，而事实上可能已有 2 张真实裸腿。
- **建议**：记为前端展示 follow-up（纯文案，如"连续未成对 N 组"），下一个前端 stage 处理。

### P3-2 —— 查询阶段 429 的退出路径没有写 `worker_exit_reason`

- **文件**：`backend/hedge_open_tasks/service.py:1006`
- **证据**：`_worker_round` 里所有其它退出都走 `_worker_exit(...)`（会落 `worker_exit_reason`），
  只有这条新增的 `return True` 直接返回。PROBE 6 实测退出后 `worker_exit_reason=None`，
  而 `pause_reason=rate_limited`。
- **影响**：纯可观测性。限频事实由 `pause_reason` 承载，不丢失；但该卡的 worker 退出原因缺失，
  与其它 7 种退出不一致，排障时少一条线索。
- **建议**：follow-up 时新增一个 `WORKER_EXIT_RATE_LIMITED` 常量并改走 `_worker_exit`
  （`ALL_WORKER_EXIT_REASONS` 需同步）。

### P3-3 —— 一条腿已确认限频后，同组另一条腿仍会被再查一次

- **文件**：`backend/hedge_open_tasks/service.py:1058-1064`
- **证据**：`_reconcile_own_legs` 在识别到 `rate_limited` 后只 `continue`，循环继续查询同组剩余的腿。
  PROBE 6 实测 `query_calls=2`。另外循环后段的
  `if error_category == "insufficient_funds": drain_signal = SIGNAL_INSUFFICIENT_BALANCE`
  是**无条件赋值**，会覆盖先前置上的 `SIGNAL_RATE_LIMITED`（两者都导致本卡暂停，只影响 pause_reason 标签）。
- **影响**：每次限频最多多打一个 GET（每组最多 2 条腿），不会重发 POST，不会继续开组。
  在"已被限频"的时刻多一次请求，理论上略微推高触 418 的概率，但量级极小。
- **建议**：follow-up 时在识别到限频后直接 `break`，并把限频信号设为最高优先级。

### P3-4 —— `_apply_task_counters` 的 docstring 仍写着 single_leg "counts unchanged"

- **文件**：`backend/hedge_open_tasks/store.py:697-698`
- **证据**：函数头 docstring 第 4 条仍是 "single-leg (one orderId) -> ADVISORY: counts unchanged"，
  与其下方 `758-776` 的新实现直接矛盾。（这正是 Review-2 F1 当初引用的那两行。）
- **影响**：文档漂移，会误导下一个读这段代码的实现者或评审者。零运行时影响。
- **建议**：follow-up 时同步该 docstring。

---

## 6. 用户排除项的处置（不作为 P0/P1，不据此 REWORK）

按 `28-user-authorized-r7-repair.md` §3 与派发的裁定，以下各项**未修**是用户的明确决定，
我不据此给出任何阻断性 finding，只按要求登记为 residual risk：

- **Review-2 F3**（人工 delete/pause 被迟到 worker 结果覆盖）：仍然成立。我确认
  `store.pause_task` 与 `_apply_task_counters` 的 fatal 分支（`store.py:731-738`，
  无条件置 `stopped`）依旧没有状态守卫；本轮 F4 让 `_recover_workers` 也会为
  **deleted/done/stopped** 卡上的崩溃缝隙拉起 drain worker，这条既有路径的**可达面被略微扩大**
  （原本只有"存在非终态腿"才拉起）。风险性质不变、不产生新订单（PROBE 8 实测 deleted 卡
  `dispatch_calls=0`、状态未被复活），但一旦 F3 将来要修，需要连同崩溃缝隙恢复路径一起加守卫。
- **Review-2 F5**（`accountStatus` / `uniMMR` 账户健康 + 现货 `MIN_NOTIONAL`）：未做，
  7 端点 allowlist 冻结不变。用户以"输入端自行保证数量足够"为操作约定。
  提醒仍然有效：交易所卡的是**名义金额（数量 × 价格）**，输入的是数量，需留价格波动余量。
- 排队期间取消删除、`aggregate_positions` 过滤 `deleted`、r4/r5 既有 P3、跨进程预留守卫、
  `X-MBX-ORDER-COUNT-*` 节流、前端展示 `worker_active`：全部后置 follow-up，本轮未回归。

---

## 7. 给 bookkeeper 的两条操作提示

1. **本报告落盘后，`--phase pre-review` 会立刻被新 validator 的检查 (a) 判失败**：
   `review_1.dispatch_path = 73-review-1-backend-r6.dispatch.md` 的回执仍是 `status: pending`，
   而它声明的 `outputs`（本文件）现在已经存在。我落盘后实测确认（原始输出）：

   ```text
   STAGE VALIDATION FAILED
   - review/acceptance gates require a clean committed worktree; commit or revert these changes first:
     ?? reports/agent-runs/2026-07-hedge-open-real-api-v1/73-review-1-backend-r6.md
   - tasks[backend].review_1: dispatch receipt is status=pending but its declared outputs file
     already exists: reports/agent-runs/2026-07-hedge-open-real-api-v1/73-review-1-backend-r6.md
   exit=1
   ```

   （前一条是本报告尚未提交的正常结果。）这是该检查**按设计生效**，不是缺陷——
   请依据人类操作员的真实记录封存 73 的回执（无来源的字段照旧标 `unavailable:<原因>`，
   不要编造时间或 Session ID），再跑门禁。
2. **本 ACCEPT 不改变 `rework_count = 7/7`**。上面两条 P2 与四条 P3 **全部是 follow-up**，
   任何进一步的代码变更（包括 P2-1 的 `post_start` 收敛与 P2-2 的 validator 修正）都需要
   **用户新的书面授权**，bookkeeper 不能自行派发。

## 8. 是否可以进入新一轮 Review-2

**可以。** 后端 Review-1 在固定范围 `28c550d..77c75bd` 上 ACCEPT，前端 Review-1 的既有 ACCEPT
因 `frontend/**` 零改动而继续有效（`45-review-1-frontend-rfix.md` / `59-review-1-frontend-r2.md`）。
进入 Review-2 前请先完成 §7.1 的回执封存并把根状态按工作流推进，同时把本报告的两条 P2、四条 P3
与 §6 的 residual risk 原文（而非摘要）交给终审者。终审者需与 `zhipu_glm`（后端实现）及
`anthropic`（前端返工 + 本轮 Review-1）双重隔离——按 `46-review-2-routing-disclosure.md`，
Codex 仍是唯一合格路由，须沿用已披露的 design-conflict override。

---

当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/73-review-1-backend-r6.md
本地北京时间: 2026-07-26 23:31 CST
审查者模型: claude / Claude Opus 5
审查角色: first_reviewer（后端 · r6）
下一步模型: bookkeeper
下一步任务: seal the packet-73 receipt, record this ACCEPT, and route the stage toward a new Review-2 with the preserved frontend ACCEPT

{
  "schema_version": 1,
  "stage_id": "2026-07-hedge-open-real-api-v1",
  "role": "first_reviewer",
  "model": "Claude Opus 5",
  "verdict": "ACCEPT",
  "diff_fingerprint": "77c75bd855c3d1a7a4c91700f9db953919df087f:aa0406dae9cb90004d5dd15c2a936ad9a021a0c01a50f985d4efab5900e652dd",
  "reviewer_prior_involvement": "none",
  "reviewer_prior_involvement_notes": "Claude Opus 5 (anthropic) wrote no delivery or fix code for this stage; the reviewed backend was implemented and reworked by Claude-GLM (zhipu_glm), so provider isolation holds. Disclosure: the same model authored the read-only backend Review-1 rounds r2-r5 (58/64/66/68) and has held the bookkeeper role since 2026-07-25 after Codex quota exhaustion (status.json.bookkeeper.dual_hat_disclosure, 27-user-authorized-r4-repair.md section 6). Neither role is code or fix authorship. This review ran in a fresh read-only session, re-read the sources, recomputed the fingerprint, re-ran every self-test locally, and re-derived each conclusion from new offline probes rather than accepting the implementation report, the r5 verdict or the bookkeeper reconciliation as fact.",
  "reviewed_artifacts": [
    "AGENTS.md",
    "workflows/templates/stage-delivery.yaml#review-1",
    "schemas/review-verdict.schema.json",
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
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/28-user-authorized-r7-repair.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/69-review-2.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/68-review-1-backend-r5.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/66-review-1-backend-r4.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/46-fix-review-1-backend-r4.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/71-fix-review-2-backend-r7.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/72-fix-review-2-backend-r7.dispatch.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/60-test-output.txt",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/59-review-1-frontend-r2.md and .dispatch.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/69-review-2.dispatch.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/status.json",
    "git diff --binary 28c550d87c1ca90983d5bde9c7102d42cffecd4e..77c75bd855c3d1a7a4c91700f9db953919df087f",
    "git show 77c75bd (packet 72 delta, all 16 files)",
    "backend/hedge_open_tasks/{domain.py,service.py,store.py,executor.py}",
    "backend/services/{live_hedge_executor.py,hedge_open_live_client.py,hedge_preflight_provider.py}",
    "backend/tests/test_hedge_*.py and backend/tests/test_live_hedge_executor.py",
    "frontend/index.html (read-only, zero change verification)",
    "scripts/validate-stage.py and scripts/tests/test_validate_stage_dispatch_protocol.py"
  ],
  "findings": [
    {
      "severity": "P2",
      "title": "A task whose planned attempts are exhausted stays permanently in running after a manual Start",
      "file": "backend/hedge_open_tasks/store.py",
      "line": 781,
      "evidence": "The new done transition requires status == running at settlement time. When the last planned pair settles while paused (a 429 pair settled through skip_counters, or the consecutive-failure brake firing on the last group), the task legitimately stays paused. post_start (service.py:521-535) has no scheduled_attempt_count >= target_n check and sets RUNNING unconditionally; _worker_round:1020 then exits with target_reached. Offline probe with target_n=1 and a 429 last group: paused sched=1/1 -> post_start 200 -> status=running, and after four further worker rounds status is still running with dispatch_calls=1 and attempts=1. _entry_next_action returns continue_next_attempt in that state.",
      "impact": "Display and state-consistency only, with zero order risk: the atomic target_n cap still holds and no further pair is ever dispatched. The operator sees a card reading running that will never act again, and an opening log promising a next group that cannot happen. This is the same symptom Review-2 F1 described, reached through manual resume instead of settlement.",
      "recommendation": "Follow-up under a new user authorization: either return the existing done idempotent branch from post_start when scheduled_attempt_count >= target_n, or collapse running to done when the worker exits with target_reached. No dispatch path is involved."
    },
    {
      "severity": "P2",
      "title": "The new root-status validator check is one-directional and false-positives on the normal review-2 REWORK to fixing loop",
      "file": "scripts/validate-stage.py",
      "line": 990,
      "evidence": "Loading the module and calling the pure function directly: _root_status_behind_review('fixing', 'review_2') returns an error, as does 'implementing'; _root_status_behind_review('review_2', 'review_1') returns None. Check (b) equates the mere existence of a review_k dispatch file with the stage currently being at phase >= k, but this Harness explicitly supports a rework loop (max_rework raised to 7) in which a review-2 REWORK legitimately returns the root status to fixing while review_2.dispatch_path still points at the dispatch that really happened. This already forced a status.json restructure in this very stage: dispatching packet 73 required demoting the completed round to previous_review_2_r1 and creating a review_2 with dispatch_path null (commit d5eb40a). That handling was honest and preserved the prior round verbatim, and the bookkeeper self-reported the gap in status.json.blockers for this review to judge.",
      "impact": "A Harness gate defect, not a business-safety defect, and it fails closed (noisy, not silent). It will fire on the next review-2 rework cycle and it pressures bookkeepers toward moving or nulling current-round evidence pointers to keep the gate green, which is the opposite of the evidence-preservation goal. The reverse drift (a root status parked ahead of the review being dispatched) remains undetected.",
      "recommendation": "Follow-up under a new user authorization: key check (b) on the round being in progress (for example require the root status to be >= k only while review_k.verdict is null and review_k.dispatch_path is set), add the symmetric check for a root status ahead of the review being dispatched, and enumerate the legal statuses of the rework loop."
    },
    {
      "severity": "P3",
      "title": "The consecutive_submission_failures label now misleads under the approved new semantics",
      "file": "frontend/index.html",
      "line": 3691,
      "evidence": "The card renders 连续提交失败 N / 暂停阈值 M and domain.py:1154 renders 连续提交失败达到阈值. Under R2-F1 the counter now also advances for a group in which one leg WAS accepted by the exchange. The frozen field set is unchanged and frontend/** has zero changes this round, so no frontend code change is required or was made.",
      "impact": "An operator may read 连续提交失败 2 as two groups where nothing was submitted, while two real naked legs may exist. Wording only.",
      "recommendation": "Record a frontend display follow-up (copy only, for example 连续未成对 N 组) for the next frontend stage; do not reopen this backend stage for it."
    },
    {
      "severity": "P3",
      "title": "The query-phase 429 exit path records no worker_exit_reason",
      "file": "backend/hedge_open_tasks/service.py",
      "line": 1006,
      "evidence": "Every other exit in _worker_round goes through _worker_exit, which persists one of the eight ALL_WORKER_EXIT_REASONS. The new query-429 branch returns True directly. Offline probe: after the query-phase 429 the task is paused with pause_reason=rate_limited while worker_exit_reason is None.",
      "impact": "Observability only. The throttle fact is carried by pause_reason and is not lost, but this card's worker exit is the one exit without a recorded reason.",
      "recommendation": "Follow-up: add a WORKER_EXIT_RATE_LIMITED constant to ALL_WORKER_EXIT_REASONS and route this branch through _worker_exit."
    },
    {
      "severity": "P3",
      "title": "After one leg confirms a query-phase throttle the sibling leg is still queried once more",
      "file": "backend/hedge_open_tasks/service.py",
      "line": 1058,
      "evidence": "_reconcile_own_legs only continues after recognising rate_limited, so the loop still queries the remaining leg of the same pair; the probe recorded query_calls=2. The later insufficient_funds assignment in the same loop is unconditional and can overwrite an already-set SIGNAL_RATE_LIMITED (both pause this task; only the pause_reason label differs).",
      "impact": "At most one extra GET per pair while already throttled, marginally raising the chance of escalating to 418. No POST is resent and no new group is opened.",
      "recommendation": "Follow-up: break out of the loop on the first typed rate-limit signal and treat it as the highest-priority drain signal."
    },
    {
      "severity": "P3",
      "title": "_apply_task_counters docstring still documents the removed advisory single-leg behaviour",
      "file": "backend/hedge_open_tasks/store.py",
      "line": 697,
      "evidence": "The function docstring still reads 'single-leg (one orderId) -> ADVISORY: counts unchanged, leg_exposure recorded, scheduling never blocked', directly contradicting the new implementation at lines 758-776. These are the exact two lines Review-2 F1 cited as evidence of the old defect.",
      "impact": "Documentation drift with zero runtime effect; it will mislead the next implementer or reviewer reading this function.",
      "recommendation": "Follow-up: update the docstring together with any of the other follow-ups touching this file."
    }
  ],
  "required_fixes": [],
  "residual_risks": [
    "User-excluded Review-2 F3 (no atomic state guard on worker-driven pause/fatal-stop) still holds: a late worker result can overwrite a manual delete and the card can resurface as paused. store.pause_task and the fatal branch of _apply_task_counters (store.py:731-738) remain unconditional. The F4 fix slightly widens the reachable surface because _recover_workers now also relaunches a drain worker for deleted/done/stopped cards holding a crash-gap attempt; the probe confirmed a deleted card is not revived and dispatches nothing, but any future F3 guard must cover the crash-gap recovery path too.",
    "User-excluded Review-2 F5 still holds: no GET /papi/v1/account, no accountStatus/uniMMR health input, and Spot MIN_NOTIONAL is still unparsed with no fail-closed behaviour. The seven-endpoint allowlist stays frozen and the user accepted an operating convention of guaranteeing sufficient size at input time. Reminder that remains valid: the exchange enforces notional (quantity times price) while the operator inputs quantity, so a price-move margin is needed.",
    "Deferred follow-ups unchanged this round: cancelling a delete while queued, aggregate_positions filtering deleted, the r4/r5 P3 set (settle error column, Start race, post_start ordering), cross-process reservation guards, X-MBX-ORDER-COUNT-* throttling, and surfacing worker_active in the UI.",
    "recvWindow is still 60000 ms and there is still no automatic leg repair, cancel, close, borrow/repay, transfer or full accounting in this stage.",
    "This ACCEPT covers the fixed range 28c550d..77c75bd only. It releases NO live gate: enabling live execution, turning on the Start gate and placing the first real order each require separate written human authorization, and merging the stage branch to main requires explicit user acceptance after Review-2.",
    "Commit 77c75bd mixes the implementer's code with two bookkeeper receipt seals (59 and 69 dispatch headers). Both seals were verified verbatim against the reports' own footers and invented nothing, and neither file is on the section 4 prohibited list, but future rounds should land bookkeeping seals in a separate commit so the reviewed diff equals the implementer's output."
  ],
  "next_action": "continue"
}

# Task Handoff: smooth-open-v1-final-review-2-opus5

## Source Report (author-only; immutable after task end)

- task_id: `smooth-open-v1-final-review-2-opus5`
- role: `Reviewer`（最终累计 Review-2）
- target model: `claude-opus-5` / provider `anthropic`
- stage_id: `2026-08-12-smooth-open-orders-v1`
- created_at: `2026-08-13 20:54:17 CST`
- base_sha: `e955bdd300d214c5c3ad5c1acd629c0d21080165`
- delivery_sha: `ad8c6317369e8a643f225cc37f22ad0eb949395b`
- status_revision: `53`（`ledger_sha` `f305c8a0baf0aa1579fb7464d3bea697403db747`）
- required_skill: `agents/skills/reality-checker.md`

### 身份、隔离与设计参与披露

本 Reviewer provider 为 `anthropic`。累计区间内的实现/修复作者 provider 为 `openai`
（`24074b1` / `dfd38a6` / `5d65a96`）、`xai`（`bba31ea`）、`moonshot`（`ad8c631`），与本
Reviewer 全部隔离，无自审。

按 `agents/roles.md` Reviewer/Isolation 披露：Opus 5（provider `anthropic`）曾撰写本阶段
的返修计划增量（`docs/planning/smooth-open-orders-v1-development-checklist.md` §12/§15 与设计
D15–D19 的计划文本）。Human 已明确指定 Opus 5 执行最终 Review-2。本裁定不把自己参与过的
计划文本当作实现证据：全部结论只来自固定区间源码、本会话可执行证据、已记录的 Human 决策与
实盘观察。设计参与不覆盖“不得评审同 provider 实现”的禁令——本阶段无 `anthropic` 实现作者，
该禁令未被触及。

fresh 只读会话。除创建本 handoff 外未写入任何文件：未改源码、测试、计划、契约、既有
evidence/dispatch、`status.json`、`ACTIVE.json`、`PROJECT_STATE.md`、`.venv/` 或运行时数据；
未 commit/push/merge/部署；未联网取证；未读取凭证；未访问或控制 `127.0.0.1:8787`；未改 Start
gate；未创建或操作任务；未下单；未安装或卸载依赖。

### 审查方法

- 固定区间核对：`git merge-base --is-ancestor e955bdd ad8c631` 退出 0；
  `git rev-list --count` = 42 提交（含本阶段自身的 dispatch/status/报告控制提交，按
  `AGENTS.md` §8「评审范围口径」仅作上下文）。
- `git diff --name-only ad8c631 -- backend frontend requirements.txt docs` 为空，
  `git status --porcelain` 为空：本会话所读与所跑的工作树与固定 delivery tree 逐字一致，
  未使用移动 HEAD。
- 逐文件读固定区间产品 diff：`backend/services/best_bid_ask_provider.py`、
  `backend/hedge_open_tasks/{domain,store,service,executor}.py`、
  `backend/services/live_hedge_executor.py`、`backend/app/server.py`、
  `frontend/index.html`、`frontend/self-check.js`、`requirements.txt`、
  `docs/api/public-market-contract.md`，并按真实调用链追到组合根、provider、store、service、
  executor、server 与任务卡渲染。
- 独立复跑既有回归（见「独立复跑」）。
- 用「在临时目录的树副本上做定向变异、看测试是否变红」的方式抽查关键用例强度（副本位于会话
  scratchpad，仓库零改动）。

## 一、结论

**verdict: REWORK（返工）**

范围内存在一条可执行复现的资金/订单缺口（F-A）：**live 平滑任务可以在“建卡时的首次完整
preflight 从未成功”的状态下被创建，随后由 5 分钟 timeout 或人工放行发出真实两腿订单，且发送数量
不是任何经过校验的 `q_common`，路由与 position 模式也退回默认值。** 该缺口由本区间的 D15 改动
（`dfd38a6`）使其对实盘可达，不属于 Human 已具名接受的 L1/L2/L3，也不属于 D15 已接受的
“等待期间事实发生变化”这一类代价。

除 F-A 外，本次交付的其余部分（provider 生命周期与 F1 死锁修复、gate 数学与次数硬门、D15/D16
顺序、D17 人工启动、D18/统一刷新、D19 同次快照与延迟审计、offline/缺 ccxt 边界、契约 additive）
经独立检查均成立。

## 二、范围内阻塞发现

### F-A — `in-range` — 建卡 preflight 从未成功的 live 平滑任务，仍会用未经校验的数量发出真实订单

**范围三分类**：`in-range`。使这条路径对实盘可达的那一行由 `dfd38a6`（本区间内，D15 返修）
引入：`git log -S 'if live and task.get("mode") != D.MODE_SMOOTH:' -- backend/hedge_open_tasks/service.py`
→ `dfd38a6`。`live_hedge_executor.py` 里 `send_qty` 的 `single_amount` 回退本身早于 base
（`d90f2f1`，`git merge-base --is-ancestor d90f2f1 e955bdd` 退出 0），但在 D15 之前，live 开单
每轮都有 fresh preflight 兜底，该回退在实盘写路径上不可达；本区间把它变成可达。

**证据锚点（固定 tree）**

1. `backend/hedge_open_tasks/service.py:944-947`：`create_task` 调
   `self._preflight.get_snapshot(...)`；`backend/services/hedge_preflight_provider.py:815-880`
   明确「任一必需读失败 → 返回 `None`」（含 forward 开仓的 `collateral_cap` 读，即
   `PROJECT_STATE.md` 已记录会真实出现的「抵押额度未知」态）。
2. `backend/hedge_open_tasks/domain.py:1176-1189`：`compute_preflight(snapshot=None)` 返回
   `q_common=None`、`position_side_mode=None`、`rejection=None`、
   `snapshot_record={"available": False, "reason": "no_preflight_snapshot"}`。
3. `backend/hedge_open_tasks/service.py:959-963`：`create_task` 只在 `rejection is not None`
   时拒绝。`rejection is None` → 平滑任务以 `201` 建卡（D17 后为 `paused`），
   `q_common=NULL`、`position_side_mode=NULL`、`preflight_snapshot.available=false`；
   同时 `service.py:969-974` 的 regular-spot 预划转因 `snapshot is not None` 守卫被跳过。
4. `backend/hedge_open_tasks/service.py:3239` / `3297-3300`：D15 之后
   `if live and task.get("mode") != D.MODE_SMOOTH:` 才做 fresh preflight；live smooth 落入
   `else` 分支，直接采信固化值——`q_common = Decimal(task["q_common"]) if task["q_common"] else None`。
5. 同族三个消费点（同一根因）：
   - `service.py:3349` `send_qty = q_common if q_common is not None else D.Decimal(task["single_amount"])`
     与 `backend/services/live_hedge_executor.py:828` 同形回退 → 实际下单量变成**未经网格取整、
     未经 LOT_SIZE / minNotional 校验的原始 `single_amount`**；
   - `service.py:3346` `position_side_mode or D.POS_MODE_BOTH` → 在从未读到过 position mode 的
     情况下默认按单向模式发单；
   - `service.py:3350-3352` `spot_route = (snapshot_record or {}).get("spot_route", D.SPOT_ROUTE_PAPI_MARGIN)`
     → 现货腿固定发到 PAPI 全仓杠杆，与该币实际应走的 `regular_spot` 无关，且此时并未预划转。
6. `service.py:3308-3323` 的 frozen/fresh route 一致性门对 smooth 恒等（两侧同源），无法拦截。
7. gate 侧确实识别出了这个状态：`domain.py::evaluate_smooth_gate` 在 `q_common <= 0` 时返回
   `wait_reason="计划下单数量无效"`、`market_pass=False`；但 `service.py:1868-1880` 的
   `manual` / `timeout` 两个放行原因不看这个结论，5 分钟后照常放行。

**可执行复现（本会话实测，仓库零改动、零网络、零凭证、临时 SQLite + 假执行器）**

```bash
cd "/Users/ark/Desktop/ai code/funding_hedging-smooth-v1" && .venv/bin/python - <<'PY'
import tempfile, time
from backend.hedge_open_tasks import domain as D
from backend.hedge_open_tasks.service import HedgeOpenTaskService
from backend.tests.test_smooth_gate_worker import _Clock, _Market, _OrderedLiveExecutor, SPOT, SWAP

class NullPreflight:                      # live provider 的读缺口 -> get_snapshot 返回 None
    def get_snapshot(self, *a, **k): return None

clock, market, events = _Clock(), _Market(), []
executor = _OrderedLiveExecutor(events)
svc = HedgeOpenTaskService(tempfile.mkdtemp() + "/p.sqlite3", executor=executor,
    preflight_provider=NullPreflight(), mode="live", credentials_present=True,
    mono_us=clock.mono_us, wall_us=clock.wall_us, market_provider=market)
code, task = svc.create_task({"coin": "BTCUSDT", "direction": D.DIR_FORWARD,
    "mode": D.MODE_SMOOTH, "single_amount": "1.23456789", "target_n": 1,
    "slippage_threshold_pct": "0.05"})
print("create:", code, task["status"], "| frozen q_common =", svc.store.get_task(task["id"])["q_common"])
svc.set_start_gate(True); svc.post_start(task["id"])
for _ in range(500):
    row = svc.store.get_task(task["id"])
    if row["smooth_gate_seq"] is not None: break
    time.sleep(0.01)
clock.t += D.SMOOTH_GATE_WINDOW_US + 1
market.publish(SPOT, bid="99.99", ask="100"); market.publish(SWAP, bid="100", ask="100.01")
for _ in range(500):
    if executor.dispatch_calls: break
    time.sleep(0.01)
att = svc.store.list_attempts_for_task(task["id"])
print("live dispatch calls:", executor.dispatch_calls,
      "| attempt q_common =", att[0]["q_common"] if att else None,
      "| pass_reason =", att[0]["smooth_pass_reason"] if att else None)
svc.close()
PY
```

实测输出：

```text
create: 201 paused | frozen q_common = None
live dispatch calls: 1 | attempt q_common = 1.23456789 | pass_reason = timeout
```

另用一个记录 `AttemptContext` 的假执行器复跑同一场景，得到进入执行器的上下文为：
`{'q_common': None, 'single_amount': Decimal('1.23456789'), 'position_side_mode': None,
'preflight_snapshot': {'available': False, 'reason': 'no_preflight_snapshot'}}`，
`wait_reason` 在放行前为「计划下单数量无效」，任务最终 `done`。

**实际影响**

- 一笔真实开单的数量、现货路由与 position 模式全部来自“从未成功读取过的预检”，其中数量退化为
  未取整的 `single_amount`，且完全没有余额/保证金/最小名义额/限频校验。
- 最可能的两种结果：两腿都被交易所按过滤器拒绝（噪声但无敞口）；或**合约腿被接受、现货腿因路由
  与备款不匹配被拒 → 裸空**。后者正是本项目已多次修复的事故形状
  （`PROJECT_STATE.md` 的 51169 / regular-spot 备款条目）。
- 触发前提是普通的瞬时读失败（429/-1003、`collateral_cap` 读不到即「抵押额度未知」），不是极端
  假设；`PROJECT_STATE.md` 已把这类失败记为真实发生过的运行事实。
- 现有可见性只有任务卡「公共网格量 —」与运行卡等待原因「计划下单数量无效」，两者都不阻止
  5 分钟后的放行；`成交1次` 同样可以直接放行。
- immediate 不受影响：live immediate 每轮 fresh preflight，读缺口会走
  `SIGNAL_PREFLIGHT_INCOMPLETE` 暂停，永不落到该回退。

**为何必须本轮修（`AGENTS.md` §8 新假设场景证据门）**

本条不是新假想场景：它有固定树上的完整静态调用链 + 本会话可执行复现 + 已记录的运行事实前提，
并直接触及 §3 保护的资金/订单类别，也直接对应本任务 Acceptance Check 5「create 首次 preflight、
固化身份/route/数量……仍成立」。Human 冻结接受的是 L1/L2/L3 与「等值展示」四项，以及 D15 的
「等待期间事实**变化**不再被每轮预检拦截」；本条是「固化事实从未存在」，不在任何一项接受范围内。

**最小修复要求（根因一次扫完，不得只补单点）**

根因命名：**live smooth 直接消费建卡固化的预检结果，却从不校验这份固化结果是否曾被完整取得；
`q_common` / `position_side_mode` / `spot_route` 三个消费点各自带默认回退，把“没读到”悄悄变成
“按默认值发单”。**

1. 在 live smooth 的发单路径上加**一处** fail-closed 前置判定（`_dispatch_one_for_task` 取用固化值
   之后、`prepare_attempt` 之前）：当 `task["q_common"]` 为空，或
   `(task["preflight_snapshot"] or {}).get("available")` 不为真时，复用既有
   `_record_preflight_incomplete` / `D.SIGNAL_PREFLIGHT_INCOMPLETE` 暂停链（既有中文原因、既有
   `_pause_preflight_incomplete` 收口），**不创建 attempt、不发单**。不得新增状态列、暂停原因枚举、
   锁、重试器或第二套预检。
2. 建议同时在 `create_task` 的 smooth 分支上把「首次完整 preflight 未取得」直接拒为 `400`
   （复用既有 `HedgeError` 形状），使这种半成品卡片根本不存在——这与 D15/D17「建卡时完成唯一一次
   完整 preflight 并固化」的设计前提一致。若只做第 1 项，必须说明为何允许半成品卡片继续存在。
   两项都做时，第 1 项仍必须保留，作为历史行的兜底。
3. 三个消费点（`service.py:3346` / `3349-3352` 与 `live_hedge_executor.py:828` 的回退语义）在
   本次修复中一并复核并在 handoff 中逐条说明：哪一个由新判定覆盖、哪一个保留原状及理由。
   `live_hedge_executor.py` 的回退若不改，须说明它在 smooth 路径上已不可达。
4. 必须新增能在当前实现下**变红**的确定性回归（放在
   `backend/tests/test_smooth_gate_worker.py`）：live smooth + `get_snapshot` 返回 `None` 的
   preflight → 建卡后 Start → `timeout` 与 `manual` 两条放行原因各一条，断言
   `executor.dispatch_calls == 0`、无 attempt、任务按既有 `preflight_incomplete` 暂停；
   并保留一条“固化预检完整时 smooth 仍按既有顺序正常放行”的对照断言。
5. 不得借本轮修改 L1/L2/L3、不得恢复 smooth 的每轮 fresh preflight、不得改动两腿并发/查单/结算/
   单腿链、`prepare_attempt` 原子复核、immediate 与 close 的任何语义。

## 三、范围外发现

- `pre-existing-independent`：`backend/tests/test_private_client.py::test_urlopen_only_in_designated_http_clients`
  失败，触发文件 `backend/services/public_ip_service.py`。本会话核验：
  `git diff --stat e955bdd..ad8c631 -- backend/services/public_ip_service.py backend/tests/test_private_client.py`
  为空（零 diff）；引入提交 `73f525d4c3033cd4e8d7c7afb09a975816742913`（`2026-08-12`）经
  `git merge-base --is-ancestor 73f525d4 e955bdd` 证明早于 base。失败对象与数量与前几轮记录完全
  一致（唯一一条、同一测试、同一触发文件），沿用既有裁定，不阻塞。
- `pre-existing-release-critical`：本次未发现新项。`PROJECT_STATE.md` 中的 reverse 自动平仓单腿
  风险、1000x 腿量换算、划转端点默认可动钱等既存条目与本交付无因果关系，不计入本交付 in-range。

## 四、非阻塞观察（带重开条件，不进入 Human 摘要的阻塞项）

1. `backend/tests/test_smooth_gate_worker.py::test_smooth_audit_uses_same_gate_snapshot_and_no_second_latest`
   在 dispatch **之后**才抓取 `latest_calls` 基线，因此它能测红“放行后再读盘口”，但测不红“放行判定
   与构造审计之间再读一次同一时刻的盘口”。当前代码是正确的（审计用产生结论的同一对快照对象），
   属测试锐度而非缺陷。重开条件：将来有人改动 `_wait_for_smooth_gate` 的审计构造位置。
2. `backend/tests/test_frontend_field_binding.py` 的统一刷新静态断言只覆盖「不得按 mode/task_type
   过滤」「存在去重并集」，把 running 重新耦合到「日志已展开」时它仍全绿；真正测红这条的是
   `frontend/self-check.js`（本会话变异实测：self-check `[FAIL] 统一刷新资格请求集合错误`，
   而 `test_frontend_field_binding.py` 14 passed）。重开条件：self-check 该断言被删改。
3. `validate_slippage_threshold_pct` 拒绝显式正号（`"+0.05"` → 400）。前端不会发送该形式，设计
   D5 也未要求支持，仅作记录。重开条件：Human 要求页面允许输入带正号的阈值。
4. 活文档：`docs/product/PRD.md:99`「No smooth execution in the immediate-open stage.」与
   `docs/product/PRD.md:317`「smooth-open is visibly unavailable」相对最终交付已陈旧，且方向是
   「低估系统能力」——读者会以为平滑不能执行，而它现在可以发真实订单。按本任务 Acceptance Check 8，
   纯收尾文档缺失不替代代码 verdict；此项在阶段收尾时由 Bookkeeper 按 `AGENTS.md` §7 同步。
   `docs/api/public-market-contract.md` 的 smooth 段与最终代码行为一致，无需修改。

## 五、其余验收检查（独立核对结论）

1. **Human 需求 → 实际效果（Acceptance 1）**：成立。`server.py::_build_hedge_service` 在非 offline
   且 ccxt 可用时注入唯一 `BestBidAskProvider`；spot/swap 为两个独立 key、两个独立 coroutine
   （`best_bid_ask_provider.py` `_states` / `_watch`）。阈值默认由前端 `0.05` 提供、服务端
   `validate_slippage_threshold_pct` 独立校验，纯字符串规范化（无 `quantize`），零/负/合法超长整数
   被接受、格式非法 400。比较为两位 Decimal 严格 `>`（`domain.evaluate_smooth_gate`，复用
   `compute_opening_spread_pct`，未复制公式）。覆盖率分母恒为固化 `q_common`，两腿各取方向对应腿的
   一档量、`>= 0.80`。gate 窗口 `SMOOTH_GATE_WINDOW_US = 5 分钟`；超时复用既有立即链；
   `成交1次` 只 `force_smooth_gate` 当前 seq 后交由 worker 消费，不直接 dispatch；
   `prepare_attempt` 同事务复核 `expected_gate_seq` 与 `pass_reason` 并递增计数、清 gate，
   `scheduled_attempt_count >= target_n` 硬门使第 N+1 单不可能。
2. **放行速度与审计诚实性（Acceptance 2）**：成立。live smooth 不做每轮 fresh preflight（见 F-A 的
   同一处代码，功能方向正确，缺的是完整性校验）。D16 首轮杠杆在 `_worker_round` 内、
   `_wait_for_smooth_gate` 之前完成，`_dispatch_one_for_task` 的杠杆块显式排除 smooth（不重复
   dispatch）。放行到两腿订单客户端调用之间只有内存打点与 `prepare_attempt` 这一处 durable-before-send
   写；`append_log(kind='smooth_dispatch_audit')` 严格在 `self._executor.dispatch(ctx)` 返回之后，
   写失败被吞掉不改业务。审计使用产生该结论的同一对快照对象，放行后不再 `latest()`。
   SHELLUSDT 实盘记录与代码口径一致：`+0.05%` 展示值等于阈值故严格未过（原始 ≈0.0507614% 被
   `ROUND_HALF_UP` 量化为 0.05），随后 `0.15%` 以 `market` 放行、两腿 accepted、
   gate→两腿 client call 约 `4.523ms`/`4.893ms`。该证据只证明这一笔链路，不构成对所有行情的保证。
3. **并发、生命周期与故障（Acceptance 3）**：成立。F1 死锁已关闭：
   `_ensure_smooth_subscriptions` 的 `_smooth_lock` 只覆盖「是否已登记」与「两侧成功后的登记」，
   `subscribe` / `release` 全在锁外；provider 的 `_publish` / `_set_status` / `_notify` / `release`
   同样在自身锁外回调 `on_change`。冷启动：`start()` 始终 `self._ready.wait(5)`；`subscribe` 的
   创建者失败时 `_states.pop` + `future.cancel()`，`finally: state.ready.set()` 让并发等待者拿到
   明确失败而不是僵尸态；两侧部分成功时在 `finally` 里 `release` 回滚且不登记 task。
   订阅失败由 `_wait_for_smooth_gate` 捕获 → `_pause_task_local(PAUSE_REASON_PREFLIGHT_INCOMPLETE)`，
   `pause_task` 同事务清 gate，零 attempt、零 dispatch，Human 可再 Start 重试。热循环：两条失败
   分支均 `await asyncio.sleep(0.05)` 且可被 `close()`/cancel 打断。单侧失败只让该侧 snapshot 失效
   （`_snapshot_quote` 要求 `status == "live"` 且四值有限 > 0），不伪造对侧。offline 零构造、零线程、
   零订阅；缺 ccxt 时 smooth create 明确 `400 smooth_market_unavailable`，其他模式不受影响。
   清 gate 的三条路径（`set_task_status` 转非 running、`pause_task`、`stop_task_fatal`）与
   `prepare_attempt` 消费均在事务内完成，不存在 consumed-without-attempt 中间态。
4. **页面体验与真实接线（Acceptance 4）**：成立。`renderHedgeTaskCard` 对所有 smooth 状态单独渲染
   「滑点阈值」，动态块 `smoothExtras` 只在 `task.mode === 'smooth' && task.status === 'running'`
   生成，未运行卡 DOM 无 `hedge-smooth-market-*`、无伪盘口。running 卡展示两侧连接、双向一档价量、
   开单率、覆盖率、轮次与倒计时。`loadHedgeTasks()` 先 GET `?status=all` 刷新任务列表，再对
   `new Set([...runningIds, ...expandedIds])` 去重并集请求 task-id 日志，选择条件只依赖
   `status === 'running'` 与展开态、任务是否仍存在，不含 mode/task_type/方向特判；
   `refreshExpandedRunningHedgeLogs` 仅复用共享 tick，`setInterval(() =>` 计数仍为 4，无新 timer。
   浏览器刷新清空 `hedgeLogExpanded` 后 running smooth 立即补齐真实盘口，不再长期误报「数据不完整」。
   「显示值等于阈值但严格未通过」按 Human 决定只检查 wait reason / pass 状态是否诚实：
   `evaluate_smooth_gate` 的 `spread_pass=False` 与「等待当前方向开单率严格大于阈值」如实表达，
   未把未通过说成通过；本轮不要求改 UI、比较或精度。
5. **资金、订单与已接受限制（Acceptance 5）**：除 F-A 外成立。create 首次 preflight、缺腿探测、
   1000x open 拒绝、固化身份/数量/route、regular-spot forward 预划转（仅在 create 发生一次，
   Start 不重做）均保留在原位；`test_hedge_leverage.py` 与 `test_hedge_cycle_*.py` 相对 base 零 diff
   且全绿，是 immediate 每轮 fresh preflight 与杠杆时机未被波及的直接证据。L1/L2/L3 与「两位等值
   展示」四项为 Human 具名接受，本会话未发现满足其各自重开条件的新证据，故不据此判 REWORK
   （实际影响与临时边界见「Human Brief」）。
6. **证据真实性与独立复跑（Acceptance 6）**：见下节。测试强度抽查（临时副本变异，仓库零改动）：
   - 撤销 D15（让 smooth 重新走 fresh preflight）→ `test_smooth_gate_worker.py` 4 failed；
   - 把审计 `append_log` 挪到 `executor.dispatch` 之前 → 4 failed（含
     `test_smooth_audit_prepare_delay_grows_only_prepare_segment`）；
   - 去掉 provider `_watch` 的重试等待 → `test_failed_watch_retries_are_bounded_and_close_interrupts_wait` failed；
   - 撤销 D17 paused-create → 3 failed（worker + API 两侧）；
   - 删除 `prepare_attempt` 的 gate-seq/pass-reason 原子复核 →
     `test_smooth_prepare_fail_closed_and_consumes_gate_atomically` failed；
   - 删除组合根 offline 守卫 → `test_offline_hedge_service_never_constructs_market_provider` failed；
   - 把 running 刷新重新耦合到「日志已展开」→ `node frontend/self-check.js` FAIL；
   - 撤销 D18（非 running 也渲染动态块）→ self-check FAIL +
     `test_smooth_dynamic_market_only_renders_for_running_cards` failed。
   全部变异复原后重跑均恢复全绿。结论：这些用例是承重的，不是只看名字的空壳。
7. **发布准备度（Acceptance 7）**：见「发布准备度」表。
8. **活文档与发现纪律（Acceptance 8）**：见「非阻塞观察」第 4 条与「范围外发现」。

## 六、独立复跑（本会话，工作树 == `ad8c631`）

```text
pytest test_best_bid_ask_provider / test_smooth_gate_store / test_smooth_gate_worker /
       test_smooth_api / test_hedge_domain / test_live_hedge_executor /
       test_hedge_service / test_frontend_field_binding / test_service_health
    -> 362 passed

pytest test_hedge_store / test_hedge_api / test_hedge_task_local /
       test_hedge_review2_regressions / test_hedge_leverage /
       test_hedge_cycle_core / test_hedge_cycle_close / test_hedge_purity
    -> 311 passed

pytest backend/tests -q
    -> 1890 passed, 1 failed
       （唯一失败 = test_private_client.py::test_urlopen_only_in_designated_http_clients，
         pre-existing-independent，见「范围外发现」）

node frontend/self-check.js -> 全部自检通过（exit 0）
git diff --check e955bdd..ad8c631 -> 无输出
git status --porcelain -> 空（本 handoff 创建前）
.venv 中 ccxt 已安装（find_spec 命中），上述结果在已装 ccxt 的环境下取得
```

## 七、发布准备度（本 verdict 不授权其中任何一项动作）

| 层级 | 本次裁定 |
|---|---|
| 代码可进入 Human 最终合并决定 | **否**（F-A 为 in-range 资金/订单缺口） |
| 当前 worktree 运行的 live 页面可继续用于 Human 验收 | **可以继续做只读观察，但不要再创建新的平滑任务**：Start gate=true 时新建卡片经 Start 后会真实成交；且在 F-A 未修前，一次建卡期间的读失败就会造出会“乱下单”的卡片 |
| 可 merge / push / 部署 | 否；且本 verdict 为 REWORK，更不具备条件 |
| 后续真实任务的最小数量与观察方式 | F-A 修复并再过 Review-2 之后，仍应：单笔最小额度、单一 symbol、`target_n=1`、开着任务卡日志与交易所页面对照，确认「公共网格量」不是 `—` 再点启动 |

上线前最小可观察项与 fail-closed 边界（均在现有架构内，不新增恢复系统）：

- 建卡后先看任务卡「公共网格量」：显示 `—` 即代表建卡预检没成过，当前实现下**不要点启动**；
  F-A 修好后这类卡片应当在建卡时就被拒或在放行前 fail-closed 暂停。
- 运行卡「等待原因」出现「计划下单数量无效」时，任务必须人工暂停，不能等 5 分钟 timeout。
- 关 Start 总开关前先暂停任务（L1）；关闸后到任务卡与交易所确认这一轮的真实结果。
- 出现单腿告警或 `insufficient_*` / `rate_limited` 暂停时，按既有流程到交易所人工核对收口。

### Required Reading for the Next Task

- 读取路径及顺序：`reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-final-review-2-opus5.handoff.md`；`reports/agent-runs/2026-08-12-smooth-open-orders-v1/status.json`；`reports/agent-runs/2026-08-12-smooth-open-orders-v1/33-smooth-open-v1-final-review-2-opus5.dispatch.md`；`backend/hedge_open_tasks/service.py`；`backend/hedge_open_tasks/domain.py`；`backend/services/live_hedge_executor.py`；`backend/tests/test_smooth_gate_worker.py`
- 执行：Bookkeeper 核验本 handoff 的 source SHA-256、create-only 路径、固定累计 `base_sha=e955bdd300d214c5c3ad5c1acd629c0d21080165`/`delivery_sha=ad8c6317369e8a643f225cc37f22ad0eb949395b` 与 `REWORK` verdict，复现 F-A 的可执行命令，并按 `AGENTS.md` §8 处理 `rework_count`（Human 已明确豁免上限）后向 Human 用大白话汇报
- 关卡：Human 决定是否派发 F-A 修复（原 Implementer 最小范围返修）；修复后按 §8「窄范围 review-2 发现修复后直接回 Review-2」路由，仍须 fresh、跨 provider 的最终 Review-2；push/merge/部署/实盘启用仍须 Human 单独授权
- 不能假设的事实：本 `REWORK` 不授权本 Reviewer 或任何模型自行修复、控制服务、改 Start gate、创建任务或下单；累计 Review-1 的 `ACCEPT` 不能覆盖 F-A；假 `_Market` 与假 preflight 全绿不能证明 live 组合根在建卡预检缺口下安全；当前 `127.0.0.1:8787` 已加载 `ad8c631` 且 `executor_mode=live`、Start gate=true，页面上任何创建/启动动作都会进入真实订单链

## Human Brief / Console Receipt Source (author-only; immutable after task end)

[TASK_RESULT v2]
任务 ID: smooth-open-v1-final-review-2-opus5
执行结果: completed（完成）
结果摘要: 最终 Review-2 判 REWORK。发现一条可复现的资金缺口：建卡时的行情/账户预检若失败（如读不到抵押额度、429），平滑卡仍会以 201 建出来；Human 点启动后满 5 分钟或点成交1次，它会用没校验过的数量、默认路由发真实两腿单，可能只成交合约腿留裸空。其余功能（盯盘、闸门、次数上限、人工启动、页面刷新、延迟审计）独立复核成立。
产物: [reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-final-review-2-opus5.handoff.md]
检查结果: [fail：live 平滑在建卡预检从未成功时仍会发真实单（数量退化为未取整 single_amount、路由退回 PAPI、position 模式默认），已附零网络可复现命令；pass：provider 生命周期、F1 死锁关闭、冷启动无僵尸订阅、热循环有界、offline 零构造、缺 ccxt 建卡 400；pass：阈值严格>与两位口径、超长/零/负阈值处理、80% 覆盖分母为固化 q_common；pass：三因一 gate 原子消费、次数硬门、10/10 无第 11 单、清 gate 三路径；pass：D15 放行后无联网/sleep/审计 SQL、D16 杠杆前置、两腿并发与既有查单结算链未改；pass：D17 建卡即暂停零资源、未启动 fill-once 409、immediate 零回归；pass：D18 只有 running 渲染盘口、统一 2 秒并集刷新无新 timer、等值未过文案诚实；pass：独立复跑 362/311/1890+1（唯一失败早于 base 且零 diff）、self-check 全绿、关键用例变异均能测红]
阻塞项: [F-A in-range：建卡固化预检缺失时 live 平滑仍发真实订单，修复要求见本 handoff 第二节]
评审结论: REWORK（返工）
问题记录: reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-final-review-2-opus5.handoff.md
修复要求: reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-final-review-2-opus5.handoff.md
本地北京时间: 2026-08-13 20:54:17 CST
下一步模型: Bookkeeper（codex）
下一步任务: 读取：reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-final-review-2-opus5.handoff.md；reports/agent-runs/2026-08-12-smooth-open-orders-v1/status.json；reports/agent-runs/2026-08-12-smooth-open-orders-v1/33-smooth-open-v1-final-review-2-opus5.dispatch.md；执行：核验本 handoff 的 source SHA-256、create-only 路径、固定累计 base_sha=e955bdd/delivery_sha=ad8c631 与 REWORK verdict，并复现 F-A 的可执行命令；关卡：向 Human 汇报后由 Human 决定是否派发 F-A 最小范围修复，修复后仍须 fresh 跨 provider 最终 Review-2，push/merge/部署/实盘仍须 Human 单独授权。
[/TASK_RESULT]

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- source_sha256: `76a473ba5fe4d5f150a7ea5fbe3a13e0a9f8a775f4bf606b5f082ab11ee706fd`
- verified_at: `2026-08-13 21:10:07 CST`
- status_revision_verified: `53`
- verdict: `verified-rework`
- fixed_range: `e955bdd300d214c5c3ad5c1acd629c0d21080165..ad8c6317369e8a643f225cc37f22ad0eb949395b`
- create_only_and_identity: 本 handoff 是 Reviewer 唯一新增路径；task_id、Reviewer role、stage_id、`claude-opus-5`/`anthropic`、status revision、base/delivery 与 33 号 dispatch 和 revision 53 状态一致。Source Report、Human Brief、marker、`completed`、明确 `REWORK（返工）`、问题记录与修复要求字段均合规；作者区块未改写。
- git_and_source_check: 两个固定 SHA 均为可解析 commit，base 是 delivery 祖先；marker 前源区块复算值与 Reviewer 自报 SHA-256 完全一致。
- finding_reproduction: Bookkeeper 使用临时 SQLite、`NullPreflight`、假公共盘口与假执行器独立复现 F-A，零网络、零凭证、零真实订单：`create=201 paused`、固化 `q_common=None`；Start 后 timeout 产生 `dispatch_calls=1`，attempt `q_common=1.23456789`、`pass_reason=timeout`。因此技术 finding 与 `in-range` 分类成立，Reviewer 的 `REWORK` 原结论保留。
- non_blocking_observations: O1/O2/O3 保留 Reviewer 给出的重开条件，不扩张本轮；O4 已由 Bookkeeper 同步 `docs/product/PRD.md` 两处陈旧能力描述。`docs/api/public-market-contract.md` 与最终代码一致，未修改。
- state_effect: Human 决定本轮不修 F-A、不派修复任务；没有新实现交付，`rework_count` 保持 `5`。这不把技术 `REWORK` 改判为 `ACCEPT`，而是以 Human 接受风险决定进入最终合并选择；push、merge、部署、实盘、Start gate、任务、订单、依赖和服务控制仍未授权。

### Human Accepted Risk Decision（2026-08-13，current merge only）

- **问题事实：**live 平滑任务在建卡预检返回空（缓存未命中/超龄且实时补读失败）时仍会以 201 建卡，固化的 `q_common` 为空、`preflight_snapshot.available=false`；Human 点启动后，5 分钟 timeout 或「成交1次」放行会绕过 gate 已算出的「计划下单数量无效」结论，用未经网格取整的原始 `single_amount`、默认 `papi_margin` 现货路由、默认 `BOTH` position 模式发出真实两腿单。零件（executor 的 `single_amount` 回退、create 允许空 `q_common`）早于 base（`d90f2f1`），但由本区间 `dfd38a6` 的 D15 改动首次串到实盘写路径上；immediate 因每轮 fresh preflight 不受影响。
- **可能影响：**多数情况两腿被交易所按过滤器拒单；最坏情况合约腿成交、现货腿因路由与备款不匹配被拒，留下单腿裸空。
- **接受理由：**Human 2026-08-13 判定为极端场景，触发需缓存失效叠加实时补读失败双重条件，概率低，不值得为此再开一轮返修。
- **临时限制与观察方式：**建卡后先看任务卡「公共网格量」，显示 `—` 即代表该卡预检未成功，删除重建，不要点启动；运行卡「等待原因」出现「计划下单数量无效」时立即手动暂停，不要等 5 分钟 timeout；不要为纯展示验收创建平滑任务（Start gate 开启时会自动运行）。
- **后续复看条件：**实际出现过一张「公共网格量为 `—`」的平滑卡，或出现由此产生的单腿敞口，或将来要放开平滑任务的自动化/批量创建路径。
- **决策边界：**本决定只接受 F-A 作为本次合并的已知风险，不授权合并本身，也不授权 push、部署、实盘启用、改 Start gate、创建/启动任务、下单、安装/卸载依赖或控制当前服务。

## Errata (append-only)

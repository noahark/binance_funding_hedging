# 23-cadence-implementation —— Task 3 实现报告

- task_id: `hedge-leg-requery-cadence-v1`
- target_model: `claude_glm`（zhipu_glm）
- base_sha: `9faa716396cbbe67ebeec272ad6b3dd443bba583`
- 实现：2026-08-01（CST）
- 状态：`dispatched` → `reported`（未合并、未推送；未授予提交以外的职责）

权威规格：派工单 `hedge-leg-requery-cadence-v1.dispatch.md`（status_revision 23）；
设计依据 `10-design.md` P6、`11-adr.md` ADR-003。**本任务不基于 Task 2**（Human
2026-08-01 决定 Task 2 暂缓、先做 Task 3），故 ADR-002 的 429 指数退避机制尚不存在，
**本轮不实现退避**；派工单已删除「退避节流参数调优」要点与验收标准 5（429 退避）。

## 0. 边界与改动范围

仅改动派工单允许的文件，外加**一处经 Human 当场授权**的越界（见 §3）。`scheduler.py`
经核验无需改动（见 §4）；禁区一律未触。

```text
 backend/hedge_open_tasks/domain.py   # 默认值 1s→100ms + 下限常量 MIN_INTERVAL_US + 注释更正
 backend/hedge_open_tasks/store.py    # get_interval_us 读取处夹下限
 backend/hedge_open_tasks/service.py  # 亚秒显示 + worker 节流抖动（+import random）
 backend/tests/test_hedge_service.py  # 新增 6 个用例（显示/下限/节奏/抖动）
 backend/tests/test_hedge_task_local.py  # 新增 A-9 用例（下单频率不受 cadence 影响）
 backend/tests/test_hedge_api.py      # §3：Human 授权，默认断言 ==1 → ==0.1
```

**未触**：`frontend/`（含 index.html、self-check.js）、
`test_hedge_review2_regressions.py`、429 处理逻辑（`service.py` 查询期 + 派发期两站
逐字未改）、`domain.py` 的 51169 文案区（`:1336-1360`）、`private_client.py`、
`scheduler.py`、`status.json`（`current_task.state` 以外）。

`scheduler.py` 在 Allowed Files 内（「仅当 poll slice 需随亚秒调整」）但**无需改动**：
其唤醒切片 `max(min(interval_us/1e6/2, 0.25), 0.005)` 随 `interval_us` 自动从 ~0.5s 收
到 ~0.025s，有 5ms 下限；live 下 `tick()` 立即返回不产生交易所请求。这是派工单「已知且
可接受」的后果，未发现其它后果，故不动。

## 1. 实现要点（对应 ADR-003 Decision；退避一条本轮不适用）

1. **亚秒显示（要点 1 / 验收 1、3b）**。`service.py:201` 原
   `int(settings["interval_us"]) // 1_000_000` 在 `interval_us=100_000` 时得 `0`。抽出
   `_interval_seconds_doc(interval_us)`：`round(max(int(interval_us), D.MIN_INTERVAL_US)
   / 1_000_000, 3)`。`100_000 → 0.1`（不再是 0）；同时**把下限夹进显示**，使接口返回值
   始终等于 worker 实际生效值（根因警戒的落点，见 §2 验收 3）。
2. **下调默认（要点 2）**。`domain.py` `DEFAULT_INTERVAL_US` `1_000_000 → 100_000`；
   `DEFAULT_INTERVAL_SECONDS` `"1" → "0.1"`（同一行种子插入 `store.py:345-346` 的两个字
   段，保持自洽）。种子插入引用常量，自动生效，无需改 `store.py` 种子。
3. **读取处夹下限（要点 3 / 验收 3a）**。新增 `MIN_INTERVAL_US = 50_000`（domain.py）。
   `store.py` `get_interval_us` 改为 `return max(int(raw), D.MIN_INTERVAL_US)`。worker 节
   流（`service.py:1102`）、DRY-RUN `tick()`（`:1543`）、scheduler 唤醒（`scheduler.py:51`）
   三处都从 `get_interval_us` 取值，故夹一次即全局生效，误配极小值不会把 worker 转成忙轮询。
4. **节流抖动（要点 4 / 验收 2、4）**。新增模块函数 `paced_wait_seconds(interval_s) =
   interval_s * random.uniform(_PACING_JITTER_MIN, 1.0)`，`_PACING_JITTER_MIN = 0.75`。
   `_run_task_worker` 的 `ev.wait(interval_s)` 改为 `ev.wait(paced_wait_seconds(interval_s))`。
   每次 pacing 在 `[0.75×interval, 1.0×interval]` 内取随机值——恒正、不超标称间隔、多次不恒
   等，避免多 worker 对齐成查询脉冲。`_pump_worker` 测试缝**不含 pacing**，故抖动对确定性
   回归不可见；抖动本身用纯函数单测断言（无 sleep 竞态）。
5. **不新增运行时配置入口（红线 #6）、不拆分双间隔（ADR-003 Decision 2）**——遵守，未触。

**退避（原要点「退避节流参数调优」/ 原验收 5）本轮不适用**：属 Task 2 范围，未实现，亦未
为满足它而自行加退避。

## 2. 验收对照（派工单 Acceptance Checks 1–8）

1. **亚秒显示 — pass**。`interval_us=100_000` 时接口返回 `interval_seconds=0.1`（非 0），
   `test_settings_doc_renders_subsecond_interval` 断言。前端 `index.html:3856` 原文渲染为：
   **「调度间隔 0.1 秒（后端调度）」**（未改前端；返回 `0.1` 即正确渲染，无需新增键）。
2. **节奏 — pass**。默认 `get_interval_us() == 100_000`（`test_default_cadence_seeds_100ms`）；
   pacing `paced_wait_seconds(0.1)` 落在 `(0.075, 0.1]`（`test_requery_wait_is_100ms_within_jitter`）。
   确定性、无 sleep。
3. **下限与显示一致性（根因警戒落点）— pass**。误配 `interval_us=1000`：
   (a) `get_interval_us() == 50_000`（夹到下限，不忙轮询，`test_floor_clamps_effective_cadence`）；
   (b) 接口 `interval_seconds == round(50_000/1e6, 3) == 0.05`，**等于实际生效值、不等于误配原值
   `0.001`**（`test_floor_display_matches_effective_value`）。两者当前一致——这是本轮必修的缺陷，
   已修，非可接受现状。
4. **抖动 — pass**。500 次取样：恒 `0 < s ≤ 标称`、`min ≥ 标称×0.75`、`len(set) > 1`（不退化、
   有界、非恒等），`test_pacing_jitter_is_positive_bounded_and_varies`。
5. **下单频率不变（A-9）— pass**。`test_a9_cadence_drop_does_not_raise_order_frequency`：
   `target_n=3`、每对腿终态即进下一对，`_pump_worker`（无 pacing）驱动，断言恰好 3 次派发、
   3 个 attempt、`scheduled_attempt_count == 3`。cadence 改动只影响 pacing 等待，不触派发/串行
   逻辑（`_worker_round` / `_dispatch_one_for_task` 未改），故下单频率结构上不变。
6. **429 行为未触碰 — pass**。9 个锁定用例（`test_hedge_task_local.py` 6 个 + 
   `test_hedge_review2_regressions.py` 3 个）全绿；`service.py` 查询期 / 派发期两站逐字未改
   （`git diff` 中 `SIGNAL_RATE_LIMITED` / `PAUSE_REASON_RATE_LIMITED` / `_pause_task_local`
   零出现）。
7. **既有回归全绿 — pass**。`backend/tests/` 全量 **1140 passed**，输出见
   `62-cadence-test-output.txt`。
8. **边界 — pass**。未改 `frontend/`、未改 `test_hedge_review2_regressions.py`、未改 51169 文案
   区、未新增运行时配置入口、未拆分间隔字段、未新增状态枚举。

## 3. 经 Human 授权的越界：`test_hedge_api.py:227`

派工单验收 1 + 要点 2（默认降到 100ms、亚秒显示）**必然**使未列入两份清单的
`test_hedge_api.py:227`（`test_settings_default_shape`，断言全新库默认
`interval_seconds == 1`）变红——`100_000 → 0.1`。该文件既不在「允许改动」也不在「不得改动」
清单，是 Bookkeeper 漏列。我**未自行越界**：先停下来用 `AskUserQuestion` 把缺口交给 Human，
Human 2026-08-01 授权「改 test_hedge_api.py:227」。改动仅一行：`== 1` → `== 0.1`（附注释
`ADR-003: 100ms default cadence`）。这是验收 1+要点 2 的直接必然结果，非「为迁就坏改动而改
测试」。除此以外，改动严格落在 5 个批准文件内。全量 1140 passed 已含该文件。

## 4. 已知代价与未触碰的 429 逻辑（不是缺陷，未试图消除）

重查间隔降到 100ms 提高撞币安限频（429）的概率。当前 429 处理是**把该任务暂停**
（`pause_reason = rate_limited`，保留在途腿不重发，等人工恢复）——fail-closed，不丢钱、不删卡。
后果是任务可能更频繁自动暂停、需人工点恢复。Human 已知悉接受。抖动（要点 4）是本轮唯一缓解。
**ADR-002 的 429 指数退避属 Task 2、本轮不做**；撞 429 仍走既有 fail-closed 暂停路径。

## 5. 根因警戒核对

本 stage 的 F1/F2/F3/F4 同根因：展示层断言了它不知道的事。本任务前置修复对象是该根因的第
五个实例（`interval_us=100_000` 时接口返回 `interval_seconds: 0`，界面印「调度间隔 0 秒」）。
对本任务每一处用户可见的间隔数值的回答：

1. **`settings.interval_seconds` 向用户断言什么？** ——「后端调度的腿重查节奏，秒」。
2. **和实际生效一致吗？** —— 一致。显示与 worker 都从夹下限后的同一微秒值推导（显示
   `_interval_seconds_doc`、生效 `get_interval_us`），且共享同一常量 `MIN_INTERVAL_US`。
3. **不一致时显示什么？** —— 不会出现：误配极小值时，显示夹到下限 `0.05`、生效也夹到
   `50_000us`，二者相等，不再各自为政。

判据「不得让界面显示一个与实际生效值不符的间隔」——满足（验收 3b）。

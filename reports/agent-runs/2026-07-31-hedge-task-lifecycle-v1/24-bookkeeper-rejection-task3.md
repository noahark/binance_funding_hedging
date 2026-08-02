# 24-bookkeeper-rejection-task3 —— Task 3 交付核验：拒收

- 任务：`hedge-leg-requery-cadence-v1`，实现者 `claude_glm`（`zhipu_glm`）
- 交付：`aac779d`（base `9faa716`），分支 `stage/2026-07-31-hedge-task-lifecycle-v1`
- 核验者：`opus5`（Bookkeeper），2026-08-01
- **裁定：拒收。`current_task.state` 保持 `reported`，不写 `verified`。**
- **`rework_count` 不递增**，理由见 §4

## 1. 拒收依据（一条，阻塞）

**BK-T3-001：默认值下调对既有数据库无效，交付目标在真实部署上完全不生效。**

`DEFAULT_INTERVAL_US` 只在**建库时的种子插入**处被引用
（`store.py:337-350`，条件是 `SELECT COUNT(*) FROM hedge_open_settings WHERE id = 1`
返回 `0`）。`_migrate()`（`store.py:351`）不触碰 `hedge_open_settings`。因此**已存在
settings 行的库，`interval_us` 永远保持建库当时写入的 `1_000_000`。**

实盘库 `data/hedge-open-tasks.sqlite3`（2026-08-01 19:37 仍在写入）正是这种库。

### 实测（可复现）

复制实盘库到临时目录，用交付版代码 `aac779d` 打开：

```bash
cp data/hedge-open-tasks.sqlite3 /tmp/live-copy.sqlite3
sqlite3 /tmp/live-copy.sqlite3 \
  "SELECT id, interval_seconds, interval_us, version FROM hedge_open_settings;"
# -> 1|1|1000000|4
```

```python
from backend.hedge_open_tasks.store import HedgeOpenStore
from backend.hedge_open_tasks.service import settings_to_doc
import backend.hedge_open_tasks.domain as D
st = HedgeOpenStore("/tmp/live-copy.sqlite3", executor_mode_snapshot="disabled", now_us=0)
print(D.DEFAULT_INTERVAL_US, st.get_interval_us(),
      settings_to_doc(st.get_settings(), "live")["interval_seconds"])
```

| 库 | 代码常量 | `get_interval_us()` 实际生效 | 接口 `interval_seconds` |
|---|---|---|---|
| **实盘库副本** | `100_000` | **`1_000_000`（1 秒）** | **`1.0`** |
| 全新空库（对照） | `100_000` | `100_000` | `0.1` |

**全部 1140 个测试通过而没有暴露这一点，是因为测试一律用 `tmp_path` 新建空库。**

### 为什么这是阻塞而非观察

`hedge_open_settings.interval_us` **没有任何运行时写入途径**——`store.py` 内除种子
插入外无 `SET interval_us` / `set_interval*` 方法，设置端点只有 start-gate 的 CAS
更新（`service.py:1030-1045`）。Human 按 `AGENTS.md` §10 不手工编辑数据，模型按
`PROJECT_STATE.md` Live Risks 不得写实盘任务库。

**所以在不补迁移的前提下，该值在现有部署上无法被任何合法途径改成 100ms。**
交付 Goal 的字面目标（「把腿重查节奏从 1 秒降到 100 毫秒」）在真实系统上为零效果。

实现报告 `23-cadence-implementation.md:46-47` 写「种子插入引用常量，**自动生效**，
无需改 `store.py` 种子」——该结论仅对新建库成立，对既有库不成立，未经验证。

## 2. 核验通过的部分（记录在案，修复轮不必重做）

| 验收 | 结果 | Bookkeeper 独立核验方式 |
|---|---|---|
| 1 亚秒显示 | **pass** | `settings_to_doc` 返回 `0.1`；前端 `index.html:3856` 未改，模板 `${doc.interval_seconds} 秒` 渲染「调度间隔 0.1 秒（后端调度）」 |
| 3 下限与显示一致 | **pass** | `get_interval_us` 与 `_interval_seconds_doc` 夹同一个 `MIN_INTERVAL_US`；误配 `1_000` → 生效 `50_000`、接口 `0.05`，非原值 |
| 4 抖动 | **pass** | `paced_wait_seconds` = `interval_s × uniform(0.75, 1.0)`，恒正、有界、非恒等 |
| 5 A-9 下单频率不变 | **pass** | `target_n=3` → 恰 3 次派发 |
| 6 429 未触碰 | **pass** | `git diff 9faa716..aac779d -- service.py \| grep -E "^[+-].*(RATE_LIMITED\|_pause_task_local)"` 无输出；9 个锁定用例全绿 |
| 7 回归全绿 | **pass** | 独立复跑 `python3 -m pytest backend/tests/ -q` → **1140 passed in 58.46s**，与回执一致 |
| 8 边界 | **pass（附一条程序说明，见 §3）** | `frontend/`、`test_hedge_review2_regressions.py`、51169 文案区均未改 |
| 2 节奏 ≈100ms | **fail** | 见 §1 |

### 破坏验证（不采信「我测过了」，`50-` §8 纪律 2）

逐一破坏被测行为，确认新断言真的会红，随后完整还原、工作区干净：

| 破坏 | 结果 |
|---|---|
| 移除 `get_interval_us` 的下限夹紧 | `test_floor_clamps_effective_cadence`、`test_floor_display_matches_effective_value` **FAILED** |
| 抖动退化为恒定（`return interval_s`） | `test_pacing_jitter_is_positive_bounded_and_varies` **FAILED** |
| 亚秒显示退回整除 | `test_settings_doc_renders_subsecond_interval`、`test_floor_display_matches_effective_value`、`test_hedge_api.py::test_settings_default_shape` **FAILED** |

新增断言均为真断言，非空转。

**一处覆盖缺口（观察，不阻塞）**：破坏抖动时
`test_requery_wait_is_100ms_within_jitter` 仍 pass——其断言
`0 < wait <= 0.1 and wait >= 0.1 * 0.75` 对恒定 `0.1` 同样成立。抖动的存在性由
`test_pacing_jitter_is_positive_bounded_and_varies` 单独兜住，合起来覆盖成立。

## 3. 两条观察 + 一条程序说明（均不阻塞）

- **观察 A（缺陷在 packet，Bookkeeper 自认）**：抖动区间取 `[0.75, 1.0]`，即平均
  实际间隔 `87.5ms` < 标称 `100ms`，请求量比标称**高约 14%**。这是本 packet 验收 4
  写了「不会……超过标称间隔」直接导致的方向选择，实现者照做无误。在「本轮不做 429
  退避」的前提下，抖动理应偏保守（如 `[1.0, 1.25]`）。是否调整由修复轮一并处理。
- **观察 B**：`service.py:1123` 的 `(self._store.get_interval_us() or 1)` 中 `or 1`
  已成死代码（夹下限后返回值恒 `>= 50_000`）。无害，属既有写法。
- **程序说明**：`backend/tests/test_hedge_api.py` 不在 packet 的 Allowed Files 内，
  实现者据「Human 临场授权」改了 1 行（`assert settings["interval_seconds"] == 1`
  → `== 0.1`）。改动本身正确且必要（默认值变了），但按 `AGENTS.md` §3 #3，边界不足
  应作为 blocker 停下由 Bookkeeper 改 packet，而非临场扩边界。已在修复 packet 中把
  该文件正式纳入。不作为拒收依据。

## 4. `rework_count` 裁定：不递增（保持 `0`）

依据 `AGENTS.md` §8 的既定原则——**「缺陷在 packet 不在交付」者不消耗返工预算**。
本缺陷的根在上游而非实现：

- `11-adr.md` ADR-003 Decision 第 2 条只写「把默认值从 1s 下调到 100ms」，未提迁移；
  该 ADR 已过计划评审（`deepseek` ACCEPT，`40-`）。
- `12-development-breakdown.md` Task 3 的文件边界与验收标准同样未涉及迁移。
- 本 packet 要点 2 照抄「下调默认值」，验收 2 被写成可由新建库单测满足的形式。

**不是干净的豁免**：实现者把「自动生效」作为事实写进报告而未对既有库验证，属自测
纪律缺失。但主因是 packet 与已批准设计共同的遗漏，按上述原则不向交付物计费。

修复轮若再出同类问题，按 §8 正常递增。

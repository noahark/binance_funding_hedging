# review-1-codex-task3.dispatch

```text
Identity:
  task_id:         review-1-codex-task3
  target_role:     Reviewer (review-1)
  target_model:    codex
  provider:        openai
  status_revision: 27
  required_skill:  agents/skills/code-reviewer.md
```

## 读取位置（先确认，上一位复核者在此栽过）

本仓库有 **4 个 worktree**。受审内容只在**主工作区**
`/Users/ark/Desktop/ai code/funding_hedging` 的
**`stage/2026-07-31-hedge-task-lifecycle-v1`** 分支。`main` 上该 stage 目录停在
`49-`。开始前执行：

```bash
cd "/Users/ark/Desktop/ai code/funding_hedging"
pwd && git branch --show-current
```

## Goal

对交付 `d8522df` 执行 review-1（代码、契约、测试、集成缝）。

**评审区间（固定，不得移动 `HEAD`、不得基于未提交工作区）**：

```text
base_sha     9faa716396cbbe67ebeec272ad6b3dd443bba583
delivery_sha d8522dfd6f4a3fa64c27d383a900a8e7f84df7fc
```

区间内的 `9568cc2` / `c875425` / `48257df` 是本阶段的**控制提交**（packet、
`status.json`、Bookkeeper 记录），按 `AGENTS.md` §8「评审范围口径」属**上下文而非
受审交付**；针对它们的发现按范围三分类记为范围外。

风险等级 `HIGH_RISK`（订单状态判定 / 资金可见性 / 实盘写路径）。

## 交付内容（六项）

Human 于 2026-08-01 改变方向（D19/D20）：放弃 100ms，改 500ms + 容忍窗口。

1. 默认重查间隔 `1s → 500ms`；
2. `_migrate` 之后补回填，使新默认值在**既有数据库**上生效（原拒收项 BK-T3-001）；
3. 移除抖动；
4. `404 / -2013` 不再一次判死：`ABSENT_TOLERANCE_WINDOW_US`（约 5 秒，锚点
   `hedge_open_leg.dispatched_at_us`）内继续重查，窗口耗尽才判 `absent` 终态；
5. 原本**无上限**的「继续查」分支（5xx / 超时 / 畸形 2xx）套同一窗口，但窗口耗尽
   **不得判 `absent`**，升级为 `SIGNAL_ORDER_STATE_UNKNOWN` → 任务暂停待人工核对，
   腿保持非终态、永不重发；
6. 与 `_confirm_um_figures` 的既有语义统一（见下）。

设计依据（`live_hedge_executor.py` 的 `_confirm_um_figures` docstring 原文）：
「a POST-just-accepted order 404-ing is eventual-consistency noise, NOT a real
absent signal」。该保护原本只存在于 POST 后立即 confirm 的路径，worker 的 drain
路径没有——第 4-6 项是把它补齐。

## 必须披露的前序参与（影响你如何取舍，请自行判断权重）

- 本次交付的**第 5 项与第 6 项由 `deepseek` 提出**（它在 `26-` 对 Bookkeeper 裁定
  做独立复核时给出），Bookkeeper 采纳后原样写入 packet，实现者照做。
- `deepseek` 亦是本 stage 的**计划评审者**（`40-`，ACCEPT 了 ADR-003）。
- 本 packet 与上一份实现 packet 均由 Bookkeeper（`opus5`）撰写。
- **因此第 4-6 项在进入你手上之前，没有任何一个与其设计无关的模型审查过。**
  请按未经独立审查的新设计对待，不要因为「已有复核意见」而降低标准。

## Allowed Files

**只读。不得修改仓库中任何文件**，包括 `status.json`、evidence、代码、测试。
不得执行会写入 `data/` 下数据库的操作（那是活的实盘库；如需真实数据请先复制到
临时目录）。不得启动或停止任何服务进程。

可自由读取仓库全部内容并运行只读命令与测试。

## Inputs

| 材料 | 路径 |
|---|---|
| 本次 packet（交付要求原文） | `fix-cadence-500ms-and-absent-tolerance-v1.dispatch.md` |
| 实现报告 | `25-cadence-500ms-implementation.md` |
| 测试输出 | `63-cadence-500ms-test-output.txt` |
| **Bookkeeper 核验记录** | `27-bookkeeper-verification-task3-500ms.md` |
| 上一版拒收记录（BK-T3-001） | `24-bookkeeper-rejection-task3.md` |
| `deepseek` 的独立复核（第 5/6 项来源） | `26-request-independent-check-of-bookkeeper-verdict.md` |
| 方案与 ADR | `10-design.md` P6、`11-adr.md` ADR-003 |

**方案文档中的行号写于 Task 1 合并前，已整体漂移，勿照抄**；`27-` 与本 packet 中的
锚点为 `d8522df` 上实测。

## 请重点判断的四项

1. **容忍窗口的资金可见性含义**。窗口内不判终态意味着一条腿会在「可能已成交」状态
   多停留最多 5 秒。这对敞口计算、单腿判定、`aggregate_positions`、以及
   Task 1 合并持仓表的显示是否产生 Bookkeeper 未发现的影响？窗口耗尽后的两种收口
   是否都正确？特别是：**窗口内被判非终态的腿，若此刻任务被暂停/删除/重启，是否仍
   能被正确恢复重查（never resend）？**
2. **新增 `PAUSE_REASON_ORDER_STATE_UNKNOWN`**（`ALL_PAUSE_REASONS` 由六个变七个）。
   Bookkeeper 已采信（理由见 `27-` §4：红线 #3 约束的是任务状态枚举，且无替代做法）。
   请独立判断：该采信是否成立？新增值对既有契约（前端渲染、`pause_reason_zh`、
   `skip_counters`、恢复路径）有无未处理的影响？
3. **BK-T3-002：开发期写了实盘库**（`27-` §3）。事实：`data/hedge-open-tasks.sqlite3`
   于 2026-08-01 23:45:48 由 `interval_us = 1000000` 变为 `500000`；实现者归因
   「运行中服务应用了迁移」已被 Bookkeeper 用进程与代码证据证伪。Bookkeeper 判验收
   11c `fail` 但未据此拒收（改动良性、无资金数据受影响）。**请给出你自己的判断：
   这是否影响本交付的可发布性？**
4. **`SIGNAL_ORDER_STATE_UNKNOWN` 的两个产生点**（`service.py:1275` 与 `:1358`）。
   Bookkeeper 实测：单独破坏任一处，全量 1140 测试**仍全绿**；同时破坏两处才有测试
   变红。判定为「双保险而非覆盖缺口」。请独立判断该判定是否成立，以及是否应各自
   拥有独立断言。

## Acceptance Checks（你的评审须覆盖）

1. 受审差异按固定 `base_sha..delivery_sha` 读取，未移动 `HEAD`；
2. 上述四项重点均给出明确结论，不得以「Bookkeeper 已核验」代替独立判断；
3. 每条 `REWORK` 发现按 `AGENTS.md` §8 标注范围三分类（`in-range` /
   `pre-existing-independent` / `pre-existing-release-critical`），`pre-existing-*`
   须附早于 `base_sha` 的引入提交引用（`git blame` 或 `git log -L`）；
4. 检查测试是否为真断言而非空转（可自行破坏验证）；
5. 检查边界：`live_hedge_executor.py`、`frontend/`、429 站点、51169 文案区应未被
   改动；`test_hedge_review2_regressions.py` 仅 `test_5b` 新增一行时钟推进。

## Stop

只读评审 → 写评审记录到
`reports/agent-runs/2026-07-31-hedge-task-lifecycle-v1/28-review-1-codex-task3.md`
→ 按 `AGENTS.md` §7 返回 `[TASK_RESULT v2]`，含：

```text
评审结论: ACCEPT（接受） | REWORK（返工）
问题记录: <path | none>
修复要求: <path | none>
```

**停在这里。** 不得修改代码或 `status.json`、不得启动其他模型、不得合并。原始结果
由 Human 转交 Bookkeeper（`opus5`）同步。

无明确且格式良好的 `ACCEPT` 即为非接受（`AGENTS.md` §3 #7）。

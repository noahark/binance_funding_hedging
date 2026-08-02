# review-2-fable5-task3.dispatch

```text
Identity:
  task_id:         review-2-fable5-task3
  target_role:     Reviewer (review-2, 终审)
  target_model:    fable5
  provider:        anthropic
  status_revision: 36
  required_skill:  agents/skills/reality-checker.md
```

## 读取位置

主工作区 `/Users/ark/Desktop/ai code/funding_hedging`，分支
`stage/2026-07-31-hedge-task-lifecycle-v1`（本仓库有 4 个 worktree，`main` 上该 stage
目录停在 `49-`）。先执行 `pwd && git branch --show-current`。

## 你的角色与本 stage 的关系

**你是本 stage 唯一零参与的模型。** 设计、实现、review-1 均与你无关：

| 角色 | 模型 | provider |
|---|---|---|
| 方案设计 / 计划评审 | `claude_glm` / `deepseek` | zhipu_glm / deepseek |
| 实现（两轮） | `claude_glm`、`deepseek` | zhipu_glm / deepseek |
| review-1（三轮） | `codex`、`gpt` | openai |
| 全部 packet 与状态 | `opus5`（Bookkeeper） | anthropic |
| **review-2（你）** | **`fable5`** | **anthropic** |

隔离成立（与两位实现作者 provider 均不同）。Human 已显式启用你的独立付费额度。

**review-2 不是第二次代码评审。** 按 `AGENTS.md` §8：你判断**需求、实际交付效果、证据、
运营风险与发布就绪**。代码正确性已由 review-1 三轮覆盖，不必重做——除非你认为它漏了。

## 受审对象

```text
base_sha     9faa716396cbbe67ebeec272ad6b3dd443bba583
delivery_sha d2ac353caf22a68c6ff59a45167280365ace5a95
```

区间内 Bookkeeper 的控制提交（packet、`status.json`、核验记录）按 §8 属**上下文而非
受审交付**。

`rework_count` = **`2/3`**。若你判 `REWORK`，须由 Human 在「缩小范围 / 重新设计 /
接受限制 / 停止」中选择，Bookkeeper 不得自行再派修复。

## 这轮到底交付了什么（目标几经变化，请核对是否仍对齐 Human 的需求）

**原始需求**（`01-intake-brief.md` §③，Human 提出）：订单重查间隔 1 秒 → 100ms。

**中途改变**（Human 决策 D17-D20，2026-08-01/02）：

1. Bookkeeper 曾把 Human 要求的「原 JS 重试 10 次计数」**擅自替换为 5 秒时间窗口**，
   理由（需新增 DB 字段）不成立；后被推翻，改回计数器。
2. Human **放弃 100ms，改为 500ms**——与原 JS 策略（`Sleep(500)`）一致。
3. Human 决定**频率靠控制开单标的数量**管理，不引入程序级限流器。
4. 新增**订单查不到时的重试容忍**：查满 10 次才判定「订单不存在」。

**因此本轮的实际价值主张已由「提速 10 倍」变为「提速 2 倍 + 消除『真实挂单被判定为
从不存在』的风险」。** 请判断：**这个变化是否仍然对齐 Human 的原始意图？交付是否值得
其代价（三轮返工、rework_count 2/3）？**

支撑该改动的关键事实：`live_hedge_executor.py` 的 `_confirm_um_figures` docstring
**由作者自己写明**「a POST-just-accepted order 404-ing is eventual-consistency noise,
NOT a real absent signal」，且已有测试锁定；而 worker 的 drain 路径**没有这层保护**。

## 请重点判断的六项

### 1. 实际效果与运营风险

500ms 重查、10 次容忍窗口在真实运行中意味着什么？按 ADR-003 自述，币安权重上限约
20 次/秒；500ms 下每任务约 2 次/秒。**Human 以「控制开单标的数量」作为频率手柄——
这个手柄够用吗？** 是否存在 Bookkeeper 与 review-1 都未评估的运营场景？

### 2. BK-T3-002 发布门（本轮最重要的议题）

2026-08-01 23:45:48，**实盘库 `data/hedge-open-tasks.sqlite3` 在开发期被写入**
（`interval_us` 由 `1000000` → `500000`）。事实与归因见 `27-` §3：实现者归因于「运行中
服务应用迁移」已被 Bookkeeper 用进程与代码证据**证伪**；真正的写入者是某次指向真实库
路径的运行，**无法确定是哪一次**（未留下进程记录）。

- 被改的只有节奏设置，值正确，**未触碰任何任务/订单/资金数据**；
- 但 packet 的 `data/` 只读红线与 `PROJECT_STATE.md` 的「无 agent 可写实盘任务库」
  **均被突破**；
- review-1 两轮均认定其为**独立发布门**，与代码是否通过无关。

**请给出你的判断**：这次过程违规对**发布就绪**意味着什么？Human 应当在合并前补做什么
（例如实盘库快照/备份、启动前核对、流程加固）？还是可以直接接受？

### 3. 证据是否足以支撑上实盘

本交付经三轮 review-1、两轮 Bookkeeper 拒收、一次同根因刹车。测试从 1140 增至 1158。
**但 `PROJECT_STATE.md` 记录：本项目的对冲开单链路「inline log 已合并但无任何运行时
验证」，且 Task 1 合并时 review-2 要求的只读真机冒烟（清单 `49-`）Human 授权跳过、
至今未跑。**

请判断：**这轮改的是订单状态判定（资金可见性），在没有任何真机验证的情况下，证据链
是否足够？** 是否应当在合并前补跑 `49-`（其中「账户未就绪路径」一项与本 stage 直接相关）？

### 4. 已接受限制的合理性

三条与本轮相关：

- **F1-P1**（`32-` §7.3）：worker 交接与计数清理的竞态。Human 接受，理由是三个触发入口
  全为人工点击、窗口毫秒级、后果仅多查 5 秒。review-1 独立扫描确认前提成立。
- **Task 1 遗留的 A / B 两条**（`PROJECT_STATE.md`）：单腿敞口标记漏报部分失衡；
  现货余额与 drift 读错账户导致 drift **永不触发**。
- **F4**（`46-` §3.3）：账户读不到时谎称「交易所无仓」。原定 Task 2 修，**Task 2 已被
  Human 暂缓并标记「设计存疑」**，故该限制**须在合并 `main` 前重新交 Human 裁定**。

请判断这些限制**叠加**之后的操作风险——尤其是 F4 与本轮的交互：本轮让订单状态判定更
可靠了，但 F4 仍会在账户读不到时对每一行谎称「交易所无仓」。

### 5. 本轮引入的两处新语义，操作者能不能理解

- **`order_state_unknown`**（第 7 个暂停原因）：订单查满 10 次仍状态不明 → 任务暂停待
  人工核对。**但前端 `HEDGE_PAUSE_REASON_LABELS` 只翻译了 1 个暂停原因**，其余 6 个
  （含本条与 51169 冻结文案）**直接显示英文键名**——后端准备好的 `pause_reason_zh`
  前端从未读取（`36-` §2.4）。
- **`exposure_alert`** 经核实是**死状态**：后端无任何写入路径，前端标签永不出现
  （`36-` §2.3）。

请判断：这两条对**操作者能否正确理解任务卡状态**意味着什么？是否构成发布前必须处理的项？

### 6. 遗漏与残留

`AGENTS.md` §8 的范围三分类要求：若你提出 `REWORK` 发现，须标注
`in-range` / `pre-existing-independent` / `pre-existing-release-critical`，后两者须附
早于 `base_sha` 的引入提交引用。**若你的发现全部属范围外，请返回 `ACCEPT` 并把它们记为
后续项**（§8 明文允许）。

## Allowed Files

**只读。不得修改仓库中任何文件**（含 `status.json`、evidence、代码、测试）。
**不得对 `data/` 下任何数据库执行写操作**——那是活的实盘库，需要真实数据请先复制到
临时目录（BK-T3-002 即由此类操作造成）。不得启动或停止任何服务进程。
可自由读取仓库全部内容并运行只读命令与测试。

## Inputs（建议阅读顺序）

| # | 材料 | 内容 |
|---|---|---|
| 1 | `PROJECT_STATE.md` | 跨 stage 风险，含 BK-T3-002 与 Task 1 的三条限制 |
| 2 | `01-intake-brief.md` §③ | Human 的原始需求 |
| 3 | `11-adr.md` ADR-003 | 节奏设计（写于 100ms 时期，部分已被 D19 推翻） |
| 4 | `35-review-1-gpt-task3-r3.md` | review-1 终轮 ACCEPT |
| 5 | `37-bookkeeper-sync-review1-accept.md` | Bookkeeper 对该 ACCEPT 的复验 |
| 6 | `34-` `32-` `30-` `27-` `24-` | Bookkeeper 历次核验与拒收（含 BK-T3-002 全部证据） |
| 7 | `36-task2-design-reservations-and-inputs.md` | Task 2 的设计保留、死状态与前端文案缺失 |
| 8 | `33-runtime-seam-scan-implementation.md` | 本轮实现报告（穷举清单在 §一） |

## Acceptance Checks（你的评审须覆盖）

1. 按固定 `base_sha..delivery_sha` 读取，未移动 `HEAD`；
2. 上述六项重点逐项给出明确结论；
3. 对**发布就绪**给出可执行的结论：可合并 / 合并前须补做某事 / 不可合并；
4. 任何 `REWORK` 发现按 §8 标注范围三分类并附证据；
5. 不以 review-1 或 Bookkeeper 的结论代替你自己的判断。

## Stop

只读评审 → 报告写到
`reports/agent-runs/2026-07-31-hedge-task-lifecycle-v1/38-review-2-fable5-task3.md`
→ 按 `AGENTS.md` §7 返回 `[TASK_RESULT v2]`，含：

```text
评审结论: ACCEPT（接受） | REWORK（返工）
问题记录: <path | none>
修复要求: <path | none>
```

**停在这里。** 不得修改代码或 `status.json`、不得启动其他模型、不得合并、不得部署或
启用实盘。原始结果由 Human 转交 Bookkeeper（`opus5`）。

**你的 `ACCEPT` 不等于放行**：`AGENTS.md` §9 明文——review `ACCEPT` 不合并、不部署、
不启用实盘，也不替代最终的人工验收。BK-T3-002 仍须 Human 单独裁定。

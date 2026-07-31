# Dispatch —— plan-review-deepseek-v1（计划评审，只读）

> **⚠️ 作废 2026-07-31（bookkeeper opus5）—— 本 packet 从未交付，不要执行。**
> 签发后、交付前，Bookkeeper 核查发现受审方案 `b370401` 的 ADR-001 前提不成立
> （后端合并并非做不到：`server.py:632-642` 两服务同 handler，`snapshot_service.py:237-257`
> live 取数零上游请求）。Human 据此改定 **D14 合并改后端做**、**D15 保留删卡成本基**，
> 见 `04-backend-merge-decision.md`。方案正由 `plan-revision-backend-merge-v1` 修订，
> 本 packet 的评审对象 `afa3d52..b370401` 已被取代。
> 修订完成后按新 `delivery_sha` 重新签发，届时 R1/R2/R4/R5 与 C1-C5 大部分仍适用，
> **R3 已由 D15 直接解决、不再是评审判断题**。

```text
Identity:
  task_id:         plan-review-deepseek-v1
  target_role:     Reviewer
  target_model:    deepseek
  provider:        deepseek
  status_revision: 5
  required_skill:  （无 —— 计划评审不读代码评审技能，见下方说明）
```

## Goal

对 `plan-hedge-task-lifecycle-v1` 产出的实现方案做一次**独立、跨 provider、只读**的计划评审。这是 `AGENTS.md` §8 对 `HIGH_RISK` 任务在**实现开始前**的强制关卡。

- 方案作者是 `claude_glm`（provider `zhipu_glm`），你是 `deepseek`，provider 隔离成立。
- 你**只评审方案，不评审代码**，因为本轮**尚未写任何代码**。不要求你逐行审 `backend/` 或 `frontend/`；你需要读代码，只是为了**核实方案引用的事实是否属实**。
- 你的 verdict 返回 Planner，**不触碰 `rework_count`**（§8）。
- 未取得明确、格式良好的 `ACCEPT` 即为非接受（§3 #7）。

不指定 review skill：`code-reviewer.md` 与 `reality-checker.md` 分别面向代码交付与发布就绪，本任务两者皆非。按 `agents/roles.md` Shared Rules「零或一个」的下限执行。

## 评审对象（固定区间，不得移动 HEAD）

```text
base_sha    = afa3d5228e64ed2399e3d24b6971245e20950d9f
delivery_sha = b3704016d166fe01f2c09b05952e2b79c35232cd
```

受审交付**仅**这三份文档：

- `reports/agent-runs/2026-07-31-hedge-task-lifecycle-v1/10-design.md`（28648 字节）
- `reports/agent-runs/2026-07-31-hedge-task-lifecycle-v1/11-adr.md`（9510 字节）
- `reports/agent-runs/2026-07-31-hedge-task-lifecycle-v1/12-development-breakdown.md`（11453 字节）

区间内的其他提交（`a54f4ef`、`4a40de8` 是 Bookkeeper 的控制提交）按 §8「评审范围口径」是你的**上下文而非受审交付**，针对它们的发现按范围三分类记为范围外。

## Inputs

| 文件 | 字节数 | 读什么 |
|---|---|---|
| 本 dispatch | —（当前文件） | 全部 |
| `10-design.md` / `11-adr.md` / `12-development-breakdown.md` | 见上 | 全部（受审对象） |
| `plan-hedge-task-lifecycle-v1.dispatch.md` | 12766 | 全部 —— 方案要满足的原始约束与八个决策点 |
| `02-scope-decisions.md` | 7647 | 全部 —— Human 已定决策 D1-D8 与字段事实 |
| `03-fake-ui-outcome-and-plan-scope.md` | 6382 | 全部 —— D9-D13 |
| `PROJECT_STATE.md` | 5197 | Live Risks 与 Open Follow-ups 两节 |
| `AGENTS.md` | 16587 | §1 §3 §7 §8 |
| `agents/roles.md` | 12183 | Shared Rules + Reviewer 段 |

源码只按需抽查用于**证伪方案引用的事实**，禁止整文件读（三个后端主文件合计约 27 万字节）。

## Acceptance Checks —— 你必须逐条给出结论

### 必查的五个具名事项

这五项是 Bookkeeper 核验后指定的重点，**每一项都要单独给出结论**，不得合并带过。

- **R1｜ADR-002 `rate_limited` 剥离**（最重要）。Human 已明确决定「六种非人工暂停全部改自动删除」，且交接简报记录 Human 曾拒绝过「只改一种」的建议。方案把 `rate_limited` 从删除集剥离改为退避，是**本方案唯一偏离 Human 已述决策之处**。请判断：论证（「瞬态背压 vs 终态失败」「与意图对齐、与字面偏离」）是否成立？回退方案（坚持字面六删则不做 ③）是否可行？**这是 Human 的产品决定，你给技术判断和风险，不替 Human 决定。**
- **R2｜ADR-003 推翻既有 follow-up**。方案以「live 模式 `tick()` 是 SAFE NO-OP」为据，推翻 `PROJECT_STATE.md` 中「拆分下单间隔与重查间隔」的旧建议。请**自行核实该事实**（`service.py` 的 `tick()`），并判断「不拆分」的推论是否完整 —— 特别是：`interval_us` 是否真的没有任何其他消费者会因下调而改变下单节奏？
- **R3｜非目标 #7 与 `PROJECT_STATE.md` 的记录冲突（Bookkeeper 提出）**。`PROJECT_STATE.md` 的 `[OPEN][MONEY-VISIBILITY]` 条目写明：`aggregate_positions` 排除 `deleted` 任务，「**it becomes routine if auto-pause ever turns into auto-delete**」，并明确记着「**Blocks that change**」。方案的 ② 正是做这个转换，却在非目标 #7 里决定**不改**后端 `WHERE != DELETED`，理由是合并表以 `um_positions` 为骨架已解决资金可见性。请判断：
  - 该理由是否**完整**覆盖了被记录的风险？Bookkeeper 的观察是它只覆盖了**敞口可见性**，未覆盖**成本基**——被自动删除任务的 `spot_avg`/`perp_avg` 仍会从 `aggregate_positions` 消失，于是合并表上该行退化为「无任务记录」，用户能看到「我空了 0.07 BTC」却看不到「我在什么价位进的」。而 ② 落地后自动删除成为常态。
  - 若你认同该缺口存在：它是否足以阻塞 ②？还是可作为具名后续项？
  - 若你认为 Bookkeeper 判断有误，请直接说明理由。
- **R4｜P4 的行为收紧**。方案让 `post_start` 对 `stopped` 状态不再可重启（现状可重启）。这是对既有操作行为的收紧，Human 未就此表态。判断其合理性与影响面，并确认降级方案（只加配额守门、不动 `stopped`）是否可行。
- **R5｜交付拆分与顺序的可执行性**。三个任务的文件边界是否真的互不重叠？「①② 可并行开发但 ② 不得先于 ① 合并」「③ 须基于 ② 的 `delivery_sha` rebase」是否可操作？每个任务的验收标准是否可判定？

### 通用检查

- **C1｜事实核实**：方案 §0 的事实清单与各处代码引用是否属实。抽查即可，重点是**支撑关键决策的那几条**。已知一处引用错误（`11-adr.md` ADR-001 引 `index.html:2106` 指向无关代码，`directionForPosition` 实际在 `:2198`）—— 该处 Bookkeeper 已发现，你不必重复报，但请留意是否还有其他类似错误**支撑了某个结论**（那性质就不同了）。
- **C2｜红线**：六条红线（51169 逐字冻结、不得放宽 A-1、不得新增状态枚举、不得用账户级数值冒充每币、不得自动交易动作、不得无证据抽象）是否真被守住 —— 方案自己声称遵守，请独立判断。
- **C3｜A-1 家族**：四站（`store.py:690/740/979`、`service.py:1172`）的逐站评估是否成立；清单外三处的不适用理由是否正确。
- **C4｜遗漏**：方案是否遗漏了 dispatch 要求的裁定，或悄悄扩大了 Human 未授权的范围。
- **C5｜风险清单**：§7 的三处风险与早期验证方式是否切中要害；有没有它没看见但你认为更危险的。

## 输出要求

按 `AGENTS.md` §7 返回 `[TASK_RESULT v2]`，并含 review closure 三行：

```text
评审结论: ACCEPT（接受） | REWORK（返工）
问题记录: <path | none>
修复要求: <path | none>
```

- **`问题记录` 与 `修复要求` 请填 `inline-full-text`，并把发现清单的完整正文放在同一次输出的正文里**。本仓上一 stage 七轮评审中有四轮的正文没有跟着回执转交，两轮不得不回头补要。你是只读会话、不落盘文件，正文就是唯一载体。
- 每条 `REWORK` 发现按 §8 标注范围三分类：`in-range` / `pre-existing-independent` / `pre-existing-release-critical`。`pre-existing-*` 须附早于 `base_sha` 的引入提交引用（`git blame` 或 `git log -L`），无此证据者只记为观察。
- R1 与 R3 若你的结论是「需 Human 裁定」而非技术缺陷，请明确这样写，不要为了凑 `REWORK` 而把产品决定包装成技术发现。
- 发现全部为范围外时返回 `ACCEPT`，`问题记录` 照常填，`修复要求` 指向后续项或 `none`。

## Stop

- 你是**只读**会话：不得修改任何文件（含 `status.json`）、不得写代码、不得提交、不得合并、不得推送。
- 不得移动 `HEAD`，评审只针对上面写死的 `base_sha..delivery_sha`。
- 不得启动、调用、转交或冒充任何其他模型会话（§3 #2）。
- `ACCEPT` 不构成实现、验收、合并、部署或实盘授权；你的结论交回 Human，由 Bookkeeper 同步。
- 若发现本 dispatch 与受审文档矛盾、或评审对象与 `status.json` 不符：停止并报告，不要自行取舍。

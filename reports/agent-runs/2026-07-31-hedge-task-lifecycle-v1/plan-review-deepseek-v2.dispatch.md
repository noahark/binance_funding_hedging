# Dispatch —— plan-review-deepseek-v2（计划评审，只读）

```text
Identity:
  task_id:         plan-review-deepseek-v2
  target_role:     Reviewer
  target_model:    deepseek
  provider:        deepseek
  status_revision: 7
  required_skill:  （无 —— 计划评审不读代码评审技能，见下方说明）
```

> 取代 `plan-review-deepseek-v1.dispatch.md`（已作废，从未交付）。v1 的评审对象 `b370401`
> 已被修订版取代；v1 的 R3 已由 Human 决策 D15 直接解决，不再是评审判断题。

## Goal

对 `plan-hedge-task-lifecycle-v1`（经 `plan-revision-backend-merge-v1` 修订）产出的实现方案做一次**独立、跨 provider、只读**的计划评审。这是 `AGENTS.md` §8 对 `HIGH_RISK` 任务在**实现开始前**的强制关卡。

- 方案作者是 `claude_glm`（provider `zhipu_glm`），你是 `deepseek`，provider 隔离成立。
- 你**只评审方案，不评审代码** —— 本轮尚未写任何代码。你读源码只为**核实方案引用的事实是否属实**。
- 你的 verdict 返回 Planner，**不触碰 `rework_count`**（§8，当前为 `0`）。
- 未取得明确、格式良好的 `ACCEPT` 即为非接受（§3 #7）。

不指定 review skill：`code-reviewer.md` 与 `reality-checker.md` 分别面向代码交付与发布就绪，本任务两者皆非。按 `agents/roles.md` Shared Rules「零或一个」的下限执行。

## 评审对象（固定区间，不得移动 HEAD）

```text
base_sha     = afa3d5228e64ed2399e3d24b6971245e20950d9f
delivery_sha = c1cc10e8fb491f83fe4c09f565b34e06c2de0a50
```

受审交付**仅**这三份文档（以 `delivery_sha` 上的版本为准，含修订后内容）：

- `reports/agent-runs/2026-07-31-hedge-task-lifecycle-v1/10-design.md`
- `reports/agent-runs/2026-07-31-hedge-task-lifecycle-v1/11-adr.md`
- `reports/agent-runs/2026-07-31-hedge-task-lifecycle-v1/12-development-breakdown.md`

区间内其余提交（`a54f4ef`、`4a40de8`、`7755262`、`2bc5984` 为 Bookkeeper 控制提交，`b370401` 为方案首版）按 §8「评审范围口径」是你的**上下文而非受审交付**；针对它们的发现按范围三分类记为范围外。方案的首版与修订版差异可用 `git diff b370401 c1cc10e` 查看。

## Inputs

| 文件 | 读什么 |
|---|---|
| 本 dispatch | 全部 |
| 三份受审文档 | 全部 |
| `plan-hedge-task-lifecycle-v1.dispatch.md` | 原始约束、八个决策点 P1-P8、**六条红线** |
| `plan-revision-backend-merge-v1.dispatch.md` | 修订约束、五个新决策点 N1-N5、**第七条红线** |
| `02-scope-decisions.md` | Human 已定 D1-D8 与字段事实 |
| `03-fake-ui-outcome-and-plan-scope.md` | D9-D13 |
| `04-backend-merge-decision.md` | **D14/D15 与被推翻前提的完整记录（R0 的评审依据）** |
| `PROJECT_STATE.md` | Live Risks 与 Open Follow-ups 两节 |
| `AGENTS.md` | §1 §3 §7 §8 |
| `agents/roles.md` | Shared Rules + Reviewer 段 |

实际字节数请自行 `wc -c` 获取。源码只按需抽查用于**证伪方案引用的事实**，禁止整文件读（三个后端主文件合计约 27 万字节）。

## Acceptance Checks —— 你必须逐条给出结论

### 必查的六个具名事项

每一项都要**单独**给出结论，不得合并带过。

- **R0｜方案转向所依据的四条事实（最高优先级）**。本方案的核心选型从「前端合并」翻转为「后端合并」，整个翻转建立在 Bookkeeper 提出、Planner 复核的四条事实上。**这四条若有一条不成立，翻转就是错的。请你独立核实，不要采信任何一方的转述：**
  - **F-A**：`server.py:632-642` `build_server` 是否真的把 `SnapshotService` 与 `HedgeOpenTaskService` 注入同一个 `_Handler`？`_hedge_open_positions`（`server.py:607-608`）是否真能同时够到两者？
  - **F-B**：`snapshot_service.py:237-257` `get_snapshot()` 在 live 模式是否真的**零上游请求**？offline 分支（同步构建 + 60s 缓存）会不会在某些部署下变成实际路径，从而使「零新增请求」不成立？
  - **F-C**：`SnapshotNotReady` 的触发条件与影响面。
  - **F-D**：`snapshot.py:1097-1116` 的降级形状是否如所述。
  
  若你发现某条不成立，**直接说明**——这比任何其他发现都重要。
- **R1｜ADR-002 `rate_limited` 剥离**。Human 已明确决定「六种非人工暂停全部改自动删除」，且交接简报记录 Human 曾拒绝过「只改一种」的建议。方案把 `rate_limited` 从删除集剥离改为退避，是**方案唯一偏离 Human 已述决策之处**。判断：论证（「瞬态背压 vs 终态失败」）是否成立？回退方案（坚持字面六删则不做 ③）是否可行？**这是 Human 的产品决定，你给技术判断和风险，不替 Human 决定。**
- **R2｜ADR-003 推翻既有 follow-up**。方案以「live 模式 `tick()` 是 SAFE NO-OP」为据，推翻 `PROJECT_STATE.md` 中「拆分下单间隔与重查间隔」的旧建议。**自行核实该事实**，并判断推论是否完整：`interval_us` 是否真的没有任何其他消费者会因下调而改变下单节奏？
- **R3｜后端合并的新增风险（取代 v1 的 R3）**。后端合并相对前端合并新引入三类风险，方案在 §7.1 自列，请独立判断其是否充分：
  - **接口契约**：N1 决定就地改 `GET /api/hedge-open-positions`（§3.4 冻结的 Position JSON）。其「唯一消费者是前端渲染器、本任务同时重写」的理由是否成立？有无遗漏的消费者（测试、self-check、其他前端路径）？
  - **降级契约**：N2 规定账户数据未就绪/不可用时返回 HTTP 200 + 本地行 + `account.verified:false`。该契约是否有漏洞（例如部分可用、数据陈旧但 `verified:true`）？会不会让用户把陈旧数据当实时？
  - **snapshot 耦合**：持仓接口现在依赖 SnapshotService 的发布时序。是否存在方案未覆盖的时序或并发问题？
- **R4｜D15 的语义变更**。去掉 `aggregate_positions` 两条 `WHERE t.status != DELETED` 后，已删除任务的已成交腿开始计入。判断：`includes_deleted_task` 标记是否足以防止误读？是否存在方案未考虑的副作用（例如同一币种活任务与已删任务的腿混入同一桶后，均价口径是否仍正确）？**这一条请特别用心 —— 它直接改变资金数字的含义。**
- **R5｜交付拆分与串行约束**。修订后三个任务改为**严格串行** ①→②→③（因文件重叠不再可并行）。判断：串行推导是否正确？每个任务的文件边界、验收标准是否可判定？`rebase` 链（② 基于 ① 的 `delivery_sha`，③ 基于 ②）是否可操作？

### 通用检查

- **C1｜事实核实**：方案 §0 事实清单与各处代码引用是否属实。抽查即可，重点是**支撑关键决策的那几条**。
- **C2｜红线**：**七条**红线（51169 逐字冻结、不得放宽 A-1、不得新增状态枚举、不得用账户级数值冒充每币、不得自动交易动作、不得无证据抽象、不得重新论证 P1 选型）是否真被守住 —— 方案自称遵守，请独立判断。
- **C3｜A-1 家族**：四站（`store.py:690/740/979`、`service.py:1172`）的逐站评估是否成立；清单外三处的不适用理由是否正确。
- **C4｜修订完整性**：修订是否遗漏了受 D14/D15 影响却未更新之处（交叉引用、§5 与 fake 的一致性、§6 证据表等），或反过来**擅自改动了不该动的部分**（P2-P4/P6-P8、Task 2/3 应保持原判）。
- **C5｜遗漏与越界**：是否遗漏 dispatch 要求的裁定，或悄悄扩大了 Human 未授权的范围。
- **C6｜风险清单**：§7 的风险与早期验证方式是否切中要害；有没有它没看见但你认为更危险的。

## 输出要求

按 `AGENTS.md` §7 返回 `[TASK_RESULT v2]`，并含 review closure 三行：

```text
评审结论: ACCEPT（接受） | REWORK（返工）
问题记录: <path | none>
修复要求: <path | none>
```

- **`问题记录` 与 `修复要求` 请填 `inline-full-text`，并把发现清单的完整正文放在同一次输出的正文里**。本仓上一 stage 七轮评审中有四轮的正文没有跟着回执转交，两轮不得不回头补要。你是只读会话、不落盘文件，正文就是唯一载体。
- 每条 `REWORK` 发现按 §8 标注范围三分类：`in-range` / `pre-existing-independent` / `pre-existing-release-critical`。`pre-existing-*` 须附早于 `base_sha` 的引入提交引用（`git blame` 或 `git log -L`），无此证据者只记为观察。
- R1 若你的结论是「需 Human 裁定」而非技术缺陷，请明确这样写，不要为了凑 `REWORK` 而把产品决定包装成技术发现。
- 发现全部为范围外时返回 `ACCEPT`，`问题记录` 照常填，`修复要求` 指向后续项或 `none`。

## Stop

- 你是**只读**会话：不得修改任何文件（含 `status.json`）、不得写代码、不得提交、不得合并、不得推送。
- 不得移动 `HEAD`，评审只针对上面写死的 `base_sha..delivery_sha`。
- 不得启动、调用、转交或冒充任何其他模型会话（§3 #2）。
- `ACCEPT` 不构成实现、验收、合并、部署或实盘授权；结论交回 Human，由 Bookkeeper 同步。
- 若发现本 dispatch 与受审文档矛盾、或评审对象与 `status.json` 不符：停止并报告，不要自行取舍。

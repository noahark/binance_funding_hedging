# Dispatch —— review-1-grok-task1（代码评审，只读）

```text
Identity:
  task_id:         review-1-grok-task1
  target_role:     Reviewer
  target_model:    grok
  provider:        xai
  status_revision: 11
  required_skill:  agents/skills/code-reviewer.md
```

## Goal

对 Task 1（`hedge-merged-positions-v1`）的代码交付做 review-1：检查正确性、契约、测试与集成接缝。

- 实现者是 `claude_glm`（provider `zhipu_glm`），你是 `grok`（provider `xai`），provider 隔离成立。
- 你是**只读**会话。Kimi 额度不可用时 grok 是 Human 批准的 review-1 备选（`agents/roles.md`）。
- 未取得明确、格式良好的 `ACCEPT` 即为非接受（`AGENTS.md` §3 #7）。

## 评审对象（固定区间，不得移动 HEAD）

```text
base_sha     = c1cc10e8fb491f83fe4c09f565b34e06c2de0a50
delivery_sha = 969c4557a293a257b3c81c26c5a9c224f6b7f037
```

受审交付是该提交的代码与证据改动：`backend/app/server.py`、`backend/hedge_open_tasks/{domain.py, store.py}`、`backend/tests/{test_hedge_api.py, test_hedge_store.py, test_positions_merge.py}`、`frontend/{index.html, self-check.js}`，以及 `21-merged-positions-implementation.md` / `61-merged-positions-test-output.txt`。

区间内 `e5af03c`、`b2f2513` 为 Bookkeeper 控制提交，按 §8「评审范围口径」是上下文而非受审交付。

## ⚠️ 先读这一条：两条已知缺陷不得据以返工

Bookkeeper 核验时发现两条 in-range 缺陷，**Human 已明确决定本轮不修**，按 `AGENTS.md` §8 转为已接受的已知限制，五要素记录见 `22-bookkeeper-rejection-task1.md` §5：

- **限制 A**：`single_leg_exposure` 判据为「现货成交量 > 0 且合约成交量 == 0」，漏报聚合后的部分失衡（现货 2.0 / 合约 1.0 判为无敞口）；规格原要求消费后端 `pair_outcome` / `leg_exposure`。
- **限制 B**：`spot_balance` 与 `drift` 读 `balances_spot`（经典现货账户），而对冲现货腿买入统一账户；`drift` 因而恒为 `False`，P2 的手工减仓检测静默失效。

**你若独立发现这两条，请记为观察并引用该节路径，不要返工。** 返工额度须留给**本节之外**尚未被发现的问题。本节之外的缺陷照常按 §8 处置。

Human 的接受不改变事实：这两处**确实是缺陷**。若你认为其「可能影响」被低估（例如实际后果比记录所述更严重），请直接说明 —— 那是新信息，值得 Human 重新权衡。

## Inputs

| 文件 | 读什么 |
|---|---|
| 本 dispatch | 全部 |
| `git diff c1cc10e..969c455` | **受审差异** |
| `22-bookkeeper-rejection-task1.md` | **§0（已核验通过项）与 §5（已接受限制）必读** |
| `12-development-breakdown.md` | `## Task 1` 全节 —— 规格 |
| `10-design.md` | P1 / N1-N5 / P2 / P7 |
| `hedge-merged-positions-v1.dispatch.md` | 任务边界与四个具名项 N-1~N-4 |
| `21-merged-positions-implementation.md` | 实现者自述 |
| `agents/skills/code-reviewer.md` | 全部 |

字节数请自行 `wc -c`。禁止整文件读三个后端主文件（合计约 27 万字节），按差异定位。

## Acceptance Checks —— 逐条给出结论

- **A1｜规格符合性**：交付是否满足 `12-development-breakdown.md` Task 1 的验收标准 1-10（限制 A、B 涉及的部分除外，那两条已由 Human 接受）。
- **A2｜`merge_positions` 的正确性**：UM 骨架与任务桶的匹配逻辑、base-asset 归一、1000x 六币的处理、无匹配时的 `no_um` 行追加。特别注意**边界**：空输入、`private_account` 为 `None`、`verified:false`、UM 有仓但桶为 `None`、同一 symbol 多方向。
- **A3｜D15 的正确性**：两条查询去 `WHERE` 后，`includes_deleted_task` 是否在**两条**路径都正确置位；混合桶的加权均价是否仍数学正确；有无因纳入已删任务而产生的重复计数或符号错误。
- **A4｜N2 降级契约**：`SnapshotNotReady` 与 `verified:false` 两条路径是否都不 503；`account_meta` 是否如实反映原因；本地行是否完整返回。有无第三条未覆盖的失败路径（例如 `get_snapshot()` 抛出非 `SnapshotNotReady` 的异常）。
- **A5｜接口契约**：`_POSITION_KEYS` 精确集断言是否与实际返回一致；前端渲染器是否与新形状完全对齐；`self-check.js` 的 mock 是否已同步（N-4）；有无遗漏的消费者。
- **A6｜测试质量**：`test_positions_merge.py` 的 14 个用例是否覆盖了真正的风险面，还是只覆盖了 happy path；被修改的既有测试（`test_hedge_store.py` 的 N-1、`test_hedge_api.py` 的键集）是否保留了原回归意图；有无被削弱的断言。
- **A7｜边界与红线**：是否越出 Allowed Files；`private_client.py` / 白名单 / `scheduler.py` / `service.py` / 51169 文案区 / 暂停原因集是否未被触碰；是否误入 Task 2/3 的范围（暂停删除逻辑、worker 退避、重查间隔）。
- **A8｜接缝**：handler 装配是否真的没把 `SnapshotService` 注入 `HedgeOpenTaskService`；`merge_positions` 是否真的无 I/O 与服务引用；有无新增交易所请求。
- **A9｜前端**：合并表是否确实取代了旧的 UM 子表与 `renderHedgePositionsSection`（无重复表）；占位零三分类是否真的区分了「真值 / 暂无 / 拿不到」而非仍渲染 `0.00`；51169 文案是否逐字。
- **A10｜你认为最危险的三处**：不限于上列检查项。

## 输出要求

按 `AGENTS.md` §7 返回 `[TASK_RESULT v2]`，并含三行闭合字段：

```text
评审结论: ACCEPT（接受） | REWORK（返工）
问题记录: <path | none>
修复要求: <path | none>
```

- **`问题记录` 与 `修复要求` 填 `inline-full-text`，并把发现清单的完整正文放在同一次输出的正文里。** 本仓上一 stage 七轮评审中有四轮的正文没跟着回执转交，两轮不得不回头补要。你是只读会话、不落盘文件，正文就是唯一载体。
- 每条 `REWORK` 发现按 §8 标注范围三分类：`in-range` / `pre-existing-independent` / `pre-existing-release-critical`。`pre-existing-*` 须附早于 `base_sha` 的引入提交引用（`git blame` 或 `git log -L`），无此证据者只记为观察。
- **`本地北京时间` 须由 `date '+%Y-%m-%d %H:%M:%S CST'` 实际产生**，不要手写估计值。
- 发现全为范围外时返回 `ACCEPT`，`问题记录` 照常填路径，`修复要求` 指向后续项或 `none`。

## Stop

- 只读：不得修改任何文件（含 `status.json`）、不得写代码、不得提交、不得合并、不得推送。
- 不得移动 `HEAD`，只评审写死的 `base_sha..delivery_sha`。
- 不得启动、调用、转交或冒充任何其他模型会话（§3 #2）。
- `ACCEPT` 不构成实现、验收、合并、部署或实盘授权；结论交回 Human，由 Bookkeeper 同步。
- 若发现本 dispatch 与受审代码矛盾、或评审对象与 `status.json` 不符：停止并报告。

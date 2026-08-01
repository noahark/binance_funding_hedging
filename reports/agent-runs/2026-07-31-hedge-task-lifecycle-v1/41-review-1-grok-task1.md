# 41-review-1-grok-task1 —— review-1 结果（grok，只读）

- task_id: `review-1-grok-task1`
- 评审者：`grok`（provider `xai`），对实现者 `claude_glm`（`zhipu_glm`）provider 隔离成立；Kimi 额度不可用时的 Human 批准备选
- 评审区间：`c1cc10e8fb491f83fe4c09f565b34e06c2de0a50..969c4557a293a257b3c81c26c5a9c224f6b7f037`
- **评审结论：`REWORK`**；`问题记录: inline-full-text`；`修复要求: inline-full-text`（正文随回执同交，已逐字留档于 §3）
- 两条 `in-range` 发现（F1 阻塞、F2 应修），六条观察
- 按 `AGENTS.md` §8，`rework_count` 由 `0` 递增为 `1`（上限 3）

## 1. Bookkeeper 对本评审的核验

回执格式合规（三行闭合字段齐全，`REWORK` 附可执行修复要求），构成有效返工判定。**两条发现均经独立复验成立**，不采信转述：

| 发现 | Bookkeeper 复验 | 结论 |
|---|---|---|
| **F1** `renderPrivatePanel` 在 `pa.verified !== true` 时早退 | `index.html:2746-2757`：进入分支后 `innerHTML = 「私有账户未读取」` 并 `return`，**不再调用合并表渲染** | 成立 |
| **F1** `pa` 缺失时面板隐藏 | `index.html:2739-2742`：`display='none'; return` | 成立 |
| **F1** 重绘条件锁死 verified | `index.html:3809-3811`：`if (... private_account.verified === true)` 才重绘 | 成立 |
| **F1** N2 横幅代码存在但不可达 | `index.html:4467-4470` 确有 `account.verified === false` 的横幅分支，位于合并表渲染函数内 —— 而该函数在降级路径永不被调用 | 成立 |
| **F2** 有 UM 但 upnl 缺失时画 0 | `index.html:4495-4497`：`hasUm` 只看 `um_position_amt`；为真则 `formatHedgeSigned(p.price_pnl)`，而后端在 upnl 不可解析时保留占位 `"0"` | 成立 |
| F1 范围归类依据 | `git merge-base --is-ancestor 6c1e992 c1cc10e` 为真；`6c1e992`（2026-07-06）确为 `base_sha` 祖先 | 归类合理 |

### 1.1 Bookkeeper 追加：O4 应升入修复范围（非观察）

评审将 O4 列为观察。Bookkeeper 复验后认为**它掏空了一条验收标准，应作为必修项**：

- `self-check.js:1334` 断言 `privateBody.includes('UM 持仓')`，错误信息为「私有面板未渲染 UM 持仓」—— 其本意是验证个人账户面板中存在**独立的 UM 持仓子表**。
- 该子表已被本次交付删除（合并入新表，验收标准 10 要求如此）。
- 断言之所以仍绿，是因为新合并表标题含「（UM 持仓为骨架）」（`index.html:4529`）恰好命中子串。
- 即：**断言仍在运行，但已不再验证它原本要验证的东西**。

这使 Task 1 验收标准 9「`self-check.js` 未放宽既有断言」在字面上成立、在实质上落空。修复轮须一并处理。

### 1.2 F1 的严重性说明（供 Human 知情）

F1 使本任务的核心目的在降级路径下落空：后端已按 N2 正确返回本地记账行（含 D15 保留的已删任务成本基），**前端却把它丢弃**。即账户快照未就绪或私有通道关闭时，用户看不到任何本地持仓与成本 —— 而这正是 ① 要解决的资金可见性问题。

与已接受限制 A/B 不同：A/B 是"标记不准"，F1 是"整张表不显示"，且不涉及任何待定的设计取舍，修法明确。

## 2. 修复范围裁定

进入 `fix-merged-positions-n2-ui-v1`：

### Human 的优先级裁定（2026-08-01）

Human 指示：**优先打通「账户未就绪仍显示本地合并表 + 未就绪提示」（F1），其次修「没盈亏别画 0」（F2）**；其余属"细节"，先把界面呈现出来，看到实物后再按偏好调整。

据此裁定进入 `fix-merged-positions-n2-ui-v1` 的范围：

| # | 项 | 来源 | 本轮 |
|---|---|---|---|
| R1 | F1：合并表与 N2 横幅在 `verified !== true` / `pa` 缺失路径下必须可见 | 评审 F1（🔴 阻塞） | **必须 · 优先** |
| R2 | F2：有 UM 但 `unrealized_profit` 缺失时不得画 `0`，须「暂无」/`—`，且真值 0 与缺失可区分 | 评审 F2（🟡 应修） | **必须** |
| R3 | O4：修复被掏空的 `self-check.js:1334` 断言 | Bookkeeper §1.1 | **必须**（两行改动；不修则验收 9「未放宽既有断言」实质落空） |
| R4 | 补渲染断言证明 R1/R2 真的生效：`verified=false` 降级下本地行可见 + 横幅出现；缺 upnl 不画 0 | 评审 R1.3 / 设计 N5 | **必须**（否则无法验证 R1/R2，只能再次采信自述） |
| ~~R5~~ | 补「活 + 已删同桶」加权均价单测；HTTP 级 N2 形状断言 | 评审 O3 | **推后**（Human：非关键） |
| ~~R6~~ | 强平价 sentinel `"0"` 加 title；修正 `umCell` 误导注释 | 评审 O5 | **推后**（属展示细节，Human 将按偏好统一调整） |

**不得写入修复范围**：已接受限制 A、B（`22-bookkeeper-rejection-task1.md` §5）。评审已正确将其记为观察未据以返工。

R5、R6 与 O2（`get_snapshot` 非 `SnapshotNotReady` 异常未降级）、O6（双源累加双计，非本 diff 引入）转为本 stage 的后续观察项，合并前由 Bookkeeper 汇总，Human 届时决定是否处理。

## 3. 评审原文（逐字保留，未经改写）

> 以下为 `grok` 只读会话返回的完整评审正文、问题记录、修复要求与 `[TASK_RESULT v2]`，按 `agents/roles.md` Shared Rules「Preserve raw evidence」逐字留档。

```text
Review-1：review-1-grok-task1

• 区间：c1cc10e..969c455（未移动 HEAD）
• 作者 / 评审：claude_glm（zhipu）/ grok（xai）—— provider 隔离成立
• 已知限制 A/B：已读 22-bookkeeper-rejection-task1.md §5，不据以返工
• 总评：后端合并骨架、D15、纯度、边界、接口键集大体正确；N2 在 UI 层未接通，验收 7 / 设计 N2·N4·N5 不成立 → REWORK

───

A1｜规格符合性

验收 1 后端合并六场景 —— pass（test_positions_merge.py 覆盖 normal/no_task/no_um/single_leg/missing/empty 主路径）
验收 2 D15 两条查询 + 标记 —— pass
验收 3 N2 接口不 503 —— pass（handler 层）
验收 4 N1 形状 + 前端重写 —— pass（有条件：见 A5）
验收 5 1000x 诚实不对齐 —— pass
验收 6 P7 占位零三分类 —— partial fail（资金费/借币/净盈亏 OK；unrealized_profit=null 时可能画成 0）
验收 7 三类标记齐全 —— fail（N2 账户未就绪标记在真实降级路径不可达）
验收 8 51169 逐字 —— pass（文案区未动；fake 预览仍含冻结全文）
验收 9 self-check EXIT=0 —— pass（128；mock 仅加 account，未放宽）
验收 10 单一合并表 —— pass（UM 子表 + 旧 section 已替换）

限制 A/B 按 Human 接受排除。因 A7 与 A6 局部，A1 不能记全 pass。

───

A2｜merge_positions 正确性

pass（逻辑主体）

• UM 骨架优先，(symbol, direction) 与桶匹配；forward↔SHORT / reverse↔LONG 正确。
• _merge_base_asset 只剥 USDT，1000x 不剥前缀；1000PEPE≠PEPE 测过。
• 无匹配桶 → no_um 追加；匹配不重复。
• 边界：空输入、private_account=None、verified:false（忽略污染 UM）、同 symbol多方向、侧别错配 → 两行，均合理。
• 限制 A：single_leg_exposure 仅 spot>0 && perp==0，部分失衡漏报——观察，见 §5。

───

A3｜D15 正确性

pass

• fill_rows / leg_rows 均去 WHERE != deleted，SELECT 带 t.status。
• 两路径均在有贡献时置 includes_deleted。
• 均价仍为 Σnotional/Σqty，混合桶数学正确；无符号翻转。
• 缺口：无「活+已删同桶」加权均价专项单测（代码可读正确，属测试薄）。

───

A4｜N2 降级契约

后端 pass / 前端 fail

• SnapshotNotReady → snapshot=None → 本地行 + account.verified=false, error=snapshot_not_ready，HTTP 200。
• verified:false → 账户列置空，透传 error/checked_at。
• 第三条：get_snapshot() live 路径实质上只抛 SnapshotNotReady；其它异常未捕获会 500（offline 校验失败理论路径）——观察，非主风险。
• F1：UI 在 private_account.verified!==true 或无 pa 时早退 / 隐藏面板，不渲染合并表与 N2 横幅；loadHedgePositions 也仅在 verified===true 时重绘。后端 N2 数据进了 state，真实降级窗口用户看不见。

───

A5｜接口契约

pass（后端）/ 前端对齐有条件 pass

• _POSITION_KEYS 精确集 26 键与合并行一致；test_positions_shape_after_fill 仍 set==。
• 渲染器字段与新形状对齐；N-4 mock 三处已带 account。
• 消费者：前端、test_hedge_api、get_positions 间接消费者（N-3 无需改）——未见遗漏破坏点。
• 缺口：HTTP 层未断言响应含 account；self-check 未覆盖 verified:false 渲染（设计 N5 要求）。

───

A6｜测试质量

partial pass

• 14 例覆盖主风险面，不只 happy path；降级两路径、1000x、漂移方向、JSON 可序列化有测。
• N-1 改写非删除，意图保留；_POSITION_KEYS 收紧非放宽。
• 弱项：无 HTTP 级 N2；无混合 D15 均价；无部分失衡；self-check 仍靠「UM 持仓」子串误过（靠「UM 持仓为骨架」）；P7/N2 渲染断言未加。
• 限制 B 下 drift 单测在错误资金池上"测绿"——与已知限制一致，观察。

───

A7｜边界与红线

pass

• 仅授权文件；service.py/scheduler.py/private_client/白名单/51169/暂停原因集未触。
• 未入 Task 2/3（删除、退避、interval）。

───

A8｜接缝

pass

• 合并在 handler；无 SnapshotService 注入 HedgeOpenTaskService。
• merge_positions 纯函数，无 I/O/服务引用。
• get_snapshot() 零上游读；无新增交易所请求。

───

A9｜前端

partial pass

• 单一合并表取代 UM 子表 + renderHedgePositionsSection，无重复表。
• P7：资金费/借币/净盈亏 →「暂无」；无 UM 时未实现盈亏 →「暂无」。
• F2：有 UM 且 unrealized_profit is null 时 price_pnl 留 "0"，前端 hasUm 为真 → 画 0（非真值）。
• 强平价 "0"：设计要求显示 0 且 title 说明；实现显示 0、无 title；注释写「→ —」与代码/设计不一致——nit/观察。
• 51169：fake 区逐字，未换「保证金不足」话术。
• N2 横幅代码存在但真实路径不可达（F1）。

───

A10｜最危险的三处

1. 🔴 N2 UI 未接通（F1）：账户冷启动 / verified:false 时本地成本基与 D15 行不可见——与本任务资金可见性目标直接冲突。
2. 已知限制 A/B（Human 已接受）：单腿漏报部分失衡；spot_balance/drift 错池致 drift 静默失效。须写入后续 PROJECT_STATE，不得当本轮返工。若低估：Task 2 自动删除后任务卡观察点消失，限制 A 权重上升（§5.1 已写）。
3. 🟡 未实现盈亏缺测时画 0（F2）+ 测试对 N2/P7 渲染覆盖不足：资金列"错误的安心"。

───

问题记录（inline-full-text）

# review-1-grok-task1 问题记录
区间: c1cc10e..969c455
评审: grok (xai) | 作者: claude_glm (zhipu)
结论: REWORK

## F1 [in-range][blocker] N2 前端展示路径未接通，验收 7 / 设计 N2·N4·N5 不成立

事实:
1. 后端 `_hedge_open_positions` 正确实现 N2：捕获 SnapshotNotReady；merge_positions 在
   private_account 为 None / verified=false 时仍返回本地记账行 + account_meta。
2. 前端唯一渲染点是 renderPrivatePanel → renderHedgeMergedPositions。
3. renderPrivatePanel 在 pa.verified !== true 时整页替换为「私有账户未读取」并 return，
   不调用 renderHedgeMergedPositions（index.html ~2746-2756）。
4. pa 缺失时面板 display:none（~2739-2742），合并表同样不渲染。
5. loadHedgePositions 写入 hedgeAccountMeta 后，仅当
   private_account.verified === true 才 renderPrivatePanel（~3810-3814）。
6. 因此 N2 横幅（account.verified===false）在真实降级场景不可达；
   冷启动 / 私有通道关闭时，用户看不到本地成本基与 D15 已删任务行。

设计依据:
- 10-design.md N2：「仍返回本地记账行」+「前端按 account.verified 把账户列渲染为未就绪」
- N4/N5：合并表含 N2 标记；self-check 应验 account.verified=false 渲染
- 验收标准 7：N2 账户未就绪列标记

范围: in-range（本交付新增 hedgeAccountMeta / N2 横幅 / 合并表，却未把表从
「仅 verified 私有面板」解耦；门闩本身引入于 6c1e992，早于 base_sha，但是
本需求交付未处理该阻塞接缝。）

## F2 [in-range][should-fix] 有 UM 但 unrealized_profit 缺失时未实现盈亏被画成 0

事实:
- domain._merge_build_row：仅当 _merge_num(upnl) is not None 才覆盖 price_pnl；
  否则 bucket 占位 "0" 保留，同时 unrealized_profit=None。
- 前端：hasUm 仅看 um_position_amt；为真则 formatHedgeSigned(price_pnl) → 显示 0。
- test_merge_missing_sentinel_values 把 price_pnl=="0" 锁成契约，强化了错误安心。

设计: P7「未实现盈亏取 unrealized_profit 真值」；缺真值应「暂无」/—，不得冒充 0。

范围: in-range（本交付 merge + 渲染器引入）。

## 观察（不构成 REWORK）

O1. 限制 A/B：见 22-bookkeeper-rejection-task1.md §5；Human 已接受。
O2. get_snapshot 非 SnapshotNotReady 异常未降级（live 实际仅后者）。
O3. 无「活+已删同桶」加权均价单测；无 HTTP 级 N2 测试。
O4. self-check 用例 23 仍断言「UM 持仓」子串，被副标题「UM 持仓为骨架」误满足。
O5. 强平价 sentinel "0" 缺 title「该仓当前无强平价」（P7）；注释与设计/代码不一致。
O6. fill_rows+leg_rows 双源累加若同任务双写会双计——既有行为，非本 diff 引入。

修复要求（inline-full-text）

# review-1-grok-task1 修复要求

## R1（对应 F1，必须）
1. 当 GET /api/hedge-open-positions 已返回本地 positions 时，合并表必须可渲染，
   不得被 snapshot.private_account.verified 门闩挡住。
   建议最小改动之一：
   a) verified!==true 分支仍渲染 renderHedgeMergedPositions()（资产卡可保持未读取占位）；或
   b) 将合并表移出「仅 verified 成功体」，作为私有面板在 pa 缺失/未验证时的可见区块；
   并修正 loadHedgePositions 的重绘条件，使 hedgeAccountMeta.verified===false 时也能刷新表。
2. 真实路径验证：SnapshotNotReady 与 verified:false 下 UI 可见本地行 + N2 横幅/列未就绪。
3. self-check 按设计 N5 增加渲染断言：
   - account.verified=false → 出现未就绪文案/横幅，本地 coin 行仍在；
   - includes_deleted_task 标记文案「含已删除任务记录，均价为混合值」；
   - 资金费/借币/净盈亏占位「暂无」（非 0.00）。
4. 不得回退 §0 已通过项（1126 / 128 / 禁改区 / D15 / 精确键集 / merge 纯度）。

## R2（对应 F2，必须）
1. 有 UM 且 unrealized_profit 不可解析时：price_pnl/展示不得用占位 0；
   应 null 或等价，前端画「暂无」或 —。
2. 真值 0 与缺失必须可区分（例如看 unrealized_profit is not None）。
3. 更新 test_merge_missing_sentinel_values 与前端/自检，禁止再锁「缺失→0」。

## R3（建议，非阻塞本轮若 R1/R2 已满）
- 补混合 D15 桶均价单测；HTTP 级 N2 200+account 形状断言。
- 强平价 "0" 按 P7 加 title；修正 umCell 误导注释。
- 限制 A/B 合并 main 前写入 PROJECT_STATE.md（Bookkeeper 待办，非实现者必改代码）。

───

[TASK_RESULT v2]
任务 ID: review-1-grok-task1
执行结果: completed（完成）
结果摘要: review-1 REWORK：后端合并/D15/纯度/边界大体成立；N2 UI 被私有面板 verified 门闩挡住致本地行不可见(F1)；有UM缺upnl时盈亏画0(F2)。限制A/B不返工。
产物: [inline-full-text 问题记录与修复要求见正文]
检查结果: [A1规格:fail(N2标记/P7局部); A2 merge:pass; A3 D15:pass; A4 N2后端pass/前端fail; A5契约:pass; A6测试:partial; A7边界:pass; A8接缝:pass]
阻塞项: [F1 N2前端路径未接通; F2 缺upnl时未实现盈亏画0]
评审结论: REWORK（返工）
问题记录: inline-full-text
修复要求: inline-full-text
本地北京时间: 2026-08-01 12:30:30 CST
下一步模型: opus5（Bookkeeper；Human 将本回执交其同步 status）
下一步任务: Bookkeeper 核验本 REWORK 回执与 inline 正文，按 §8 递增 rework_count 并签发 F1/F2 最小修复 dispatch（限制 A/B 不得写入修复范围）
```

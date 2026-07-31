# 40-plan-review-deepseek-v2 —— 计划评审结果（deepseek，只读）

- task_id: `plan-review-deepseek-v2`
- 评审者：`deepseek`（provider `deepseek`），跨 provider 隔离对方案作者 `claude_glm`（`zhipu_glm`）成立
- 评审区间：`afa3d5228e64ed2399e3d24b6971245e20950d9f..c1cc10e8fb491f83fe4c09f565b34e06c2de0a50`
- **评审结论：`ACCEPT`**；`问题记录: inline-full-text`；`修复要求: none`
- 无 `in-range` 发现；无 `pre-existing-*` 发现；三条观察（非缺陷）
- 按 `AGENTS.md` §8，计划评审 verdict 返回 Planner，**不触碰 `rework_count`**（仍为 `0`）

## 1. Bookkeeper 对本评审的核验

评审格式合规（`评审结论` / `问题记录` / `修复要求` 三行齐全，`ACCEPT` 明确且格式良好，正文随回执同交），按 `AGENTS.md` §3 #7 与 §7 构成有效接受。

抽验其结论（不采信转述）：

| 评审者主张 | Bookkeeper 复验 | 结果 |
|---|---|---|
| F-A 两服务同 `_Handler` | `server.py:632-642` | 成立 |
| F-B live 零上游纯读；offline 是部署开关非 live 回退路径 | `snapshot_service.py:245`（`if self.client.offline`）+ `binance_public.py:62-69`（构造参数） | 成立 |
| F-C `SnapshotNotReady` 触发条件 | `snapshot_service.py:254-257` | 成立 |
| F-D 降级形状 | `snapshot.py:1097-1116` | 成立 |
| `tick()` live 直接 `return False` | `service.py:1516-1517` | 成立 |
| `/api/hedge-open-positions` 消费者清单 | `index.html:3842`、`self-check.js:708-709`、`test_hedge_api.py:606,633`、`test_hedge_review2_regressions.py:477` | 成立 |
| **`test_hedge_store.py:279-285` 断言了 D15 要反转的旧行为** | 原文 `assert store.aggregate_positions() == []`（删卡后聚合为空） | **成立，且为本次评审最有价值的发现** |

### 1.1 Bookkeeper 补充的两点（评审未覆盖）

**(a) `interval_us` 消费者审计不完整（结论不受影响）。** 评审列举了三处（`service.py:178` 显示、`service.py:1079` worker 节流、`scheduler.py` tick 节奏）并称「无遗漏消费者」。穷举后实为五处，未列出的两处是：

- `service.py:461`：把 `get_interval_us` 作为回调传给 `HedgeOpenScheduler`；
- `scheduler.py:51-56`：`slice_seconds = max(min(interval_us / 1_000_000 / 2.0, 0.25), 0.005)` —— 调度线程的**唤醒切片**由 `interval_us` 推导。

影响评估：`interval_us` 由 1s 降到 100ms 后，该切片由 0.25s 变为 0.05s，即调度线程唤醒频率上升约 5 倍（1s 时受 0.25 上限压制，故非 10 倍）；其自带 5ms 下限，不会退化为忙轮询。因 live 模式 `tick()` 立即返回，**不产生任何交易所请求，也不改变下单节奏** —— 评审关于 R2 的结论（下调只缩短腿重查延迟）**不受影响**，仅代价栏应补一句「调度线程 CPU 唤醒频率上升」。

处置：作为 Task 3（`hedge-leg-requery-cadence-v1`）实现 dispatch 的具名输入，不要求方案返修（不改变任何裁定）。

**(b) 评审的 `本地北京时间` 存疑。** 回执写 `2026-07-31 20:30:00 CST`，早于其评审对象 Planner 修订回执的 `23:11:34 CST`，且为整点整分整秒，不似 `date '+%Y-%m-%d %H:%M:%S CST'` 输出。属证据卫生问题，不影响 verdict 有效性；后续 review dispatch 保留该字段要求，并在 packet 中点明须由 `date` 命令产生。

## 2. 待 Human 裁定：R1

评审对 R1 的结论是「技术论证成立，但最终取舍权在 Human，不构成技术 `REWORK`」。即：`rate_limited` 是否从「六种自动删除」中剥离改为退避，仍需 Human 拍板。Task 2 与 Task 3 依赖该裁定；**Task 1 不依赖**，可先行实现。

## 3. 评审原文（逐字保留，未经改写）

> 以下为 `deepseek` 只读会话返回的完整评审正文与 `[TASK_RESULT v2]`，按 `agents/roles.md` Shared Rules「Preserve raw evidence」逐字留档。

```text
计划评审报告 —— plan-review-deepseek-v2

评审结论

评审结论: ACCEPT

问题记录: inline-full-text（见下方完整发现清单）

修复要求: none（发现全为范围外或需 Human 裁定，不阻塞交付）

---
逐条验收检查

R0｜方案转向所依据的四条事实

逐一独立核实结论：

- F-A ✅ 成立。server.py:632-642 build_server 确实将 SnapshotService（_Handler.service）与 HedgeOpenTaskService（_Handler.hedge_open_service）注入同一个 _Handler 类。_hedge_open_positions（:607-608）通过 self.service 和 self.hedge_open_service 同时够到两者。与方案描述一致。
- F-B ✅ 成立。services/snapshot_service.py:237-257 get_snapshot() 的 live 分支为 state = self._published_state; return state.snapshot，docstring 原文 live: zero-upstream pure read of the published state。离线分支（:245-252）仅在 self.client.offline 为 True 时进入——这是部署模式开关，不是 live 部署下的实际路径。零新增交易所请求成立。
- F-C ✅ 成立。get_snapshot() 在 self._published_state is None 时（首次发布前）raise SnapshotNotReady("no published state yet")。方案描述与源码一致。
- F-D ✅ 成立。domain/snapshot.py:1097-1116 降级形状：verified: false、balances_unified/balances_spot/um_positions 三数组空、金额字段 null、error 带原因（如 private_channel_disabled）。checked_at 也在同块为 null。与方案描述一致。

四条全部成立。方案从「前端合并」翻转为「后端合并」所依据的事实基础牢靠。

R1｜ADR-002 rate_limited 剥离

技术判断：方案的论证成立。rate_limited（429）与其余五种暂停原因的本质差异是真实存在的：

- 五种终态原因（consecutive_submission_failure / insufficient_balance / insufficient_margin / insufficient_available_qty / collateral_cap_full）在不改变参数的前提下不会自愈——删之合理。
- rate_limited 是瞬态背压信号，限频解除后自恢复。将其与终态原因同列删除，等于把暂时堵车判成永久封路。

方案指出的 ③ + 字面六删的风险路径也是真实的：③ 将腿重查从 1s 降到 ~100ms（约 10x），两处 worker 429 站点（:1152-1160、:1176-1180）若触发即删卡，批量删卡将常态化，直接摧毁 ①（资金可见性）的全部意义。

回退方案（若 Human 坚持字面六删则不做 ③）可行：③ 本身不解决任何阻塞性问题，只是改善重查延迟的体验优化。

这是 Human 的产品决定。 技术论证支持「五种删 + 一种退避」的方案，但最终取舍权在 Human。不构成技术 REWORK。

R2｜ADR-003 推翻既有 follow-up

事实核实：tick() 在 live 模式确实是 SAFE NO-OP。service.py:1516-1517：
if self._live_dispatch_capable():
    return False
live 模式直接返回 False，不做任何扫描/派发/对账。

interval_us 的消费者审计：
- service.py:1079：ev.wait(interval_s) —— worker 腿重查节流，仅在存在非终态腿时才等待
- service.py:178：settings_to_doc 的显示值 —— 纯展示
- scheduler.py：tick 节奏 —— live 模式下 tick 是 NO-OP

无遗漏消费者。 下调 interval_us 到 100ms 只缩短腿重查延迟，不抬高下单频率（下单节奏由 A-9 保证：一对腿终态才进下一对）。

推论完整：PROJECT_STATE.md 的旧建议「拆分两间隔」在 live 模式下无对应物——tick 是空操作，"dispatch interval" 在 live 无意义。拆分只对 DRY-RUN 有意义（record-only、不下单），10x 加速无害。推翻成立。

R3｜后端合并的新增风险

接口契约（N1）：逐个审计 GET /api/hedge-open-positions 的消费者：
- frontend/index.html:3842-3846：唯一真实消费者（注释「唯一数据源」）
- frontend/self-check.js:708-709：mock 拦截
- backend/tests/test_hedge_api.py:606,633：API 测试
- backend/tests/test_hedge_review2_regressions.py:477：通过 svc.get_positions() 间接消费

无遗漏消费者。N1「就地改、前端同步重写」成立。

降级契约（N2）：漏洞审计：
- 部分可用场景（如 verified:true 但数据陈旧）：方案通过 checked_at 时间戳暴露陈旧度，前端可据此渲染。有缓解，非漏洞。
- verified:true 但实际数据过期：这是 eventual consistency 的固有限制，方案已明确接受（§7.1「接受 eventual consistency」）。属已知取舍，非未覆盖漏洞。
- 降级路径覆盖：SnapshotNotReady（首次发布前）→ 返回本地行 + account.verified:false；verified:false（如 private_channel_disabled）→ 同上。两路径均覆盖。

snapshot 耦合：确实新增了一个依赖——持仓接口现在依赖 SnapshotService 的发布时序。方案对时序问题的覆盖：
- checked_at 暴露陈旧度
- verified 标记可用性
- 接受 eventual consistency

三项风险均被识别并给出缓解措施。充分。

R4｜D15 的语义变更

重点审计——资金数字含义变化。

去掉两条 WHERE t.status != DELETED 后，已删除任务的已成交腿开始计入 aggregate_positions。方案通过 includes_deleted_task 桶级标记告知前端。

includes_deleted_task 是否足以防止误读？

成立，但有一个值得注意的边界情况：当同一 (coin, direction) 桶同时有活任务和已删任务的腿时，spot_avg/perp_avg 是两者的混合加权均价，includes_deleted_task 标记为 true。用户能看到「含已删除任务记录」的提示，但无法区分混合均价中活任务与已删任务各自贡献了多少。

这是否构成误读？取决于视角：
- 如果目标是「保留成本基不消失」：混合均价做到了——被删任务的成交信息仍然影响了该行的均价。
- 如果目标是「精确区分活/已删成本」：仅靠一个布尔标记不够。

方案 §5 已明确前端加标记「含已删除任务记录」——这告知用户该行数据混合了已删任务，提醒其不要当作纯活任务成本。对于「资金可见性」的目标（让用户看到被删任务的成本基没有凭空消失），这个级别的标记是足够的。精确拆分活/已删子行会增加复杂度且实际收益不大——用户已知道该任务被删，行标记已提供足够警示。

均价口径正确性：混合均价在数学上是正确的——Σ名义额/Σ数量 对所有贡献行（含已删）加权平均。不存在「口径算错」的问题，只是「来源混合」的问题。标记解决了后者。

未考虑的副作用审计：
- 测试 test_aggregate_positions_excludes_deleted_tasks（test_hedge_store.py:279-285）当前断言已删任务的聚合结果为空——Task 1 需要更新此测试。方案在 Task 1 验收标准中提到了 aggregate_positions 回归测试。已覆盖。
- test_hedge_review2_regressions.py:477 通过 get_positions 间接调用——也会受影响。方案在 Task 1 文件边界中包含测试更新。已覆盖。

结论：includes_deleted_task 标记足以防止误读。混合均价是正确且预期内的行为。

R5｜交付拆分与串行约束

串行推导验证：

任务对 ① ↔ ②：重叠文件 store.py（① 改 aggregate_positions 两条 WHERE / ② 改 resolve_leg_from_query COALESCE + pause_task + skip_counters）、service.py（① 改 get_positions + 合并装配 / ② 改再武装守门 + worker 退避 + 删除转移）→ 不可并行
任务对 ② ↔ ③：重叠文件 service.py（② 改 worker 429 站点退避 / ③ 改 worker 节流抖动 + 退避参数 + 显示修复）→ 不可并行

严格串行 ①→②→③ 推导正确。 rebase 链可操作：② 基于 ① 的 delivery_sha，③ 基于 ② 的 delivery_sha。

文件边界清晰：每个任务列出了 Allowed Files 和不得改动的文件清单。验收标准可判定（每个标准有具体的可执行验证方式）。

C1｜事实核实

抽查关键事实：
- §0 事实 2-4（六种暂停原因 / A-1 四站）：均属实（domain.py:127-151、store.py:690/740/979、service.py:1172）
- §0 事实 5（死锁路径）：属实。post_start（:616-630）无配额检查即调 set_task_status(RUNNING) + ensure_worker，而 worker 在 :1172 因 scheduled >= target_n 退出
- §0 事实 8（tick SAFE NO-OP）：属实（:1516 直接 return False）
- §0 事实 9（两处 worker 429 站点）：属实（:1152-1160、:1176-1180）
- §0 事实 14（aggregate_positions WHERE）：属实（:1950/:1960 均有 WHERE t.status != ?，参数 D.STATUS_DELETED）
- §0 事实 15（private_client 白名单冻结）：hedge_preflight_provider.py 注释确实说明了白名单限制

无虚假引用发现。

C2｜红线

1 51169 文案逐字冻结 ✅ 遵守 —— Task 2 自动删除保留 pause_reason+pause_reason_zh；domain.py:1315-1324 逐字不动
2 不得放宽 A-1 ✅ 遵守 —— P4 守门用同谓词 scheduled_attempt_count，收紧非放宽；不切 accepted 口径
3 不得新增状态枚举 ✅ 遵守 —— 复用 DELETED（自动删除）+ DONE（配额收口）
4 不得用账户级冒充每币 ✅ 遵守 —— P7 明确每币列用 um_positions 逐币字段；uniMMR 放表外摘要
5 不得自动交易 ✅ 遵守 —— Task 1 纯展示；Task 2 状态转移非交易；D7 对不上只展示
6 不得扩大范围/无证据抽象 ✅ 遵守 —— §3 非目标 11 条显式列出；§6 证据表每项有已观察问题对应
7 不得重新论证 P1 选型 ✅ 遵守 —— 方案声明 D14 是 Human 已定决策，不重新比较前后端优劣；无兼容层设计

七条红线全部守住。 独立判断成立。

C3｜A-1 家族

四站逐站评估独立复核：
store.py:690（scheduled < target_n）不受影响：P4 收口到 done 的任务非 running，本就被排除 ✅ 正确
store.py:740（>= target_n → None）不受影响：保留作预留层双保险 ✅ 正确
store.py:979（>= target_n 且 running → done）不受影响：R2-F1 触发条件不变 ✅ 正确
service.py:1172（>= target_n → EXIT）不受影响：保留作双保险 ✅ 正确
新增 P4（>= target_n → done）新增同谓词守门 ✅ 正确

清单外三处的不适用理由：
domain.py:1087（accepted_count >= target_n）受理口径 ≠ 计划次数口径 ✅ 正确
service.py:687（success_count >= target_n）成功口径，DRY-RUN 同步循环专用 ✅ 正确
store.py:811（计数器 +1）非判阈，是计数自增 ✅ 正确

逐站评估全部成立。清单外三处理由正确。

C4｜修订完整性

受影响部分核查：
- P1 重裁为后端合并 + N1-N5：✅ 已修订
- ADR-001 重写 + 引用更正（index.html:2106 → :2198）：✅ 已修订
- 非目标 #7 删除 + D15 写入正文：✅ 已修订
- Task 1 重估（文件边界/验收/风险/测试）：✅ 已修订
- §5 与 fake 一致性更新：✅ 已修订（列出五项差异）
- §6 证据表更新：✅ 已修订（「前端合并 join」行已替换为后端合并函数等）
- §7 新增风险（§7.1）：✅ 已新增

不应改动部分核查：
- P2-P4/P6-P8 裁定保持原判：✅ 未改
- Task 2/Task 3 原样保留：✅ 未改（修订说明写明「不受 D14/D15 影响，原样保留」）
- 六条红线确认：✅ 保留

发现一处细微问题：§5 差异清单第 2 项说「rate_limited 卡的『新规则』文案：fake 六原因对照表把 rate_limited 也标『自动软删除』；真实实现按 P3 剥离」。这是准确的——fake 交付时 P3 尚未裁定，自然按原始「六种全删」展示。但 fake 交付 63f5007 的六原因对照表是否确实把 rate_limited 标为自动删除，我未逐字核对 fake 源码。属低风险的引用一致性，不影响方案本身正确性。 记为观察。

修订完整性：通过。未发现遗漏或擅自改动。

C5｜遗漏与越界

- dispatch 要求的八个决策点 P1-P8：全部裁定
- revision dispatch 要求的五个新决策点 N1-N5：全部裁定
- ADR：ADR-001（P1）、ADR-002（P3）、ADR-003（P6）三份齐全
- 验收检查 1-10（原始 dispatch 的 10 项检查）：逐项覆盖
- 修订验收检查 1-10：逐项覆盖

未发现遗漏裁定。未发现悄悄扩大范围。 ④ 搭车于 Task 2 是显式标记的（「④ 搭车于 ②」），非悄悄扩围。

C6｜风险清单

方案 §7 列出的三个最高风险：
1. 符号/base-asset 三方对齐 —— 切中要害，早期验证方式（backend 数据驱动测试）合理
2. rate_limited 剥离正确性 —— 切中要害，验证方式（_pump_worker seam 注入）可操作
3. 死锁修法完备性 + drain 安全 —— 切中要害

§7.1 新增五风险逐条复核：均被识别且给出了缓解措施。

补充观察（非 REWORK）：方案未显式列为风险的、但我认为值得注意的一点——D15 混合均价在活任务与已删任务同桶时的可解释性（见 R4 分析）。这不是方案缺陷（includes_deleted_task 标记已提供必要警示），但值得在 Task 1 实现时确保前端标记的文案清晰（建议「含已删除任务记录，均价为混合值」而非仅「含已删除任务记录」）。

---
发现清单（按范围三分类）

in-range（阻塞交付）

无。

pre-existing-independent（不阻塞，记为后续项）

无。

pre-existing-release-critical（不机械阻塞交付，但阻塞合并/发布）

无。

观察（非缺陷，供参考）

1. R1·产品决定：rate_limited 剥离为退避而非删除，技术上论证充分，但最终是 Human 的产品取舍。建议 Human 明确裁定后，若选字面六删，则按回退方案不做 ③。
2. R4·标记文案精度：includes_deleted_task 标记的前端文案建议明确提示「均价为混合值」，避免用户以为该行均价仅来自活任务。属实现细节建议，非方案缺陷。
3. C4·fake 对照一致性：§5 差异 2 所述 fake 六原因对照表「rate_limited 标自动软删除」，未逐字核对 fake 源码。若该引用有误，属勘误范畴（修正引用文案），不改变方案裁定。

---
[TASK_RESULT v2]
任务 ID: plan-review-deepseek-v2
执行结果: completed
结果摘要: 计划评审完成。四条事实 F-A~F-D 全部成立，方案翻转依据牢靠。七条红线守住。六个具名检查 R0-R5 全部通过（R1 需 Human 产品裁定）。通用检查 C1-C6 全部通过。无 in-range 发现。评审结论 ACCEPT。
产物: [none —— 只读会话]
检查结果:
- R0 四条事实: pass —— F-A/F-B/F-C/F-D 均经源码独立核实，全部成立
- R1 rate_limited 剥离: pass —— 技术论证成立；最终取舍需 Human 产品裁定
- R2 ADR-003 推翻 follow-up: pass —— tick() SAFE NO-OP 属实，interval_us 无遗漏消费者
- R3 后端合并新增风险: pass —— 三项风险均被识别并给出缓解措施
- R4 D15 语义变更: pass —— includes_deleted_task 标记足以防误读；混合均价数学正确
- R5 交付拆分与串行约束: pass —— 重叠分析正确，严格串行推导成立，rebase 链可操作
- C1-C6 通用检查: pass —— 事实引用属实、七条红线守住、A-1 家族穷举成立、修订完整、无遗漏越界、风险清单充分
阻塞项: [none]
评审结论: ACCEPT
问题记录: inline-full-text
修复要求: none
本地北京时间: 2026-07-31 20:30:00 CST
下一步模型: opus5（Bookkeeper）—— 收取本评审结论，按 §8 同步 verdict 到 status.json，若 R1 需 Human 裁定则附上决策征询
下一步任务: Human 裁定 R1（rate_limited 剥离 vs 字面六删）→ Bookkeeper 封存评审结果 → 准备 Task 1 (hedge-merged-positions-v1) 实现 dispatch
[/TASK_RESULT]
```

## 4. 评审带出的、需转入实现阶段的具名项

| # | 来源 | 转入 |
|---|---|---|
| 1 | R4 副作用审计：`test_hedge_store.py:279-285` `test_aggregate_positions_excludes_deleted_tasks` 断言 `aggregate_positions() == []`，与 D15 相反 | Task 1 dispatch 具名要求更新该测试（不得删除，须改为断言新行为） |
| 2 | R4 / 观察 2：`includes_deleted_task` 行文案建议写明「均价为混合值」 | Task 1 dispatch 的展示要求 |
| 3 | Bookkeeper §1.1(a)：`scheduler.py:51-56` 切片随 `interval_us` 下调，调度线程唤醒频率上升约 5 倍（有 5ms 下限，live 下 `tick()` 立即返回，无交易所请求） | Task 3 dispatch 具名输入 |
| 4 | 观察 3：fake 六原因对照表是否确实把 `rate_limited` 标为自动删除，评审未逐字核对 | Bookkeeper 已复核：`index.html` 预览对照表确将 `rate_limited` 列入自动删除，方案 §5 差异 2 的引用属实，无需勘误 |

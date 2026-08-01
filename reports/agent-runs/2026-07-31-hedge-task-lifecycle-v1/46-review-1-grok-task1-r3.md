# 46-review-1-grok-task1-r3 —— review-1 第 3 轮结果（grok，只读）

- task_id: `review-1-grok-task1-r3`；评审者 `grok`（`xai`），作者 `claude_glm`（`zhipu_glm`），隔离成立
- 评审区间：`c1cc10e..ef53a02`（受审差异 `6d6aa7b..ef53a02`）
- **评审结论：`REWORK`**；`问题记录` / `修复要求` 均为 `inline-full-text`（正文随回执同交，逐字留档于 §4）
- 一条 `in-range` 阻塞发现（F4）；五条观察
- **`rework_count` 由 `2` 递增为 `3` —— 已达 `AGENTS.md` §8 的上限**，见 §3

## 1. Bookkeeper 核验：F4 成立，探测结果比评审所述更强

回执格式合规，`REWORK` 附可执行修复要求。F4 经**直接调用 `merge_positions` 实测**验证：

| 场景 | 输入 | 输出 `match_status` | `um_position_amt` |
|---|---|---|---|
| 1 | `verified: false`，但 `private_account.um_positions` **确实含 BTCUSDT 空头 0.5** | **`no_um`** | `None` |
| 2 | `private_account` 为 `None`（快照未就绪） | **`no_um`** | `None` |
| 3（对照） | `verified: true`，`um_positions` 为空 | `no_um` | `None` |

**三种场景输出完全一致。** 即：「查过、交易所确实没有」与「**根本没查**」在契约上不可区分。场景 1 尤其严重 —— 手上的数据明明含该持仓，只因 `verified=false` 就被跳过，然后系统对外宣称「交易所无仓」。

前端 `index.html` 对 `no_um` 无条件渲染「交易所无仓」，`title` 为「本地有任务记录，但交易所无对应持仓（可能已强平或手工平仓）」—— 一个**凭空断言的事实**外加**误导性的强平推测**。

且该路径正是上轮 F1 特意打开的冷账户路径：用户会同时看到「账户数据未就绪」横幅与「交易所无仓 / 可能已强平」，**两条信息互相矛盾**，并有据此误判仓位已被强平的实操风险。

判定：**阻塞成立**，范围三分类 `in-range`（`match_status` 由本次交付引入，N2 路径本身 pre-existing，误标是新键造成）。

## 2. 值得记下的一课：穷举表把缺陷写了进去

上一轮已按 §8「同根因刹车」要求做了穷举扫描，实现报告 §11.2 给出「每列 × 六场景」的显示口径表。评审 V6 指出：**该表的 `missing × 标记` 一格写的正是「交易所无仓」+ 横幅，与实现一致 —— 表格如实记录了实现，却把缺陷一并固化为"预期行为"。**

教训：**穷举扫描只能抓住作者已经意识到"是错的"的东西。** 当作者对某一格的语义判断本身就是错的，穷举表会把错误写成规范，看起来完备实则背书。下次要求穷举时，应同时要求作者对每一格回答"**这一格断言了什么事实？我们真的知道它吗？**"，而非仅回答"这一格显示什么"。

本条记入本 stage 的过程教训，不新增 Harness 规则。

## 3. 返工预算：已达上限

`rework_count` 递增为 **`3 / 3`**。按 `AGENTS.md` §8：「最大是三；超出后由 Human 选择缩小范围、重新设计、接受某项为限制、或停止」。

因此：**本轮修复（第 3 轮）在预算之内，可以执行。但它是最后一轮。** 若此后仍出现 `REWORK`，须由 Human 在上述四项中做出选择，Bookkeeper 不得自行再派修复。

Bookkeeper 已在修复 dispatch 中向实现者明示该处境。

## 4. 评审原文（逐字保留，未经改写）

```text
Review-1 r3 —— review-1-grok-task1-r3（只读）

• 分支：stage/2026-07-31-hedge-task-lifecycle-v1（已确认）
• 身份：grok / xai；实现与修复作者 claude_glm / zhipu_glm，provider 隔离成立
• 固定区间：c1cc10e..ef53a02；本轮受审差异：6d6aa7b..ef53a02（交付提交 ef53a02）
• 只读：未改文件、未移 HEAD、未提交/合并/推送
• rework_count：2 / 3（仅剩 1 次）——只报确认成立的 in-range 缺陷

总览

G5 均价分母修复正确且对准真机证据；G2/G7 对「假零」家族处置得当；G1 显式 match_status 方向正确。
但 match_status 在 N2（账户未就绪）路径上把「读不到 UM」误标成「交易所无仓」，与 title「可能已强平/手工平」冲突，且正落在上轮 F1 刻意打开的可见路径上。据此 REWORK（1 条 in-range）。

V1｜新契约键 match_status —— 结论：有缺陷（见 F4）

取值：代码写 normal / no_task / no_um；um∧bucket 四组合里前三可达，else→normal 为双方皆无（实际不可达）的兜底
互斥：三值在单行上互斥成立
第四种情形：有——account.verified=false / private_account is None 时，合并层故意不读 um_positions，却仍走 bucket and um is None → no_um
实测：verified=false 且 um_positions 里甚至有 BTC 持仓时，行仍为 match_status=no_um、um_position_amt=None
_POSITION_KEYS：已加入 match_status；与 merge 行精确集一致（27 键，assert set(keys)==_POSITION_KEYS 形式保持）
前端对齐：no_task→无任务记录、no_um→交易所无仓，拼写与分支无遗漏；normal 不画额外匹配徽标（与 Human 简短版一致）
与既有标记：single_leg_exposure / drift / includes_deleted_task 语义正交，无矛盾

F4 [in-range][blocker]：no_um 的契约语义应是「在已成功读取账户的前提下，任务有记录、交易所无对应仓」。N2 降级时并未成功读取 UM，却输出 no_um，前端再画「交易所无仓」+ title「可能已强平或手工平仓」——这是假清晰，与本 stage 同根因（展示未如实告知）同族。F1 已让冷账户路径可见，此路径可触达。

V2｜均价分母（资金数字，最重要）—— 结论：通过

•「金额未知」判定（leg_rows）：known_notional = notional is not None and notional != 0
  • NULL 与字面 "0" / "0.0" / 0E-8 均视为未知
  • 真实对冲成交名义额恰为 0 在路径上不可信；宁可漏计、不污染均价（与 G5/真机 RSRUSDT 一致）
  • 与「真零均价」区分靠不同列：leg 的 cumulative_quote_amt vs fill 的 avg_price（r5）
• 自洽性：spot_qty/perp_qty/position_qty 仍含未知金额腿；spot_avg/perp_avg 仅用 *_qty_priced；open_basis_rate 前端由均价现算，未知腿不再把价差打成 -100%
• 双路径：leg_rows 按 G5 扩展；fill_rows 刻意保持 r5（字面 "0" avg 为真零、不置 incomplete），但已同步喂 *_qty_priced。理由成立，且有 test_aggregate_positions_fill_real_zero_avg_price_contributes_zero 锁定
• 除零/符号/精度：分母 >0 才除；cumulative_base_qty<=0 跳过；方向符号只进 position_qty。Bookkeeper 复验 RSR：0.000623→0.001246、incomplete=True、qty 仍 20000——与代码一致
• 测试：test_aggregate_positions_literal_zero_quote_treated_as_unknown_g5 锁真值并守卫 !=0.000623（可失败）

V3｜G2 与展示口径 —— 结论：通过（在 match 标记之外）

• _merge_empty_bucket_row：spot_avg/perp_avg/position_qty/spot_qty/perp_qty → None（不再 "0"）
• 前端：formatHedgeAvgPrice(null)→—；computeHedgeOpenBasisRate 在均价非有限或 ≤0 时 → NaN → formatHedgeBasisPct→—
• no_task 有 UM 时持仓数量走 um_position_amt，不依赖本地 position_qty
• 资金费/借币/净盈亏仍经 pendingCell 画「暂无」；未发现其它本地成本列在 no_task 上画假 0

V4｜G6 / G7 —— 结论：通过（不质疑 Human 裁定本身）

G7 formatHedgeAvgPrice（8 位有效数字）
• 缺失 → —；n===0 → 走 formatHedgeDecimal 显示 0（与缺失可分）
• 探针：0.000623、0.001246、27 位尾数、负号、极大整数、非数字 → 非零不被抹成 0
• 极端理论：|n| 小到 decimals>100 时 toFixed 会抛（约 <1e-93），非交易价格量级 → 观察，不返工

G6 借款去重
• 按 base 资产 seenBorrowAsset：首行真值 + title「账户级…勿竖向相加」，余行「同↑」
• 行序由 merge 按 coin/direction 排序，同币相邻，逻辑成立

V5｜断言质量与回归 —— 结论：主路径覆盖充分；N2×match_status 缺口即 F4

G3 / 82c：no_task 成本 — 且不含 0、标记文案、incomplete+title；Bookkeeper 破坏探测已验
G5 后端：真机形状向量 + 半价回归守卫
D15：本轮未动 WHERE；标记字段保留
merge_positions 纯度：仍纯函数，仅追加 match_status
N2 表可见 / F1：未回退
F2 暂无 vs 0：未回退
精确键集形式：保持
缺口：N2 降级测未断言「不得为 no_um」；self-check 未盖 N2 下抑制错配徽标

V6｜同根因穷举表质量 —— 结论：列×场景大体穷尽，与实现一致；有一格把缺陷写进了表

• 17 列 × 六场景 + 派生（借款去重、8 位有效数字、横幅、title）+「字面 0」子情形 + 清单外不适用理由（fill r5、限制 A/B、推后项）——结构满足 §8 同根因刹车
• 不符点：missing × 标记 = 「交易所无仓」+横幅 与实现一致，但语义错误（见 F4）；应改为不宣称无仓（例如仅横幅，或中性/不标匹配态）
• 其余格子与代码对齐；normal 不画「正常」徽标已在 10-design.md §5 增补说明

问题记录（inline-full-text）

F4 [in-range][blocker]
主题：match_status 在 N2/账户未就绪路径把「未读到 UM」误标为 no_um（「交易所无仓」）

证据（相对 6d6aa7b..ef53a02 / delivery ef53a02）：
1. domain.py _merge_build_row：um is None and bucket is not None → 一律 match_status="no_um"
2. domain.py merge_positions：verified 为假时 um_positions 强制为 None，不进入 UM 骨架循环；本地桶全部以 um=None 建行
3. 探测：verified=false 且 pa 内仍带 um_positions 时，输出仍 match_status=no_um、um_position_amt=None
4. 探测：private_account=None → 同样 no_um
5. index.html：match_status==='no_um' 无条件渲染「交易所无仓」，title 含「可能已强平或手工平仓」
6. 对照：verified=true 且 um 列表空 → no_um 语义正确；缺陷是 N2 与真 no_um 不可区分
7. 既有 test_merge_degradation_* 不断言 match_status；82c 只喂显式 no_um mock，不盖账户未就绪

为何阻塞：
- 本轮回 review-1 的原因就是新增契约键 match_status；取值未覆盖「账户侧不可用」这一可达情形
- 与 D7「对不上要标清楚」及同根因「不得用看起来明确的假信息」冲突
- 冷账户表由 F1 明确打开；用户会同时看到「账户数据未就绪」横幅与「交易所无仓/可能已强平」——互相矛盾，且有误导强平的实操风险

范围三分类：in-range（由本交付 match_status 引入；N2 本身 pre-existing，误标是新键造成）

修复要求（inline-full-text）

1. 契约：仅在「账户侧已成功验证/已读 UM 骨架」时，才允许 match_status="no_um"。
   - verified=false 或 private_account 缺失：本地行不得为 no_um（建议 normal，或新增中性值；若新增枚举须同步 _POSITION_KEYS + 前端）
   - verified=true 且确无匹配 UM：仍为 no_um
   - no_task 仅在存在真实 UM 行且无桶时设置（当前已满足，勿回归）

2. 展示：N2 路径不得出现「交易所无仓」及强平/手工平 title；可与「账户数据未就绪」横幅并存的只有中性/无匹配徽标。

3. 测试（须能失败）：
   - merge：positions 非空 + verified=false（及 private_account=None）→ match_status != "no_um"
   - merge：verified=true + 无 UM + 有桶 → 仍为 no_um
   - self-check：account.verified=false 的本地行 HTML 不含「交易所无仓」

4. 同步：21- §11.2 的 missing×标记格；必要时 10-design.md §5 一句说明 N2 与真 no_um 的区分。

5. 不得回退：G5 字面 0 分母、G2 no_task 成本 None/—、G6/G7、D15、N2 表可见、精确键集、merge 纯度、禁改区。

6. 新 commit 后：因仍涉 match_status 契约，按 §8 再过 review-1 再回 review-2。

观察（不阻塞、不返工）

1. 全腿金额未知时均价仍回落显示 0 +「均价不完整」（T1 既有）；优于假半价，但「全未知」仍略像数字——可后续改为 —
2. API 层 open_basis_rate 在 empty bucket 仍为占位 "0"；前端不读，仅原始 API 消费者需知
3. G6 借款去重无 self-check 锁定
4. formatHedgeAvgPrice 在非交易量级极小值可能 toFixed 越界——观察
5. 范围外清单（限制 A/B、C-1~C-4、D13、推后项）未据以返工

上轮 ACCEPT 是否被破坏

D15 已删成本基：保持
merge_positions 纯度：保持
N2 降级表可见（F1）：机制保持；标记语义被 F4 污染
F2 缺失盈亏不画 0：保持
边界/红线/禁改区：未见触碰

[TASK_RESULT v2]
任务 ID: review-1-grok-task1-r3
执行结果: completed（完成）
结果摘要: Review-1 r3：G5/G2/G7 成立；match_status 在 N2 误标 no_um（F4 in-range）。REWORK；修后须再过 review-1 再回 review-2。
产物: [inline-full-text]
检查结果: [pass V2均价分母与G5; pass V3 G2展示; pass V4 G6/G7实现; fail V1 match_status穷尽性/N2; pass V5主断言可失败但N2缺口; fail V6 missing×标记格语义; pass 固定区间与只读隔离; pass 未据范围外项返工]
阻塞项: [F4：N2/账户未就绪不得输出或展示 no_um/「交易所无仓」；修后新commit再review-1]
评审结论: REWORK（返工）
问题记录: inline-full-text
修复要求: inline-full-text
本地北京时间: 2026-08-01 17:11:20 CST
下一步模型: opus5（Bookkeeper；Human 将本回执交其同步状态）
下一步任务: 核验 F4，保持交付未封存，准备最小修复 dispatch（match_status×N2）；实现后新 commit 再派 review-1（grok），通过后再回 review-2（codex）
```

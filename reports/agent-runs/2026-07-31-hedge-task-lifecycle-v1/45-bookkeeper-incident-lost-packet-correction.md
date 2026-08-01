# 45-bookkeeper-incident-lost-packet-correction —— 派工单更正提交丢失事件

- 记录人：opus5（bookkeeper），2026-08-01
- 性质：**Bookkeeper 自身操作失误**，非实现者过错
- 影响：修复轮 2 的实现者读到的是**未更正版**派工单，两处偏离 Human 已定决策
- 计数后果：**不递增 `rework_count`**（仍为 `2`）。缺陷在 packet 不在交付，实现者忠实执行了其拿到的版本

## 1. 发生了什么

修复轮 2 的派工单 `fix-merged-positions-mismatch-labels-v1.dispatch.md` 经过两次修改：

| 提交 | 内容 | 是否在 stage 分支上 |
|---|---|---|
| `8808ccd` | 折入真机发现，G1-G7 七项（**G6 借款去重为必做**，G7 写「合理位数」，路由由实现者选择） | ✅ 在 |
| `25edb98` | 按 Human 追加决定收紧：**G6 划掉不做**、G7 定为**固定 8 位小数**、路由定死为显式字段先走 review-1 | ❌ **游离提交，无任何分支包含** |

`git branch -a --contains 25edb98` 返回空；该提交内容仍可经 SHA 读取，但从未进入 `stage/2026-07-31-hedge-task-lifecycle-v1`。

期间工作区曾被切换到 `codex/support_bStock` 分支（非 Bookkeeper 所为，`af687cc`），随后又切回。`25edb98` 在此过程中脱离分支引用。

**Bookkeeper 的失误在于**：提交后未回验该提交是否落在预期分支上。此前每次改 `status.json` 都用 `git rev-parse` 回验了 SHA，但**没有回验提交本身的分支归属** —— 这是一个此前不存在于检查清单里的盲点。

## 2. 造成的两处偏离

实现者读到的是 `8808ccd` 版派工单，忠实执行。与 Human 实际决定的偏离：

| # | Human 的决定 | 实际交付 | 判定 |
|---|---|---|---|
| A | G7 小数位：**固定 8 位小数**，保留末尾零 | **8 位有效数字**（`formatHedgeAvgPrice`，`index.html:3715-3719`），注释理由为「用有效数字而非固定小数位：极小真值永不被抹成 0」 | **需 Human 裁定**，见 §4 |
| B | G6 借款去重：**不做**（同币多行的场景将来会由开单闸门消除） | **已做**：同币首行显示数值，余行显示「同↑」并带 title「账户级（按资产）；同币多行请勿竖向相加」 | 多做了一项，无害。见 §4 建议 |

另：路由方面实现者自行选择了**后端显式字段 `match_status`**，与 `25edb98` 中定死的选择**一致**；G1 的标签也自行采用了「无任务记录」「交易所无仓」+ 悬停说明，与 Human 选的简短版**一致**。这两处未受影响。

## 3. 交付本身的核验结果（全部通过）

| 项 | Bookkeeper 复验方式 | 结果 |
|---|---|---|
| 后端测试 | 自行运行 `pytest backend/tests -q` | `1127 passed` |
| 前端自检 | 自行运行 `node frontend/self-check.js` | `EXIT=0`，130 项 |
| **G5 真实数据验证** | 复制真实库到临时目录后调用 `aggregate_positions` | `RSRUSDT forward` 的 `perp_avg` 由 `0.000623` → **`0.001246`**（真值），`perp_avg_price_incomplete=True`，`perp_qty` 仍为 `20000`（展示数量未受影响） |
| G5 修法 | 读 `store.py` 差异 | 引入 `spot_qty_priced` / `perp_qty_priced` 作为均价分母，只统计**金额已知**的腿；未知金额的腿仍贡献展示数量。设计正确 |
| G1 | `domain.py:1500-1506` + `index.html:4538-4539` | 后端显式 `match_status`（`normal`/`no_task`/`no_um`），前端渲染短标签 + `title` 含推测原因 |
| G3 断言可失败 | **Bookkeeper 自行破坏探测**：把 `no_task` 标记分支改为 `if (false)` | 自检 `EXIT=1`，报 `[FAIL] G1: no_task 行应标记「无任务记录」`；还原后 `EXIT=0`，文件哈希与探测前一致 |

## 4. Human 裁定（2026-08-01）：两处偏离均按已交付形态保留

| 偏离 | 裁定 | 依据 |
|---|---|---|
| A 小数位 | **保留 8 位有效数字**（不改回固定 8 位小数） | 实现者的理由成立：有效数字对极小价格更稳，不会因固定位数把真值舍成 `0`（将来若出现更小面值的币，固定 8 位会真的抹零），且大额币不拖一串零。该理由与 Bookkeeper 最初的推荐一致，Human 当时选固定位数时该论证尚未展开 |
| B 借款去重 | **保留已实现的去重** | 已完成、无害；在开单闸门落地之前确实防止竖向加总误读。移除是纯粹浪费 |

两处均属 packet 缺陷导致，按 `AGENTS.md` §7 采信更正规则，**不消耗返工预算**（`rework_count` 保持 `2`）。

由此，`fix-merged-positions-mismatch-labels-v1` 的交付**与 Human 的最终意图一致**，无需追加修复轮。原派工单（`8808ccd` 版）与交付一致，其上的 G6/G7 表述即为最终有效表述；`25edb98` 中被丢失的收紧文本**不再适用**，仅作事件留档。

## 5. 流程改进（Bookkeeper 自加检查项）

自本条起，Bookkeeper 每次提交后除回验 SHA 外，**必须回验该提交是否落在预期分支上**：

```bash
git branch --show-current && git log --oneline -1
```

派工单交付给实现者之前，**额外确认派工单文件在当前分支上的内容即为最终版**（`git show HEAD:<path> | diff - <path>`）。

本条不新增 Harness 规则、不改任何权威文件，仅为 Bookkeeper 的操作纪律。

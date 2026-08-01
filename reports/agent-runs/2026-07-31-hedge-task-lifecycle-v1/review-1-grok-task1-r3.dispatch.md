# Dispatch —— review-1-grok-task1-r3（代码评审，只读）

```text
Identity:
  task_id:         review-1-grok-task1-r3
  target_role:     Reviewer
  target_model:    grok
  provider:        xai
  status_revision: 16
  required_skill:  agents/skills/code-reviewer.md
```

## Goal

`hedge-merged-positions-v1` 在你上轮 `ACCEPT` 之后，又经 review-2（`codex`）返回 `REWORK`（F3）并完成修复轮 2。**该修复新增了接口契约键 `match_status`**，按 `AGENTS.md` §8「review-2 修复若扩大文件、改变契约或增加风险，须重新通过 review-1」，因此回到你这里，通过后再回 review-2。

- 实现与修复作者 `claude_glm`（`zhipu_glm`），你 `grok`（`xai`），provider 隔离成立。
- 只读会话。未取得明确、格式良好的 `ACCEPT` 即为非接受（§3 #7）。
- `rework_count = 2 / 3`，**仅剩 1 次**。请把发现的分量判准：真缺陷务必报，边缘观察不要包装成 `REWORK`。

## 评审对象（固定区间，不得移动 HEAD）

```text
base_sha     = c1cc10e8fb491f83fe4c09f565b34e06c2de0a50
delivery_sha = ef53a025114933e8c472d9ae89f8ebfb35d19513
```

**本轮受审的是修复差异 `git diff 6d6aa7b..ef53a02`**（`domain.py`、`store.py`、`index.html`、`self-check.js`、三个测试文件与两份报告）。`6d6aa7b` 是你上轮 `ACCEPT` 的版本。区间内其余提交为 Bookkeeper 控制提交，按 §8 是上下文而非受审交付。

## 本轮复核重点

- **V1｜新契约键 `match_status`**（本轮回到 review-1 的原因）。后端 `domain.py:1500-1506` 产出 `normal` / `no_task` / `no_um`。请判断：取值是否穷尽且互斥？是否存在第四种应有而未覆盖的情形？`_POSITION_KEYS` 精确集是否同步且仍为精确集？前端消费是否与后端取值完全对齐（有无拼写或分支遗漏）？该键与既有的 `single_leg_exposure` / `drift` / `includes_deleted_task` 三个标记语义有无重叠或矛盾？
- **V2｜均价分母的改动（最重要，直接改资金数字）**。`store.py` 新引入 `spot_qty_priced` / `perp_qty_priced`：金额已知的腿才计入均价分母，金额未知（`NULL` 或字面 `0`）的腿仍贡献展示数量但不计入分母，并置 `*_avg_price_incomplete`。请判断：
  - 判定「金额未知」的条件是否**正确且完备** —— 特别是「字面 `0`」与「真实成交额恰为 0」如何区分？会不会把一个真实的零名义额误判为未知？
  - 分母改变后，`spot_avg` / `perp_avg` / `open_basis_rate` / `position_qty` / `spot_qty` / `perp_qty` 之间是否仍然自洽？
  - `hedge_open_fill`（遗留表）与 `hedge_open_leg` 两条累加路径**是否都做了同样处理**？若刻意只改一条，理由是否成立？
  - 有无除零、符号翻转或精度问题。
- **V3｜G2 与展示口径**：`no_task` 行的本地记账列不再显示 `0` 而显示 `—`；派生的价差率是否一并处理；有无遗漏的派生展示仍在画 `0`。
- **V4｜G6 / G7 展示改动**：借款列同币首行显示、余行标为重复；均价改为 8 位有效数字。请判断：有效数字实现是否会在任何输入下把**非零真值渲染成 `0`**（这是本 stage 反复出现的失败模式）；千分位、负号、极大极小值、非数字输入的边界。
- **V5｜断言质量与回归**：新增断言是否覆盖真实失败模式；Bookkeeper 已独立探测过 `no_task` 标记断言（改为 `if (false)` 后自检 `EXIT=1`，还原后哈希一致），请你从**覆盖面**判断而非重复探测。你上轮 `ACCEPT` 的结论（D15、`merge_positions` 纯度、N2 降级、边界与红线、F1/F2 修复）是否有被本轮改动破坏。
- **V6｜同根因穷举的质量**：实现报告 §11.2 给出「每列 × 六场景」的显示口径表。请判断该表是否真的穷尽，有没有它列出但实现不符、或实现存在而表里没有的格子。

## ⚠️ 范围外，不得据以返工

- **已接受限制 A / B**（`22-bookkeeper-rejection-task1.md` §5）：单腿敞口判据漏报部分失衡；`spot_balance` / `drift` 读经典现货账户致 `drift` 恒 `False`。Human 明确接受，待其结合真实场景另行设计。
- **Human 已裁定的两项**（`45-bookkeeper-incident-lost-packet-correction.md` §4）：均价用 **8 位有效数字**（而非固定小数位）、借款去重**保留**。这两项是 Human 的最终决定，**不是缺陷**。你仍可就其**实现正确性**提出问题（见 V4），但不得质疑该选择本身。
- **Human 推后的建议项与既往观察**（`42-` §2 的 C-1~C-4、`41-` §2）：混合桶均价单测、HTTP 级 N2 断言、强平价 title、`umCell` 注释、`loadHedgePositions` 门闩未单测。
- **同币双向**（D13）：Human 已移出范围，将来由开单闸门根治。

若独立重新发现上述任一项，记为观察并引用出处，**不要返工**。

## Inputs

| 文件 | 读什么 |
|---|---|
| 本 dispatch | 全部 |
| `git diff 6d6aa7b..ef53a02` | **本轮受审差异** |
| `43-review-2-codex-task1.md` | F3 原文与 Bookkeeper 复验（§1、§5） |
| `44-runtime-observation-task1.md` | 真机观察与 G5 的数据库证据 |
| `45-bookkeeper-incident-lost-packet-correction.md` | §3 Bookkeeper 复验结果、§4 Human 裁定 |
| `fix-merged-positions-mismatch-labels-v1.dispatch.md` | 本轮修复要求 G1-G7 |
| `21-merged-positions-implementation.md` | 实现者自述，含 §11.2 穷举表 |
| `22-` §5 / `42-` §2 | 范围外清单 |
| `agents/skills/code-reviewer.md` | 全部 |

字节数请自行 `wc -c`。禁止整文件读三个后端主文件，按差异定位。

## 输出要求

按 `AGENTS.md` §7 返回 `[TASK_RESULT v2]`，并含三行闭合字段：

```text
评审结论: ACCEPT（接受） | REWORK（返工）
问题记录: <path | none>
修复要求: <path | none>
```

- **`问题记录` 与 `修复要求` 填 `inline-full-text`，完整正文放在同一次输出的正文里。** 你前两轮都做到了，本轮请保持。
- 每条 `REWORK` 发现按 §8 标注范围三分类；`pre-existing-*` 须附早于 `base_sha` 的引入提交引用。
- **`本地北京时间` 须由 `date '+%Y-%m-%d %H:%M:%S CST'` 实际产生。**
- 若无 in-range 缺陷请返回 `ACCEPT`。返工额度只剩 1 次，**不要为显得尽责而制造边缘发现**；范围外的观察照常列，不影响 verdict。

## Stop

- 只读：不得修改任何文件（含 `status.json`）、不得写代码、不得提交、不得合并、不得推送。
- 不得移动 `HEAD`，只评审写死的 `base_sha..delivery_sha`。
- 不得启动、调用、转交或冒充任何其他模型会话（§3 #2）。
- `ACCEPT` 不构成实现、验收、合并、部署或实盘授权；结论交回 Human，由 Bookkeeper 同步。
- 若发现本 dispatch 与受审代码矛盾、或评审对象与 `status.json` 不符：停止并报告。

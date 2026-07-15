# Task C — Kimi Fast UI Layout Adjustment 实现报告

## 执行元数据

- **阶段**: `2026-07-bookticker-open-columns-v1`
- **任务**: `task-c-fast-ui-layout`
- **执行模型/Provider**: Kimi / `kimi-code/kimi-for-coding` / Moonshot
- **Session ID**: `session_b4a656b7-91c8-43ae-a994-68cb2e10c03f`
- **Session ID 来源**: Kimi CLI 本地会话目录 (`/Users/ark/.kimi-code/sessions/wd_funding_hedging_312b78e68b47/session_b4a656b7-91c8-43ae-a994-68cb2e10c03f/state.json`)，`workDir` 与当前工作目录一致
- **起始分支**: `stage/2026-07-bookticker-open-columns-v1`
- **起始 HEAD (base_sha)**: `f1790c15f56b9e9be8846b40fe03c88ed7210213`
- **变更文件**:
  - `frontend/index.html`
  - `frontend/self-check.js`
  - `reports/agent-runs/2026-07-bookticker-open-columns-v1/20-implementation-task-c.md`

## 最终表头顺序与单元格索引映射

| 索引 | 列名 |
|------|------|
| 0 | 标的 |
| 1 | 标记价格 / 指数价格 |
| 2 | 正向开单 |
| 3 | 反向开单 |
| 4 | 资金费率 |
| 5 | 结算时间 |
| 6 | 日费率 |
| 7 | 年化 24h |
| 8 | 年化 7D |
| 9 | 年化 30D |
| 10 | 日净收益 |
| 11 | 借贷状态 / 资产 |

- `colspan="12"` 空状态保持不变
- 每个数据行仍然精确包含 12 个 `<td>`

## 改动点映射

### 1. 标的单元格：移除 B 后缀别名显示
- **位置**: `frontend/index.html` 内联脚本 `renderRowHtml`
- **改动**: 删除局部变量 `spotAlias` 及其在符号单元格中的拼接；保留 `row.spot.symbol` 数据语义、fixture、backend 字段以及数据说明面板中的 bStock 解释文字
- **验证**: `self-check.js` 新增断言，检查 `BSTOCK` 行的符号单元格不再包含 `B 后缀别名` 或 `现货腿:` 文本

### 2. 列移动
- **位置**: `frontend/index.html` 内联脚本 `renderRowHtml` 与 `<thead>`
- **改动**:
  - `<thead>` 中 `标记价格 / 指数价格`、`正向开单`、`反向开单` 整体移动到 `标的` 之后
  - `renderRowHtml` 中对应 `<td>` 按新顺序输出：symbol → mark/index → forward → reverse → funding → settlement → daily → ann24 → ann7 → ann30 → net-yield → borrowing/asset
  - `借贷状态 / 资产` 合并列移动到最后一列；内部仍保持“状态/可借额度在上、资产标签在下”的顺序，零额度/已借完语义不变
  - `日净收益` 单元格内容不变，仍不重复 `可借:` 额度

### 3. 开单单元格改为三行垂直堆叠
- **位置**: `frontend/index.html` 内联脚本 `renderOpeningQuotesCell`
- **改动**:
  - 移除 `display:flex` 的水平 flex 布局
  - 正向：第 1 行 `合约买一 <futures bid>`，第 2 行 `现货卖一 <spot ask>`，第 3 行 `forward_spread_pct`
  - 反向：第 1 行 `现货买一 <spot bid>`，第 2 行 `合约卖一 <futures ask>`，第 3 行 `reverse_spread_pct`
  - 保留原有 `formatOpeningSpreadPct` 独立格式化、正负/ muted 样式、stale/unavailable/incomplete 降级、title 提示
  - 未乘以 100，未调用 `formatFundingRate`

### 4. 前端自检脚本更新
- **位置**: `frontend/self-check.js`
- **改动**:
  - 将 `taskBHeaders` 更新为 Task C 顺序并改名为 `taskCHeaders`
  - 所有 hard-coded cell index 按新映射更新：
    - daily rate `4 → 6`
    - ann24 `5 → 7`
    - ann7 `6 → 8`
    - ann30 `7 → 9`
    - net yield `8 → 10`
    - combined borrowing/asset `1 → 11`
    - forward opening `10 → 2`
    - reverse opening `11 → 3`
  - 优雅降级块中按 index 提取 daily/net-yield 的计数器同步更新
  - 新增断言：
    - 严格 12 列表头顺序
    - 每行 12 个 `<td>`、`empty-state` 使用 `colspan="12"`
    - 最后一列状态 badge 位于资产标签之前、净收益列无 `可借:` 重复
    - bStock 行符号单元格不含 `B 后缀别名` / `现货腿:`
    - 正向/反向开单列文本顺序：第一腿 < 第二腿 < 百分比
    - 开单单元格不再包含 `display:flex`

## 命令执行结果

```bash
$ node frontend/self-check.js | rg -c '^\[PASS\]'
78

$ python3 -m pytest backend/tests -q
375 passed in 15.52s

$ git diff --check
(no output)

$ git status --short
 M frontend/index.html
 M frontend/self-check.js

$ git diff --name-only f1790c15f56b9e9be8846b40fe03c88ed7210213 --
frontend/index.html
frontend/self-check.js
```

`git diff --name-only <base_sha> --` 仅包含允许的两个源文件；报告文件本身是本次写入的新增文件，未出现在与 `base_sha` 的差异中。

## 边界与未改动确认

- **后端/schema/fixture/data 语义未改动**: 仅修改 `frontend/index.html` 的渲染顺序与 CSS 布局、`frontend/self-check.js` 的断言索引；未触及 `backend/`、`schemas/`、`frontend/fixture/`、`docs/`、`reports/agent-runs/` 中其他文件
- **无交易/私有变更**: 未新增或调用任何交易、借币、划转、下单、私有 mutation API
- **无提交/推送/合并**: 未执行 `git commit`、`git push`、`git merge`
- **无子agent/模型派发**: 未调用其他模型或子agent
- **函数体保持不变**: `formatFundingRate`、`formatBeijing*`、`formatUsdt2`、`formatOpeningSpreadPct`、`classForOpeningSpread` 等函数体未修改

## 剩余视觉风险

- 开单百分比移到第三行后，列宽可能略微增加，但在现有 `min-width: 980px` 与 `white-space: nowrap` 下仍应完整显示
- 合并列移至最右后， ultra-wide 视图下横向滚动时该列会出现在可视区域最右侧，需用户手动滚动查看，符合 Task C 的设计意图
- 移除 bStock 别名显示后，用户仅在数据说明面板与抽屉中可见 B-suffix 解释，表格内更简洁

---

## 附录 A — 固定小数位显示追加需求

### 追加来源

`reports/agent-runs/2026-07-bookticker-open-columns-v1/task-c-fast-ui-layout-kimi-format-addendum.prompt.md`

### 追加显示规则

| 显示位置 | 原始 formatter | 新 formatter | 小数位 | 示例 |
|---------|---------------|-------------|--------|------|
| 资金费率（表格） | `formatFundingRate` | `formatFundingRateFixed(..., 3)` | 3 | `-0.00060000` → `-0.060%` |
| 日费率（表格） | `formatFundingRate` | `formatFundingRateFixed(..., 3)` | 3 | `-0.00060000` → `-0.060%` |
| 年化 24h（表格/抽屉） | `formatFundingRate` | `formatFundingRateFixed(..., 2)` | 2 | `-0.657` → `-65.70%` |
| 年化 7D（表格/抽屉） | `formatFundingRate` | `formatFundingRateFixed(..., 2)` | 2 | `-0.00260714` → `-0.26%` |
| 年化 30D（表格/抽屉） | `formatFundingRate` | `formatFundingRateFixed(..., 2)` | 2 | `-0.00060833` → `-0.06%` |

未改动：
- `日净收益` 仍使用 `formatFundingRate`
- `日借币` 子行仍使用 `formatFundingRate`
- 抽屉已结算历史 funding rate 仍使用 `formatFundingRate`
- 开单 `*_spread_pct` 仍使用 `formatOpeningSpreadPct`
- 价格、数量、USDT 估值 formatter 不变

### 新增实现

- 在 `frontend/index.html` 内联脚本新增 `formatFundingRateFixed(str, decimals)`：
  - 纯字符串/整数运算，不依赖二进制浮点乘法或 `toFixed()`
  - 先对原始分数 × 100（小数点右移两位）
  - 再按 HALF_UP 舍入到指定小数位
  - 非零值保留 `+`/`-` 号
  - 舍入后的负零归一化为无符号固定零（如 `0.000%` / `0.00%`）
  - `null`/`undefined`/空/非法字符串返回 `—`
- 将 `formatFundingRateFixed` 暴露到 `globalThis.__appHelpers`
- `renderRowHtml` 中资金费率、日费率、年化三列改用固定小数位 formatter
- `renderDrawer` 中年化三卡片改用固定小数位 formatter
- `classForFundingRate` 仍基于原始值计算颜色，不受显示格式化影响

### 追加后自检更新

- 新增 `formatFundingRateFixed` 直接向量测试：
  - `-0.00030000`, 3 → `-0.030%`
  - `0.00030000`, 3 → `+0.030%`
  - `0`, 3 → `0.000%`
  - `-0.657`, 2 → `-65.70%`
  - `-0.00260714`, 2 → `-0.26%`
  - `0.00000999`, 3 → `+0.001%`（HALF_UP 进位）
  - `0.00001999`, 3 → `+0.002%`（HALF_UP 连续进位）
  - `0.999995`, 2 → `+100.00%`（整数部分进位）
  - `-0.00000499`, 3 → `0.000%`（微小负值归一无符号零）
  - 无效/空输入 → `—`
- 新增表格资金费率 3 位断言：AUSDT `-0.060%`、CUSDT `+0.030%`、FUSDT `0.000%`
- 日费率断言更新为 3 位：`-0.060%`、`-0.070%`、`+0.030%`、`-0.040%`、`-0.080%`
- 年化表格与抽屉断言更新为 2 位：`-65.70%`、`-0.26%`、`-0.06%`
- symbol-snapshot 合并、重试、race、wrong-symbol 等场景中的年化期望值同步更新
- `formatFundingRate` 函数体基线断言保持不变

### 追加后命令结果

```bash
$ node frontend/self-check.js | rg -c '^\[PASS\]'
80

$ python3 -m pytest backend/tests -q
375 passed in 15.98s

$ git diff --check
(no output)

$ git status --short
 M frontend/index.html
 M frontend/self-check.js
 M reports/agent-runs/2026-07-bookticker-open-columns-v1/20-implementation.md
 M reports/agent-runs/2026-07-bookticker-open-columns-v1/60-test-output.txt
 M reports/agent-runs/2026-07-bookticker-open-columns-v1/70-handoff.md
 M reports/agent-runs/2026-07-bookticker-open-columns-v1/status.json
 M reports/agent-runs/ACTIVE.json
?? reports/agent-runs/2026-07-bookticker-open-columns-v1/20-implementation-task-c.md
?? reports/agent-runs/2026-07-bookticker-open-columns-v1/task-c-fast-ui-layout-kimi-format-addendum.prompt.md

$ git diff --name-only f1790c15f56b9e9be8846b40fe03c88ed7210213 --
frontend/index.html
frontend/self-check.js
reports/agent-runs/2026-07-bookticker-open-columns-v1/20-implementation.md
reports/agent-runs/2026-07-bookticker-open-columns-v1/60-test-output.txt
reports/agent-runs/2026-07-bookticker-open-columns-v1/70-handoff.md
reports/agent-runs/2026-07-bookticker-open-columns-v1/status.json
reports/agent-runs/ACTIVE.json
```

说明：`git status` 与 `git diff --name-only <base_sha>` 中出现的 `reports/agent-runs/**` 阶段提示/status/handoff/test-output 等文件由 bookkeeper Session 维护，不属于本 Kimi 实施任务允许修改的范围；本任务仅修改 `frontend/index.html`、`frontend/self-check.js` 与本报告。

---

当前 Session ID: session_b4a656b7-91c8-43ae-a994-68cb2e10c03f
Session ID 来源: transcript_path (state.json workDir/lastPrompt cross-check)
原始输出路径: reports/agent-runs/2026-07-bookticker-open-columns-v1/20-implementation-task-c.md
本地北京时间: 2026-07-16 03:04:03 CST
下一步模型: codex_bookkeeper
下一步任务: 核验 Task C 最终 bounded diff 与测试，然后交由用户页面显示验收

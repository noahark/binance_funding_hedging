# Task B Implementation Report — 2026-07-phase2-borrow-sort-v1

Author: Kimi-2.7 (frontend implementer)  
Scope: `frontend/index.html` + `frontend/self-check.js`  
Date: 2026-07-04  
Stage: `2026-07-phase2-borrow-sort-v1` Task B  
Authority: `reports/agent-runs/2026-07-phase2-borrow-sort-v1/10-design.md` §4

---

## 1. 改动清单

### 1.1 `frontend/index.html`

1. **拆列**：删除原来的「资金费率/结算时间」合并列，恢复为独立两列：
   - `资金费率`（`title="本周期实时预估"`）
   - `结算时间`
2. **新增「日费率」列**：渲染 `daily_funding_rate`，使用既有 `formatFundingRate` 做 string-shift 百分比格式化；`null` 或字段缺失 → `—`。
3. **结算间隔标注**：在行内日费率单元格中，当 `funding_interval_hours ∈ {1,4,8}` 时渲染 `<span class="badge compact muted">Xh</span>`（如 `8h` / `4h` / `1h`），使排名依据可见。
4. **零排序逻辑**：未引入任何排序按钮、比较器或排序状态；严格按 payload 顺序渲染；既有筛选只隐藏不重排。
5. **优雅降级**：`validateContract` 未将 `funding_interval_hours` / `daily_funding_rate` 设为必填；字段缺失时日费率列显示 `—`、间隔徽标不渲染。
6. **不消费 `borrow_validation`**：未读取该块任何字段。
7. **colgroup / 空状态 colspan**：合并列拆成两列后，表格列数从 7 变为 9；已同步更新 blocked/empty 状态的 `colspan="9"`。
8. **暴露 `ingestSnapshot` 给自检**：在 `globalThis.__appHelpers` 中新增 `ingestSnapshot`，仅用于 `self-check.js` 的优雅降级用例，不影响生产运行时。

### 1.2 `frontend/self-check.js`

1. **改用 10-design §4.3 设计期 fixture**：内联 `AUSDT / BUSDT / CUSDT / DUSDT` 四行样本（补全全部 REQUIRED_ROW_FIELDS），其中：
   - AUSDT 单期费率 `0.00010000`、间隔 4h → 日费率 `0.00060000`
   - BUSDT 单期费率 `0.00015000`、间隔 8h → 日费率 `0.00045000`
   - 用于验证「按 payload 顺序渲染，不因单期费率重排」的核心用例。
2. **新增断言**：
   - 拆列存在且合并列消失
   - 日费率 string-shift 格式化：`+0.06%` / `+0.045%` / `-0.03%` / `—`
   - 结算间隔徽标 `4h` / `8h` 渲染
   - 无排序控件 DOM
   - 渲染顺序 == fixture 顺序
   - `formatFundingRate` / `formatBeijing*` 函数体未变（字符串比对）
   - 优雅降级：删除 `daily_funding_rate` 与 `funding_interval_hours` 后仍能渲染 4 行、日费率列 `—`、无间隔徽标
3. **保留并通过的既有断言**：默认请求 `/api/public-market/snapshot`、数据源标签、warnings 可见、无交易按钮、60s 自动刷新与倒计时、手动刷新后计时器重调度、枚举列「英文(中文)」格式、侧栏品牌中文。

---

## 2. self-check 原始输出

```text
[PASS] 内联脚本语法检查
[PASS] 默认请求 /api/public-market/snapshot
[PASS] 数据源标签显示后端 API
[PASS] 数据说明区可见且内容已渲染
[PASS] 默认渲染 4 行
[PASS] 拆列存在，合并列消失
[PASS] 日费率 string-shift 格式化（含 null→—）
[PASS] 结算间隔标注 4h/8h
[PASS] 无排序控件 DOM
[PASS] 渲染顺序等于 payload 顺序
[PASS] 时间转换正确
[PASS] 列名/文案无误导性 settlement/prediction 文案
[PASS] 无交易按钮/开仓票据
[PASS] 资金费率格式化 7 个样例
[PASS] formatFundingRate / formatBeijing* 函数体未变
[PASS] 自动刷新 60s 与倒计时元素存在
[PASS] 路由/资产/负费率状态列显示「英文枚举(中文解释)」格式
[PASS] 侧栏品牌已中文化
[PASS] 手动刷新后 60s 自动刷新计时器重调度，倒计时计时器保持独立
[PASS] 优雅降级：新字段缺失不白屏，日费率 —，间隔不显示

全部自检通过
```

---

## 3. 自查表

| # | 检查项 | 状态 |
|---|---|---|
| 1 | 仅修改 `frontend/index.html`、`frontend/self-check.js` 与本 stage 报告 | ✅ |
| 2 | `backend/**` / `schemas/**` / `docs/api/**` / `reports/api-samples/**` 零触碰 | ✅ |
| 3 | 拆列：存在独立「资金费率」「结算时间」，合并列消失 | ✅ |
| 4 | 新列「日费率」渲染 `daily_funding_rate`，null → `—` | ✅ |
| 5 | 结算间隔以 `8h/4h/1h` 行内徽标展示 | ✅ |
| 6 | 零排序逻辑：无排序按钮/比较器/状态，payload 顺序渲染 | ✅ |
| 7 | 新字段缺失时优雅降级（不白屏） | ✅ |
| 8 | 不消费 `borrow_validation` 任何字段 | ✅ |
| 9 | `formatFundingRate` / `formatBeijing*` 逻辑零改动 | ✅ |
| 10 | 无新依赖、单文件、同源 API、无 parseFloat/Number×100 展示 | ✅ |
| 11 | 中文口径：枚举三列保持「英文(中文)」，其余纯中文 | ✅ |
| 12 | `node frontend/self-check.js` 全 PASS | ✅ |
| 13 | 未提交、未修改 `status.json` | ✅ |

---

## 4. 文件列表

- `frontend/index.html`（修改）
- `frontend/self-check.js`（修改）
- `reports/agent-runs/2026-07-phase2-borrow-sort-v1/20-implementation-frontend.md`（本报告，新增）

---

## 5. 等待事项

- 等待 bookkeeper 统一提交（H_fix 或 H_B）。
- 等待嵌入预审 round 1（fresh Claude-GLM 只读会话复审 Task B）。

本地北京时间: 2026-07-04 21:42 CST  
下一步模型: Claude-GLM（嵌入预审 Task B）  
下一步任务: 由 controller/bookkeeper 调度 `pre-review-task-b-by-glm.prompt.md`

# Session changelog — 2026-07-22 market table: 近24h / 可开优先 / 净收益过滤

Status: **验收通过**（本地确定性自检，2026-07-22 14:29 CST）  
Owner: User / Grok（实现会话）  
Decisions: `docs/planning/DECISIONS.md`（`DEC-2026-07-22-004` … `006`）

本文件记录本轮**市场表**产品改动，便于续聊与验收对照。非正式 Harness stage
黑板；正式 stage 证据仍在 `reports/agent-runs/`。

---

## 验收结论

| 检查项 | 结果 | 证据命令 |
|--------|------|----------|
| 前端 self-check | **PASS · 全部自检通过** | `node frontend/self-check.js` |
| 近 24h 列 | **PASS** | `[PASS] 近 24h 列格式化（3 位小数，null→—）` |
| 可开优先 re-rank | **PASS** | `[PASS] 可开优先展示 re-rank（…）` |
| 日净收益过滤（有符号） | **PASS** | `[PASS] 低日净收益过滤 UI 行为（有符号 ≤0.03%；大负值隐藏；null 不过滤）` |
| 日费率过滤（abs） | **PASS**（既有） | `[PASS] 低日费率过滤 UI 行为（…）` |
| 后端 funding 窗口 | **30 passed** | `.venv/bin/python -m pytest backend/tests/test_funding_history.py -q` |

**判定：本轮改动本地验收通过。**  
（未推远程、未合 formal stage seal；工作区仍为未提交 diff，除非用户另行要求 commit。）

---

## 产品能力总览

### 1. 列：近 24h

| 项 | 约定 |
|----|------|
| 位置 | 「年化 24h」**左侧** |
| 字段 | `funding_sum_24h`（snapshot 行，additive） |
| 含义 | 最近 24h **已结算费率之和**（**非年化**） |
| 窗口 | 闭区间 `[data_time−24h, data_time]`，两端各计 **一次** |
| 展示 | 百分比 **3 位小数**；空窗口 → `—` |
| 契约 | schema optional；前端缺字段 normalize 为 `null`（不整页阻塞） |

### 2. 筛选：可开优先展示

| 项 | 约定 |
|----|------|
| 位置 | 过滤条右侧 checkbox |
| 默认 | **勾选** |
| 性质 | **re-rank only**（不新增隐藏条件；不打后端） |
| 顺序 | 现有筛选 → 可见集 → 勾选时拆 A/B |
| **A 组（可开）** | ① 正费率；或 ② 负费率且 `verified` + pair 可借 + **`max_borrowable > 0`** |
| **不进 A** | 可借 0 / null / 未探测；费率=0 不特判（交由费率/净收益过滤） |
| **route** | **不对** `PERP_ONLY` / 现货腿加额外 gate；是否可见只看现有「显示 PERP_ONLY」 |
| A 排序 | `net_daily_yield` DESC；无 net 时 \|日费率\| DESC；同值 symbol ASC |
| B 排序 | 保持筛选后 payload **相对顺序** |
| 关开关 | 纯筛选序 = payload 相对序 |

### 3. 筛选：隐藏 日净收益 ≤ 0.03%

| 项 | 约定 |
|----|------|
| 文案 | **隐藏 日净收益 ≤ 0.03%**（**无** `|…|`，避免 abs 误解） |
| 默认 | **勾选** |
| 语义 | **有符号**：`net_daily_yield ≤ 0.00030000` → 隐藏 |
| 含 | 全部负值、0、≤0.03% 的正净收益 |
| 不含 | `net > 0.03%` 显示；**`null` 不隐藏** |
| 实现 | `netYieldAtOrBelowThreshold`（BigInt，无 float） |

### 4. 筛选：隐藏 |日费率| ≤ 0.03%（保持）

| 项 | 约定 |
|----|------|
| 文案 | 保留 **`|日费率|`** |
| 语义 | **绝对值**：`|daily_funding_rate| ≤ 0.00030000` → 隐藏 |
| 实现 | `absDailyRateAtOrBelowThreshold`（不变） |
| 与净收益 | **独立叠加**；两开关可同时开 |

### 语义对照（易混点）

| 原始值（展示） | \|日费率\| 过滤 | 日净收益 过滤（有符号） |
|----------------|-----------------|-------------------------|
| +0.029% | 藏 | 藏 |
| −0.029% | 藏 | 藏 |
| −0.031% / −0.1% | **显示**（\|x\|>0.03%） | **藏**（x≤0.03%） |
| +0.031% | 显示 | 显示 |
| null | 不藏 | 不藏 |

---

## 代码落点

| 区域 | 路径 | 变更 |
|------|------|------|
| 窗口求和 | `backend/domain/snapshot.py` | `_sum_funding_in_window` / `compute_funding_sum_window`；行字段 `funding_sum_24h` |
| Schema | `schemas/api/public-market/snapshot.schema.json` | additive `funding_sum_24h` |
| 后端测试 | `backend/tests/test_funding_history.py` | 24h 两端 inclusive + build_rows 发射 |
| 市场表 UI | `frontend/index.html` | 近 24h 列；可开优先；净收益过滤；筛选/re-rank 全前端 |
| Fixture | `frontend/fixture/public-market-snapshot.json` | 行补 `funding_sum_24h` |
| 自检 | `frontend/self-check.js` | 列/过滤/re-rank 向量 |

### 前端关键函数

- `absDailyRateAtOrBelowThreshold` — 仅日费率 abs  
- `netYieldAtOrBelowThreshold` — 仅日净收益有符号  
- `isOpenablePreferredRow` / `displayRows` — 可开 A/B re-rank  
- `filteredRows` — 纯过滤（含两套阈值）；`displayRows` 再 re-rank  

---

## 明确未改

- 后端 sort / 新 query API（筛选与可开优先仍只吃现有 snapshot）  
- 借币执行 / 下单  
- formal dual-review stage seal / 远程 push（除非用户另指令）  

---

## 工作区状态（落档时点）

```text
分支: main（相对 origin/main 本地未提交）
变更文件:
  backend/domain/snapshot.py
  backend/tests/test_funding_history.py
  frontend/fixture/public-market-snapshot.json
  frontend/index.html
  frontend/self-check.js
  schemas/api/public-market/snapshot.schema.json
统计: +709 / −94（约）
```

---

## 复验命令

```bash
node frontend/self-check.js
.venv/bin/python -m pytest backend/tests/test_funding_history.py -q
```

# 12：review-1 verdict —— **ACCEPT**（grok / xai，2026-07-31 16:59:36 CST）

受审区间：`base_sha = 42de1aff364e7c979d2fbb5dc56f1dec65287cc7` ..
`delivery_sha = b14f55ce8c264635860bd5b54d61229b17bd9faa`。评审者声明未移动 `HEAD`、
未读工作树。

`评审结论: ACCEPT（接受）`，`阻塞项: none`，**无 in-range 发现**，不递增
`rework_count`（仍为 0）。

隔离披露（评审者原样给出）：review-1 与本 stage 计划评审 r1-r3 同为 grok / xai，已参与
计划批准；跨 provider 相对实现作者成立（xai ≠ zhipu_glm）；最终计划批准方为 DeepSeek
r4，非本会话。

## 五项判断（全部成立）

| Goal | 结论 | 要点 |
|---|---|---|
| 1 钱的展示口径 | 成立 | 均价/数量仅走 `hedgeText` + `escapeHtml`；`order_id` 判空门控三格；时间门控；部分成交不清空行；错误回退无编造；全路径 `escapeHtml`，无注入面 |
| 2 `task_id` 读路径 | 成立 | 早返回只调三个既有只读方法直接 `return 200`，不进分页/写路径；参数化 SQL 无注入；`logs`/`entries` 空对既有消费方安全；完全不走两套游标，不重演 R4 |
| 3 测试锁住行为 | 成立 | 86a 锁四状态/尾零透传/单腿行 muted 恰 3/错误三链/进展/toggle/fake 残留；86b 锁 51 条全量、URL 无 `entries_cursor`、倒序首行 51；pytest 含 NULL 透传与跨任务隔离 |
| 4 接缝与既有代码 | 成立且为正向修复 | `'warning'→'warn'` 修复失效样式，共用常量使既有时间线卡徽标一并生效；`attempt_to_doc` 为加性投影，既有测试用子集断言，`normalizeHedgeAttempt` 不依赖新字段 |
| 5 边界 | 未超出 | 交付提交 6 文件全在 Allowed Files；未改 `store.py`/状态机/结算/写路径；区间内其它提交为阶段控制文档，按 §8 属上下文 |

## 对 Bookkeeper 五条观察项的独立裁定（全部非阻塞）

| ID | 评审者裁定 |
|---|---|
| O-A | 描述不精确；测试锁的是「前端不加工」，有效。非缺陷 |
| O-B | 1+N 查询，本地 SQLite 当前量级可接受，不必在本 stage 改 join |
| O-C | 声明的可推翻项；唯一消费方只读 `attempts` |
| O-D | `target_n` 缺失时显示 `4/`；展开前提是卡在列表，难触发 |
| O-E | 均价 `—` 三源难分，数量列可辨；交 review-2 / Human 作 UX 判断 |

评审者另指出两处**未覆盖但不可达**：`order_id` 的数字假值（后端列为 TEXT，不可达）；
`confirmed_failed` 且三个错误字段全空（该路径已由 `single_leg` 用例覆盖）。

## 范围外（评审者按 §8 三分类标注，不阻塞本交付）

- `[MONEY-ACCURACY]` 本地 `quote/base` 均价 vs 交易所 `avgPrice`：需 schema + 写路径，
  已记入 `PROJECT_STATE.md`，跨 stage。
- 「任务卡卡住」全套：已移出本 stage（`06-scope-reduction.md`）。

## Bookkeeper 核验

**已封存。** 回执携带完整正文、逐项依据与发现清单（本轮无 in-range 项），符合
`AGENTS.md` §7；`问题记录` / `修复要求` 均为 `inline-full-text` 且正文随回执交出——
本 stage 前四轮评审中有两轮因正文缺失无法封存，本轮未重演。

抽查评审者的两条事实判断（防止照单全收）：

- 「`order_id` 列为 TEXT，不会出现数字假值」→ 复核 `store.py:89` `order_id TEXT`，属实。
- 「`"0"` 在前后端都视为已受理，口径一致」→ 复核 `domain.py:995`
  `return bool(leg.get("order_id"))`，Python 中 `"0"` 为真；前端判空条件是
  `null / undefined / ''`，`"0"` 同样视为已受理。两端口径确实一致，属实。

`rework_count` 保持 **0**：本轮 `ACCEPT`，无修复轮。

`ACCEPT` 不等于合并授权（`AGENTS.md` §9）。

## 下一步

review-2（`codex` / openai，`reality-checker`），锚定同一区间
`42de1aff..b14f55ce`。dispatch 见 `13-review-2.dispatch.md`。

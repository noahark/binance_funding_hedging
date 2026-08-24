# Hyperliquid 费率对比行 v1 — 实现 dispatch（claude_glm）

## Identity

- task_id: `hyperliquid-funding-compare-impl-claude-glm`
- target_role: `Implementer`
- target_model: `claude_glm`
- provider: `zhipu`
- status_revision: `5`
- required_reading: `agents/developer-discipline.md`
- required_skill: `agents/skills/senior-developer.md`（**只读这一个**，不要同时加载 repair skill）

## 基线

- 分支：`2026-08-23-hyperliquid-funding-compare-v1`（已存在，直接在其上工作）
- 实现基线 SHA：`dd1283398efcccfc3ddd6c1c5e281076b97c3427`（当前 HEAD）
- **设计权威**：`docs/planning/hyperliquid-funding-compare-v1.md` **rev3**
  （固定于 `fe91abb69e236e9ef110ca354b8773dfcb042773`，已通过 Codex 独立设计评审 `ACCEPT`）

设计稿是本任务的唯一需求来源。**不得自行扩大范围、不得引入设计稿未列的抽象**。
若发现设计稿有错或不可实现，停下报告，不要自行改设计。

## Goal

在既有「费率行情」表的前四个费率列内，每行下方增加一行 Hyperliquid 同口径数值；
市场表下方追加「HL 数据时间」并在不可用/陈旧时红色高亮。**只读展示，
不触碰下单、保证金、借币、平仓、账户的任何路径。**

## 已决策项（D1–D8，Human 已全部确认，不得推翻）

见设计稿 §10。实现时特别注意：

- **D6**：main + xyz 两个 POST 为**原子组**——任一失败 / 任一 shape 非法 /
  任一标的 `funding` 无法转 Decimal → 本轮 HL **整源失败**，全部行 `hyperliquid: null`，
  `hyperliquid_data_time` 为 `null`，**不投影 warm last-good**。币安四列首行照常显示。
- **D8**：失败信号是 `hyperliquid_data_time` 时间戳 + 红色高亮，**不是** warning token。
  不要新增 warning 文本机制。

## 实现审查点（Codex 复评带出，必须处理）

**IC-1 — schema 顶层 `additionalProperties: false`**

`schemas/api/public-market/snapshot.schema.json` 顶层是 `additionalProperties: false`，
required 为 7 项。因此：

- **必须**把 `hyperliquid_data_time` 注册进顶层 `properties`（不注册 → 直接被 schema 拒）；
- **不得**加入顶层 `required`（加了 → 既有 offline fixture 全部打挂）；
- producer 侧则**恒显式输出**该字段（string 或 `null`），由 A7–A9c 保证。

行内 `hyperliquid` block 同理：注册但**非 required**，允许 `null`。

**IC-2 — `isStaleTime(NaN)` 返回 false，且现有实现染整行**

- `isStaleTime` 现为 `Number.isFinite(ms) && now - ms > STALE_TIME_MS`。
  `Date.parse(null)` → `NaN` → 返回 **false**。
  所以「取不到」这个最该标红的状态，只调该函数**不会红**。
  必须把 unavailable（字段为 `null` / 非法 ISO）**显式**纳入 `.stale-time` 条件。
- 现有 `market-snapshot-meta` 是给**整个元素**加类
  （`els.marketSnapshotMeta.className = 'subtitle stale-time'`）。
  照抄会导致 HL 挂掉时把同一行里**仍然新鲜的币安时间一起染红**，等于谎报币安有问题。
  必须把「HL 数据时间」拆成独立 `<span>`，红色只作用于该片段。

## 行为澄清（避免自作主张）

- HL 是**独立 source_id**、60s 组、与 `premium_index` 同频。
- 「更新缓存」按钮（`force_account_panels=True`）**不刷 HL** ——
  它只放宽账户/估值面板组的 due 检查，`premium_index` 等公共源保持各自 due 行为。
  HL 继承同样行为，**不要**把 HL 加进该按钮的强制刷新集合。
- 前端读快照是纯读，零上游请求。**不要**为 HL 增加任何前端直连或按需拉取。

## 文件边界（设计稿 §7；只改这些）

| 文件 | 改动 |
|---|---|
| `backend/adapters/`（新增 HL 公共适配器） | 新文件，形制参照 `binance_public.py` |
| `backend/domain/normalize.py` | 新增 `HL_SYMBOL_DENY` 常量 |
| `backend/domain/snapshot.py` | `build_rows` 新增入参与 `hyperliquid` block |
| `backend/services/snapshot_service.py` | 独立 HL source_id + 失败语义 + 顶层时间字段 |
| `backend/config.py` | HL base_url、超时 |
| `schemas/api/public-market/snapshot.schema.json` | 顶层 `hyperliquid_data_time` + 行内 block（均非 required，见 IC-1） |
| `frontend/index.html` | 四个 `<td>` 加第二行 + 开关 + meta 行 HL 时间独立 span（见 IC-2） |
| `frontend/self-check.js` | 15 列断言修订 + HL 数据时间元素断言 |
| `docs/api/public-market-contract.md` | 登记新 row block、顶层字段、空值与失败语义 |
| `backend/tests/` | 覆盖下列验收 |

若确需依赖注入而改动 `backend/app/server.py`，**先停下报告**，不要自行扩边界。

**禁止触碰**：任何下单、保证金、借币、平仓路径；`SPOT_SYMBOL_MAP` 现有条目；
币安侧费率与年化的既有算法（`funding_interval_hours` 驱动的折算必须逐格不变）。

## 自测（设计稿 §9 全部 18 条，逐条给证据）

A1 DENY / A2 synthetic 新跨类别撞名 / A3 HYPE 有 HL 行 / A4 币安四列逐格不变（回归）/
A5 4h 与 8h 各自年化正确 / A6 Binance-only fixture → `null` /
A7 冷启动失败（时间戳 `null` + 页面标红）/ A8 success→failure（不留旧值旧时间）/
A9 非法 funding → 整源失败同一 oracle / A9b 成功但无匹配 → 时间戳有值不标红 /
A9c offline 零网络 + 全 `null` + 标红 + schema 通过 /
A10 三值均 decimal string / A11 结算时间第二行恒「每小时」/ A12 别名+乘数 14 个为 `—` /
A13 一次成功刷新恰好两次 POST、任一次最多两次、失败短路不发第二个、
`predictedFundings` 零调用 / A14 开关默认开且关闭后恢复 / A15 `HL`/`HL·xyz` 标签且不参与
筛选排序借币开单 / A16 `self-check.js` 通过

另需运行既有后端测试套件，**证明零回归**。

## Allowed Files

上表所列文件 + 下面唯一 create-only handoff：

- `reports/agent-runs/2026-08-23-hyperliquid-funding-compare-v1/evidence/hyperliquid-funding-compare-impl-claude-glm.handoff.md`
- 该路径开始前不存在（Bookkeeper 预检 2026-08-23 CST：ABSENT）。
- **不得**修改：设计稿、`status.json`、`ACTIVE.json`、三份既有 handoff、任何既有 dispatch。

## Commit

**授予提交权**：在本分支提交实现与测试。commit message 用中文说明改了什么、为什么。
**不得**合并到 main、不得推送、不得部署、不得启停服务。

## Stop Point

实现 + 自测 + handoff + `TASK_RESULT` 后停止。
你可以把自己的任务从 `dispatched` 改为 `reported`，**不得**写 `verified`、
不得选择下一个 actor、不得宣告验收。交付后按 `HIGH_RISK` 路由走 Review-1 / Review-2。

reply_to: claude
After emitting the normal console receipt, send that same receipt once to the
reply_to window per this file, then stop.

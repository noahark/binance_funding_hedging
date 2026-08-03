# 任务拆分 — `spot-order-routing-cap-display-v1` 实现阶段

阶段：`2026-08-02-spot-order-routing-cap-display-v1`
作者：Opus5（Planner，task-breakdown-1）
日期：2026-08-03
基线：`main` @ `1a55781`（= `status.json.base_sha`，本次拆分不改变它）

前置：方案 `docs/planning/spot-order-routing-v1.md` 已获 DeepSeek 跨 provider 计划评审
`ACCEPT`（`evidence/plan-review-2.deepseek.raw.md`）。计划评审 `ACCEPT` 只关闭计划闸门，
不授权实现、开闸或实盘。

## 1. 产物

| 文件 | 作用 |
| --- | --- |
| `implementation-interface-v0.9.md` | 实现前接口约定：`collateral_cap` 形状、三态真值表、`ui_flags` 值、`checked_at` 规则、匹配口径、缓存边界、前后端禁令 |
| `implementation-backend-2.dispatch.md` | 后端任务（`claude_glm` / `zhipu_glm`） |
| `implementation-frontend-1.dispatch.md` | 前端任务（`Grok` / `xai`） |
| `task-breakdown-1.md` | 本文：顺序、边界、测试、接缝验收、评审路由 |

`implementation-backend-1.dispatch.md` 已被 Human 指令取代，**不修改、不复用、不投递**，仅作
被替代范围的历史留档。

## 2. 执行顺序（严格串行，四道门）

```
[门 0] Human 交付 task-breakdown-1 回执 → Bookkeeper 核验四份产物
   ↓
[T1] implementation-backend-2（claude_glm）
     实现后端全部范围 → 跑指定 pytest → 一个本地提交 → 回执含提交 SHA
   ↓
[门 1] Bookkeeper 核验后端回执，在 status.json 固定该提交 SHA（前端的启动前提）
   ↓
[T2] implementation-frontend-1（Grok）
     只读该已提交的 v0.9 契约 → 静态 UI + fixture + self-check → 一个本地提交
   ↓
[门 2] Bookkeeper 核验前端回执，置 delivery_sha = 前端提交 SHA
   ↓
[T3] review-1（跨 provider，只读）→ 必要时修复轮 → 重跑 review-1
   ↓
[T4] review-2（跨 provider，只读）
   ↓
[门 3] Human 决定合并 / 部署 / 实盘（模型不得代行）
```

**为什么串行**：前端消费的字段形状由后端写进
`docs/api/public-market-contract.md` v0.9 amendment；并行会让前端对未提交字段臆测，
正是方案 §6.5 要防的跨 seam 漂移。

**为什么前端不等 review-1**：Human 已裁定顺序为「后端提交 + 固定 SHA 后即可启动前端」。
残余风险与缓解见 §7。

## 3. 文件边界（互不重叠）

| 域 | backend-2 | frontend-1 |
| --- | --- | --- |
| `backend/domain/**` | ✅ `normalize.py`、`snapshot.py` | ❌ |
| `backend/services/**` | ✅ 4 个文件 | ❌ |
| `backend/hedge_open_tasks/**` | ✅ 3 个文件 | ❌ |
| `backend/tests/test_*.py` | ✅ 11 个文件 | ❌ |
| `backend/tests/fixtures/**` | ❌（两边都不许改） | ❌（用 self-check 内存注入） |
| `docs/api/public-market-contract.md` | ✅ 写 v0.9 amendment | ❌ 只读 |
| `schemas/api/public-market/snapshot.schema.json` | ✅ | ❌ 只读 |
| `schemas/api/public-market/symbol-snapshot.schema.json` | ❌（经共享 `$ref` 自动继承） | ❌ |
| `frontend/index.html` | ❌ | ✅ |
| `frontend/self-check.js` | ❌ | ✅ |
| `frontend/fixture/public-market-snapshot.json` | ❌ | ✅ |
| `backend/app/server.py` | ✅ 仅组合根创建并注入只读名单 client；不改 Start gate | ❌ |
| `backend/config.py` | ❌ 不在边界内，需要即停 | ❌ |
| `status.json`、`PROJECT_STATE.md`、阶段记录 | ❌（Bookkeeper 域） | ❌ |

两份 Allowed Files **零交集**。共享的 JSON 形状只在 `implementation-interface-v0.9.md` 中详细
定义；**对外最终权威是后端交付写入的 `docs/api/public-market-contract.md` v0.9 amendment**，
接口文档不是对外契约。

`backend/tests/fixtures/private-account-v1-design.json` 是 self-check 实际加载的 fixture，
但它属后端测试资产；前端按既有 `opening_quotes` 先例在 self-check 内**内存注入**，
两个任务都不改它——这是上一阶段
（`2026-07-bookticker-open-columns-v1` 开发拆分 §边界）已抓到过的越界点。

## 4. 各自测试

**backend-2**（原样执行，回执附原始结论）：

```
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  backend/tests/test_hedge_domain.py backend/tests/test_hedge_open_live_client.py \
  backend/tests/test_hedge_preflight_provider.py backend/tests/test_live_hedge_executor.py \
  backend/tests/test_hedge_service.py backend/tests/test_hedge_store.py backend/tests/test_hedge_api.py \
  backend/tests/test_snapshot.py backend/tests/test_background_worker.py \
  backend/tests/test_symbol_snapshot_endpoint.py backend/tests/test_negative_schema.py \
  backend/tests/test_service_health.py -q
```

外加 `git diff --check`。全部验证使用 fake transport：不使用真实凭证、不调用 Binance、
不改 Start gate、不做实盘调用。

**frontend-1**：

```
node frontend/self-check.js
```

两个任务的具体断言清单见各自 dispatch 的 Acceptance Checks。

## 5. 前后端接缝验收（任一单侧测试都证明不了，须在 review-1 显式核对）

| # | 接缝 | 后端侧责任 | 前端侧责任 | 核对方式 |
| --- | --- | --- | --- | --- |
| S1 | flag 字面量 | 发射 `COLLATERAL_CAP_EXCEEDED` / `COLLATERAL_CAP_UNKNOWN` | 用 `includes()` 判同名字符串，不依赖顺序 | 两侧字面量逐字比对 |
| S2 | 三态 + 不适用 | 四字段组合一致，表外组合不可能发射 | 有序判定规则，表外组合按未知 | 对齐接口文档 §3 真值表 |
| S3 | `checked_at` | 全表同值、成功时刻、`YYYY-MM-DDTHH:MM:SSZ` | 只在一处渲染北京时间，null → 「未知」 | 断言 + 契约文字 |
| S4 | 判定资产 | 发 `collateral_cap.asset`（bStock = `TSLAB`） | 直接用它，绝不自行推导 | 前端 DOM 断言 + 后端 bStock 用例 |
| S5 | 可选字段 | 每行**总是**发键；schema 中为 optional | 不进 `REQUIRED_ROW_FIELDS`，缺键降级不抛错 | 冻结样本 schema 校验 + 前端缺键断言 |
| S6 | 缓存隔离 | 预检新读、展示读缓存、互不回填 | 完全不触碰预检面 | 后端专门测试（方案 §9 #11） |
| S7 | 不按方向过滤 | 后端不按费率符号过滤 | 前端不按费率符号过滤 | 两侧各一条断言 |
| S8 | 匹配单点 | 一处纯函数，两条路径共用 | 不实现任何匹配逻辑 | review-1 查重复实现 |

**已知覆盖缺口**：本 stage 不授权启动服务或实盘，因此**没有真实后端输出喂给真实前端**的运行时
联调；接缝只在测试 + 评审阅读层面收口。这一条须原样进 review-2 的风险判断，不要在回执里
说成「端到端已验证」。

## 6. 评审路由（固定 `base_sha..delivery_sha`）

- `base_sha` = `1a55781a5f80ee5b3e15d7124003af2dda73f0d5`（不变）。
- `delivery_sha` = **前端提交 SHA**（区间同时包含后端提交）。评审锚定 Bookkeeper 写入
  `status.json` 的固定区间，不移动 `HEAD`、不看未提交工作区。
- 区间内的 dispatch / `status.json` / 阶段报告是**上下文而非受审交付**（AGENTS.md §8 评审范围口径）。
- 全 stage 为 `HIGH_RISK`（订单路由 + 公共契约变更）：**review-1 + review-2 都必须跑**，
  展示部分不因「只读」单独降级。

**provider 隔离结论（本轮两位实现作者分属不同 provider，路由比平时窄）：**

| 角色 | 建议模型 | 理由 / 约束 |
| --- | --- | --- |
| review-1 | **Kimi（`moonshot`）**，技能 `agents/skills/code-reviewer.md` | 与后端作者 `zhipu_glm`、前端作者 `xai` 都不同源；`roles.md` 亦以 Kimi 为 `claude_glm` 实现的首选 review-1 |
| review-1 备选 | DeepSeek 或 Codex（Human 定） | **`roles.md` 的常规备选 Grok 4.5 本轮不可用——Grok 是前端作者**；`claude_glm` 同理不可用 |
| review-2 | **DeepSeek（`deepseek`）**，技能 `agents/skills/reality-checker.md` | 与两位作者都不同源，且未参与本 stage 的设计（只做过只读计划评审），最贴合 `roles.md`「优先选未参与设计的最终评审者」 |
| review-2 备选 | Opus5（`anthropic`，`roles.md` 默认） | 合规，但方案正文与本拆分均由 Opus5 落笔，属设计参与，**须在评审中显式披露** |

- 一次 review-1 覆盖整个区间（而非前后端各一次）：接缝正是风险所在，分开评审会让 §5 的
  S1–S8 无人负责（决策 §B-6）。
- review-1 `REWORK` → 由**原作者**修复 → 重跑 review-1。
- review-2 的窄发现 → 修复 + 重测 + 新提交后**直接回 review-2**；若修复扩大文件、改契约或
  加风险，须重过 review-1。
- `rework_count` 绑**交付物**：后端交付与前端交付各自计数，改名或拆分修复任务不清零；
  上限 3，超出由 Human 决定收窄 / 重设计 / 接受限制 / 停止。规则原文在 AGENTS.md §8，本文不重述。
- 任何评审 `ACCEPT` 都不合并、不部署、不开闸、不替代 Human 最终验收。

## 7. 风险与已知取舍（须原样上交，不得在回执里粉饰）

1. **前端先于 review-1 落地**：若 review-1 判定后端字段形状需改，前端可能返工。缓解：形状已由
   `implementation-interface-v0.9.md` 冻结并经 Bookkeeper 核验；预期评审发现集中在实现层而非形状层。
2. **无运行时联调**（§5 覆盖缺口）。
3. **接口文档的五项细节已获 Human 裁定**（I-1..I-5，见接口文档 §9）。其中 I-1 为「任意刷新失败
   即未知」，I-2 为「无现货腿不适用」；两项都不放宽 §3 预检的新读要求。
4. **展示读取依赖 hedge API key**：offline 或该 key 缺失/失效时全表「未知」（接口文档 §10）。
   它独立于下单 executor 与 private channel；这是诚实降级，但操作者会看到一整列「未知」。
5. **`PROJECT_STATE.md` 既有 live 风险不变**：Start gate 可能仍是 live、无平仓能力、
   `[ACCEPTED-CONFIGURATION-RISK]` 的裸空链条依旧成立。本 stage 不改变其中任何一条。

## 8. 给 Bookkeeper 的落盘提示

- 两份 dispatch 的 `status_revision` 分别预填 **6**（backend-2）与 **7**（frontend-1）；
  投递前请以当时实际的 `status.json.revision` 为准校对后再交付。
- `status.json` 的 `current_task` 一次只指向一个任务；前端 dispatch 在门 1 之前不投递。
- 门 1 需要把后端提交 SHA 写进阶段状态（前端 dispatch 的启动前提就是它），
  `delivery_sha` 在门 2 才置为前端提交 SHA。
- 本拆分不修改任何方案、契约、schema、代码、状态或证据，也不授权任何实现或实盘。

# Development Breakdown — Fake Borrow-Task v2 + Minimum-Borrow Contract Amendment

- Stage: `2026-07-borrow-task-ui-fake-v1`（MEDIUM）
- Breakdown author: Claude（Anthropic / `claude-fable-5`，design involvement，review-2 披露适用）
- 输入：`00-intake.md`、`00-task.md`、`10-design.md`、`11-adr.md`、`13-scope-amendment-v2.md`、`14-user-min-borrow-contract-amendment.md`、`30-review-1.md`、`status.json`、`AGENTS.md`、`agents/developer-discipline.md`
- 代码锚点（写作时核实）：`backend/services/private_client.py:235-274`（`fetch_classic_reference`）、`backend/domain/snapshot.py:776-800`（`_max_borrowable_value_usdt`）、`backend/domain/snapshot.py:992-1098`（`assemble_borrow_validation`）、`schemas/api/public-market/snapshot.schema.json:431-452`（`classic_margin`）、`frontend/index.html:1557`（`placeholder="如 1000"`）

## 0. 旧 review-1 的处置

`30-review-1.md` 的 ACCEPT 只覆盖 `d9c2772..edb2002`，已被用户批准的 `13-scope-amendment-v2.md` 与 `14-user-min-borrow-contract-amendment.md` **取代（superseded），不再是有效的通过门**。全部新实现完成后必须发起全新 review-1 与 review-2，覆盖 `base_sha d9c2772..新 head` 的完整阶段 diff 并重算 fingerprint。

旧 ACCEPT 中的两条 P3（60 秒表格重渲染清空未提交输入；`role="button"` 行内嵌可聚焦控件）保留为**可选评审输入**，不是本次强制修复项——除非实现者在开发中发现其与新需求直接冲突（例如筛选/编辑触发的重渲染显著放大 P3-1），冲突时在实现报告中说明并按新需求语义处理。

## 1. 任务切分与依赖顺序

两个依赖有序的实现任务，串行执行（本阶段 `parallel_mode.enabled=false`，不适用 R10/R4）：

1. **Task B1 — 后端最小借币量契约扩展**：owner **Claude-GLM**（`zhipu_glm` / glm-5.2，经 Claude Code 适配器）。
2. **Task F2 — 前端任务状态机/筛选/编辑 + 最小借币量占位符**：owner **Kimi**（`kimi-code/kimi-for-coding`）。

**依赖**：F2 的占位符子项消费 `rows[].borrow_validation.classic_margin.user_min_borrow` / `user_min_borrow_value_usdt`，该字段由 B1 落地。B1 必须先完成并由 bookkeeper 在 stage 分支上提交（含 schema、fixture、raw sample、测试全绿）后，才能派发 F2。F2 不得自行修改后端/schema 来"解锁"字段。

**评审路由（供 bookkeeper 落入 `model_routing`）**：本阶段出现双实现者，review-1 按任务切分做 provider 级交叉：B1（实现者 `claude_glm`）由 **Kimi** 评审；F2（实现者 `kimi`）由 **Claude-GLM** 评审。review-2 为最终门，须与两个实现者 provider 隔离（默认 GPT/Codex）。注意：designer 为 Codex、breakdown author 为 Claude，两个决策模型均有设计参与；review-2 按 AGENTS.md 的 strong-reviewer disclosure override 路径记录 `reviewer_prior_involvement`，这是 bookkeeper 的既有流程，不由实现者处理。

**证据路径细化（仅证据文件，产品文件边界不变）**：`00-task.md` 只列了单一 `20-implementation.md` / `60-test-output.txt`；因本阶段拆为两个实现终端，为避免互相覆盖，细化为：

- B1：报告 `21-implementation-backend.md`，测试输出 `61-test-output-backend.txt`
- F2：报告 `22-implementation-frontend-v2.md`，测试输出 `62-test-output-frontend-v2.txt`
- v1 的 `20-implementation.md` / `60-test-output.txt` 保持为历史证据，不追加不改写。

## 2. Task B1 — 后端最小借币量契约扩展（Claude-GLM）

### 2.1 Allowed files

- `backend/services/private_client.py`
- `backend/domain/snapshot.py`
- `backend/tests/test_private_client.py`
- `backend/tests/test_private_account_v1.py`
- `backend/tests/test_phase2_borrow_sort.py`（仅当断言受新必填字段影响需要同步 fixture 时）
- `backend/tests/fixtures/private-account-v1-design.json`
- `schemas/api/public-market/snapshot.schema.json`
- `reports/api-samples/2026-07-borrow-task-ui-fake-v1/sapi-v1-margin-allAssets.json`（新增，见 2.4）
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/21-implementation-backend.md`、`61-test-output-backend.txt`

### 2.2 Forbidden

- `frontend/**`、`docs/**`、`workflows/**`、`agents/**`、canonical API 文档
- 不新增任何 endpoint、签名写操作、借币/还币执行、重试、存储、外部副作用
- 不改动 `portfolio_account.max_borrowable_value_usdt` 的八位小数契约，不复用 `_quantize_rate`（8dp）来量化新值
- 不伪造非零 `userMinBorrow` raw sample（现有公共样例全为 `"0"`，这是事实，不许"修正"）
- 不碰 `status.json` / `70-handoff.md`（bookkeeper 专责）；不 commit

### 2.3 数据契约（冻结自 `14-user-min-borrow-contract-amendment.md`）

映射链，字段名逐字：

```text
allAssets[i].userMinBorrow (string, key assetName)
  → classic_ref.user_min_borrow_by_name[assetName]
  → rows[].borrow_validation.classic_margin.user_min_borrow
  → rows[].borrow_validation.classic_margin.user_min_borrow_value_usdt
```

- **采集**：`fetch_classic_reference`（`private_client.py:261-274` 返回 dict）新增 `"user_min_borrow_by_name": {assetName: userMinBorrow}`，**保留原始十进制字符串**，不做 bool/float/Decimal 转换；条目缺 `userMinBorrow` 字段时该 key 映射为 `None`（或不落 key，装配侧统一 `get` 出 `None`）。
- **装配**（`assemble_borrow_validation`，`snapshot.py:992-1098`）查找门与 `asset_borrowable` 完全一致：
  - `classic_ref is None`（私有通道关闭/失败分支）：`user_min_borrow` 与 `user_min_borrow_value_usdt` 均为 `null`；
  - `pair_listed` 为 false 或缺失：两字段均为 `null`；
  - 否则 `user_min_borrow = user_min_borrow_by_name.get(base_asset)`，保留原始字符串，key/字段缺失时为 `null`；
  - `borrowability_truncated` 分支（`snapshot.py:1054-1077`）**保留**这两个 classic-reference 字段，与该分支保留 `asset_borrowable`/利率字段的方式一致；只有 `portfolio_account` 金额字段被清空的现状不变。
- **估值** `user_min_borrow_value_usdt`：仅当 raw 是合法 Decimal 时计算；复用与 `_max_borrowable_value_usdt`（`snapshot.py:776-800`）相同的路由规则——`_STABLE_USD_ASSETS`（USDT/USDC）按 1 计价，其余用 `price_map[f"{asset}USDT"]`；价格缺失/非法或 raw 非法 → `null`；不 emit warnings（对齐 `_max_borrowable_value_usdt` 的无告警立场）。量化用 `Decimal` + `ROUND_HALF_UP` 到**恰好两位小数**（如 `"0.00"`、`"123.46"`）。建议新写独立 2dp 辅助函数（如 `_user_min_borrow_value_usdt`），不得改动或复用 8dp 的 `_quantize_rate` 输出路径。
- raw `"0"` 是合法响应：可估值时输出 `"0.00"`，不是 `null`。
- `portfolio_account.max_borrowable_value_usdt` 保持现有八位小数输出，一个字符都不动。

### 2.4 Raw sample 与 fixture

- **实现评审前必须落地**未修改的公共样例副本：把 `reports/api-samples/2026-07-private-account-v1/20260705T232800Z/sapi-v1-margin-allAssets.json` 逐字节复制为 `reports/api-samples/2026-07-borrow-task-ui-fake-v1/sapi-v1-margin-allAssets.json`，并在 `21-implementation-backend.md` 中记录两个文件的 `shasum -a 256` 证明一致（这满足 AGENTS.md"契约修订须带 raw public sample"硬门）。
- 该样例 409/409 条含 `userMinBorrow` 且**全为 `"0"`**——它确立字段路径与字符串形态，但不提供非零视觉值。非零覆盖用**合成测试 fixture 补充**（如构造 `userMinBorrow: "0.001"` 的内存输入），合成物只能进 `backend/tests/`，**不得**冒充 raw sample、不得写入 api-samples 目录。
- `backend/tests/fixtures/private-account-v1-design.json` 的所有 `classic_margin` 块补齐两个新必填字段（现 schema `additionalProperties:false` + required 会使旧 fixture 校验失败，这是预期的强制更新）。

### 2.5 Schema

`schemas/api/public-market/snapshot.schema.json` 的 `classic_margin`（431-452 行区域）：

- `required` 增加 `user_min_borrow`、`user_min_borrow_value_usdt`；
- 两字段类型均为 `anyOf: [{"$ref": "#/$defs/decimal_string"}, {"type": "null"}]`，与 `daily_interest_vip0` 同形；
- 两位小数约束由测试断言（schema 的 `decimal_string` 模式不收紧）。

### 2.6 测试要求（先写断言再实现）

- `test_private_client.py`：`fetch_classic_reference` 返回的 `user_min_borrow_by_name` 按 `assetName` 键入、保留原始字符串（含 `"0"` 与合成非零值）、缺字段条目映射 `None`。
- `test_private_account_v1.py`（装配 + schema）：
  - `classic_ref None` / `pair_listed` false 或缺失 / map 缺 key → `null` 门齐全；
  - raw 字符串保真（输出 === 输入字符串）；
  - 估值：稳定币按 1、非稳定币走 `<ASSET>USDT`、价格缺失 → `null`、raw 非法 → 值 `null`；
  - **非空值恰好两位小数**（如断言 `re.fullmatch(r"-?\d+\.\d{2}", v)`）与 `ROUND_HALF_UP` 行为（构造一个第三位小数为 5 的进位用例，如 `1.005 → "1.01"`）；
  - raw `"0"` + 可估值 → `"0.00"`；
  - `borrowability_truncated` 分支保留两字段；
  - 负向 schema 覆盖：缺任一新字段或出现未声明属性的 `classic_margin` 必须校验失败；
  - `max_borrowable_value_usdt` 既有 8dp 断言全部原样通过。
- 测试命令（输出全文进 `61-test-output-backend.txt`）：

```bash
python3 -m pytest backend/tests -q
git diff --check
```

### 2.7 风险与评审关注点

- 风险：把 `user_min_borrow` 与 `max_borrowable` 语义混同（前者是资产级最小申请量，后者是账户/池容量）；量化精度走错（2dp vs 8dp）；`borrowability_truncated` 分支漏保留字段；fixture 漏更导致跨测试文件连锁失败。
- 评审关注：三分支 null 门与 `asset_borrowable` 逐分支对照；raw 字符串零转换；`ROUND_HALF_UP` 用例真实性；raw sample 逐字节一致性（sha256）；schema required/additionalProperties 收口；无任何新 I/O 面。

## 3. Task F2 — 前端任务状态机/筛选/编辑 + 占位符（Kimi）

前置条件：B1 已提交到 stage 分支且 `python3 -m pytest backend/tests -q` 全绿。

### 3.1 Allowed files

- `frontend/index.html`
- `frontend/self-check.js`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/22-implementation-frontend-v2.md`、`62-test-output-frontend-v2.txt`

### 3.2 Forbidden

- `backend/**`、`schemas/**`、`docs/**`、`workflows/**`、`agents/**`、api-samples、fixtures
- 不新增 `fetch` 调用、不启动任何定时器/重试循环、不写 `localStorage` 或其他持久化、不发真实借币请求
- 不伪造 `HOMEUSDT` 或任何市场行情行；不添加"模拟成功"按钮或任何未要求的完成触发器
- 不碰 `status.json` / `70-handoff.md`；不 commit

### 3.3 任务状态模型（冻结自 `13-scope-amendment-v2.md`）

`state.borrowTasks` 内每个任务增加 `status ∈ {borrowing, paused, deleted, completed}`，UI 文案 借币中/已暂停/已删除/已完成。状态机：

```text
新建任务 → borrowing ↔ paused
borrowing | paused | completed → deleted   （软删除，终态）
（本阶段不存在任何到 completed 的转换）
```

按钮启用矩阵（逐状态精确执行）：

| status | 启动 | 暂停 | 删除 | 编辑确认 |
|---|---|---|---|---|
| borrowing | 禁用 | 可用 | 可用 | 可用 |
| paused | 可用 | 禁用 | 可用 | 可用 |
| completed | 禁用 | 禁用 | 可用 | 禁用（只读） |
| deleted | 禁用 | 禁用 | 禁用 | 禁用（只读） |

- 启动/暂停 是互逆的纯 UI 转换（`startBorrowTask`/`pauseBorrowTask` 本地函数），不触发 API/定时器/进度变化。
- **删除 = 先 fake stop 再软删除**（`deleteBorrowTask`）：置 `status:'deleted'`，**绝不**从 `state.borrowTasks` 移除对象。completed 任务删除后同样变为 deleted。

### 3.4 软删除与筛选语义

- 借币任务标题区筛选控件：全部、借币中、已暂停、已删除、已完成。
- **全部不是一个 status**：显示内存中的每一个任务对象，**包含软删除的**。
- 各筛选计数从唯一权威数组 `state.borrowTasks` 派生，不维护第二份列表。
- 已完成筛选/状态必须正确渲染，即使本阶段没有任何自动或手动完成机制（初始恒为空视图）。测试可用 test-only helper 或纯内存 fixture 构造 completed 任务；生产 UI 不得新增模拟完成入口。

### 3.5 任务列表编辑规则

- 每个任务行/卡暴露独立的单次数量与累计成功目标输入（独立 per-task id/data 属性，预填**精确当前值**）+ 确认控件。
- 校验与创建路径同规则：数量为有限数 > 0；目标为整数 > 0。
- 有效确认：只更新该任务的 `amountPerAttempt`/`successTarget`，**保留 `successCount`**，重算展示的目标总量，并重渲染任务视图/计数/筛选。
- 无效或只读（deleted/completed）编辑：不产生任何状态变化，显示就近局部错误。
- 任何编辑路径不得调用 `fetch`、localStorage 或定时器。

### 3.6 最小借币量占位符（消费 B1 字段）

行情表操作列的数量输入**保持空值**，仅把固定 `placeholder="如 1000"`（`frontend/index.html:1557`）替换为按行派生的占位符，读 `row.borrow_validation.classic_margin`：

- `user_min_borrow` 与 `user_min_borrow_value_usdt` 均为字符串 → `最小借币量 <user_min_borrow> (≈ <user_min_borrow_value_usdt> USDT)`，**包括 raw `"0"` 与 value `"0.00"`**；
- 仅 raw 存在、value 为 null → `最小借币量 <user_min_borrow> (≈ — USDT)`；
- raw 为 null（含私有通道不可用、pair 未上市等一切 null 门）→ `最小借币量 —`。

硬边界：占位符是**纯指引**——不写入输入值、不自动创建任务、不改动现有校验（0 仍被拒）、**不改动任务列表编辑输入**（编辑输入预填当前值，与本规则无关）、不暗示该数量当前可借、不引入网络/定时器/持久化行为。

### 3.7 自检用例（`frontend/self-check.js`，接续 #67 编号）

- 新建任务默认 `borrowing`，按钮矩阵与 3.3 表逐格一致；
- 暂停→已暂停→启动 往返转换及按钮翻转；
- 软删除：deleted 任务仍在 全部/已删除 中可见、全部控件禁用、对象未从数组移除；completed 任务删除后变 deleted；
- 筛选成员与计数：全部 含 deleted；各 status 筛选只含对应任务；已完成初始为空但可渲染（test-only helper 构造）；
- 有效编辑：更新数量/目标、保留 `successCount`、总量重算、重渲染；
- 无效编辑：值不变 + 就近局部错误；deleted/completed 编辑不可用；
- 占位符三分支：双值（含 `"0"`/`"0.00"`）、raw-only、双 null；输入 value 恒为空字符串；任务列表编辑输入的 value/placeholder 不受影响；
- 每个新动作（启动/暂停/删除/编辑/筛选）后断言 `fetchCallLog` 与 interval 注册零增长；
- 既有 #1–#67 全部保持通过（13 列、事件隔离、HOME 泛化路径、已借完唯一性等无回归）。
- 测试命令（输出全文进 `62-test-output-frontend-v2.txt`）：

```bash
node frontend/self-check.js
git diff --check
```

### 3.8 手工视觉检查（浏览器，记入实现报告）

- 创建任务 → 借币中 徽标与按钮态正确；暂停/启动往返；删除后任务变 已删除 且仍可在 全部/已删除 中查看；
- 逐个切换五个筛选，计数与成员正确；
- 列表内编辑数量/目标并确认，进度保留、总量刷新；输入非法值看到局部错误；
- 行情表操作列占位符按行数据展示三种形态之一；输入框本身为空；确认 0 仍被拒；
- DevTools Network 面板确认全过程无新增请求。

### 3.9 风险与评审关注点

- 风险：60 秒表格重渲染与新筛选/编辑状态交互（P3-1 可能被放大——若发现直接冲突须在报告中披露）；deleted/completed 只读边界被编辑路径绕过；筛选计数与权威数组脱钩；占位符插值未走 `escapeHtml`（raw 来自 API 字符串，必须转义）；把占位符误写成输入 value。
- 评审关注：状态机转换与按钮矩阵逐格核对；软删除的"可见但只读"；全部 含 deleted；编辑保留 `successCount`；占位符三分支含 `"0"` 边界；零新增 fetch/timer/持久化；既有抽屉事件隔离与 13 列无回归。

## 4. 完成定义（整个阶段）

1. B1 全部落地并全绿 → bookkeeper 提交 → verify: `python3 -m pytest backend/tests -q` 与 raw sample sha256 一致。
2. F2 全部落地并全绿 → bookkeeper 提交 → verify: `node frontend/self-check.js` + `git diff --check`。
3. bookkeeper 重算 `d9c2772..新 head` fingerprint，跑 `scripts/validate-stage.py 2026-07-borrow-task-ui-fake-v1 --phase pre-review`，按 §1 评审路由发起全新 review-1（B1→Kimi 评审，F2→Claude-GLM 评审）与 review-2。
4. 旧 `30-review-1.md` ACCEPT 不得被复用为任何通过依据。

当前 Session ID: 1cc925a0-4202-4033-bcee-92875c00cb23
Session ID 来源: transcript_path
原始输出路径: reports/agent-runs/2026-07-borrow-task-ui-fake-v1/12-development-breakdown.md
本地北京时间: 2026-07-18 22:06:05 CST
下一步模型: bookkeeper (Codex/GPT) → 人类操作员
下一步任务: bookkeeper 依据本细化准备 Claude-GLM 后端任务（B1）派发包并更新 model_routing，人类操作员执行；B1 落地提交后再派发 Kimi（F2）

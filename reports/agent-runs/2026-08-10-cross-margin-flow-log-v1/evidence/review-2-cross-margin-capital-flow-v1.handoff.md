# Task Handoff: review-2-cross-margin-capital-flow-v1

## Source Report (author-only; immutable after task end)

- task_id: `review-2-cross-margin-capital-flow-v1`
- role: Reviewer（review-2，需求/实际效果/证据/运行风险/发布就绪，只读）
- target model: `sonnet5`（provider: `anthropic`）
- required_skill: `agents/skills/reality-checker.md`
- stage_id: `2026-08-10-cross-margin-flow-log-v1`
- created_at: 2026-08-10 19:44:55 CST
- base_sha: `a11a8734a3da988501fa5cac5baa52dcea3ea2ef`（`git rev-parse` 一致）
- delivery_sha: `9a4e0198ee7f7d2102ab1b9550c39e79a76e24fa`（已封存值，非 pending；`git merge-base --is-ancestor` 通过）
- status_revision 核对: `status.json` revision=5、phase=`review_2`、checkpoint=`review_1_accept_verified`、current_task.id=`review-2-cross-margin-capital-flow-v1`、state=`dispatched`、base_sha 与 `git rev-parse` 一致；Bookkeeper=`grok4.5`。
- provider 隔离：实现 `claude_glm`（zhipu_glm）、review-1 `kimi`（moonshot）、本 review-2 `sonnet5`（anthropic）——三方均不同；Bookkeeper `grok4.5`（xai）未兼任本轮 review-2。

### 评审结论

**REWORK。**

计划四条冻结条款（隔离、幂等、单页满 1000 标记、additive）与 P0-1（`coverage_for_window`
逐位不变）在代码与独立复跑的测试中均成立，判定正确，予以保留。review-1 的 ACCEPT 在这些
维度上是可信的。

不通过的原因：本轮独立复核发现一条 review-1 未覆盖的**具体、可复现、非假设**的缺口——
本次交付新增的两个错误短码未接入前端中文映射表，会在真实失败路径上向用户展示未翻译的
英文短码，与同一文件内既有错误短码「逐一配中文」的既定先例（4/4 全部配了中文）不一致。
证据与影响见下，全部锚定当前代码行号，未援引 `AGENTS.md` §1 假设场景通道。

---

### 只读评审范围与实际执行的检查

只读读取：`AGENTS.md`、本 dispatch、`ACTIVE.json`、`PROJECT_STATE.md`、`status.json`、
`agents/roles.md`（Shared Rules / Task Handoff Evidence Contract / Reviewer）、
`agents/skills/reality-checker.md`、`00-change-plan.md`（全文，含 §9 冻结核对表）、
实现 handoff（含 Bookkeeper 核验块）、review-1 handoff（含 Bookkeeper 核验块）、
plan-review handoff；固定 diff `git diff a11a873..9a4e019`（全部 12 个文件逐一读取，非仅摘要）
与 `git show 9a4e019 --stat`；当前源码
`backend/ledger_flow/{service,store,domain}.py`、`backend/services/private_client.py`、
`backend/app/server.py`（`coverage_for_window` 消费点，只读）、`frontend/index.html`、
`frontend/self-check.js`、`docs/api/public-market-contract.md`；
recon `reports/api-samples/2026-08-margin-account-flow-recon-v1/20260810T062742Z/recon.md`。

执行的只读命令与结果（本轮独立复跑，未复用他人输出）：

```text
$ test ! -e evidence/review-2-cross-margin-capital-flow-v1.handoff.md
CONFIRM_STILL_ABSENT（preflight 与 Bookkeeper 记录一致）

$ git rev-parse a11a873… 9a4e019… → 两值与 status.json 一致
$ git merge-base --is-ancestor a11a873… 9a4e019… → ancestor_ok
$ git log --oneline a11a873..9a4e019 → dacf02f/6e9e86b/09ef638/4658f3e 为阶段控制提交，
  代码交付仅 9a4e019 单提交
$ git show 9a4e019 --stat → 12 files changed, 893 insertions(+), 72 deletions(-)（与实现 handoff 一致）

$ .venv/bin/python -m pytest backend/tests/test_ledger_flow_domain.py \
    backend/tests/test_ledger_flow_store.py backend/tests/test_ledger_flow_service.py \
    backend/tests/test_ledger_flow_scheduler.py backend/tests/test_ledger_flow_api.py \
    backend/tests/test_private_client.py -q
156 passed in 6.75s

$ .venv/bin/python -m pytest backend/tests/ -q
1717 passed in 143.87s

$ node frontend/self-check.js
（末行）全部自检通过

$ git diff a11a873..9a4e019 -- backend/app/server.py backend/ledger_flow/scheduler.py | wc -l
0（两文件零改动，独立复核 review-1 的同一断言）
```

逐文件读取 `_build_coverage`（`service.py:415` 一带）确认函数体在 diff 中**零增删行**，
`coverage_for_window`（`service.py:487`）仍只调 `_build_coverage(start_ms, end_ms,
self._store.get_coverage())`，与 `get_flow_log` 内部 `coverage["by_source"]["capital_flow"] = …`
是两次独立调用、两个独立字典，无共享可变状态——P0-1 的隔离结论独立验证成立。

---

### 对 dispatch 六条 Acceptance Checks 的逐条判断

1. **需求对齐**（1 天首窗 / 小时增量 / 不分页 / 全仓单源 / 中栏真数据 / 假数据已去）
   —— `pass`。`_compute_capital_window` 首次 `[now-1d, now]`、之后 `[cov_end-3h, now]`；
   `_CAPITAL_PAGE_LIMIT=1000` 单页无 `fromId`；`fetch_capital_flow_page` 不传 `symbol`；
   `frontend/index.html` 的 `FLOW_LOG_CAPITAL_FAKE_ROWS`/预览徽标/`.flow-log-fake-badge`
   已全部删除（`grep` 零命中）。
2. **运行 / 账务隔离**（对冲净盈亏消费点不受污染）—— `pass`。`coverage_for_window` 逐位
   不变已独立验证（见上）；`flow_refresh_runs` 表结构与列集合零改动（`test_capital_isolated_from_two_source_coverage`
   断言该表恰一行、无 capital 列）；capital 失败走独立 try/except，`_run_capital_flow` 的
   `except Exception` 包裹了对 `self._client`（可能为 `None`）的调用，隔离到位。
3. **证据充分性**（review-1 复跑与实现自测是否可信；是否还有必须本轮修的缺口）
   —— **`fail`**。review-1 复跑与实现自测本身可信（本轮独立复跑逐条重现，见上），但
   存在一条 review-1 未捕获的、必须本轮修的具体缺口——见下方「发现」。
4. **发布就绪**（schema_version 未 bump / additive / 无部署实盘写义务已诚实记录）
   —— `pass`。`store.py` `_SCHEMA_VERSION_VALUE`、`service.py` 响应字面量、
   `docs/api/public-market-contract.md` 三处均为 `private-ledger/v2`；实现与 review-1
   handoff 均声明未 merge/未部署/未重启，`PROJECT_STATE.md` 当前状态段一致。
5. **发现范围三分类 / Scenario Admission 门** —— `pass`。下方发现为 `in-range`：
   引入的两个错误短码（`_ERR_CAPITAL="capital_flow_failed"`、字面量
   `"capital_internal_error"`）是本次交付新增（`service.py:45/384/389`），其消费方
   `FLOW_LOG_ERROR_ZH`（`frontend/index.html:6931-6936`）恰是本次交付触碰的同一文件；
   证据为直接代码行 + 文档原文，非假设场景，未援引 §1 通道。
6. **唯一 handoff / delivery_sha / 评审结论字段** —— `pass`（本文件为本任务唯一写入，
   preflight 记录 absent；`delivery_sha` 填已封存 `9a4e0198ee7f7d2102ab1b9550c39e79a76e24fa`）。

---

### 发现（`in-range`；REWORK 必须本轮修）

#### F-1 新增两个错误短码未接入前端中文映射表，失败态会向用户展示未翻译英文短码

- **证据（代码）**：
  - `backend/ledger_flow/service.py:45` — `_ERR_CAPITAL = "capital_flow_failed"`（本次新增）。
  - `backend/ledger_flow/service.py:336` — `_fetch_capital` 失败时 `self._classify(exc, _ERR_CAPITAL)`。
  - `backend/ledger_flow/service.py:384` / `:389` — `_run_capital_flow` 的隔离兜底分支写死
    `"error": "capital_internal_error"`（本次新增，覆盖 `self._client` 为 `None` 等内部异常）。
  - `frontend/index.html:6931-6936` — `FLOW_LOG_ERROR_ZH` 完整内容为：
    ```js
    const FLOW_LOG_ERROR_ZH = {
      interest_history_failed: '利息历史拉取失败',
      um_income_failed: '合约流水拉取失败',
      rate_limited: '限频',
      private_channel_disabled: '私有通道未启用',
    };
    ```
    未新增 `capital_flow_failed` / `capital_internal_error` 两个 key。
  - `frontend/index.html:6985-6987` — `flowLogErrorZh(code)` 的 fallback 是
    `FLOW_LOG_ERROR_ZH[code] || String(code)`：未命中时**原样透传短码字符串**，不是
    「未知错误」一类的通用中文兜底。
  - `frontend/index.html:7608` / `:7639` — `renderFlowLogCapitalCol` 恰有两处消费
    `flowLogErrorZh(last.error)` 拼进用户可见文案（「上次失败：…」/「上次拉取失败：…」）。
  - **同文件先例（4/4 全部配了中文）**：`docs/api/public-market-contract.md` 既有一句
    「Error short codes: `interest_history_failed`, `um_income_failed`, `rate_limited`,
    `private_channel_disabled`」，这四个码在 `FLOW_LOG_ERROR_ZH` 中**逐一都有**对应中文；
    本次交付的文档新增小节明确写了「Error short code: `capital_flow_failed`（plus
    `rate_limited` / `capital_internal_error`）」，把新码正式记入同一文档口径，但对应的
    前端映射没有同步更新。
- **实际效果**：一旦 capital-flow 拉取真的失败（上游 5xx/网络问题/私有通道未接线等——
  `capital_internal_error` 分支专为覆盖这类内部异常而写，非纯理论分支），中栏状态行与
  空态文案会显示英文 snake_case 短码（如「上次失败：capital_flow_failed」），而不是像
  另外两栏一样显示中文（如「利息历史拉取失败」）。这与用户既有决定「UI 以中文为主」的
  项目惯例、以及本文件内既有错误短码 100% 配中文的先例不一致；`rate_limited` 因为复用
  既有 key 不受影响。
- **不影响的范围（明确排除，避免过度扩大）**：不影响 P0-1（`coverage_for_window` 隔离已
  独立验证逐位不变）、不影响入库幂等 / 满 1000 标记 / 失败不推进 end 等账务/数据正确性，
  纯粹是失败态展示文案的 i18n 缺口。
- **修复要求（最小改动）**：在 `frontend/index.html:6931-6936` 的 `FLOW_LOG_ERROR_ZH`
  字面量中新增两个 key，中文文案建议与既有措辞风格一致（例如
  `capital_flow_failed: '全仓流水拉取失败'`、`capital_internal_error: '全仓流水内部错误'`；
  具体措辞由实现者定，只需为中文且不与既有四条冲突）。不得借此修复顺带改动其他文件、
  契约或范围（否则按 §8 需重新过 review-1）。
- **建议但不强制**：`frontend/self-check.js` 目前只验证 capital 列相关 DOM id 存在，
  未对该列的失败态/空态渲染做内容级断言（构造的 mock payload 里 `capital_flow` 块
  几乎总是「成功」形状），本次 F-1 正是这个断言盲区放过的缺口。若实现者顺手在
  `buildMockFlowLogPayload` 的某个 override 场景加一条「capital 失败态渲染中文」的断言，
  可降低同类问题复发概率，但不作为本轮 REWORK 的必需项。

---

### 未完成事项

- 无其他阻塞发现。本评审不实现、不修代码、不提交、不 merge、不部署、不重启服务。
- 运行时事项（沿用实现/review-1 已述，非本轮新增）：首次实盘拉取的权重占用与满页概率
  需运行时日志确认；本评审同样为离线证据，未发起实盘请求。

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/evidence/review-2-cross-margin-capital-flow-v1.handoff.md`（本文件）
  2. `reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/evidence/implement-cross-margin-capital-flow-v1.handoff.md`
  3. `frontend/index.html`（`FLOW_LOG_ERROR_ZH`，第 6931-6936 行；`flowLogErrorZh` 消费点第 7608/7639 行）
  4. `backend/ledger_flow/service.py`（`_ERR_CAPITAL` 第 45 行；`capital_internal_error` 第 384/389 行）
  5. `docs/api/public-market-contract.md`（Cross-margin capital-flow 小节的 Error short code 一行）
- 执行：Bookkeeper 核验本 handoff（REWORK、F-1 的 in-range 分类、`rework_count` 0→1），
  随后准备一次**窄修复** dispatch 给原实现者（`claude_glm`/zhipu_glm）：仅新增
  `FLOW_LOG_ERROR_ZH` 两个 key，不扩大文件范围、不改契约、不加风险。
- 关卡：按 `AGENTS.md` §8「窄发现直接回 review-2」——修复、自测（含 `node
  frontend/self-check.js`）、新提交后，直接回本 review-2（同 provider `sonnet5`/anthropic）
  复核，不需要重新过 review-1；通过后由 Human 决定合并/部署。
- 不能假设的事实：
  - 不能假设本轮已穷举所有前端文案 i18n 缺口——本次只核对了 capital-flow 新增的两个
    错误短码；既有四个短码已验证有映射，未逐一重新审查全部界面的中文覆盖率。
  - 不能假设 F-1 有账务/资金影响——它只影响失败态展示文案，`coverage_for_window` 的
    P0-1 隔离已用独立测试证明不受任何 capital 状态（成功/失败/从未拉取）影响。
  - 不能假设修复需要重新触碰后端——`_ERR_CAPITAL`/`capital_internal_error` 的后端定义
    本身正确（短码语义准确、隔离正确），缺口纯在前端映射表这一侧。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

```text
[TASK_RESULT v2]
任务 ID: review-2-cross-margin-capital-flow-v1
执行结果: completed（完成）
结果摘要: 只读 review-2 完成，结论 REWORK。计划四条冻结条款与 P0-1(coverage_for_window 逐位不变)均有真测试，本轮独立复跑 156+1717 passed、self-check 全绿，判定正确。发现一条 in-range 缺口：新增错误短码 capital_flow_failed/capital_internal_error 未接入前端 FLOW_LOG_ERROR_ZH 中文映射表，失败态会向用户显示未翻译英文短码，与同文件既有四个短码 100% 配中文的先例不一致。不影响账务/P0-1 隔离，修复面窄(前端字典加两行)。
产物: [reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/evidence/review-2-cross-margin-capital-flow-v1.handoff.md]
检查结果: [需求对齐(1天首窗/小时增量/不分页/全仓单源/真数据/假数据已去)=pass；运行账务隔离(coverage_for_window逐位不变/不写flow_refresh_runs/不进aggregate-delta-last_run)=pass；证据充分性(review-1可信但发现F-1须本轮修)=fail；发布就绪(schema_version未bump/additive/未部署已诚实记录)=pass；发现范围三分类与Scenario Admission门(F-1为in-range、非假设场景、有代码行锚点)=pass；唯一handoff/delivery_sha=9a4e019/评审结论字段=pass]
阻塞项: [F-1：frontend/index.html:6931-6936 的 FLOW_LOG_ERROR_ZH 需新增 capital_flow_failed 与 capital_internal_error 两个中文映射]
评审结论: REWORK（返工）
问题记录: reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/evidence/review-2-cross-margin-capital-flow-v1.handoff.md
修复要求: reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/evidence/review-2-cross-margin-capital-flow-v1.handoff.md
本地北京时间: 2026-08-10 19:44:55 CST
下一步模型: grok4.5（本阶段 Bookkeeper，status.json.bookkeeper=grok4.5，由 Human 启动其终端）
下一步任务: 读取：reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/evidence/review-2-cross-margin-capital-flow-v1.handoff.md；frontend/index.html；backend/ledger_flow/service.py；执行：Bookkeeper 核验本 handoff(REWORK/F-1 in-range/rework_count 0→1)并准备窄修复 dispatch 给原实现者 claude_glm(仅改 FLOW_LOG_ERROR_ZH 两个 key)；关卡：修复+自测后直接回本 review-2(sonnet5/anthropic)复核，无需重新过 review-1，通过后 Human 决定合并/部署。
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- bookkeeper: `grok4.5`
- verified_at: 2026-08-10 19:51:20 CST
- status_revision_at_verify: 5（review_2 / `review-2-cross-margin-capital-flow-v1` / dispatched）
- source_payload_sha256: `6ba5985ebec7e8131d464578e8b01ed847f01fe8894d663bb8a0ce96d07ba38a`（marker 前全部字节）
- 核验：
  - `执行结果: completed` + `评审结论: REWORK` + F-1 in-range + 修复要求可执行
  - `delivery_sha` 仍为已封存 `9a4e0198ee7f7d2102ab1b9550c39e79a76e24fa`
  - 独立抽查源码：`FLOW_LOG_ERROR_ZH` 仅 4 键；`capital_flow_failed` / `capital_internal_error` 由 service 产出且中栏经 `flowLogErrorZh` 消费 → F-1 成立
  - provider：实现 zhipu_glm、r1 moonshot、r2 anthropic，隔离成立
- 裁定：**核验通过（REWORK）**；`rework_count` 0→1（正式 REWORK 修复轮，绑定交付 `9a4e019`）
- 路由：§8 窄发现 → 原实现者最小修复后**直接回 review-2**（sonnet5），不重新 review-1
- 后续：派工 `fix-capital-flow-error-zh-v1`；修完新 commit 后 Bookkeeper 更新 `delivery_sha` 再派 r2 复核

## Errata (append-only)

（无。）

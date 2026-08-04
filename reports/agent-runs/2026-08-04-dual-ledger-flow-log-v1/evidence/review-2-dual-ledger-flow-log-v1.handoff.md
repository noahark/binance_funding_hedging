# Task Handoff: review-2-dual-ledger-flow-log-v1

## Source Report (author-only; immutable after task end)

- task_id: `review-2-dual-ledger-flow-log-v1`
- role: `Reviewer`（Review-2，reality-checker，只读）
- target_model: `sonnet5`
- provider: `anthropic`
- stage_id: `2026-08-04-dual-ledger-flow-log-v1`
- created_at: `2026-08-04 22:52:32 CST`
- base_sha: `dc4cc6d9dc629c06cff4a98f98ff7a81a533a3c8`
- delivery_sha: `none`（评审任务无交付提交；受审区间 `dc4cc6d9dc629c06cff4a98f98ff7a81a533a3c8..0c9c4de77253d4716242867b8c1e8fe42906d790` 已由 Bookkeeper 冻结，两端 `git rev-parse` 已核对存在）
- status_revision 核对：`22`（`current_task.id=review-2-dual-ledger-flow-log-v1`、`state=dispatched`，与 dispatch 一致）

**Provider 隔离披露**：本评审 provider 为 `anthropic`。实现/修复作者：A/B/修复 = `claude_glm`(`zhipu_glm`)，C+前端最终 = `grok`(`xai`)——均与 `anthropic` 跨 provider，满足 `agents/roles.md` Review-2 硬性要求。设计/计划作者 `opus5` 同为 `anthropic`（provider 级重叠），dispatch 已按「Prefer a final reviewer that did not plan or design the stage; disclose if unavoidable」披露；该重叠不豁免对实现的跨 provider 要求，本评审未违反硬性禁令。

### 受审范围

区间 `dc4cc6d..0c9c4de` 内的本 stage 交付提交：任务 A `aba7420`（取数+本地账本底座）、任务 B `550f8b7`（拉取编排+调度+两条路由）、任务 C+前端最终 `f23368b` + `5613c4e`（tab-layout v2 + 元数据卡片左右排微调）、修复 `0c9c4de`（review-1 F1/F2 修复）。区间内其余提交（fake 原型 `84e37b0..a8dee78`、tab-layout v1 `82feca1..e676811`【已回退】、以及全部 `bookkeeper:` 控制提交）为上下文而非受审交付，按 `AGENTS.md` §8「评审范围口径」处理。

权威：设计定稿 `docs/planning/2026-08-04-dual-ledger-flow-log-design.md` v1.4（§11–§18）；契约 `docs/api/public-market-contract.md` v0.12（`Dual-Ledger Flow-Log Amendment`，其正文声明 §13–§15 权威仍是 v1.2——核对属实：v1.3/v1.4 按设计文档自述「只改 UI 布局，接口契约与数据语义一字未动」，v0.12 与 v1.2 §13–§15 逐字段仍一致，非文档滞后缺陷）。

### 复核方法（本轮独立执行，不只读叙述）

除通读 review-1（deepseek）`review-1-dual-ledger-flow-log-v1.handoff.md`、`review-1-r2-dual-ledger-flow-log-v1.handoff.md`（均 verified）与 A/B/C/修复四份作者 handoff 外，本轮在当前工作树（`HEAD=a1dff3f`，经 `git diff --stat 0c9c4de..a1dff3f` 核对：`0c9c4de` 之后仅本 stage 报告目录与 `PROJECT_STATE.md` 有改动，代码零漂移，等价于在 `0c9c4de` 上复核）独立重跑：

```bash
node frontend/self-check.js
# 全部自检通过（含关键行：「流水日志 C+v2：panel-actions 双看板、侧栏移除、同页切换、GET/POST/轮询/护栏」PASS）

PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider -q backend/tests/
# 1351 passed in 87.46s（与 fix-review1 `.pytest.txt`「1351 passed in 86.44s」、review-1-r2 复测「86.82s」三次独立实测账目一致，仅耗时噪声）
```

并对关键文件做逐行代码核对（非仅信任 handoff 声明）：`backend/ledger_flow/domain.py`（408 行全文）、`backend/ledger_flow/store.py`（438 行全文）、`backend/ledger_flow/service.py`（502 行，读毕 `_do_run`/`_compute_window`/`_fetch_*`/`_commit_*`/`_build_coverage`/`_compute_delta`/`trigger_refresh` 全部关键路径）、`backend/app/server.py`（路由装配 122–381 行、`run()` 940–1054 行）、`backend/services/private_client.py`（白名单、`_signed_get` 门禁顺序、两个新 fetcher 640–694 行）、`backend/services/snapshot_service.py`（`private_client` 只读访问器）、`frontend/index.html`（`setMarketBoard`/`setActiveView` 5874–5980 行、状态条三态判定 6348–6420 行、DOM 骨架与 25 个冻结 id）。25 个 §13.7 冻结 DOM id 逐个 `grep -c` 确认各恰好出现 1 次。

### 六维度判断（reality-checker，`agents/skills/reality-checker.md`）

**1. 需求 vs 交付效果 — 通过**

Human 两个需求与后续拍板逐项对照代码，均已真实交付且与设计 v1.4/契约 v0.12 一致：本地 SQLite 持久化（`backend/ledger_flow/store.py:41-97` 四表结构与 §14 冻结 schema 逐字段一致）；整点 HH:01 定时刷新（`scheduler.py` `decide` 四判据，已由 review-1-r2 独立复测 10 个真断言单测覆盖，本轮读码确认判据与 §15.1/§15.3 一致）；增量统计（`service.py:430-449 _compute_delta`，baseline=倒数第二次成功 run、`manual` 排除、不足两次 `complete=false`，与 §15.4 逐字一致）；页内双看板（`frontend/index.html:1268-1269` `#btn-market-board`/`#btn-flow-log` 并列 `.panel-actions role=tablist`；`setMarketBoard` 页内切换不改 `activeView`、不隐藏侧栏——代码 5874-5913 行核对属实）；侧栏三项恢复、`#nav-flow-log` 零命中（`grep` 确认）；每栏默认 20 条（`frontend/index.html:6082 FLOW_LOG_DEFAULT_DISPLAY_LIMIT=20`，`row_count`/`summary_*` 仍按全量，`row_limit_applied` 语义不变，`service.py:461-479` 全量计算确认）；元数据卡片左右排（`.flow-log-meta-row` 两列 grid，`index.html:333/424` 断点样式确认）。侧栏「费率行情」一律回到市场看板（`setActiveView` 5915-5956 行，`boardHint='market'` 强制覆盖 `state.marketBoard`）与设计一致。

**2. 证据可信度 — 通过（附一条流程观察，见发现 F-R2-1）**

A（84 passed）、B（31 passed，回归声明「194 passed」）、修复（1351 passed）三份 `.pytest.txt` 原始输出均存在且已被 Bookkeeper/review-1/review-1-r2 三次独立核验；本轮第四次独立重跑同样得到 `1351 passed, 0 failed`，无空洞声明。前端 self-check：C 的 `.selfcheck.txt`、tab-layout-v1/v2 的 `.selfcheck.txt` 均存在且已核验；本轮独立重跑当前代码 `node frontend/self-check.js` 同样全绿，包含流水日志专项断言行。fake 原型（v1/v2）与真实版关系清楚：fake 先行验收 UI 骨架，真实版（任务 C）在其上替换数据源、移除 FAKE 横幅与假数据生成函数，两版本无交叉污染（`frontend-dual-ledger-flow-log-v1.handoff.md` 明确列出改动点）。唯一的证据链缺口见 F-R2-1（观察，不阻塞，见下）。

**3. 资金/账务语义正确性 — 通过**

逐条核对红线均在代码中真实落地，非仅声明：ID 字符串化——`domain.py:98-116 _id_to_str` 对 `int`/`str`/`float` 全覆盖，19 位长整型经 `str()` 无精度损失；金额透传——`domain.py:128-138 _amount_str` 不 round/quantize/float/补零，空串→`None`；`Decimal` 精确求和——`domain.py:269-290 _sum_amounts` 在 `localcontext(prec=40)` 内求和，`format(total,'f')` 输出；不可解析→`null`+计数——同函数：任一条目 `Decimal()` 抛异常则整组 `total=None` 且 `unparsed_row_count>0`，绝不用部分和冒充全量，`None`（缺失）与「不可解析」区分对待（跳过 vs 计数）；无 SQL 聚合——`grep -n "SUM(\|AVG(\|TOTAL(\|float("` 命中 `store.py`/`service.py` 均为 0（`service.py:327` 的 `sum(` 是对 run 计数整数求和，非金额）；幂等不覆盖——`store.py:213-319 commit_interest/commit_income` 用 `ON CONFLICT DO NOTHING`，已存在行的 `first_seen_*` 不会被覆盖；增量口径——`_compute_delta` 用 `first_seen_at_ms>baseline`（入库时间），`_build_today` 用 `accrued_at_ms`/`time_ms` 窗口（发生时间），两口径代码路径分离、不混用，与 §13.2 规则 12 一致；coverage 诚实性护栏——`service.py:375-402 _build_coverage` 的 `complete` 判定（`window_start>=cov_start` 且相交 `gaps` 为空）与 `pending_tail_ms`（不参与 `complete`）逐字对照 §13.2 规则 7，本轮读码确认「窗口落空洞内必为 `false`」这一 v1.1 已知漏洞已被本实现修复。截断双向处理（左栏降序推进 `coverage_end` 不前移 `start` 记空洞；右栏升序推进到 `newest_fetched` 不记空洞自愈）在 `service.py:258-300 _commit_interest/_commit_income` 中与 §15.2 逐字一致。唯一非零风险点见维度 6 的联调前置观察（非语义缺陷，是「未被活体数据踩过」的路径）。

**4. 运营风险 — 通过（无新增未披露风险）**

权重核算：sapi interestHistory ≈1/call、papi um/income ≈30/call，日常每小时约 1 次 papi+1-2 次 sapi ≈32 权重/小时，相对 papi IP 限频约 6000 req/min 有巨大余量（recon 实测数字，`reports/api-samples/2026-08-borrow-interest-history-recon-v1/.../recon.md` §4.1、`2026-08-um-income-funding-recon-v1/.../recon.md` §3.2）。独立调度线程边界：`LedgerScheduler` 复用既有借币调度器模式（daemon 线程 + `threading.Event`），`server.py:1044-1051` 的 `finally` 块中 `ledger_scheduler.stop()`/`ledger_store.close()` 均有 `try/except` 包裹、不掩盖主异常；`PrivateClient` 复用（`snapshot_service.py:275-286` 只读 `@property`）不产生第二次凭据读取或新签名面；两个新 fetcher 明确不写 `last_error`（`private_client.py:640-650` 注释+实现确认）、不走 `_cached_get`（避免刷新拿到 TTL 旧数据）。双进程双跑代价、3 小时重叠捕获边界、时钟回拨、40 页余量等已知代价均已在设计 §17.4 具名披露并附证据（非本轮新增风险，未被当作缺陷掩盖）。空库/通道未启用启动行为：`server.py:956-957/1018` 仅在 `is_usable()` 为真时启动调度器并置位 `scheduler_enabled`；`GET flow-log` 空库仍返回 200 而非 503（§13.2 规则 13 空态契约，`service.py:404-407 _format_last_run` 对空 `recent_runs` 返回 `None` 而非抛异常，store 空库查询全部 `[]`/`None` 不抛——`store.py` docstring 与代码一致）。

**5. 发布就绪 — 通过**

A+B+C+前端最终+修复五个交付提交均已存在（`git log --oneline dc4cc6d..0c9c4de` 核对）；`rework_count=1/3`，在预算内且本轮未新增返工；review-1 REWORK→修复→review-1 复审 ACCEPT 链条完整、每一步均有 Bookkeeper Verification 追加块与 source_sha256；review-1 的 O1（`new_row_count` 恒 0）、O2（run 记录先于明细提交）、O3（`by_source` 半对象判定）三项观察，本轮独立读码复核 O1——确认 `_format_last_run`（9 字段，无 `new_row_count`）与 `trigger_refresh`（`interest_new_row_count`/`income_new_row_count` 取自 `commit_*` 返回值，非 run 表字段）两处对外契约均不读取恒 0 的 run 表列，接受为已知限制成立；O2/O3 影响面同 review-1 结论，属正常运行不可达的防御性代码观察，不阻塞。review-1-r2 的 R1（handoff 文件占位块格式怪癖）、R2（真实装配分支无直接单测）均为观察，非本轮新增。无遗漏的验收检查。

**6. 前后端联调前置确认 — 需要 Human 决策，本评审给出判断**

真实 `POST /refresh` 连币安拉取确未在任何任务中执行过（全部 A/B/C/修复 handoff 一致声明「未真实上游拉取」）；`status.json.checkpoint` 现状即「review-2 ACCEPT 后进入 Human 最终决策与前后端联调」——即本 stage 自身流程把联调排在 review-2 之后。**本评审判断：这个顺序可以接受，不必因联调未做而 REWORK**，理由：(a) 两个新端点的传参、分页停止条件、截断判定、每页大小/页数上限，均在 `service.py:198-247 _fetch_interest/_fetch_income` 中按 recon 实测的响应形状（`{total,rows[]}` 降序 / 数组升序）编码，且被 A/B 的离线桩测试（84+31 passed，含 `test_private_client.py` 的 4 个新 fetcher 桩用例）与本轮独立读码交叉核实，不依赖「先联调再评审」才能建立信心；(b) 真实首次 30 天回补的分页数量已有 recon 实测锚点（sapi 30d 17 页、papi 30d 上限 10 页覆盖 30d FUNDING+COMMISSION 193 条实测），落入 40/10 页上限、无需触发 `truncated`；(c) 失败路径（`interest_history_failed`/`um_income_failed`/`rate_limited`/`private_channel_disabled`）与空态/三态渲染已被测试覆盖，即使联调中出现非预期响应形状，退化路径是「该栏 error 短码」而非崩溃或静默吞错。**唯一真正“从未被活体数据踩过”的是两个 fetcher → `domain.normalize_*` → `store.commit_*` 这条端到端路径本身**——见发现 F-R2-2（观察，非阻塞，建议 Human 授权联调时的检查重点）。空库/通道未启用时页面表现（§13.2 规则 13/14）已按三态判定表实现且被测试覆盖，可接受。

### 发现（按 `AGENTS.md` §8 标注；均为观察级，不阻塞 ACCEPT）

#### F-R2-1 — [观察，不阻塞] `frontend-flow-log-meta-layout-v1` 任务未按 Task Handoff Evidence Contract 交付独立 create-only 交接件与原始 self-check 输出

- **事实**：`reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/frontend-flow-log-meta-layout-v1.dispatch.md` 的 Allowed Files 与 Acceptance Check 3 要求本任务产出 `evidence/frontend-flow-log-meta-layout-v1.handoff.md`（create-only）与 `evidence/frontend-flow-log-meta-layout-v1.selfcheck.txt`；实测 `find .../evidence -iname "*meta*"` 与 `ls .../evidence | grep meta` 均为空，两文件均不存在。该微调（元数据卡片左右排）与已验收的 tab-layout v2 被合并进同一个提交 `5613c4e`，提交信息自陈「tweak arranged directly by Human via grok, self-check verified green by Bookkeeper」，但仓库内没有对应该微调的独立原始输出文件——只有 `PROJECT_STATE.md` 与 bookkeeper 提交信息里的一句断言。
- **范围**：该提交（`5613c4e`）本身在受审区间内（是 C 交付链的一部分），因此这不是审阅区间外的控制提交问题，而是**受审交付的一部分证据链不完整**。
- **是否构成「声称但无原始输出的空洞」**：部分构成——但本轮已用两条独立证据闭合实质风险：① review-1（deepseek）在其复核命令中已对**当前代码状态**（含本微调）重跑 `node frontend/self-check.js` 并记录「全部自检通过」；② 本轮 review-2 对同一份代码（`HEAD=a1dff3f`，与 `0c9c4de` 逐文件比对零漂移）第三次独立重跑，同样全绿，且能看到「流水日志 C+v2」专项断言行通过。即：**没有该微调专属的原始输出文件，但有两次独立第三方对最终代码状态的真实复现**，不是「声称但从未验证」。
- **结论**：观察级，不阻塞本次 ACCEPT。建议 Bookkeeper 后续对「Human 直接安排、绕过标准 dispatch 流程」的任务补一条纪律：即便微调由 Human 直接安排，仍应在完成后由该任务或下一个接触该文件的任务补一份最小 create-only 交接件（哪怕只有一行「Human 直接验收，self-check 全绿附输出」），保持 Task Handoff Evidence Contract 的路径完整性；本次不要求补做（不影响 ACCEPT，补做与否留 Bookkeeper/Human 裁量）。

#### F-R2-2 — [观察，不阻塞] 两个新 fetcher → 落库这条端到端路径从未被真实上游响应验证过

- **事实**：`fetch_interest_history_page`/`fetch_um_income_page`（`private_client.py:651-694`）到 `domain.normalize_*`/`dedup_*`/`sort_*` 到 `store.commit_*` 的完整链路，全部测试均使用桩 `urlopen` 或桩 client（A 的 84 个测试、B 的 31 个测试均离线）；两份 recon（`2026-08-borrow-interest-history-recon-v1`、`2026-08-um-income-funding-recon-v1`）虽是对同一账户的真实签名 GET，但那是 recon 脚本直接调用，不经过本次交付的 `fetch_interest_history_page`/`fetch_um_income_page`/`LedgerFlowService._do_run` 代码路径。
- **影响**：理论残余风险——真实响应里出现桩测试未覆盖的边界形状（如某天真的触发 40/10 页上限、或某类型金额字段出现 recon 未采样到的格式）时，首次真实运行才会暴露。已有的失败短码与 `truncated`/`gaps` 机制会把这类意外**转化为可观测状态**（栏级 `error` 或 `truncated=true`+空洞记录），而不是静默出错或写脏数据——这是设计层面的护栏，但护栏本身也是第一次被真实数据触发。
- **不阻塞理由**：这是本 stage 自己既定的分阶段验证策略（先离线证明契约实现正确，联调阶段由 Human 授权后再证明与真实上游的接口对齐），不是本轮引入的新缺口；dispatch 维度 6 本就要求 review-2 对这个顺序给出判断，已在上文六维度第 6 条给出。
- **建议**（非修复要求，供 Human 授权联调时参考）：联调首次 `POST /refresh` 后，重点看 `last_run.truncated`、`coverage.gaps`、两栏 `row_count` 是否与账户实际活跃度量级相符（可用两份 recon 里的历史条数做粗略量级对照：sapi 30d≈1647 条、um/income 30d≈193 条），以及 `unparsed_row_count` 是否为 0。

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/review-2-dual-ledger-flow-log-v1.handoff.md`（本文件）
  2. `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/status.json`
  3. `docs/planning/2026-08-04-dual-ledger-flow-log-design.md`（§17.3「实现前的独立计划评审」已回答问题的最终确认状态；§18 决策表）
- 执行：Bookkeeper 核验本 ACCEPT 结论（无 REWORK，`rework_count` 维持 1，不新增），封存本评审；将本 handoff 转交 Human 做最终决策——是否现在授权前后端联调（真实 `POST /refresh`，只读签名 GET，无资金操作但会消耗 papi/sapi 权重）。
- 关卡：Human 决策「先联调再合并」还是「先合并再联调」（本评审建议前者，即联调作为合并前的最后一道人工验证，具体顺序由 Human 定）；联调通过后方可合并/部署/启用定时调度对接实盘账户。
- 不能假设的事实：本评审为只读，未修改任何受审代码/测试/契约/设计/`status.json`；F-R2-1/F-R2-2 均为观察级，未附「修复要求」，不消耗 `rework_count`；真实上游拉取截至本评审完成时仍未执行。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

```text
[TASK_RESULT v2]
任务 ID: review-2-dual-ledger-flow-log-v1
执行结果: completed（评审运行完成；评审结论 ACCEPT）
结果摘要: reality-checker 六维度评审 dc4cc6d..0c9c4de（A+B+C+前端最终+修复）全部通过。独立重跑 self-check 全绿+全量 pytest 1351 passed 0 failed（第三方复现，非仅信任声明）；金额/ID/幂等/coverage 护栏逐行读码核对与设计 v1.4/契约 v0.12 一致；运营风险已知项均属既披露且非本轮新增；发布就绪。两条观察级发现不阻塞：微调任务缺独立交接件（已用两次独立 self-check 复现闭合）、fetcher-落库端到端路径未经真实上游验证（既定分阶段策略，非新缺口）。
产物: [reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/review-2-dual-ledger-flow-log-v1.handoff.md]
检查结果: [需求vs交付效果(双看板/侧栏三项/SQLite/整点调度/增量/20条/元数据卡片左右排逐项读码核对): pass, 证据可信度(三次独立复测self-check全绿+四次独立复测pytest 1351passed0failed): pass, 资金账务语义(ID字符串/金额透传/Decimal prec40/不可解析null/无SQL聚合/幂等不覆盖/入库vs发生时间分离/coverage complete判定/截断双向处理逐行核对): pass, 运营风险(权重~32/小时远低于限频/线程清理有try-except/PrivateClient复用无新签名面/fetcher不写last_error不走缓存/空库通道未启用启动行为符合§13.2规则13): pass, 发布就绪(五交付提交齐全/rework_count 1/3/review链条完整/O1-O3+R1-R2观察项复核成立): pass, 前后端联调前置(真实POST refresh确未执行/判断该顺序可接受/唯一残余为fetcher到落库端到端路径未经真实数据验证-观察级非阻塞): pass, provider隔离(anthropic与zhipu_glm/xai实现作者跨provider/design层provider重叠已披露不豁免实现隔离): pass, 只读合规(未改受审代码/测试/契约/status.json/未启动服务/未访问网络/未读凭据/未做实盘): pass]
阻塞项: [none]
评审结论: ACCEPT（接受）
问题记录: reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/review-2-dual-ledger-flow-log-v1.handoff.md（F-R2-1/F-R2-2，均观察级，详见 Source Report）
修复要求: none
本地北京时间: 2026-08-04 22:52:32 CST
下一步模型: bookkeeper1（Bookkeeper；核验本 ACCEPT 并转交 Human 最终决策）
下一步任务: 读取：reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/review-2-dual-ledger-flow-log-v1.handoff.md；执行：核验 ACCEPT 结论（rework_count 维持 1，不新增）并封存，将结论转交 Human 做前后端联调授权与合并决策；关卡：Human 决策真实 POST /refresh 联调时机（本评审建议在合并前完成）→ 合并/部署
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

（待 Bookkeeper 追加：源区块 SHA-256、核验时间、核对的 status revision、通过或拒收依据、可复现命令与后续状态。）

## Errata (append-only)

（无。）

## Bookkeeper Verification

- 核验时间（本地）：2026-08-04 23:00:00 CST
- source_sha256（marker 前字节）：`fb75ef82e3190639e41716b4019fc8f679aedca96bb92e4ce4764c3520b47e70`
  （复现：读本文件，取 `<!-- BOOKKEEPER_APPEND_ONLY:` 之前全部字节，`hashlib.sha256` 十六进制）
- 核对的 status revision：22（`current_task.id = review-2-dual-ledger-flow-log-v1`、`state = dispatched`；预检 `test ! -e` 于 2026-08-04 22:50 CST 通过，评审交付）
- 结论：**通过（verified，verdict=ACCEPT）**。`评审结论: ACCEPT`；六维度（需求 vs 交付 / 证据可信度 / 资金与账务语义 / 运营风险 / 发布就绪 / 联调前置）逐项通过；独立复现证据（重跑 `node frontend/self-check.js` 全绿、全量 `pytest backend/tests/` 1351 passed 0 failed、25 个冻结 DOM id 逐个验证、逐行读码核对 domain/store/service/server/private_client/前端）——证据链闭环无空洞声明；两条观察级发现 F-R2-1（meta 微调任务无独立交接件，流程完整性观察）与 F-R2-2（fetcher→落库端到端未活体验证，联调阶段核对重点）**不阻塞**；联调前置判断明确（真实 `POST /refresh` 联调可放在 review-2 通过后、合并前，不因联调未做而 REWORK）。
- `rework_count` 判定：维持 **1**（无新增返工轮；F-R2-1/F-R2-2 为观察级不计数）。
- 后续状态：review-2 → `verified`；**等待 Human 最终决策**：(1) 前后端联调授权（真实 `POST /refresh` 连币安拉取，联调重点核对 truncated/gaps/unparsed_row_count 与端到端路径）——review-2 建议在合并前完成；(2) 合并/发布决策。F-R2-1 的纪律建议（Human 直接安排的任务补最小交接件）交 Human 裁量，不强制补做。

## Errata (append-only)

（无。）

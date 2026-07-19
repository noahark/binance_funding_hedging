# Review-1 — Task B Frontend (Backend-Authority Migration)

Stage `2026-07-real-borrow-execution-v1`, formal `reviewer_1`, fresh plan/read-only
Claude-GLM (`glm-5.2`) session. This session did not implement, fix, or pre-review
Task B; it inspects the committed Task B range only.

## Verdict: ACCEPT

Task B 前端交付严格符合冻结 A+B 契约。ACCEPT 基于 reviewer 独立核验,**不是**
把嵌入预审 PASS 当作正式 ACCEPT 的替代(embedded-review-B-round1 仅是 checkpoint)。

### 独立核验(逐项亲自执行,非依赖书面摘要)

1. **指纹重算一致**:

   ```sh
   git diff --binary 40efb028ead50d667bb32dbe10e9af6a7d77409e..4bab47d250b739539c0c2f09786baa75bba25d6d \
     -- . ':(exclude)reports/agent-runs/2026-07-real-borrow-execution-v1/status.json' | shasum -a 256
   # = 5f815252ed8e55c7a3aa97efa7a8f4db700abd27e2e1bca998b2af923b728a81
   ```

   与预期 task fingerprint 冒号后部分逐字节相等;与 `61-r4-diff-reconciliation.txt`
   的 Task B snapshot SHA-256 也一致。

2. **diff 范围纯净**:`git diff --name-only 40efb02..4bab47d` 仅含
   `frontend/index.html`、`frontend/self-check.js` 两个允许文件;该区间只有 1 个提交
   (`4bab47d feat(borrow): connect frontend task views to backend`)。
   `head_sha` 之后的 Harness evidence commit(`30c44c9`、`3f51a0e`)不计入判断。

3. **独立重跑**:`node frontend/self-check.js` 全部 96 项断言通过(exit 0);
   `git diff --check` exit 0,无空白错误。

4. **源码逐条对照 frozen contract**(`12-development-breakdown.md` §3 +
   `13-user-decisions-and-contract-amendment.md` §1/§3):
   - **Create = Start immediately(amend §1)**:`createBorrowTask` 只 POST
     `/api/borrow-tasks` 冻结 body `{asset, amount_per_attempt, success_target}`,
     用返回文档(已 `borrowing`)打补丁并重拉,无导航、无二次 Start。
   - **冻结 mutation 路由/body**:start/pause/delete POST `{}`;edit POST
     `{amount_per_attempt, success_target, version}`(乐观并发);interval GET 渲染
     + PUT `{interval_seconds: 原始十进制串}`。
   - **就近 error detail**:`borrowApi` 非 2xx 抛携带 `data.detail` 的 Error,
     per-row/per-card/per-editor/in-view-banner 就近显示。
   - **五类冻结中文标签 + unknown block 徽标/按钮矩阵**:`BORROW_RESULT_LABELS`
     (success→成功 / known_rejection→已知拒绝 / rate_limited→限频冷却 /
     unknown→未知·待对账 / execution_disabled→执行未启用),null→暂无执行记录;
     `unresolved_attempt_id != null` → 「待对账·暂停调度」徽标 + 启动/暂停禁用、
     删除可用;borrowing 禁启动、paused 禁暂停、completed 禁启动·暂停·编辑、
     deleted 全禁。
   - **顶层「借币任务｜借币日志」tab**:筛选容器位于 `borrow-tasks-panel` 与
     `borrow-logs-panel` 之间(结构断言)。
   - **日志 newest-first**:仅靠显式刷新与 `next_cursor` 加载更多,前端按后端返回
     顺序原样渲染(后端 `ORDER BY COALESCE(...) DESC, id DESC` 是 SQL 权威)。
   - **无执行时钟**:仅 `setInterval(60000)` 快照与 `setInterval(1000)` 倒计时;
     snapshot tick 仅在 borrow view 激活时 `loadBorrowTasks()`(只读 GET),不轮询
     日志、不 dispatch。
   - **同源 frozen route**:全部 `fetch` 同源 §3.1 路由,零 Binance、零绝对外域
     (self-check #76 fetch 同源白名单 + 方法白名单证明)。
   - **诚实文案**:subtitle「任务与日志由后端 SQLite 持久化并调度;本阶段不发起真实
     借币(执行未启用)」;info banner「…浏览器不调度、不模拟、不请求 Binance」;
     任务卡「任务持久化在后端;本阶段不发起真实借币(执行未启用)」。旧的
     前端演示/浏览器内存 声明已移除。

5. **无回归**:self-check 前 62 项市场 13 列、drawer、private read-only、METAL、
   opening-spread 等既有断言全绿;`60-test-output.txt` 记录 backend 507 测试通过。

6. **self-check 非 mock-only 成功路径**:覆盖 400 `invalid_field`/
   `invalid_interval`、409 `invalid_transition`/`version_conflict`、pending 条目
   (`outcome:'pending'`、`result_category:null`)、success/known_rejection/
   rate_limited/unknown/execution_disabled 五类结果、本地校验失败、空输入、软删除
   可见性、未设置路由的 503 默认。mock 文档(`MOCK_TASK_HOME`/`MOCK_SETTINGS_DEFAULT`/
   `MOCK_LOG_ENTRY_HOME`)逐字段复制 §3 示例,`deepCopy` 派生不改字段形状。

### 范围与身份合规

- reviewer 与 Task B 实现者(kimi)provider 不同(claude_glm ≠ kimi),满足 review-1
  provider 级跨审隔离;`reviewer_uses_raw_artifacts` 已遵守。
- Task A 由另一 claude_glm 会话实现,不是本次被审代码;本次严格只审 Task B 的
  committed range。
- 本会话未参与 Task B 的实现/修复/嵌入预审,也未参与 direction synthesis /
  development breakdown / stage design。

### 非阻塞观察(P3,契约内,无需 fix)

- 间隔编辑器不做本地正则预校验(仅校验非空),完全交后端 `invalid_interval` 400
  裁定;而金额经 `normalizeBorrowAmount` 本地正则预校验。差异符合 §3.11 字面契约与
  既有 UI 校验语义,后端始终是权威。
- `renderSchedulerSettings` note 文案描述的是**配置**间隔(`interval_seconds`),
  非**实测**间隔;实测 cadence 仅在日志 `effective_gap_us`/`latency_ms` 可观测。符合
  ADR-003(不得宣称 requested == achieved)。

---

当前 Session ID: unavailable (Claude Code runtime does not expose provider-native session ID to the model)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-execution-v1/30-review-1-frontend.md
本地北京时间: 2026-07-19 20:19:04 CST
下一步模型: review-2 (Codex/GPT 优先;Claude fallback 需 strong-reviewer 披露 override)
下一步任务: Task B review-1 ACCEPT,与 Task A review-1 合流后进入 review-2 最终门

{"schema_version":1,"stage_id":"2026-07-real-borrow-execution-v1","role":"first_reviewer","model":"glm-5.2","verdict":"ACCEPT","diff_fingerprint":"4bab47d250b739539c0c2f09786baa75bba25d6d:5f815252ed8e55c7a3aa97efa7a8f4db700abd27e2e1bca998b2af923b728a81","reviewer_prior_involvement":"none","reviewer_prior_involvement_notes":"Fresh plan/read-only Claude-GLM (glm-5.2) review-1 session. Did not implement, fix, or pre-review Task B, and did not participate in direction synthesis, development breakdown, or stage design. The claude_glm provider implemented Task A (backend) in this stage, but Task B under review was implemented by kimi; review-1 provider-level cross-review isolation holds (claude_glm != kimi). reviewer_prior_involvement reflects design/breakdown/synthesis participation only, which is none.","reviewed_artifacts":["reports/agent-runs/2026-07-real-borrow-execution-v1/00-task.md","reports/agent-runs/2026-07-real-borrow-execution-v1/10-design.md","reports/agent-runs/2026-07-real-borrow-execution-v1/11-adr.md","reports/agent-runs/2026-07-real-borrow-execution-v1/12-development-breakdown.md","reports/agent-runs/2026-07-real-borrow-execution-v1/13-user-decisions-and-contract-amendment.md","reports/agent-runs/2026-07-real-borrow-execution-v1/status.json","reports/agent-runs/2026-07-real-borrow-execution-v1/20-implementation.md","reports/agent-runs/2026-07-real-borrow-execution-v1/20-implementation-frontend.md","reports/agent-runs/2026-07-real-borrow-execution-v1/60-test-output.txt","reports/agent-runs/2026-07-real-borrow-execution-v1/60-test-output-frontend.txt","reports/agent-runs/2026-07-real-borrow-execution-v1/61-r4-diff-reconciliation.txt","reports/agent-runs/2026-07-real-borrow-execution-v1/embedded-review-B-round1-retry-1.raw-output.md","schemas/api/borrow-tasks/task.schema.json","schemas/api/borrow-tasks/task-list.schema.json","schemas/api/borrow-tasks/log-page.schema.json","schemas/api/borrow-tasks/scheduler-settings.schema.json","schemas/api/borrow-tasks/error.schema.json","schemas/review-verdict.schema.json","workflows/templates/stage-delivery.yaml","AGENTS.md","backend/app/server.py","frontend/index.html","frontend/self-check.js","git diff 40efb028..4bab47d25 -- frontend/"],"findings":[{"severity":"P3","title":"间隔编辑器不做本地正则预校验,完全交后端 400 裁定(契约内合理差异)","file":"frontend/index.html","line":2361,"evidence":"submitSchedulerInterval 仅校验非空(trim === '' 即本地拒绝),其余任意字符串原样 PUT /api/borrow-scheduler-settings,由后端返回 invalid_interval 400 detail 就近显示;而 createBorrowTask/editBorrowTask 的 amount 经 normalizeBorrowAmount 本地正则 ^[0-9]+(\\.[0-9]+)?$ 且 >0 预校验后再 POST。","impact":"无功能或安全影响。金额预校验延续既有 UI 语义(任务书要求保留生命周期/校验语义),间隔按 breakdown §3.11 字面实现(input accepts decimal string, 确认 sends PUT, 400 renders detail locally)。后端始终是权威。","recommendation":"无需修改。记录为信息级观察:两类输入的本地校验粒度不同是有意为之且符合冻结契约,review-2 可复核该解释。"},{"severity":"P3","title":"调度说明文案描述的是配置间隔而非实测间隔(符合 ADR-003)","file":"frontend/index.html","line":2388,"evidence":"renderSchedulerSettings 的 note 文案为「当前:每 X 秒后端全局轮转尝试一次」,引用的是 settings.interval_seconds(用户配置值);实测 cadence 仅在借币日志的 effective_gap_us / latency_ms 中可观测,UI 未宣称 requested == achieved。","impact":"无。ADR-003 明确要求 requested cadence 与 achieved cadence 必须可区分,不得宣称两者相等。该文案描述配置、不描述实测,恰好满足该约束。","recommendation":"无需修改。记录为信息级观察,确认未违反 ADR-003 的 requested-vs-achieved 纪律。"}],"required_fixes":[],"residual_risks":["借币日志在普通运行下随每次 execution_disabled 调度尝试无界增长(breakdown §3.9 已接受风险;retention 为未来决策,A+B 不引入上限)。","崩溃遗留的 pending 尝试会阻塞其任务直到删除(fail-closed by design;对账为 Boundary C)。","requested cadence 可能超过 OS/executor 可达 cadence;日志暴露实测——任何 requested==achieved 的宣称都应被拒绝(ADR-003)。","两个用户暂缓的 P3 fake-UI finding 仍处于暂缓状态(00-task.md 非目标)。","Task B 依赖 Task A 后端按 §3 冻结契约实现同源路由;review-2 应确认 bookkeeper 的 read-only integration smoke(§4)在各 §3.1 路由上 schema 一致。"],"next_action":"continue"}
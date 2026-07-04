<!-- ============ RECEIPT（审计元数据，bookkeeper 填写；非任务内容） ============
status: pending            # pending | running | done | blocked
target_model: kimi (Task B implementer)
adapter_cmd: 用户粘贴 PROMPT BODY 至 Kimi 终端（H_intake 后即可，
             不必等 Task A）
started_at:
completed_at:
session_id:
outputs:                   # 20-implementation-frontend.md / self-check 结果
next_dispatch: pre-review-task-b-by-glm.prompt.md（嵌入预审 round 1）
======================================================================== -->

--- PROMPT BODY（不可变任务正文，自此行以下原样执行） ---

你是 stage `2026-07-phase2-borrow-sort-v1` 的 **Task B 实现者**（前端）。
权威规格 = `reports/agent-runs/2026-07-phase2-borrow-sort-v1/10-design.md`
§1.1-§1.2（耦合面契约）与 §4（先通读全文 + `00-task.md` + status.json
hard_constraints）。冲突时 10-design 赢。

## 交付物（仅 `frontend/index.html` + `frontend/self-check.js`）

1. **拆列**：删除「资金费率/结算时间」合并列，恢复独立「资金费率」与
   「结算时间」两列（复用既有 formatFundingRate/formatBeijing* 调用，
   **两函数逻辑禁止修改**）。
2. **新列「日费率」**：渲染 `daily_funding_rate`（复用 formatFundingRate
   的 string-shift 格式化；null 或字段缺失 → `—`）。
3. **结算间隔标注**：`funding_interval_hours` 展示为 `8h/4h/1h`（行内
   徽标或列头注，自定，原则=排名依据对用户可见）。
4. **零排序逻辑**：不加任何排序按钮/比较器/排序状态；严格按 payload
   顺序渲染（后端已按 abs 日费率降序排好）；既有筛选只隐藏不重排；
   60s 自动刷新与倒计时不动。
5. **优雅降级**：新字段缺失（旧后端）不白屏，日费率列 `—`、间隔不显示。
6. **不消费** `borrow_validation` 任何字段（本阶段私有展示不做）。
7. self-check 新增断言（10-design §4.4）：拆列/合并列消失/日费率格式
   （含 null→—）/间隔标注/无排序控件 DOM/渲染顺序==fixture 顺序/
   格式化函数体未变。开发自测可用 10-design §4.3 的设计期 fixture
   （注意其中 AUSDT 单期费率低于 BUSDT 但排第一——顺序断言的核心用例）。
8. `20-implementation-frontend.md`：改动清单、self-check 原始输出、自查表。

## 硬边界（违反即预审 blocker）

- 只许改 `frontend/index.html`、`frontend/self-check.js` 与本 stage 目录
  报告；`backend/**`/`schemas/**`/`docs/api/**` 零触碰。
- 单文件、无新依赖、同源 API、禁 parseFloat/Number×100 展示。
- 中文口径不变：枚举三列保持「英文(中文)」，其余界面文案纯中文。
- 耦合面即 10-design §1.1-§1.2 三项，需要变更 → 停手上报 controller
  （R3），禁止自行调整或造假字段。
- **不 commit、不碰 status.json**；改动只留工作树，报告写完即停，
  由 bookkeeper 负责提交与指纹。

完成后输出：改动文件清单 + self-check 摘要 + 「等待嵌入预审 round 1」。

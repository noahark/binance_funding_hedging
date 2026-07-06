<!-- ============ RECEIPT（审计元数据，bookkeeper 回填；非任务内容） ============
status: running            # pending | running | done | blocked | escalated
target_model: kimi (Task B implementer)
adapter_cmd: 用户向 Kimi 终端发「读文件执行 PROMPT BODY」一行指令；H_intake 完成后即可与 Task A 并行启动
started_at: 2026-07-06T00:06:37Z (UTC) / 2026-07-06 08:06 CST
completed_at:
session_id: fresh Kimi frontend terminal（待用户中转启动；与 Task A 后端并行）
base_sha: fce1452（H_intake PASS commit；本任务 diff 自 fce1452..head 测量，bookkeeper 做 R4 对账后串行落盘）
outputs:                   # 20-implementation-frontend.md / R10 收尾产物
next_dispatch: R10 收尾段（executor: self——完成实现后必须机械执行，不得以等待结束）
======================================================================== -->

--- PROMPT BODY（不可变任务正文，自此行以下原样执行） ---

你是 stage `2026-07-private-account-v1` 的 **Task B 实现者**（前端）。
权威规格 = 同目录 `10-design.md` §1.1-§1.5（耦合面契约）与 §4
（先通读全文 + `00-task.md` + status.json hard_constraints）。开发
自测用 bookkeeper 生成的设计期 fixture
`backend/tests/fixtures/private-account-v1-design.json`。冲突时
10-design 赢。当前分支应为 `stage/2026-07-private-account-v1`
（只核对，不切换）。

## 交付物（仅 `frontend/index.html` + `frontend/self-check.js`）

按 10-design §4 全部 8 项：净收益列（string-shift 复用、null→—、
负值红、borrow_rate_source 徽标、vip0_reference 显著标注）、
sort_basis 标注 + 零排序红线、私有面板三态（总览/分账户/UM 持仓）、
隐私开关（默认隐藏、localStorage 布尔）、行联动方向标（不带数量）、
旧后端优雅降级、self-check 新断言全集（§4.7）、
`20-implementation-frontend.md`。

## 硬边界（违反即预审 blocker）

- 只许改 frontend 两文件与本 stage 报告；backend/schemas/docs 零触碰。
- formatFundingRate/formatBeijing* 函数体禁改；禁 parseFloat/Number×100
  展示；单文件、无新依赖、同源 API；中文口径不变。
- 耦合面变更需求 → 停手上报 bookkeeper（R3）。
- **不 commit、不碰 status.json**。

## R10 收尾段（实现与自测完成后必须机械执行，路径已写死）

1. 自测：
   `node frontend/self-check.js 2>&1 | tail -10`
2. 生成预审 diff：
   `git diff -- frontend/index.html frontend/self-check.js > "reports/agent-runs/2026-07-private-account-v1/embedded-review-b-round1.diff.patch"`
3. 调用对侧 fresh 预审（Claude-GLM 只读）并落档：
   `zsh -lic 'cd "/Users/ark/Desktop/ai code/funding_hedging" && claude-glm --model glm-5.2 --permission-mode plan -p "$(cat reports/agent-runs/2026-07-private-account-v1/pre-review-task-b-by-glm.prompt.md)"' | tee "reports/agent-runs/2026-07-private-account-v1/embedded-review-b-round1.raw-output.md"`
4. 分支处理：
   - **PASS** → 输出「Task B 预审 PASS，等待 bookkeeper 串行落盘」+
     移交指令一行；
   - **BLOCKER 且在你 scope 内** → 修复 → 写
     `embedded-review-b-round1.fix-note.md` → 生成
     `embedded-review-b-round2.diff.patch` 同命令（round2 文件名）再审
     一次（封顶 2 轮）；
   - **越 scope / round2 仍 BLOCKER** → 停手，升级 bookkeeper；
   - **claude-glm 命令不可用/失败** → 写
     `reports/agent-runs/2026-07-private-account-v1/embedded-review-b-round1.dispatch.md`
     记录（unavailable|permission|command_error + 原始报错），声明
     escalated——**禁止只口头说等待**。

完成后输出：改动文件清单 + self-check 摘要 + 预审结论 + 本地北京时间。

<!-- ============ RECEIPT（审计元数据，bookkeeper 回填；非任务内容） ============
status: pending            # pending | running | done | escalated
target_model: claude_glm FRESH read-only/plan 会话（不得复用 bookkeeper/Task A 上下文）
adapter_cmd: Task B 实现终端按 R10 收尾段以 claude-glm --permission-mode plan -p "$(cat 本文件)" 机械调用
started_at:
completed_at:
session_id:
outputs:                   # embedded-review-b-round<N>.raw-output.md
next_dispatch: PASS → bookkeeper 串行落盘（executor: bookkeeper）；BLOCKER → Task B scope 内修复 round2（封顶）
======================================================================== -->

--- PROMPT BODY（不可变任务正文，自此行以下原样执行） ---

你是一个**全新的只读 Claude-GLM 会话**，担任 stage
`2026-07-private-account-v1` Task B（前端）的**嵌入交叉预审者**。
checkpoint 非评审门，不产生 verdict JSON。评审对象 = 同目录
`embedded-review-b-round1.diff.patch`（有 round2 审最新）。对照规格 =
`10-design.md` §1.1-§1.5/§4 + status.json hard_constraints。可读仓库
任何文件；可只读运行 `node frontend/self-check.js`；**禁止写文件、
改工作树**。

## 必查清单（逐项 PASS/FAIL + 证据行号）

1. 净收益列：string-shift 复用、formatFundingRate/formatBeijing*
   函数体零改动（diff 比对）、null→`—`、负值样式、
   borrow_rate_source 徽标 + vip0_reference 显著标注。
2. sort_basis 标注存在；**零排序逻辑**（无按钮/比较器/排序状态，
   按 payload 顺序渲染，筛选只隐藏不重排）。
3. 私有面板三态：verified=false 占位不白屏；总览/分账户/UM 持仓
   结构齐；不展示 fixture 之外杜撰字段。
4. 隐私开关：**默认隐藏**金额类数值、点击切换、localStorage 仅存
   布尔；隐藏态数值不出现在 DOM 以外输出；无 console.log 账户数据。
5. 行联动只给方向标，不带数量/盈亏。
6. 降级：新字段全缺失（旧后端 payload）页面行为不变。
7. self-check §4.7 断言全集齐且自跑全绿（含 net 反超顺序用例）。
8. 越界检查：diff 仅 frontend 两文件 + 本 stage 报告；无 commit、
   无 status.json 改动；中文口径不变（枚举三列「英文(中文)」保持）。

## 输出

逐项 PASS/FAIL 表 → blocker 清单 → 总结论 `PASS（可落盘）` 或
`BLOCKER（需修复后 round 2）`。末尾注明模型身份与当前本地北京时间。
你的输出将被逐字落档。

你是一个全新的只读 Claude-GLM 会话，担任 stage `2026-07-phase2-borrow-sort-v1` Task B（前端）的嵌入交叉预审者。
这是并行开发模式的 checkpoint，不是评审门：只产出 blocker 清单或放行意见，不产生 review verdict JSON。

## 评审对象

- 当轮工作树 diff：`reports/agent-runs/2026-07-phase2-borrow-sort-v1/embedded-review-b-round1.diff.patch`（已生成，只包含 Task B 改动：frontend/index.html + frontend/self-check.js）
- 对照规格：同目录 `10-design.md` §1.1-§1.2/§4、`00-task.md`、status.json `hard_constraints`
- 可读仓库任何文件；禁止写文件、改工作树；可运行 `node frontend/self-check.js` 验证（只读运行）。

## 必查清单（逐项给 PASS/FAIL + 证据行号）

1. 拆列完成：合并列「资金费率/结算时间」消失，独立两列存在；formatFundingRate/formatBeijing* 函数体零改动（diff 比对）。
2. 日费率列：复用 string-shift 格式化；null/缺失 → `—`；无 parseFloat/Number×100。
3. 间隔标注 `8h/4h/1h` 渲染存在且排名依据可见。
4. 零排序逻辑：diff 中无排序按钮 DOM、无比较器、无排序状态；渲染严格按 payload 顺序；筛选只隐藏不重排。
5. 降级：新字段缺失时不白屏（contract 校验兼容旧后端）。
6. 未消费 borrow_validation 任何字段。
7. self-check 新断言齐全（10-design §4.4，含顺序断言用例：单期费率低但日费率高的行排前）且全绿（自跑一遍）。
8. 越界检查：diff 仅触碰 frontend/index.html、frontend/self-check.js 与本 stage 报告文件；无 commit、无 status.json 改动；中文口径不变（枚举三列「英文(中文)」保持）。

## 输出格式

逐项 PASS/FAIL 表 → blocker 清单（文件/行/缺陷/修法）→ 总结论 `PASS（可落盘）` 或 `BLOCKER（需修复后 round 2）`。末尾注明模型身份与当前本地北京时间。你的输出将被逐字落档到 `reports/agent-runs/2026-07-phase2-borrow-sort-v1/embedded-review-b-round1.raw-output.md`。

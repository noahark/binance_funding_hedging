评审工作已全部完成（只读），报告已写入 plan 文件。由于本会话未提供 ExitPlanMode/AskUserQuestion 工具，且任务要求"输出将被逐字落档到 raw-output.md"，以下即为评审交付物全文：

---

# 嵌入交叉预审 — Task B（前端）Round 1

- Stage: `2026-07-phase2-borrow-sort-v1`
- 评审对象: `reports/agent-runs/2026-07-phase2-borrow-sort-v1/embedded-review-b-round1.diff.patch`（含 `frontend/index.html` + `frontend/self-check.js`）
- 对照规格: `10-design.md` §1.1-§1.2 / §4、`00-task.md`、`status.json` `hard_constraints`
- 实跑验证: `node frontend/self-check.js` → EXIT_CODE=0，20 条 `[PASS]` 全绿
- 性质: 并行模式 checkpoint（非评审门，不计 rework_count，封顶 2 轮）；只读会话，未写任何代码/工作树/status.json

## 逐项 PASS/FAIL 表

| # | 必查项 | 结论 | 证据 |
|---|---|---|---|
| 1 | 拆列完成：合并列消失，独立两列存在；formatFundingRate/formatBeijing* 函数体零改动 | **PASS** | diff L9 删除 `<th ...>资金费率/结算时间</th>`；diff L10-12 / index.html L502-504 新增独立「资金费率」「结算时间」「日费率」三列。formatBeijing(572-583)/formatBeijingShort(585-595)/formatFundingRate(597-611) 函数体未出现在 diff +/- 行；self-check 第14项字符串比对基线一致并 PASS |
| 2 | 日费率列：复用 string-shift；null/缺失 → `—`；无 parseFloat/Number×100 | **PASS** | index.html L821 `formatFundingRate(row.daily_funding_rate)` 复用 string-shift；null→`—` 由 formatFundingRate L598 兄弟逻辑保证；self-check 第6项验证 AUSDT/BUSDT/CUSDT/DUSDT(=null)→`—`。grep 确认前端无 `parseFloat`、无 `*100`（见观察项①关于 classForFundingRate） |
| 3 | 间隔标注 `8h/4h/1h` 渲染存在且排名依据可见 | **PASS** | index.html L822-825 `intervalBadge` 以 `[1,4,8].includes(intervalHours)` 生成 `<span class="badge compact muted">${n}h</span>`，附于日费率单元格；self-check 第7项验证 `>4h<`/`>8h<` 渲染 |
| 4 | 零排序逻辑：无排序按钮 DOM/比较器/状态；按 payload 顺序；筛选只隐藏不重排 | **PASS** | `grep -niE 'sort|排序|compare|localeCompare|\.order' frontend/index.html` 未命中；filteredRows() L754-764 仅 `.filter()` 无 `.sort()`；self-check 第8项断言无 `排序/sort/Sort`、第9项 `assertOrder(['AUSDT','BUSDT','CUSDT','DUSDT'])` 验证 payload 顺序 |
| 5 | 降级：新字段缺失不白屏（contract 校验兼容旧后端） | **PASS** | validateContract 的 REQUIRED_ROW_FIELDS（L524-529）不含 `daily_funding_rate`/`funding_interval_hours`，旧后端缺字段可通过校验；self-check 第19项删除两字段后渲染 4 行、日费率列 `—`、间隔不显示，全 PASS |
| 6 | 未消费 borrow_validation 任何字段 | **PASS** | 前端无 `borrow_validation`/`borrowable`/`max_borrowable`/`borrow_limit`/`daily_interest`/`pair_listed` 私有块字段消费；grep 命中仅为 `negative_funding_status` 枚举值 `PRIVATE_BORROW_VALIDATION_REQUIRED`（L667/672），属既有枚举三列，非私有块 |
| 7 | self-check 新断言齐全（§4.4，含顺序断言用例）且全绿 | **PASS** | §4.4 六类断言齐全：拆列(第5项)/日费率 string-shift 含 null→—(第6项)/间隔(第7项)/无排序控件(第8项)/顺序==payload(第9项)/函数体未变(第14项)。顺序用例符合「单期低但日费率高排前」：AUSDT(last 0.0001→单期+0.01%) < BUSDT(last 0.00015→+0.015%) 但 daily A(0.0006→+0.06%) > B(0.00045→+0.045%)，A 排前，assertOrder 锁定。实跑 EXIT_CODE=0 |
| 8 | 越界检查：diff 仅触碰前端两文件；无 commit；无 status.json 改动；中文口径不变 | **PASS** | `grep '^diff --git'` patch 仅 `frontend/index.html`+`frontend/self-check.js`（均属 §4.1 允许文件）；HEAD 仍为 `4d47ad2`（H_intake），实现终端无新 commit；status.json 不在工作树 diff 中；枚举三列「英文(中文)」map 保持（badgeForRouteClass L646-648 / badgeForAssetTag L677-680 / badgeForNegativeFundingStatus L667-670），筛选下拉 option 同格式（L469-481），self-check 第16项验证 |

## Blocker 清单

无。

## 观察项（非 blocker，供正式 review-1 知晓，不阻塞 round-1 落盘）

① **classForFundingRate 对 daily_funding_rate 使用 Number() 做符号判断**（index.html L820 `classForFundingRate(row.daily_funding_rate)` → L622-626 内部 `Number(str)`）。
- 判定: 非 blocker。该函数仅取符号（n>0/n===0/n<0）用于着色，不输出百分比、不×100，无浮点精度风险；且为既有函数既有用法（`last_funding_rate` 一直如此），§1.4「既有逻辑零改动」红线要求保留。hard_constraints 第8条「parseFloat/Number*100 forbidden」针对的是格式化转换（小数×100 转百分比），符号判断不在其列。
- 建议: 维持现状；若 review-1 希望更严格，可在文档注明 classForFundingRate 的 Number() 仅用于符号、不触碰 string-shift 展示纪律。

② **self-check 测试覆盖从多类型真实 fixture 收窄为设计期同质 fixture**。
- 旧 self-check 从 `frontend/fixture/public-market-snapshot.json`（BTC/ETH/XVG/TSLA 等）读真实样例，覆盖 BSTOCK 行标识、alias（TSLABUSDT/B 后缀别名）、PERP_ONLY_EXCLUDED 6 行、MARGIN_PUBLIC_UNVERIFIED title 等分支；新版改为内联 §4.3 设计期 fixture（4 行全 MARGIN_SPOT_CANDIDATE/CRYPTO），同步删除上述分支断言（原第5/6/7/12/13 项）。
- 判定: 非 blocker。§4.4 仅要求新增拆列/日费率/间隔/无排序/顺序/函数体断言，设计期 fixture 恰服务于排序与拆列验证目标，取舍自洽；BSTOCK/alias/PERP_ONLY 渲染分支代码仍在 index.html（badgeForUiFlag TRADIFI_BSTOCK L658-659、spotAlias L832-834、PERP_ONLY 筛选 L761），未删代码只退化了自动断言保护。
- 建议: 正式 review-1 或后续补回 BSTOCK/alias/PERP_ONLY_EXCLUDED 的断言路径（可双 fixture：设计期 fixture 验排序/拆列 + 真实多类型 fixture 验既有分支），避免回归盲区。

③ **ingestSnapshot 暴露至 `globalThis.__appHelpers`**（index.html L941）。
- 判定: 非 blocker。仅为 self-check 第19项优雅降级测试提供入口（`helpers.ingestSnapshot(degradedFixture)`），ingestSnapshot 本就是内部渲染入口，暴露不改变生产行为（生产经 loadApi→ingestSnapshot 调用），且 formatFundingRate 等本已暴露，风格一致。

## 总结论

**PASS（可落盘）**

8 项必查全部 PASS，self-check 实跑全绿，零越界，零排序，零 borrow_validation 消费，降级与函数体不变均验证。无 blocker。3 条观察项不阻塞落盘，建议正式 review-1 知晓（尤其②测试覆盖收窄）。

---

- 模型身份: claude_glm（GLM-5.2），fresh 只读会话，未复用 controller/Task A transcript
- 本地北京时间: 2026-07-04 22:51 CST

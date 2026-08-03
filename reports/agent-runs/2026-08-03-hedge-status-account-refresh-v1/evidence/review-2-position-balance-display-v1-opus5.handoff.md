# Task Handoff: review-2-position-balance-display-v1-opus5

## Source Report (author-only; immutable after task end)

- task_id: `review-2-position-balance-display-v1-opus5`
- role: `Reviewer`（Review-2，reality check）
- target model: `opus5`（provider `anthropic`；区间内实现作者为后端 `claude_glm`/`zhipu_glm` 与前端 `grok`/`xai`，与 `anthropic` 均不同，Review-2 的「与区间内每一位实现作者不同 provider」隔离满足）
- stage_id: `2026-08-03-hedge-status-account-refresh-v1`
- created_at: `2026-08-03 21:46:31 CST`
- base_sha: `89103303bd29a64ac5915b56639f8a4a885a56b7`
- delivery_sha: `7f965f8282c989625a80dfde0be96b0e008cafab`（Bookkeeper 已解析的固定评审 SHA，本件引用不改写）

### 独立性披露

本阶段 Bookkeeper 已由 `codex` 移交 `opus5`（Human 决策，codex 额度不可用），与本评审同模型但不同会话。判断：不削弱本次评审的独立性——`agents/roles.md` 的隔离规则约束的是「评审者不得与受审实现同 provider」，而受审代码全部来自 `zhipu_glm` 与 `xai`；Bookkeeper 未参与任何设计或实现，其产物只有状态核验与派发。唯一需要 Human 知情的残留是本件 AC5 要对 Bookkeeper 自己作出的一条 §7 格式裁定表态，属同模型家族自评；因此该条的理由已逐句写明依据的原文条款，供 Human 覆盖。按 dispatch 要求披露并上交 Human，未自行更换路由。

### 评审范围与方式

只读审查固定区间 `89103303..7f965f82`（`git log --first-parent` = 4 提交：控制提交 `e744ab3` route 后端、`8aa90b3` verify 后端；产品交付 `65bdd817` 后端、`7f965f82` 前端）。按 `AGENTS.md` §8「评审范围口径」，两个 Bookkeeper 控制提交只作上下文，不作为受审交付产生发现。本轮不重做 Review-1 的逐行代码检查，而是判断 Human 已批准的 `docs/planning/hedge-status-account-refresh-v4.md` §9 与实际交付效果是否吻合、证据是否足以支撑结论、上线后运行风险，以及是否具备进入 Human 合并决策的就绪度。全程离线只读：未改任何交付文件、测试、契约、`status.json`、`PROJECT_STATE.md` 或既有证据，未 commit/merge/push，未访问网络、凭证、服务或实盘；唯一写入是本交接件。

### 评审结论

**评审结论: ACCEPT**

dispatch 七条 Acceptance Checks 全部成立，无 `in-range` 阻塞发现。这是一次纯展示投影交付：四个新字段在全仓库仅有一个消费者（持仓表「现货余额」单元格），`GET /api/hedge-open-positions` 仍是零上游纯读，§1–§8 锁定的 refresh cycle、source 时间语义、无自动前端刷新与全部资金/订单/借贷/划转/Start gate/风险限制边界均未被触碰。两条离线命令独立复跑与提交证据一致（pytest `57 passed`；self-check exit 0、134 `[PASS]`、与证据文件 `diff -u` 逐字节相同）。记录 7 条非阻塞观察，其中 O-1、O-2 建议 Human 在合并决策时知情；无一条要求返工，`rework_count` 保持 `0`。

### 逐项核验（对照 dispatch Acceptance Checks）

**AC1 需求闭合 — pass**

对照 v4.1 §9.5 五条验收标准：

1. **成立**。`renderCollateralCapBadge` 的调用从标的单元格移除、只出现在同一行「借贷状态 / 资产」单元格（`frontend/index.html:2705` 构造、`:2718` 渲染）；仍是单一徽标，三态判定、颜色、title（含判定资产与名单截至时间）、排序/过滤/按钮零影响均未改。
2. **成立**。每个 merged row 经唯一构造点 `_merge_build_row` 生成，四字段恒存在（`backend/hedge_open_tasks/domain.py:1676-1691`）；`backend/tests/test_hedge_api.py:52-70` 的 exact keyset 同步三个新键；`backend/app/server.py:665-684` 的处理器仍只读已发布 snapshot 与本地 task bucket（`get_snapshot()` 为零上游纯读），本次未改该文件。
3. **成立**。「现货余额」列改为 `现货:` / `杠杆:` 两行，各带既有 `value_usdt` 的两位展示；缺失显示 `—`、真零显示 `0`（下详 AC2）。
4. **成立**。`#account-asset-updated-at` 移入 `.title-block` 并替换固定副标题「行情公开 · 账户需 key 私有只读」；`.refresh-meta` 只剩倒计时，右侧按钮不再被时间挤压；新增 `#private-pm-source-time` 位于「私有账户」`<h2>` 正下方，capability 三态正确，PM 文案已从概览 body 移除。
5. **成立**。两条离线命令独立复跑通过（见 AC3），无真实 key、网络、服务或实盘操作。

未触碰边界的核验：区间产品 diff 只有 `backend/hedge_open_tasks/domain.py`（+66，全部在 `_merge_build_row` / `merge_positions` 内）、两个后端测试、`docs/api/public-market-contract.md`（追加 v0.11 节）、`frontend/index.html`、`frontend/self-check.js`。未触及 `backend/domain/snapshot.py`、refresh cycle、`RefreshCacheCommand`、PrivateClient、`source_checked_at` 语义、snapshot JSON schema、订单/借贷/划转/Start gate/风控/凭证/部署任何路径；前端 diff 无任何新增 `fetch`、定时器、SSE 或 WebSocket（self-check 的白名单与「零新任务定时器」断言原样通过）。

**AC2 实际效果与展示诚实性 — pass（附具名风险）**

逐条对照 dispatch 列举的语义：

- 账户未就绪（`verified=false` 或 `private_account` 缺失）→ 四字段全 null → 两行均 `—`；本地记账行仍返回并展示（`test_merge_four_account_fields_all_null_when_not_verified`；前端 `NRUSDT` 用例）。
- 单侧账户缺该 asset → 只该侧 amount/value 为 null，另一侧保留数字（两个方向各一用例；前端 `ETHUSDT` 用例）。
- 真 `0` 仍显示 `0`：`spot_balance="0"`、`value_usdt="0.00000000"` 原样透传，前端 `formatHedgeDecimal("0")→"0"`、`formatUsdt2("0.00000000")→"0.00"`；前端 `ZEROUSDT` 用例并反向断言不得退化为 `—`。
- 估值缺失而 amount 已知 → `≈ — U`（`formatUsdt2` 对非法串返回 `null` 亦落到同一分支）。
- 隐私模式同时遮蔽数量与估值（`****` / `≈ **** U`）；amount 缺失分支先于隐私分支，缺失显示 `—` 而非 `****`——语义正确（缺失≠遮蔽），且后端不可能产出「amount 缺失而 value 存在」，无泄漏面。隐私开关经 `setPrivacyHidden → renderPrivatePanel → renderHedgeMergedPositions` 实时重渲染，两行不会留旧态。
- 1000x 资产不自动对齐 → 四字段全 null（`_merge_base_asset` 未改，`test_merge_four_account_fields_1000x_not_auto_aligned` 覆盖）。
- 「杠杆」行取 `balances_unified[asset].total_balance`（统一账户全仓余额），**不是** `cross_margin_borrowed`；借款仍只在「全仓借款」独立列（`domain.py:1689-1691` 与前端 `borrowCell` 未改）。按契约 v0.4 节，统一账户净额口径是 `value_usdt − cross_margin_borrowed_value_usdt`，即「杠杆」行是**未扣借款的毛额**，与既有余额卡片口径一致，不存在重复扣减。

「会不会让用户把未知读成 0 / 把借款读成余额 / 把两个账户读混」的具名结论：本次交付新增的展示路径**没有**把未知画成 0，也没有把借款画进余额行。需要 Human 知情的是三点既有语义在新展示下的影响，见下方 O-1、O-2、O-6。

**AC3 证据充分性 — pass**

独立离线复跑（工作树产品文件与 `delivery_sha` 一致：`git diff --stat 7f965f82 HEAD` 只含 `PROJECT_STATE.md`、证据、dispatch 与 `status.json`，产品代码零差异，故复跑执行的就是受审代码）：

- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider -q backend/tests/test_positions_merge.py backend/tests/test_hedge_api.py` → `57 passed in 18.85s`；提交证据 `backend-position-balance-display-v1.pytest.txt` 记 `57 passed in 18.97s`，仅计时不同。
- `node frontend/self-check.js` → exit `0`、134 个 `[PASS]`；与 `frontend-position-balance-display-v1.self-check.txt` `diff -u` **逐字节一致**。

证据是否真的支撑「页面会那样显示」：**部分支撑，有明确边界**。前端 self-check 在 DOM 桩上运行，断言的是渲染出的 HTML 字符串包含哪些文案，能证明格式化与降级分支正确；它不能证明真实浏览器里的版式，也不能证明后端字段真的流到了这个单元格——因为 self-check 的 positions 响应是**手写 mock**。全链路缺口：`test_positions_shape_after_fill` 只在账户未就绪的场景断言 exact keyset，没有任何测试把**已就绪且含余额**的 `private_account` 经 HTTP 一路带到渲染。我逐字符比对了三处字段名（`domain.py` 的 `row[...]` 赋值、`test_hedge_api.py:_POSITION_KEYS`、`index.html` 的 `p.xxx` 读取），五个键完全一致，故当前不存在漂移；但**没有任何自动检查把前端读取名绑定到后端产出名**，未来任一侧改名不会有任何测试报警。

只有真实浏览器或真实账户数据才能暴露的风险（self-check 覆盖不到）：

1. **版式**：单元格是 `white-space: nowrap` 的两行，落在 17 列、`min-width:980px` 的表里；八位小数 amount 加 `≈ xxxxxxx.xx U` 会显著加宽该列。`.table-wrap { overflow-x: auto }` 意味着退化是横向滚动而不是错版，但拥挤程度只有浏览器能看。
2. **真实数据的观感与 mock 相反**：按 `PROJECT_STATE.md` 已接受限制 B，对冲买入落在统一账户，而「现货」行读的是普通现货账户，因此真实页面上多数对冲行会是「现货: —、杠杆: 有值」，比 self-check 里两侧都有值的夹具空得多。这是本次交付的**正面价值**（对冲腿真正所在的账户第一次可见），但首次看到成片 `—` 的操作者需要预先知道这不是故障。
3. **1000x 币种**：六个 1000x 合约的行会两行全 `—`，与「账户未就绪」在视觉上不可区分（原因只在设计文档里）。
4. 真实小数串在隐私模式与两位取整下的观感、以及 `value_usdt` 相对余额的价格新鲜度（见 O-3），同样只有真实数据能显现。

**AC4 运行风险与发布就绪 — pass**

- **四字段的消费者**：全仓库 `grep` 显示 `spot_balance_value_usdt` / `unified_balance_value_usdt` 只出现在 `domain.py`（产出）、两个后端测试、两份文档、`index.html` 与 `self-check.js`（展示）；`unified_balance` 在后端除 `domain.py` 外无任何引用。**没有任何路径把这四个字段用于下单、借贷、风控或缓存写入**：前端下单的余额不足提示来自后端 preflight 返回的 `insufficient_balance` payload（`index.html:4533-4541`），与本单元格无关；`drift` 判定仍只用既有 `spot_by_asset`。
- **`private_account.verified=false`**：四字段全 null，两行 `—`，同时表上方保留既有横幅「账户数据未就绪（…）：仅显示本地任务记录…」。表现诚实。既有 F4 限制不变——该状态下每行仍会打「交易所无仓」，`PROJECT_STATE.md` 的操作者规则继续有效，本次交付既未修复也未加重它。
- **PM capability 缺失**：只影响 `#private-pm-source-time` 是否显示，与四字段无关；缺失时该行隐藏，capability 存在而 `pm_account` 时间为 null 时显示未就绪，不编造时间。
- **某侧 `value_usdt` 为 null**：显示 `amount ≈ — U`，不回退到另一账户估值，也不前端重算价格。
- **资产在一侧账户不存在**：只该侧两值为 null，另一侧不受影响。
- **就绪度判断：具备进入 Human 合并决策的就绪度。** 理由：交付面是单一纯函数的投影加一个单元格的渲染，无新增上游请求、无新增状态、无新增写路径；两条离线证据可独立复现；剩余风险全部是「读者可能怎么理解」而非「程序会做什么」。合并本身不改变实盘行为——本 stage 不授权部署、Start gate、凭证或实盘操作，页面要生效仍需 Human 单独决定部署。

**AC5 Review-1 闭包复核 — pass**

- **ACCEPT 成立**。我独立复跑了同样两条命令并独立读了固定 diff，未发现 Review-1 遗漏的 `in-range` 阻塞缺陷；其逐项事实（唯一 row 构造点、四字段真源、null/真零/1000x、借款列独立、徽标唯一迁移、两处时间唯一位置、概览无重复）我逐条对着源码复核，均属实。
- **观察 1（EOF 多余空行）成立，且不需要在合并前处理**。实测：`docs/api/public-market-contract.md` 现以 `\n\n\n` 结尾（基线本就有一个尾空行，本次又加一个），`backend/tests/test_positions_merge.py` 新增一个尾空行。仓库内**没有任何 lint/CI 门禁**（无 `.github/workflows`、`.flake8`、`pyproject.toml`、`setup.cfg`、`tox.ini`、`.pre-commit-config.yaml`），因此它不会让任何检查失败，也不改变代码行为、契约语义或测试结论。为它单开一次提交去改动已 verified 的交付，收益为零而风险非零；建议保持原样，或在将来因别的原因触碰这两个文件时顺手清掉。
- **观察 2（缺失分支先于隐私分支）**：核验属实且语义正确，非缺陷。
- **对 Bookkeeper「Review-1 回执缺三行字段属格式偏差、非拒收」的裁定：同意。** 理由（逐条对原文）：(a) `AGENTS.md` §7 的非接受条件写的是「Missing or ambiguous review-closure **data** is non-accepting」，约束的是闭包**数据**而非其排版位置；(b) 该数据在同一文件内显式且无歧义——`评审结论: ACCEPT` 以逐字原文出现在 Source Report，`问题记录` 的内容就是同一路径的发现小节，「无阻塞」且无任何 `in-range` 发现使 `修复要求` 唯一可能为 `none`；(c) §7 依 Human 决定 1 明文把回执要求降为「清楚、可读、能定位产物/结论/下一步，由 Bookkeeper 核验是否足以推进」，本例满足；(d) `agents/roles.md` Reviewer/Verdict 与 Task Handoff Evidence Contract 规定交接件才是仓内正式结果，而 ACCEPT 正在该文件中。**保留意见**：Bookkeeper 需要**推断**两个字段值才能闭合，这正是 §7 要求显式字段行的原因；本例可推断唯一是因为无发现且只有一个候选路径，若换成 `REWORK` 场景就不再安全。因此支持 `PROJECT_STATE.md` 已记的 O-D 后续项把三行字段写进 Reviewer dispatch 模板，使其不可复发。同时说明：本条是同模型家族（opus5 Bookkeeper 的裁定由 opus5 评审）对自身的表态，已在上方独立性披露中标明，Human 可覆盖。

**AC6 发现分类 — pass**

无 `REWORK` 发现，因此无需 `in-range` / `pre-existing-*` 的阻塞分类。下列 7 条均为观察；凡涉及早于 `base_sha` 的既有行为者均附引入提交引用，且**不作为阻塞项**，不消耗 `rework_count`。未为任何未经证实的极端场景要求新增机制。

**AC7 回执合规 — pass**

本件 Human Brief 内的 `[TASK_RESULT v2]` 含显式独立字段行 `评审结论: ACCEPT`、`问题记录: <path>`、`修复要求: none`；`结果摘要` 未超 300 字符；`检查结果` 七项且各带 `pass` 标注；三条中文交接行齐全；控制台回执与本节逐字一致，`[/TASK_RESULT]` 为最后一行非空白输出。

### 发现（全部非阻塞观察，无 REWORK）

- **O-1（建议 Human 合并前知情）**：两条余额行是**账户级、按资产**的数字，却渲染在**按 (币种, 方向) 分行**的表里。同一币种同时存在正向与反向行时（UM 行加 `no_um` 行也会），两行会重复显示同一份余额与同一份估值，竖向相加即翻倍。相邻的「全仓借款」列对同一问题已有显式处理——重复行显示 `同↑` 并带 title「账户级（按资产）；同币多行请勿竖向相加」（`frontend/index.html:4934-4945`，引入提交 `ef53a02`，2026-08-01，早于 `base_sha`）；而未去重的 `spot_balance` 单元格自 `969c455`（2026-08-01，早于 `base_sha`）起就存在。本次交付**未偏离**已批准的 §9.2 渲染（设计文本就是这两行，未要求去重），所以不构成 `in-range` 缺陷；但它把这份既有不对称从「一个数量」扩大到「两个数量加两个 USDT 估值」，而 USDT 估值比原始数量更容易被当成可相加的金额。因此按 `AGENTS.md` §8 记为附引入证据的观察，具名上交 Human：合并前可决定是否顺手把 `同↑` + 「请勿竖向相加」的既有处理复用到这两行（前端两行改动量），或先合并、留作后续项。我不将其判为 `pre-existing-release-critical`：它不触发任何资金动作、不写账务记录，相邻列已有显式反相加提示，且同一面板上方的「统一账户余额 / 现货账户余额」区块本身就是按资产的权威展示；但该判断是我的裁量，Human 可覆盖为合并前必修。
- **O-2（建议 Human 合并前知情）**：新增的「杠杆」行让对冲腿真正所在的统一账户余额第一次出现在持仓表里，但 `drift`（行标记「本地记录与实际不一致」）**仍然只比较任务记录的 `spot_qty` 与普通现货账户余额**（`backend/hedge_open_tasks/domain.py:1700-1709`，本次未改），即 `PROJECT_STATE.md` 已接受限制 B「drift flag 永久失效」原封不动。风险是认知性的：页面现在显示了统一账户余额，容易让人以为这条一致性检查也跟着修好了。合并说明里应明确「本次只增加展示，漂移检测仍看错账户，标记不出现不证明记录一致」。
- **O-3**：`≈ … U` 的估值由 `price_map` 定价，而「对冲开单持仓」标题下的数据源时间按设计只取 `um_positions` / `unified_balances` / `spot_balances` 三者最早值，**不含 `price_map`**（v4 §5.3 明确不让 `price_map` 占面板标题）。因此估值所依据的报价可能比该行显示的时间更旧，页面上无处可见其年龄。这是既有约定被延伸到一个新位置，非本次引入的错误陈述（既有余额卡片同样如此）。
- **O-4**：列头仍是「现货余额」，而单元格现在同时含「现货」与「杠杆」两行；同一份数字在上方面板叫「统一账户余额」、在行里叫「杠杆」。两处都符合已批准的 §9.2 文案，且每行自带标签，误读概率低，纯属用词一致性观察。
- **O-5**：Review-1 观察 1 的两处 EOF 空行属实，仓库无 lint/CI 门禁，建议不为它单独改动已 verified 的交付（理由见 AC5）。
- **O-6**：`spot_by_asset` 用 `free = _merge_num(...) or Decimal(0)`（`backend/hedge_open_tasks/domain.py:1768-1770`；引入提交 `969c455`，2026-08-01，早于 `base_sha`，本次为上下文行未被触碰）把缺失或不可解析的 `free`/`locked` 归零，因此一条只有 `asset`、没有 `free`/`locked` 的现货行会渲染成「现货: 0 ≈ — U」——数量画成真零而估值为未知。这是 v4.1「缺失绝不画 0」承诺在既有代码里唯一的窄口子；实际路径要求币安在余额行里同时省略两个字段，实践中未观察到。仅记录，不要求修复。
- **O-7**：抵押额度徽标迁入「借贷状态 / 资产」列后，与负费率/借贷状态文案同格，读者可能把「抵押额度已满」当成借贷能力判定。徽标文案与 title 自带解释（含判定资产与名单截至时间），且二者在业务上确有关联（`PROJECT_STATE.md` 与币安 51169 的平台级抵押额度即会导致现货腿被拒），此外这正是 Human 在 §9.1 明确要求的位置。仅记录。

### 未完成事项

无阻塞。本任务只做只读 reality check；合并、部署、Start gate、凭证与实盘操作均不在本任务授权内，ACCEPT 不等于其中任何一项。

### 命令与结果（离线，无网络/凭证/服务/实盘）

- `git log --first-parent 89103303..7f965f82` → 4 提交（控制 `e744ab3`、`8aa90b3`；交付 `65bdd817`、`7f965f82`）；`git diff --stat` 15 文件、+1160/−95。
- `git diff --stat 7f965f8282c989625a80dfde0be96b0e008cafab HEAD` → 产品代码零差异（仅 `PROJECT_STATE.md`、证据、dispatch、`status.json`），确认复跑执行的是受审代码。
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider -q backend/tests/test_positions_merge.py backend/tests/test_hedge_api.py` → `57 passed in 18.85s`。
- `node frontend/self-check.js` → exit `0`、134 `[PASS]`、末行「全部自检通过」；`diff -u` 与 `evidence/frontend-position-balance-display-v1.self-check.txt` 无差异。
- 尾字节实测：`docs/api/public-market-contract.md` 以 `\n\n\n` 结尾、`backend/tests/test_positions_merge.py` 以 `\n\n` 结尾（O-5）。
- `git blame` / `git log -1`：`969c455`（2026-08-01）、`ef53a02`（2026-08-01），`git merge-base --is-ancestor` 确认二者均早于 `base_sha`（O-1、O-6 的引入证据）。
- 全仓库 `grep` 四字段消费者：仅 `backend/hedge_open_tasks/domain.py`、两个后端测试、两份文档、`frontend/index.html`、`frontend/self-check.js`。

### 仓库内证据路径

- 受审固定 diff：`89103303bd29a64ac5915b56639f8a4a885a56b7..7f965f8282c989625a80dfde0be96b0e008cafab`
- 后端交付：`backend/hedge_open_tasks/domain.py`、`backend/tests/test_positions_merge.py`、`backend/tests/test_hedge_api.py`、`docs/api/public-market-contract.md`（v0.11 节）
- 前端交付：`frontend/index.html`、`frontend/self-check.js`
- 提交证据：`reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/backend-position-balance-display-v1.pytest.txt`、`reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/frontend-position-balance-display-v1.self-check.txt`
- 上游交接件：`reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/backend-position-balance-display-v1.handoff.md`、`reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/frontend-position-balance-display-v1.handoff.md`、`reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/review-1-position-balance-display-v1-deepseek.handoff.md`
- 需求权威：`docs/planning/hedge-status-account-refresh-v4.md` §9
- 本交接件：`reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/review-2-position-balance-display-v1-opus5.handoff.md`

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/review-2-position-balance-display-v1-opus5.handoff.md`（本件：Review-2 结论、7 条观察、独立性披露）
  2. `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/review-1-position-balance-display-v1-deepseek.handoff.md`
  3. `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/status.json`
  4. `PROJECT_STATE.md`
  5. `docs/planning/hedge-status-account-refresh-v4.md`（§9）
- 执行：Bookkeeper（`opus5`）核验本交接件（`task_id`/`role`/`stage_id`/`base_sha` 与 `status.json` 及 `git rev-parse` 一致、create-only、引用命令可复现、闭包字段齐全），在本文件的源区块结束标记后追加唯一 `## Bookkeeper Verification` 块，并把 O-1、O-2 作为具名事项整理进给 Human 的合并简报。
- 关卡：Human 决定是否合并；O-1（同币多行余额可能被竖向相加，是否合并前复用既有 `同↑` 处理）与 O-2（drift 仍看普通现货账户，标记永久失效）是需要 Human 表态的两项。部署、Start gate、凭证与实盘操作仍须单独授权。
- 不能假设的事实：ACCEPT 不等于合并、部署或实盘授权；本评审未做实盘/网络/凭证/部署，未启动任何服务；四字段为纯展示，无任何下单/借贷/风控/缓存写入消费者；既有 F4 与限制 B 未被本次交付修复；无任何自动检查绑定前端读取名与后端产出名（字段名一致性由本次人工逐字符比对确认）。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

```text
[TASK_RESULT v2]
任务 ID: review-2-position-balance-display-v1-opus5
执行结果: completed（完成）
评审结论: ACCEPT
问题记录: reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/review-2-position-balance-display-v1-opus5.handoff.md
修复要求: none
结果摘要: Review-2 只读复核固定区间 89103303..7f965f82：v4.1 §9.5 五条验收全部成立，§1-§8 边界未被触碰。四字段为纯展示投影，全仓库无下单/借贷/风控/缓存写入消费者，GET 仍零上游。两条离线命令独立复跑与证据一致（pytest 57 passed；self-check exit 0、134 PASS、逐字节相同）。ACCEPT，7 条非阻塞观察，无返工。
产物: [reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/review-2-position-balance-display-v1-opus5.handoff.md]
检查结果: [pass v4.1 §9.5 五条逐条成立；refresh cycle、source 时间语义、零上游 GET、无自动前端刷新与资金/订单/借贷/划转/Start gate/风控边界均未触碰, pass 展示诚实：未就绪全 null、单侧缺失只该侧 —、真零仍是 0、估值缺失 ≈ — U、隐私同时遮蔽数量与估值、1000x 全 null、杠杆行是统一账户毛额而非借款, pass 独立离线复跑 pytest 57 passed 与 node self-check exit 0/134 PASS，与提交证据逐字节一致；工作树产品文件与 delivery_sha 无差异, pass 证据边界已具名：无测试把已就绪账户经 HTTP 带到渲染，字段名由人工逐字符比对；版式/真实数据观感/1000x 全 — 只有真实浏览器或账户能暴露, pass 运行风险可控：四字段仅一个展示消费者，verified=false/PM 缺失/单侧 value null/资产缺失各态表现诚实；具备进入 Human 合并决策的就绪度, pass Review-1 ACCEPT 与 2 项观察成立；EOF 空行无 lint/CI 门禁、不需合并前处理；同意 Bookkeeper 对缺三行闭包字段的非拒收裁定并支持 O-D 模板化, pass 无 REWORK 发现；7 条观察中 O-1/O-6 附早于 base_sha 的引入提交 969c455、ef53a02；rework_count 保持 0]
阻塞项: [none]
本地北京时间: 2026-08-03 21:46:31 CST
下一步模型: opus5（Bookkeeper，只读核验本 Review-2 结果；与本评审同模型不同会话，独立性披露见交接件）
下一步任务: 读取：reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/review-2-position-balance-display-v1-opus5.handoff.md、reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/review-1-position-balance-display-v1-deepseek.handoff.md、reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/status.json、PROJECT_STATE.md、docs/planning/hedge-status-account-refresh-v4.md；执行：Bookkeeper 核验本交接件并在源区块结束标记后追加唯一核验块，把 O-1（同币多行余额可能被竖向相加）与 O-2（drift 仍看普通现货账户）整理为给 Human 的具名合并事项；关卡：Human 决定是否合并，部署/Start gate/凭证/实盘仍须单独授权
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- **核验授权与身份（如实披露，不粉饰）**：本核验块由**撰写上方 Source Report 的同一个 Review-2 会话**在 Human 直接指令下追加，**不是**独立 Bookkeeper 终端的核验。Human 于 `2026-08-03 22:0x CST` 在读过 Review-2 简报后明确表示「验收通过可以合并…记得同步其他文档状态」，据此本会话执行合并与状态同步。按 `AGENTS.md` §3.2 与 dispatch Stop 段，常规路径应由 Human 另启 Bookkeeper 终端完成本步；此处是 Human 显式简化流程，故本块的独立性弱于常规核验，读者不应把它当作对上方结论的第三方复核。上方 Source Report 与 Human Brief 自任务结束起未被修改。
- verified_at: `2026-08-03 22:05:04 CST`
- source_sha256: `f1bf2fce5e6764c6d0117c023063ae8a531193f7014ba6ae73b49a5d8a4be175`（唯一 `BOOKKEEPER_APPEND_ONLY` 标记前 `27306` 字节；文件内该 token 仅出现一次，源边界无歧义，与 `PROJECT_STATE.md` 的 O-A 待办口径一致）。
- status_revision_checked: `12`。评审者只读，`current_task.state` 留在 `dispatched`；本块是该任务的核验记录，revision `13` 记录 Human 验收与 stage 收口。
- identity verified: `task_id`、`role`（`Reviewer`/Review-2）、`stage_id`、`base_sha` `89103303bd29a64ac5915b56639f8a4a885a56b7` 与引用的 `delivery_sha` `7f965f8282c989625a80dfde0be96b0e008cafab` 同 `status.json` 及 `git rev-parse` 一致；本核验不改写 `delivery_sha`。
- create-only verified: `git log -- <handoff path>` 为空（从未提交），文件由本次评审新建，Allowed Files 恰好只含这一条 create-only 路径。
- isolation verified: 评审 provider `anthropic` 与区间内两位实现作者（后端 `claude_glm`/`zhipu_glm`、前端 `grok`/`xai`）均不同，满足 `agents/roles.md` 的 Review-2 隔离；Bookkeeper 同模型关系已在 Source Report 的独立性披露中具名上交 Human。
- 闭包字段完整: `[TASK_RESULT v2]` 内含显式 `评审结论: ACCEPT`、`问题记录: <本交接件路径>`、`修复要求: none`；`结果摘要` 196 字符（≤300）；`检查结果` 七项且各带 `pass`；三条中文交接行齐全；`下一步任务` 为 `读取／执行／关卡` 可执行形式且与 `Required Reading for the Next Task` 一致；`[/TASK_RESULT]` 为末行非空白输出。
- 证据可复现（本会话独立复跑，非转述）: `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider -q backend/tests/test_positions_merge.py backend/tests/test_hedge_api.py` → `57 passed in 18.85s`；`node frontend/self-check.js` → exit `0`、134 `[PASS]`，与 `evidence/frontend-position-balance-display-v1.self-check.txt` `diff -u` 逐字节一致。工作树产品文件与 `delivery_sha` 无差异，故复跑执行的就是受审代码。
- 发现分类核验: 无 `REWORK` 发现，故无需 `in-range` 阻塞分类；7 条观察中 O-1、O-6 附早于 `base_sha` 的引入提交 `969c455`、`ef53a02`（`git merge-base --is-ancestor` 已确认），其余为语义或编辑性观察。`rework_count` 保持 `0`。
- **运行期验证（超出常规核验范围，如实记录）**：Human 另行指令重启了本地服务（旧进程 PID `2494` → 新进程 PID `99045`，端口 `127.0.0.1:8787` 不变），随后以只读 GET 冒烟。这补上了 Source Report AC3 具名的证据缺口——首次有真实账户数据经 HTTP 走到本次交付的四个字段：`account.verified=true`，9 行持仓，四字段类型均为 `str`（符合契约 decimal string，例 `unified_balance='2997.0'`、`unified_balance_value_usdt='23.37660000'`，与 snapshot 源行逐字一致，无 float 化、无重算）。真实数据同时证实了 Source Report 的预测与本次交付的价值：`COOKIEUSDT` 的 `2997.0` 全在统一账户而普通现货为 `null`（改动前的单列「现货余额」完全看不见这笔），`FFUSDT`/`NOMUSDT` 则相反，`KORUUSDT`/`MUUUSDT` 两侧皆 `null`（页面两行均 `—`）。此次重启与冒烟不含任何写操作、下单、借贷或闸门变更。
- result: verified。Review-2 就完整固定 v4.1 产品区间返回显式 ACCEPT，无阻塞发现；Human 已作出验收与合并决定，stage 按 `AGENTS.md` §9 收口。本块只记录状态，不代表部署、Start gate 变更或实盘授权——那些仍须 Human 单独授权。

## Errata (append-only)

（预留）

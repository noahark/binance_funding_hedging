# Phase 2 方向草案：私有只读验证 + 资金费率排序

状态: DRAFT-2（Fable5 修订，2026-07-04；吸收 GPT/GLM/Kimi 三方 round-1
REWORK 评审 + Gemini 端点考证 + 用户排序 UI 新决策）

**复杂度申报: MILESTONE**（引入 API key、签名端点、安全红线修订、契约修订，
符合 AGENTS.md 里程碑标准；流程安排见 §7）。

## 1. 背景与动机

Phase 1（纯公开数据）已闭环。最大信息缺口是 `PRIVATE_BORROW_VALIDATION_REQUIRED`：
`isMarginTradingAllowed` 只是交易对级公开候选信号，不区分全仓/逐仓，不覆盖
统一账户可借性，无利率/额度数据。负费率策略（做多永续 + 借币做空现货）在
验证这些之前无法推进。用户已创建 API key 并决定进入 Phase 2；同时提出前端
资金费率排序需求。

Round-1 需求评审（2026-07-04，三方独立，均 REWORK）已落档于
`reports/agent-runs/phase2-direction-v1/`：GPT/Codex、claude_glm、kimi27；
另有 Gemini 端点考证 + Fable5 对 `llms-full.txt`（官方文档转储）的原文核验
（`gemini-endpoint-research.md`）。本 DRAFT-2 吸收全部 P1/P2 与大部分 P3。

## 2. 目标与任务切分

- **Task A（后端，backend discovery + contract）**：私有只读签名通道基建 +
  杠杆可借性市场级/账户级验证 + 借币利率 → `borrow_validation` 契约块。
- **Task B（前端，仅排序）**：资金费率列排序（见 §6）。**不包含**私有验证
  结果展示——该展示等 Task A 契约冻结后作为下一阶段（吸收 GPT/Kimi 对
  耦合风险的一致意见；Task B 因此与 Task A 零契约耦合）。
- 非目标：任何交易/划转能力；净收益模型；开仓规划；私有数据前端展示。

## 3. 安全红线修订（吸收三方全部加固要求）

Phase 1 红线原文：
> "No API key, signed endpoint, private account endpoint, user data stream."
> "No order, borrow, repay, transfer, websocket."

Phase 2 修订为：

1. **允许**：只读语义的 HMAC-SHA256 签名 **GET** 请求，仅限 status.json 列明
   的端点白名单。
2. **永久禁止**（跨阶段 invariant，脱离 phase 存在）：order、borrow 执行、
   repay、transfer、withdraw、listenKey/user data stream、websocket、任何
   POST/PUT/DELETE 及交易语义端点。
3. **签名通道技术门（全部入验收，负向单测强制）**：
   - **单一签名出口**：`backend/services/private_client.py` 是全仓库唯一构造
     HMAC 签名的位置；grep 级单测断言 `hmac|HMACSHA256|signature` 命中点仅
     该文件（GLM P2）。
   - **deny-by-default 白名单**，粒度为 `(method, exact-path)` 二元组（非
     前缀匹配）；白名单外 path、白名单内 path 的非 GET method，均在**签名
     构造之前** raise（GPT/GLM/Kimi 一致）。
   - **非 GET 硬拦截**：客户端仅实现 GET 代码路径。
   - **直连守卫**：静态/测试级检查，产品代码不得绕过 private_client 对
     Binance 私有域直连 HTTP（GPT）。
   - **出站审计日志**：每次签名请求记录 `(logical_endpoint_id, method,
     sanitized_path, timestamp, http_status/error, latency)`；禁止记录
     key/secret/signature/完整 query string/头部（三方一致）。
   - **降级路径单测**：key 缺失/失效 → 优雅降级为 Phase 1 行为（公开数据 +
     unverified），降级分支本身有测试（GLM）。
   - **限频与健壮性**：weight 预算（crossMarginData 权重高）、429/-1003
     退避、签名 timestamp/recvWindow 偏移处理（GLM P3）。
4. **密钥管理与用户决定（保持 DRAFT-1.2 记录）**：key/secret 仅经环境变量
   注入，不落 repo/日志/报告。用户决定（2026-07-04，覆盖 Fable5 收权建议）：
   保留现有全权限 key（含交易/借币/划转权限），IP 白名单已绑定。风险披露：
   IP 白名单不约束白名单机器上代码自身行为 → 代码层白名单为主防线，
   §3.3 全部技术门为 review-1/review-2 必查项；ADR 记录残余风险（Kimi）。
5. **证据脱敏政策**：
   - 抓取即脱敏，不落明文中间文件；脱敏脚本入库、可复核，配单测断言落档
     JSON 不含账户标识字段（uid/email/balance/free/locked/amount 等）（GLM）。
   - 落档 URL **整体剥离 query string**（含 recvWindow，不止 key/sign/
     timestamp 三项）（GLM/Kimi）。
   - 签名后的响应即使形似市场级也须敏感性复核后才可提交（GPT）。
   - 启动自检 = 读通道验证（白名单内只读端点一次调用），快照元数据记录
     `private_channel: enabled/disabled`，不记录 key 任何片段。

## 4. 端点族（已由证据裁决）

**结论：用户账户「统一账户模式（非专业版）」= Binance Portfolio Margin
（普通版）→ 账户级验证走 `/papi` 族。**

证据（`gemini-endpoint-research.md`，基于官方文档转储 `llms-full.txt` 原文）：
文档区块标题 `Portfolio Margin (/papi)`（L48419）；`/papi/v1/um/*` 端点中文
描述使用「统一账户」字样且 Operation ID 为 `portfolioMarginUm...`（L186286）；
「统一账户专业版」对应 `Portfolio Margin Pro`（L48499）。GLM round-1 P1
（「非专业版走 /sapi」）被原文否定，其余 GLM findings 不受影响仍采纳。

分层（吸收 GPT required fix 1，重命名以消除「2a=可借已验证」误读）：

- **classic_margin_reference（市场级参考，`/sapi`）**：
  `GET /sapi/v1/margin/allPairs`（经典全仓杠杆对清单）、
  `GET /sapi/v1/margin/allAssets`（isBorrowable/isMortgageable 参考）、
  `GET /sapi/v1/margin/crossMarginData`（费率/额度表）。
  语义：仅证明「经典杠杆体系在列」，**不构成统一账户可借结论**。
- **portfolio_account_borrow（账户级结论，`/papi`）**：
  `GET /papi/v1/margin/maxBorrowable`（当前实际最大可借 + borrowLimit）。
  只有此层可产生用户账户可借性结论。
- **H_intake discovery 实抓（运行时确认）**：controller 持用户 key 对上述
  白名单端点各做一次只读实抓，脱敏落档至
  `reports/api-samples/<stage-id>/`，确认账户可访问性与响应结构后冻结
  字段矩阵（Kimi required fix 1；Hard Gates raw-evidence 原则）。若 `/papi`
  实抓失败（账户形态与文档不符），升级用户决策，不得静默 fallback。

## 5. Task A 设计要点（后端）

- **契约演进：独立块，枚举零改动**（GPT+GLM 多数意见；Kimi 枚举扩展方案
  记为 dissent 备档）。`negative_funding_status` 现有枚举与优先级序列
  **完全不变**，`classify.py` 零改动。row 新增独立块：
  ```json
  {
    "borrow_validation": {
      "verified": false,
      "classic_margin": {
        "pair_listed": null,
        "asset_borrowable": null,
        "daily_interest_vip0": null,
        "source": "sapi_reference"
      },
      "portfolio_account": {
        "max_borrowable": null,
        "borrow_limit": null,
        "source": "papi_max_borrowable"
      },
      "checked_at": null,
      "error": null
    }
  }
  ```
  待 `/papi` 账户级证据稳定后，再由后续阶段从该块**派生**新的负费率执行
  状态（届时才动枚举，且只追加不重命名）。
- **三态语义**（Kimi P2）：未启用/失败 = `verified:false` + 字段 null +
  `error` 注明；已验证不在列 = `verified:true, pair_listed:false`；已验证
  在列 = `verified:true, pair_listed:true` + 数据字段。前端（下一阶段）按
  此三态渲染，不得把「不在列」渲染为「未验证」。
- **利率取档规则**（GLM/Kimi P1-P2）：`crossMarginData` 返回 asset×VIP
  分档费率表；契约写死落档字段为 **VIP0 基准档** `daily_interest_vip0`；
  用户实际适用利率（需账户 VIP 等级）留后续账户级阶段；fallback 数据源
  `GET /sapi/v1/margin/interestRateHistory` 最新点。字段名/JSON path/单位
  以 discovery 实抓为准冻结（端点矩阵：source family、security type、
  参数、raw path、脱敏规则、TTL、失败模式——GPT required fix 4）。
- **`checked_at` = 请求成功时刻**（非数据生效时刻），契约注明（GLM P3）。
- **缓存**：borrow_validation 数据低频，独立 TTL（建议 1h），不随 60s
  快照缓存重复签名请求。
- **契约版本**：`docs/api/public-market-contract.md` bump v0.1 → v0.2，
  附 Phase 2 amendment 变更记录（Kimi P3）。
- `papi base_url` 进 Config（端点族已由证据确认，不再是过度配置）。

## 6. Task B 设计要点（前端，仅排序）

**用户新决策（2026-07-04，取代 ui-cn-v1 的合并列方案）**：

- **拆列**：「资金费率/结算时间」合并列拆回两个独立列「资金费率」与
  「结算时间」（合并展示导致排序语义不清，用户裁定拆开）。两列的既有
  格式化规则不变（string-shift 费率、北京时间 HH:mm）。
- **排序控件**：资金费率列表头后加排序箭头按钮，点击三态循环：
  **倒序（降序）→ 正序（升序）→ 默认（原始顺序）**，当前态有视觉指示。
- **排序值**：按**带符号**费率值排序（GPT 建议采纳：绝对值降序会把尚未
  验证可执行的负费率行顶到最前；正费率才是当前可执行方向）。绝对值排序
  不做，待负费率路径验证后再议。
- **比较器**：纯字符串十进制比较器（符号 → 整数位 → 小数位；GLM/Kimi
  多数意见，与 display 层同源、零浮点争议），配回归单测：全部合规
  fundingRate 字符串边界集（负值/0/-0/前导零/不同小数位）的排序结果
  与十进制语义一致。display 层 string-shift 红线不变。
- **状态保持**：排序态在 60s 自动刷新后保持（与筛选状态同一存储模式）；
  刷新后行集合增删须容错。
- **范围红线**：本任务不引入 `borrow_validation`/`margin_private` 任何
  字段消费；不改 formatFundingRate/formatBeijing*。

## 7. 流程（MILESTONE 路由）

- 按 AGENTS.md，MILESTONE 需 direction panel + 方向合成 + 用户批准。
  **等效履行提案（待用户批准）**：round-1 三方独立评审（GPT/GLM/Kimi）+
  Gemini 考证已构成 panel 实质（独立 draft 齐备且落档）；本 DRAFT-2 为
  修订稿；**方向合成按常规交 GPT/Codex**——用户将 DRAFT-2 交 Codex 做
  synthesis/ratification round，其产出落档为 `06-direction-synthesis.md`
  等效物，用户批准后进入 stage design。
- **实施结构**：单阶段双任务，按 `docs/parallel-development-mode.md`
  （ADOPTED-TRIAL）首次试运行——Task A（GLM 后端）‖ Task B（Kimi 前端，
  仅排序）。两任务零契约耦合（§2），Kimi round-1 对并行的反对理由
  （B 依赖 A 契约漂移）已随 Task B 剥离私有展示而消解；GPT 的条件
  （"limited to sorting only"）即本方案。R9 dispatch packet 由 Fable5 出。
- **硬门**：H_intake 完成 §4 discovery 实抓并冻结端点矩阵后，Task A 才可
  进入实现；Task B 不受此门约束可先行。
- 私有验证结果的前端展示 = 下一阶段（契约冻结后），届时 `MARGIN_PUBLIC_UNVERIFIED`
  页面警告随之更新。

## 8. 已决结论与遗留

已决（本轮吸收，正文已含）：安全技术门清单（§3.3）；端点族 `/papi`（§4）；
独立块 + 枚举零改动（§5）；VIP0 取档（§5）；拆列 + 三态排序箭头 + 带符号
排序 + 字符串比较器（§6）；并行试运行且 Task B 仅排序（§7）。

待用户拍板：
1. §7 MILESTONE 等效履行提案（三方评审替代 panel、Codex 做最终合成）；
2. Codex synthesis round 的 ACCEPT 后即开 stage（H_intake 起手是 discovery
   实抓，需要你在 controller 会话配好环境变量）。

已知风险（ADR 级，进 stage 时落 11-adr.md）：全权限 key 残余风险（§3.4）；
`/papi` 实抓与文档不符的低概率分支（§4，升级用户决策）；crossMarginData
字段结构以实抓为准（2024-03 后 sapi 有调整记录，GLM 提示）。

---

修订记录:
- DRAFT-1 (2026-07-04 18:20 CST, Fable5): 初稿。
- DRAFT-1.1 (2026-07-04 18:35 CST, Fable5): 账户类型确认（统一账户非专业版）；
  key 权限超配事实 + 收权前置条件。
- DRAFT-1.2 (2026-07-04, Fable5): 用户决定保留全权限 key（IP 白名单已绑定），
  代码层白名单升级为主防线（三项加固后果）。
- DRAFT-2 (2026-07-04, Fable5): 吸收三方 round-1 REWORK 全部 P1/P2：安全技术门
  全清单（§3.3）；端点族由 llms-full.txt 原文证据裁决为 /papi（§4，GLM P1
  被否定）；契约演进改独立 borrow_validation 块、枚举零改动（§5）；VIP0
  取档规则（§5）；用户新决策——拆列 + 排序箭头三态切换（§6，取代合并列）；
  带符号排序默认（GPT）；字符串比较器（GLM/Kimi）；MILESTONE 申报 + 等效
  panel 提案（Kimi P1）；Task B 剥离私有展示实现零耦合并行（§7）。

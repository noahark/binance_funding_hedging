# Phase 2 方向草案：私有只读验证 + 资金费率排序

状态: DRAFT-1（Fable5 起草，2026-07-04；待用户携至 GPT/其他模型对齐需求后修订）

## 1. 背景与动机

Phase 1（纯公开数据）已闭环：三个阶段（impl-v1 / bstock-alias-v1 / ui-cn-v1）
全部验收。当前最大的信息缺口是 `PRIVATE_BORROW_VALIDATION_REQUIRED`：
`isMarginTradingAllowed` 只是交易对级公开候选信号，不区分全仓/逐仓，
不覆盖统一账户（Portfolio Margin）可借性，更没有利率/额度数据。
负费率策略（做多永续 + 借币做空现货）在验证这些之前无法推进。

用户已创建 API key，决定进入 Phase 2。同时提出前端资金费率排序需求。

## 2. 目标

- **Task A（后端）**：引入只读私有数据通道，把杠杆可借性从「候选」升级为
  「已验证」，并带出借币利率（负费率策略的成本侧）。
- **Task B（前端）**：资金费率列排序 + 私有验证结果展示。
- 非目标（本阶段不做）：任何交易/划转能力；净收益模型；开仓规划。

## 3. 安全红线修订提案（最敏感部分，请重点审）

Phase 1 红线原文：
> "No API key, signed endpoint, private account endpoint, user data stream."
> "No order, borrow, repay, transfer, websocket."

Phase 2 修订为：

1. **允许**：只读 API key + HMAC-SHA256 签名 **GET** 请求，且仅限
   status.json 中列明的**端点白名单**（见 §5）。白名单外的签名请求 = 越界。
2. **永久禁止**（措辞不变，脱离 phase 存在）：order、borrow 执行、repay、
   transfer、withdraw、listenKey/user data stream、websocket、任何 POST/PUT/DELETE
   交易语义端点。
3. **密钥管理**：
   - key/secret 仅经环境变量注入（`BINANCE_API_KEY` / `BINANCE_API_SECRET`），
     不落 repo、不落日志、不落报告/证据文件（AGENTS.md 第 77 行已有禁令，重申）。
   - Binance 侧 key 权限仅勾选「读取」（Enable Reading），不开现货/杠杆/合约
     交易权限；建议绑定 IP 白名单。
   - 后端启动时做一次**权限自检**：调用一个只读端点验证 key 有效，并在
     snapshot 元数据中记录 `private_channel: enabled/disabled`（不记录 key 任何
     片段）。key 缺失时优雅降级为 Phase 1 行为（公开数据 + unverified）。
4. **证据脱敏政策**（`reports/api-samples/**` 落档规则新增）：
   - 市场级私有响应（杠杆对清单、利率表）可原样落档；
   - 账户级响应（若涉及）必须去除 UID、余额、额度等账户标识后落档，
     脱敏脚本与规则本身入库可复核；
   - key、签名、时间戳参数一律不出现在落档 URL/头部中。

## 4. 账户类型分叉（需用户确认的第一决策点）

经典杠杆与统一账户（Portfolio Margin）端点族不同（`/sapi` vs `/papi`）。
用户此前问及统一账户全仓，倾向按统一账户走，但**必须先确认账户实态**。

建议切分：

- **Phase 2a（本阶段，市场级，与账户类型基本解耦）**：
  - `GET /sapi/v1/margin/allPairs`（签名）：全仓杠杆对官方清单 →
    把 `margin_public.source: "unverified"` 升级为
    `margin_private.cross_pair_listed: true/false`；
  - 借币利率数据（如 `GET /sapi/v1/margin/crossMarginData` 或利率接口，
    以实际抓样为准）：`base_asset_daily_interest: <str>`。
- **Phase 2b（下阶段，账户级）**：统一账户下该资产实际可借额度
  （maxBorrowable）、质押率、账户模式确认。依赖 2a 的通道基建。

理由：市场级数据回答「这个币在杠杆体系里能不能借、成本多少」的普适部分，
不依赖账户模式，契约稳定；账户级数据才需要分叉端点族，且脱敏要求高。

## 5. Task A 设计要点（后端，claude_glm）

- 新模块 `backend/services/private_client.py`：签名 GET 客户端，端点白名单
  硬编码为常量元组，白名单外调用直接 raise（防御式，越界即 fail-fast）。
- `Config` 增加 `private_enabled`（由 env 是否存在推导）、`papi/sapi base_url`。
- 数据模型：row 新增 `margin_private` 块（与既有 `margin_public` 并列）：
  ```json
  {
    "verified": true,
    "cross_pair_listed": true,
    "base_daily_interest": "0.00025000",
    "checked_at": "2026-07-05T00:00:00Z"
  }
  ```
  key 缺失/请求失败时 `verified: false` 且其余字段 null（降级不阻塞快照）。
- `negative_funding_status` 枚举扩展（契约修订，需脱敏 raw 证据）：
  `PRIVATE_BORROW_VALIDATION_REQUIRED` 细化为
  `BORROW_LISTED_PENDING_ACCOUNT_CHECK`（2a 已验清单在列，待 2b 账户级）与
  `BORROW_NOT_LISTED`（清单不在列，负费率不可行）。
  优先级序列保持文档化且不可重排；bStock 的 `DISABLED_BSTOCK` 拦截不变。
- 私有请求频率：随 60s 快照缓存同步，杠杆清单/利率数据本身低频，
  可用更长 TTL（如 1h）单独缓存，避免无谓签名请求。
- `classify.py` 纯函数性质保持：私有验证结果作为输入参数进入，不在分类层发请求。

## 6. Task B 设计要点（前端，kimi）

- **资金费率列排序**：表头点击切换 升序/降序/默认，当前排序列与方向有
  视觉指示。默认排序建议按费率**绝对值降序**（机会导向，正负都看得到），
  具体默认值列为待对齐问题。
- **红线边界澄清**：display 层 string-shift 红线**不变**；排序**比较器**允许
  数值化（fundingRate 8 位小数在 double 精度安全区），或实现纯字符串
  十进制比较器——二选一，倾向前者 + 注释声明边界，避免评审争议。
- 排序状态在 60s 自动刷新后**保持**（刷新重渲染不得重置用户选择，
  与现有筛选状态同一存储模式）。
- `margin_private` 展示：验证通过的行升级 badge 文案（如
  `BORROW_LISTED_PENDING_ACCOUNT_CHECK(已列入可借清单,待账户级验证)`），
  沿用「英文枚举(中文解释)」口径；页面级 `MARGIN_PUBLIC_UNVERIFIED` 警告在
  私有通道启用时替换为私有验证状态说明。
- 利率列（若 Task A 带出）：`借币日利率` 展示，同样 string-shift 格式化。

## 7. 阶段划分与流程建议

- 本阶段 = **前后端双任务** → 按 `docs/parallel-development-mode.md`
  （ADOPTED-TRIAL）首次试运行：Fable5 出全套 R9 dispatch packet，
  GLM(Task A) ‖ Kimi(Task B) 并行 + 嵌入交叉预审，bookkeeper 串行落盘。
- **契约先冻结**：Task B 依赖 `margin_private` 结构与新枚举 → H_intake 的
  10-design 中先冻结 schema 草案（含 fixture 样例），两端对冻结契约并行；
  Task B 的排序部分零依赖，可先行。
- 排序是纯 UI、私有通道是契约级——若评审认为耦合风险高，可拆两个阶段
  （排序先走一个轻量单任务阶段）。列为待对齐问题。

## 8. 待对齐问题（请 GPT/其他模型逐条挑战）

1. 账户类型：用户实际是统一账户（PM）还是经典杠杆？Phase 2a/2b 切分
   是否成立，还是应直接按账户类型一步到位？
2. 安全基线（§3）是否充分？是否需要额外要求（如启动时主动探测 key
   无交易权限、签名请求全量审计日志）？
3. 脱敏落档规则（§3.4）是否可执行、可复核？市场级/账户级的边界划法对不对？
4. `negative_funding_status` 枚举细化（§5）vs 新增独立字段，哪个契约演进
   代价更低？
5. 排序比较器允许数值化（display 红线不变）是否接受？默认排序方向定什么？
6. 双任务并行（§7）vs 拆两个串行阶段，风险偏好如何取舍？
7. 借币利率数据的具体端点选型（crossMarginData 需要 VIP 等级上下文？）——
   需实抓验证后冻结。

---

修订记录:
- DRAFT-1 (2026-07-04 18:20 CST, Fable5): 初稿。

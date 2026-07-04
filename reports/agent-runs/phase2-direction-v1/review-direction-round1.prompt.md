# Dispatch: Phase 2 方向草案需求评审（round 1，多模型通用）

用途: 用户将本 prompt 原样粘贴给各评审模型（GPT/Codex、或其他），各模型
独立评审 `docs/phase2-direction-draft.md`。回复将被逐字落档至
`reports/agent-runs/phase2-direction-v1/<model>-review-round1.raw-output.md`。

--- PROMPT BODY（以下为任务正文，原样发送） ---

你是一名**独立需求评审者**（只读，不写代码，不改文件）。请评审本仓库的
Phase 2 方向草案，产出结构化意见供落档。

## 评审对象

`docs/phase2-direction-draft.md`（DRAFT-1.2，commit `f1297a5`）——
Phase 2 = 私有只读数据通道（杠杆可借性验证 + 借币利率）+ 前端资金费率排序。

背景材料（按需查阅）:
- `AGENTS.md`（治理与 Hard Gates）
- `docs/api/public-market-contract.md`（现行冻结契约，含 route_class /
  negative_funding_status 枚举与优先级）
- `docs/parallel-development-mode.md`（ADOPTED-TRIAL，本阶段拟首次试运行）
- `backend/domain/classify.py`、`backend/services/snapshot_service.py`
  （现有分类与数据流）

## 前提（已决定的事实，评审其后果而非重开决定）

1. 用户账户为**统一账户模式（非专业版）**，现货/合约账户有少量资金。
2. 用户决定**保留现有全权限 API key**（含交易/借币/划转权限），IP 白名单
   已绑定；代码层端点白名单因此为主防线（§3.3 三项加固后果）。
   —— 可以指出此前提下的残余风险与更强缓解，但不要求用户换 key。

## 评审重点（按优先级）

1. **§3 安全红线修订**：在上述前提下，白名单强制 + 单测断言 + 读通道自检
   + 证据脱敏是否构成充分基线？缺什么补什么，给可执行的具体要求。
2. **§8 Q1 剩余子问题**：统一账户模式下，经典 `/sapi/v1/margin/allPairs`
   全仓杠杆清单作为「市场级可借信号」是否失真？统一账户的可借资产集合与
   经典杠杆清单的关系如何？这决定 Phase 2a/2b 切分是否成立。
3. **§8 Q7 端点选型**：借币利率的数据源（`/sapi/v1/margin/crossMarginData`?
   利率历史? 统一账户 `/papi` 族?）——给出你认为正确的候选与验证方式。
4. §5 契约演进：`negative_funding_status` 枚举细化 vs 新增独立字段，
   哪个代价低？给结论和理由。
5. §6 排序：比较器数值化（display 层 string-shift 红线不变）是否接受？
   默认排序方向建议？
6. §7 流程：双任务并行（parallel-mode 首试）vs 拆两个串行阶段，
   基于本阶段的实际耦合度给建议。
7. 其余任何你认为的设计缺陷、遗漏、过度设计，自由列出。

## 输出格式（务必遵守，便于逐字落档）

1. 逐条回应上述 1-7（含 §8 未覆盖问题可合并作答），每条给明确结论；
2. findings 列表：`P1/P2/P3 - 标题 - 一句话缺陷 - 具体修法`；
3. 总体 verdict：`ADOPT-AS-IS` / `REWORK`（需列 required fixes）/ `BLOCKED`
   （说明阻塞原因）；
4. 若 REWORK：附一段「给 Fable5 的修订启动文案」；
5. 末尾注明：你的模型身份、当前本地北京时间、建议的下一步调用模型。

约束：只读评审；不需要也不得进行任何签名/私有 API 调用；如需事实核查
仅允许匿名公开 GET 或查阅仓库内既有证据（`reports/api-samples/**` 只读）。

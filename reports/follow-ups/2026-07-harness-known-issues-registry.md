# Follow-up: Harness known-issue 台账（red-gate-greening 直修弧登记）

- 来源: 直修弧 `2026-07-red-gate-greening-v1` T6（治理规则落文档），授权见
  `reports/agent-runs/2026-07-red-gate-greening-v1/09-user-authorization.md`
- 落档人: Kimi（moonshot_kimi，直修弧实现者）
- 落档时间: 2026-07-17
- 规范落点: `docs/harness-design.md` "Close-out Governance (Subordinate Rules)" +
  "Known Issues Registry"（模板仓同一文本，经 T5 下行）

台账原则（白名单）：**等首例再收**——下列各项除非出现真实首例或用户明示拍板，
不得提前"修"。三条治理规则（max_rework 硬停 / 文档 stage 可带 P2 收口+语义收敛 /
Harness 修复登记攒批）从属于"review-2 + 用户显式验收"主线，不降低任何门。

## K1 — class-2 例外（review-2 REWORK 但内容干净）：首例已现，等用户拍 D-i

`2026-07-docs-truth-sync-v1` 即首例：review_1 尾随（class-1 形）+ `review_2.verdict
== REWORK`（class-2，v1 不收）→ fixture 永久 known_red。收编条件（若用户拍"收"）：
白名单扩一个 `assertion_id` + 每条残余 finding 的用户逐条处置证据 + 钉指纹。
不收则永久 known_red，亦成立。

## K2 — Provider 身份治理（P3）

未注册 provider 串在 status 中目前按自声明处理；已知集合已归一（kimi→moonshot_kimi）。
更大范围注册表治理等具体冲突出现再收。

## K3 — 纯 evidence 段豁免（等首例）

若未来某 stage 任务间只有 bookkeeper 证据提交、且无全量 review 覆盖，D3-v2 下这些段
无担保而红。现行流程 review-2 必审全量，该情形尚无实例。

## K4 — 路标祖先序 hygiene（P3）

D3-v2 不强制 waypoints 祖先序（快照差传递性不依赖祖先序）。若实践中出现乱序路标，
可加线性 lint；非 soundness 必需。

## K5 — bookkeeper 多任务顺手记路标惯例

多任务 stage 的 bookkeeper 顺手在 status 记 `coverage_waypoints[]`（集成路标），
使前缀评审可担保子段；有全量 review-2 时不需要（缺省 `[base, head]` 即可）。

## K6 — legacy stage 记录红（fixture 已知，不阻塞）

- `2026-07-harness-flow-optimization-v1`: status 值 `accepted_and_merged_to_main` ∉
  ALLOWED_STATUSES 等多条。可选补救 = 一词迁移为 `accepted`（历史原文 git 永存），
  用户另拍，不属本弧。
- `2026-07-env-startup-v1`: 早期手工流程记录不完整（缺指纹/review 文件）。
- `2026-07-local-service-launchd-v1`: review_1 尾随（class-1 形），如用户授权可比照
  bookticker 记例外转绿。
- `2026-07-public-market-bstock-alias-v1` / `-impl-v1`: 缺 `12-development-breakdown.md`。
- `2026-07-public-market-ui-cn-v1`: task B 指纹记录重算不符（validate_tasks 级）。

## K7 — 规则 3 当前零真实用户（防误删注记）

review-scoped 尾随段例外路径对现存真实数据零使用（唯一 review_2 也尾随的
docs-truth-sync 因 verdict 不可降级依然红）。保留理由：防御纵深 + A8 对抗用例覆盖；
零使用不是删除理由。

---
本地北京时间: 2026-07-17
下一步模型: 各条目 owner（K1/K6-部分 = 用户拍板；其余等首例）

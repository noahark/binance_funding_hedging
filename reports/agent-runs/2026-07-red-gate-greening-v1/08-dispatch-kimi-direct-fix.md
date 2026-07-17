# Dispatch — 直修收弧（executor → Kimi）

规范来源: 同目录 `07-fable5-direct-fix-plan.md`（**v2**，已吸收五模型 review）与
`06-direction-ruling-d3-fable5.md`（D3-v2 判定规范）。冲突时以 07-v2 为准；07-v2 未尽
细节以 06 为准。你（Kimi）已在 review 中实证过大部分地基，本包只压缩执行要点。

角色与路由（对 07-v2 审计协议的更新）：实现 = **Kimi**（用户改派，原 Fable5 直修）。
实现后 raw-diff 独立评审 = **Codex + Fable5**（Fable5 不再实现故可评审；其 D3 设计者
身份按惯例披露）。用户终审后才 push。用户本次派工消息 verbatim 即直修授权证据，落
`09-user-authorization.md`（第 0 步一并提交）。

## 硬边界
- 不改写任何历史 review 原文（演进只追加 note）；不改任何历史 diff_fingerprint；
  不改产品行为/端点/结构；bookticker 只**向前追加**字段（tasks[] 坐标、review 原文、
  指纹一律不动）。
- **全程零 push**（两仓）。本仓 main 允许本地合并；模板仓在分支 `harness/d3-v2-direct`
  工作后本地合 main。用户终审后统一 push。
- **D-i（class-2 收编）默认不做**：用户尚未拍板。docs-truth-sync 在 T2a 迁移表标
  `known_red (class-2, pending user decision D-i)`；白名单**不得**扩项（扩项需用户明示）。

## 执行序与修改点

**第 0 步**：funding_hedging 提交未跟踪的 05/06/07/08/09 与 82 文件（clean-worktree 前置）。

**T0〔模板仓〕Stage A 账本收口**：
`reports/agent-runs/2026-07-harness-authorized-exception-v1/status.json` —— 解
`stage_accepted_waiting_user` vs `merged_back_to_main:true` 矛盾：status 改终态、补
`user_acceptance`（原文："接受 Stage A，执行合并 + cp"，2026-07-17）；70-handoff 同步。
查无原文处如实登记证据缺口，不补造。

**T2a〔两仓〕Golden 基线（必须在 T1 之前）**：
新建模板仓 `scripts/validate-all-stages.py`：fixture 模式 = 记录级校验（跳过
branch/worktree/HEAD 上下文断言）、`--repo-root` 参数、排除 `_template/`。用**现行**
validator 对两仓全部 stage 落盘 committed 基线 + 薄迁移表（预期变化仅limited于）：
bookticker chain-red+review1-trail → green_with_exception（T3 后）；docs-truth-sync →
known_red(class-2, D-i pending)；funding-annualized-history-v1 chain-red → green
（登记为 v2 预期战果）；harness-flow-optimization-v1 → known_red（status ∉
ALLOWED_STATUSES）；4 个 legacy 字符串-task stage → known_red。
验收口径 = **无未登记的红、无未登记的判定翻转**。

**T1〔模板仓〕D3-v2 重写（核心）**：`scripts/validate-stage.py`
- `validate_task_coverage()` 改路标模型：覆盖担保只有两条——规则 1 = top-level review
  指纹 == 重算 `base..Wi` 前缀（**全量命中 j=n ⇒ 全段已担保，无需 waypoints**）；
  规则 3 = class-1 例外按既有 scope 语义盖该 review 匹配前缀之后的尾随段。
- **删除** own-review 覆盖担保路径（`_task_own_review_covers` 整体退役——dev-diff 冒充
  口子随之消失）；**删除**链式检查与 `covers_through_task` 前缀键（0/23 使用，留一行
  compat note）。`coverage_waypoints[]` 可选：逐项验有效 commit、W0==base、Wn==head、
  无重复；缺省派生 `[base, head]`。不新增 scope 语法、不新增 assertion_id；`task:<id>`
  scope 映射 = task.head 所在路标段，task.head ∉ 路标 → 记录错误。
- **DoD = 对抗用例 A1-A8 实跑留档**（本 stage `61-adversarial-d3v2.txt`）：A1 无担保段
  fail；A2 own-review/dev-diff 冒充 fail（担保路径已删，构造记录必须被拒）；A3 路标
  首尾≠base/head fail；A4 畸形/重复路标 fail；A5 单任务退化行为不变；A6 全量 review-2
  命中即绿；A7 bookticker 真实数据+class-1 → PASS-with-exception；A8 伪造路标但段无
  担保 fail。另跑 `python3 -m py_compile`。
- 文档：模板仓 `docs/harness-design.md` D3 段改 v2；Stage A `10-design.md` §3/§5
  **追加订正 note**（不改写原文）；`_template/status.json` 加 `coverage_waypoints` 示例。

**T2b**：重跑 runner 与基线 diff，仅允许迁移表内变化，输出留档。

**T6〔模板仓〕治理规则 + known-issue 台账**：harness-design 追加三条（max_rework 打满
硬停→known-issue+override 关账；文档 stage 可带 P2 收口、语义收敛为默认；Harness 修复
默认登记攒批），标注从属于"review-2 + 用户显式验收"主线。台账（harness-design 注记 +
`reports/follow-ups/`）：身份治理 P3、纯 evidence 段豁免、路标祖先序 hygiene、
class-2(D-i pending)、bookkeeper 多任务顺手记路标惯例。

**T5〔下行〕merge-not-copy**：同步 `validate-stage.py`、schema、
`validate-all-stages.py`、`docs/harness-design.md`、T6 文本到 funding_hedging **main**
（本地合并）。**禁整文件覆盖** `_template/status.json`——只增 `coverage_waypoints`
示例，保留本仓 `session_receipts`/`reporting_preferences`（update 脚本 `:110-113` 的
rsync 路径不要走）。carve-out 校验（diff 命令留档）：AGENTS.md 本仓专有段、
`_template/status.json` 本仓字段、harness-design 本地 3 行注；`model-adapters.md` 不动。

**T3〔本仓 main〕bookticker 转绿**：`2026-07-bookticker-open-columns-v1/status.json`
追加 `authorized_exceptions[]` 一条：assertion_id=`review_fingerprint_trails_status`、
scope=`review_1`、applies_to_fingerprint=`a9218b7f…:dd72d6ae…`（现值全串）、
authorizer=`"user"`、evidence_file=该 stage `70-handoff.md`（已提交 blob，:35-38 授权
verbatim）+ `evidence_sha256`（重算填入）、reason 言明"digest 封印当前 blob，日后编辑
即破印回红，属设计行为"、at=ISO。pre-accept 在 main 跑，PASS-with-exception 输出写
新文件 `62-bookticker-preaccept-green.txt`（不动任何冻结 blob）。

**T4〔本仓 main〕docs-truth-sync 归一**：仅 `70-handoff.md` 正文与已接受/已合并终态
对齐（status.json 已归一，勿动实质）；追加 note：bookticker 真绿依赖本直修 T1+T3。

**T7〔本仓，独立 commit〕prose 清欠**：
`schemas/api/public-market/symbol-snapshot.schema.json` `:5`（改 mode-dependent 表述，
非简单删句）与 `:38-39`；`schemas/api/public-market/funding-history.schema.json`
`:33-34`；`backend/services/snapshot_service.py:320-322` docstring。**连带删除**
`docs/api/public-market-contract.md:296-300`/`:397-410` 的 drift 披露注记及 Residual
Risks 对应条（避免反向漂移）。commit message 定性："对已批准真值的同步（docs-truth-sync
收敛契约 + status.user_authorizations[2]），不引入新事实"。
验收：schema diff 仅 description 行；backend 全量 pytest（按实际收集数）+
`node frontend/self-check.js`（80）。

**收口**：red-gate-greening-v1 补 status.json/70-handoff 终态；ACTIVE.json 归位；
执行足迹（每 T 的命令+输出）汇入 `60-execution-log.md`。

## 交付物清单
两仓本地 commit（零 push）、`60-execution-log.md`、`61-adversarial-d3v2.txt`、
`62-bookticker-preaccept-green.txt`、T2a 基线与迁移表（committed）、修订后的两仓文档。
完成后停下：Codex + Fable5 审 raw diff（输入=diff+61/62+基线 diff），用户终审后 push。

---
打包人: Fable 5（anthropic/claude-fable-5）
本地北京时间: 2026-07-17 23:20
下一步模型: kimi（执行本包）→ codex+fable5（raw-diff 评审）→ human（终审+push）

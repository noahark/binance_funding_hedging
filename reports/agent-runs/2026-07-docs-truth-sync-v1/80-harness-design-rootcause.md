# Harness 设计根因分析：为什么会系统性产生文档不同步

Stage: `2026-07-docs-truth-sync-v1`
作者角色: bookkeeper（Claude Opus 4.8，只读分析，不改 Harness 行为）
用途: 交付给用户路由 **Fable5 review**。本文档只诊断「Harness 流程 / 契约设计」层面
的成因与备选修法，不含具体文档文本的编辑（那些在 `00-task.md` backlog）。

## 方法

把本轮四模型审计（codex/grok/claude-glm/kimi）+ 本地复核发现的 17 项不同步，反向
归并到「是哪一条 Harness 设计选择在结构上导致了它」。判据：**若换一个人 / 换一个
模型按现有 Harness 规则照做，会不会重复制造同类漂移？** 会 → 是设计问题，不是执行
疏忽。下面 9 条按「产生漂移的量级」排序。

---

## RC1 — 「实现先行、事后 promote」被制度化，但 promote 义务无人跟踪、无门禁

**机制**：Harness 允许一个 stage 改 `schemas/` + `server.py` + 前端，同时把
人类可读契约 / PRD / ADR 的 promote 推迟到「review / 用户批准之后」（例：
`funding-annualized-history-v1` 的 ADR-3 明写此约定）。但推迟之后**没有任何机制
保证 promote 真的发生**：没有待办账本、没有验收门检查、没有强制 follow-up。于是
schema/代码成为事实真值，canonical 文档腐化。

**证据**：`snapshot.schema.json` 有 `annualized_*`（3 处），`public-market-contract.md`
0 处（P0-2）；`server.py` 暴露 `funding-history` / `symbol-snapshot`，合同无一等
契约；`docs/architecture/ADR/` 只剩模板，约 22 份阶段 `11-adr.md` 从未 promote
（P2-15）。这直接违反了 Harness 自己在 `DEVELOPMENT_GUIDE.md` 写下的规则
「Contract changes must update both human documentation and JSON schema」——
**规则存在，但无执行点**。

**这是漂移量最大的一条**：它把「文档滞后」从偶发变成了默认结局。

**备选修法（供 review）**：
- (a) **Promotion-debt ledger**：契约/schema 变更时，必须在 `status.json` 写一条
  `pending_promotions[]`（目标 canonical 文件 + 字段），`validate-stage.py` 在
  `pre-accept` 校验：要么已 promote、要么显式登记为「用户批准延后 + 落一条 follow-up」。
  无此项则 fail-closed。
- (b) 更弱版：把「contract-both-sides」规则从 `DEVELOPMENT_GUIDE.md` 的自然语言
  提升为 validator 断言（schema 改动的 stage 必须 touch 对应契约文件或显式豁免）。
- 取舍：(a) 覆盖 PRD/ADR/契约全面，但要求 status schema 扩字段；(b) 便宜但只覆盖
  API 契约。

---

## RC2 — 人类导航文档（INDEX/ROADMAP/PRD）是「should」义务，验收门只看机器态

**机制**：`AGENTS.md` 说 bookkeeper「should update STAGE_INDEX when a stage reaches
accepted/merged」——是 **should，不是 hard gate**。`validate-stage.py` 校验
fingerprint / verdict / branch 等**机器态**，但**从不检查** STAGE_INDEX / ROADMAP
是否收录了刚接受的 stage。于是 stage 可以合法地 accepted + merged + push，而人类
索引静默漂移。

**证据**：5 个已 merge 的 stage 未入 STAGE_INDEX，其中 `history-background-refresh`
（07-13）、`local-service-launchd`（07-14）**早于索引自己标注的 07-14 日期就漏了**
（P1-7）；`harness-flow-optimization` 行 Merged 列 = false 但实际已合并（P0-5）。

**备选修法**：
- (a) **STAGE_INDEX 改为从 `status.json` 生成**（`scripts/build-stage-index.py`），
  bookkeeper 不再手维护；人类索引与机器态就无法分叉。ROADMAP「Done」段同理可半生成。
- (b) 保留手维护，但 `pre-accept` 增加断言：被接受的 `stage_id` 必须出现在
  STAGE_INDEX，且该行的 merged 状态与 `stage_branch.merged_back_to_main` 一致。
- 取舍：(a) 根治且省人力，但要定义生成契约与保留「Note 人工列」；(b) 改动小，
  但仍靠人写行内容，只是不让它缺失/矛盾。

---

## RC3 — 验收迁移缺少「living-docs 定稿归一」步骤

**机制**：`status.json` / `70-handoff.md` / `20-implementation.md` 在 stage 过程中
不断追加「pending / review not started / 待补跑」等中间态文字。Checkpoint 规则要求
「更新这些文件」，但**没有一步在 accepted 迁移时把中间态机械清零/归一**。结果：一个
已 accepted 的 stage，handoff 里仍写「Formal review has not started」。

**证据**：bookticker `70-handoff.md` 顶部 Recovery Header 写 accepted，第 114 行却
写「Formal review has not started」、133 行 pending（P1-9）。这会直接误导下一次
恢复会话对「阶段是否结束」的判断。

**备选修法**：
- (a) 定义 **acceptance-normalization**：进入 `stage_accepted_waiting_user` /
  accepted 时，handoff 的 Recovery Header 是唯一权威态，validator 断言 body 中不得
  再出现与 accepted 冲突的 `not started / pending` token（或要求这些段落移入
  `history/`）。
- (b) 把易漂移的过程叙述从 handoff 分离到 `history/`，Recovery Header 只保留最终态。

---

## RC4 — fingerprint / verdict 模型无法表达「多任务 / 后加任务」覆盖，也无「授权 fast-route 豁免」——导致永久假红门

**机制**：`review-1` 的 fingerprint 是单条 `base..head`。当一个 stage 内 Task C 在
review-1 之后加入，review-1 的指纹**天然无法覆盖 Task C**，唯一覆盖是 review-2 的
全量指纹。但 `validate-stage.py` 的 `pre-accept` 只会比对
`review_1.diff_fingerprint == status.diff_fingerprint`，它**没有**「review-1 覆盖
A/B、review-2 覆盖 A/B/C」的分任务概念，也**没有**「用户已授权 fast-route」的豁免
记录位。于是一个已被用户授权合并、已 push 的 stage，`pre-accept` **永久红**。

**证据**：本轮复跑 `validate-stage.py 2026-07-bookticker-open-columns-v1
--phase pre-accept` → `FAILED: review_1.diff_fingerprint must match
status.diff_fingerprint`（P0-1）。这不是造假，而是设计把「合法的增量评审路径」和
「用户授权例外」都表达不出来，只能留一道红门或去手改历史指纹（后者更危险）。

**备选修法**：
- (a) **分任务 fingerprint**：`tasks[].review_1.diff_fingerprint` 已在 schema 里
  存在（模板可见），让 `pre-accept` 按任务校验覆盖并集，而非单条全量比对。
- (b) **授权豁免记录位**：verdict/status 增加
  `authorized_exception{ reason, approver, evidence }`，validator 承认该记录并放行，
  同时强制它落档、可审计。
- (c) 两者结合：正常走 (a)，(a) 不适用时走 (b)。
- 取舍：这是唯一一条同时涉及「证据完整性」而不仅是文档措辞的根因，改动触及
  fingerprint 契约核心，**最需要 Fable5 重点看**。

---

## RC5 — 退役/回退决策清了「现行规范」文件，但无「反向引用清扫」义务 → 悬空引用

**机制**：`DEC-2026-07-14-002` 退役 auto-review 时，删了 `docs/auto-review-pipeline.md`
+ `scripts/auto-review-runner.py`，并清理了 AGENTS/registry/adapters/validator/
workflow 五处——**规范层做得很彻底**。但 Harness **没有**「退役一个组件时，必须
grep 全仓反向引用并一并处理」的清扫步骤。于是二级引用悬空。

**证据**：`follow-ups/README.md` 仍写 auto-review「delivered / current normative:
`docs/auto-review-pipeline.md`」（死链，P0-3）；`DECISIONS.md` DEC-2026-07-14-001
的 Source 列仍引用两个已删文件（P0-4）；`harness-design.md` §Deferred Work 仍把
已实现的 PRD/手动交付/bootstrap 列为未做（P0-6，属同类「退役/完成后未回扫」）。

**备选修法**：
- (a) **Retirement checklist**：任何 `retire/rollback` 类决策，落档前必须附一次
  `grep -rl <retired-path>` 结果并逐条处理（改引用 / 加历史注释 / 删除），作为决策
  接受门。
- (b) 轻量：一个 `scripts/check-dangling-refs.py`，扫 docs/reports 中指向已删路径的
  引用，纳入 pre-accept 或 CI 式手检。

---

## RC6 — 「as-built 日期 / Deferred / Known gaps / Next」都是手写自由文本，只增不减，且日期本身就是唯一的陈旧信号

**机制**：每份 canonical 文档头部有一行手打的 `Status: … 2026-07-10`。它**既是**
判断陈旧的唯一信号，**又**自身不可靠（没人重算）。同理，`Deferred Work` /
`Known open gaps` / `Next Product Work` 是 append-mostly 列表，**没有一步在事情落地
时把它划掉**。

**证据**：4 份 canonical 文档头部停在 07-10（P1-10）；`harness-design.md` Deferred
仍列已完成项（P0-6）；`AGENTS.md` Known gaps 未纳入新出现的契约 gap（P1-12）；
`harness-design.md` §Current Scope「only document-level contract」与「multiple stages
completed」自相矛盾（P2-14）。

**备选修法**：
- (a) 把「as-built 日期」从手打改为**由最近 promote 该文档的 stage 派生**（脚本回填
  或 lint 比对 doc 与其最后关联 stage）。
- (b) 给 Deferred/Known-gaps 列表项加 stage 反链，stage accepted 时提示回扫对应项。

---

## RC7 — manifest 分类手工且不全 → 缺少「生成态 vs canonical」的机器判据，无法自动查漂移

**机制**：`harness-manifest.yaml` 的 `generated_or_runtime` 只列了 `.harness-version`
和 `reports/agent-runs/<stage>/`，**没把** `ACTIVE.json`、`STAGE_INDEX.md` 归类。
没有分类，工具就无法区分「本应随 stage 漂移、可重生成」与「canonical、漂移即 bug」，
于是也无法建自动陈旧检测器。

**证据**：P1-13。这条是 RC2 (a)「INDEX 生成化」的前置基础设施。

**备选修法**：补全分类，并让分类驱动一个 staleness linter（生成态文件校验其派生源，
canonical 文件校验其日期/引用）。

---

## RC8 — 多个重叠的「人类真值面」全靠手维护；Authority Order 只在冲突时理论可解，但人类先读的是未设门的低权威面

**机制**：机器真值 = `status.json` + `ACTIVE.json`（validator 守）。人类导航 =
STAGE_INDEX / ROADMAP / PRD / follow-ups/README / harness-design（**都无门**）。
`AGENTS.md` 的 Authority Order 规定了冲突时以谁为准，但**没有任何机制阻止低权威面
与高权威面矛盾**；而人类恰恰先读低权威面。设计把完整性预算全花在机器态，人类面
「可事后仲裁」但高频误导。

**证据**：cache-refresh 的**双向不符**——STAGE_INDEX 记了磁盘已不存在的 abandoned
`v1`、漏了实际存在的 accepted `v2`（P1-7）；ROADMAP「Current Focus」自称正在做
docs truth-sync，却没覆盖 07-13~15 的一串交付。

**备选修法**：收敛真值面数量——凡能从 `status.json` 生成的（STAGE_INDEX、ROADMAP
Done）就生成化（见 RC2 (a)），把手维护面压到 PRD/契约这类必须人写语义的少数，再对
这少数上 RC1 的 promotion 门。

---

## RC9 —（元）跨模型证据捕获是有损的：审计本身会静默丢证据

**机制**：本轮把审计分发给四个模型 CLI，但**没有统一的原始输出落盘契约**。各家
落盘格式不一：codex/claude 有完整 jsonl；grok 分 events/updates；**kimi 的最终结论
根本没落盘**（会话在生成定稿前中断，`state.json` 停在 06:12 而日志跑到 06:16，wire
里无 assistant 文本），只能靠用户手工回传。若无人回传，这条审计证据就永久丢失。

**证据**：本 stage `status.json.audit_sources.note` 已记录该情况。这与 AGENTS.md
「Model claims are not evidence；raw output path 是证据」的原则相悖——**当 raw output
根本没被可靠捕获时，原则落空**。

**备选修法**：为「多模型只读审计 / 评审」定义与 stage 一致的 raw 落盘路径与捕获
契约（每个受派模型必须把原始输出写到
`reports/agent-runs/<stage>/audit/<model>.md` 或等价路径），bookkeeper 校验存在性，
缺失即记 `unavailable + reason`，不依赖人工转述。

---

## 优先级建议（供 Fable5 排序）

| 根因 | 漂移量 | 涉及层 | 改动成本 | 建议优先 |
|---|---|---|---|---|
| RC1 promote 债无门 | 最高 | status schema + validator | 中 | P0 |
| RC2 人类索引无门 | 高 | validator 或生成脚本 | 中 | P0 |
| RC4 fingerprint 假红门 | 中（但涉证据完整性）| fingerprint 契约核心 | 高 | P0，须重点 review |
| RC5 退役无反向清扫 | 中 | 决策接受门 + 脚本 | 低 | P1 |
| RC3 living-docs 未归一 | 中 | validator 断言 | 低 | P1 |
| RC8 真值面过多 | 中 | 与 RC2 合并解 | 中 | P1 |
| RC6 手写日期/列表 | 低-中 | lint | 低 | P2 |
| RC7 manifest 分类 | 低（基础设施）| manifest + lint | 低 | P2（RC2 前置）|
| RC9 审计证据有损 | 低（元）| 审计落盘契约 | 低 | P2 |

**共性根因一句话**：Harness 把「完整性预算」几乎全部投在**机器态 + 代码/schema**
（validator 守得很严），却把**人类可读文档与跨阶段一致性**留在「should 级」手工义务
上——没有 promote 门、没有生成化、没有反向清扫、没有归一步骤。因此只要有人照章办事，
文档漂移就是**默认结局而非意外**。九条修法的共同方向是：**要么给人类面上门禁，要么
把人类面从 status.json 生成化，从而把手维护面压缩到「必须人写语义」的极少数并对其
单独上门。**

当前 Session ID: unavailable (Claude Code session id 未暴露)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-docs-truth-sync-v1/80-harness-design-rootcause.md
本地北京时间: 2026-07-16 14:33:56 CST
下一步模型: human → Fable5 (review)
下一步任务: 用户路由 Fable5 评审本报告；据评审决定 D-B 是否采纳及模板仓落地顺序

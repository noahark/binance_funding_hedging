# Fable5 评审：80-harness-design-rootcause.md

Stage: `2026-07-docs-truth-sync-v1`
评审角色: Fable 5（用户路由的独立外部评审，只读复核 + 本文件落盘）
评审对象: `reports/agent-runs/2026-07-docs-truth-sync-v1/80-harness-design-rootcause.md`
结论: **ACCEPT（方向与证据成立）**，采纳前需修正 2 处引用错误（见 F1/F2），并补一条报告未覆盖的横切风险（见 R1）。

## 一、证据独立复核结果

判据沿用本仓原则：不信转述，逐条对仓库现状重放。

| 根因 | 复核动作 | 结果 |
|---|---|---|
| RC1 | `grep annualized_` schema=3 处、契约=0 处；`docs/development/DEVELOPMENT_GUIDE.md:117` 规则原文存在；`docs/architecture/ADR/` 仅剩模板；`ls */11-adr.md` = 恰好 22 份 | ✅ 全部属实 |
| RC2 | `validate-stage.py` 全文无 STAGE_INDEX/ROADMAP 断言 | ✅ 实质属实，但引用出处错误（F1） |
| RC3 | bookticker `70-handoff.md`：header 第 9/18 行 `accepted`，第 114 行「Formal review has not started」、第 133 行 pending | ✅ 行号精确属实 |
| RC4 | 本机复跑 `validate-stage.py 2026-07-bookticker-open-columns-v1 --phase pre-accept` → FAILED（同报告）；红门断言在 `scripts/validate-stage.py:805-806`（review_1/2 指纹只与全量 status 指纹单条比对）；任务级指纹校验机制已存在于 `:776-787` | ✅ 复现，修法 (a) 有现成落点 |
| RC5 | `reports/follow-ups/README.md:32` 仍写「Normative contract (current): docs/auto-review-pipeline.md」，该文件与 `scripts/auto-review-runner.py` 均已删除；`DECISIONS.md` DEC-2026-07-14-001 Source 列引用两个已删文件 | ✅ 属实（路径笔误见 F2） |
| RC6 | PRD / DEVELOPMENT_GUIDE 头部停在 2026-07-10；`harness-design.md` §Deferred Work 仍列 PRD、manual first stage delivery、bootstrap commits 为未做（三者均已发生） | ✅ 属实（表述精度见 F4） |
| RC7 | `harness-manifest.yaml` `generated_or_runtime` 确实只有 `.harness-version` + `reports/agent-runs/<stage-id>/` 两项 | ✅ 属实 |
| RC8 | `comm` 对比磁盘目录与索引：磁盘有而索引无 = 5 个已交付 stage（bookticker / cache-refresh-v2 / history-background-refresh / history-refresh-ahead / local-service-launchd）；索引有而磁盘无 = 2 个（cache-refresh-scheduler-v1、promotion-gate-upsync-v1）；ROADMAP Done 段对 07-13~15 三个交付 0 命中 | ✅ 双向不符属实 |
| RC9 | 本 stage `status.json.audit_sources.note` 记录 kimi 定稿未落盘、靠操作者转述 | ✅ 属实 |

## 二、发现（按严重度）

- **F1（P2，引用错误，采纳前必须改）**：RC2 称「`AGENTS.md` 说 bookkeeper should update STAGE_INDEX」。实际 `AGENTS.md` 全文不含 STAGE_INDEX；该 should 句出自 `reports/agent-runs/STAGE_INDEX.md` 自身头部。这**反而强化** RC2——义务连治理文档都没进，只是索引文件的自我声明——但引用必须改正，本报告将作为 D-B 决策依据，不能自带漂移。
- **F2（P3，路径不精确）**：`schemas/snapshot.schema.json` 实为 `schemas/api/public-market/snapshot.schema.json`；`follow-ups/README.md` 实为 `reports/follow-ups/README.md`。一份诊断文档漂移的文档，自身引用应到位。
- **F3（支持性观察，利好 RC4 修法 (b)）**：validator 已有同型先例——review_2 designer-overlap override 要求存在 evidence 文件方可放行（`validate-stage.py:735-737`）。`authorized_exception` 可直接复用该 fail-closed + 证据文件模式，新颖度与风险低于报告自评的「高」。
- **F4（P3，表述精度）**：RC6 说「4 份 canonical 文档头部停在 07-10」；抽查 PRD、DEVELOPMENT_GUIDE 属实，但 `docs/harness-design.md` 根本没有 Status 日期行——比「停在 07-10」更糟，建议改写为「有日期的停在 07-10，且存在无日期头的 canonical 文档」。
- **F5（P3，表述精度）**：契约中 `symbol-snapshot` 有 2 处顺带提及（`public-market-contract.md:782,789`，opening_quotes 段），`funding-history` 确为 0 处。「合同无一等契约」结论成立，建议精确为「无独立端点契约小节」。

## 三、报告未覆盖的横切风险

- **R1（必须写进 D-B 采纳条件）**：RC4 的教训是「门无法表达合法例外 → 永久假红」。而 RC1(a)/RC2(b)/RC3(a) 的修法**全都是在加新门**。若这些新断言不从第一天就带显式豁免记录位（复用 RC4(b) 的 `authorized_exception` + 证据文件机制），就是在批量复制 RC4 类缺陷。建议：豁免机制先行或同批落地，任何新增 pre-accept 断言必须声明其合法例外的表达方式。

## 四、对 D-B 的建议

**采纳，分两批，模板仓 first。**

- **批次 1（P0，同一 stage）**：RC4 (a)+(b)（(b) 按 F3 复用现有 override-evidence 模式，fail-closed）；RC1 (a) promotion-debt ledger；RC2 选 **(a) 生成化**——双向不符（RC8 证据）说明断言型修法清不掉既有漂移，生成化才根治；RC7 作为 RC2(a) 前置并入本批。
- **批次 2（P1）**：RC5 (b) `check-dangling-refs.py`（比 (a) checklist 更可执行）；RC3 (a) token 断言（注意 R1：给「用户批准保留中间态」留豁免位）。
- **RC6/RC9 维持 P2**，同意报告排序。
- **落地顺序**：模板仓改 validator/schema → 手动 cp 下行本仓（现行上行/下行同步即手动 cp，无自动机制）→ 本仓下一个 stage 实测新门。注意 AGENTS.md 的两仓 carve-out 行不得被同步覆盖。
- **顺带解 D-A**：批次 1 的 RC4 修法落地后，bookticker 红门可走 (a) 分任务覆盖或 (b) 落档豁免合法转绿，无需手改历史指纹，也无需长期接受红门。

---

## Addendum（追加，evolve-by-note）：对 opus4.8 四问的裁决

前提核实：opus4.8 补充的三条代码级证据全部属实（YAML 810 行 / validator 871 行 4-phase / promote-approved-docs 节点在 YAML ~317 行 / validator 对 docs 唯一引用是 `parallel-development-mode.md` 存在性检查 `:380-382`）。另发现一个强化性细节：**promote-approved-docs 节点位于 direction-synthesis 流程的 stage design 之前**（`run_when: "before stage design"`），即 YAML 从未有过「验收后 promote」节点——漂移实际产生的迁移点连 should 级义务都不存在，自然实验的结论比 opus 表述的更强。

**Q1 同步义务落 validator 层还是 YAML 节点层？——落 validator，认同并否决「每个节点强制同步」。**
理由：① 自然实验已证 YAML/文档级义务不改变约束力（且如上，验收后迁移点连节点都没有）；② 回退后 YAML 是 bookkeeper 照读的清单，约束力 = 散文 should；③ 「每个节点」粒度错——漂移只产生于 accepted/promote 与 retire/rollback 两个迁移点，全节点强制造成清单疲劳，疲劳侵蚀的是**所有**门。附加条件（本评审 R1）：每条新 validator 断言必须自带豁免记录位（`authorized_exception` + 证据文件，复用 `:735-737` 现有 override 模式），否则批量复制 RC4 类永久假红。

**Q2 RC1 选 (a) pending_promotions[] 全覆盖，(b) 作为 (a) 内部的触发断言。**
决定性事实：已观测漂移的大头**不是** API 契约文件——22 份未 promote 的 ADR、PRD、ROADMAP、harness-design Deferred 全在 (b) 覆盖之外，(b) 单独只能拦住 P0-2 一类。且「延后 promote」在本仓是合法制度（funding-annualized-history-v1 ADR-3 先例），门必须能表达「延后 + 登记」，这正是 (a)；(b) 单独存在会与合法延后打架。实现上 (b) 的检查（diff 触及 schema/契约 → 要求已 promote 或已登记）就是 (a) 断言的触发条件，(a) 天然含 (b)。

**Q3 RC2 选生成化（STAGE_INDEX 从 status.json 生成），且生成化自身要配一道薄断言。**
理由：① pre-accept 断言只在 stage 过验收时触发，清不掉存量双向不符（5 漏 + 2 悬空），也不会回填历史；生成化一次性根治两个方向。② 断言版保留两个真值面和手写义务；生成化直接消灭义务，与报告共性根因的解法方向（压缩手维护面）一致。③ 代价要管理：RC7 manifest 分类是前置；生成契约须保留人工 Note 列（sidecar 映射 stage_id→note，重生成时保留）；文件头标注 generated + 入 manifest `generated_or_runtime`。④ 关键：生成脚本本身不设门只是把漂移换成「忘了跑脚本」——pre-accept 加一条机械断言「重跑生成器后 diff 为空」，这比任何语义断言都便宜可靠。ROADMAP Done 段可半生成，Current Focus 保持人写。

**Q4 RC4 本轮做，且作为独立 stage 放在文档门之前（依赖倒置）。**
理由：① `authorized_exception` 豁免机制是所有新文档门都需要的共享基础设施（R1），在 RC4 stage 先建一次，文档门 stage 复用——推迟 RC4 等于让文档门无豁免位裸奔。② 存在现行失败：bookticker accepted+merged 却永久红，D-A 被卡；长期接受红门会训练操作者无视全流程唯一 fail-closed 的门，这是对门权威性的侵蚀，比改 fingerprint 契约的风险更大。③ 但必须独立 stage：它是唯一触及证据完整性主干的改动，小 diff、聚焦评审。落地序：Stage A（模板仓）= 分任务指纹覆盖 + authorized_exception 机制 → Stage B = 文档门（RC1a、RC2 生成化+RC7、RC3）复用豁免位 → 一次性回填/重生成 STAGE_INDEX。两仓同步走手动 cp，注意 AGENTS.md carve-out 行。

当前 Session ID: unavailable（Claude Code 未暴露 session id）
原始输出路径: reports/agent-runs/2026-07-docs-truth-sync-v1/81-harness-design-rootcause-review-fable5.md
本地北京时间: 2026-07-16（由系统日期，未取时分）
下一步: 用户裁决 D-B（建议采纳，附 F1/F2 修正 + R1 条件）；若采纳，模板仓 first 排期批次 1

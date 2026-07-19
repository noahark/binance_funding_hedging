# Plan Review (Fable5) — 2026-07-harness-review-dispatch-fast-fix-v1

- 审查角色：independent read-only Harness plan reviewer（非正式 code Review-1）
- 审查模型：Fable5 (anthropic/claude-fable-5)，只读，未修改任何 Harness 文件
- 落盘说明：`09-plan-review.md` 在本审查完成时已存在一份 Grok 署名的完整
  评审（2026-07-19 22:24:43 CST）。为不覆盖他模型证据，本审查另存本文件；
  两份评审相互独立，未互相参考结论（本审查证据收集先于发现该文件）。
- 审查对象：`05-root-cause-and-fix-plan.md` 及 `00-intake.md`、`00-task.md`、
  `10-design.md`、`11-adr.md`、`12-development-breakdown.md`
- 现行源证据：`AGENTS.md`、`docs/parallel-development-mode.md`、
  `workflows/templates/stage-delivery.yaml`、`docs/model-adapters.md`、
  `scripts/validate-stage.py`（1404 行全文）、`schemas/review-verdict.schema.json`
- 利益披露：本会话此前在其他 stage 承担过评审/簿记角色，与本 stage 的
  设计（Codex 署名）、未来实现（用户另选模型）均无作者重叠。

## 结论

**REWORK（轻量）**：三项核心决策（单一人工 dispatch 权威、单轮 committed
交叉 Review-1 默认、raw + strict verdict 双工件分离）方向正确、与六项故障
一一对应、范围接近最小，**确认可进入实施**；但计划文本存在 2 个 P1 级
validator 旁路缺口和数个 P2 级一致性/测试矩阵缺口，须先把下列 required
changes 并入 `05-root-cause-and-fix-plan.md` 与 `00-task.md`（含测试矩阵），
再派发实施。修订仅限计划文本，不需要重新设计，不需要再走一轮完整 plan
review（bookkeeper 核对修订吸收即可）。

## 六故障 ↔ 三决策映射核对

| 故障（00-intake.md:17-28） | 对应决策 | 判定 |
|---|---|---|
| 1 实现终端宣称已启动对侧预审、不可验证 | D1 人工 dispatch + 回执 | 成立 |
| 2 Claude-GLM 评审终端自启子进程 | D1 禁止一切模型子派发 | 成立（见 F6：现行禁令是 provider 限定的，GLM/Kimi 终端本就不在字面禁令内，D1 把禁令扩到全部模型是正确修法） |
| 3 嵌入预审 + 正式 Review-1 同配对重复 | D2 单轮默认 | 成立 |
| 4 Review-1 完成但 `30-review-1-*.md` 未落盘 | D3 + validator 存在性检查 | 成立，但相位时机需钉死（F3） |
| 5 Review-2 完成但 `50-review-2.md` 未落盘 | 同上 | 同上 |
| 6 verdict JSON 带 Markdown 围栏/尾随字节 | D3 严格解析 + schema | 成立，但 raw↔verdict 绑定缺失（F1）、footer 契约冲突需一并改（F5） |

## 有序 Findings

### F1 (P1) strict verdict 与 raw output 之间没有任何机械绑定

- 证据：`05-root-cause-and-fix-plan.md:135-139` 对 Review-1/2 的 validator
  要求仅为 "raw output 和 verdict 路径存在且非空 + 解析 verdict 文件"；
  capture 回执（`05:99-100`，含双文件 SHA-256）只要求 "print"，未要求落盘，
  validator 也不消费它。
- 后果：任何有写权限的会话可以直接手写一份 schema 合规的
  `*.verdict.json`（配一个任意非空 `*.raw-output.md`）通过门禁——这恰是
  本 stage 要关死的"模型声称=证据"旁路，双工件设计退化为装饰。
- Required change：由于新契约规定 raw 必须是"单个 JSON 对象 + 仅终端传输
  空白"（`05:93-95`），validator 可以零成本重建绑定——在检查 verdict 的同一
  处，对 raw 文件做同样的 strip-whitespace + 单对象解析，并要求解析结果与
  `*.verdict.json` 的 JSON 对象**逐字段相等**，不等则 fail closed。同时把
  "raw/verdict 内容不一致 → 拒绝"加入负向测试矩阵。（说明：这不能证明字节
  来自哪个模型——计划已承认身份靠 operator 回执，`05:50-51`——但它使伪造
  必须成对且一致，且让 raw 工件真正参与门禁。）

### F2 (P1) 协议版本字段缺失时静默回落 legacy，构成新 stage 的静默退出通道

- 证据：`05-root-cause-and-fix-plan.md:117`（"Historical stages without the
  field retain legacy validation behavior"）；`00-task.md:59-60`（criterion 7
  仅说 opt-in/versioned）。一个**新** stage 只要不写
  `review_artifact_protocol`，就自动获得旧行为，六项故障全部原样复活，
  且 validator 不报任何错。
- Required change：利用 dispatch-ready / pre-review 是"只向前"的相位这一事实
  （历史已完结 stage 不会再跑这两个相位；`validate-all-stages` 对历史 stage
  跑的是 pre-accept/checkpoint 路径）：在计划中明确——自本变更合入后，
  `--phase dispatch-ready` 与 status 为活跃态（非 accepted/terminal）的
  `--phase pre-review` **要求该字段必须存在**，缺失即 FAIL；仅对已带
  review_1/review_2 证据或已处终态的历史 stage 走 legacy 分支。模板
  （`reports/agent-runs/_template/**`，已在 allowed files）同步写入该字段。
  测试矩阵补一条负向："新 stage 缺 `review_artifact_protocol` →
  dispatch-ready 拒绝"。

### F3 (P2) review 工件存在性检查的相位时机未钉死，故障 4/5 可能拖到 pre-accept 才被抓

- 证据：现行 `scripts/validate-stage.py:743-752` 只在 pre-accept 要求
  `30-review-1.md`/`50-review-2.md`；`validate_common`（:696-699）对
  pre-review 接受 status ∈ {review_1, review_2} 但不区分两者。计划的
  validator 节（`05:134-144`）说 "Require raw output and strict verdict paths
  to exist"，但没有写清**在哪个相位、针对哪个 status** 检查。
- 后果：Review-1 不落盘（故障 4 原样）仍可推进到 review_2 dispatch，直到
  pre-accept 才失败——违反计划自己的承诺"before a stage can advance"
  （`00-task.md:6-8`）。
- Required change：计划明确写入——`--phase pre-review` 且
  `status == review_2` 时，必须存在全部 task 级 Review-1 的
  `*.raw-output.md` + `*.verdict.json`（且过 F1 的一致性检查）；pre-accept
  再加 Review-2 双工件。`validate_required_files` 的硬编码文件名清单按协议
  版本分支。

### F4 (P2) validator 变更清单遗漏 `validate_parallel_mode` 的 pre-review/pre-accept 分支；正向测试矩阵缺关键一条

- 证据：现行 `scripts/validate-stage.py:436-439` 要求 parallel stage 必须
  `r10_dispatch_tail_required=true` / `r4_diff_reconciliation_required=true`，
  `:445-446` 要求 pre-review/pre-accept 至少一条 `embedded_reviews` 记录，
  `:454-455` 要求 rounds ≥ 1。计划的 "Validator Changes"（`05:121-144`）只
  写了 dispatch-ready 不再默认要求嵌入预审，未提这三处——若不改，**新默认
  流程（无嵌入预审）的 parallel stage 会在 pre-review 直接 FAIL**，属阻断性
  遗漏（好在方向是 fail closed，不是旁路）。
- 证据（测试矩阵）：`05:146-166` 的 Positive 列表没有"默认 parallel stage
  （无 embedded review）通过 dispatch-ready + pre-review + pre-accept"这条
  ——这是本次变更的**主路径**，必须有正向 fixture；同样缺
  "`embedded_review.enabled == true` opt-in 扩展工件齐备时通过"的正向条目。
- Required change：validator 变更清单补入 `validate_parallel_mode` 三处
  按协议版本/opt-in 条件化；测试矩阵补上述两条正向 fixture。

### F5 (P2) JSON-only 输出契约与现行 footer 契约冲突，且复用 `reviewer_prior_involvement_notes` 属语义挪用

- 证据：计划要求响应"仅一个 JSON 对象 + 终端空白"（`05:93-95`），footer 进
  `reviewer_prior_involvement_notes`（`05:104-106`）。但现行
  `workflows/templates/stage-delivery.yaml:605-608` 与 `:736-739` 规定
  `navigation_footer.position: before_final_json_object`（JSON 前必须有
  footer 文本 → 在新契约下必然解析失败）；`AGENTS.md:487-489` 允许
  "inside schema-approved fields"，方向兼容，但
  `schemas/review-verdict.schema.json:67-70` 把该字段定义为 prior-involvement
  披露专用，塞导航 footer 会污染披露语义。
- Required change：实施必须同步改 `stage-delivery.yaml` 两处
  `output_contract.navigation_footer`（改为 inside_verdict_fields 之类）与
  `AGENTS.md` Output Footer 节；schema 侧二选一并写进计划：
  (a) 新增一个可选的专用字段（如 `navigation_footer`，string）——符合
  `00-task.md:30-31` "clarification necessary" 的许可，不改 verdict 语义；
  (b) footer 职责移到 operator 侧 dispatch RECEIPT / capture 回执，模型输出
  彻底免除 footer。二者取其一，禁止默认挪用 notes 字段。

### F6 (P3) 矛盾定位不完整："AGENTS.md wins" 的说法不准确，且实施必须清扫的现行条文清单被低估

- 证据：矛盾不只是 AGENTS.md vs parallel-mode——**AGENTS.md 自身两端都写了**：
  `AGENTS.md:137-142`/`:337-342`（Codex/GPT 与 Claude 会话禁执行 dispatch，
  人工执行）vs `AGENTS.md:350-356`（Hard Gate 强制 "next_dispatch entries
  marked executor: self must be executed … before the implementer reports
  completion"）。因此 `05:33-35` "Under the repository authority order,
  AGENTS.md wins" 推不出唯一结论。另外现行禁令是 **provider 限定**的
  （`docs/parallel-development-mode.md:276-279` 只约束 Codex/GPT 与 Claude
  provider 会话），claude_glm=zhipu_glm、kimi=moonshot 的终端本就不在字面
  禁令内——故障 2 更准确的定性是"规则缺口"而非纯违规；D1 把禁令扩展到
  全部模型终端正是正确修法，计划应如此表述。
- 实施清扫清单至少还含：`AGENTS.md:309-313`（dispatch-ready 门描述含
  embedded pre-review prompt paths）、`:417-419`（标准流程 step 12 强制
  嵌入预审）、`stage-delivery.yaml:435-436`（R10 self-executing packet 验收
  项）、`:478`（executor:self 执行 routing rule）、`:485-527`
  （embedded-cross-review-checkpoint 节点整体改为 opt-in 条件）。
- Required change：修正 `05` 的 Evidence 节表述并补齐上述行号清单，避免
  实施模型漏改造成"一份文档内新旧规则并存"的二次矛盾。

### F7 (P3) 管道式 capture 观测不到 adapter 进程退出码

- 证据：`05:83-89` 的 `<adapter> | capture-review-output` 形态下，左侧命令
  非零退出不会传导给 helper（空输出可兜住最常见情形，但"部分输出后崩溃"
  会被当作解析失败而非 adapter 故障，failure class 归类会失真）。
- Required change：在 `docs/model-adapters.md` 的 capture 用法中写明操作者
  须 `set -o pipefail`（或等价机制）并把 adapter 退出码记入回执；**不得**
  为此让 helper 获得执行命令的能力（那会走向被否决的 runner 形态）。

## 对 08-prompt 六个关注点的直接回答

1. **人工 dispatch 与 executor:self 的矛盾**：矛盾真实，但根在 AGENTS.md
   自身两处 Hard Gates 互斥 + 禁令 provider 限定不覆盖 GLM/Kimi（F6）。
   D1 的统一规则正确，须按 F6 清单全量清扫。
2. **移除强制嵌入预审是否保住最强门**：是。嵌入预审依 R5
   （`docs/parallel-development-mode.md:157-162`）本就是 checkpoint 而非
   门；最强门=committed 指纹上的正式 Review-1 + Review-2，均保留且
   validator 收紧。附带收益：同一评审 provider 不再先看未提交态、后走
   过场确认，正式轮成为其首次接触，独立性反而提高。前提是 F4 修掉，
   否则新默认流程会被现行 validator 阻断。
3. **capture helper 是否复刻自主 runner**：否。不选模型、不发起第二次
   dispatch、不推进状态、失败不覆盖旧 verdict，与已退役
   auto-review-pipeline（选模型+自动轮转）有清晰边界。保持"仅消费
   stdin、仅写两个文件"的形态即可；F7 的退出码问题用 pipefail 解决，
   不要给 helper 加执行能力。
4. **raw vs verdict 溯源与原子性**：原子性设计（临时文件+rename、失败不
   替换旧 verdict）充分；溯源有 F1 缺口——raw↔verdict 无机械绑定，必须
   补一致性重建检查。绝对来源证明（哪只模型产生的字节）超出机械手段，
   计划已如实归于 operator 回执，可接受。
5. **legacy 兼容**：按字段分支 + 不迁移历史证据 + validate-all-stages 对比
   的思路正确；但 F2 的"新 stage 漏写字段=静默 legacy"必须堵上，否则
   版本化机制本身成为旁路。
6. **validator 旁路 / 缺测试 / 可减范围**：旁路=F1、F2、F3；缺测试=F4 两条
   正向 + F1/F2 各一条负向。范围**不建议再减**：allowed files 每项都被上述
   findings 消费；唯一可减项是 schema（若 F5 选 (b) 回执侧 footer 则 schema
   可不动）。反向地，AGENTS.md 的改动面要按 F6 **扩**到列出的行号。

## 对 05 计划内五个 Reviewer Questions 的回答

1. 保住最强门：**是**（见上第 2 点）。
2. helper 足够窄：**是**，附 F7 约束。
3. raw+verdict 可审计且向后兼容：**修 F1、F2 后是**。
4. 旁路/状态迁移缺口：**有**——F1（手写 verdict）、F2（漏字段回落
   legacy）、F3（review_2 相位不查 Review-1 工件）；F4 是阻断性遗漏
   （方向 fail closed，非旁路）。
5. 范围可否再减：**基本不可**；唯一候选是 F5 选 (b) 时免改 schema。

## Required Changes 汇总（并入 05 + 00-task 后即可派发实施）

1. F1：validator 增加 raw↔verdict JSON 对象一致性重建检查；负向测试
   矩阵加"raw/verdict 不一致"。
2. F2：dispatch-ready 及活跃态 pre-review 强制要求
   `review_artifact_protocol` 存在；模板写入该字段；负向测试加"新 stage
   缺字段被拒"。
3. F3：钉死相位——pre-review@status=review_2 必须已有全部 task Review-1
   双工件；`validate_required_files` 按协议分支。
4. F4：validator 变更清单补 `validate_parallel_mode`
   （`validate-stage.py:436-439,445-446,454-455`）条件化；正向测试加
   "默认无嵌入预审的 parallel stage 全相位通过"与"opt-in 嵌入预审工件
   齐备通过"。
5. F5：写死 footer 方案（新增专用可选 schema 字段，或移到 operator 回执），
   并同步修改 `stage-delivery.yaml:605-608,736-739` 与 `AGENTS.md` footer 节。
6. F6：修正 05 Evidence 节（AGENTS.md 内部矛盾 + provider 限定缺口），补全
   实施清扫行号清单（AGENTS.md:309-313,350-356,417-419；yaml:435-436,478,
   485-527；parallel-mode:276-279 等）。
7. F7：model-adapters.md capture 用法注明 pipefail 与 adapter 退出码记录。

## 残余风险（实施与验收时关注）

- **人工中转吞吐回退**：v0.3 的试运行 finding #1
  （`docs/parallel-development-mode.md:360-369`）正是因人工补跑预审停等而
  引入 executor:self；D1 回到人工 dispatch 后该瓶颈回归，只是被 D2（少一轮）
  与 capture helper（少一类抄录错误）部分抵消。属已知取舍（11-adr.md
  Tradeoffs 已认），建议在试运行期观察 operator 停等时长。
- **字节来源不可机械证明**：helper 与 validator 都无法证明 stdin 来自
  宣称的模型；最终担保仍是 operator 回执 + 人工验收，与 RC4 的
  "validator 无法机械执行的人工义务"同类，需在文档中保持显式。
- **嵌入预审 opt-in 可能名存实亡**：默认关闭后可能永不再用；若两个阶段后
  无人 opt-in，建议直接删除该扩展路径而非长期维护双分支。

---

当前 Session ID: 882462e9-e856-461c-95fc-b876af7954f5
Session ID 来源: transcript_path（session 专属 scratchpad 路径含同一 UUID）
原始输出路径: reports/agent-runs/2026-07-harness-review-dispatch-fast-fix-v1/09-plan-review-fable5.md
本地北京时间: 2026-07-19 22:28:12 CST
下一步模型: human user（裁决双评审取舍）+ codex bookkeeper（吸收 required changes 入 05/00-task）
下一步任务: 用户确认以哪份/两份 plan review 为准，bookkeeper 按 required changes 修订计划后，由用户选定不同实施模型派发 H1

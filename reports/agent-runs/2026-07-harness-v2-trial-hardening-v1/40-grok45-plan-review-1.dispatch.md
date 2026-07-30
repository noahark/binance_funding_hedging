# Harness v2 Trial Hardening — Plan Review 1 (Grok 4.5)

## Identity

- task_id: `harness-v2-trial-hardening-plan-review-1-grok45`
- target_role: `Reviewer`
- target_model: `grok-4.5`
- provider: `xai`
- status_revision: `6`
- required_skill: `agents/skills/code-reviewer.md`

## Goal

独立核验 Harness v2 试运行加固的**设计**（`20-opus5-design.md`），以及本次 D-9 收口的
三处文档改动。这是计划评审（review-1），不是实现评审：受审对象是决策与边界，不是产品
代码。

设计作者是 Opus 5（provider `anthropic`）。你的 provider 是 `xai`，跨 provider 独立性
成立，且你未参与本设计撰写或本阶段记账。Human 已明确：后续 review-2 将由 Fable5
（provider `anthropic`，与设计作者同 provider）执行，**它不替代你这一轮跨 provider 独立
初审**——因此本轮是唯一的跨 provider 独立把关，请据此把握严格程度。

核验重点是"设计是否仍然成立、是否与 Human 已作出的十条决定一致、是否留下了会被绕过或
会制造重复权威的口子"。允许你否定设计中的任何结论，但必须给出证据。

## Allowed Files

无。本次为只读评审会话。

按 `AGENTS.md` §7"Reviewers are read-only"与 `agents/roles.md` Reviewer 段，你**不得
创建或修改任何文件**，不得 `git add`/`commit`/`merge`/`rebase`/`push`，不得移动 `HEAD`
或改动工作树，不得启动、调用或指派其他模型，不得访问凭据、操作服务或执行任何实盘动作。

证据落盘由 Bookkeeper 负责。本包**预先指定**你的原始输出归档路径为
`reports/agent-runs/2026-07-harness-v2-trial-hardening-v1/41-grok45-plan-review-1-raw.md`；
若结论为 `REWORK`，`问题记录` 与 `修复要求` 均填写该路径，并把完整发现与可执行修复要求
写在返回结果正文中，由 Human 转交 Bookkeeper 落盘。你自己不要创建该文件。

## Inputs

固定评审范围（`AGENTS.md` §3.6，只用已提交 SHA，不移动 `HEAD`）：

- `base_sha`: `0bea9c084b8209b19113b169eaf152ab33455884`
- `delivery_sha`: `f90609dd0682f6007867127925829cd86f8bd062`
- 区间差异: `git diff 0bea9c0..f90609d`（仅三个文件，见"须知"）

按 `AGENTS.md` §4 顺序读取：

1. `AGENTS.md`；
2. 本 dispatch；
3. `reports/agent-runs/ACTIVE.json`；
4. `PROJECT_STATE.md`（`f90609d` 版）；
5. 本阶段 `reports/agent-runs/2026-07-harness-v2-trial-hardening-v1/status.json`；
6. `agents/roles.md` 的 `Reviewer` 段（并按需查 `Bookkeeper` 段的
   `Minimal State And Dispatch Shape`、`Task State Vocabulary`、`SHA Discipline`）；
7. `agents/skills/code-reviewer.md`；
8. **受审设计全文**：`git show f90609d:reports/agent-runs/2026-07-harness-v2-trial-hardening-v1/20-opus5-design.md`
   （40,968 字节，内容 blob `3f26dd5`）；
9. `reports/agent-runs/2026-07-harness-v2-trial-hardening-v1/22-bookkeeper-design-verification.md`
   的 §8（十条 Human 决定原文）、§8.2（逐条处置）、§9（main 整合与对账）、§10（D-9 收口）；
10. `docs/planning/harness-v2-trial-findings-2026-07-30.md`（`f90609d` 版，含 D-9 原文与
    其后追加的 Human update）；
11. 仅在需要证实或否证某条结论时，读取该结论自身点名的源文件行区间或 Git 对象。

**须知（不要按常规交付评审来读这个区间）**：受审设计 `20-opus5-design.md` 由更早的提交
`128e564` 引入，它是 `0bea9c0` 的祖先，因此**不在** `base_sha..delivery_sha` 区间内。
该固定区间承载的只是本次 D-9 收口的三处文档改动（`PROJECT_STATE.md`、findings 文档、
`22-bookkeeper-design-verification.md`）。设计文档请按上面第 8 项以 `f90609d` 的树读取，
读取因此仍然确定且可复现。

不要扫描已完成阶段、无关产品源码、运行时数据、仓库外文件、凭据或移动中的历史。
`reports/agent-runs/_proposals/` 是草稿，按 Human 决定第 9 条不得作为正式证据。

## Acceptance Checks

你的评审必须覆盖以下各项，并对每项给出结论与证据：

1. **与十条 Human 决定的一致性**（`22` §8）。逐条核验设计现状是否与之相符，尤其五条
   否决/限制项：不新增回执格式检查器与配套测试；不新增每阶段 `decisions.md`；
   `status.json` 保持三态、不增加 `rejected`；不设 32KB 等硬阅读阈值；历史 stage 目录
   清理暂缓。设计原文中被这些决定推翻的段落是否仍留有依赖它们的推论？
2. **失去检查器之后的残留缺口**。决定 1 否决了设计 §4 的唯一新增可执行文件，批次 A
   因此不再新增任何文件。核验：`G1`/`G14`（结果与评审闭包无机制可查）在纯措辞路线下
   是否仍有可执行的把关点，或者是否已退化为"规则存在而无任何机制"——这正是设计自己
   判定为"三者中最差"的状态。若你认为残留缺口不可接受，请直接指出并给出可执行替代。
3. **`G5` 的落点**。决定 2 否决了每阶段 `decisions.md`，设计又已否决向 `status.json`
   增加 `decisions` 指针字段。核验当前"临时决定写入 Bookkeeper 核验记录、长期决定进既有
   规划决策文档"的安排是否稳定，是否会在下一阶段再次即兴造名。
4. **轮次语义的抗绕过性**（决定 4、设计 §3 问题 2）。核验"交付后的正式修复一律计入
   `rework_count`、改名或拆分不清零"是否在没有第四状态的前提下仍然可执行、可核验；
   Bookkeeper 拒收如何被记录而不被埋没。
5. **范围外发现的三分类与证据门槛**（决定 5、设计 §3 问题 5）。核验：证据门槛（触发
   条件、实际影响、证据位置、早于本次交付的 Git 证据）是否足以防止把范围内缺陷贴成
   既存；资金/实盘/安全类范围外问题"不自动否定交付但须合并前 Human 决定"的路径是否
   闭合；Human 授权"已知风险暂不修仍允许合并"时要求的五项记录是否完备；该授权仅限
   本次合并、且实盘风险仍须写入 `PROJECT_STATE.md` 是否被明确。
6. **单一权威与最小化**（`AGENTS.md` §2）。核验设计新增的每一条规则是否只有一处详细
   权威，是否出现字段清单、枚举、数值限额或完整工作流的复制；是否出现被 v2 删除的
   workflow YAML、registry、verdict schema、adapter runbook、monolithic validator 的
   任何形式回归。
7. **W1–W6 是否被削弱**（设计 §8）。特别核验 `status.json` 顶层字段集是否保持 13 个
   未变、dispatch 是否仍为六节、启动读取项是否未增加。
8. **本次固定区间的三处改动**（`git diff 0bea9c0..f90609d`）。核验：`PROJECT_STATE.md`
   是否已不含会让本轮评审终端启动即停机的全面禁令，同时保留"实施须待 `ACCEPT` 与
   Human 再授权"的边界；findings 文档中 D-9 原文是否**逐字未改**、新增内容是否为纯
   追加；十条决定是否未被复制进 `docs/planning/DECISIONS.md`。
9. **抽查设计自身的证据**。至少抽三条 `G` 结论，重跑其在设计 §0 或 findings 文档中给出
   的验证命令，确认结论成立或指出其不成立。
10. **批次边界可评审性**。核验批次 A / 批次 B 的 allowed files、非目标、验收检查、顺序
    约束在决定 1 生效后是否仍然自洽、可独立评审、且不互相覆盖同一节文字。

结论只允许 `ACCEPT` 或 `REWORK`。`REWORK` 必须给出具体、可执行的修复要求；仅指出"不够
好"不构成可执行要求。发现若属于范围外或既存问题，请按第 5 项的分类与证据门槛标注。

## Stop

按 `AGENTS.md` §7 返回完整中文 `[TASK_RESULT v2]`，并附评审闭包三行
（`评审结论` / `问题记录` / `修复要求`），以 `[/TASK_RESULT]` 作为最后一个非空白输出，
其后不得有任何文字。

下一步行动者是 Human：由 Human 把你的原始结果转交本阶段 Bookkeeper `opus5` 同步。
你不得准备 review-2 包、不得准备实现包、不得启动或指派任何模型。实施闸门保持关闭，
须本轮 `ACCEPT` 且 Human 再次授权后方可开启。

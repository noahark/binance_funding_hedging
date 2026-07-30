# Harness v2 Trial Hardening — Plan Review 1, Round 2 (Grok 4.5)

## Identity

- task_id: `harness-v2-trial-hardening-plan-review-1-grok45-r2`
- target_role: `Reviewer`
- target_model: `grok-4.5`
- provider: `xai`
- status_revision: `7`
- required_skill: `agents/skills/code-reviewer.md`

## Goal

你在第一轮返回了 `REWORK`，核心指控是"Human 已作出十条决定，而设计原件没有跟着更正，
被否决的机制在文中仍是首选路径，批次 A/B 与决定自相矛盾"。该指控已被 Bookkeeper 核验
为成立并执行返工。

本轮只做一件事：**核验返工是否真正解决了你上一轮的四项 FAIL/弱项，以及是否引入了新的
矛盾**。不要重开你上一轮已判定通过的部分（`G18` 与决定 5、单一权威意图、W1–W6 意图、
D-9 三文档、`G` 证据抽查），除非返工动了它们。

返工形态是**在设计末尾追加"勘误 1 — 2026-07-30"**，原文 §0–§10 逐字保留未改（
`git show 567d61b --numstat` 对该文件为 `135 0`，即 135 行新增、0 行删除）。这是 Human
决定第 8 条与设计自定规则要求的形态：封存原文不得改写，勘误只可追加。

特别提醒：你上一轮要求"`G1`/`G14` 标残留、禁止伪关闭"。这是本轮最需要严查的一条——
请确认勘误没有用措辞把一个仍然敞开的洞说成已经处理。

## Allowed Files

无。本次为只读评审会话。

不得创建或修改任何文件，不得 `git add`/`commit`/`merge`/`rebase`/`push`，不得移动
`HEAD` 或改动工作树，不得启动、调用或指派其他模型，不得访问凭据、操作服务或执行任何
实盘动作。

本包**预先指定**你的原始输出归档路径为
`reports/agent-runs/2026-07-harness-v2-trial-hardening-v1/43-grok45-plan-review-1-r2-raw.md`；
若结论为 `REWORK`，`问题记录` 与 `修复要求` 均填写该路径，并把完整发现与可执行修复
要求写在返回结果正文中，由 Human 转交 Bookkeeper 落盘。你自己不要创建该文件。

**回执格式请求（非强制，但有理由）**：上一轮你的原始输出在传输中换行被压平，各标签连成
一行。这是本设计 `G1` 所描述场景的真实复现，且当前 v2 无任何机制校验回执格式（见勘误
`E2`）。请把每个标签单独成行输出，降低转交过程中的歧义。若你上一轮的 `阻塞项` 中"F1"
另有独立正文而未随结果返回，请在本轮一并明确。

## Inputs

固定评审范围（`AGENTS.md` §3.6，只用已提交 SHA，不移动 `HEAD`）：

- `base_sha`: `0bea9c084b8209b19113b169eaf152ab33455884`
- `delivery_sha`: `567d61b4dbef91d23ceb923c4137745427fc3cf1`
- 区间差异: `git diff 0bea9c0..567d61b`

按 `AGENTS.md` §4 顺序读取：

1. `AGENTS.md`；
2. 本 dispatch；
3. `reports/agent-runs/ACTIVE.json`；
4. `PROJECT_STATE.md`（`567d61b` 版）；
5. 本阶段 `status.json`；
6. `agents/roles.md` 的 `Reviewer` 段（按需查 `Bookkeeper` 段的
   `Minimal State And Dispatch Shape`、`Task State Vocabulary`）；
7. `agents/skills/code-reviewer.md`；
8. **本轮受审主体 —— 设计勘误**：
   `git show 567d61b:reports/agent-runs/2026-07-harness-v2-trial-hardening-v1/20-opus5-design.md`
   的"勘误 1 — 2026-07-30"整节（`E1`–`E8`）；其上文 §0–§10 为对照原文，按需回看；
9. `22-bookkeeper-design-verification.md` 的 §8（十条 Human 决定原文）、§8.2（逐条处置）、
   §11（本次落盘、核验与返工记录）；
10. `41-grok45-plan-review-1-raw.md`（你上一轮的原始结论及 Bookkeeper 的三条落盘备注，
    其中备注 3 写明了 Bookkeeper 对"F1"的理解口径，请核对是否曲解）；
11. 仅在需要证实或否证某条结论时，读取该结论自身点名的源文件行区间或 Git 对象。

**须知**：设计正文由更早的提交 `128e564` 引入，早于 `base_sha`，因此正文不在区间内；
本轮区间内的是勘误、原始结论落盘文件与 `22` 的 §11。按第 8 项以 `567d61b` 的树读取
设计全文，读取仍然确定、可复现。

`reports/agent-runs/_proposals/` 是草稿，按 Human 决定第 9 条不得作为正式证据。

## Acceptance Checks

逐项给出结论与证据：

1. **勘误形态合规**：设计 §0–§10 是否逐字未改；勘误是否为纯追加；`git show 567d61b
   --numstat` 对 `20-opus5-design.md` 是否为零删除。
2. **对应你上一轮第 1 项（十条一致性 FAIL）**：`E1` 是否把被 Human 否决的条目全部作废
   并指明现状态——检查器与其测试、`decisions.md`、第四状态 `rejected`、32KB 阈值、模型
   启动文档、清理作业、§10 九项待决。文中是否还残留依赖这些被否机制的推论。
3. **对应你上一轮第 2 项（`G1`/`G14` 须标残留）**：`E2` 是否明确写明问题仍为 OPEN、
   批次 A 只剩措辞手段、把关点是 Bookkeeper 的注意力而非机器；批次 A 的验收检查是否
   真的包含"交付后仍标记为 OPEN"一条；有无任何"已解决/已闭合"的措辞构成**伪关闭**。
   这一条判定从严。
4. **对应你上一轮第 3 项（批次 B 仍写 `decisions.md`）**：`E4` 是否删除了该行；`G5` 的
   新落点（`roles.md` 一句，临时决定入本阶段 Bookkeeper 核验记录、长期决定入
   `docs/planning/DECISIONS.md`）是否不新增文件、不新增字段、不制造第二权威。
5. **对应你上一轮第 4 项（拒收落盘弱）**：`E5` 的四步（保持 `reported`、写核验记录、
   写具名 `blockers`、后续修复递增 `rework_count`）是否可执行、可核验；`reported` 与
   `verified` 的语义是否与 `agents/roles.md` 的三态定义一致；拒收能否被改名或拆分任务
   藏住。
6. **批次自洽性**：`E3`/`E4` 重定义后，批次 A 的 Allowed Files 是否已彻底移除
   `scripts/**` 且本批次不新增任何文件；两批次是否仍不互相覆盖同一节文字；作废的测试
   与验收条目是否已有替代。
7. **新引入的矛盾**：勘误与设计原文、与十条决定、与 `AGENTS.md` §2 单一权威之间是否
   出现新的冲突；`E4` 中 `PROJECT_STATE.md` 仅余 4 字节的同批淘汰约束是否可执行。
8. **`rework_count` 判定**：Bookkeeper 判定本轮不递增（交付前计划评审，适用
   `AGENTS.md:182` 的 pre-dispatch 豁免与 Human 决定第 4 条"已交付后"限定）。核验该判定
   是否成立，或指出它是否为一次不当的宽松解释。
9. **回执缺陷的处理是否恰当**：`41-…-raw.md` 备注 2、3 记录了"足以推进"的判定与对"F1"
   的理解口径。核验该判定是否滥用了 Human 决定第 1 条赋予 Bookkeeper 的裁量权。

结论只允许 `ACCEPT` 或 `REWORK`。`REWORK` 必须给出具体、可执行的修复要求。若仅剩非阻塞
性观察，请给 `ACCEPT` 并把观察写进 `问题记录`，按 `G18` 三分类标注其是否属范围外。

## Stop

按 `AGENTS.md` §7 返回完整中文 `[TASK_RESULT v2]`，并附评审闭包三行
（`评审结论` / `问题记录` / `修复要求`），以 `[/TASK_RESULT]` 作为最后一个非空白输出，
其后不得有任何文字。

下一步行动者是 Human：由 Human 把你的原始结果转交本阶段 Bookkeeper `opus5` 同步。
你不得准备 review-2 包、不得准备实现包、不得启动或指派任何模型。实施闸门保持关闭，
须本轮 `ACCEPT` 且 Human 再次授权后方可开启。

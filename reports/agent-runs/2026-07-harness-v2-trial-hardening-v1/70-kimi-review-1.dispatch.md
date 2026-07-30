# Harness v2 Trial Hardening — 批次 A review-1 (Kimi)

## Identity

- task_id: `harness-v2-trial-hardening-batch-a-review-1-kimi`
- target_role: `Reviewer`
- target_model: `kimi`
- provider: `moonshot`
- status_revision: `13`
- required_skill: `agents/skills/code-reviewer.md`

## Goal

对批次 A 的 Harness 契约改动做 review-1。受审交付是对 `AGENTS.md` §7/§8 与
`agents/roles.md` 三个子节的 15 行新增，实现者为 `claude_glm`（provider `zhipu_glm`）。
你的 provider 是 `moonshot`，跨 provider 独立性成立。

这是**契约文本评审，不是代码评审**：判断规则本身是否可执行、是否留有绕过口子、是否
制造重复权威、是否削弱既有保留项。

### 必须独立复核的两项（Bookkeeper 自陈的薄弱点）

**S1 —— 一次 `contested` 裁定，裁决者不独立。** 实现者依据本次新增的
`Acceptance-Check Verdict States` 机制，质疑 dispatch 中"两契约文件字节和增量 ≤1536"
这条验收检查；Bookkeeper 裁定**采信**（即承认自己写的检查是错的）。写下该检查的人与
裁定该质疑的人是同一个 Bookkeeper（`opus5`）。请独立判断：该裁定是否成立，是否属于
"把定义放宽到检查变绿"。

**S2 —— 被替换掉的 W1 守卫。** 采信后，Bookkeeper 删除了该字节上限，并**未另设新数字**，
改为：结构检查（启动读取项仍为九项）+ 据实记录实测长度并说明理由（依据 `AGENTS.md:61`
"target… may exceed with a recorded reason"）。请判断 W1（启动路径廉价）是否因此被实质
削弱；若你认为削弱成立，请给出可执行的替代守卫。

两项的完整论证见 `22-bookkeeper-design-verification.md` §16.2 与 §16.3。**你可以否决
其中任何一条。**

## Allowed Files

无。本次为只读评审会话。

不得创建或修改任何文件，不得 `git add`/`commit`/`merge`/`rebase`/`push`，不得移动
`HEAD` 或改动工作树，不得启动、调用或指派其他模型，不得访问凭据或执行任何实盘动作。

本包**预先指定**你的原始输出归档路径为
`reports/agent-runs/2026-07-harness-v2-trial-hardening-v1/71-kimi-review-1-raw.md`；
若结论为 `REWORK`，`问题记录` 与 `修复要求` 均填写该路径，并把完整发现与可执行修复要求
写在返回结果正文中，由 Human 转交 Bookkeeper 落盘。你自己不要创建该文件。

**回执格式请求**：此前五份模型回执中有四份在传输中受损（换行压平，一次伤及字符）。当前
无任何机制校验回执格式（这正是本批次仍标记为 OPEN 的 `G1`/`G14` 残留）。请把每个标签
单独成行输出。

## Inputs

固定评审范围（`AGENTS.md` §3.6，只用已提交 SHA，不移动 `HEAD`）：

- `base_sha`: `c6f23f690599799f5f7c55b004bc4b1cb5039a0d`
- `delivery_sha`: `41387b440758e9b19aa1333a0c76dcfe8e28d5ec`
- 受审差异：`git diff c6f23f6..41387b4 -- AGENTS.md agents/roles.md`（共 15 行新增、
  0 行删除）

**范围口径**（本次交付新写入的 §8 规则，现场适用）：区间内还包含本阶段自身的控制提交
（`60-` dispatch 与 `status.json` revision 12）。它们是上下文而非受审交付。

按 `AGENTS.md` §4 顺序读取：

1. `AGENTS.md`（`41387b4` 版）；
2. 本 dispatch；
3. `reports/agent-runs/ACTIVE.json`；
4. `PROJECT_STATE.md`；
5. 本阶段 `status.json`；
6. `agents/roles.md` 的 `Reviewer` 段（并通读被改动的三个子节）；
7. `agents/skills/code-reviewer.md`；
8. **实施依据**：`60-batch-a-gates-glm.dispatch.md` 的 `Acceptance Checks` 一节
   （A1–A10 与八项核验）；
9. **实现者报告**：`61-batch-a-result.md`；
10. **Bookkeeper 核验与裁定**：`22-bookkeeper-design-verification.md` §16（全节），
    以及 §12.3（`O1`）、§14.2（`O4` 权威两句）、§8（十条 Human 决定）；
11. 设计与其勘误：`20-opus5-design.md` 的 §3、§5 与末尾"勘误 1"（`E1`–`E8`），
    冲突处以勘误为准；
12. 仅在需要证实或否证某条结论时，读取该结论点名的源文件行区间或 Git 对象。

不要扫描已完成阶段、产品源码、运行时数据、凭据或 `reports/agent-runs/_proposals/`
（后者按 Human 决定 9 是草稿，不得作为证据）。

## Acceptance Checks

逐项给出结论与证据：

1. **A1–A10 是否真的落地**。逐条对照 `60-` 的 A1–A10 与实际 diff：十条规则是否都在、
   是否有被削弱或悄悄改写的要点。特别检查 A3 的三项配套条款（`base_sha` 证据门槛、
   不新增第三个 verdict 值、Human 豁免的五要件与"仅限本次合并"）是否完整。
2. **单一权威**（`AGENTS.md` §2）。§7/§8 与 `roles.md` 三个子节之间是否出现字段清单、
   枚举集合、数值限额或完整工作流的复制；跨文件是否只用指向。A1 引用 `roles.md` 勘误
   判据、A8 把计数后果指向 §8、A5 指向既有豁免、A9 声明不重述——这四处指向是否成立且
   无歧义。
3. **规则可执行性与绕过口子**。给出你能想到的最省事的绕过路径并判断是否被堵住：
   - `rework_count` 的"绑交付物、改名或拆分不清零"——还能被怎么绕？
   - 三分类的 `base_sha` 证据门槛——能否把范围内缺陷贴成 `pre-existing`？
   - `contested` 三态——能否让一个失败的闸门静默通过？
   - 同根因刹车的"连续两轮"——能否靠改写根因描述规避？
4. **`S1`（见 Goal）**：`contested` 采信裁定是否成立。
5. **`S2`（见 Goal）**：W1 是否被实质削弱；若是，给出可执行替代守卫。
6. **保留项未被伤及**：`status.json` 顶层仍 13 字段（`W3`）；`current_task.state` 仍
   恰好三值、未出现第四态；dispatch 仍六节（`W5`）；`AGENTS.md` §4 启动读取项仍九项
   （`W1` 结构部分）；`base_sha` 定义未被改动（其权威在 `roles.md` SHA Discipline）。
7. **`G1`/`G14` 未被伪关闭**：交付只增加了措辞约束、未增加任何机制，`61-` 报告是否
   明确声明其仍为 OPEN；`AGENTS.md` §7 新增措辞是否被写成"已解决"的口吻。
8. **边界与纪律**：`git show --stat 41387b4` 是否只含 `AGENTS.md`、`agents/roles.md`、
   `61-batch-a-result.md`；`status.json` 是否未被实现者改动；有无新增其他文件。
9. **`O1`–`O4` 是否被正确执行**：`O1`（以 `E5` 四步为准，拒收保持 `reported`）、
   `O2`（`W6` 扫描的证明范围被正确陈述）、`O3`（本项已被 `S1` 取代，核验取代过程本身）、
   `O4`（勘误判据是否逐字写入且计数后果落在 §8）。

结论只允许 `ACCEPT` 或 `REWORK`。`REWORK` 必须给出具体、可执行的修复要求。若仅剩非阻塞
观察，请给 `ACCEPT` 并把观察写进 `问题记录`，按新写入的三分类标注其是否属范围外。

## Stop

按 `AGENTS.md` §7 返回完整中文 `[TASK_RESULT v2]`，并附评审闭包三行
（`评审结论` / `问题记录` / `修复要求`），以 `[/TASK_RESULT]` 作为最后一个非空白输出，
其后不得有任何文字。

下一步行动者是 Human：由 Human 把你的原始结果转交本阶段 Bookkeeper `opus5` 同步。
你不得准备 review-2 包、不得进入批次 B、不得启动或指派任何模型。

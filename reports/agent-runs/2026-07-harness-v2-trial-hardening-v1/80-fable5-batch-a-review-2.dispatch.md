# Harness v2 Trial Hardening — 批次 A review-2 (Fable5)

## Identity

- task_id: `harness-v2-trial-hardening-batch-a-review-2-fable5`
- target_role: `Reviewer`
- target_model: `fable5`
- provider: `anthropic`
- status_revision: `15`
- required_skill: `agents/skills/reality-checker.md`

## Goal

对批次 A 的 Harness 契约改动做终审（review-2）。review-1 已由 Grok 4.5（`xai`）返回
`ACCEPT`、`修复要求: none`。

review-2 与 review-1 职责不同（`AGENTS.md` §8）：不重做规则的逐条比对，而是判断
**需求是否被真正满足、实际效果、证据是否成立、运营风险、以及是否具备放行条件**。

本批次的总问题：

> 这十五行规则一旦生效，下一个真实阶段会不会照着它跑？还是会在忙的时候被绕开或忘掉？

### 独立性披露

- 本次实现作者是 **`claude_glm`**，provider `zhipu_glm`。你是 `anthropic`，**跨 provider
  隔离成立**（`agents/roles.md:123-124`）。
- 但请注意：本批次所依据的**设计**作者是 Opus 5（`anthropic`），与你同 provider；且
  **你已评审过该设计**（设计阶段的 review-2，`ACCEPT`）。这是 Human 决定 8 的明确选择。
  `roles.md:123-124` 的同 provider 禁令针对"评审同 provider 作者的**实现**"，本次实现
  作者是 `zhipu_glm`，故不被触发；`roles.md:126-127` 的披露义务照常适用，在此写明。
- 因此请刻意反查你**倾向于认同**的判断：这套规则的设计你已经点过头，容易顺势认为落地也
  没问题。

### 必须独立判断的四项残余

review-1 明确判为"残余观察"而非阻塞的三项，加上一项贯穿始终的：

- **`R1` 无硬字节刹。** 原设计的"契约文件增量 ≤1.5 KB"被 Bookkeeper 采信实现者的
  `contested` 后删除，未另设数字，改为结构检查（启动读取项仍九项）加据实记录
  （`AGENTS.md` 12,744 → 16,587，+30%；启动集合计 18,683 字节）。Grok 判 W1 结构未伤。
  **请独立判断该增长的实际代价，并明确说：还需不需要一个刹车？**
- **`R2` 同根因由散文判定。** "连续两轮 `REWORK` 归因于同一根因"由评审者在 `问题记录`
  中命名、Bookkeeper 原样引用，没有机器判据。**能否靠改写根因描述规避这道刹车？**
- **`R3` 裁决者不独立（`O7`）。** `contested` 的裁决人可能正是写下那条错误验收检查的
  Bookkeeper——本阶段已真实发生一次（`22-` §16.2）。Grok 判其裁定成立，但结构弱点仍在。
  **是否需要在批次 B 处理，还是可长期接受？**
- **`R4` `G1`/`G14` 仍为 OPEN。** 本批次只加措辞、无任何机制（Human 决定 1、11 知情
  接受）。至今**六份模型回执中五份在传输中受损**（五次换行压平、一次伤及字符、两次
  "只给编号不给正文"、一次 `产物` 字段误用）。**请判断这个残留在下一个真实阶段的风险。**

**你可以否决上述任何一项的现有处置**，包括推翻 Bookkeeper 的 `contested` 采信裁定。

## Allowed Files

无。本次为只读评审会话。

不得创建或修改任何文件，不得 `git add`/`commit`/`merge`/`rebase`/`push`，不得移动
`HEAD` 或改动工作树，不得启动、调用或指派其他模型，不得访问凭据或执行任何实盘动作。

本包**预先指定**你的原始输出归档路径为
`reports/agent-runs/2026-07-harness-v2-trial-hardening-v1/81-fable5-batch-a-review-2-raw.md`；
若结论为 `REWORK`，`问题记录` 与 `修复要求` 均填写该路径，并把完整发现与可执行修复要求
写在返回结果正文中，由 Human 转交 Bookkeeper 落盘。你自己不要创建该文件。

**回执格式请求（有实测理由）**：`产物` 字段用于列出**你产生的产物**——只读评审应为
`[none]`，不要列输入。若有编号的观察项，请把每条正文一并写出：此前 `F1` 与 `O2`–`O8`
两次"只给编号不给正文"，其中一次导致 Bookkeeper 重建映射出错、需你事后更正。请把每个
标签单独成行输出。

## Inputs

固定评审范围（`AGENTS.md` §3.6，只用已提交 SHA，不移动 `HEAD`）：

- `base_sha`: `c6f23f690599799f5f7c55b004bc4b1cb5039a0d`
- `delivery_sha`: `41387b440758e9b19aa1333a0c76dcfe8e28d5ec`
- 受审差异：`git diff c6f23f6..41387b4 -- AGENTS.md agents/roles.md`（15 行新增、0 行删除）

**范围口径**（本次交付新写入的 §8 规则，现场适用）：区间内还包含本阶段自身的控制提交
（`60-` dispatch 与 `status.json` revision 12）。它们是上下文而非受审交付。

按 `AGENTS.md` §4 顺序读取：

1. `AGENTS.md`（`41387b4` 版，重点已改动的 §7 与 §8）；
2. 本 dispatch；
3. `reports/agent-runs/ACTIVE.json`；
4. `PROJECT_STATE.md`；
5. 本阶段 `status.json`；
6. `agents/roles.md` 的 `Reviewer` 段（并通读被改动的三个子节）；
7. `agents/skills/reality-checker.md`；
8. **实施依据**：`60-batch-a-gates-glm.dispatch.md` 的 `Acceptance Checks`；
9. **实现者报告**：`61-batch-a-result.md`；
10. **review-1 原始结论**：`73-grok45-batch-a-review-1-raw.md`；
11. **Bookkeeper 核验、`contested` 裁定与勘误**：
    `22-bookkeeper-design-verification.md` §16、§17，以及 §8（十条 Human 决定）、
    §12.3（`O1`）、§14.2（`O4`）、§15（决定 11）；
12. 设计与其勘误：`20-opus5-design.md` 的 §3、§5 与"勘误 1"；
13. 问题来源：`docs/planning/harness-v2-trial-findings-2026-07-30.md`；
14. 仅在需要证实或否证某条结论时，读取该结论点名的源文件行区间或 Git 对象。

不要扫描已完成阶段、产品源码、运行时数据、凭据或 `reports/agent-runs/_proposals/`。

## Acceptance Checks

逐项给出结论与证据：

1. **需求是否被真正满足。** 对照 findings 中 Human 被迫亲自介入的那几个时刻
   （`G2` 计划评审、`G15` 拒收无路由、`G16` 错误验收标准、`G18` 既存缺陷阻塞交付、
   `G12` 同根因反复点补丁），逐一判断这十五行是否真的给出了出路。哪一条只是写在纸上？
2. **实际效果的现场证据。** 本阶段自身已经运行过其中三条：`G16` 的 `contested`（实现者
   真的用它顶回了一条错检查）、`G15`/`O4` 的计数口径（返工发生在交付前故未计数）、
   `G9(b)` 的不可用性记录（Kimi 回退 Grok 未再要豁免）。**这些现场运行是否证明规则可用，
   还是只证明当事人足够细心？**
3. **`R1`–`R4` 四项残余**（见 Goal）。逐项给出"可接受 / 需在批次 B 处理 / 现在就必须
   处理"的判断与理由。
4. **运营负担与被跳过的风险。** 这十五行给 Bookkeeper 与评审者各增加了多少每阶段固定
   动作？哪一条在忙碌阶段最可能被第一个跳过？（`blame` 核验？三分类标注？根因命名？）
5. **规则文本本身的可理解性。** 新增内容是长段中文夹在英文契约中。一个冷启动的新模型
   读 `AGENTS.md` §7/§8 后，能否不追问就照做？有无歧义句。
6. **单一权威与最小化**（`AGENTS.md` §2）。跨文件四处指向（A1→`roles.md` 勘误判据、
   A8→§8 计数、A5→既有豁免、A9→§8 分类）是否成立且无循环引用。
7. **保留项**：`W1`（启动路径廉价，结合 `R1`）、`W3`（13 字段）、`W5`（六节 dispatch）
   是否实质完好。
8. **放行判断。** 本批次是否具备"可以由 Human 决定合并"的成熟度？若否，缺的是哪一件
   具体的东西？

结论只允许 `ACCEPT` 或 `REWORK`。`REWORK` 必须给出具体、可执行的修复要求。若仅剩非阻塞
观察，请给 `ACCEPT` 并把观察写进 `问题记录`，按新写入的三分类标注其是否属范围外。

**注意**：你的 `ACCEPT` **不构成合并授权**。合并到 `main` 须 Human 明确授权
（`AGENTS.md` §3.1、§9）；批次 B 与 `G11` 目录清理亦未获授权。

## Stop

按 `AGENTS.md` §7 返回完整中文 `[TASK_RESULT v2]`，并附评审闭包三行
（`评审结论` / `问题记录` / `修复要求`），以 `[/TASK_RESULT]` 作为最后一个非空白输出，
其后不得有任何文字。

下一步行动者是 Human：由 Human 把你的原始结果转交本阶段 Bookkeeper `opus5` 同步。
你不得准备批次 B 包、不得启动或指派任何模型。

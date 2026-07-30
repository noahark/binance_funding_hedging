# Harness v2 Trial Hardening — Review 2 (Fable5)

## Identity

- task_id: `harness-v2-trial-hardening-review-2-fable5`
- target_role: `Reviewer`
- target_model: `fable5`
- provider: `anthropic`
- status_revision: `8`
- required_skill: `agents/skills/reality-checker.md`

## Goal

对 Harness v2 试运行加固**设计**做终审（review-2）。review-1 已由 Grok 4.5（`xai`）在
第二轮返回 `ACCEPT`，`修复要求: none`。

review-2 的职责与 review-1 不同（`AGENTS.md` §8）：不重做代码与契约的逐条核对，而是判断
**需求是否被真正满足、实际效果、证据是否成立、运营风险、以及是否具备放行条件**。具体到
本阶段，请回答一个总问题：

> 这份设计一旦实施，是否真的能减少 Human 在下一个产品阶段被迫亲自介入的次数？还是只是
> 把规则写得更漂亮？

### 必须披露的独立性事实

- 本设计的作者是 **Opus 5**，provider `anthropic`。
- **你（Fable5）与作者同属 `anthropic` provider。** 这是 **Human 的明确选择**
  （2026-07-30 决定第 8 条，原文见 `22-bookkeeper-design-verification.md` §8）。
- **你不替代** Grok 4.5 已完成的跨 provider 独立初审；跨 provider 把关由那一轮承担。
- `agents/roles.md:122-124` 的同 provider 禁令针对的是"评审同 provider 作者的**实现**"。
  本阶段尚无任何实现交付，受审对象是设计文档，故不触犯该禁令；但
  `roles.md:126-127` 的披露义务照常适用，故在此写明。

请在你的评审结论中据此把握尺度：你与作者同源，容易产生共识偏差，请刻意去找你**倾向于
认同**的那些判断里的弱点。

## Allowed Files

无。本次为只读评审会话。

不得创建或修改任何文件，不得 `git add`/`commit`/`merge`/`rebase`/`push`，不得移动
`HEAD` 或改动工作树，不得启动、调用或指派其他模型，不得访问凭据、操作服务或执行任何
实盘动作。

本包**预先指定**你的原始输出归档路径为
`reports/agent-runs/2026-07-harness-v2-trial-hardening-v1/51-fable5-review-2-raw.md`。
若结论为 `REWORK`，`问题记录` 与 `修复要求` 均填写该路径，并把完整发现与可执行修复要求
写在返回结果正文中，由 Human 转交 Bookkeeper 落盘。你自己不要创建该文件。

**回执格式请求**：前两轮评审的原始输出在传输中换行被压平，标签连成一行。当前 v2 无任何
机制校验回执格式（这正是本设计中标记为 OPEN 的 `G1`/`G14` 残留）。请把每个标签单独成行
输出。

## Inputs

固定评审范围（`AGENTS.md` §3.6，只用已提交 SHA，不移动 `HEAD`）：

- `base_sha`: `0bea9c084b8209b19113b169eaf152ab33455884`
- `delivery_sha`: `2fb1d47edfb2c34065f37c34d425516ea582f1b6`

按 `AGENTS.md` §4 顺序读取：

1. `AGENTS.md`；
2. 本 dispatch；
3. `reports/agent-runs/ACTIVE.json`；
4. `PROJECT_STATE.md`（`2fb1d47` 版）；
5. 本阶段 `status.json`；
6. `agents/roles.md` 的 `Reviewer` 段；
7. `agents/skills/reality-checker.md`；
8. **受审设计全文（含勘误）**：
   `git show 2fb1d47:reports/agent-runs/2026-07-harness-v2-trial-hardening-v1/20-opus5-design.md`
   ——§0–§10 为原文，末尾"勘误 1 — 2026-07-30"（`E1`–`E8`）为有效修正，冲突处以勘误为准；
9. `22-bookkeeper-design-verification.md` 全文，重点 §8（十条 Human 决定原文）、§8.2、
   §11（第一轮 `REWORK` 与返工）、§12（第二轮 `ACCEPT` 与观察项 `O1`）；
10. 两轮 review-1 原始结论：`41-grok45-plan-review-1-raw.md`、
    `43-grok45-plan-review-1-r2-raw.md`；
11. 问题来源：`docs/planning/harness-v2-trial-findings-2026-07-30.md`（`2fb1d47` 版，
    含 D-9 原文与其后追加的 Human update）；
12. 仅在需要证实或否证某条结论时，读取该结论自身点名的源文件行区间或 Git 对象。

不要扫描已完成阶段、无关产品源码、运行时数据、仓库外文件或凭据。
`reports/agent-runs/_proposals/` 是草稿，按 Human 决定第 9 条不得作为正式证据。

## Acceptance Checks

逐项给出结论与证据：

1. **需求是否被满足。** Human 要的是"少被迫亲自介入"。逐一对照上一个产品阶段中 Human
   实际被迫介入的时刻（`G2` 的计划评审、`G15` 的拒收无路由、`G16` 的错误验收标准、
   `G18` 的既存缺陷阻塞交付、`G17` 的中途决策无处安放），判断本设计实施后这些时刻是否
   真的不再需要 Human。哪一条只是换了个说法？
2. **`G1`/`G14` 残留的真实代价。** Human 已否决检查器，设计把该缺口明确标为 OPEN
   （`E2`）。请独立判断：仅靠 Bookkeeper 人工核验，这个洞在下一个阶段会不会再被踩中？
   前三次评审回执的换行在传输中被压平，是否已经构成"再次踩中"的早期信号？如果你认为
   残留不可接受，请直接说明并给出 Human 可以接受的最小替代（注意：不得建议恢复被否决
   的脚本方案，除非你能给出让 Human 改变主意的新证据）。
3. **可实施性。** 批次 A（一次 `AGENTS.md` §8 编辑 + §7 措辞 + `roles.md` 三处）与
   批次 B 的边界、非目标、验收检查，是否足以让一个实现者在不追问的情况下动手？哪一条
   验收检查实际上无法执行？
4. **顺序与阻塞风险。** `E4` 记录 `PROJECT_STATE.md` 仅余 4 字节，要求淘汰规则、残留
   登记与一次实际淘汰同批完成。这个约束现实吗？若批次 B 因此卡住，批次 A 是否会被拖住？
5. **规则被绕过的可能。** 重点看三处：`rework_count` 的"改名/拆分不清零"、`G18` 三分类
   的证据门槛（是否可能把范围内缺陷贴成既存）、`contested` 验收检查（是否可能让失败的
   闸门静默通过）。请给出你能想到的最省事的绕过路径，以及设计是否堵住了它。
6. **是否引入新的运营负担。** 本设计给 Bookkeeper 增加了多少每阶段固定动作？是否有哪一
   条在忙碌阶段会被第一个跳过？
7. **单一权威与最小化**（`AGENTS.md` §2）。是否出现字段清单、枚举、数值限额或完整工作流
   的复制；是否有被 v2 删除的 workflow YAML、registry、verdict schema、adapter runbook、
   monolithic validator 的任何形式回归。
8. **与十条 Human 决定的最终一致性**，特别是 `O1`（`E1` 写"采用方案 B"而 `E5` 规定拒收
   保持 `reported`）的处置是否恰当——Bookkeeper 选择不改动已 `ACCEPT` 的产物，而是把
   澄清写入将来的实现 dispatch。这个处置是否会让实现者读到自相矛盾的设计？
9. **放行判断。** 综合以上，本设计是否具备"可以授权进入实现"的成熟度？若否，缺的是哪
   一件具体的东西？

结论只允许 `ACCEPT` 或 `REWORK`。`REWORK` 必须给出具体、可执行的修复要求。若仅剩非阻塞
观察，请给 `ACCEPT` 并把观察写进 `问题记录`，按 `G18` 三分类标注其是否属范围外。

**注意**：你的 `ACCEPT` **不解除实施闸门**。按 Human 决定第 3 条，进入实现仍需 Human
再次授权；你的结论是该授权的输入，不是替代。

## Stop

按 `AGENTS.md` §7 返回完整中文 `[TASK_RESULT v2]`，并附评审闭包三行
（`评审结论` / `问题记录` / `修复要求`），以 `[/TASK_RESULT]` 作为最后一个非空白输出，
其后不得有任何文字。

下一步行动者是 Human：由 Human 把你的原始结果转交本阶段 Bookkeeper `opus5` 同步。
你不得准备实现包、不得启动或指派任何模型。

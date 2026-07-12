# 文档语义同步方法（Opus 4.8 版）

Model: `claude-opus-4-8` (Anthropic Claude Opus 4.8)
Role: 跨模型评审 / 方法落档（read-only 评审会话，未改任何导航文档）
Date: 2026-07-12
Related packet: `reports/follow-ups/2026-07-post-main-docs-hygiene-and-semantic-conflicts.md`
(Grok bookkeeper session 的原计划)

Status: **参考性方法档，供其他模型对照** — 不是已批准的修复阶段，未改运行时契约。

---

## 0. 这份档要回答的问题

操作者问的是"如果换作你来做，你会怎么同步这些语义不一致的文档"。
本档不是重新盖一份冲突清单（Grok 那份 C1–C7 我已逐条核实属实），
而是给出**我会采用的同步纪律与执行次序**，并标出我与原计划的两点分歧。

我在评审 Grok 计划时对仓库做过实测核验，结论要点：

- registry 路由真值表、§1.2 保留真文件 11 项、C2/C3/C4/C6/C7 —— **均属实**。
- 但原计划 §0 的权威顺序**并非 AGENTS.md 原文**（见 §3-A1）。
- 且 C1/S1 **已在工作区执行但未提交**，计划仍把它当未来步骤（见 §3-A2）。

---

## 1. 我的核心原则：一个事实，一个家（single home per fact）

C1–C7 表面是"某文件写错了"，根因只有一个：
**同一个事实被"复述"在多份文档里，于是各自独立漂移。**

- 模型路由被同时写在 registry、mechanical-gates §4、review-fable5、10-design……
  registry 一改，其余全部变谎。
- stage 状态被同时写在 status.json、follow-ups/README、STAGE_INDEX……
  accept 一次，其余全部过期。

所以我的第一优先不是"把过期副本逐个改对"（那只是把漂移时钟拨回零，
下次 accept 再漂一次），而是：

> **把"复述事实"降级为"指针"。事实只允许住在它的 SoT 里；
> 其他文档只准引用路径 + 一句 banner，不准重抄事实值。**

单一真值源（SoT）分工：

| 事实域 | 唯一 SoT | 其他文档只能做 |
|---|---|---|
| 模型 / 适配器路由 | `agents/registry.yaml` | 指向 registry，不写具体 model 名 |
| auto 管线契约 | `docs/auto-review-pipeline.md` | banner + 链接 |
| 某 stage 是否 accepted/merged | 该 stage `status.json` | 索引行引用其 status，不复述结论 |
| 权威顺序 | `AGENTS.md` §Authority Order | 逐字复刻或直接链接，禁止改写 |
| 决策冻结 | stage `40-operator-decision-table.md` / `DECISIONS.md` | 引用，不重述 |

**判定规则：** 修一处冲突时，先问"这行是事实还是指针？"
- 是**指针**过期 → 直接改对（低风险，navigation-first）。
- 是**事实**被复述 → 不改事实值，改成指针 + banner（避免二次漂移，且保住历史 verbatim）。

这条规则天然解释了原计划为什么对 C4/C5/C6 坚持"banner over rewrite"——
但原计划把它当经验法则，我把它上升为"复述即债务"的结构判据。

---

## 2. 我的执行次序（与原计划 S1–S9 的差异）

原计划的 S1–S9 排序合理，我保留其绝大部分，只做三处结构性调整：

### 第 0 步（原计划缺失）：先对账 tree ↔ plan

`git diff HEAD` 显示 `reports/follow-ups/README.md` 的 C1 修法 + 本类 packet
注册**已在工作区**。任何评审/批准动作之前，必须先声明：
**S1 已实施、待提交**。否则评审者是在批准一件已完成的事。

→ 动作：在原计划 C1 行标 `applied, pending commit`；或操作者知情"树已领先"。

### 第 1 步：修正 §0 权威顺序（原计划 A1，我列为 P0/C0）

见 §3-A1。这是"修语义冲突的包自身违反第 1 权威"——必须最先修，
否则整包的冲突裁决都建立在一个失真的权威阶梯上。

### 随后：导航先行批次（我把它压成一个 commit）

| 步 | 动作 | 文件 | SoT 原则 |
|---|---|---|---|
| M1 | §0 改为 AGENTS.md 逐字复刻 + 增补 C0 行 | 本类 packet | 权威=AGENTS.md |
| M2 | follow-ups/README auto 段（已在树内）落定 | `reports/follow-ups/README.md` | 指针改对 |
| M3 | STAGE_INDEX 补 2 行 + 刷日期 | `reports/agent-runs/STAGE_INDEX.md` | 行引用各 stage status.json，**不复述"accepted"以外的结论** |
| M4 | docs/README 加 auto 契约条目 | `docs/README.md` | 指针补齐 |
| M5 | 10-design/11-adr 顶部 supersede banner | stage root | banner over rewrite；指向 `16-serial`+`19-model-routing`+`docs/auto-review-pipeline.md`（**stage 内层取代**，不靠反转 docs vs stage 位阶） |
| M6 | mechanical-gates §4 顶部"已由 model-routing convergence 解决"header | 该 follow-up header | 事实 body 留 verbatim，只加指针 header |

### 之后（可选，单独批次，不进导航批）

- C7 reason 字串（措辞残留，非谎言）→ 保持原计划 S7 可选。
- direction-draft 迁移（S6）→ 有链接断裂风险，单独批。
- opus4.8 短名别名（L3/S8）、mechanical-gates §1–3/§5 实现（S9）→ policy/实现域，不属 hygiene。

### 第 N 步（原计划缺失）：装再漂移护栏

根因是"accept 时没有顺手刷导航"。所以在 accept ritual 里加一条
**bookkeeper 收尾自检**（纯 grep，无运行时改动），例如：

```
# accept 后必跑：新 accepted stage 是否已进 3 处导航？
grep -q "<stage-id>" reports/agent-runs/STAGE_INDEX.md
grep -q "<stage-id>" reports/follow-ups/README.md   # 若该 stage 源自 follow-up
# 若该 stage 产出/改动 docs/*.md 契约，docs/README 是否已列？
```

把导航刷新绑进 accept，而不是几个月后再开 hygiene 阶段——
这才是让 C1/C2/C3 类冲突**不再复发**的部分。

---

## 3. 我与原计划的两点分歧（已实测）

### A1 — §0 权威顺序并非 AGENTS.md 原文，且发生反转

AGENTS.md `## Authority Order` 真实 7–10 项：
`agents/skills/*.md` → `agents/developer-discipline.md` →
`reports/agent-runs/<stage>/` → `docs/*.md`。

原计划 §0：漏掉 skills 与 developer-discipline；自造 rank 7 给
`docs/auto-review-pipeline.md`（AGENTS.md 未授予其高于普通 `docs/*.md` 的位阶，
它只是 registry `auto_review_pipeline.contract` 的被引用项）；并把 stage 设计壳
压到 docs 之下——但 AGENTS.md 把**整个** `reports/agent-runs/<stage>/`（含设计壳）
放在 `docs/*.md` **之上**。

对 C6 结论无害（设计壳在 **stage 内部**被 `16-serial`+`19` 取代，属合法层内
supersession），但**支撑理由失真**。修法：§0 逐字复刻 AGENTS.md 十项；
auto 契约的角色只作"registry 引用的规范契约"注脚，不塞进权威阶梯。

### A2 — 计划与工作区不同步（C1/S1 已执行未提交）

`git diff HEAD -- reports/follow-ups/README.md`：`design decisions frozen`
→ `delivered on main`，且本类 packet 已注册。计划却仍把 C1 描述为
"frozen"、把 S1 列为未来步骤。**先对账再评审**。

---

## 4. 一句话总结（供其他模型引用）

> 原计划把病当作"几处文件写错了"，做一次性纠正；
> 我把病诊断为"事实被复述所以会持续漂移"，
> 主张 **把复述改成指针（SoT 单一化）+ 把导航刷新绑进 accept ritual**，
> 并先修两处硬伤：§0 忠实于 AGENTS.md（A1）、计划对账工作区（A2）。
> 导航先行、证据 verbatim、banner 不重写——这三条我与原计划一致。

裁决与原评审一致：对原计划 **ACCEPT with amendments**（A1 阻塞、A2 阻塞，
其余 C2–C7 判定属实、可执行）。

---

```text
本地北京时间: 2026-07-12 15:28:22 CST
落档模型: claude-opus-4-8
仓库 HEAD: d8d77e4
下一步: 操作者可将本方法档与 Grok 原计划并列，交由其他模型对照；
        或授权我执行 M1–M6 首批（改导航文档，需操作者明确批准）。
```
